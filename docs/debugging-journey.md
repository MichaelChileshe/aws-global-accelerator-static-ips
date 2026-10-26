# Debugging journey

## Before the build: reading my own code against how AWS behaves

Before I applied anything, I reviewed the configuration and scripts against the documented behaviour of Global Accelerator, NLB and SSM. Four changes came out of it:

1. **The endpoint groups are now created one after the other.** Global Accelerator applies changes to an accelerator one at a time, so the us-east-1 endpoint group now `depends_on` the eu-west-1 one ([ADR 0004](adr/0004-one-accelerator-change-at-a-time.md)).
2. **The switch now starts after a reboot.** Its systemd unit had no `[Install]` section, so `systemctl enable` would have done nothing at boot. I added `WantedBy=multi-user.target`. That mattered later: the reboot of the hung instance (below) brought the switch back on its own.
3. **The latency probe compares full authorisation times.** Global Accelerator ends TCP at the edge, so a static IP's "connect" time only reaches the edge. The probe's labels and my write-up now compare the full authorisation instead.
4. **The failover drill now expects resets.** I had expected "connection refused" when the Region was down. Because the edge always accepts the connection, the real symptom is a reset after connecting. That's exactly what all 214 failures were.

I also ran the Terraform through `validate`, `tflint` and a mocked plan before touching AWS, which confirmed 48 resources plus 4 data sources.

## 1. The first apply ended without creating anything

I ran the plan and apply in one block, with the plan output going to a file. The terminal went quiet for a long time. When I checked:
- no accelerator existed;
- no Terraform process was running;
- `terraform state list` returned **0**.

Applying the saved plan again failed with:

```
Error: Saved plan is stale
The given plan file can no longer be applied because the state was changed by another operation after the plan was created.
```

So the first apply had run and touched the state, but created nothing. I hadn't kept its output, so I can't say what stopped it.

**Fix:** I re-planned (`Plan: 48 to add`) and applied with `2>&1 | tee build/results/tf-apply-base.txt`, so the output was on screen and in a file. That apply finished: `48 added`.

**Lesson:** every apply in this repo is logged to a file. An error I can't read again is an error I can't fix.

## 2. One DR switch hung, and my SSM helper hung with it

Screenshots [`05`](screenshots/05-dr-status-check-hangs.png)–[`08`](screenshots/08-dr-switches-healthy-again.png). Times are UTC.

| Time | What I saw |
|---|---|
| 04:31:46 | Both us-east-1 instances booted. The boot log shows the switch `active`, the expected SHA-256 and `paysw ready in us-east-1 (main)`. |
| 04:38:15 | `ga_status`: every endpoint `HEALTHY`. |
| 04:39:58 | `region_ctl.py status dr`. `i-0581e2948846db3b5` answered in 6 s. `i-007d44cbd6a491f79` never did. |
| ~04:46 | `list-command-invocations`: that instance's command still `InProgress`. EC2 status checks `running ok ok`. |
| ~04:49 | Target health (copied from my terminal; the screenshot only covers the later checks): `i-007d44cbd6a491f79 unhealthy Target.FailedHealthChecks`, while the other instance was `healthy`. |
| ~04:49 | Console log: no out-of-memory, `hung_task` or other kernel message after boot. |
| ~04:50:35 | `aws ec2 reboot-instances`. A check every 15 s for the next 3½ minutes: still `unhealthy`. |
| 04:54:44 | The console log shows a fresh boot, about 4 minutes after the request. |
| 04:57 | Both targets `healthy`. The status command answered on both instances, with the same SHA-256. |

**What I know:**
- The switch started correctly, then stopped answering both the NLB health check and SSM.
- EC2's instance-level checks still passed.
- A reboot request took about 4 minutes to turn into a real restart. EC2 forces a hard reboot when an instance doesn't shut down cleanly, which fits a machine that had stopped responding.
- After the restart, everything worked. The systemd unit started the switch at boot.

**What I don't know:** the cause. The console log has nothing from before the reboot, and I had no memory or disk metrics from inside the instance. `t4g.nano` has 512 MiB of memory, and the log shows Amazon Linux running zram swap. That made memory a reasonable suspect, but nothing I captured proves it, so I'm not claiming it.

**What I'd do differently:**
- run the CloudWatch agent (memory, disk) on the instances;
- capture `get-console-screenshot` before rebooting;
- run the same build on `t4g.micro` to see whether it recurs.

### My own bug in that moment

`scripts/ssm_run.py` polled `get-command-invocation` in a loop with **no time limit**. When one instance never answered, the script waited forever, and I had to Ctrl+C it (the traceback is in screenshot [`05`](screenshots/05-dr-status-check-hangs.png)).

**Fix:**
- `run()` now takes a `timeout` (default 180 s);
- it prints `still waiting for: <instance> (<status>)` every 15 s;
- on timeout, it exits naming each instance and its last status.

I tested it against a mocked instance stuck in `InProgress`.

**Lesson:** any loop that waits on a remote system needs a deadline. A health check in an operations script should never be the thing that hangs.

## 3. My failover summary got two fields wrong

The live summary (screenshot [`25`](screenshots/25-failover-drill-summary.png)) said `last_answer_from_stopped_region: 05:34:42.793Z`. That's after the restart, not before the outage: the function took the last eu-west-1 answer anywhere after the stop event. It also said `failed_after_stop: 209`, because it stopped counting at the first us-east-1 answer and missed 5 later on-and-off failures on one static IP. The real count is 214.

**Fix:**
- Each action is now analysed only up to the next action. So the stop window ends when the start is sent.
- The summary adds `last_failure`, `first_to_last_failure_s` and a per-static-IP breakdown.
- `terminal.py summarise` rebuilds the summary from the saved raw log, and I regenerated every published number from it.

The original is kept as [`results/raw/watch-failover-summary-as-run.json`](results/raw/watch-failover-summary-as-run.json).

**Lesson:** keep the raw log, not just the summary. The summary had a bug, and the raw data let me fix it after the infrastructure was gone.

## 4. The canary split didn't match the weights

At weight 50 against 200, I expected about 20% on the canary and measured **29.7%** (89 of 300). I report the measured number and the expected one side by side in [traffic controls](traffic-controls.md), rather than rounding it into agreement. One client's 300 connections isn't a basis for explaining it.
