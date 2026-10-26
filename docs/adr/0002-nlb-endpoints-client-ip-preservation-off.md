# ADR 0002: NLB endpoints, with client IP preservation off

**Status:** accepted

## Context
Global Accelerator can send traffic to an ALB, an NLB, an EC2 instance or an Elastic IP. The switch speaks TCP, so an NLB fits. With client IP preservation on, the instances would see the terminals' public addresses, and their security group would have to allow traffic from the internet.

## Decision
- **NLB endpoints**, internet-facing (so I can also measure the direct path), cross-zone.
- **Client IP preservation off** on both the endpoint and the target group (`preserve_client_ip = false`).
- **The instances' security group** allows TCP 7000 from their own VPC range only.

## Consequences
- **The switch sees the NLB's private address** (measured: `10.150.1.57`, `10.150.2.229` in eu-west-1), not the terminal's.
- **Terminal identity has to come from the protocol,** which it already does: the terminal ID in the `AUTH` line. Audit logs can't rely on the source IP.
- **The NLBs are reachable directly from the internet** in this lab. In production I'd give the NLB a security group that only allows Global Accelerator, or make it internal.
