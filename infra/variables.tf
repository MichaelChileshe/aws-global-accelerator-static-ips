variable "primary_region" {
  description = "Primary Region: the payment switch the terminals normally reach."
  type        = string
  default     = "eu-west-1"
}

variable "dr_region" {
  description = "DR Region: takes the traffic when the primary is unhealthy or dialled down."
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "Payment switch instances (Graviton, arm64)."
  type        = string
  default     = "t4g.nano"
}

# ---- traffic controls: change in phases.auto.tfvars, then apply ----

variable "primary_traffic_dial" {
  description = "Share (0-100) of the traffic Global Accelerator would send to the primary Region that it actually sends there; the rest spills to the next-closest healthy Region."
  type        = number
  default     = 100

  validation {
    condition     = var.primary_traffic_dial >= 0 && var.primary_traffic_dial <= 100
    error_message = "primary_traffic_dial must be between 0 and 100."
  }
}

variable "dr_traffic_dial" {
  description = "Traffic dial (0-100) for the DR Region's endpoint group."
  type        = number
  default     = 100

  validation {
    condition     = var.dr_traffic_dial >= 0 && var.dr_traffic_dial <= 100
    error_message = "dr_traffic_dial must be between 0 and 100."
  }
}

variable "primary_nlb_weight" {
  description = "Weight (0-255) of the primary Region's main NLB inside its endpoint group."
  type        = number
  default     = 200
}

variable "canary_weight" {
  description = "Weight (0-255) of the primary Region's canary NLB (a new switch version taking a share of traffic). 0 = no traffic."
  type        = number
  default     = 0

  validation {
    condition     = var.canary_weight >= 0 && var.canary_weight <= 255
    error_message = "canary_weight must be between 0 and 255."
  }
}
