output "nlb_arn" {
  description = "Main NLB ARN (a Global Accelerator endpoint)."
  value       = aws_lb.this["main"].arn
}

output "nlb_dns" {
  description = "Main NLB DNS name (reachable directly, for comparison)."
  value       = aws_lb.this["main"].dns_name
}

output "canary_nlb_arn" {
  description = "Canary NLB ARN, or null."
  value       = var.with_canary ? aws_lb.this["canary"].arn : null
}

output "canary_nlb_dns" {
  description = "Canary NLB DNS name, or null."
  value       = var.with_canary ? aws_lb.this["canary"].dns_name : null
}

output "instance_ids" {
  description = "Main switch instance IDs."
  value       = [for k, i in aws_instance.switch : i.id if k != "canary"]
}

output "canary_instance_id" {
  description = "Canary instance ID, or null."
  value       = var.with_canary ? aws_instance.switch["canary"].id : null
}
