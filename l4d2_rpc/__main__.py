"""L4D2 Better Presence: a detailed Discord Rich Presence for Left 4 Dead 2.

    python -m l4d2_rpc                 run (waits for the game, updates the card, clears it when the game closes)
    python -m l4d2_rpc --dry-run       same, but prints the card instead of sending it
    python -m l4d2_rpc --simulate      a fake game through every situation (add --dry-run to only print)
    python -m l4d2_rpc --dump          raw state read from the running game, then exit
    python -m l4d2_rpc -v              log every console line and event
    python -m l4d2_rpc doctor          check Python, Discord, the game, its launch options and the console
    python -m l4d2_rpc setup           print the Steam launch options to paste (new console password)
    python -m l4d2_rpc startup on|off  start (or not) silently with Windows
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import secrets
import socket
import subprocess
import sys
import time
from dataclasses import asdict
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import config as config_mod
from . import data, steam, system
from .app import App, DryRunClient, Sender
from .discord_ipc import DiscordClient, discord_running, handshake_test
from .parser import ConsoleParser
from .presence import build_activity
from .simulate import scenario
from .state import Tracker

log = logging.getLogger("l4d2rpc")
ROOT = Path(__file__).resolve().parent.parent
STARTUP_LINK_NAME = "L4D2 Better Presence.lnk"


def setup_logging(verbose: bool, console: bool = True) -> Path:
    folder = config_mod.log_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "l4d2rpc.log"
    log.setLevel(logging.DEBUG if verbose else logging.INFO)
    file_handler = RotatingFileHandler(path, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(file_handler)
    if console and sys.stdout is not None:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%H:%M:%S"))
        log.addHandler(handler)
    return path


def print_card(title: str, activity: dict | None, now: float) -> None:
    print(f"\n[{title}]")
    if activity is None:
        print("  (no card: cleared)")
        return
    a = activity.get("assets", {})
    start = activity.get("timestamps", {}).get("start")
    elapsed = f"{int(now - start) // 60}:{int(now - start) % 60:02d} elapsed" if start else "-"
    party = activity.get("party", {}).get("size")
    print(f"  details : {activity.get('details', '-')}")
    print(f"  state   : {activity.get('state', '-')}" + (f"   ({party[0]} of {party[1]})" if party else ""))
    print(f"  timer   : {elapsed}")
    print(f"  large   : {a.get('large_text', '-')}  <{(a.get('large_image') or '-')[:70]}>")
    print(f"  small   : {a.get('small_text', '-')}  <{(a.get('small_image') or '-')[:70]}>")


# ------------------------------------------------------------------------------------------------ simulate
def run_simulation(cfg: dict, dry_run: bool) -> int:
    parser, tracker = ConsoleParser(), Tracker()
    start = time.time()
    now = start
    tracker.game_started(start - 60, now)
    client = DryRunClient() if dry_run else DiscordClient(cfg["client_id"])
    sender = Sender(client)
    if not dry_run:
        log.info("Simulation on your real Discord profile: each situation stays ~10-20 s. Ctrl+C to stop.")
    try:
        for step in scenario():
            if step.process == "closed":
                tracker.game_closed()
            for line in step.lines:
                for ev in parser.feed(line):
                    tracker.apply(ev, now)
            tracker.tick(now)
            activity, key = build_activity(tracker.state, cfg, now, step.idle)
            if dry_run:
                print_card(step.title, activity, now)
                now += step.seconds
                continue
            log.info("Situation: %s", step.title)
            end = time.monotonic() + step.seconds
            while time.monotonic() < end:
                activity, key = build_activity(tracker.state, cfg, time.time(), step.idle)
                sender.offer(activity, key, time.monotonic())
                time.sleep(0.5)
            now = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        client.stop()
    return 0


# ------------------------------------------------------------------------------------------------ dump
def netcon_exchange(port: int, password: str, command: str, wait: float = 1.5) -> list[str] | None:
    try:
        sock = socket.create_connection(("127.0.0.1", port), timeout=3)
    except OSError:
        return None
    sock.settimeout(0.3)
    if password:
        sock.sendall(f"PASS {password}\n".encode())
    sock.sendall((command + "\n").encode())
    buf = b""
    end = time.monotonic() + wait
    while time.monotonic() < end:
        try:
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
        except socket.timeout:
            pass
    sock.close()
    return buf.decode("utf-8", "replace").splitlines()


def netcon_settings(cfg: dict) -> tuple[int | None, str, steam.LaunchOptions | None]:
    opts = steam.launch_options()
    port = cfg["netcon_port"] or (opts.netcon_port if opts else None)
    password = cfg["netcon_password"] or ((opts.netcon_password or "") if opts else "")
    return port, password, opts


def run_dump(cfg: dict) -> int:
    port, password, _ = netcon_settings(cfg)
    if not port:
        print("No -netconport in the game's launch options: run 'L4D2RPC.bat setup'.")
        return 1
    lines = netcon_exchange(port, password, "name;cl_language;z_difficulty;status;g15_dumpplayer")
    if lines is None:
        print(f"The game console is not reachable on port {port}: is Left 4 Dead 2 running?")
        return 1
    print("---- raw console answer ----")
    for line in lines:
        print(line)
    parser, tracker = ConsoleParser(), Tracker()
    now = time.time()
    game = system.find_game()
    if game:
        tracker.game_started(game.start_time, now)
    for line in lines + [""]:
        for ev in parser.feed(line):
            tracker.apply(ev, now)
    state = asdict(tracker.state)
    print("---- state read ----")
    print(json.dumps(state, indent=1, ensure_ascii=False))
    activity, _ = build_activity(tracker.state, cfg, now, system.idle_seconds())
    print_card("Card that would be shown", activity, now)
    return 0


# ------------------------------------------------------------------------------------------------ doctor
def run_doctor(cfg: dict, problems: list[str]) -> int:
    ok_all = True

    def check(ok: bool, good: str, bad: str, fatal: bool = True) -> None:
        nonlocal ok_all
        print(("  OK    " if ok else ("  FAIL  " if fatal else "  WARN  ")) + (good if ok else bad))
        if not ok and fatal:
            ok_all = False

    print("L4D2 Better Presence - doctor\n")
    check(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]}",
          f"Python {sys.version.split()[0]} is too old: install Python 3.10 or newer.")
    check(not problems, "config.json is valid" if config_mod.CONFIG_PATH.exists() else "No config.json yet (defaults)",
          "config.json: " + " / ".join(problems), fatal=False)
    try:
        d = data.game_data()
        check(len(d["campaigns"]) == 14, f"Name tables: {len(d['campaigns'])} campaigns, {len(d['weapons'])} weapons",
              "Name tables incomplete: run 'python tools/build_data.py'.")
    except (OSError, ValueError) as e:
        check(False, "", f"Name tables missing ({e}): run 'python tools/build_data.py'.")
    running = discord_running()
    check(running, "Discord desktop app is running", "Discord desktop app not found (the browser version cannot "
                                                     "show game activities).", fatal=False)
    if running:
        accepted, user, error = handshake_test(cfg["client_id"])
        check(accepted, f"Discord accepts application {cfg['client_id']}" + (f" (user {user})" if user else ""),
              f"Discord refused application {cfg['client_id']}: {error}")
    gd = steam.game_dir()
    check(gd is not None, f"Left 4 Dead 2 installed: {gd}", "Left 4 Dead 2 not found in the Steam libraries.")
    port, password, opts = netcon_settings(cfg)
    check(bool(opts), f"Launch options read from Steam: {opts.raw if opts else ''}",
          "Could not read the launch options from Steam (userdata/<id>/config/localconfig.vdf).", fatal=False)
    check(bool(port), f"-netconport {port}", "No -netconport: run 'L4D2RPC.bat setup' and paste the line in Steam.")
    check(bool(password), "-netconpassword set (console closed to the network)",
          "No -netconpassword: anyone on your network could type commands in your game. Run setup.")
    check(bool(opts and opts.g15), "-g15 set (health and weapon available)",
          "No -g15: health, weapon and pause cannot be shown.", fatal=False)
    game = system.find_game()
    check(game is not None, f"Game running (PID {game.pid if game else ''})",
          "Game not running: start it to test the console.", fatal=False)
    if game and port:
        lines = netcon_exchange(port, password, "z_difficulty;g15_dumpplayer")
        if lines is None:
            check(False, "", f"Console not reachable on port {port} (was the game started with these options?).")
        else:
            text = "\n".join(lines)
            check("password protected" not in text, "Console answers (password accepted)",
                  "Console refused the password: launch options and config.json disagree.")
            check("(localplayer)" in text or "Must run with -g15" not in text,
                  "g15_dumpplayer answers" + ("" if "(localplayer)" in text else " (in a map it will show health)"),
                  "g15_dumpplayer needs -g15 in the launch options (then restart the game).", fatal=False)
    print("\n" + ("Everything needed is in place." if ok_all else "Fix the FAIL lines above, then run doctor again."))
    print(f"Log file: {config_mod.log_dir() / 'l4d2rpc.log'}")
    return 0 if ok_all else 1


# ------------------------------------------------------------------------------------------------ setup
def run_setup() -> int:
    opts = steam.launch_options()
    current = opts.raw if opts else ""
    password = secrets.token_hex(8)
    line = steam.suggested_launch_options(password, (opts.netcon_port if opts and opts.netcon_port else 27015),
                                          current)
    print("Paste this line in Steam: Library > right-click Left 4 Dead 2 > Properties > General > Launch options")
    print("(replace what is there; it keeps your other options):\n")
    print("    " + line + "\n")
    try:
        subprocess.run(["clip"], input=line.encode("ascii"), check=True)
        print("It is already copied: just press Ctrl+V in the Launch options box.")
    except (OSError, subprocess.CalledProcessError):
        pass
    print("Then restart the game. Nothing else to change: the program reads these options from Steam itself.")
    return 0


# ------------------------------------------------------------------------------------------------ startup
def startup_folder() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def run_startup(action: str) -> int:
    link = startup_folder() / STARTUP_LINK_NAME
    if action == "off":
        if link.exists():
            link.unlink()
            print(f"Removed {link}")
        else:
            print("Start with Windows was not on.")
        return 0
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        print(f"pythonw.exe not found next to {sys.executable}.")
        return 1

    def q(p) -> str:  # single-quoted PowerShell string
        return "'" + str(p).replace("'", "''") + "'"

    command = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({q(link)});"
               f"$s.TargetPath={q(pythonw)};$s.Arguments='-m l4d2_rpc';$s.WorkingDirectory={q(ROOT)};"
               f"$s.Description='L4D2 Better Presence';$s.Save()")
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True)
    if result.returncode != 0 or not link.exists():
        print("Could not create the shortcut:", result.stderr.strip())
        return 1
    print(f"Created {link}\nThe program will start silently with Windows and wait for the game.")
    return 0


# ------------------------------------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="l4d2_rpc", description="Detailed Discord Rich Presence for Left 4 Dead 2")
    ap.add_argument("command", nargs="?", choices=["run", "doctor", "setup", "startup"], default="run")
    ap.add_argument("action", nargs="?", choices=["on", "off"])
    ap.add_argument("--dry-run", action="store_true", help="compute the card without sending it")
    ap.add_argument("--simulate", action="store_true", help="fake game through every situation")
    ap.add_argument("--dump", action="store_true", help="print the raw state read from the game")
    ap.add_argument("-v", "--verbose", action="store_true", help="log every console line and event")
    ap.add_argument("--config", type=Path, help="another config.json")
    args = ap.parse_args(argv)
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if args.command == "setup":
        return run_setup()
    if args.command == "startup":
        return run_startup(args.action or "on")

    console = sys.stdout is not None
    setup_logging(args.verbose, console=console and not (args.simulate and args.dry_run))
    cfg, problems = config_mod.load(args.config, create=not (args.simulate or args.dump or args.command == "doctor"))
    if args.command == "doctor":
        return run_doctor(cfg, problems)
    for p in problems:
        log.warning(p)
    if args.dump:
        return run_dump(cfg)
    if args.simulate:
        return run_simulation(cfg, args.dry_run)

    lock = system.SingleInstance()
    if lock.already_running and not args.dry_run:
        log.info("L4D2 Better Presence is already running; this copy stops.")
        return 3
    try:
        return App(cfg, dry_run=args.dry_run, verbose=args.verbose).run()
    finally:
        lock.release()


if __name__ == "__main__":
    sys.exit(main())
