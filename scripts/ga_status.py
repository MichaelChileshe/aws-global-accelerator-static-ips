#!/usr/bin/env python3
"""The accelerator as Global Accelerator sees it: status, static IPs, and every endpoint group with its
traffic dial and each endpoint's weight and health. The Global Accelerator API lives in us-west-2,
whichever Regions the endpoints are in.

  python3 scripts/ga_status.py                 # print once, save build/results/ga-status-<label>.json
  python3 scripts/ga_status.py --wait          # repeat until DEPLOYED and every weighted endpoint HEALTHY
  python3 scripts/ga_status.py --label after-dial
"""
import argparse
import sys
import time
from datetime import datetime, timezone

from kit_aws import aws, tf_output, write_result

GA = ("--region", "us-west-2")


def snapshot():
    arn = tf_output("accelerator_arn")
    acc = aws("globalaccelerator", "describe-accelerator", "--accelerator-arn", arn, *GA)["Accelerator"]
    lst = aws("globalaccelerator", "list-listeners", "--accelerator-arn", arn, *GA)["Listeners"][0]
    groups = aws("globalaccelerator", "list-endpoint-groups", "--listener-arn", lst["ListenerArn"], *GA)["EndpointGroups"]
    snap = {
        "taken_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "name": acc["Name"], "status": acc["Status"], "enabled": acc["Enabled"], "dns_name": acc["DnsName"],
        "static_ips": [ip for s in acc["IpSets"] for ip in s["IpAddresses"]],
        "listener": {"protocol": lst["Protocol"], "ports": lst["PortRanges"], "client_affinity": lst["ClientAffinity"]},
        "groups": [],
    }
    for g in sorted(groups, key=lambda g: g["EndpointGroupRegion"]):
        snap["groups"].append({
            "region": g["EndpointGroupRegion"], "traffic_dial": g["TrafficDialPercentage"],
            "health_check": f'{g["HealthCheckProtocol"]}:{g.get("HealthCheckPort")} every {g["HealthCheckIntervalSeconds"]} s, '
                            f'threshold {g["ThresholdCount"]}',
            "endpoints": [{"endpoint": e["EndpointId"].split("/")[-2], "weight": e["Weight"],
                           "health": e["HealthState"], "reason": e.get("HealthReason", ""),
                           "client_ip_preservation": e.get("ClientIPPreservationEnabled")}
                          for e in g["EndpointDescriptions"]],
        })
    return snap


def show(s):
    print(f'{s["taken_utc"]}  {s["name"]}  status={s["status"]}  enabled={s["enabled"]}')
    print(f'  static IPs: {"  ".join(s["static_ips"])}    DNS: {s["dns_name"]}')
    print(f'  listener: {s["listener"]["protocol"]} {s["listener"]["ports"][0]["FromPort"]}  '
          f'client affinity {s["listener"]["client_affinity"]}')
    for g in s["groups"]:
        print(f'  {g["region"]:<10} dial {g["traffic_dial"]:>5.1f}%   health check {g["health_check"]}')
        for e in g["endpoints"]:
            print(f'      {e["endpoint"]:<22} weight {e["weight"]:>3}  {e["health"]:<9} {e["reason"]}')


def ready(s):
    weighted = [e for g in s["groups"] for e in g["endpoints"] if e["weight"] > 0]
    return s["status"] == "DEPLOYED" and all(e["health"] == "HEALTHY" for e in weighted)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--label", default="now")
    a = ap.parse_args()
    t0 = time.time()
    while True:
        s = snapshot()
        show(s)
        if not a.wait or ready(s):
            break
        if time.time() - t0 > 1200:
            sys.exit("not DEPLOYED and healthy after 20 minutes: read the health reasons above")
        print("  ... not ready yet, checking again in 20 s\n", flush=True)
        time.sleep(20)
    if a.wait:
        print(f"\nready after {time.time() - t0:.0f} s of waiting")
    print("saved", write_result(f"ga-status-{a.label}", s))


if __name__ == "__main__":
    main()
