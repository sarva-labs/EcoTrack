resource "aws_db_parameter_group" "postgres" {
  name   = "ecotrack-${var.environment}-postgres16"
  family = "postgres16"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements,auto_explain,pg_cron,timescaledb,postgis,pgvector"
  }

  parameter {
    name  = "log_statement"
    value = "ddl"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  parameter {
    name  = "max_connections"
    value = var.environment == "production" ? "500" : "200"
  }

  parameter {
    name  = "work_mem"
    value = var.environment == "production" ? "16384" : "8192"
  }

  parameter {
    name  = "maintenance_work_mem"
    value = var.environment == "production" ? "2GB" : "1GB"
  }

  parameter {
    name  = "random_page_cost"
    value = "1.1"
  }

  parameter {
    name  = "effective_cache_size"
    value = var.environment == "production" ? "24GB" : "12GB"
  }

  tags = {
    Environment = var.environment
    Project     = "EcoTrack"
  }
}

resource "aws_db_subnet_group" "postgres" {
  name       = "ecotrack-${var.environment}-postgres-subnet"
  subnet_ids = module.vpc.database_subnets

  tags = {
    Environment = var.environment
    Project     = "EcoTrack"
  }
}

resource "aws_db_instance" "postgres" {
  identifier             = "ecotrack-${var.environment}-postgres"
  engine                 = "postgres"
  engine_version         = "16.1"
  instance_class         = var.db_instance_class
  allocated_storage      = var.db_allocated_storage
  max_allocated_storage  = var.db_max_allocated_storage
  storage_type           = "gp3"
  storage_encrypted      = true
  
  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password
  port                   = 5432
  
  vpc_security_group_ids = [aws_security_group.database.id]
  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  parameter_group_name   = aws_db_parameter_group.postgres.name
  
  multi_az               = var.environment == "production" ? true : false
  publicly_accessible    = false
  
  backup_retention_period = var.environment == "production" ? 30 : 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:30-sun:05:30"
  
  auto_minor_version_upgrade = true
  allow_major_version_upgrade = false
  apply_immediately          = false
  deletion_protection        = var.environment == "production" ? true : false
  skip_final_snapshot        = var.environment == "production" ? false : true
  final_snapshot_identifier  = var.environment == "production" ? "ecotrack-${var.environment}-postgres-final-${formatdate("YYYYMMDDhhmmss", timestamp())}" : null
  
  performance_insights_enabled          = true
  performance_insights_retention_period = var.environment == "production" ? 7 : 7
  
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  monitoring_interval             = 60
  monitoring_role_name            = "ecotrack-${var.environment}-postgres-monitoring"
  create_monitoring_role          = true
  
  tags = {
    Environment = var.environment
    Project     = "EcoTrack"
  }

  lifecycle {
    prevent_destroy = var.environment == "production" ? true : false
  }
}

# RDS PostgreSQL Extensions
resource "null_resource" "postgres_extensions" {
  depends_on = [aws_db_instance.postgres]

  provisioner "local-exec" {
    command = <<-EOT
      PGPASSWORD=${var.db_password} psql -h ${aws_db_instance.postgres.address} -U ${var.db_username} -d ${var.db_name} -c "CREATE EXTENSION IF NOT EXISTS postgis;"
      PGPASSWORD=${var.db_password} psql -h ${aws_db_instance.postgres.address} -U ${var.db_username} -d ${var.db_name} -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
      PGPASSWORD=${var.db_password} psql -h ${aws_db_instance.postgres.address} -U ${var.db_username} -d ${var.db_name} -c "CREATE EXTENSION IF NOT EXISTS pgvector;"
      PGPASSWORD=${var.db_password} psql -h ${aws_db_instance.postgres.address} -U ${var.db_username} -d ${var.db_name} -c "CREATE EXTENSION IF NOT EXISTS pg_cron;"
    EOT
  }

  triggers = {
    db_instance_id = aws_db_instance.postgres.id
  }
}

# RDS Enhanced Monitoring IAM Role
resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "ecotrack-${var.environment}-rds-enhanced-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      },
    ]
  })

  managed_policy_arns = ["arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"]

  tags = {
    Environment = var.environment
    Project     = "EcoTrack"
  }
}