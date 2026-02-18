resource "aws_elasticache_parameter_group" "redis" {
  name   = "ecotrack-${var.environment}-redis7"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "volatile-lru"
  }

  parameter {
    name  = "notify-keyspace-events"
    value = "Ex"
  }

  parameter {
    name  = "timeout"
    value = "300"
  }

  parameter {
    name  = "maxmemory-samples"
    value = "10"
  }

  parameter {
    name  = "activedefrag"
    value = "yes"
  }

  tags = {
    Environment = var.environment
    Project     = "EcoTrack"
  }
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "ecotrack-${var.environment}-redis-subnet"
  subnet_ids = module.vpc.elasticache_subnets

  tags = {
    Environment = var.environment
    Project     = "EcoTrack"
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id          = "ecotrack-${var.environment}-redis"
  description                   = "EcoTrack ${var.environment} Redis cluster"
  node_type                     = var.redis_node_type
  port                          = 6379
  parameter_group_name          = aws_elasticache_parameter_group.redis.name
  subnet_group_name             = aws_elasticache_subnet_group.redis.name
  security_group_ids            = [aws_security_group.redis.id]
  automatic_failover_enabled    = var.environment == "production" ? true : false
  multi_az_enabled              = var.environment == "production" ? true : false
  num_cache_clusters            = var.redis_num_cache_nodes
  at_rest_encryption_enabled    = true
  transit_encryption_enabled    = true
  auth_token                    = random_password.redis_auth_token.result
  apply_immediately             = true
  auto_minor_version_upgrade    = true
  maintenance_window            = "sun:05:00-sun:06:00"
  snapshot_window               = "00:00-01:00"
  snapshot_retention_limit      = var.environment == "production" ? 7 : 1
  final_snapshot_identifier     = "ecotrack-${var.environment}-redis-final"
  
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis.name
    destination_type = "cloudwatch-logs"
    log_format       = "text"
    log_type         = "slow-log"
  }

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis.name
    destination_type = "cloudwatch-logs"
    log_format       = "text"
    log_type         = "engine-log"
  }

  tags = {
    Environment = var.environment
    Project     = "EcoTrack"
  }
}

resource "random_password" "redis_auth_token" {
  length  = 32
  special = false
}

resource "aws_cloudwatch_log_group" "redis" {
  name              = "/aws/elasticache/ecotrack-${var.environment}-redis"
  retention_in_days = var.environment == "production" ? 30 : 7

  tags = {
    Environment = var.environment
    Project     = "EcoTrack"
  }
}

# Store Redis credentials in AWS Secrets Manager
resource "aws_secretsmanager_secret" "redis" {
  name        = "ecotrack/${var.environment}/redis"
  description = "Redis connection details for EcoTrack ${var.environment}"
  
  tags = {
    Environment = var.environment
    Project     = "EcoTrack"
  }
}

resource "aws_secretsmanager_secret_version" "redis" {
  secret_id = aws_secretsmanager_secret.redis.id
  secret_string = jsonencode({
    host      = aws_elasticache_replication_group.redis.primary_endpoint_address
    port      = 6379
    auth_token = random_password.redis_auth_token.result
    ssl       = true
  })
}