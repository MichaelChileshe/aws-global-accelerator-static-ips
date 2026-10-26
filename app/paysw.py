"""paysw: Nkosi Payments' card-authorisation switch, as small as it can be.

Card terminals open a TCP connection to port 7000, send one line and read one line back:

  AUTH <terminal id> <amount in cents> <client timestamp ms>
    -> APPROVED <region> <instance id> <auth code> <client timestamp ms> <peer address>
  PING
    -> PONG <region> <instance id>

Raw TCP, no HTTP: that's the point. Card terminals in retailers' networks speak a TCP protocol
and can only reach IP addresses the retailer's firewall allows. The auth code is derived from
the request, so the same request gets the same code in any region.

Settings come from /etc/paysw.conf (REGION, written by the boot script); the instance id is
read from the instance metadata service once at start.
"""
import hashlib
import socketserver
import sys
import urllib.request

PORT = 7000


def conf():
    out = {}
    try:
        for line in open("/etc/paysw.conf"):
            if "=" in line:
                k, v = line.strip().split("=", 1)
                out[k] = v
    except OSError:
        pass
    return out


def instance_id():
    try:
        req = urllib.request.Request("http://169.254.169.254/latest/api/token", method="PUT",
                                     headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"})
        tok = urllib.request.urlopen(req, timeout=2).read().decode()
        req = urllib.request.Request("http://169.254.169.254/latest/meta-data/instance-id",
                                     headers={"X-aws-ec2-metadata-token": tok})
        return urllib.request.urlopen(req, timeout=2).read().decode()
    except Exception:
        return "local"


REGION = conf().get("REGION", "local")
IID = instance_id()


class Handler(socketserver.StreamRequestHandler):
    timeout = 5

    def handle(self):
        try:
            line = self.rfile.readline(256).decode(errors="replace").strip()
        except OSError:
            return
        if not line:            # a health check: connect, then close
            return
        parts = line.split()
        if parts[0] == "PING":
            reply = f"PONG {REGION} {IID}"
        elif parts[0] == "AUTH" and len(parts) == 4:
            code = hashlib.sha256(" ".join(parts[1:]).encode()).hexdigest()[:6].upper()
            reply = f"APPROVED {REGION} {IID} {code} {parts[3]} {self.client_address[0]}"
        else:
            reply = "ERROR bad-request"
        try:
            self.wfile.write((reply + "\n").encode())
        except OSError:
            pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    with Server(("0.0.0.0", port), Handler) as srv:
        print(f"paysw listening on {port} in {REGION} as {IID}", flush=True)
        srv.serve_forever()


if __name__ == "__main__":
    main()
