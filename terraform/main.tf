# ═══════════════════════════════════════════════════════════════════════════════
# AudioClass — Terraform root module
# Deploy to AWS (ECS Fargate) or GCP (Cloud Run) with a single flag.
# ═══════════════════════════════════════════════════════════════════════════════

terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    bucket         = "audioclass-terraform-state"
    key            = "terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

# ── AWS deployment ────────────────────────────────────────────────────────────
module "aws" {
  count  = var.cloud_provider == "aws" ? 1 : 0
  source = "./modules/aws"

  region          = var.region
  project_name    = var.project_name
  environment     = var.environment

  app_image       = var.app_image
  app_port        = var.app_port
  app_cpu         = var.app_cpu
  app_memory      = var.app_memory

  min_instances        = var.min_instances
  max_instances        = var.max_instances
  desired_instances    = var.desired_instances
  scale_cpu_threshold  = var.scale_cpu_threshold
  scale_memory_threshold = var.scale_memory_threshold

  vpc_cidr            = var.vpc_cidr
  public_subnet_cidrs = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  allowed_cidrs       = var.allowed_cidrs

  database_enabled        = var.database_enabled
  database_instance_class = var.database_instance_class
  database_name           = var.database_name
  database_username       = var.database_username
  database_password       = var.database_password
  database_storage_gb     = var.database_storage_gb

  storage_bucket_name     = var.storage_bucket_name
  storage_lifecycle_days  = var.storage_lifecycle_days

  api_key         = var.api_key
  gemini_api_key  = var.gemini_api_key
  openai_api_key  = var.openai_api_key

  domain_name     = var.domain_name
  certificate_arn = var.certificate_arn
}

# ── GCP deployment ────────────────────────────────────────────────────────────
module "gcp" {
  count  = var.cloud_provider == "gcp" ? 1 : 0
  source = "./modules/gcp"

  project_id      = var.gcp_project_id
  region          = var.region
  project_name    = var.project_name
  environment     = var.environment

  app_image       = var.app_image
  app_port        = var.app_port
  app_cpu         = var.app_cpu
  app_memory      = var.app_memory

  min_instances        = var.min_instances
  max_instances        = var.max_instances
  scale_cpu_threshold  = var.scale_cpu_threshold
  scale_memory_threshold = var.scale_memory_threshold

  database_enabled        = var.database_enabled
  database_instance_class = var.database_instance_class
  database_name           = var.database_name
  database_username       = var.database_username
  database_password       = var.database_password
  database_storage_gb     = var.database_storage_gb

  storage_bucket_name     = var.storage_bucket_name
  storage_lifecycle_days  = var.storage_lifecycle_days

  api_key         = var.api_key
  gemini_api_key  = var.gemini_api_key
  openai_api_key  = var.openai_api_key
}

# ── Additional variables for GCP ─────────────────────────────────────────────
variable "gcp_project_id" {
  description = "GCP project ID (only needed when cloud_provider = gcp)"
  type        = string
  default     = ""
}
