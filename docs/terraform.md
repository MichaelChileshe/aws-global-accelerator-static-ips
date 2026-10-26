# Terraform: structure, gates, counts

## Layout

```
bootstrap/main.tf              the shared state bucket (applied once, long ago; its own state stays local)
infra/versions.tf              backend (S3, key aws-global-accelerator-static-ips/, use_lockfile), two providers
infra/variables.tf             Regions, instance type, and the traffic controls (dials, weights) with validation
infra/main.tf                  IAM, the two Region modules, accelerator, listener, endpoint groups
infra/outputs.tf               static IPs, DNS name, ARNs, per-Region NLB names and instance IDs, paysw SHA-256
infra/modules/region/          one Region: VPC, subnets, IGW, routes, SG, instances, NLBs, target groups
infra/templates/userdata.sh.tftpl   writes the switch and its systemd unit at boot
infra/.terraform.lock.hcl      provider pinned: hashicorp/aws 6.69.1 (constraint ~> 6.60)
```

- **Two providers:** the default one is us-east-1, which holds the DR Region, IAM and the Global Accelerator resources (the provider sends Global Accelerator calls to us-west-2 by itself). The `aws.primary` alias is eu-west-1. `module "primary"` gets `providers = { aws = aws.primary }`. The same module code builds both Regions, so the only differences between them are the inputs: name, CIDR, and whether there's a canary.
- **The switch code is part of the configuration.** `filebase64("app/paysw.py")` goes into each instance's user data. The output `paysw_sha256` is what I compared against `sha256sum` on every instance.

## Quality gates before any apply

| Gate | Result |
|---|---|
| `terraform fmt -check -recursive` | clean |
| `terraform validate` | `Success! The configuration is valid.` |
| `tflint --recursive` (recommended preset) | clean |
| `checkov` (soft fail, then triaged below) | **Passed 86, Failed 24, Skipped 0** |

Screenshot [`02`](screenshots/02-init-and-quality-gates.png). Full output: [`results/raw/checkov.txt`](results/raw/checkov.txt).

### What checkov flagged, and my decision

Counts are per check across both modules.

| Check | Count | Decision |
|---|---|---|
| CKV_AWS_130 subnets assign public IPs | 4 | **Accepted for the lab.** Instances need outbound access for SSM, and public subnets avoid NAT gateway cost. In production: private subnets with NAT or VPC endpoints, and only the NLB public. |
| CKV_AWS_91 NLB access logs, CKV_AWS_75 Global Accelerator flow logs, CKV2_AWS_11 VPC flow logs | 2 + 1 + 2 | **Gap, recorded.** For a card switch these are required evidence (PCI DSS Req. 10). Left off to keep the lab's cost and teardown simple. |
| CKV_AWS_150 NLB deletion protection | 2 | **Accepted.** The lab must destroy cleanly. In production: on. |
| CKV2_AWS_12 default security group not restricted | 2 | **Should fix:** a tiny `aws_default_security_group` with no rules, at no cost. Noted as a follow-up. |
| CKV_AWS_126 detailed monitoring, CKV_AWS_135 EBS-optimised | 2 + 2 | Not meaningful for `t4g.nano` lab instances. Detailed monitoring would have helped with the [hung instance](debugging-journey.md), though. |
| CKV_AWS_394 AZ data source not pinned to zone IDs | 2 | **Accepted.** The module takes the first two available AZs. Pinning zone IDs would make the AZ choice explicit; worth doing if capacity in a specific AZ matters. |
| 5 checks on `bootstrap/` (state bucket: access logs, KMS, replication, event notifications, abort incomplete uploads) | 5 | **Out of scope here.** It's the shared state bucket from an earlier project; tracked there. |

## Counts and timings

| Operation | Result |
|---|---|
| Plan | `Plan: 48 to add, 0 to change, 0 to destroy.` |
| Apply | `Apply complete! Resources: 48 added, 0 changed, 0 destroyed.` State list: 52, including 4 data sources. |
| Canary 0 → 50 / 50 → 0 | `1 to change` each, 42 s / 41 s |
| Dial 100 → 50 / 50 → 100 | `1 to change` each, 1 min 2 s / 31 s |
| Destroy | `Plan: 0 to add, 0 to change, 48 to destroy.`, then `Destroy complete! Resources: 48 destroyed.` The accelerator took 38 s, because the provider disables it before deleting it. |

The plan, first apply, the two drill applies and the destroy are logged in [`results/raw/`](results/raw/), ANSI colour codes stripped. The two "back" applies (canary 50 → 0, dial 50 → 100) exist only as screenshots [`14`](screenshots/14-canary-back-to-0.png) and [`18`](screenshots/18-dial-back-to-100.png). `tf-apply-base.txt` is the successful second apply; see the [debugging journey](debugging-journey.md) for the first one.
