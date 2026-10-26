#!/usr/bin/env python3
"""Regenerates docs/architecture.svg + docs/architecture.png using the OFFICIAL AWS Architecture Icons.

The icon pack is not committed (AWS licenses it for diagrams, not redistribution). Download it from
https://aws.amazon.com/architecture/icons/, unzip, then:

    AWS_ICONS_DIR=/path/to/unzipped-icon-package python3 build_architecture.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from awsdiag import Diagram, GREY, INK

TERM, GA, PRI, DR, CAN, IAC, OPS = ("#2E73B8", "#8C4FFF", "#3F8624", "#D86613", "#E7157B", "#7B42BC", "#7D8998")
d = Diagram(1900, 1180)
d.text(40, 40, "Two static IPs in front of two Regions: Global Accelerator for a raw-TCP payment switch, "
               "built and destroyed with Terraform", 19, "bold")
d.text(40, 64, "Nkosi Payments card-authorisation switch  ·  TCP 7000, no HTTP  ·  eu-west-1 primary, us-east-1 DR  ·  "
               "every resource declared in Terraform, state in S3 with native locking", 13, "normal", GREY)


def node(key, x, y, title, lines=(), color=INK, size=44):
    d.icon(key, x, y, size)
    d.text(x + size + 10, y + 15, title, 12.5, "bold", color)
    for i, l in enumerate(lines):
        d.text(x + size + 10, y + 32 + i * 15, l, 11, "normal", GREY)


# ---------------------------------------------------------------- the terminal side
d.box(40, 100, 300, 250, TERM, fill="#F2F7FC", dashed=False)
d.text(56, 126, "Card terminals", 13.5, "bold", TERM)
node("client", 56, 144, "My laptop as a terminal", ["scripts/terminal.py", "AUTH line over raw TCP 7000",
                                                      "new connection per authorisation"], TERM, 40)
d.text(56, 238, "The retailer's firewall allow-list:", 12, "bold", INK)
d.text(56, 258, "15.197.220.221/32", 12, "normal", INK)
d.text(56, 276, "166.117.216.165/32", 12, "normal", INK)
d.text(56, 298, "the same two addresses through every", 11, "normal", GREY)
d.text(56, 314, "drill: weights, dial, Region failover", 11, "normal", GREY)

d.box(40, 380, 300, 300, IAC, fill="#F7F2FC", dashed=False)
d.text(56, 406, "My machine (WSL)", 13.5, "bold", IAC)
d.text(56, 430, "terraform plan / apply / destroy", 12, "bold", INK)
d.text(56, 448, "bootstrap/  infra/  modules/region", 11, "normal", GREY)
d.text(56, 466, "drills = variables in phases.auto.tfvars:", 11, "normal", GREY)
d.text(56, 482, "canary_weight, primary_traffic_dial", 11, "normal", GREY)
d.text(56, 510, "quality gates before any apply:", 12, "bold", INK)
d.text(56, 528, "fmt · validate · tflint · checkov", 11, "normal", GREY)
d.text(56, 556, "the drills run as commands:", 12, "bold", INK)
d.text(56, 574, "ga_status (API in us-west-2)", 11, "normal", GREY)
d.text(56, 592, "region_ctl stop/start (SSM)", 11, "normal", GREY)
d.text(56, 610, "terminal probe / mix / watch", 11, "normal", GREY)
d.text(56, 628, "edge_compare (ip-ranges.json)", 11, "normal", GREY)
d.text(56, 656, "no SSH, no key pair, no inbound admin port", 11, "normal", GREY)

d.box(40, 710, 300, 170, OPS, fill="#F7F8F8", dashed=True)
node("cloudfront", 56, 728, "Why not CloudFront?", ["HTTP/HTTPS only: the switch", "speaks raw TCP",
                                                     "214 IPv4 blocks, 4,225,413", "addresses to allow-list",
                                                     "(ip-ranges.json, 26 Oct 2026)"], OPS, 40)

# ---------------------------------------------------------------- AWS
d.group("cloud", 370, 90, 1100, 1070, "AWS Cloud")
node("s3_bucket", 1170, 100, "nkosi-tfstate-(account id)", ["state key aws-global-accelerator-static-ips/",
                                                          "S3-native lock file (use_lockfile)"], IAC, 36)

node("global_accelerator", 410, 140, "nkosi-paysw  (AWS Global Accelerator)",
     ["2 static anycast IPv4 announced from AWS edge locations",
      "listener TCP 7000 · client affinity NONE · client IP preservation off",
      "health = each NLB's own target health · API in us-west-2"], GA, 56)
node("edge_location", 410, 228, "Nearest edge location", ["my TCP connection ends here; Global Accelerator",
                                                          "opens its own to the NLB over the AWS network"], GA, 36)
d.line([(340, 190), (404, 190)], TERM, width=2.6)
d.label(342, 176, "TCP 7000", TERM, 10)

# endpoint-group panel
d.box(890, 136, 260, 150, GA, fill="#F6F2FE", dashed=False)
d.text(904, 158, "Endpoint groups", 12.5, "bold", GA)
d.text(904, 178, "eu-west-1  dial 100%  (50% in drill)", 11, "normal", INK)
d.text(904, 194, "   main NLB weight 200", 11, "normal", GREY)
d.text(904, 210, "   canary NLB weight 0  (50 in drill)", 11, "normal", GREY)
d.text(904, 230, "us-east-1  dial 100%", 11, "normal", INK)
d.text(904, 246, "   main NLB weight 128", 11, "normal", GREY)
d.text(904, 270, "both at 100%: nearest healthy Region wins", 10.5, "normal", GREY)


def region(y, h, name, label, cidr, color, nlbs):
    d.group("region", 390, y, 1060, h, f"{name}  ({label})")
    d.group("vpc", 410, y + 44, 1020, h - 64, f"{cidr}")
    d.group("public", 430, y + 88, 980, h - 120, "2 public subnets, one per AZ (NLB nodes and instances in both)")
    yy = y + 140
    for n, (title, lines, targets, col) in enumerate(nlbs):
        ny = yy + n * 130
        node("nlb", 450, ny, title, lines, col, 44)
        for k, (tx, tt, tl) in enumerate(targets):
            node("ec2_instance", tx, ny - 6 + k * 0, tt, tl, col, 40)
            d.line([(700, ny + 22), (tx - 6, ny + 22)], col, width=1.6)
    return yy


region(310, 420, "eu-west-1", "primary, nearest to the terminals", "nkosi-paysw-eu-vpc 10.150.0.0/16", PRI, [
    ("nkosi-paysw-eu (NLB)", ["internet-facing, cross-zone, TCP 7000", "target group: TCP check every 10 s, 2 to flip"],
     [(950, "switch-0 · switch-1", ["t4g.nano, AL2023 arm64", "paysw.py under systemd", "one in each AZ"])], PRI),
    ("nkosi-paysw-eu-canary (NLB)", ["the new switch version's way in", "weight 0 = no traffic"],
     [(950, "canary", ["t4g.nano, same code,", "ROLE=canary, first AZ"])], CAN),
])
region(760, 300, "us-east-1", "DR", "nkosi-paysw-us-vpc 10.151.0.0/16", DR, [
    ("nkosi-paysw-us (NLB)", ["internet-facing, cross-zone, TCP 7000", "same target group settings"],
     [(950, "switch-0 · switch-1", ["t4g.nano, AL2023 arm64", "same paysw.py (sha256 9a0d72f4...)"])], DR),
])

# accelerator to the two Regions
d.line([(438, 196), (438, 286), (470, 286), (470, 446)], PRI, width=2.4)
d.label(454, 296, "eu-west-1 endpoint group", PRI, 10)
d.line([(392, 210), (380, 210), (380, 920), (446, 920)], DR, width=2.4)
d.label(384, 744, "us-east-1 endpoint group", DR, 10)

# management
node("iam_role", 1180, 186, "nkosi-paysw-role", ["AmazonSSMManagedInstanceCore only"], OPS, 32)
node("ssm", 1180, 240, "SSM Run Command", ["region_ctl: stop / start / status"], OPS, 32)
d.text(410, 1100, "Instances accept TCP 7000 only from inside their VPC (the NLB); IMDSv2 required; encrypted gp3; "
                  "the NLBs are reachable directly only for the latency comparison.", 11, "normal", GREY)
d.text(410, 1118, "The account ID is never written into the code: the state bucket name is passed at terraform init.",
       11, "normal", GREY)

# ---------------------------------------------------------------- measured panel
bx, by = 1490, 90
d.box(bx, by, 390, 1070, "#D5DBDB", fill="#fff", dashed=False)
d.text(bx + 14, by + 26, "Measured (one build, 26 October 2026)", 14, "bold")
res = [
    ("Static IPs", GA, ["2 IPv4, both inside AWS's GLOBALACCELERATOR", "ranges; DNS name gave the same 2, 10 of 10",
                        "same 2 IPs through every drill"]),
    ("Full authorisation from my laptop (p50)", TERM, ["through the static IPs: 474.65 / 500.55 ms",
                                                      "straight to eu-west-1 NLB: 614.1 ms",
                                                      "straight to us-east-1 NLB: 716.7 ms"]),
    ("Canary by weight (200 vs 50)", CAN, ["300 connections: 211 main / 89 canary",
                                           "29.7% on the canary (weight ratio 20%)"]),
    ("Traffic dial eu-west-1 at 50%", DR, ["300 connections: 154 eu-west-1 /", "146 us-east-1 (48.7% spilled)"]),
    ("eu-west-1 down (switch stopped)", PRI, ["first failure 4.0 s after the stop",
                                              "first us-east-1 answer 58.24 s later",
                                              "214 failed authorisations, each static",
                                              "IP converged on its own (last fails 10.5 s apart)"]),
    ("eu-west-1 back", PRI, ["first eu-west-1 answer 64.47 s after start",
                             "0 failed: us-east-1 served meanwhile"]),
    ("Along the way", OPS, ["one DR instance hung: SSM stuck, NLB", "unhealthy; forced reboot fixed it",
                            "my SSM helper now gives up after 3 min"]),
    ("Terraform", IAC, ["48 added; each drill 1 change in place;", "Destroy complete! 48 destroyed",
                        "clean check: nothing left"]),
]
y = by + 58
for title, c, ls in res:
    d.text(bx + 14, y, title, 12, "bold", c)
    for l in ls:
        y += 16
        d.text(bx + 14, y, l, 11.2)
    y += 26

here = os.path.dirname(os.path.abspath(__file__))
d.save(os.path.join(here, "..", "architecture.svg"), os.path.join(here, "..", "architecture.png"))
print("wrote docs/architecture.svg and docs/architecture.png")
