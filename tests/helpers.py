"""Replays anonymised real recordings (tests/fixtures, cut by tools/make_fixtures.py) through the parser."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from l4d2_rpc.parser import ConsoleParser  # noqa: E402
from l4d2_rpc.state import Tracker  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BASE = 1_791_993_600.0  # 2026-10-14 00:00 UTC, so recorded times map to realistic epochs


def stamp(hms: str) -> float:
    h, m, s = hms.split(":")
    return BASE + int(h) * 3600 + int(m) * 60 + float(s)


def lines(name: str):
    for raw in (FIXTURES / name).read_text(encoding="utf-8").splitlines():
        if len(raw) >= 13 and raw[2] == ":" and raw[12] == " ":
            yield stamp(raw[:12]), raw[13:]


class Replay:
    """Feeds a fixture up to a given time and exposes the tracker."""

    def __init__(self, name: str, started: str = "17:00:00"):
        self.parser = ConsoleParser()
        self.tracker = Tracker()
        self.tracker.game_started(stamp(started), stamp(started))
        self._lines = list(lines(name))
        self._pos = 0
        self.events = []

    def until(self, hms: str):
        limit = stamp(hms)
        while self._pos < len(self._lines) and self._lines[self._pos][0] <= limit:
            t, line = self._lines[self._pos]
            for ev in self.parser.feed(line):
                self.events.append((t, ev))
                self.tracker.apply(ev, t)
            self._pos += 1
        self.tracker.tick(limit)
        return self.tracker.state
