variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "app_image" {
  description = "Container image for Cloud Run"
  type        = string
}

variable "app_port" {
  description = "Application port"
  type        = number
}

variable "app_cpu" {
  description = "CPU millicores"
  type        = number
}

variable "app_memory" {
  description = "Memory in MiB"
  type        = number
}

variable "min_instances" {
  description = "Minimum instances"
  type        = number
}

variable "max_instances" {
  description = "Maximum instances"
  type        = number
}

variable "scale_cpu_threshold" {
  description = "CPU scale threshold (%)"
  type        = number
}

variable "scale_memory_threshold" {
  description = "Memory scale threshold (%)"
  type        = number
}

variable "database_enabled" {
  description = "Enable Cloud SQL"
  type        = bool
}

variable "database_instance_class" {
  description = "Cloud SQL tier"
  type        = string
}

variable "database_name" {
  description = "Database name"
  type        = string
}

variable "database_username" {
  description = "Database username"
  type        = string
  sensitive   = true
}

variable "database_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "database_storage_gb" {
  description = "Database storage GB"
  type        = number
}

variable "storage_bucket_name" {
  description = "GCS bucket name"
  type        = string
}

variable "storage_lifecycle_days" {
  description = "Storage lifecycle days"
  type        = number
}

variable "api_key" {
  description = "API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_api_key" {
  description = "Gemini API key"
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
