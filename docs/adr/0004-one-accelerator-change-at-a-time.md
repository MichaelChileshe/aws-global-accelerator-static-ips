# ADR 0004: One change to the accelerator at a time

**Status:** accepted

## Context
Terraform creates independent resources in parallel. The two endpoint groups depend only on the listener and their own NLB, so by default they'd be created together. Global Accelerator applies changes to an accelerator one at a time, and the provider waits for the accelerator to return to `DEPLOYED` after each change.

## Decision
The us-east-1 endpoint group `depends_on` the eu-west-1 endpoint group.

## Consequences
- **The apply log shows them in sequence:** eu-west-1 in 31 s, then us-east-1 in 29 s. No conflicts.
- **About 30 s added** to a full build.
- **Destroy runs in reverse:** endpoint groups, then listener, then accelerator.
