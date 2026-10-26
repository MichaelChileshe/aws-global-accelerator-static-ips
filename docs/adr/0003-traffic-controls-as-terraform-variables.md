# ADR 0003: Weights and dials as Terraform variables, not console changes

**Status:** accepted

## Context
Traffic shifting is an operational action: a canary, draining a Region, recovering slowly. It's easy to do in the console, and just as easy to forget to undo.

## Decision
- **The weights and dials are variables,** each with validation: `canary_weight` 0–255 and `primary_traffic_dial` / `dr_traffic_dial` 0–100. `primary_nlb_weight` (200) is a variable without a range check.
- **A drill is one line** in `infra/phases.auto.tfvars`.
- **Ending the drill** means deleting the line and applying again.

## Consequences
- **Every change is a reviewed plan:** each drill was `1 to change` on one endpoint group.
- **The state always says what the traffic split is.** A `terraform plan` shows any drift if someone changes it in the console.
- **Each apply took 31 s to 1 min 2 s,** because the provider waits for the accelerator to be `DEPLOYED`. That's fine for planned changes. For an emergency, the console or CLI is faster, and Terraform will show the difference afterwards.
