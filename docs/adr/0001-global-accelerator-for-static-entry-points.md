# ADR 0001: Global Accelerator as the terminals' only entry point

**Status:** accepted

## Context
Card terminals reach the switch over raw TCP on port 7000, and only at addresses the retailers' firewalls allow. The switch has to survive the loss of a Region, and Nkosi can't afford a change ticket at 400 retailers every time something behind the entry point changes.

## Options
1. **NLB with Elastic IPs in one Region.** Fixed addresses, but only in that Region. Failing over means new addresses, so new tickets.
2. **DNS failover (Route 53).** Doesn't help terminals that hard-code addresses, and terminals that cache DNS for hours.
3. **CloudFront.** HTTP/HTTPS only, so it can't carry the switch's raw TCP; normally hundreds of address blocks to allow ([comparison](../cloudfront-vs-global-accelerator.md)).
4. **Global Accelerator.** Two static anycast addresses, TCP listeners, endpoint groups per Region with health-based failover, weights and dials.

## Decision
Option 4. Both Regions sit behind one accelerator, with one endpoint group each.

## Consequences
- **Two addresses, allow-listed once.** Measured: the same pair through the canary, the dial and a whole-Region failover.
- **Failover without DNS took about a minute** in the drill (58.24 s from first failure to first DR answer). Terminals must retry.
- **A fixed fee of about US$18 a month** per accelerator, plus a data-transfer premium per GB.
- **The accelerator must never be deleted in production.** Its addresses go with it.
