"""Cut anonymised test fixtures out of real netcon recordings (recordings/ is not versioned).

Keeps the timestamp of each line, replaces the player's name, Steam IDs and IP addresses.

Usage:
    python tools/make_fixtures.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REC = ROOT / "recordings"
OUT = ROOT / "tests" / "fixtures"

# (output name, recording, [(from, to), ...] time windows HH:MM:SS)
CUTS = [
    ("solo_newgame_changelevel_menu.log", "session1.log",
     [("17:17:59", "17:18:17"), ("17:19:40", "17:19:46"), ("17:24:30", "17:25:19")]),
    ("solo_vitals.log", "session2.log",
     [("17:30:54", "17:31:01"), ("17:31:19", "17:31:30"), ("17:33:30", "17:33:45"), ("17:36:09", "17:36:13"),
      ("17:37:45", "17:38:08")]),
    ("survival.log", "survival_session.log",
     [("18:50:45", "18:51:12"), ("18:52:25", "18:52:40"), ("18:53:15", "18:53:25"), ("18:54:01", "18:54:55")]),
]

PLAYER = "Sam"


def anonymise(line: str) -> str:
    line = re.sub(r"STEAM_\d:\d:\d+", "STEAM_1:0:12345", line)
    if " version : " not in line:  # "2.2.4.3" is the game version, not an address
        line = re.sub(r"\b(?!127\.0\.0\.1\b)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "192.0.2.1", line)
    line = re.sub(rf"\b{PLAYER}\b", "Player", line)
    return line


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, source, windows in CUTS:
        lines = (REC / source).read_text(encoding="utf-8", errors="replace").splitlines()
        kept = []
        for line in lines:
            stamp = line[:8]
            # Lines starting with ">>> " are what the probe sent (PASS <password>…): never kept
            if any(a <= stamp <= b for a, b in windows) and not line[12:].startswith(" >>> "):
                kept.append(anonymise(line))
        (OUT / name).write_text("\n".join(kept) + "\n", encoding="utf-8")
        print(f"{name}: {len(kept)} lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
