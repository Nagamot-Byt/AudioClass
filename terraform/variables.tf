variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "cloud_provider" {
  description = "Cloud provider to deploy to (aws or gcp)"
  type        = string
  default     = "aws"

  validation {
    condition     = contains(["aws", "gcp"], var.cloud_provider)
    error_message = "Cloud provider must be aws or gcp."
  }
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "audioclass"
}

variable "region" {
  description = "Cloud region to deploy to"
  type        = string
  default     = "us-east-1"
}

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}

# ── Application settings ──────────────────────────────────────────────────────
variable "app_image" {
  description = "Docker image for AudioClass server"
  type        = string
  default     = "audioclass-server:latest"
}

variable "app_port" {
  description = "Port the application listens on"
  type        = number
  default     = 8000
}

variable "app_cpu" {
  description = "CPU units for the application container (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "app_memory" {
  description = "Memory in MiB for the application container"
  type        = number
  default     = 2048
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
  default     = 1
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
  default     = 10
}

variable "desired_instances" {
  description = "Desired number of instances (ECS only)"
  type        = number
  default     = 2
}

variable "scale_cpu_threshold" {
  description = "CPU utilization threshold for autoscaling (%)"
  type        = number
  default     = 70
}

variable "scale_memory_threshold" {
  description = "Memory utilization threshold for autoscaling (%)"
  type        = number
  default     = 80
}

# ── Networking ────────────────────────────────────────────────────────────────
variable "vpc_cidr" {
  description = "CIDR block for VPC (AWS) or network (GCP)"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.10.0/24", "10.0.20.0/24"]
}

variable "allowed_cidrs" {
  description = "CIDR blocks allowed to access the server"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# ── Database ──────────────────────────────────────────────────────────────────
variable "database_enabled" {
  description = "Enable managed database"
  type        = bool
  default     = false
}

variable "database_instance_class" {
  description = "Database instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "database_engine" {
  description = "Database engine"
  type        = string
  default     = "postgresql"
}

variable "database_name" {
  description = "Database name"
  type        = string
  default     = "audioclass"
}

variable "database_username" {
  description = "Database master username"
  type        = string
  default     = "audioclass"
  sensitive   = true
}

variable "database_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "database_storage_gb" {
  description = "Database storage in GB"
  type        = number
  default     = 20
}

# ── S3 / Cloud Storage ────────────────────────────────────────────────────────
variable "storage_bucket_name" {
  description = "S3/GCS bucket name for recordings"
  type        = string
  default     = ""
}

variable "storage_lifecycle_days" {
  description = "Days before moving recordings to cold storage (0 = disabled)"
  type        = number
  default     = 90
}

# ── Secrets ───────────────────────────────────────────────────────────────────
variable "api_key" {
  description = "API key for AudioClass server"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_api_key" {
  description = "Google Gemini API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
  default     = ""
}

# ── Domain / TLS ──────────────────────────────────────────────────────────────
variable "domain_name" {
  description = "Domain name for the application (empty = no custom domain)"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM certificate ARN (AWS only, empty = auto-provision)"
  type        = string
  default     = ""
}
