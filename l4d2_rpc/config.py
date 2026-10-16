"""config.json: created from the defaults on first run, every key optional. Unknown or wrong values are
reported in plain words and replaced by the default; the program never stops because of a setting."""

from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path

log = logging.getLogger("l4d2rpc")

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
EXAMPLE_PATH = ROOT / "config.example.json"

OFFICIAL_CLIENT_ID = "356954277803065354"  # Discord's own "Left 4 Dead 2" application (detectable list)
ROTATION_ITEMS = ("vitals", "specials", "team", "record")
TIMERS = ("campaign", "chapter", "session", "none")
STATUS_DISPLAY = ("name", "state", "details")

IMAGE_HOST = "https://images.guns.lol/2d34137430fbdf92ffab3a07ade119c29de30536/"

STARTER = {"_comment": "Your settings. Copy here only the keys you want to change from config.example.json "
                        "(all keys and their role: README > Configuration)."}

DEFAULTS: dict = {
    "client_id": OFFICIAL_CLIENT_ID,
    "language": "en",
    "status_display": "name",
    "timer": "campaign",
    "emoji": True,
    "images": True,
    # Sam's hosted portraits (from the "Survivor Better Materials" workshop preview, tools/extract_portraits.py)
    "character_images": {
        "Coach": IMAGE_HOST + "sGWZ799inw1xcwXX9tQGz.png",
        "Ellis": IMAGE_HOST + "YahTLLkcf79rUWXJfqR6o.png",
        "Nick": IMAGE_HOST + "9twGryOKpthNEtbM8Tp2W.png",
        "Rochelle": IMAGE_HOST + "dpoAi8kddFfdVf6ASbROO.png",
        "Bill": IMAGE_HOST + "W7wDKSDtdtGSQqOG7kJnQ.png",
        "Zoey": IMAGE_HOST + "FwQry26L33A1n8NmGTzOR.png",
        "Francis": IMAGE_HOST + "2rdohtxtfvoaUjaL0LBVq.png",
        "Louis": IMAGE_HOST + "Cd5kqErF8OaH7YeIWkibr.png",
    },
    "cover_image": IMAGE_HOST + "R7kq6VUsjDtVC7alNkrjk.png",
    "buttons": [],
    "state_rotation": ["vitals", "team", "record"],  # "specials" available, off by Sam's choice
    "rotate_seconds": 20,
    "idle_minutes": 5,
    "show_health": True,
    "show_weapon": True,
    "show_ammo": False,  # Sam: weapon name only
    "show_specials": True,
    "show_team": True,
    "show_character": True,
    "show_difficulty": True,
    "show_attempts": True,
    "show_records": True,
    "survival_records": {},  # your in-game records, typed once: {"Gun Shop": "4:32"}
    "gm_demo_archive": False,  # also read your times from the Gold Miners "GM Demo Archive" site
    "steam_id64": "",  # for the archive; empty = the Steam account logged in on this PC
    "show_online": True,
    "show_pause": True,
    "show_idle": True,
    "card_owner": "companion",
    "netcon_host": "127.0.0.1",
    "netcon_port": 0,
    "netcon_password": "",
    "poll_seconds": 2,
}


def _problem(key: str, value, expected: str) -> str:
    return f'config.json: "{key}" = {json.dumps(value)} is not valid ({expected}); using the default.'


def validate(raw: dict) -> tuple[dict, list[str]]:
    cfg = copy.deepcopy(DEFAULTS)
    problems: list[str] = []
    if not isinstance(raw, dict):
        return cfg, ["config.json does not contain a JSON object; using the defaults."]
    for key, value in raw.items():
        if key.startswith("_"):
            continue
        if key not in DEFAULTS:
            problems.append(f'config.json: unknown key "{key}" (ignored).')
            continue
        default = DEFAULTS[key]
        if key == "language":
            if value not in ("en", "fr", "auto"):
                problems.append(_problem(key, value, '"en", "fr" or "auto"'))
                continue
        elif key == "timer":
            if value not in TIMERS:
                problems.append(_problem(key, value, " / ".join(TIMERS)))
                continue
        elif key == "character_images":
            if not isinstance(value, dict) or not all(
                    isinstance(v, str) and v.startswith("https://") and len(v) <= 256 for v in value.values()):
                problems.append(_problem(key, value, '{"Coach": "https://…", …} with links of 256 characters at most'))
                continue
        elif key == "survival_records":
            from .records import parse_manual  # here to avoid an import cycle
            _parsed, bad = parse_manual(value)
            if bad:
                problems.append(_problem(key, {k: value[k] for k in bad} if isinstance(value, dict) else value,
                                         "map names as in the game's Survival menu (or c1m2_streets) and times "
                                         'like "4:32"'))
            value = {k: v for k, v in value.items() if k not in bad} if isinstance(value, dict) else {}
        elif key == "steam_id64":
            if not (isinstance(value, str) and (value == "" or (value.isdigit() and len(value) == 17))):
                problems.append(_problem(key, value, 'a 17-digit SteamID64 in quotes, or ""'))
                continue
        elif key == "cover_image":
            if not (isinstance(value, str) and (value == "" or (value.startswith("https://") and len(value) <= 256))):
                problems.append(_problem(key, value, 'an "https://…" image link of 256 characters at most, or ""'))
                continue
        elif key == "card_owner":
            if value not in ("companion", "game"):
                problems.append(_problem(key, value, '"companion" or "game"'))
                continue
        elif key == "status_display":
            if value not in STATUS_DISPLAY:
                problems.append(_problem(key, value, " / ".join(STATUS_DISPLAY)))
                continue
        elif key == "state_rotation":
            if (not isinstance(value, list) or not value
                    or any(item not in ROTATION_ITEMS for item in value)):
                problems.append(_problem(key, value, "a list of " + ", ".join(ROTATION_ITEMS)))
                continue
        elif key == "buttons":
            if not isinstance(value, list) or len(value) > 2 or not all(
                    isinstance(b, dict) and isinstance(b.get("label"), str) and isinstance(b.get("url"), str)
                    and b["url"].startswith("https://") and 0 < len(b["label"]) <= 32 and len(b["url"]) <= 512
                    for b in value):
                problems.append(_problem(key, value, 'up to 2 {"label": ≤32 chars, "url": "https://…"}'))
                continue
        elif key == "client_id":
            if not (isinstance(value, str) and value.isdigit()):
                problems.append(_problem(key, value, "a Discord application ID, digits only, in quotes"))
                continue
        elif isinstance(default, bool):
            if not isinstance(value, bool):
                problems.append(_problem(key, value, "true or false"))
                continue
        elif isinstance(default, int):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                problems.append(_problem(key, value, "a positive number"))
                continue
            value = int(value) if isinstance(default, int) and float(value).is_integer() else value
        elif isinstance(default, str) and not isinstance(value, str):
            problems.append(_problem(key, value, "text in quotes"))
            continue
        cfg[key] = value
    cfg["rotate_seconds"] = max(5, cfg["rotate_seconds"])
    cfg["poll_seconds"] = min(10, max(1, cfg["poll_seconds"]))
    return cfg, problems


def load(path: Path | None = None, create: bool = True) -> tuple[dict, list[str]]:
    path = path or CONFIG_PATH
    if not path.exists():
        if create:
            try:
                # Only the keys you change go here: a full copy would freeze today's defaults
                path.write_text(json.dumps(STARTER, indent=2), encoding="utf-8")
                log.info("Created %s with the default settings.", path.name)
            except OSError as e:
                return copy.deepcopy(DEFAULTS), [f"Could not create {path}: {e}"]
        return validate({})
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as e:
        return copy.deepcopy(DEFAULTS), [f"{path.name} is not valid JSON ({e}); using the defaults."]
    except OSError as e:
        return copy.deepcopy(DEFAULTS), [f"Could not read {path}: {e}; using the defaults."]
    return validate(raw)


def log_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "L4D2RPC"
