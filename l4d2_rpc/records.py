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

    def add(self, map_name: str, seconds: float, when: float) -> bool:
        """Records one finished round. True when it is a new best for that map."""
        key = map_name.lower()
        entry = self.data.setdefault(key, {"best": 0, "date": None, "rounds": 0})
        entry["rounds"] = int(entry.get("rounds") or 0) + 1
        new_best = seconds > float(entry.get("best") or 0)
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


def clock(seconds: float | None) -> str:
    """3:21, or 1:02:05 past an hour."""
    total = int(seconds or 0)
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
