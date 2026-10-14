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
ROTATION_ITEMS = ("vitals", "specials", "team")
TIMERS = ("campaign", "chapter", "session", "none")
STATUS_DISPLAY = ("name", "state", "details")

DEFAULTS: dict = {
    "client_id": OFFICIAL_CLIENT_ID,
    "language": "en",
    "status_display": "name",
    "timer": "campaign",
    "emoji": True,
    "images": True,
    "buttons": [],
    "state_rotation": ["vitals", "specials", "vitals", "team"],
    "rotate_seconds": 20,
    "idle_minutes": 5,
    "show_health": True,
    "show_weapon": True,
    "show_ammo": True,
    "show_specials": True,
    "show_team": True,
    "show_character": True,
    "show_difficulty": True,
    "show_attempts": True,
    "show_online": True,
    "show_pause": True,
    "show_idle": True,
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
                source = EXAMPLE_PATH.read_text(encoding="utf-8") if EXAMPLE_PATH.exists() else json.dumps(
                    DEFAULTS, indent=2)
                path.write_text(source, encoding="utf-8")
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
