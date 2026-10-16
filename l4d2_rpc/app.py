"""The main loop: wait for the game, read its console, rebuild the state, keep the Discord card up to date."""

from __future__ import annotations

import ctypes
import json
import os
import logging
import queue
import time

from . import gm_archive, steam, system
from .config import log_dir
from .discord_ipc import DiscordClient
from .netcon import NetconClient
from .parser import ConsoleParser
from .presence import build_activity
from .records import SurvivalRecords, clock, parse_manual
from .state import Tracker

log = logging.getLogger("l4d2rpc")

FAST_UPDATE_SECONDS = 5  # an important change (place, strong state) reaches Discord within this
SLOW_UPDATE_SECONDS = 15  # health, ammo, rotation: at most this often
GAME_CHECK_SECONDS = 2
NETCON_RETRY_SECONDS = (2, 3, 5, 10)
STATUS_EVERY = 2  # status is asked every STATUS_EVERY dumps
DIFFICULTY_SECONDS = 30
STARTUP_QUERY = "name;cl_language;z_difficulty;status"
GENERIC_CARD = {"type": 0, "details": "Left 4 Dead 2", "state": "Surviving"}


class DryRunClient:
    """Same interface as DiscordClient; prints the card instead of sending it."""

    status = "dry-run"
    error = ""
    user = ""

    def __init__(self, *args, **kwargs):
        self.last = "unset"
        self.sent_count = 0

    def show(self, activity, pid=None):
        if activity != self.last:
            self.last = activity
            self.sent_count += 1
            if activity is None:
                log.info("Card cleared (dry run).")
            else:
                log.info("Card (dry run): %s", json.dumps(activity, ensure_ascii=False))

    def stop(self, timeout=0):
        pass


class Sender:
    """Decides when a new card goes to Discord: important changes quickly, the rest at a slower pace, and only
    when the card actually changed. The last wanted card always wins."""

    def __init__(self, client):
        self.client = client
        self.sent = None
        self.sent_key = None
        self.sent_at = -1e9

    def offer(self, activity, key, now: float, pid: int | None = None) -> bool:
        if activity is None:
            if self.sent is not None:
                self.client.show(None)
                self.sent, self.sent_key, self.sent_at = None, None, now
                return True
            return False
        if activity == self.sent:
            return False
        wait = FAST_UPDATE_SECONDS if key != self.sent_key else SLOW_UPDATE_SECONDS
        if now - self.sent_at < wait:
            return False
        self.client.show(activity, pid=pid)
        self.sent, self.sent_key, self.sent_at = activity, key, now
        return True


class ConsoleCloseGuard:
    """Ctrl+C, Ctrl+Break and closing the console window all ask the loop to stop, so the card is removed."""

    def __init__(self):
        self.stop = False
        self._handler = None
        try:
            HANDLER = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_uint)

            def handler(event):
                self.stop = True
                if event == 2:  # CTRL_CLOSE_EVENT: Windows waits for us only a few seconds
                    time.sleep(1.5)
                return 1

            self._handler = HANDLER(handler)
            ctypes.windll.kernel32.SetConsoleCtrlHandler(self._handler, True)
        except Exception:  # pythonw: no console, nothing to guard
            self._handler = None


class App:
    def __init__(self, cfg: dict, dry_run: bool = False, verbose: bool = False, client=None):
        self.cfg = cfg
        self.dry_run = dry_run
        self.verbose = verbose
        self.client = client or (DryRunClient() if dry_run else DiscordClient(cfg["client_id"]))
        self.sender = Sender(self.client)
        self.parser = ConsoleParser()
        self.tracker = Tracker()
        self.game: system.GameProcess | None = None
        self.netcon: NetconClient | None = None
        self._netcon_failures = 0
        self._next_netcon_try = 0.0
        self._next_game_check = 0.0
        self._next_poll = 0.0
        self._polls = 0
        self._next_difficulty = 0.0
        self._warned: set[str] = set()
        self.records = SurvivalRecords(log_dir() / "survival_records.json")
        self.manual_records = parse_manual(cfg.get("survival_records") or {})[0]  # typed from the game's menu
        self.gm = None
        if cfg.get("gm_demo_archive"):
            sid = int(cfg["steam_id64"]) if cfg.get("steam_id64") else                 gm_archive.steam_id64_from_account(steam.active_account_id())
            self.gm = gm_archive.GmArchive(log_dir() / "gm_records.json", sid)

    # ------------------------------------------------------------------ helpers
    def _warn_once(self, key: str, message: str, *args) -> None:
        if key not in self._warned:
            self._warned.add(key)
            log.warning(message, *args)

    def _netcon_settings(self) -> tuple[int | None, str]:
        port = self.cfg["netcon_port"] or None
        password = self.cfg["netcon_password"] or ""
        if not port or not password:
            opts = steam.launch_options()
            if opts:
                port = port or opts.netcon_port
                password = password or (opts.netcon_password or "")
                if not opts.g15:
                    self._warn_once("g15", "The launch options have no -g15: health and weapon will not be shown. "
                                           "Run 'L4D2RPC.bat setup' for the line to paste in Steam.")
        return port, password

    # ------------------------------------------------------------------ game process
    def _check_game(self, now: float) -> None:
        if now < self._next_game_check:
            return
        self._next_game_check = now + GAME_CHECK_SECONDS
        game = system.find_game()
        if game and (self.game is None or game.pid != self.game.pid):
            if self.game is not None:
                self._game_closed()
            self.game = game
            self.tracker.game_started(game.start_time, time.time())
            self._netcon_failures = 0
            self._next_netcon_try = now
            self._warned.discard("netcon_down")
            log.info("Game detected (PID %d).", game.pid)
        elif not game and self.game is not None:
            self._game_closed()

    def _game_closed(self) -> None:
        log.info("Game closed: clearing the card.")
        self.game = None
        if self.netcon:
            self.netcon.close()
            self.netcon = None
        self.parser.reset()
        self.tracker.game_closed()

    # ------------------------------------------------------------------ console
    def _ensure_netcon(self, now: float) -> None:
        if self.game is None or (self.netcon and self.netcon.connected) or now < self._next_netcon_try:
            return
        if self.netcon is not None:
            log.info("Lost the game console (%s).", self.netcon.closed_reason or "closed")
            self.netcon.close()
            self.netcon = None
            self.parser.reset()
        port, password = self._netcon_settings()
        if not port:
            self._warn_once("no_port", "The game was not started with -netconport: only 'Playing' can be shown. "
                                       "Run 'L4D2RPC.bat setup' for the launch options to paste in Steam.")
            self._next_netcon_try = now + 30
            return
        if not password:
            self._warn_once("no_password", "No -netconpassword in the launch options: the console is open to "
                                           "your whole network. Run 'L4D2RPC.bat setup' to add one.")
        client = NetconClient(self.cfg["netcon_host"], port, password)
        try:
            client.connect()
        except OSError as e:
            delay = NETCON_RETRY_SECONDS[min(self._netcon_failures, len(NETCON_RETRY_SECONDS) - 1)]
            self._netcon_failures += 1
            if self._netcon_failures == 3:
                log.info("Game console not reachable yet on port %d (%s); still trying.", port, e)
            self._next_netcon_try = now + delay
            return
        self.netcon = client
        self._netcon_failures = 0
        self._warned.discard("password")
        log.info("Connected to the game console (port %d).", port)
        client.send(STARTUP_QUERY)
        self._next_poll = now + 1

    def _drain(self) -> None:
        if not self.netcon:
            return
        while True:
            try:
                stamp, line = self.netcon.lines.get_nowait()
            except queue.Empty:
                break
            if self.verbose:
                log.debug("console: %s", line)
            for ev in self.parser.feed(line):
                if ev.kind == "password_required":
                    self._warn_once("password", "The game refused the console password: check -netconpassword "
                                                "in the launch options (and 'netcon_password' in config.json).")
                    continue
                if self.verbose and ev.kind not in ("dump", "status"):
                    log.debug("event: %r", ev)
                before = (self.tracker.state.phase, self.tracker.state.map)
                self.tracker.apply(ev, stamp)
                self._log_change(before, ev)

    def _log_change(self, before, ev) -> None:
        s = self.tracker.state
        if (s.phase, s.map) != before:
            if s.phase in ("loading", "ingame"):
                self._next_difficulty = 0.0  # read the difficulty again at the first poll in the new map
            if s.phase == "loading":
                log.info("Loading %s.", s.map or "a map")
            elif s.phase == "ingame":
                log.info("In game on %s.", s.map)
            elif s.phase == "menu":
                log.info("Back to the main menu.")

    def _poll(self, now: float) -> None:
        s = self.tracker.state
        if not self.netcon or not self.netcon.connected or s.phase != "ingame" or now < self._next_poll:
            return
        self._next_poll = now + self.cfg["poll_seconds"]
        commands = ["g15_dumpplayer"]
        if self._polls % STATUS_EVERY == 0:
            commands.append("status")
        if now >= self._next_difficulty:
            commands.append("z_difficulty")
            self._next_difficulty = now + DIFFICULTY_SECONDS
        self._polls += 1
        self.netcon.send(";".join(commands))

    def _save_rounds(self) -> None:
        s = self.tracker.state
        if self.gm is not None and s.survival:
            self.gm.refresh_if_due()
        while self.tracker.finished_rounds:
            map_name, seconds, end = self.tracker.finished_rounds.pop(0)
            new_best = self.records.add(map_name, seconds, end, floor=self._other_best(map_name))
            if map_name == s.map:
                s.last_round_record = new_best
            log.info("Survival round on %s: %s%s.", map_name, clock(seconds), " (new best)" if new_best else "")
        if s.survival:
            bests = [b for b in (self.records.best(s.map), self._other_best(s.map)) if b]
            s.survival_best = max(bests) if bests else None
        else:
            s.survival_best = None

    def _other_best(self, map_name: str | None) -> float | None:
        """Best known from outside our own measurements: typed in config.json, or the GM Demo Archive."""
        bests = [self.manual_records.get(map_name or "")]
        if self.gm is not None:
            bests.append(self.gm.bests.get(map_name or ""))
        bests = [b for b in bests if b]
        return max(bests) if bests else None

    # ------------------------------------------------------------------ loop
    def step(self) -> None:
        mono = time.monotonic()
        self._check_game(mono)
        self._ensure_netcon(mono)
        self._drain()
        self._poll(mono)
        now = time.time()
        self.tracker.tick(now)
        self._save_rounds()
        idle = system.idle_seconds()
        try:
            activity, key = build_activity(self.tracker.state, self.cfg, now, idle)
        except Exception:
            self._warn_once("build", "Could not build the card for this state; showing a generic one.")
            log.debug("state: %r", self.tracker.state, exc_info=True)
            activity, key = (GENERIC_CARD if self.game else None), ("generic",)
        # Which process Discord ties the card to. "game": Discord removes it by itself when the game exits, but
        # answered nothing for ~15 s while a map loaded from the menu (FINDINGS.md). "companion": avoids that.
        pid = self.game.pid if (self.game and self.cfg["card_owner"] == "game") else os.getpid()
        self.sender.offer(activity, key, mono, pid=pid)

    def run(self) -> int:
        guard = ConsoleCloseGuard()
        pid_file = log_dir() / "companion.pid"  # lets Uninstall.bat stop this program
        if not self.dry_run:
            try:
                pid_file.write_text(str(os.getpid()))
            except OSError:
                pid_file = None
        log.info("L4D2 Better Presence started%s. Log: %s", " (dry run)" if self.dry_run else "", log_dir())
        log.info("Waiting for Left 4 Dead 2…")
        try:
            while not guard.stop:
                try:
                    self.step()
                except Exception:
                    log.exception("Unexpected error; continuing with a generic card.")
                    time.sleep(1)
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        log.info("Stopping: clearing the card.")
        if self.netcon:
            self.netcon.close()
        self.sender.offer(None, None, time.monotonic())
        self.client.stop()
        if not self.dry_run and pid_file is not None:
            try:
                pid_file.unlink()
            except OSError:
                pass
        return 0
