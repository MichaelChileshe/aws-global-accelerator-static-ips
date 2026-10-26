terraform {
  required_version = ">= 1.11.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.60"
    }
  }

  # Remote state in the shared bucket (one key per project), passed at init time:
  #   terraform init -backend-config="bucket=nkosi-tfstate-<account id>"
  backend "s3" {
    key          = "aws-global-accelerator-static-ips/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

locals {
  tags = { Project = "aws-global-accelerator-static-ips", ManagedBy = "terraform" }
}

# us-east-1: the DR region, IAM, and (through the provider) the Global Accelerator API.
provider "aws" {
  region = var.dr_region
  default_tags {
    tags = local.tags
  }
}

# eu-west-1: the primary region (closest AWS Region in this pair to the terminals in South Africa).
provider "aws" {
  alias  = "primary"
  region = var.primary_region
  default_tags {
    tags = local.tags
  }
}
