# Cost

The resources existed from the second apply (instances booted at 04:31) until the destroy (state written at 05:41:55 UTC), so **about 70 minutes**.

These are estimates from the list prices I used when planning: on-demand, us-east-1 and eu-west-1, October 2026. The figure from my bill will replace this once Cost Explorer shows the day.

| Item | Quantity | Rate (US$/h) | Per hour (US$) |
|---|---|---|---|
| Global Accelerator, fixed fee | 1 accelerator | 0.025 | 0.025 |
| Network Load Balancers | 2 in eu-west-1, 1 in us-east-1 | ~0.0252 / ~0.0225 + LCUs (negligible here) | ~0.073 |
| EC2 `t4g.nano` | 3 in eu-west-1, 2 in us-east-1 | ~0.0046 / ~0.0042 | ~0.022 |
| Public IPv4 addresses | 5 instances + 6 NLB node addresses (2 per NLB) | 0.005 each | ~0.055 |
| EBS gp3 | 5 × 8 GiB | ~0.08 per GiB-month | ~0.004 |
| Global Accelerator data transfer premium, SSM, `ip-ranges.json` | a few hundred kilobytes | per GB | ~0 |
| **Total** | | | **~US$0.18 an hour** |

**Estimated for the build: about US$0.20–0.25.**

**What would change in production:**
- **Global Accelerator** runs all month (the fixed fee is about US$18 a month), plus a data-transfer premium per GB that depends on where the terminals and Regions are.
- **The NLBs** would carry LCU charges for real traffic.
- **The instances** would move to private subnets behind NAT or VPC endpoints, which removes most of the public IPv4 charge but adds NAT or endpoint costs.
