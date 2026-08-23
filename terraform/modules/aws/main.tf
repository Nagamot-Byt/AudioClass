terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ── Provider ──────────────────────────────────────────────────────────────────
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ── Data sources ──────────────────────────────────────────────────────────────
data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  account_id  = data.aws_caller_identity.current.account_id
  azs         = slice(data.aws_availability_zones.available.names, 0, 2)
}

# ── VPC ───────────────────────────────────────────────────────────────────────
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name_prefix}-vpc"
  cidr = var.vpc_cidr

  azs             = local.azs
  private_subnets = var.private_subnet_cidrs
  public_subnets  = var.public_subnet_cidrs

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment != "production"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    "kubernetes.io/cluster/${local.name_prefix}-eks" = "shared"
  }

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }
}

# ── ECR Repository ───────────────────────────────────────────────────────────
resource "aws_ecr_repository" "audioclass" {
  name                 = "${local.name_prefix}-server"
  image_tag_mutability = "MUTABLE"
  force_delete         = var.environment != "production"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "audioclass" {
  repository = aws_ecr_repository.audioclass.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ── ECS Cluster ──────────────────────────────────────────────────────────────
module "ecs" {
  source  = "terraform-aws-modules/ecs/aws"
  version = "~> 5.0"

  cluster_name = "${local.name_prefix}-ecs"

  cluster_settings = [
    {
      name  = "containerInsights"
      value = "enabled"
    }
  ]

  fargate_capacity_providers = {
    FARGATE = {
      default_capacity_provider_strategy = {
        base   = 1
        weight = 100
      }
    }
    FARGATE_SPOT = {
      default_capacity_provider_strategy = {
        base   = 0
        weight = 50
      }
    }
  }
}

# ── ECS Task Definition ──────────────────────────────────────────────────────
resource "aws_ecs_task_definition" "audioclass" {
  family                   = "${local.name_prefix}-server"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.app_cpu
  memory                   = var.app_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "audioclass"
      image     = var.app_image
      essential = true

      portMappings = [
        {
          containerPort = var.app_port
          hostPort      = var.app_port
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "AUDIOCLASS_HOST", value = "0.0.0.0" },
        { name = "AUDIOCLASS_PORT", value = tostring(var.app_port) },
        { name = "AUDIOCLASS_MAX_UPLOAD_MB", value = "200" },
        { name = "AUDIOCLASS_RATE_LIMIT", value = "30" },
        { name = "AUDIOCLASS_MODEL", value = "base" },
        { name = "PYTHONUNBUFFERED", value = "1" },
      ]

      secrets = [
        { name = "AUDIOCLASS_API_KEY", valueFrom = aws_secretsmanager_secret.api_key.arn },
        { name = "GEMINI_API_KEY", valueFrom = aws_secretsmanager_secret.gemini_key.arn },
        { name = "OPENAI_API_KEY", valueFrom = aws_secretsmanager_secret.openai_key.arn },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.audioclass.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "server"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:${var.app_port}/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
}

# ── ECS Service ──────────────────────────────────────────────────────────────
resource "aws_ecs_service" "audioclass" {
  name            = "${local.name_prefix}-server"
  cluster         = module.ecs.cluster_id
  task_definition = aws_ecs_task_definition.audioclass.arn
  desired_count   = var.desired_instances
  launch_type     = "FARGATE"

  scheduling_strategy = "REPLICA"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.audioclass.arn
    container_name   = "audioclass"
    container_port   = var.app_port
  }

  depends_on = [aws_lb_listener.https]

  lifecycle {
    ignore_changes = [desired_count]
  }
}

# ── Application Load Balancer ────────────────────────────────────────────────
resource "aws_security_group" "alb" {
  name_prefix = "${local.name_prefix}-alb-"
  vpc_id      = module.vpc.vpc_id
  description = "Security group for AudioClass ALB"

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidrs
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "ecs" {
  name_prefix = "${local.name_prefix}-ecs-"
  vpc_id      = module.vpc.vpc_id
  description = "Security group for AudioClass ECS tasks"

  ingress {
    from_port       = var.app_port
    to_port         = var.app_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "rds" {
  count       = var.database_enabled ? 1 : 0
  name_prefix = "${local.name_prefix}-rds-"
  vpc_id      = module.vpc.vpc_id
  description = "Security group for AudioClass RDS"

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb" "audioclass" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets

  enable_deletion_protection = var.environment == "production"

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.id
    prefix  = "alb"
    enabled = true
  }
}

resource "aws_s3_bucket" "alb_logs" {
  bucket        = "${local.name_prefix}-alb-logs-${local.account_id}"
  force_destroy = var.environment != "production"
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    id     = "cleanup-old-logs"
    status = "Enabled"

    expiration {
      days = 30
    }
  }
}

resource "aws_lb_target_group" "audioclass" {
  name        = "${local.name_prefix}-tg"
  port        = var.app_port
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 5
    timeout             = 5
    interval            = 30
    path                = "/health"
    port                = "traffic-port"
    matcher             = "200-299"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.audioclass.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.audioclass.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn != "" ? var.certificate_arn : aws_acm_certificate.audioclass[0].arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.audioclass.arn
  }
}

# ── ACM Certificate (auto-provisioned if not provided) ───────────────────────
resource "aws_acm_certificate" "audioclass" {
  count = var.domain_name != "" && var.certificate_arn == "" ? 1 : 0

  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# ── CloudWatch ───────────────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "audioclass" {
  name              = "/ecs/${local.name_prefix}-server"
  retention_in_days = var.environment == "production" ? 90 : 30
}

resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${local.name_prefix}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = var.scale_cpu_threshold
  alarm_description   = "AudioClass ECS CPU utilization > ${var.scale_cpu_threshold}%"

  dimensions = {
    ClusterName = module.ecs.cluster_name
    ServiceName = aws_ecs_service.audioclass.name
  }
}

resource "aws_cloudwatch_metric_alarm" "high_memory" {
  alarm_name          = "${local.name_prefix}-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 60
  statistic           = "Average"
  threshold           = var.scale_memory_threshold
  alarm_description   = "AudioClass ECS Memory utilization > ${var.scale_memory_threshold}%"

  dimensions = {
    ClusterName = module.ecs.cluster_name
    ServiceName = aws_ecs_service.audioclass.name
  }
}

# ── Auto Scaling ─────────────────────────────────────────────────────────────
resource "aws_appautoscaling_target" "ecs" {
  max_capacity       = var.max_instances
  min_capacity       = var.min_instances
  resource_id        = "service/${module.ecs.cluster_name}/${aws_ecs_service.audioclass.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "cpu" {
  name               = "${local.name_prefix}-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = var.scale_cpu_threshold
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

resource "aws_appautoscaling_policy" "memory" {
  name               = "${local.name_prefix}-memory-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value       = var.scale_memory_threshold
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# ── S3 Bucket for recordings ─────────────────────────────────────────────────
resource "aws_s3_bucket" "recordings" {
  bucket        = var.storage_bucket_name != "" ? var.storage_bucket_name : "${local.name_prefix}-recordings-${local.account_id}"
  force_destroy = var.environment != "production"
}

resource "aws_s3_bucket_versioning" "recordings" {
  bucket = aws_s3_bucket.recordings.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "recordings" {
  bucket = aws_s3_bucket.recordings.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "recordings" {
  bucket = aws_s3_bucket.recordings.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "recordings" {
  count  = var.storage_lifecycle_days > 0 ? 1 : 0
  bucket = aws_s3_bucket.recordings.id

  rule {
    id     = "move-to-glacier"
    status = "Enabled"

    transition {
      days          = var.storage_lifecycle_days
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = var.storage_lifecycle_days * 2
      storage_class = "GLACIER"
    }
  }
}

# ── IAM Roles ────────────────────────────────────────────────────────────────
resource "aws_iam_role" "ecs_execution" {
  name_prefix = "${local.name_prefix}-ecs-exec-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task" {
  name_prefix = "${local.name_prefix}-ecs-task-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_s3" {
  name = "s3-recordings-access"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
        ]
        Resource = [
          aws_s3_bucket.recordings.arn,
          "${aws_s3_bucket.recordings.arn}/*",
        ]
      },
    ]
  })
}

# ── Secrets Manager ──────────────────────────────────────────────────────────
resource "aws_secretsmanager_secret" "api_key" {
  name_prefix = "${local.name_prefix}-api-key"
}

resource "aws_secretsmanager_secret_version" "api_key" {
  secret_id = aws_secretsmanager_secret.api_key.id
  secret_string = var.api_key != "" ? var.api_key : "no-key-configured"
}

resource "aws_secretsmanager_secret" "gemini_key" {
  name_prefix = "${local.name_prefix}-gemini-key"
}

resource "aws_secretsmanager_secret_version" "gemini_key" {
  secret_id     = aws_secretsmanager_secret.gemini_key.id
  secret_string = var.gemini_api_key != "" ? var.gemini_api_key : "no-key-configured"
}

resource "aws_secretsmanager_secret" "openai_key" {
  name_prefix = "${local.name_prefix}-openai-key"
}

resource "aws_secretsmanager_secret_version" "openai_key" {
  secret_id     = aws_secretsmanager_secret.openai_key.id
  secret_string = var.openai_api_key != "" ? var.openai_api_key : "no-key-configured"
}

# ── RDS PostgreSQL ──────────────────────────────────────────────────────────
resource "aws_db_subnet_group" "audioclass" {
  count      = var.database_enabled ? 1 : 0
  name       = "${local.name_prefix}-db-subnets"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_rds_cluster" "audioclass" {
  count = var.database_enabled ? 1 : 0

  cluster_identifier = "${local.name_prefix}-db"
  engine             = "aurora-postgresql"
  engine_version     = "15.4"
  database_name      = var.database_name
  master_username    = var.database_username
  master_password    = var.database_password

  storage_encrypted = true
  storage_type      = "gp3"

  vpc_security_group_ids = [aws_security_group.rds[0].id]
  db_subnet_group_name    = aws_db_subnet_group.audioclass[0].name

  backup_retention_period = var.environment == "production" ? 30 : 7
  preferred_backup_window = "03:00-04:00"
  skip_final_snapshot     = var.environment != "production"

  deletion_protection = var.environment == "production"
}

# ── Outputs ──────────────────────────────────────────────────────────────────
output "vpc_id" {
  value = module.vpc.vpc_id
}

output "cluster_id" {
  value = module.ecs.cluster_id
}

output "service_name" {
  value = aws_ecs_service.audioclass.name
}

output "alb_dns" {
  value = aws_lb.audioclass.dns_name
}

output "alb_arn" {
  value = aws_lb.audioclass.arn
}

output "ecr_repository_url" {
  value = aws_ecr_repository.audioclass.repository_url
}

output "cloudwatch_log_group" {
  value = aws_cloudwatch_log_group.audioclass.name
}

output "recordings_bucket" {
  value = aws_s3_bucket.recordings.bucket
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.audioclass.arn
}

output "task_role_arn" {
  value = aws_iam_role.ecs_task.arn
}

output "execution_role_arn" {
  value = aws_iam_role.ecs_execution.arn
}
