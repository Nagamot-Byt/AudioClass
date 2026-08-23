# AudioClass — Terraform Cloud Deployment

Despliegue AudioClass en AWS (ECS Fargate) o GCP (Cloud Run) con un solo flag.

## Architecture

### AWS

```
Internet → ALB (HTTPS) → ECS Fargate → CloudWatch
                            ↓
                   ┌────────────────────┐
                   │  CloudWatch Logs   │
                   │  Secrets Manager   │
                   │  S3 (recordings)   │
                   │  RDS PostgreSQL*   │
                   │  ECR (images)      │
                   └────────────────────┘
```

### GCP

```
Internet → Cloud Run (HTTPS) → Container
                     ↓
            ┌────────────────────┐
            │  Cloud Storage     │
            │  Secret Manager    │
            │  Cloud SQL*        │
            │  Cloud Monitoring  │
            │  Cloud Logging     │
            └────────────────────┘

* Optional
```

## Quick Start

```bash
# 1. Configure
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars

# 2. Set secrets via env vars
export TF_VAR_api_key="your-key"
export TF_VAR_gemini_api_key="your-gemini-key"

# 3. Deploy to AWS
terraform init
terraform plan -var="cloud_provider=aws"
terraform apply -var="cloud_provider=aws"

# Or deploy to GCP
terraform plan -var="cloud_provider=gcp" -var="gcp_project_id=your-project"
terraform apply -var="cloud_provider=gcp" -var="gcp_project_id=your-project"
```

## Providers

| Provider | Services | Pricing Model |
|----------|----------|---------------|
| **AWS** | ECS Fargate, ALB, S3, RDS, ECR, Secrets Manager, CloudWatch | Pay-per-use (Fargate) + ALB + S3 |
| **GCP** | Cloud Run, Cloud Storage, Cloud SQL, Secret Manager | Pay-per-request (Cloud Run) + storage |

### AWS Resources

| Resource | Description |
|----------|-------------|
| ECS Fargate | Serverless containers (no EC2 management) |
| ALB | Load balancer with HTTPS termination |
| ECR | Container image registry |
| S3 | Recordings storage with lifecycle policies |
| RDS Aurora PostgreSQL | Optional managed database |
| Secrets Manager | API keys and sensitive config |
| CloudWatch | Logs, metrics, alarms, dashboards |
| ACM | TLS certificates (auto-provisioned) |

### GCP Resources

| Resource | Description |
|----------|-------------|
| Cloud Run | Serverless containers (auto-scale to zero) |
| Cloud Storage | Recordings storage with lifecycle policies |
| Cloud SQL | Optional managed PostgreSQL |
| Secret Manager | API keys and sensitive config |
| Cloud Monitoring | Metrics and alerting |
| Cloud Logging | Centralized logging |

## Configuration

### Environment Variables

```bash
# Secrets (always set via env vars, never in tfvars)
export TF_VAR_api_key="your-api-key"
export TF_VAR_database_password="secure-password"
export TF_VAR_gemini_api_key="your-gemini-key"
export TF_VAR_openai_api_key="your-openai-key"
```

### Custom Backend

```hcl
# terraform/main.tf — change backend
terraform {
  backend "s3" {
    bucket         = "your-tfstate-bucket"
    key            = "audioclass/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
```

## Cost Estimation (US East)

### Production (2 instances)

| Service | AWS | GCP |
|---------|-----|-----|
| Compute (2x 1vCPU, 2GB) | $58/mo | $38/mo (Cloud Run) |
| Load Balancer | $18/mo | — |
| Storage (100GB recordings) | $2/mo | $2/mo |
| Database (optional) | $13/mo | $7/mo |
| Secrets Manager | $0.40/secret | $0.06/secret |
| **Total** | **~$91/mo** | **~$47/mo** |

### Development (1 instance, auto-scale to 0)

| Service | AWS | GCP |
|---------|-----|-----|
| Compute | $29/mo | $0-15/mo |
| Other services | ~$5/mo | ~$5/mo |
| **Total** | **~$34/mo** | **~$5-20/mo** |

## Commands

```bash
# Plan (preview changes)
terraform plan

# Apply (deploy)
terraform apply

# Destroy (tear down)
terraform destroy

# State management
terraform state list
terraform state show module.aws[0].aws_ecs_service.audioclass

# Outputs
terraform output
terraform output aws_alb_dns
terraform output gcp_service_url
```

## AWS-Specific Setup

### 1. Create S3 backend bucket

```bash
aws s3 mb s3://audioclass-terraform-state --region us-east-1
aws dynamodb create-table \
  --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### 2. Push Docker image to ECR

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin $(terraform output -raw aws_ecr_repository_url | cut -d'/' -f1)

docker build -t audioclass-server .
docker tag audioclass-server:latest $(terraform output -raw aws_ecr_repository_url):latest
docker push $(terraform output -raw aws_ecr_repository_url):latest
```

### 3. Check service status

```bash
aws ecs describe-services \
  --cluster $(terraform output -raw aws_cluster_id) \
  --services $(terraform output -raw aws_service_name)
```

## GCP-Specific Setup

### 1. Authenticate

```bash
gcloud auth application-default login
gcloud config set project your-project-id
```

### 2. Push Docker image to Artifact Registry

```bash
gcloud auth configure-docker us-east1-docker.pkg.dev
docker build -t us-east1-docker.pkg.dev/your-project/audioclass/server:latest .
docker push us-east1-docker.pkg.dev/your-project/audioclass/server:latest
```

### 3. Check service status

```bash
gcloud run services describe audioclass-production --region us-east1
```

## Security

| Feature | AWS | GCP |
|---------|-----|-----|
| TLS/HTTPS | ACM certificates | Cloud Run managed |
| Secrets | Secrets Manager | Secret Manager |
| Network isolation | Private subnets + security groups | VPC + private IPs |
| IAM | ECS task roles | Service accounts |
| Audit | CloudTrail | Cloud Audit Logs |
| Encryption | AES256 (S3), TLS (RDS) | Default (GCS), TLS (Cloud SQL) |

## Troubleshooting

### ECS service won't start

```bash
aws ecs describe-services --cluster audioclass-production-ecs --services audioclass-production-server
aws logs tail /ecs/audioclass-production-server --follow
```

### Cloud Run deployment fails

```bash
gcloud run services describe audioclass-production --region us-east1
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=audioclass-production" --limit 50
```

### Terraform state locked

```bash
# AWS
aws dynamodb delete-item --table-name terraform-locks --key '{"LockID":{"S":"audioclass/terraform.tfstate"}}'

# GCP (not applicable, uses local or GCS backend)
```

## Adding New Resources

1. Add to `modules/aws/main.tf` or `modules/gcp/main.tf`
2. Add corresponding variables to `variables.tf`
3. Add outputs to `outputs.tf`
4. Add resource to root `main.tf` if shared

## Multi-environment

```bash
# Deploy dev
terraform apply -var="environment=dev" -var="desired_instances=1"

# Deploy staging
terraform apply -var="environment=staging" -var="desired_instances=1"

# Deploy production
terraform apply -var="environment=production" -var="desired_instances=3"
```
