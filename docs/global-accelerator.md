# Global Accelerator, the static IPs and the latency test

## What Terraform builds

| Part | Resources | Notes |
|---|---|---|
| IAM | 3 | `nkosi-paysw-role` with only `AmazonSSMManagedInstanceCore`, plus its attachment and the `nkosi-paysw-profile` instance profile. IAM is global, so one role serves both Regions. |
| eu-west-1 (`module.primary`) | 23 | VPC, 2 public subnets, internet gateway, route table, default route, 2 associations, security group with 1 ingress and 1 egress rule, 3 instances (switch-0, switch-1, canary), 2 NLBs (main, canary), 2 target groups, 2 listeners, 3 target attachments |
| us-east-1 (`module.dr`) | 18 | The same, without the canary: 2 instances, 1 NLB, 1 target group, 1 listener, 2 attachments |
| Global Accelerator | 4 | Accelerator, TCP 7000 listener, 2 endpoint groups |
| **Total** | **48** | `terraform state list` shows **52**, because it also lists 4 data sources: the AZ list and the AMI parameter, once per Region |

The apply log ([`results/raw/tf-apply-base.txt`](results/raw/tf-apply-base.txt)) shows where the time went:

| Resource | Creation took |
|---|---|
| Instances | 16–17 s each |
| Accelerator | 1 min 20 s |
| Listener | 38 s |
| NLBs (3) | 2 min 48 s to 2 min 49 s, in parallel |
| Endpoint groups | 31 s (eu-west-1), then 29 s (us-east-1) |

The endpoint groups have to wait for the NLBs, and I create the second only after the first. Global Accelerator applies changes to an accelerator one at a time, so I make Terraform do the same rather than risk a conflict ([ADR 0004](adr/0004-one-accelerator-change-at-a-time.md)).

## The accelerator's own view

`scripts/ga_status.py` reads the accelerator through its API, which lives in **us-west-2** whatever Regions the endpoints are in. Every snapshot is saved in [`results/raw/`](results/raw/).

```
nkosi-paysw  status=DEPLOYED  enabled=True
  static IPs: 15.197.220.221  166.117.216.165    DNS: a68b840701c2ad124.awsglobalaccelerator.com
  listener: TCP 7000  client affinity NONE
  eu-west-1  dial 100.0%   health check TCP:7000 every 10 s, threshold 3
      nkosi-paysw-eu         weight 200  HEALTHY
      nkosi-paysw-eu-canary  weight   0  HEALTHY
  us-east-1  dial 100.0%   health check TCP:7000 every 10 s, threshold 3
      nkosi-paysw-us         weight 128  HEALTHY
```

The health-check settings on the endpoint groups are accepted, but for load balancer endpoints Global Accelerator takes health from the **NLB's own target health**. That's why the target group's settings (TCP every 10 s, 2 checks to flip either way) are the ones that matter in the [failover drill](failover.md).

Before any measurement, I checked the switch on all five instances through SSM:
- `active` on every instance;
- the same SHA-256 (`9a0d72f4522368cf…`) as `filesha256("app/paysw.py")` in the Terraform output.

Screenshots [`04`](screenshots/04-ga-status-and-primary-switches.png) and [`08`](screenshots/08-dr-switches-healthy-again.png).

## One authorisation by hand

```
$ printf 'AUTH POS-0001 2599 1700000000000\n' | nc -w 3 15.197.220.221 7000
APPROVED eu-west-1 i-0add9540a72758534 2201BF 1700000000000 10.150.2.229
```

- **eu-west-1 answered,** because from where I sit it's the nearest healthy Region and both dials were at 100%.
- **`2201BF`** is the first 6 hex characters of the SHA-256 of the request. The same request gets the same code in any Region.
- **`10.150.2.229`** is the address the switch saw: the NLB's private address in the eu-west-1 VPC. Client IP preservation is off on both the endpoint and the target group, so the instance's security group only has to allow its own VPC range.

## Latency: the static IPs against each NLB directly

`terminal.py probe` made 30 authorisations against each target, each on a new TCP connection. Data: [`results/latency-probe.csv`](results/latency-probe.csv). Screenshot: [`10`](screenshots/10-nc-probe-and-baseline-mix.png).

| Target | OK | Answered by | Connect p50 (ms) | Full authorisation p50 / p90 (ms) |
|---|---|---|---|---|
| Static IP 1 (`15.197.220.221`) | 30/30 | eu-west-1 | 101.05 (to the edge) | **474.65** / 512.6 |
| Static IP 2 (`166.117.216.165`) | 30/30 | eu-west-1 | 96.65 (to the edge) | **500.55** / 512.7 |
| eu-west-1 NLB directly | 30/30 | eu-west-1 | 307.1 | **614.1** / 615.0 |
| us-east-1 NLB directly | 30/30 | us-east-1 | 409.05 | **716.7** / 819.1 |

**How to read it.** Global Accelerator ends my TCP connection at the nearest AWS edge location and opens its own connection onward to the NLB. So for the static IPs, "connect" only measures my laptop to the edge, about 100 ms. An NLB passes the connection straight through, so its connect time covers the whole path to the instance. The fair comparison is the **full authorisation**: the round trip a terminal actually waits for. Through the static IPs it was **114–139 ms faster at the median** than going straight to the same Region's NLB. The data shows where that came from: the TCP handshake finished at the nearby edge in about 100 ms instead of 307 ms to the NLB. After the handshake, the rest of the round trip took about 374–404 ms through Global Accelerator against about 307 ms direct, so the onward leg was not faster here. The whole gain was the handshake ending close to me.

This is one laptop, one morning. Terminals elsewhere will see different numbers, but the comparison method is the same.

## Static IPs: what "static" was worth here

- The same two addresses answered through all three drills: a canary, a traffic dial and a whole-Region failover. Every [`ga-status-*.json`](results/raw/) snapshot lists the same pair.
- [`edge_compare.py`](../scripts/edge_compare.py) found both addresses inside AWS's published `GLOBALACCELERATOR` ranges.
- It resolved the accelerator's DNS name 10 times and got exactly the same two addresses every time.

A retailer's firewall team allow-lists two `/32`s once, and nothing behind them ever needs another ticket.
