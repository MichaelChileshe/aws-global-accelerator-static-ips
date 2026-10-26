# Screenshots

All 30 screenshots come from the build on 26 October 2026, in the order things happened. The account ID is masked as `<account-id>`.

| # | What it shows |
|---|---|
| [01](screenshots/01-state-bucket-and-t4g-offerings.png) | State bucket exists; AZs offering `t4g.nano` in eu-west-1 and us-east-1 |
| [02](screenshots/02-init-and-quality-gates.png) | `terraform init` (aws 6.69.1), fmt, validate, tflint clean, checkov 86 passed / 24 failed |
| [03](screenshots/03-apply-48-and-static-ips.png) | The two static IPs, the accelerator ARN and DNS name, state list 52 |
| [04](screenshots/04-ga-status-and-primary-switches.png) | Accelerator DEPLOYED and all endpoints HEALTHY; the switch active on all 3 eu-west-1 instances with the expected SHA-256 |
| [05](screenshots/05-dr-status-check-hangs.png) | DR status check: one instance answers, the other never does; my helper had no time limit (Ctrl+C traceback) |
| [06](screenshots/06-ssm-one-invocation-stuck.png) | The command `InProgress` on one instance while EC2 status checks say `ok` |
| [07](screenshots/07-forced-reboot-still-unhealthy.png) | Reboot sent; the instance stays `unhealthy` for the next few minutes |
| [08](screenshots/08-dr-switches-healthy-again.png) | Both DR targets `healthy`, the switch active on both with the expected SHA-256 |
| [09](screenshots/09-ga-status-all-healthy.png) | Accelerator snapshot `base`, everything HEALTHY |
| [10](screenshots/10-nc-probe-and-baseline-mix.png) | One authorisation by hand with `nc`, the latency probe, the baseline mix (200/200 eu-west-1) |
| [11](screenshots/11-canary-weight-50-apply.png) | `canary_weight = 50`: 1 to change, 42 s |
| [12](screenshots/12-canary-weight-50-status.png) | Canary endpoint at weight 50, HEALTHY |
| [13](screenshots/13-canary-mix.png) | 300 connections: 211 main, 89 canary |
| [14](screenshots/14-canary-back-to-0.png) | Canary back to weight 0: 1 to change, 41 s |
| [15](screenshots/15-dial-50-apply.png) | `primary_traffic_dial = 50`: 1 to change, 1 min 2 s |
| [16](screenshots/16-dial-50-status.png) | eu-west-1 dial 50.0% |
| [17](screenshots/17-dial-50-mix.png) | 300 connections: 154 eu-west-1, 146 us-east-1 |
| [18](screenshots/18-dial-back-to-100.png) | Dial back to 100%: 1 to change, 31 s |
| [19](screenshots/19-failover-watcher-before.png) | Failover drill: the terminal authorising back to back, all eu-west-1 |
| [20](screenshots/20-failover-stop-eu-west-1.png) | The switch stopped on all 3 eu-west-1 instances through SSM |
| [21](screenshots/21-failover-to-us-east-1.png) | `ConnectionResetError` failures, then us-east-1 answering |
| [22](screenshots/22-failover-ga-status-unhealthy.png) | The accelerator's view: eu-west-1 UNHEALTHY, us-east-1 HEALTHY |
| [23](screenshots/23-failover-start-eu-west-1.png) | The switch started again in eu-west-1 |
| [24](screenshots/24-failover-back-to-eu-west-1.png) | Traffic moving back to eu-west-1, each static IP on its own |
| [25](screenshots/25-failover-drill-summary.png) | The live drill summary (two fields were wrong; see [failover](failover.md)) |
| [26](screenshots/26-edge-compare-cloudfront.png) | ip-ranges.json counts; both static IPs inside the Global Accelerator ranges; DNS gives the same two |
| [27](screenshots/27-results-summary-accelerator.png) | Results summary: accelerator snapshots |
| [28](screenshots/28-results-summary-edge-terraform.png) | Results summary: edge comparison and Terraform lines |
| [29](screenshots/29-destroy-48.png) | `Destroy complete! Resources: 48 destroyed.` |
| [30](screenshots/30-clean-check.png) | Clean check: nothing left; empty state of 587 bytes |
