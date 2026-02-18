variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (staging or production)"
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be either 'staging' or 'production'."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones to use"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "eks_cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "ecotrack"
}

variable "eks_cluster_version" {
  description = "Kubernetes version for the EKS cluster"
  type        = string
  default     = "1.29"
}

variable "eks_node_group_instance_types" {
  description = "Instance types for the EKS node groups"
  type        = map(list(string))
  default = {
    on_demand = ["t3.large", "t3.xlarge"]
    spot      = ["t3.large", "t3.xlarge"]
  }
}

variable "eks_node_group_desired_size" {
  description = "Desired size of the EKS node groups"
  type        = map(number)
  default = {
    on_demand = 2
    spot      = 1
  }
}

variable "eks_node_group_min_size" {
  description = "Minimum size of the EKS node groups"
  type        = map(number)
  default = {
    on_demand = 1
    spot      = 0
  }
}

variable "eks_node_group_max_size" {
  description = "Maximum size of the EKS node groups"
  type        = map(number)
  default = {
    on_demand = 5
    spot      = 10
  }
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.large"
}

variable "db_allocated_storage" {
  description = "Allocated storage for the RDS instance in GB"
  type        = number
  default     = 100
}

variable "db_max_allocated_storage" {
  description = "Maximum allocated storage for the RDS instance in GB"
  type        = number
  default     = 500
}

variable "db_name" {
  description = "Name of the database"
  type        = string
  default     = "ecotrack"
}

variable "db_username" {
  description = "Username for the database"
  type        = string
  default     = "ecotrack"
  sensitive   = true
}

variable "db_password" {
  description = "Password for the database"
  type        = string
  sensitive   = true
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.medium"
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes in the ElastiCache Redis cluster"
  type        = number
  default     = 2
}

variable "s3_bucket_names" {
  description = "Names of S3 buckets to create"
  type        = map(string)
  default = {
    data_lake     = "ecotrack-data-lake"
    model_artifacts = "ecotrack-model-artifacts"
    backups      = "ecotrack-backups"
  }
}

variable "ecr_repository_names" {
  description = "Names of ECR repositories to create"
  type        = list(string)
  default     = ["api-python", "api", "web", "worker", "ml-api"]
}