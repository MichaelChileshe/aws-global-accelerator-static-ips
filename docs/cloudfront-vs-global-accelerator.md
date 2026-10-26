# Why not CloudFront in front of the switch?

CloudFront is the other AWS edge network, and it was the first suggestion when the static-IP problem came up. I answered it with evidence rather than opinion.

## 1. The protocol

The switch speaks a raw TCP protocol on port 7000: one line in, one line back. CloudFront serves HTTP and HTTPS, so it can't carry this traffic at all without rewriting both the terminals and the switch. Global Accelerator's listener is plain TCP (UDP is also supported), so nothing had to change on either side.

## 2. The addresses a firewall would have to allow

[`scripts/edge_compare.py`](../scripts/edge_compare.py) reads AWS's published address list, `ip-ranges.json`. This copy had `syncToken 1792984625` and `createDate 2026-10-26-03-17-05`. The script counts the blocks per service. Data: [`results/edge-ranges.csv`](results/edge-ranges.csv). Screenshot: [`26`](screenshots/26-edge-compare-cloudfront.png).

| Service in ip-ranges.json | IPv4 blocks | IPv4 addresses | IPv6 blocks |
|---|---|---|---|
| `CLOUDFRONT` | 214 | 4,225,413 | 34 |
| `CLOUDFRONT_ORIGIN_FACING` | 49 | 344,384 | 38 |
| `GLOBALACCELERATOR` | 132 | 429,312 | 47 |
| **My accelerator** | **2 addresses** | `15.197.220.221`, `166.117.216.165` | n/a (IPv4 accelerator) |

- **CloudFront viewers** normally connect to whichever edge address DNS hands them. To allow-list that, a retailer would have to open all 214 blocks, and keep that list current as AWS changes it, which also lets through every other CloudFront customer's traffic. CloudFront does offer anycast static IPs for distributions that need a fixed list, but it is still HTTP/HTTPS only. The protocol rules CloudFront out here before addresses do.
- **The `GLOBALACCELERATOR` ranges are shared too,** but my accelerator uses exactly **two** addresses from them. Those two are mine for as long as the accelerator exists. The script confirmed both are inside the published ranges.
- **The accelerator's DNS name** resolved to the same two addresses in 10 of 10 lookups, so the name and the allow-list can't drift apart.

(`CLOUDFRONT_ORIGIN_FACING` is the set CloudFront uses to reach *origins*. It's shown for completeness; it's what an origin would allow, not a viewer.)

## When I'd pick which

| Need | Pick |
|---|---|
| Fixed addresses for allow-listing, non-HTTP protocols (TCP/UDP), fast Region failover that doesn't depend on DNS caching | Global Accelerator |
| Caching static or dynamic HTTP content near users, HTTP features at the edge (headers, functions, WAF on HTTP) | CloudFront |
| Both: an HTTP API that also needs fixed addresses | Global Accelerator in front of an ALB, or CloudFront with its own constraints; decide per client |
