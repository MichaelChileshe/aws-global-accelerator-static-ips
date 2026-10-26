#!/usr/bin/env python3
"""Every measured number from build/results/ in one list (and build/results/summary.csv).
Anything not measured yet shows as "-".

  python3 scripts/results.py
"""
import csv
import json
import os
import re

from kit_aws import RESULTS


def j(name):
    p = os.path.join(RESULTS, f"{name}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    rows = []

    def add(section, item, value):
        rows.append((section, item, "-" if value in (None, "") else value))

    files = sorted(os.listdir(RESULTS)) if os.path.isdir(RESULTS) else []
    for name in files:
        if name.startswith("ga-status-") and name.endswith(".json"):
            s = j(name[:-5])
            add("Accelerator", f"{name[10:-5]}: status / static IPs", f'{s["status"]} / {" ".join(s["static_ips"])}')
            for g in s["groups"]:
                add("Accelerator", f'{name[10:-5]}: {g["region"]} dial / endpoints',
                    f'{g["traffic_dial"]}% / ' + ", ".join(f'{e["endpoint"]} w{e["weight"]} {e["health"]}'
                                                            for e in g["endpoints"]))
    p = j("probe")
    for r in (p or {}).get("rows", []):
        add("Latency", f'{r["target"]}: ok / answered by / connect p50 ms (static IP: to edge) / full AUTH p50 / p90 ms',
            f'{r["ok"]}/{r["attempts"]} / {",".join(r["answered_by"])} / {r["connect_ms_p50"]} / '
            f'{r["auth_ms_p50"]} / {r["auth_ms_p90"]}')
    for name in files:
        if name.startswith("mix-") and name.endswith(".json"):
            m = j(name[:-5])
            add("Traffic mix", f'{name[4:-5]} ({m["n"]} connections)',
                ", ".join(f"{k} {v}" for k, v in sorted(m["counts"].items(), key=lambda kv: -kv[1])))
    for name in files:
        if name.startswith("watch-") and name.endswith("-summary.json"):
            s = j(name[:-5])
            add("Watch", f'{name[6:-13]}: approved / attempts / by region', f'{s["ok"]} / {s["attempts"]} / {s["by_region"]}')
            for d in s["drills"]:
                at = d["sent_utc"][11:23]
                if d["action"] == "stop":
                    add("Watch", f'{name[6:-13]}: stop {d["region"]} at {at}: last answer / 1st fail / 1st other Region / last fail',
                        f'{(d.get("last_answer_from_stopped_region") or "")[11:23]} / {(d.get("first_failure") or "")[11:23]} / '
                        f'{(d.get("first_answer_from_other_region") or "")[11:23]} / {(d.get("last_failure") or "")[11:23]}')
                    add("Watch", f'{name[6:-13]}: stop {d["region"]}: failed / stop->other s / 1st fail->other s / 1st->last fail s',
                        f'{d.get("failed")} / {d.get("stop_to_other_region_s")} / {d.get("first_failure_to_other_region_s")} / '
                        f'{d.get("first_to_last_failure_s")}')
                else:
                    add("Watch", f'{name[6:-13]}: start {d["region"]} at {at}: 1st answer back / last other Region / s / failed',
                        f'{(d.get("first_answer_from_region") or "")[11:23]} / {(d.get("last_answer_from_other_region") or "")[11:23]} / '
                        f'{d.get("start_to_back_s")} / {d.get("failed")}')
                for ip, v in d.get("per_static_ip", {}).items():
                    add("Watch", f'{name[6:-13]}: {d["action"]} - {ip}',
                        ", ".join(f"{k} {(str(x)[11:23] if isinstance(x, str) else x)}" for k, x in v.items()))
    e = j("edge-compare")
    if e:
        for svc, c in sorted(e["prefix_counts"].items()):
            add("Edge compare", f"{svc}: IPv4 blocks / IPv4 addresses / IPv6 blocks",
                f'{c["ipv4"]} / {c["ipv4_addresses"]} / {c["ipv6"]}')
        add("Edge compare", "static IPs inside GLOBALACCELERATOR blocks", e["static_ips_inside_ga_ranges"])
        add("Edge compare", "DNS answers over 10 lookups / match static IPs",
            f'{" ".join(e["dns_answers_over_10_lookups"])} / {e["dns_matches_static_ips"]}')
    for name in files:
        if name.startswith("tf-") and name.endswith(".txt"):
            line = None
            for ln in open(os.path.join(RESULTS, name), errors="replace"):
                if re.search(r"^(Plan:|Destroy complete!|Apply complete!|No changes\.)", ln.strip()):
                    line = ln.strip()
            add("Terraform", name, line)
    if not rows:
        print("nothing measured yet")
        return
    w = max(len(r[1]) for r in rows)
    sec = None
    for s, i, v in rows:
        if s != sec:
            print(f"\n== {s}")
            sec = s
        print(f"  {i:<{w}}  {v}")
    with open(os.path.join(RESULTS, "summary.csv"), "w", newline="") as f:
        csv.writer(f).writerows([("section", "item", "value"), *rows])
    print("\nsaved build/results/summary.csv")


if __name__ == "__main__":
    main()
