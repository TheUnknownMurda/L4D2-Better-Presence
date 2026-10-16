"""Survival best times from the Gold Miners community "GM Demo Archive" (opt-in: config "gm_demo_archive").

The archive keeps the demos of rounds played on the Gold Miners servers. Its profile page asks
    http://survival.site.nfoservers.com/DemoArchive/personal.php?id=<SteamID64>&view=times
and answers JSON {"html": …}: for each map a heading ("Gun Shop") then rows Category | Players | Final Time
("364:09.27") | SI/min | Date | Download. Checked on 2026-10-15 (see FINDINGS.md).

Only the player's SteamID64 is sent, to that site only. The answer is cached and refreshed every few hours, in a
background thread: a slow or broken site never delays the card.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

log = logging.getLogger("l4d2rpc")

URL = "http://survival.site.nfoservers.com/DemoArchive/personal.php"
REFRESH_SECONDS = 6 * 3600
RETRY_SECONDS = 15 * 60
STEAM_ID64_BASE = 76561197960265728

# The site's map names (its map list, 2026-10-15) -> map codes. Where the game uses one name for two maps the site
# adds the campaign ("Port Passing", "The Bridge (cc)"…).
SITE_MAPS = {
    "gun shop": "c1m2_streets", "mall atrium": "c1m4_atrium",
    "riverbank": "c6m1_riverbank", "bedlam/underground": "c6m2_bedlam", "port passing": "c6m3_port",
    "motel": "c2m1_highway", "stadium gate": "c2m4_barns", "concert": "c2m5_concert",
    "gator village": "c3m1_plankcountry", "shanty town": "c3m3_shantytown", "plantation": "c3m4_plantation",
    "burger tank": "c4m1_milltown_a", "sugar mill": "c4m2_sugarmill_a", "cane field": "c4m3_sugarmill_b",
    "waterfront": "c5m1_waterfront", "bus depot": "c5m2_park", "cemetery": "c5m3_cemetery", "float": "c5m4_quarter",
    "bridge": "c5m5_bridge",
    "traincar": "c7m1_docks", "barge": "c7m2_barge", "port sacrifice": "c7m3_port",
    "generator room": "c8m2_subway", "gas station": "c8m3_sewers", "hospital": "c8m4_interior",
    "rooftop": "c8m5_rooftop",
    "the bridge (cc)": "c9m1_alleys", "truck depot": "c9m2_lots",
    "drains": "c10m2_drainage", "church": "c10m3_ranchhouse", "street": "c10m4_mainstreet",
    "boathouse": "c10m5_houseboat",
    "crane": "c11m2_offices", "construction site": "c11m3_garage", "terminal": "c11m4_terminal",
    "runway": "c11m5_runway",
    "warehouse": "c12m2_traintunnel", "the bridge (bh)": "c12m3_bridge", "farmhouse": "c12m5_cornfield",
    "junkyard (cs)": "c13m3_memorialbridge", "junkyard (cold stream)": "c13m3_memorialbridge",
    "waterworks": "c13m4_cutthroatcreek",
    "junkyard (ls)": "c14m1_junkyard", "junkyard (last stand)": "c14m1_junkyard", "lighthouse": "c14m2_lighthouse",
}

RE_TOKEN = re.compile(r"<h[2-5][^>]*>(.*?)</h[2-5]>|<tr[^>]*>(.*?)</tr>", re.S | re.I)
RE_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
RE_FINAL = re.compile(r"^(\d+):(\d\d)(?:\.(\d\d))?$")


def _text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def parse_times(page_html: str) -> dict[str, float]:
    """{map code: best final time in seconds} from the profile's "times" view (best of all categories)."""
    best: dict[str, float] = {}
    current = None
    for m in RE_TOKEN.finditer(page_html or ""):
        heading, row = m.groups()
        if heading is not None:
            # Headings may carry an icon: <i class="material-icons">ondemand_video</i>
            name = _text(re.sub(r"<i[^>]*material-icons[^>]*>.*?</i>", " ", heading, flags=re.S | re.I)).lower()
            if name in SITE_MAPS:
                current = SITE_MAPS[name]
            continue
        if current is None:
            continue
        cells = [_text(c) for c in RE_CELL.findall(row)]
        # Category | Players | Final Time | SI/min | Date | Download
        if len(cells) >= 5 and RE_FINAL.match(cells[2]) and re.search(r"\b\d{4}\b", cells[4]):
            mm, ss, cc = RE_FINAL.match(cells[2]).groups()
            seconds = int(mm) * 60 + int(ss) + int(cc or 0) / 100
            best[current] = max(seconds, best.get(current, 0))
    return best


def fetch(steam_id64: int, timeout: float = 15) -> dict[str, float]:
    query = urllib.parse.urlencode({"id": steam_id64, "view": "times"})
    req = urllib.request.Request(f"{URL}?{query}", headers={"User-Agent": "L4D2-Better-Presence",
                                                           "X-Requested-With": "XMLHttpRequest"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8-sig", "replace")
    try:
        page = json.loads(raw).get("html", "")
    except ValueError:
        page = raw
    return parse_times(page)


class GmArchive:
    """Cached best times, refreshed in the background. `bests` is always safe to read."""

    def __init__(self, cache_path: Path, steam_id64: int | None):
        self.cache_path = cache_path
        self.steam_id64 = steam_id64
        self.bests: dict[str, float] = {}
        self._fetched = 0.0
        self._next_try = 0.0
        self._busy = False
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("steam_id64") == steam_id64:
                self.bests = {k: float(v) for k, v in (cached.get("bests") or {}).items()}
                self._fetched = float(cached.get("fetched") or 0)
        except (OSError, ValueError, AttributeError):
            pass

    def refresh_if_due(self, now: float | None = None) -> None:
        now = now or time.time()
        if not self.steam_id64 or self._busy or now < max(self._fetched + REFRESH_SECONDS, self._next_try):
            return
        self._busy = True
        threading.Thread(target=self._refresh, name="gm-archive", daemon=True).start()

    def _refresh(self) -> None:
        try:
            bests = fetch(self.steam_id64)
            self.bests = bests
            self._fetched = time.time()
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps({"steam_id64": self.steam_id64, "fetched": self._fetched,
                                                   "bests": bests}, indent=1), encoding="utf-8")
            log.info("GM Demo Archive: %d map(s) with a recorded run.", len(bests))
        except Exception as e:  # network, site down, layout change: keep the cache
            self._next_try = time.time() + RETRY_SECONDS
            log.info("GM Demo Archive not reachable (%s); retrying later.", e)
        finally:
            self._busy = False


def steam_id64_from_account(account_id: int | None) -> int | None:
    return STEAM_ID64_BASE + account_id if account_id else None
