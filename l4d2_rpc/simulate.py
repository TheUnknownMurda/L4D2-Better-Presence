"""A fake game that goes through every situation of the card, built from console lines in the exact formats
recorded on the real game (FINDINGS.md). Used by `--simulate` and by the tests."""

from __future__ import annotations

from dataclasses import dataclass, field


def dump_lines(health=100, team=2, weapon="CSubMachinegun", clip=50, ammo_type=5, reserve=650, tick=1000,
               dead=False, reloading=False) -> list[str]:
    """A shortened g15_dumpplayer answer with the fields the program reads."""
    lines = [
        "(localplayer)",
        "",
        f"C_TerrorPlayer::m_iTeamNum integer ({team})",
        f"C_TerrorPlayer::m_iHealth integer ({health})",
        f"C_TerrorPlayer::m_nTickBase integer ({tick})",
        f"C_TerrorPlayer::deadflag bool ({'true' if dead else 'false'})",
        f"C_TerrorPlayer::m_flMaxspeed float ({900.0 if dead else 220.0:.6f})",
    ]
    lines += [f"C_TerrorPlayer::m_iAmmo[{i}] integer ({reserve if i == ammo_type else 0})" for i in range(32)]
    lines += ["(localteam)", "", "C_Team::m_iTeamNum integer (0)",
              "(playerresource)", "", "C_PlayerResource::m_iHealth integer (0)",
              "(localplayerweapon)", "",
              f"{weapon}::m_iClip1 integer ({clip})",
              f"{weapon}::m_iPrimaryAmmoType integer ({ammo_type})",
              f"{weapon}::m_bInReload bool ({'true' if reloading else 'false'})",
              "Other replacements:", ""]
    return lines


def status_lines(map_name="c2m1_highway", humans=None, bots=("Coach", "Nick", "Ellis"), local=True,
                 max_players=4) -> list[str]:
    humans = humans or [("Sam", "loopback" if local else "203.0.113.7:27005")]
    lines = ["hostname: Sam" if local else "hostname: Some Server", "version : 2.2.4.3 10097 insecure  ",
             "os      : Windows Listen" if local else "os      : Linux Dedicated",
             f"map     : {map_name} at ( 0, 0, 0 )",
             f"players : {len(humans)} humans, 0 bots ({max_players} max) (not hibernating) (unreserved)", "",
             "# userid name uniqueid connected ping loss state rate adr"]
    uid = 2
    for name, adr in humans:
        lines.append(f'#  {uid} 1 "{name}" STEAM_1:1:{1000 + uid} 01:35 33 0 active 30000 {adr}')
        uid += 1
    for name in bots:
        lines.append(f'# {uid} "{name}" BOT active')
        uid += 1
    lines.append("#end")
    return lines


@dataclass
class Step:
    title: str
    lines: list[str] = field(default_factory=list)
    seconds: float = 10  # how long the situation lasts
    idle: float = 0  # simulated keyboard/mouse idle time
    process: str = "running"  # running | closed


def scenario() -> list[Step]:
    t = 1000  # tick counter
    steps = [
        Step("Main menu (game just started)", [
            "BinkOpen( c:\\program files (x86)\\steam\\steamapps\\common\\left 4 dead 2\\left4dead2\\media\\l4d2_background05.bik )",
            '"name" = "Sam"', '"cl_language" = "english" ( def. "english" )', '"z_difficulty" = "Easy" ( def. "Normal" )']),
        Step("Loading a solo game", ["---- Host_NewGame ----", "Host_NewGame on map c2m1_highway",
                                     "Executing listen server config file",
                                     "Initializing Director's script", "Initializing Director's script",
                                     "Sending UDP connect to public IP 127.0.0.1:27015"]),
        Step("In game: health and weapon", ["Left 4 Dead 2", "Map: c2m1_highway",
                                            "Players: 1 (0 bots) / 4 humans", "#Cstrike_TitlesTXT_Game_connected"]
             + status_lines() + dump_lines(health=81, tick=t), seconds=22),
        Step("In game: specials alive (rotation)", status_lines(bots=("Coach", "Nick", "Ellis", "Charger", "Jockey"))
             + dump_lines(health=81, clip=37, tick=t + 300), seconds=22),
        Step("Tank!", status_lines(bots=("Coach", "Nick", "Ellis", "Tank")) + dump_lines(health=64, tick=t + 600)),
        Step("Incapacitated", dump_lines(health=297, weapon="CPistol", clip=15, ammo_type=1, reserve=0, tick=t + 900)),
        Step("Revived (limping)", status_lines() + dump_lines(health=1, weapon="CPistol", clip=15, ammo_type=1,
                                                                   reserve=0, tick=t + 1200)),
        Step("Paused (Esc in solo)", dump_lines(health=1, tick=t + 1200) + dump_lines(health=1, tick=t + 1200)),
        Step("Dead", ["Player: Sam - Damage Given", "-------------------------",
                      'Damage Given to "Tank" - 700 in 3 hits'] + dump_lines(health=0, dead=True, tick=t + 1500)),
        Step("Chapter restarts (retry)", ["Initializing Director's script", "Initializing Director's script"]
             + dump_lines(health=100, weapon="CPistol", clip=15, ammo_type=1, reserve=0, tick=t + 1800)),
        Step("Safe room reached", ["Saving weapon_first_aid_kit_spawn at 2022, 4298, 1214 (model x.mdl)"]
             + dump_lines(health=100, tick=t + 2100)),
        Step("Next chapter loading", ["---- Host_Changelevel ----", "Initializing Director's script"]),
        Step("Finale", ["Left 4 Dead 2", "Map: c2m5_concert", "Players: 1 (0 bots) / 4 humans",
                        "#Cstrike_TitlesTXT_Game_connected"] + status_lines("c2m5_concert")
             + dump_lines(health=93, weapon="CRifle_AK47", clip=40, ammo_type=3, reserve=360, tick=t + 2400)),
        Step("Idle (no keyboard/mouse for 5 min)", dump_lines(health=93, weapon="CRifle_AK47", clip=40, ammo_type=3,
                                                              reserve=360, tick=t + 2700), idle=400),
        Step("Back to the main menu", [
            "BinkOpen( c:\\program files (x86)\\steam\\steamapps\\common\\left 4 dead 2\\left4dead2\\media\\l4d2_background01.bik )",
            "Dropped Sam from server (Server shutting down)"]),
        Step("Online co-op on a server", ["Connecting to 203.0.113.7:27015", "Left 4 Dead 2", "Map: c8m2_subway",
                                          "Players: 3 (1 bots) / 4 humans", "#Cstrike_TitlesTXT_Game_connected"]
             + status_lines("c8m2_subway", humans=[("Sam", "198.51.100.2:27005"), ("Friend", "198.51.100.3:27005"),
                                                   ("Other", "198.51.100.4:27005")], bots=("Bill",), local=False)
             + dump_lines(health=72, weapon="CShotgun_Chrome", clip=8, ammo_type=7, reserve=72, tick=5000),
             seconds=22),
        Step("Versus, playing a Hunter", ["Disconnect: Server shutting down", "Connecting to 203.0.113.7:27015",
                                          "Left 4 Dead 2", "Map: c5m1_waterfront", "Players: 8 (0 bots) / 8 humans",
                                          "#Cstrike_TitlesTXT_Game_connected"]
             + status_lines("c5m1_waterfront", humans=[("Sam", "198.51.100.2:27005"), ("P2", "1.2.3.4:1")],
                            bots=(), local=False, max_players=8)
             + dump_lines(health=250, team=3, weapon="CHunterClaw", clip=-1, ammo_type=-1, reserve=0, tick=6000)),
        Step("Game closed", [], process="closed"),
    ]
    return steps
