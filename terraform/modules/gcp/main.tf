terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# ── Provider ──────────────────────────────────────────────────────────────────
provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Enable APIs ──────────────────────────────────────────────────────────────
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "compute.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "cloudbuild.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

# ── Cloud Run Service ────────────────────────────────────────────────────────
resource "google_cloud_run_v2_service" "audioclass" {
  name     = "${var.project_name}-${var.environment}"
  location = var.region

  template {
    containers {
      image = var.app_image

      ports {
        container_port = var.app_port
      }

      resources {
        limits = {
          cpu    = "${var.app_cpu / 1000}f"
          memory = "${var.app_memory}Mi"
        }
      }

      env {
        name  = "AUDIOCLASS_HOST"
        value = "0.0.0.0"
      }

      env {
        name  = "AUDIOCLASS_PORT"
        value = tostring(var.app_port)
      }

      env {
        name  = "AUDIOCLASS_MAX_UPLOAD_MB"
        value = "200"
      }

      env {
        name  = "AUDIOCLASS_MODEL"
        value = "base"
      }

      env {
        name  = "PYTHONUNBUFFERED"
        value = "1"
      }

      # Secrets from Secret Manager
      dynamic "env" {
        for_each = google_secret_manager_secret.api_key[*]
        content {
          name = "AUDIOCLASS_API_KEY"
          value_source {
            secret_key_ref {
              secret  = env.value.secret_id
              version = "latest"
            }
          }
        }
      }

      dynamic "env" {
        for_each = google_secret_manager_secret.gemini_key[*]
        content {
          name = "GEMINI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = env.value.secret_id
              version = "latest"
            }
          }
        }
      }

      dynamic "env" {
        for_each = google_secret_manager_secret.openai_key[*]
        content {
          name = "OPENAI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = env.value.secret_id
              version = "latest"
            }
          }
        }
      }

      # Database URL from Cloud SQL
      dynamic "env" {
        for_each = var.database_enabled ? [1] : []
        content {
          name  = "DATABASE_URL"
          value = "postgresql://${var.database_username}:${var.database_password}@//cloudsql/${google_sql_database_instance.audioclass[0].connection_name}/${var.database_name}"
        }
      }

      startup_probe {
        http_get {
          path = "/health"
          port = var.app_port
        }
        initial_delay_seconds = 30
        period_seconds        = 10
        failure_threshold     = 30
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = var.app_port
        }
        initial_delay_seconds = 30
        period_seconds        = 30
        failure_threshold     = 3
      }

      volume_mounts {
        name       = "recordings"
        mount_path = "/app/recordings"
      }
    }

    volumes {
      name = "recordings"
      gcs {
        bucket = google_storage_bucket.recordings.name
      }
    }

    # Scaling
    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    # Service account
    service_account = google_service_account.audioclass.email

    # VPC connector for Cloud SQL
    dynamic "vpc_access" {
      for_each = var.database_enabled ? [1] : []
      content {
        connector = google_vpc_access.connector[0].id
        egress    = "PRIVATE_RANGES_ONLY"
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [google_project_service.apis]
}

# ── Cloud Run IAM (public access) ───────────────────────────────────────────
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = google_cloud_run_v2_service.audioclass.project
  location = google_cloud_run_v2_service.audioclass.location
  name     = google_cloud_run_v2_service.audioclass.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Service Account ─────────────────────────────────────────────────────────
resource "google_service_account" "audioclass" {
  account_id   = "${var.project_name}-${var.environment}"
  display_name = "AudioClass ${var.environment} server"
}

resource "google_project_iam_member" "audioclass_roles" {
  for_each = toset([
    "roles/cloudsql.client",
    "roles/secretmanager.secretAccessor",
    "roles/storage.objectAdmin",
    "roles/monitoring.metricWriter",
    "roles/logging.logWriter",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.audioclass.email}"
}

# ── Cloud SQL ───────────────────────────────────────────────────────────────
resource "google_sql_database_instance" "audioclass" {
  count = var.database_enabled ? 1 : 0

  name             = "${var.project_name}-${var.environment}"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier = var.database_instance_class

    disk_size    = var.database_storage_gb
    disk_type    = "PD_SSD"
    disk_autoresize = true

    backup_configuration {
      enabled          = true
      start_time       = "03:00"
      point_in_time_recovery_enabled = true
    }

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.vpc[0].id
    }

    insights_config {
      query_insights_enabled = true
    }
  }

  deletion_protection = var.environment == "production"

  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "audioclass" {
  count    = var.database_enabled ? 1 : 0
  name     = var.database_name
  instance = google_sql_database_instance.audioclass[0].name
}

resource "google_sql_user" "audioclass" {
  count    = var.database_enabled ? 1 : 0
  name     = var.database_username
  instance = google_sql_database_instance.audioclass[0].name
  password = var.database_password
}

# ── VPC for Cloud SQL ───────────────────────────────────────────────────────
resource "google_compute_network" "vpc" {
  count                   = var.database_enabled ? 1 : 0
  name                    = "${var.project_name}-${var.environment}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "private" {
  count         = var.database_enabled ? 1 : 0
  name          = "${var.project_name}-${var.environment}-private"
  ip_cidr_range = "10.0.0.0/24"
  region        = var.region
  network       = google_compute_network.vpc[0].id
}

resource "google_compute_global_address" "private_ip" {
  count         = var.database_enabled ? 1 : 0
  name          = "${var.project_name}-${var.environment}-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc[0].id
}

resource "google_service_networking_connection" "private_vpc" {
  count                   = var.database_enabled ? 1 : 0
  network                 = google_compute_network.vpc[0].id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip[0].name]
}

# ── VPC Access Connector (for Cloud SQL) ────────────────────────────────────
resource "google_vpc_access_connector" "connector" {
  count = var.database_enabled ? 1 : 0

  name          = "${var.project_name}-${var.environment}-connector"
  ip_cidr_range = "10.8.0.0/28"
  network       = google_compute_network.vpc[0].name
}

# ── Cloud Storage ────────────────────────────────────────────────────────────
resource "google_storage_bucket" "recordings" {
  name          = var.storage_bucket_name != "" ? var.storage_bucket_name : "${var.project_id}-${var.environment}-recordings"
  location      = var.region
  storage_class = "STANDARD"
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = var.storage_lifecycle_days > 0 ? var.storage_lifecycle_days : 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = var.storage_lifecycle_days > 0 ? var.storage_lifecycle_days * 2 : 180
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  uniform_bucket_level_access = true
}

# ── Secret Manager ──────────────────────────────────────────────────────────
resource "google_secret_manager_secret" "api_key" {
  count     = var.api_key != "" ? 1 : 0
  secret_id = "${var.project_name}-${var.environment}-api-key"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "api_key" {
  count     = var.api_key != "" ? 1 : 0
  secret    = google_secret_manager_secret.api_key[0].id
  secret_data = var.api_key
}

resource "google_secret_manager_secret" "gemini_key" {
  count     = var.gemini_api_key != "" ? 1 : 0
  secret_id = "${var.project_name}-${var.environment}-gemini-key"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "gemini_key" {
  count       = var.gemini_api_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.gemini_key[0].id
  secret_data = var.gemini_api_key
}

resource "google_secret_manager_secret" "openai_key" {
  count     = var.openai_api_key != "" ? 1 : 0
  secret_id = "${var.project_name}-${var.environment}-openai-key"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "openai_key" {
  count       = var.openai_api_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.openai_key[0].id
  secret_data = var.openai_api_key
}

# ── Monitoring ──────────────────────────────────────────────────────────────
resource "google_monitoring_alert_policy" "high_cpu" {
  display_name = "AudioClass High CPU"
  combiner     = "OR"

  conditions {
    display_name = "CPU utilization"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/container/cpu/utilization\""
      duration        = "180s"
      comparison      = "COMPARISON_GT"
      threshold_value = var.scale_cpu_threshold / 100

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = []
}

resource "google_monitoring_alert_policy" "high_memory" {
  display_name = "AudioClass High Memory"
  combiner     = "OR"

  conditions {
    display_name = "Memory utilization"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND metric.type = \"run.googleapis.com/container/memory/utilization\""
      duration        = "180s"
      comparison      = "COMPARISON_GT"
      threshold_value = var.scale_memory_threshold / 100

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = []
}

# ── Outputs ──────────────────────────────────────────────────────────────────
output "service_url" {
  value = google_cloud_run_v2_service.audioclass.uri
}

output "service_name" {
  value = google_cloud_run_v2_service.audioclass.name
}

output "service_location" {
  value = google_cloud_run_v2_service.audioclass.location
}

output "service_account_email" {
  value = google_service_account.audioclass.email
}

output "recordings_bucket" {
  value = google_storage_bucket.recordings.name
}

output "recordings_bucket_url" {
  value = google_storage_bucket.recordings.url
}

output "database_connection_name" {
  value = var.database_enabled ? google_sql_database_instance.audioclass[0].connection_name : ""
}
