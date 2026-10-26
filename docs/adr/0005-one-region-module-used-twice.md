# ADR 0005: One Region module, used twice

**Status:** accepted

## Context
The primary and DR Regions must run the same switch on the same network shape. If the DR copy is hand-built or copy-pasted, it drifts, and drift in DR is only discovered on the day it's needed.

## Decision
- **`infra/modules/region`** is called twice: `module.primary` (eu-west-1, through the `aws.primary` provider alias) and `module.dr` (us-east-1).
- **The only differences are inputs:** name, VPC range, instance count and `with_canary`.
- **The switch code is `filebase64("app/paysw.py")`** in both.

## Consequences
- **Same code, verifiably.** The same SHA-256 (`9a0d72f4522368cf…`) was measured on all five instances.
- **The canary exists only in the primary Region,** controlled by one flag.
- **Changes to the module reach both Regions in one plan,** and that plan shows them side by side.
