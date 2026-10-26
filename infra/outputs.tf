output "static_ips" {
  description = "The accelerator's two static anycast IPv4 addresses: what the retailers allow-list."
  value       = flatten([for s in aws_globalaccelerator_accelerator.paysw.ip_sets : s.ip_addresses])
}

output "accelerator_dns" {
  description = "The accelerator's DNS name (resolves to the two static IPs)."
  value       = aws_globalaccelerator_accelerator.paysw.dns_name
}

output "accelerator_arn" {
  description = "For aws globalaccelerator commands (API in us-west-2)."
  value       = aws_globalaccelerator_accelerator.paysw.arn
}

output "endpoint_groups" {
  description = "Endpoint group ARNs by role."
  value       = { primary = aws_globalaccelerator_endpoint_group.primary.arn, dr = aws_globalaccelerator_endpoint_group.dr.arn }
}

output "regions" {
  description = "Per Region: the NLB's DNS name (direct, without the accelerator) and the switch instances."
  value = {
    primary = { region = var.primary_region, nlb_dns = module.primary.nlb_dns, canary_nlb_dns = module.primary.canary_nlb_dns,
    instances = module.primary.instance_ids, canary_instance = module.primary.canary_instance_id }
    dr = { region = var.dr_region, nlb_dns = module.dr.nlb_dns, instances = module.dr.instance_ids }
  }
}

output "paysw_sha256" {
  description = "SHA-256 of app/paysw.py: compare with the file on an instance."
  value       = filesha256("${path.module}/../app/paysw.py")
}
