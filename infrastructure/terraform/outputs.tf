output "vpc_id" {
  description = "The ID of the VPC"
  value       = module.vpc.vpc_id
}

output "vpc_cidr_block" {
  description = "The CIDR block of the VPC"
  value       = module.vpc.vpc_cidr_block
}

output "private_subnets" {
  description = "List of IDs of private subnets"
  value       = module.vpc.private_subnets
}

output "public_subnets" {
  description = "List of IDs of public subnets"
  value       = module.vpc.public_subnets
}

output "database_subnets" {
  description = "List of IDs of database subnets"
  value       = module.vpc.database_subnets
}

output "elasticache_subnets" {
  description = "List of IDs of elasticache subnets"
  value       = module.vpc.elasticache_subnets
}

output "eks_cluster_id" {
  description = "The name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "The endpoint for the EKS cluster"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = aws_security_group.eks_cluster.id
}

output "eks_node_security_group_id" {
  description = "Security group ID attached to the EKS nodes"
  value       = aws_security_group.eks_nodes.id
}

output "eks_oidc_provider_arn" {
  description = "The ARN of the OIDC Provider"
  value       = module.eks.oidc_provider_arn
}

output "rds_endpoint" {
  description = "The connection endpoint for the RDS PostgreSQL instance"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_address" {
  description = "The hostname of the RDS instance"
  value       = aws_db_instance.postgres.address
}

output "rds_port" {
  description = "The port on which the RDS instance accepts connections"
  value       = aws_db_instance.postgres.port
}

output "rds_database_name" {
  description = "The database name"
  value       = aws_db_instance.postgres.db_name
}

output "redis_endpoint" {
  description = "The endpoint of the ElastiCache Redis cluster"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
}

output "redis_port" {
  description = "The port on which the Redis cluster accepts connections"
  value       = aws_elasticache_replication_group.redis.port
}

output "s3_data_lake_bucket" {
  description = "The name of the S3 data lake bucket"
  value       = aws_s3_bucket.data_lake.bucket
}

output "s3_model_artifacts_bucket" {
  description = "The name of the S3 model artifacts bucket"
  value       = aws_s3_bucket.model_artifacts.bucket
}

output "s3_backups_bucket" {
  description = "The name of the S3 backups bucket"
  value       = aws_s3_bucket.backups.bucket
}

output "ecr_repository_urls" {
  description = "The URLs of the ECR repositories"
  value       = { for k, v in aws_ecr_repository.repositories : k => v.repository_url }
}

output "secrets_manager_redis_secret_arn" {
  description = "The ARN of the Secrets Manager secret for Redis"
  value       = aws_secretsmanager_secret.redis.arn
}