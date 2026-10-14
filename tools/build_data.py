"""Generate data/game_data.json (names) and data/images.json (image links).

Names come from the game's own files, read-only:
  - update/pak01_dir.vpk          missions/campaign1.txt … campaign14.txt (maps, chapter order)
  - left4dead2/pak01_dir.vpk      resource/l4d360ui_<lang>.txt, resource/left4dead2_<lang>.txt
  - update/resource/l4d360ui_tu_<lang>.txt   (title-update strings: campaigns 6-14)
Weapon class names were read from left4dead2/bin/client.dll (see FINDINGS.md); their display names are
the game's own strings where it has one, otherwise the Left 4 Dead Wiki's page title (EN) and a plain
French translation (marked "project" in the output).

Images (--images, needs internet): page images of the Left 4 Dead Wiki (left4dead.fandom.com MediaWiki
API, prop=pageimages) and Steam's store art for app 550. Every link is checked (HTTP 200) before it is kept.

Usage:
    python tools/build_data.py [--game "C:\\...\\Left 4 Dead 2"] [--images]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from l4d2_rpc import vdf  # noqa: E402
from vpk import Vpk  # noqa: E402

DEFAULT_GAME = r"C:\Program Files (x86)\Steam\steamapps\common\Left 4 Dead 2"
LANGS = ("english", "french")
SHORT = {"english": "en", "french": "fr"}

# Wiki page per campaign (the API follows redirects).
CAMPAIGN_PAGES = {
    1: "Dead Center", 2: "Dark Carnival", 3: "Swamp Fever", 4: "Hard Rain", 5: "The Parish",
    6: "The Passing", 7: "The Sacrifice", 8: "No Mercy", 9: "Crash Course", 10: "Death Toll",
    11: "Dead Air", 12: "Blood Harvest", 13: "Cold Stream", 14: "The Last Stand (Left 4 Dead)",
}
# Survivors: the game's own HUD portraits (materials/vgui/s_panel_<internal name>.vtf), as uploaded on the wiki.
SURVIVOR_FILES = {
    "Coach": "File:S_panel_coach.png", "Ellis": "File:S_panel_mechanic.png", "Nick": "File:S_panel_gambler.png",
    "Rochelle": "File:S_panel_producer.png", "Bill": "File:S_panel_namvet.png", "Zoey": "File:S_panel_teenangst.png",
    "Francis": "File:S_panel_biker.png", "Louis": "File:S_panel_manager.png",
}
CHARACTER_PAGES = {
    "Tank": "The Tank", "Witch": "The Witch", "Hunter": "The Hunter", "Smoker": "The Smoker",
    "Boomer": "The Boomer", "Spitter": "The Spitter", "Charger": "The Charger", "Jockey": "The Jockey",
}
STEAM_ART = {
    "cover": "https://cdn.cloudflare.steamstatic.com/steam/apps/550/library_600x900.jpg",
    "header": "https://cdn.cloudflare.steamstatic.com/steam/apps/550/header.jpg",
}

# client class -> (kind, game string key or None, English name, French name when the game has none)
# kind: primary, secondary, melee, throwable, medkit, pills, ammo_upgrade, carry, claw
WEAPONS = {
    "CPistol": ("secondary", "L4D_Weapon_Pistol", "Pistol", None),
    "CMagnumPistol": ("secondary", None, "Magnum", "Magnum"),
    "CTerrorMeleeWeapon": ("melee", None, "Melee weapon", "Arme de corps à corps"),
    "CChainsaw": ("melee", None, "Chainsaw", "Tronçonneuse"),
    "CSubMachinegun": ("primary", "L4D_Weapon_SMG", "Submachine Gun", None),
    "CSMG_Silenced": ("primary", None, "Silenced SMG", "Mitrailleuse silencieuse"),
    "CSMG_MP5": ("primary", None, "MP5", "MP5"),
    "CPumpShotgun": ("primary", "L4D_Weapon_PumpShotgun", "Pump Shotgun", None),
    "CShotgun_Chrome": ("primary", None, "Chrome Shotgun", "Fusil à pompe chromé"),
    "CAutoShotgun": ("primary", "L4D_Weapon_AutoShotgun", "Tactical Shotgun", None),
    "CShotgun_SPAS": ("primary", None, "Combat Shotgun", "Fusil de combat SPAS"),
    "CAssaultRifle": ("primary", "L4D_Weapon_AssaultRifle", "M-16 Assault Rifle", None),
    "CRifle_AK47": ("primary", None, "AK-47", "AK-47"),
    "CRifle_Desert": ("primary", None, "Combat Rifle", "Fusil de combat"),
    "CRifle_SG552": ("primary", None, "SG 552", "SG 552"),
    "CRifle_M60": ("primary", None, "M60", "M60"),
    "CSniperRifle": ("primary", "L4D_Weapon_HuntingRifle", "Hunting Rifle", None),
    "CSniper_Military": ("primary", None, "Military Sniper Rifle", "Fusil de précision militaire"),
    "CSniper_Scout": ("primary", None, "Scout", "Scout"),
    "CSniper_AWP": ("primary", None, "AWP", "AWP"),
    "CGrenadeLauncher": ("primary", None, "Grenade Launcher", "Lance-grenades"),
    "CMolotov": ("throwable", "L4D_Weapon_Molotov", "Molotov", None),
    "CPipeBomb": ("throwable", "L4D_Weapon_PipeBomb", "Pipe Bomb", None),
    "CItem_VomitJar": ("throwable", None, "Bile Bomb", "Bocal de bile"),
    "CFirstAidKit": ("medkit", "L4D_Weapon_FirstAidKit", "First Aid Kit", None),
    "CItemDefibrillator": ("medkit", None, "Defibrillator", "Défibrillateur"),
    "CItemUpgradePackExplosive": ("ammo_upgrade", None, "Explosive Ammo", "Munitions explosives"),
    "CItemUpgradePackIncendiary": ("ammo_upgrade", None, "Incendiary Ammo", "Munitions incendiaires"),
    "CPainPills": ("pills", "L4D_Weapon_PainPills", "Pain Pills", None),
    "CItem_Adrenaline": ("pills", None, "Adrenaline", "Adrénaline"),
    "CGasCan": ("carry", None, "Gas Can", "Bidon d'essence"),
    "CPropaneTank": ("carry", None, "Propane Tank", "Bonbonne de propane"),
    "COxygenTank": ("carry", None, "Oxygen Tank", "Bouteille d'oxygène"),
    "CFireworkCrate": ("carry", None, "Fireworks Crate", "Caisse de feux d'artifice"),
    "CGnome": ("carry", None, "Gnome Chompski", "Gnome Chompski"),
    "CItemAmmoPack": ("carry", None, "Ammo Pack", "Pack de munitions"),
    "CTankClaw": ("claw", None, "Tank", "Tank"),
    "CHunterClaw": ("claw", None, "Hunter", "Hunter"),
    "CSmokerClaw": ("claw", None, "Smoker", "Smoker"),
    "CBoomerClaw": ("claw", None, "Boomer", "Boomer"),
    "CJockeyClaw": ("claw", None, "Jockey", "Jockey"),
    "CSpitterClaw": ("claw", None, "Spitter", "Spitter"),
    "CChargerClaw": ("claw", None, "Charger", "Charger"),
}

# English names checked against the wiki's page titles and redirects on 2026-10-14; this one has no page.
NO_WIKI_PAGE = {"CFireworkCrate"}

DIFFICULTIES = {"Easy": "Easy", "Normal": "Normal", "Hard": "Hard", "Impossible": "Impossible"}
MODES = ["coop", "realism", "survival", "versus", "teamversus", "scavenge", "teamscavenge"]
SURVIVORS_L4D2 = ["Coach", "Ellis", "Nick", "Rochelle"]
SURVIVORS_L4D1 = ["Bill", "Zoey", "Francis", "Louis"]
SPECIAL_INFECTED = ["Tank", "Witch", "Hunter", "Smoker", "Boomer", "Spitter", "Charger", "Jockey"]


def load_strings(game: Path, lang: str) -> dict[str, str]:
    """All UI strings for one language, title-update file last so it wins."""
    base = Vpk(str(game / "left4dead2" / "pak01_dir.vpk"))
    strings: dict[str, str] = {}
    sources = [
        vdf.decode(base.read(f"resource/l4d360ui_{lang}.txt")),
        vdf.decode(base.read(f"resource/left4dead2_{lang}.txt")),
        vdf.decode((game / "update" / "resource" / f"l4d360ui_tu_{lang}.txt").read_bytes()),
    ]
    for text in sources:
        tokens = vdf.parse(text).path("lang", "Tokens") or {}
        for key, value in tokens.items():
            if isinstance(value, str) and not key.startswith("[english]"):
                strings[key.lower()] = value
    return strings


def localise(strings: dict[str, str], token: str) -> str | None:
    if not token:
        return None
    return strings.get(token.lstrip("#").lower())


def strip_number(name: str) -> str:
    """'1: Hôtel' -> 'Hôtel'."""
    return re.sub(r"^\s*\d+\s*:\s*", "", name).strip()


def build_game_data(game: Path) -> dict:
    update = Vpk(str(game / "update" / "pak01_dir.vpk"))
    strings = {lang: load_strings(game, lang) for lang in LANGS}
    campaigns = []
    maps: dict[str, dict] = {}
    for n in range(1, 15):
        mission = vdf.parse(vdf.decode(update.read(f"missions/campaign{n}.txt"))).get("mission")
        names = {SHORT[l]: localise(strings[l], mission.get("DisplayTitle")) for l in LANGS}
        modes = mission.get("modes") or {}
        coop = modes.get("coop") or {}
        chapters = []
        for index in sorted(coop, key=lambda k: int(k)):
            entry = coop[index]
            chapter_names = {SHORT[l]: strip_number(localise(strings[l], entry.get("DisplayName")) or entry.get("Map"))
                             for l in LANGS}
            chapters.append({"map": entry.get("Map"), "names": chapter_names})
        campaign = {"id": n, "names": names, "chapters": chapters, "modes": sorted(modes.keys())}
        campaigns.append(campaign)
        total = len(chapters)
        for i, ch in enumerate(chapters, 1):
            maps[ch["map"].lower()] = {"campaign": n, "chapter": i, "chapters": total}
        # Survival and Scavenge give their own name to the maps they use ("Gun Shop" for c1m2_streets)
        for mode, block in modes.items():
            if mode == "coop" or not isinstance(block, dict):
                continue
            for entry in block.values():
                if not (isinstance(entry, dict) and entry.get("Map")):
                    continue
                key = entry["Map"].lower()
                mode_names = {SHORT[l]: strip_number(localise(strings[l], entry.get("DisplayName")) or entry["Map"])
                              for l in LANGS}
                if key not in maps:  # a map used only by this mode
                    maps[key] = {"campaign": n, "chapter": None, "chapters": total, "names": mode_names}
                if mode in ("survival", "scavenge"):
                    maps[key].setdefault("mode_names", {})[mode] = mode_names

    difficulties = {}
    for value, key in DIFFICULTIES.items():
        difficulties[value] = {SHORT[l]: localise(strings[l], f"L4D360UI_Difficulty_{key}") for l in LANGS}
    modes = {m: {SHORT[l]: localise(strings[l], f"L4D360UI_Mode_{m}") for l in LANGS} for m in MODES}

    weapons = {}
    for cls, (kind, key, en, fr) in WEAPONS.items():
        game_fr = localise(strings["french"], key) if key else None
        game_en = localise(strings["english"], key) if key else None
        weapons[cls] = {
            "kind": kind,
            "names": {"en": game_en or en, "fr": game_fr or fr},
            "source": {"en": "game" if game_en else ("project" if cls in NO_WIKI_PAGE else "wiki"),
                       "fr": "game" if game_fr else "project"},
        }

    return {
        "_generated_by": "tools/build_data.py from the game files (see FINDINGS.md)",
        "campaigns": campaigns,
        "maps": dict(sorted(maps.items())),
        "difficulties": difficulties,
        "modes": modes,
        "weapons": weapons,
        "survivors": SURVIVORS_L4D2 + SURVIVORS_L4D1,
        "special_infected": SPECIAL_INFECTED,
    }


def http_ok(url: str) -> bool:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "L4D2-Better-Presence-data-tool"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read(64)
            return r.status == 200
    except Exception:
        return False


def wiki_images(titles: list[str]) -> dict[str, str]:
    query = urllib.parse.urlencode({
        "action": "query", "prop": "pageimages", "piprop": "original", "redirects": "1",
        "format": "json", "titles": "|".join(titles),
    })
    req = urllib.request.Request(f"https://left4dead.fandom.com/api.php?{query}",
                                 headers={"User-Agent": "L4D2-Better-Presence-data-tool"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)["query"]
    redirects = {d["to"]: d["from"] for d in data.get("redirects", [])}
    out = {}
    for page in data["pages"].values():
        src = (page.get("original") or {}).get("source")
        if src:
            out[redirects.get(page["title"], page["title"])] = src
    return out


def wiki_files(titles: list[str]) -> dict[str, str]:
    """Direct links of wiki files ("File:…" titles), keyed by their normalised title."""
    query = urllib.parse.urlencode({"action": "query", "prop": "imageinfo", "iiprop": "url", "format": "json",
                                    "titles": "|".join(titles)})
    req = urllib.request.Request(f"https://left4dead.fandom.com/api.php?{query}",
                                 headers={"User-Agent": "L4D2-Better-Presence-data-tool"})
    with urllib.request.urlopen(req, timeout=30) as r:
        pages = json.load(r)["query"]["pages"]
    return {p["title"]: p["imageinfo"][0]["url"] for p in pages.values() if p.get("imageinfo")}


def build_images() -> dict:
    result = {"_generated_by": "tools/build_data.py --images (Left 4 Dead Wiki page images, Steam store art)",
              "steam": {}, "campaigns": {}, "characters": {}}
    for key, url in STEAM_ART.items():
        if http_ok(url):
            result["steam"][key] = url
        else:
            print(f"Steam art not reachable: {url}")
    found = wiki_images(list(CAMPAIGN_PAGES.values()))
    for n, title in CAMPAIGN_PAGES.items():
        url = found.get(title)
        if url and len(url) <= 256 and http_ok(url):
            result["campaigns"][str(n)] = url
        else:
            print(f"No usable image for campaign {n} ({title})")
    found = wiki_files(list(SURVIVOR_FILES.values()))
    for name, title in SURVIVOR_FILES.items():
        url = found.get(title.replace("_", " "))
        if url and len(url) <= 256 and http_ok(url):
            result["characters"][name] = url
        else:
            print(f"No usable portrait for {name} ({title})")
    found = wiki_images(list(CHARACTER_PAGES.values()))
    for name, title in CHARACTER_PAGES.items():
        url = found.get(title)
        if url and len(url) <= 256 and http_ok(url):
            result["characters"][name] = url
        else:
            print(f"No usable image for {name} ({title})")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=DEFAULT_GAME)
    ap.add_argument("--images", action="store_true", help="also refresh data/images.json (needs internet)")
    args = ap.parse_args()
    game = Path(args.game)
    out = ROOT / "l4d2_rpc" / "data"
    out.mkdir(exist_ok=True)
    data = build_game_data(game)
    (out / "game_data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"game_data.json: {len(data['campaigns'])} campaigns, {len(data['maps'])} maps, {len(data['weapons'])} weapons")
    if args.images:
        images = build_images()
        (out / "images.json").write_text(json.dumps(images, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"images.json: {len(images['campaigns'])} campaigns, {len(images['characters'])} characters")
    return 0


if __name__ == "__main__":
    sys.exit(main())
