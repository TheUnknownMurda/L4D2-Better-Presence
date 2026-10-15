"""Survival best times kept by the companion itself (the game's own records cannot be read from outside:
no per-map survival stat in Steam's stats, no public leaderboard; see FINDINGS.md).

File: %LOCALAPPDATA%\\L4D2RPC\\survival_records.json
    {"c1m2_streets": {"best": 201.4, "date": "2026-10-14T19:05:00", "rounds": 3}, ...}

Times are measured from the round's detected start (first special or damage, a few seconds after the real start)
to its end, so they can be slightly shorter than the game's.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
from pathlib import Path

log = logging.getLogger("l4d2rpc")


class SurvivalRecords:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, dict] = {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.data = {k: v for k, v in raw.items() if isinstance(v, dict)}
        except (OSError, ValueError):
            pass

    def best(self, map_name: str | None) -> float | None:
        entry = self.data.get((map_name or "").lower())
        value = entry.get("best") if entry else None
        return float(value) if isinstance(value, (int, float)) and value > 0 else None

    def add(self, map_name: str, seconds: float, when: float, floor: float | None = None) -> bool:
        """Records one finished round. True when it beats the best for that map (and `floor`, a record typed in
        config.json from the game's own Survival menu)."""
        key = map_name.lower()
        entry = self.data.setdefault(key, {"best": 0, "date": None, "rounds": 0})
        entry["rounds"] = int(entry.get("rounds") or 0) + 1
        new_best = seconds > max(float(entry.get("best") or 0), floor or 0)
        if new_best:
            entry["best"] = round(seconds, 1)
            entry["date"] = dt.datetime.fromtimestamp(when).isoformat(timespec="seconds")
        self._save()
        return new_best

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as e:
            log.warning("Could not save the survival records (%s).", e)


def parse_time(value) -> float | None:
    """"4:32", "1:02:05", "272" or 272 -> seconds; None when not a time."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if value > 0 else None
    if not isinstance(value, str):
        return None
    m = re.fullmatch(r"\s*(?:(\d+):)?(\d+):(\d{1,2}(?:\.\d+)?)\s*|\s*(\d+(?:\.\d+)?)\s*", value)
    if not m:
        return None
    if m.group(4):
        return float(m.group(4)) or None
    h, mnt, sec = int(m.group(1) or 0), int(m.group(2)), float(m.group(3))
    return h * 3600 + mnt * 60 + sec if sec < 60 else None


def resolve_map(name: str) -> str | None:
    """A Survival map from its code (c1m2_streets) or its name in the game's Survival menu ("Gun Shop", in English or
    French). Names used by several campaigns (e.g. "Port") need the code."""
    from . import data

    def norm(text: str) -> str:  # the game writes "L’armerie" with a typographic apostrophe
        return text.strip().lower().replace(chr(0x2019), "'")

    key = norm(name)
    maps = data.game_data()["maps"]
    if key in maps:
        return key
    found = [m for m, e in maps.items()
             if any(norm(n) == key for n in ((e.get("mode_names") or {}).get("survival") or {}).values())]
    return found[0] if len(found) == 1 else None


def parse_manual(value) -> tuple[dict[str, float], list[str]]:
    """config.json "survival_records" -> ({map code: seconds}, [keys that could not be read])."""
    if not isinstance(value, dict):
        return {}, ["(not an object)"]
    out, bad = {}, []
    for name, time in value.items():
        map_code, seconds = resolve_map(str(name)), parse_time(time)
        if map_code and seconds:
            out[map_code] = max(seconds, out.get(map_code, 0))
        else:
            bad.append(name)
    return out, bad


def clock(seconds: float | None) -> str:
    """3:21, or 1:02:05 past an hour."""
    total = int(seconds or 0)
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
