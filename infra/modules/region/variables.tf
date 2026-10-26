variable "name" {
  description = "Name prefix for this Region's resources."
  type        = string
}

variable "region" {
  description = "The Region this module is deployed in (written into the switch's settings)."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of this Region's VPC."
  type        = string
}

variable "instance_type" {
  description = "Instance type of the switch instances (arm64)."
  type        = string
}

variable "instance_count" {
  description = "Switch instances behind the main NLB (spread over two AZs)."
  type        = number
}

variable "with_canary" {
  description = "Also build a canary: one more instance behind its own NLB."
  type        = bool
}

variable "instance_profile" {
  description = "Instance profile name (SSM access)."
  type        = string
}

variable "code_b64" {
  description = "app/paysw.py, base64-encoded, written to the instances at boot."
  type        = string
}
