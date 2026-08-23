# ── AWS outputs ──────────────────────────────────────────────────────────────
output "aws_vpc_id" {
  description = "AWS VPC ID"
  value       = var.cloud_provider == "aws" ? module.aws[0].vpc_id : null
}

output "aws_cluster_id" {
  description = "AWS ECS cluster ID"
  value       = var.cloud_provider == "aws" ? module.aws[0].cluster_id : null
}

output "aws_service_name" {
  description = "AWS ECS service name"
  value       = var.cloud_provider == "aws" ? module.aws[0].service_name : null
}

output "aws_alb_dns" {
  description = "AWS ALB DNS name"
  value       = var.cloud_provider == "aws" ? module.aws[0].alb_dns : null
}

output "aws_ecr_repository_url" {
  description = "AWS ECR repository URL"
  value       = var.cloud_provider == "aws" ? module.aws[0].ecr_repository_url : null
}

output "aws_cloudwatch_log_group" {
  description = "AWS CloudWatch log group"
  value       = var.cloud_provider == "aws" ? module.aws[0].cloudwatch_log_group : null
}

output "aws_recordings_bucket" {
  description = "AWS S3 bucket for recordings"
  value       = var.cloud_provider == "aws" ? module.aws[0].recordings_bucket : null
}

output "aws_task_definition_arn" {
  description = "AWS ECS task definition ARN"
  value       = var.cloud_provider == "aws" ? module.aws[0].task_definition_arn : null
}

output "aws_task_role_arn" {
  description = "AWS ECS task role ARN"
  value       = var.cloud_provider == "aws" ? module.aws[0].task_role_arn : null
}

# ── GCP outputs ──────────────────────────────────────────────────────────────
output "gcp_service_url" {
  description = "GCP Cloud Run service URL"
  value       = var.cloud_provider == "gcp" ? module.gcp[0].service_url : null
}

output "gcp_service_name" {
  description = "GCP Cloud Run service name"
  value       = var.cloud_provider == "gcp" ? module.gcp[0].service_name : null
}

output "gcp_service_account_email" {
  description = "GCP service account email"
  value       = var.cloud_provider == "gcp" ? module.gcp[0].service_account_email : null
}

output "gcp_recordings_bucket" {
  description = "GCP Cloud Storage bucket for recordings"
  value       = var.cloud_provider == "gcp" ? module.gcp[0].recordings_bucket : null
}

output "gcp_database_connection_name" {
  description = "GCP Cloud SQL connection name"
  value       = var.cloud_provider == "gcp" ? module.gcp[0].database_connection_name : null
}
