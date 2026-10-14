"""Reconnaissance probe for the Source engine "netcon" remote console.

Left 4 Dead 2 started with the launch option `-netconport <port>` opens a
plain-text TCP console. This probe connects to it, prints every console line
with a timestamp and records them to recordings/netcon_<date>.log.

Commands are sent only when asked (--query / --send). The defaults only read
cvars or print information; nothing here changes gameplay.

Usage:
    python tools/netcon_probe.py                      # listen only
    python tools/netcon_probe.py --query 10           # + read state every 10 s
    python tools/netcon_probe.py --send "net_showevents 2"
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import socket
import sys
import time

DEFAULT_QUERY = "status;mp_gamemode;z_difficulty;host_map;sv_gametypes"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=27015)
    ap.add_argument("--password", default="")
    ap.add_argument("--query", type=float, default=0, help="seconds between state queries (0 = never)")
    ap.add_argument("--query-cmd", default=DEFAULT_QUERY)
    ap.add_argument("--send", action="append", default=[], help="command to send once after connecting")
    ap.add_argument("--duration", type=float, default=0, help="stop after N seconds (0 = until Ctrl+C)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = args.out or os.path.join(root, "recordings", f"netcon_{dt.datetime.now():%Y%m%d_%H%M%S}.log")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    t0 = time.monotonic()
    try:
        sock = socket.create_connection((args.host, args.port), timeout=3)
    except OSError as e:
        print(f"Cannot connect to {args.host}:{args.port}: {e}")
        return 1
    print(f"Connected to {args.host}:{args.port}, recording to {out}")
    sock.settimeout(0.5)

    def send(cmd: str) -> None:
        sock.sendall((cmd + "\n").encode("utf-8"))
        log.write(f"{dt.datetime.now():%H:%M:%S.%f}"[:-3] + f" >>> {cmd}\n")
        log.flush()

    buf = b""
    next_query = time.monotonic()
    with open(out, "a", encoding="utf-8", newline="\n") as log:
        if args.password:
            send(f"PASS {args.password}")
        for cmd in args.send:
            send(cmd)
        try:
            while True:
                now = time.monotonic()
                if args.duration and now - t0 > args.duration:
                    break
                if args.query and now >= next_query:
                    send(args.query_cmd)
                    next_query = now + args.query
                try:
                    chunk = sock.recv(65536)
                    if not chunk:
                        print("Connection closed by the game.")
                        break
                    buf += chunk
                except socket.timeout:
                    pass
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.rstrip(b"\r").decode("utf-8", "replace")
                    stamp = f"{dt.datetime.now():%H:%M:%S.%f}"[:-3]
                    log.write(f"{stamp} {text}\n")
                    log.flush()
                    print(f"{stamp} {text}")
        except KeyboardInterrupt:
            pass
        except OSError as e:
            print(f"Connection lost: {e}")
    sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
