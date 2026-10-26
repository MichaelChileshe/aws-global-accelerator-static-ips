# Traffic controls: endpoint weights and the traffic dial

Global Accelerator has two separate controls, and I tested both. Each one is a Terraform variable. A drill is a single line in `infra/phases.auto.tfvars`: apply it, measure, then remove the line and apply again.

| Control | Scope | Range | Variable |
|---|---|---|---|
| **Endpoint weight** | Between endpoints in the same endpoint group (Region) | 0–255 | `primary_nlb_weight` (200), `canary_weight` (0) |
| **Traffic dial** | The share of traffic a Region would get that it actually gets; the rest spills to the next-closest healthy Region | 0–100% | `primary_traffic_dial`, `dr_traffic_dial` (100) |

Each change was **`Plan: 0 to add, 1 to change, 0 to destroy.`**, applied as one in-place update to `aws_globalaccelerator_endpoint_group.primary`:

| Change | Apply took |
|---|---|
| canary 0 → 50 | 42 s |
| canary 50 → 0 | 41 s |
| dial 100% → 50% | 1 min 2 s |
| dial 50% → 100% | 31 s |

After each apply, I waited for `ga_status.py --wait` to show `DEPLOYED` and every weighted endpoint healthy before measuring. Data: [`results/traffic-mix.csv`](results/traffic-mix.csv).

## Baseline

200 connections through both static IPs: **200 to the eu-west-1 main NLB (100%)**. The canary was at weight 0 and both dials were at 100%, so every connection went to the nearest Region's main NLB (screenshot [`10`](screenshots/10-nc-probe-and-baseline-mix.png)).

## A canary by weight: main 200, canary 50

| Answered by | Connections | Share |
|---|---|---|
| eu-west-1 main NLB | 211 | 70.3% |
| eu-west-1 canary NLB | 89 | **29.7%** |

Screenshots [`11`](screenshots/11-canary-weight-50-apply.png)–[`14`](screenshots/14-canary-back-to-0.png).

The weights say 50 / (200 + 50) = **20%**, and I measured 29.7%. That's too far off to put down to normal randomness for 300 connections, so I'm not going to describe it as "about 20%". What I can say:

- **The control clearly works.** The canary went from 0 connections at weight 0 to 89 at weight 50, inside the same Region, without the terminal changing anything.
- **This was one run of 300 connections from a single machine.** Global Accelerator decides per connection. All my connections came from one source address with sequential source ports. That's a very narrow sample, and I didn't run it enough times to say whether the gap is how the split behaves at this volume or something else.
- **What I'd do in production:** judge a canary's share from the NLBs' own new-connection metrics over a longer window and real terminal traffic, and move the weight in small steps while watching error rates. One client's sample isn't evidence of a split.

## The traffic dial: eu-west-1 at 50%

| Answered by | Connections | Share |
|---|---|---|
| eu-west-1 main NLB | 154 | 51.3% |
| us-east-1 main NLB | 146 | **48.7%** |

Screenshots [`15`](screenshots/15-dial-50-apply.png)–[`18`](screenshots/18-dial-back-to-100.png).

With the eu-west-1 dial at 50%, about half of the connections that would have gone to eu-west-1 spilled over to the next-closest healthy Region, us-east-1. This is how I'd drain a Region for maintenance (100 → 50 → 0), or bring it back gradually after an incident, while the terminals stay on the same two addresses.

**Weights and dials are different tools.** Weights split traffic between load balancers inside one Region, which suits a canary or a blue/green release. The dial moves traffic between Regions, which suits maintenance, draining and gradual recovery. Neither touches DNS, and neither touches the retailers' firewalls.
