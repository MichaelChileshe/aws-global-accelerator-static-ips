# One Region of the payment switch: a VPC with two public subnets, the switch instances, an
# internet-facing NLB on TCP 7000 in front of them, and optionally a canary (one instance
# behind its own NLB). Instances accept port 7000 only from inside the VPC: the NLB.

data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ssm_parameter" "al2023_arm" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-arm64"
}

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  tags                 = { Name = "${var.name}-vpc" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index + 1)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.name}-public-${count.index}" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-igw" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = { Name = "${var.name}-public-rt" }
}

resource "aws_route" "internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "switch" {
  name        = "${var.name}-switch-sg"
  description = "Payment switch - port 7000 from inside the VPC (the NLB) only"
  vpc_id      = aws_vpc.this.id
  tags        = { Name = "${var.name}-switch-sg" }
}

resource "aws_vpc_security_group_ingress_rule" "nlb_to_switch" {
  security_group_id = aws_security_group.switch.id
  description       = "TCP 7000 from the NLB (its addresses are inside the VPC)"
  ip_protocol       = "tcp"
  from_port         = 7000
  to_port           = 7000
  cidr_ipv4         = var.vpc_cidr
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.switch.id
  description       = "Outbound: SSM, package repositories"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

locals {
  # main instances 0..n-1, plus "canary" if wanted
  instances = merge(
    { for i in range(var.instance_count) : "switch-${i}" => { subnet = i % 2, role = "main" } },
    var.with_canary ? { canary = { subnet = 0, role = "canary" } } : {}
  )
}

resource "aws_instance" "switch" {
  for_each = local.instances

  ami                    = data.aws_ssm_parameter.al2023_arm.insecure_value
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public[each.value.subnet].id
  vpc_security_group_ids = [aws_security_group.switch.id]
  iam_instance_profile   = var.instance_profile

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  root_block_device {
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/../../templates/userdata.sh.tftpl", {
    region = var.region, role = each.value.role, code_b64 = var.code_b64
  })
  user_data_replace_on_change = true

  tags = { Name = "${var.name}-${each.key}", SwitchRole = each.value.role }

  depends_on = [aws_route.internet, aws_route_table_association.public, aws_vpc_security_group_egress_rule.all]

  lifecycle {
    ignore_changes = [ami]
  }
}

# ---- load balancers: main (all "main" instances) and, optionally, canary ----

locals {
  nlbs = merge({ main = "main" }, var.with_canary ? { canary = "canary" } : {})
}

resource "aws_lb" "this" {
  for_each                         = local.nlbs
  name                             = each.key == "main" ? var.name : "${var.name}-canary"
  load_balancer_type               = "network"
  internal                         = false
  subnets                          = aws_subnet.public[*].id
  enable_cross_zone_load_balancing = true
}

resource "aws_lb_target_group" "this" {
  for_each             = local.nlbs
  name                 = each.key == "main" ? var.name : "${var.name}-canary"
  port                 = 7000
  protocol             = "TCP"
  vpc_id               = aws_vpc.this.id
  target_type          = "instance"
  preserve_client_ip   = false
  deregistration_delay = 10

  health_check {
    protocol            = "TCP"
    port                = "7000"
    interval            = 10
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }
}

resource "aws_lb_listener" "this" {
  for_each          = local.nlbs
  load_balancer_arn = aws_lb.this[each.key].arn
  port              = 7000
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this[each.key].arn
  }
}

resource "aws_lb_target_group_attachment" "this" {
  for_each         = local.instances
  target_group_arn = aws_lb_target_group.this[each.value.role].arn
  target_id        = aws_instance.switch[each.key].id
  port             = 7000
}
