# The failover drill: eu-west-1 goes down

## How I ran it

- **Terminal A:** `terminal.py watch --label failover` authorises back to back, alternating between the two static IPs, each on a new connection. The loop waits at most 0.25 s between attempts, so with answers taking about 400 ms the real pace was 609 attempts in 265 s (about one every 0.47 s while answers came back, about one every 0.27 s while they failed). Every attempt is logged to [`results/raw/watch-failover.jsonl`](results/raw/watch-failover.jsonl): time, IP, outcome, Region, instance and milliseconds.
- **Terminal B:** `region_ctl.py stop primary`, then later `region_ctl.py start primary`. These run `systemctl stop|start paysw` on all three eu-west-1 instances (switch-0, switch-1, canary) through SSM. Each action is logged to [`results/raw/events.jsonl`](results/raw/events.jsonl) with the time it was sent and the time all three confirmed.

Nothing changed on the terminal side: same two IPs, no DNS. The instances themselves stayed up. Only the switch process stopped, which is how a crashed application looks to the load balancer.

## What happened

From [`results/raw/watch-failover-summary.json`](results/raw/watch-failover-summary.json) and [`results/failover-timeline.csv`](results/failover-timeline.csv). Times are UTC on 26 October 2026.

| UTC | Event |
|---|---|
| 05:30:17.860 | Watching starts. All 76 attempts before the stop are answered by eu-west-1 (p50 458.55 ms). |
| 05:30:52.222 | **Stop sent.** All three instances confirm `stopped=inactive` by 05:31:03.737. |
| 05:30:55.828 | Last answer from eu-west-1. |
| 05:30:56.252 | **First failure**, 4.03 s after I ran the stop command. That includes the few seconds the SSM call itself takes, so the switch went down less than 4 s before. |
| 05:31:54.491 | **First answer from us-east-1** (`166.117.216.165`), 58.24 s after the first failure and 62.27 s after the stop. |
| 05:31:57.518 | First answer from us-east-1 on `15.197.220.221`. That IP still fails occasionally until 05:32:04.484. |
| 05:31:58 | `ga_status`: both eu-west-1 NLBs `UNHEALTHY`, us-east-1 `HEALTHY` (screenshot [`22`](screenshots/22-failover-ga-status-unhealthy.png)). |
| 05:32:20.500 | **Start sent.** All three confirm `started=active` by 05:32:43.517. |
| 05:33:24.968 | **First answer from eu-west-1 again** (`166.117.216.165`), 64.47 s after the start. |
| 05:33:28.654 | First eu-west-1 answer on `15.197.220.221`. |
| 05:33:30.705 | Last answer from us-east-1. |
| 05:34:42.793 | Watching stops. |

**Totals:** 609 attempts. 395 were approved (240 by eu-west-1, 155 by us-east-1) and **214 failed**.

### Each static IP moved on its own

| Static IP | Failed | First failure | Last failure | First us-east-1 answer | First eu-west-1 answer after the start |
|---|---|---|---|---|---|
| `15.197.220.221` | 110 | 05:30:56.252 | 05:32:04.484 | 05:31:57.518 | 05:33:28.654 |
| `166.117.216.165` | 104 | 05:30:56.510 | 05:31:53.969 | 05:31:54.491 | 05:33:24.968 |

On the way out, `166.117.216.165` had its last failure 10.5 s before `15.197.220.221` did. Between 05:31:54 and 05:32:04, one IP was already answering from us-east-1 while the other still failed now and then. On the way back, `15.197.220.221` kept getting some us-east-1 answers for 7 s after `166.117.216.165` had moved. Each static IP converged separately, so a terminal configured with both addresses gets its service back sooner than one that only knows one of them.

### What the failures looked like

- **All 214 failures were `ConnectionResetError` after connecting**, never a refused connection. Global Accelerator ends the TCP connection at the edge, so the connection always succeeds. The reset arrives when nothing behind it can answer.
- **Failures were fast:** median 261.2 ms, range 213.4–1,331.2 ms. A terminal that retries a failed authorisation loses little by doing so.

### Latency in each phase

| Phase | Answers | p50 (ms) | Range (ms) |
|---|---|---|---|
| eu-west-1 before the stop | 76 | 458.55 | 394.5–522.8 |
| us-east-1 during the outage | 155 | 612.2 | 524.1–714.4 |
| eu-west-1 after recovery (from 05:33:24.968) | 156 | 510.9 | 404.8–534.4 |

Serving from us-east-1 cost about 100–150 ms more per authorisation than eu-west-1 from my laptop: the price of the DR Region being further away.

## Why about a minute

The target group checks each instance every 10 s and marks it unhealthy after **2 failed checks**, so the NLB's own view needs about 20 s. Global Accelerator then has to see that endpoint as unhealthy and steer new connections elsewhere. I measured the total, **58.24 s from the first failure to the first us-east-1 answer**. I didn't measure how that splits between the two stages.

The way back had **zero failures**. us-east-1 kept answering until eu-west-1's targets had passed 2 healthy checks and Global Accelerator moved new connections back. That took 64.47 s from the start command.

**Levers if a minute is too long:**
- a shorter health-check interval or lower threshold on the target group, at the cost of more false alarms;
- a client-side retry on reset, which the fast failures make cheap;
- for a planned move, use the traffic dial *before* stopping anything. That drains the Region gradually with no failures at all.

## A bug in my own summary, fixed

The summary my script printed live (screenshot [`25`](screenshots/25-failover-drill-summary.png)) got two fields wrong. `last_answer_from_stopped_region` said 05:34:42.793: the last eu-west-1 answer **after the restart**, not the last one before the outage. `failed_after_stop` said 209: it counted only up to the first us-east-1 answer and missed the 5 on-and-off failures on `15.197.220.221` after it. The full count is 214.

- **The fix:** the logic now looks only at the window from each action to the next one, and it adds the per-IP breakdown above.
- **`terminal.py summarise --label failover`** rebuilds the summary from the saved raw log. Every figure on this page comes from that rebuilt summary.
- **The as-run summary is kept** in [`results/raw/watch-failover-summary-as-run.json`](results/raw/watch-failover-summary-as-run.json).

The first-failure, first-other-Region and restart timings are the same in both versions.
