#!/usr/bin/env python3
"""Why not CloudFront in front of the switch? Two facts I can check from here:

1. AWS's published address list (ip-ranges.json): how many address blocks a retailer's firewall
   would have to allow for CloudFront, against Global Accelerator; and whether my two static IPs
   are inside the Global Accelerator blocks.
2. The accelerator's DNS name, resolved repeatedly: always the same two addresses.

  python3 scripts/edge_compare.py
"""
import ipaddress
import json
import socket
import time
import urllib.request

from kit_aws import tf_output, write_result

URL = "https://ip-ranges.amazonaws.com/ip-ranges.json"


def main():
    data = json.load(urllib.request.urlopen(URL, timeout=30))
    count = {}
    nets = {"GLOBALACCELERATOR": [], "CLOUDFRONT": []}
    for p in data["prefixes"]:
        if p["service"] in ("CLOUDFRONT", "GLOBALACCELERATOR", "CLOUDFRONT_ORIGIN_FACING"):
            count.setdefault(p["service"], {"ipv4": 0, "ipv6": 0, "ipv4_addresses": 0})
            count[p["service"]]["ipv4"] += 1
            net = ipaddress.ip_network(p["ip_prefix"])
            count[p["service"]]["ipv4_addresses"] += net.num_addresses
            if p["service"] in nets:
                nets[p["service"]].append(net)
    for p in data["ipv6_prefixes"]:
        if p["service"] in count:
            count[p["service"]]["ipv6"] += 1
    print(f'ip-ranges.json  syncToken {data["syncToken"]}  createDate {data["createDate"]}')
    for svc, c in sorted(count.items()):
        print(f'  {svc:<26} {c["ipv4"]:>4} IPv4 blocks ({c["ipv4_addresses"]:,} addresses)  {c["ipv6"]:>4} IPv6 blocks')

    ips = tf_output("static_ips")
    inside = {ip: any(ipaddress.ip_address(ip) in n for n in nets["GLOBALACCELERATOR"]) for ip in ips}
    print("my static IPs inside a GLOBALACCELERATOR block:", inside)

    dns = tf_output("accelerator_dns")
    seen = set()
    for _ in range(10):
        seen |= {ai[4][0] for ai in socket.getaddrinfo(dns, 7000, socket.AF_INET, socket.SOCK_STREAM)}
        time.sleep(1)
    print(f"{dns} resolved 10 times -> {sorted(seen)}  (same as the static IPs: {sorted(seen) == sorted(ips)})")

    out = {"sync_token": data["syncToken"], "create_date": data["createDate"], "prefix_counts": count,
           "static_ips": ips, "static_ips_inside_ga_ranges": inside, "accelerator_dns": dns,
           "dns_answers_over_10_lookups": sorted(seen), "dns_matches_static_ips": sorted(seen) == sorted(ips)}
    print("saved", write_result("edge-compare", out))


if __name__ == "__main__":
    main()
