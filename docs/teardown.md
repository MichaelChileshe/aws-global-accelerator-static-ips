# Teardown and clean check

```bash
cat infra/phases.auto.tfvars 2>/dev/null        # should be empty: every drill line removed
terraform -chdir=infra destroy
```

`Plan: 0 to add, 0 to change, 48 to destroy.`, then **`Destroy complete! Resources: 48 destroyed.`** The provider disables the accelerator before deleting it, which took 38 s here. Screenshot [`29`](screenshots/29-destroy-48.png). Log: [`results/raw/tf-destroy.txt`](results/raw/tf-destroy.txt).

The static IPs go back to AWS with the accelerator. In production I'd **never** destroy it, because those two addresses are the whole point. Here it's a lab.

## Clean check

Every query uses single quotes, because of the backticks:

```bash
terraform -chdir=infra state list | wc -l
aws globalaccelerator list-accelerators --region us-west-2 --query 'Accelerators[?Name==`nkosi-paysw`].AcceleratorArn' --output text
for r in eu-west-1 us-east-1; do aws ec2 describe-instances --region $r --filters Name=tag:Project,Values=aws-global-accelerator-static-ips Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId' --output text; done
for r in eu-west-1 us-east-1; do aws ec2 describe-vpcs --region $r --filters Name=tag:Project,Values=aws-global-accelerator-static-ips --query 'Vpcs[].VpcId' --output text; done
for r in eu-west-1 us-east-1; do aws elbv2 describe-load-balancers --region $r --query 'LoadBalancers[?starts_with(LoadBalancerName, `nkosi-paysw`)].LoadBalancerName' --output text; done
for r in eu-west-1 us-east-1; do aws elbv2 describe-target-groups --region $r --query 'TargetGroups[?starts_with(TargetGroupName, `nkosi-paysw`)].TargetGroupName' --output text; done
aws iam list-roles --query 'Roles[?starts_with(RoleName, `nkosi-paysw`)].RoleName' --output text
aws iam list-instance-profiles --query 'InstanceProfiles[?starts_with(InstanceProfileName, `nkosi-paysw`)].InstanceProfileName' --output text
aws s3 ls "s3://$STATE_BUCKET/aws-global-accelerator-static-ips/"
```

**Result** (screenshot [`30`](screenshots/30-clean-check.png)):
- The state list was `0`.
- Every check printed nothing.
- The state key holds only `terraform.tfstate` at **587 bytes**, which is an empty state.

The project doesn't change any account-wide setting, so the destroy is the whole teardown.
