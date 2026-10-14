"""Game state -> Discord activity. Pure: everything it needs (state, settings, time, idle time) is passed in.

Layout (see README "What the card shows"):
    details  = where: campaign · chapter n/N (or the main menu)
    state    = what moves: a strong state (dead, down, Tank, paused…) or a rotating line (health & weapon,
               specials alive, team)
    large image = campaign poster (tooltip: difficulty, attempt, online)
    small image = the player's survivor (tooltip: the name), or the special infected played in Versus
"""

from __future__ import annotations

import re

from . import data
from .i18n import EMOJI, resolve_language, text
from .records import clock
from .state import TEAM_INFECTED, TEAM_SPECTATOR, GameState

ACTIVITY_PLAYING = 0
PAD = chr(0x2800)  # blank Braille pattern: visible as nothing, not trimmed by Discord
MAX_TEXT = 128
MAX_URL = 256
REVIVED_SECONDS = 20
SETTLE_SECONDS = 45  # from the start of the load
STATUS_DISPLAY_TYPES = {"name": 0, "state": 1, "details": 2}


def _length(s: str) -> int:
    """Length the way Discord counts it (UTF-16 units: an emoji counts as 2)."""
    return len(s.encode("utf-16-le", "surrogatepass")) // 2


def truncate(value: str | None, maximum: int = MAX_TEXT, minimum: int = 2) -> str | None:
    """The one place every card text goes through. Line breaks become " | ", spaces are collapsed, a text
    longer than `maximum` is cut on a character boundary and ends with "…", one shorter than `minimum` is padded.
    Returns None for an empty text."""
    if value is None:
        return None
    s = str(value).encode("utf-16-le", "surrogatepass").decode("utf-16-le", "ignore")  # drop lone surrogates
    s = re.sub(r"\s*[\r\n]+\s*", " | ", s)
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)
    s = re.sub(r"[ \t]+", " ", s).strip()
    if not s:
        return None
    if _length(s) > maximum:
        kept, length = [], 0
        for ch in s:
            length += _length(ch)
            if length > maximum - 1:
                break
            kept.append(ch)
        s = "".join(kept).rstrip() + "…"
    while _length(s) < minimum:
        s += PAD
    return s


def _url(value: str | None) -> str | None:
    if value and value.startswith("https://") and len(value) <= MAX_URL:
        return value
    return None


def _cover(cfg: dict) -> str | None:
    """The game's cover: the one set in config.json, else Steam's library art."""
    return _url(cfg.get("cover_image")) or data.cover_image()


def _e(cfg: dict, key: str) -> str:
    return (EMOJI[key] + " ") if cfg.get("emoji", True) else ""


def _join(parts: list[str]) -> str:
    return " · ".join(p for p in parts if p)


# ------------------------------------------------------------------------------------------------ lines
def _where(s: GameState, lang: str) -> str:
    info = s.map_info
    if info is None:
        return text(lang, "unknown_map")
    if s.survival:
        place = data.mode_map_name(info.map, "survival", lang) or data.chapter_name(info.map, lang) or info.map
        return f"{data.mode_name('survival', lang)} · {place}"
    if info.campaign is None:
        return text(lang, "custom_map", map=info.map)
    campaign = data.campaign_name(info.campaign, lang)
    chapter = data.chapter_name(info.map, lang) or info.map
    if info.chapter is None:
        return f"{campaign} · {chapter}"
    if info.finale:
        return text(lang, "finale", campaign=campaign, chapter=chapter)
    return text(lang, "chapter", campaign=campaign, n=info.chapter, total=info.chapters, chapter=chapter)


def _vitals(s: GameState, cfg: dict, lang: str) -> str | None:
    parts = []
    if cfg["show_health"] and s.health is not None and s.team != TEAM_SPECTATOR:
        heart = "last_life" if s.last_life else "health"
        hp = _e(cfg, heart) + text(lang, "health", health=s.health)
        if s.last_life:
            hp += f" ({text(lang, 'last_life')})"
        parts.append(hp)
    w = data.weapon(s.weapon_class)
    if cfg["show_weapon"] and w and w["kind"] != "claw":
        kind = w["kind"]
        icon = {"primary": "weapon", "secondary": "weapon"}.get(kind, kind)
        label = _e(cfg, icon) + data.weapon_name(s.weapon_class, lang)
        if cfg["show_ammo"] and (kind in ("primary", "secondary") or s.weapon_class == "CChainsaw"):
            if s.reloading:
                label += f" ({text(lang, 'reloading')})"
            elif s.clip is not None and s.clip >= 0:
                infinite_reserve = kind == "secondary" or s.weapon_class == "CChainsaw"
                if s.reserve is not None and not infinite_reserve:
                    label += f" {s.clip}/{s.reserve}"
                else:
                    label += f" {s.clip}"
        parts.append(label)
    return _join(parts) or None


def _specials(s: GameState, cfg: dict, lang: str) -> str | None:
    if not cfg["show_specials"]:
        return None
    names = [n for n in s.specials_alive if n != "Tank"]
    if not names:
        return None
    return _e(cfg, "specials") + text(lang, "specials", names=", ".join(names))


def _team(s: GameState, cfg: dict, lang: str) -> str | None:
    if not cfg["show_team"] or s.humans is None:
        return None
    bots = len(s.survivor_bots)
    if s.humans <= 1:
        return None  # solo: nothing worth a line (Sam's choice, 2026-10-14)
    if bots:
        return _e(cfg, "team") + text(lang, "players_bots", players=s.humans, bots=bots)
    return _e(cfg, "team") + text(lang, "players", players=s.humans)


def _strong(s: GameState, cfg: dict, lang: str, now: float, idle: float) -> tuple[str, str] | None:
    """(kind, text) for a state that stays on screen while it lasts, in priority order."""
    fresh = s.vitals_fresh(now)
    if s.dead and s.team != TEAM_INFECTED:
        if s.survival and s.round_end is not None and s.last_round is not None:
            line = _e(cfg, "dead") + text(lang, "round_over", time=clock(s.last_round))
            if cfg["show_records"] and s.last_round_record:
                line += " · " + _e(cfg, "record") + text(lang, "new_best")
            return "round_over", line
        if s.survival:
            return "dead", _e(cfg, "dead") + text(lang, "dead_survival")
        return "dead", _e(cfg, "dead") + text(lang, "dead_solo" if s.solo else "dead")
    if fresh and s.incapacitated:
        return "incap", _e(cfg, "incap") + text(lang, "incap")
    if cfg["show_pause"] and fresh and s.paused:
        return "paused", _e(cfg, "paused") + text(lang, "paused")
    if fresh and s.revived_since is not None and now - s.revived_since <= REVIVED_SECONDS and s.health:
        if cfg["show_health"]:
            return "revived", _e(cfg, "revived") + text(lang, "revived", health=s.health)
        return "revived", _e(cfg, "revived") + text(lang, "revived_short")
    if s.safe_room_since is not None:
        return "safe_room", _e(cfg, "safe_room") + text(lang, "safe_room")
    if cfg["show_specials"] and s.tank:
        vitals = _vitals(s, cfg, lang) if fresh else None
        return "tank", _join([_e(cfg, "tank") + text(lang, "tank"), vitals])
    if cfg["show_attempts"] and s.retry_since is not None and now - s.retry_since <= 20 and s.attempt > 1:
        return "retry", _e(cfg, "retry") + text(lang, "round" if s.survival else "retry", n=s.attempt)
    if s.round_waiting:
        line = _e(cfg, "survival_wait") + text(lang, "survival_wait")
        if cfg["show_records"] and s.survival_best:
            line += " · " + text(lang, "best_short", time=clock(s.survival_best))
        return "survival_wait", line
    if fresh and s.team == TEAM_SPECTATOR:
        return "spectating", _e(cfg, "spectating") + text(lang, "spectating")
    if fresh and s.team == TEAM_INFECTED:
        w = data.weapon(s.weapon_class)
        if w and w["kind"] == "claw":
            hp = f" · {text(lang, 'health', health=s.health)}" if cfg["show_health"] and s.health else ""
            return "infected", _e(cfg, "infected") + text(lang, "infected", name=w["names"]["en"]) + hp
    if cfg["show_idle"] and idle >= cfg["idle_minutes"] * 60 > 0:
        return "idle", _e(cfg, "idle") + text(lang, "idle")
    return None


def _record(s: GameState, cfg: dict, lang: str, now: float) -> str | None:
    """Survival only: the best time on this map, or that the running round beats it."""
    if not (cfg["show_records"] and s.survival and s.survival_best and s.round_start and s.round_end is None):
        return None
    if now - s.round_start > s.survival_best:
        return _e(cfg, "record") + text(lang, "beating_best", time=clock(s.survival_best))
    return _e(cfg, "record") + text(lang, "best_here", time=clock(s.survival_best))


def _rotating(s: GameState, cfg: dict, lang: str, now: float) -> str:
    builders = {"vitals": lambda: _vitals(s, cfg, lang) if s.vitals_fresh(now) else None,
                "specials": lambda: _specials(s, cfg, lang),
                "team": lambda: _team(s, cfg, lang),
                "record": lambda: _record(s, cfg, lang, now)}
    rotation = cfg["state_rotation"]
    slot = int(now // cfg["rotate_seconds"]) % len(rotation)
    # Start at the current slot and take the first item that has something to say
    for i in range(len(rotation)):
        line = builders[rotation[(slot + i) % len(rotation)]]()
        if line:
            return line
    return text(lang, "in_game")


# ------------------------------------------------------------------------------------------------ card
def build_activity(s: GameState, cfg: dict, now: float, idle: float = 0.0) -> tuple[dict | None, tuple]:
    """Returns (activity or None to clear, importance key). A change of key is sent quickly (≤5 s);
    other changes (health, ammo, rotation) wait for the slower cadence."""
    if s.phase == "closed":
        return None, ("closed",)
    lang = resolve_language(cfg["language"], s.game_language)
    images = cfg["images"]
    activity: dict = {"type": ACTIVITY_PLAYING}
    assets: dict = {}
    timestamps: dict = {}

    if s.phase == "menu":
        details = text(lang, "menu")
        last = data.campaign_name(s.last_campaign, lang)
        state = text(lang, "menu_last", campaign=last) if last else text(lang, "menu_idle")
        if cfg["show_idle"] and idle >= cfg["idle_minutes"] * 60 > 0:
            state = _e(cfg, "idle") + text(lang, "idle")
        if images and _url(_cover(cfg)):
            assets["large_image"] = _cover(cfg)
            assets["large_text"] = text(lang, "game_title")
        start = s.session_start if cfg["timer"] != "none" else None
        key = ("menu", state == text(lang, "menu_idle"))
    else:
        details = _where(s, lang)
        # Just in: the first health/weapon read is ~2 s away, keep "Loading…" rather than an empty line
        settling = (s.phase == "ingame" and s.last_dump is None and s.chapter_start is not None
                    and now - s.chapter_start < SETTLE_SECONDS)
        if s.phase == "loading" or settling:
            state = _e(cfg, "loading") + text(lang, "loading")
            kind = "loading"
        else:
            strong = _strong(s, cfg, lang, now, idle)
            if strong:
                kind, state = strong
            else:
                kind, state = "normal", _rotating(s, cfg, lang, now)
        # Large image: the campaign poster; its tooltip carries what does not fit on the lines
        poster = data.campaign_image(s.campaign) or _cover(cfg)
        if images and _url(poster):
            assets["large_image"] = poster
            tip = []
            if s.survival:
                tip.append(data.campaign_name(s.campaign, lang))  # the map's campaign, not on line 1 here
            elif cfg["show_difficulty"] and s.difficulty and s.team != TEAM_INFECTED:
                tip.append(text(lang, "difficulty", difficulty=data.difficulty_name(s.difficulty, lang)))
            if cfg["show_attempts"] and s.attempt > 1:
                tip.append(text(lang, "round_n" if s.survival else "attempt", n=s.attempt))
            if cfg["show_online"] and s.remote:
                tip.append(text(lang, "online"))
            tooltip = _join(tip)
            assets["large_text"] = (tooltip[0].upper() + tooltip[1:]) if tooltip else text(lang, "game_title")
        # Small image: who you are
        who = None
        if s.team == TEAM_INFECTED:
            w = data.weapon(s.weapon_class)
            who = w["names"]["en"] if w and w["kind"] == "claw" else None
        elif cfg["show_character"]:
            who = s.character
        portrait = _url((cfg.get("character_images") or {}).get(who or "")) or _url(data.character_image(who))
        if images and who and portrait:
            assets["small_image"] = portrait
            assets["small_text"] = who
        timer = cfg["timer"]
        start = {"campaign": s.campaign_start, "chapter": s.chapter_start, "session": s.session_start}.get(timer)
        if s.survival and timer != "none":
            # Survival: the round's time (from when it was seen starting); none while waiting or once it is over
            start = (s.round_start if s.round_end is None else None) if timer != "session" else s.session_start
        key = (s.phase, s.map, s.mode, kind, who, s.team)
        # Online: "(2 of 4)" after the state line
        if cfg["show_online"] and s.phase == "ingame" and s.humans and s.max_players and (s.remote or s.humans > 1):
            activity["party"] = {"id": "l4d2rpc-party", "size": [min(s.humans, s.max_players), s.max_players]}

    activity["details"] = truncate(details)
    activity["state"] = truncate(state)
    if start:
        timestamps["start"] = int(start)
    if timestamps:
        activity["timestamps"] = timestamps
    if assets:
        for k in ("large_text", "small_text"):
            if k in assets:
                assets[k] = truncate(assets[k])
        activity["assets"] = assets
    if cfg["buttons"]:
        activity["buttons"] = [{"label": truncate(b["label"], 32, 1), "url": b["url"]}
                               for b in cfg["buttons"][:2]]
    display = STATUS_DISPLAY_TYPES.get(cfg["status_display"], 0)
    if display:
        activity["status_display_type"] = display
    return {k: v for k, v in activity.items() if v is not None}, key
