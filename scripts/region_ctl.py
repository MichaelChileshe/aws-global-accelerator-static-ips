#!/usr/bin/env python3
"""Stop, start or check the payment switch on every instance in one Region (through SSM), and log
exactly when, so the terminal watcher's timeline can be lined up with what I did.

  python3 scripts/region_ctl.py status primary|dr
  python3 scripts/region_ctl.py stop   primary|dr      # the "Region is down" drill
  python3 scripts/region_ctl.py start  primary|dr

Every stop/start appends one line to build/results/events.jsonl (UTC, milliseconds).
"""
import json
import os
import sys
from datetime import datetime, timezone

from kit_aws import RESULTS, tf_output
from ssm_run import run

CMDS = {
    "status": "echo role=$(grep ROLE /etc/paysw.conf | cut -d= -f2) active=$(systemctl is-active paysw) "
              "sha256=$(sha256sum /opt/paysw/paysw.py | cut -c1-16)",
    "stop": "systemctl stop paysw && echo stopped=$(systemctl is-active paysw)",
    "start": "systemctl start paysw && sleep 1 && echo started=$(systemctl is-active paysw)",
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in CMDS or sys.argv[2] not in ("primary", "dr"):
        sys.exit(__doc__)
    action, which = sys.argv[1], sys.argv[2]
    r = tf_output("regions")[which]
    iids = list(r["instances"]) + ([r["canary_instance"]] if r.get("canary_instance") else [])
    sent = now()
    print(f"{sent}  {action} paysw on {len(iids)} instance(s) in {r['region']} ({which})")
    run(iids, CMDS[action], r["region"])
    done = now()
    print(f"{done}  done")
    if action != "status":
        os.makedirs(RESULTS, exist_ok=True)
        with open(os.path.join(RESULTS, "events.jsonl"), "a") as f:
            f.write(json.dumps({"action": action, "group": which, "region": r["region"], "instances": iids,
                                "sent_utc": sent, "done_utc": done}) + "\n")
        print("logged to build/results/events.jsonl")


if __name__ == "__main__":
    main()
