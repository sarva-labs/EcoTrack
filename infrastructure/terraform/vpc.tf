module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "ecotrack-${var.environment}-vpc"
  cidr = var.vpc_cidr

  azs             = var.availability_zones
  private_subnets = [for i, az in var.availability_zones : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i, az in var.availability_zones : cidrsubnet(var.vpc_cidr, 4, i + length(var.availability_zones))]
  
  # Database subnets for RDS
  database_subnets = [for i, az in var.availability_zones : cidrsubnet(var.vpc_cidr, 4, i + 2*length(var.availability_zones))]
  
  # ElastiCache subnets for Redis
  elasticache_subnets = [for i, az in var.availability_zones : cidrsubnet(var.vpc_cidr, 4, i + 3*length(var.availability_zones))]

  # Enable NAT Gateway for private subnets
  enable_nat_gateway = true
  single_nat_gateway = var.environment == "staging" ? true : false
  one_nat_gateway_per_az = var.environment == "production" ? true : false

  # DNS settings
  enable_dns_hostnames = true
  enable_dns_support   = true

  # VPC Flow Logs
  enable_flow_log                      = true
  create_flow_log_cloudwatch_log_group = true
  create_flow_log_cloudwatch_iam_role  = true
  flow_log_max_aggregation_interval    = 60

  # Public subnet tags for EKS
  public_subnet_tags = {
    "kubernetes.io/cluster/${var.eks_cluster_name}-${var.environment}" = "shared"
    "kubernetes.io/role/elb"                                          = "1"
  }

  # Private subnet tags for EKS
  private_subnet_tags = {
    "kubernetes.io/cluster/${var.eks_cluster_name}-${var.environment}" = "shared"
    "kubernetes.io/role/internal-elb"                                 = "1"
  }

  # Database subnet group
  create_database_subnet_group = true
  database_subnet_group_name   = "ecotrack-${var.environment}-db-subnet"

  # ElastiCache subnet group
  create_elasticache_subnet_group = true
  elasticache_subnet_group_name   = "ecotrack-${var.environment}-redis-subnet"

  tags = {
    Environment = var.environment
    Project     = "EcoTrack"
  }
}

# Security Groups
resource "aws_security_group" "eks_cluster" {
  name        = "ecotrack-${var.environment}-eks-cluster-sg"
  description = "Security group for EKS cluster control plane"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "ecotrack-${var.environment}-eks-cluster-sg"
    Environment = var.environment
  }
}

resource "aws_security_group" "eks_nodes" {
  name        = "ecotrack-${var.environment}-eks-nodes-sg"
  description = "Security group for EKS worker nodes"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 0
    to_port         = 0
    protocol        = "-1"
    security_groups = [aws_security_group.eks_cluster.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "ecotrack-${var.environment}-eks-nodes-sg"
    Environment = var.environment
  }
}

resource "aws_security_group" "database" {
  name        = "ecotrack-${var.environment}-database-sg"
  description = "Security group for PostgreSQL database"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.eks_nodes.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "ecotrack-${var.environment}-database-sg"
    Environment = var.environment
  }
}

resource "aws_security_group" "redis" {
  name        = "ecotrack-${var.environment}-redis-sg"
  description = "Security group for Redis ElastiCache"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.eks_nodes.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "ecotrack-${var.environment}-redis-sg"
    Environment = var.environment
  }
}