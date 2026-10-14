"""Card texts in English (default) and French. Game names come from data.py, not from here."""

from __future__ import annotations

STRINGS = {
    "en": {
        "menu": "In the main menu",
        "menu_last": "Last game: {campaign}",
        "menu_idle": "Getting ready",
        "loading": "Loading…",
        "chapter": "{campaign} · {n}/{total} {chapter}",
        "finale": "{campaign} · Finale: {chapter}",
        "custom_map": "Custom map: {map}",
        "unknown_map": "In a game",
        "health": "{health} HP",
        "last_life": "last life",
        "reloading": "reloading",
        "specials": "Specials: {names}",
        "solo_bots": "Solo with {bots} bots",
        "solo": "Solo",
        "players_bots": "{players} players + {bots} bots",
        "players": "{players} players",
        "dead": "Dead — waiting for a rescue",
        "dead_solo": "Dead",
        "incap": "Incapacitated — needs help!",
        "revived": "Revived — limping, {health} HP",
        "tank": "TANK!",
        "paused": "Paused",
        "safe_room": "Reached the safe room",
        "retry": "Retry #{n}",
        "idle": "Idle",
        "spectating": "Spectating",
        "infected": "Playing as the {name}",
        "in_game": "Surviving",
        "difficulty": "{difficulty} difficulty",
        "attempt": "attempt {n}",
        "online": "online",
        "game_title": "Left 4 Dead 2",
    },
    "fr": {
        "menu": "Au menu principal",
        "menu_last": "Dernière partie : {campaign}",
        "menu_idle": "Se prépare",
        "loading": "Chargement…",
        "chapter": "{campaign} · {n}/{total} {chapter}",
        "finale": "{campaign} · Finale : {chapter}",
        "custom_map": "Carte perso : {map}",
        "unknown_map": "En partie",
        "health": "{health} PV",
        "last_life": "dernière vie",
        "reloading": "recharge",
        "specials": "Spéciaux : {names}",
        "solo_bots": "Solo avec {bots} bots",
        "solo": "Solo",
        "players_bots": "{players} joueurs + {bots} bots",
        "players": "{players} joueurs",
        "dead": "Mort — en attente de secours",
        "dead_solo": "Mort",
        "incap": "À terre — a besoin d'aide !",
        "revived": "Relevé, boite — {health} PV",
        "tank": "TANK !",
        "paused": "En pause",
        "safe_room": "Pièce sécurisée atteinte",
        "retry": "Nouvel essai n°{n}",
        "idle": "Inactif",
        "spectating": "Spectateur",
        "infected": "Joue le {name}",
        "in_game": "Survit",
        "difficulty": "Difficulté {difficulty}",
        "attempt": "essai {n}",
        "online": "en ligne",
        "game_title": "Left 4 Dead 2",
    },
}

EMOJI = {
    "health": "❤️",
    "last_life": "🖤",
    "weapon": "🔫",
    "melee": "🔪",
    "throwable": "💣",
    "medkit": "🩹",
    "pills": "💊",
    "carry": "📦",
    "ammo_upgrade": "🧨",
    "specials": "🧟",
    "team": "👥",
    "solo": "🤖",
    "dead": "💀",
    "incap": "🩸",
    "revived": "🦯",
    "tank": "🔥",
    "paused": "⏸️",
    "safe_room": "🚪",
    "retry": "🔁",
    "idle": "💤",
    "loading": "⏳",
    "spectating": "👀",
    "infected": "🧟",
}


def text(lang: str, key: str, **kwargs) -> str:
    table = STRINGS.get(lang) or STRINGS["en"]
    template = table.get(key) or STRINGS["en"][key]
    return template.format(**kwargs)


def resolve_language(setting: str, game_language: str | None) -> str:
    """'en', 'fr', or 'auto' (follows the game's language: French if the game is in French, else English)."""
    setting = (setting or "en").lower()
    if setting == "auto":
        return "fr" if (game_language or "").lower() == "french" else "en"
    return setting if setting in STRINGS else "en"
