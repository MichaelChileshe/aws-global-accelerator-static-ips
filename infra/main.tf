# Two Regions, the same payment switch in each, one Global Accelerator in front with two static
# anycast IPs. The terminals (and the retailers' firewalls) only ever know those two IPs.

# ---- one instance role for every switch instance: SSM only ----

resource "aws_iam_role" "switch" {
  name = "nkosi-paysw-role"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

resource "aws_iam_role_policy_attachment" "switch_ssm" {
  role       = aws_iam_role.switch.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "switch" {
  name = "nkosi-paysw-profile"
  role = aws_iam_role.switch.name
}

# ---- the two Regions ----

module "primary" {
  source    = "./modules/region"
  providers = { aws = aws.primary }

  name             = "nkosi-paysw-eu"
  region           = var.primary_region
  vpc_cidr         = "10.150.0.0/16"
  instance_type    = var.instance_type
  instance_count   = 2
  with_canary      = true
  instance_profile = aws_iam_instance_profile.switch.name
  code_b64         = filebase64("${path.module}/../app/paysw.py")

  depends_on = [aws_iam_role_policy_attachment.switch_ssm]
}

module "dr" {
  source = "./modules/region"

  name             = "nkosi-paysw-us"
  region           = var.dr_region
  vpc_cidr         = "10.151.0.0/16"
  instance_type    = var.instance_type
  instance_count   = 2
  with_canary      = false
  instance_profile = aws_iam_instance_profile.switch.name
  code_b64         = filebase64("${path.module}/../app/paysw.py")

  depends_on = [aws_iam_role_policy_attachment.switch_ssm]
}

# ---- Global Accelerator: two static anycast IPv4 addresses, TCP 7000, one endpoint group per Region ----

resource "aws_globalaccelerator_accelerator" "paysw" {
  name            = "nkosi-paysw"
  ip_address_type = "IPV4"
  enabled         = true
}

resource "aws_globalaccelerator_listener" "tcp7000" {
  accelerator_arn = aws_globalaccelerator_accelerator.paysw.arn
  protocol        = "TCP"
  client_affinity = "NONE" # each new connection is routed on its own (5-tuple)

  port_range {
    from_port = 7000
    to_port   = 7000
  }
}

resource "aws_globalaccelerator_endpoint_group" "primary" {
  listener_arn            = aws_globalaccelerator_listener.tcp7000.arn
  endpoint_group_region   = var.primary_region
  traffic_dial_percentage = var.primary_traffic_dial

  # For load balancer endpoints, Global Accelerator uses the load balancer's own target health.
  health_check_protocol         = "TCP"
  health_check_port             = 7000
  health_check_interval_seconds = 10
  threshold_count               = 3

  endpoint_configuration {
    endpoint_id                    = module.primary.nlb_arn
    weight                         = var.primary_nlb_weight
    client_ip_preservation_enabled = false
  }

  endpoint_configuration {
    endpoint_id                    = module.primary.canary_nlb_arn
    weight                         = var.canary_weight
    client_ip_preservation_enabled = false
  }
}

resource "aws_globalaccelerator_endpoint_group" "dr" {
  listener_arn            = aws_globalaccelerator_listener.tcp7000.arn
  endpoint_group_region   = var.dr_region
  traffic_dial_percentage = var.dr_traffic_dial

  health_check_protocol         = "TCP"
  health_check_port             = 7000
  health_check_interval_seconds = 10
  threshold_count               = 3

  endpoint_configuration {
    endpoint_id                    = module.dr.nlb_arn
    weight                         = 128
    client_ip_preservation_enabled = false
  }

  # One change at a time on the accelerator: Global Accelerator rejects overlapping updates.
  depends_on = [aws_globalaccelerator_endpoint_group.primary]
}
