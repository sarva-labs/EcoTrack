module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = "${var.eks_cluster_name}-${var.environment}"
  cluster_version = var.eks_cluster_version

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Security groups
  cluster_security_group_id        = aws_security_group.eks_cluster.id
  create_node_security_group       = false
  node_security_group_id           = aws_security_group.eks_nodes.id

  # Cluster addons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = true
    }
  }

  # EKS Managed Node Groups
  eks_managed_node_groups = {
    on_demand = {
      name            = "on-demand-ng"
      use_name_prefix = true

      subnet_ids = module.vpc.private_subnets

      min_size     = var.eks_node_group_min_size["on_demand"]
      max_size     = var.eks_node_group_max_size["on_demand"]
      desired_size = var.eks_node_group_desired_size["on_demand"]

      instance_types = var.eks_node_group_instance_types["on_demand"]
      capacity_type  = "ON_DEMAND"

      labels = {
        nodegroup = "on-demand"
      }

      update_config = {
        max_unavailable_percentage = 33
      }

      tags = {
        "k8s.io/cluster-autoscaler/enabled"                      = "true"
        "k8s.io/cluster-autoscaler/${var.eks_cluster_name}-${var.environment}" = "owned"
      }
    }

    spot = {
      name            = "spot-ng"
      use_name_prefix = true

      subnet_ids = module.vpc.private_subnets

      min_size     = var.eks_node_group_min_size["spot"]
      max_size     = var.eks_node_group_max_size["spot"]
      desired_size = var.eks_node_group_desired_size["spot"]

      instance_types = var.eks_node_group_instance_types["spot"]
      capacity_type  = "SPOT"

      labels = {
        nodegroup = "spot"
      }

      taints = [
        {
          key    = "spot"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      ]

      update_config = {
        max_unavailable_percentage = 50
      }

      tags = {
        "k8s.io/cluster-autoscaler/enabled"                      = "true"
        "k8s.io/cluster-autoscaler/${var.eks_cluster_name}-${var.environment}" = "owned"
      }
    }
  }

  # Cluster IAM role
  create_iam_role = true
  iam_role_name   = "eks-cluster-${var.eks_cluster_name}-${var.environment}"

  # Node IAM role
  create_node_security_group = false

  # Fargate profiles
  fargate_profiles = {
    default = {
      name = "default"
      selectors = [
        {
          namespace = "kube-system"
          labels = {
            k8s-app = "kube-dns"
          }
        },
        {
          namespace = "default"
        }
      ]

      subnet_ids = module.vpc.private_subnets

      tags = {
        Owner = "default"
      }
    }
  }

  # AWS Auth ConfigMap
  manage_aws_auth_configmap = true

  aws_auth_roles = [
    {
      rolearn  = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/Admin"
      username = "admin"
      groups   = ["system:masters"]
    },
  ]

  tags = {
    Environment = var.environment
    Project     = "EcoTrack"
  }
}

# Cluster Autoscaler IAM Policy
resource "aws_iam_policy" "cluster_autoscaler" {
  name        = "eks-cluster-autoscaler-${var.eks_cluster_name}-${var.environment}"
  description = "EKS cluster autoscaler policy for ${var.eks_cluster_name}-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "autoscaling:DescribeAutoScalingGroups",
          "autoscaling:DescribeAutoScalingInstances",
          "autoscaling:DescribeLaunchConfigurations",
          "autoscaling:DescribeTags",
          "autoscaling:SetDesiredCapacity",
          "autoscaling:TerminateInstanceInAutoScalingGroup",
          "ec2:DescribeLaunchTemplateVersions"
        ]
        Resource = "*"
        Effect   = "Allow"
      }
    ]
  })
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# Helm release for cluster autoscaler
resource "helm_release" "cluster_autoscaler" {
  depends_on = [module.eks]
  
  name       = "cluster-autoscaler"
  repository = "https://kubernetes.github.io/autoscaler"
  chart      = "cluster-autoscaler"
  namespace  = "kube-system"
  version    = "9.29.0"

  set {
    name  = "autoDiscovery.clusterName"
    value = "${var.eks_cluster_name}-${var.environment}"
  }

  set {
    name  = "awsRegion"
    value = var.aws_region
  }

  set {
    name  = "rbac.serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.eks.eks_managed_node_groups["on_demand"].iam_role_arn
  }
}

# Helm release for AWS Load Balancer Controller
resource "helm_release" "aws_load_balancer_controller" {
  depends_on = [module.eks]
  
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"
  version    = "1.6.0"

  set {
    name  = "clusterName"
    value = "${var.eks_cluster_name}-${var.environment}"
  }

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.eks.eks_managed_node_groups["on_demand"].iam_role_arn
  }
}