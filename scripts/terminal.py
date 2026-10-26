#!/usr/bin/env python3
"""A card terminal: opens a TCP connection to port 7000, sends one AUTH line, reads the answer.
It only knows the accelerator's two static IPs (like a retailer's firewall allow-list).

  python3 scripts/terminal.py probe [--n 30]          # latency: static IPs vs each Region's NLB directly
  python3 scripts/terminal.py mix --label weights [--n 300]
                                                      # which Region / which NLB answered, over n connections
  python3 scripts/terminal.py watch --label failover [--seconds 1800]
                                                      # back-to-back authorisations (at most one per 0.25 s) until Ctrl+C,
                                                      # then the timeline (lined up with events.jsonl)
  python3 scripts/terminal.py summarise --label failover
                                                      # rebuild that summary from the saved .jsonl
Results go to build/results/.
"""
import argparse
import json
import os
import socket
import statistics
import time
from datetime import datetime, timezone

from kit_aws import RESULTS, tf_output, write_result

PORT = 7000


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def authorise(host, seq, timeout=2.0):
    """One authorisation on a new connection. Returns a dict (ok, region, instance, ms timings or error)."""
    t0 = time.time()
    rec = {"t": utc(t0), "target": host, "seq": seq, "ok": False}
    try:
        s = socket.create_connection((host, PORT), timeout=timeout)
    except OSError as e:
        rec.update(error=f"connect: {type(e).__name__}", ms=round((time.time() - t0) * 1000, 1))
        return rec
    t1 = time.time()
    try:
        s.settimeout(timeout)
        s.sendall(f"AUTH POS-{seq % 1000:04d} {1000 + seq % 9000} {int(t0 * 1000)}\n".encode())
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(256)
            if not chunk:
                break
            buf += chunk
    except OSError as e:
        rec.update(error=f"reply: {type(e).__name__}", ms=round((time.time() - t0) * 1000, 1))
        return rec
    finally:
        s.close()
    t2 = time.time()
    parts = buf.decode(errors="replace").split()
    rec.update(connect_ms=round((t1 - t0) * 1000, 1), reply_ms=round((t2 - t1) * 1000, 1), ms=round((t2 - t0) * 1000, 1))
    if len(parts) == 6 and parts[0] == "APPROVED":
        rec.update(ok=True, region=parts[1], instance=parts[2], code=parts[3], seen_from=parts[5])
    else:
        rec["error"] = "reply: " + (" ".join(parts) or "connection closed with no answer")
    return rec


def roles():
    """instance id -> 'eu-west-1 switch' / 'eu-west-1 canary' ..., from the Terraform outputs."""
    out = {}
    for g in tf_output("regions").values():
        for iid in g["instances"]:
            out[iid] = f'{g["region"]} main NLB'
        if g.get("canary_instance"):
            out[g["canary_instance"]] = f'{g["region"]} canary NLB'
    return out


def pct(vals, p):
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(round(p / 100 * (len(vals) - 1))))] if vals else None


def cmd_probe(a):
    ips, regions = tf_output("static_ips"), tf_output("regions")
    targets = [(f"static IP {i + 1}", ip) for i, ip in enumerate(ips)]
    targets += [(f'{g["region"]} NLB direct', g["nlb_dns"]) for g in regions.values()]
    rows = []
    for name, host in targets:
        recs = [authorise(host, i) for i in range(a.n)]
        ok = [r for r in recs if r["ok"]]
        conn, tot = [r["connect_ms"] for r in ok], [r["ms"] for r in ok]
        row = {"target": name, "host": host, "attempts": a.n, "ok": len(ok),
               "answered_by": sorted({r["region"] for r in ok}),
               "connect_ms_p50": statistics.median(conn) if conn else None, "connect_ms_p90": pct(conn, 90),
               "auth_ms_p50": statistics.median(tot) if tot else None, "auth_ms_p90": pct(tot, 90),
               "server_saw": sorted({r["seen_from"] for r in ok})[:3]}
        rows.append(row)
        print(f'{name:<22} {row["ok"]}/{a.n} ok  answered by {",".join(row["answered_by"]) or "-":<10} '
              f'connect p50 {row["connect_ms_p50"]} ms p90 {row["connect_ms_p90"]}   '
              f'full AUTH p50 {row["auth_ms_p50"]} ms p90 {row["auth_ms_p90"]}', flush=True)
    print("saved", write_result("probe", {"taken_utc": utc(time.time()), "rows": rows}))


def cmd_mix(a):
    ips, who = tf_output("static_ips"), roles()
    recs = [authorise(ips[i % len(ips)], i) for i in range(a.n)]
    counts = {}
    for r in recs:
        k = who.get(r.get("instance"), r.get("region", "?")) if r["ok"] else "FAILED"
        counts[k] = counts.get(k, 0) + 1
    print(f"{a.n} connections over both static IPs:")
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<26} {v:>4}  ({100 * v / a.n:.1f}%)")
    print("saved", write_result(f"mix-{a.label}", {"taken_utc": utc(time.time()), "n": a.n, "counts": counts}))


def summarise(recs, events):
    segs = []
    for r in recs:
        key = r["region"] if r["ok"] else "FAILED"
        if segs and segs[-1]["state"] == key:
            segs[-1].update(end=r["t"], count=segs[-1]["count"] + 1)
        else:
            segs.append({"state": key, "start": r["t"], "end": r["t"], "count": 1})
    for s in segs:
        s["seconds"] = round(parse_utc(s["end"]) - parse_utc(s["start"]), 2)
    t_first, t_last = parse_utc(recs[0]["t"]), parse_utc(recs[-1]["t"])
    drills = []
    evs = sorted((e for e in events if t_first <= parse_utc(e["sent_utc"]) <= t_last),   # only while watching
                 key=lambda e: parse_utc(e["sent_utc"]))
    for k, e in enumerate(evs):
        ts = parse_utc(e["sent_utc"])
        te = parse_utc(evs[k + 1]["sent_utc"]) if k + 1 < len(evs) else t_last + 1
        window = [r for r in recs if ts <= parse_utc(r["t"]) < te]     # from this action to the next one
        before = [r for r in recs if parse_utc(r["t"]) < ts]
        d = {"action": e["action"], "region": e["region"], "sent_utc": e["sent_utc"], "done_utc": e["done_utc"]}
        per_ip = {}
        if e["action"] == "stop":
            fails = [r for r in window if not r["ok"]]
            moved = [r for r in window if r["ok"] and r["region"] != e["region"]]
            still = [r for r in window if r["ok"] and r["region"] == e["region"]]
            last_ok = (still or [r for r in before if r["ok"] and r["region"] == e["region"]] or [None])[-1]
            d["last_answer_from_stopped_region"] = last_ok["t"] if last_ok else None
            d["first_failure"] = fails[0]["t"] if fails else None
            d["first_answer_from_other_region"] = moved[0]["t"] if moved else None
            d["last_failure"] = fails[-1]["t"] if fails else None
            d["failed"] = len(fails)
            if moved:
                d["stop_to_other_region_s"] = round(parse_utc(moved[0]["t"]) - ts, 2)
            if fails and moved:
                d["first_failure_to_other_region_s"] = round(parse_utc(moved[0]["t"]) - parse_utc(fails[0]["t"]), 2)
            if fails:
                d["first_to_last_failure_s"] = round(parse_utc(fails[-1]["t"]) - parse_utc(fails[0]["t"]), 2)
            for ip in sorted({r["target"] for r in window}):
                w = [r for r in window if r["target"] == ip]
                f = [r for r in w if not r["ok"]]
                m = [r for r in w if r["ok"] and r["region"] != e["region"]]
                per_ip[ip] = {"first_failure": f[0]["t"] if f else None, "last_failure": f[-1]["t"] if f else None,
                              "failed": len(f), "first_answer_from_other_region": m[0]["t"] if m else None}
        else:
            back = [r for r in window if r["ok"] and r["region"] == e["region"]]
            other = [r for r in window if r["ok"] and r["region"] != e["region"]]
            d["first_answer_from_region"] = back[0]["t"] if back else None
            d["last_answer_from_other_region"] = other[-1]["t"] if other else None
            d["failed"] = sum(1 for r in window if not r["ok"])
            if back:
                d["start_to_back_s"] = round(parse_utc(back[0]["t"]) - ts, 2)
            for ip in sorted({r["target"] for r in window}):
                w = [r for r in window if r["target"] == ip]
                b = [r for r in w if r["ok"] and r["region"] == e["region"]]
                o = [r for r in w if r["ok"] and r["region"] != e["region"]]
                per_ip[ip] = {"first_answer_from_region": b[0]["t"] if b else None,
                              "last_answer_from_other_region": o[-1]["t"] if o else None,
                              "failed": sum(1 for r in w if not r["ok"])}
        d["per_static_ip"] = per_ip
        drills.append(d)
    by_region = {}
    for r in recs:
        k = r["region"] if r["ok"] else "FAILED"
        by_region[k] = by_region.get(k, 0) + 1
    return {"attempts": len(recs), "ok": sum(r["ok"] for r in recs), "by_region": by_region,
            "first": recs[0]["t"], "last": recs[-1]["t"], "segments": segs, "drills": drills}


def report(s):
    print(f'\n{s["ok"]}/{s["attempts"]} approved  {s["first"]} -> {s["last"]}   by region: {s["by_region"]}')
    print("timeline:")
    for seg in s["segments"]:
        print(f'  {seg["start"]} -> {seg["end"]}  {seg["state"]:<10} {seg["count"]:>5} attempts  {seg["seconds"]} s')
    for d in s["drills"]:
        per_ip = d.pop("per_static_ip")
        print("drill:", json.dumps(d))
        for ip, v in per_ip.items():
            print(f"  {ip:<16}", json.dumps(v))
        d["per_static_ip"] = per_ip


def events_list():
    ev_path = os.path.join(RESULTS, "events.jsonl")
    return [json.loads(l) for l in open(ev_path)] if os.path.exists(ev_path) else []


def cmd_summarise(a):
    """Rebuild watch-<label>-summary.json from the saved watch-<label>.jsonl and events.jsonl."""
    recs = [json.loads(l) for l in open(os.path.join(RESULTS, f"watch-{a.label}.jsonl"))]
    s = summarise(recs, events_list())
    report(s)
    print("saved", write_result(f"watch-{a.label}-summary", s))


def cmd_watch(a):
    ips = tf_output("static_ips")
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, f"watch-{a.label}.jsonl")
    recs, i, t_end = [], 0, time.time() + a.seconds
    print(f"back-to-back authorisations, at most one every {a.interval} s, alternating {ips[0]} / {ips[1]}; Ctrl+C to stop\n", flush=True)
    last_state = None
    try:
        with open(path, "w") as f:
            while time.time() < t_end:
                t0 = time.time()
                r = authorise(ips[i % 2], i)
                recs.append(r)
                f.write(json.dumps(r) + "\n")
                f.flush()
                state = r.get("region") if r["ok"] else "FAILED " + r.get("error", "")
                if state != last_state or i % 40 == 0:
                    print(f'{r["t"]}  #{i:<5} {r["target"]:<15} '
                          + (f'{r["region"]:<10} {r["instance"]}  {r["ms"]} ms' if r["ok"] else f'FAILED  {r["error"]}'),
                          flush=True)
                    last_state = state
                i += 1
                time.sleep(max(0.0, a.interval - (time.time() - t0)))
    except KeyboardInterrupt:
        print("\nstopped")
    if not recs:
        return
    s = summarise(recs, events_list())
    report(s)
    print("saved", path, "and", write_result(f"watch-{a.label}-summary", s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["probe", "mix", "watch", "summarise"])
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--label", default="run")
    ap.add_argument("--seconds", type=int, default=1800)
    ap.add_argument("--interval", type=float, default=0.25)
    a = ap.parse_args()
    if a.mode == "probe":
        a.n = a.n or 30
        cmd_probe(a)
    elif a.mode == "mix":
        a.n = a.n or 300
        cmd_mix(a)
    elif a.mode == "summarise":
        cmd_summarise(a)
    else:
        cmd_watch(a)


if __name__ == "__main__":
    main()
