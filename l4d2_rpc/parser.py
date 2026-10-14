"""Turns the game's console output (read through netcon) into events. Pure: no I/O, no clock.

Every line format handled here was seen in a real recording; see FINDINGS.md for the evidence.
Multi-line answers (`g15_dumpplayer`, `status`) are collected into one event each.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- single lines -----------------------------------------------------------------------------------------------
RE_NEW_GAME = re.compile(r"^Host_NewGame on map (\S+)")
RE_CHANGELEVEL = re.compile(r"^---- Host_Changelevel ----")
RE_SERVER_MAP = re.compile(r"^Map: (\S+)\s*$")
RE_SERVER_PLAYERS = re.compile(r"^Players: (\d+) \((\d+) bots\) / (\d+) humans")
RE_CONNECTED = re.compile(r"^#Cstrike_TitlesTXT_Game_connected")
RE_CONNECTING = re.compile(r"^(?:Connecting to|Connected to) (\S+)")
RE_LOCAL_CONNECT = re.compile(r"^Sending UDP connect to public IP (\S+)")
RE_DROPPED = re.compile(r"^Dropped (.*) from server \((.*)\)\s*$")
RE_DISCONNECT = re.compile(r"^Disconnect: (.*)$")
RE_MENU_VIDEO = re.compile(r"^BinkOpen\( .*[\\/]media[\\/]l4d2_background\d*\.bik", re.IGNORECASE)
RE_DAMAGE_REPORT = re.compile(r"^Player: (.*) - Damage Given\s*$")
RE_DIRECTOR_INIT = re.compile(r"^Initializing Director's script")
RE_SAFE_ROOM = re.compile(r"^Saving weapon_")
RE_ATTACKED = re.compile(r"^(.+) attacked (.+)$")
RE_CVAR = re.compile(r'^"([^"]+)" = "([^"]*)"')
RE_UNKNOWN = re.compile(r'^Unknown command:? "?([^"\s]+)"?')
RE_PASSWORD = re.compile(r"^This server is password protected for console access")

# --- g15_dumpplayer ---------------------------------------------------------------------------------------------
RE_DUMP_SECTION = re.compile(r"^\((localplayer|localteam|playerresource|localplayerweapon)\)\s*$")
RE_DUMP_FIELD = re.compile(r"^(C\w+)::([\w.\[\]]+)(?: (\w+) \((.*)\))?\s*$")
RE_DUMP_END = re.compile(r"^Other replacements:")

# --- status -----------------------------------------------------------------------------------------------------
RE_STATUS_HOST = re.compile(r"^hostname: ?(.*)$")
RE_STATUS_MAP = re.compile(r"^map\s+: (\S+)")
RE_STATUS_PLAYERS = re.compile(r"^players : (\d+) humans, (\d+) bots \((\d+) max\)")
RE_STATUS_HEADER = re.compile(r"^# userid name")
RE_STATUS_ROW = re.compile(r'^#\s*(\d+)\s+(?:\d+\s+)?"(.*)"\s+(BOT|\S+)(.*)$')
RE_STATUS_END = re.compile(r"^#end\s*$")


@dataclass
class Event:
    kind: str
    data: dict = field(default_factory=dict)

    def __repr__(self) -> str:  # compact in logs and test failures
        return f"Event({self.kind}, {self.data})" if self.data else f"Event({self.kind})"


def _value(kind: str | None, raw: str | None):
    if raw is None:
        return None
    if kind in ("integer", "short", "int"):
        try:
            return int(raw)
        except ValueError:
            return None
    if kind == "float":
        try:
            return float(raw)
        except ValueError:
            return None
    if kind == "bool":
        return raw.strip() == "true"
    return raw


class ConsoleParser:
    """Feed it console lines one by one; it returns the events each line completes."""

    def __init__(self) -> None:
        self._dump: dict | None = None
        self._dump_section: str | None = None
        self._status: dict | None = None

    # A dump or status block can be cut by the game closing: reset() drops it.
    def reset(self) -> None:
        self._dump = None
        self._dump_section = None
        self._status = None

    def feed(self, line: str) -> list[Event]:
        line = line.rstrip("\r\n")
        text = line.strip()
        out: list[Event] = []

        # ---- inside a g15_dumpplayer answer
        if self._dump is not None:
            m = RE_DUMP_SECTION.match(text)
            if m:
                self._dump_section = m.group(1)
                return out
            m = RE_DUMP_FIELD.match(text)
            if m:
                self._dump_field(*m.groups())
                return out
            if text == "":
                return out
            # "Other replacements:" ends the dump; any other line means it was cut short
            out.append(self._finish_dump())
            if RE_DUMP_END.match(text):
                return out

        if RE_DUMP_SECTION.match(text) and text == "(localplayer)":
            self._dump = {"player": {}, "weapon": {}, "weapon_class": None, "ammo": {}}
            self._dump_section = "localplayer"
            return out

        # ---- inside a status answer
        if self._status is not None:
            if self._status_line(text):
                if RE_STATUS_END.match(text):
                    out.append(Event("status", self._status))
                    self._status = None
                return out
            # unexpected line: the status block is over (or was cut)
            out.append(Event("status", self._status))
            self._status = None

        m = RE_STATUS_HOST.match(text)
        if m:
            self._status = {"hostname": m.group(1), "map": None, "humans": None, "bots": None, "max": None,
                            "rows": [], "local": False}
            return out

        out.extend(self._single(text))
        return out

    # ------------------------------------------------------------------------------------------------------------
    def _single(self, text: str) -> list[Event]:
        if not text:
            return []
        m = RE_NEW_GAME.match(text)
        if m:
            return [Event("new_game", {"map": m.group(1).lower()})]
        if RE_CHANGELEVEL.match(text):
            return [Event("changelevel")]
        m = RE_SERVER_MAP.match(text)
        if m:
            return [Event("server_map", {"map": m.group(1).lower()})]
        m = RE_SERVER_PLAYERS.match(text)
        if m:
            return [Event("server_players", {"players": int(m.group(1)), "bots": int(m.group(2)),
                                             "max": int(m.group(3))})]
        if RE_CONNECTED.match(text):
            return [Event("connected")]
        m = RE_LOCAL_CONNECT.match(text)
        if m:
            return [Event("connecting", {"remote": not _is_local(m.group(1))})]
        m = RE_CONNECTING.match(text)
        if m:
            return [Event("connecting", {"remote": not _is_local(m.group(1))})]
        m = RE_DROPPED.match(text)
        if m:
            return [Event("dropped", {"name": m.group(1), "reason": m.group(2)})]
        m = RE_DISCONNECT.match(text)
        if m:
            return [Event("disconnect", {"reason": m.group(1)})]
        if RE_MENU_VIDEO.match(text):
            return [Event("menu")]
        m = RE_DAMAGE_REPORT.match(text)
        if m:
            return [Event("damage_report", {"player": m.group(1)})]
        if RE_DIRECTOR_INIT.match(text):
            return [Event("director_init")]
        if RE_SAFE_ROOM.match(text):
            return [Event("safe_room")]
        m = RE_CVAR.match(text)
        if m:
            return [Event("cvar", {"name": m.group(1).lower(), "value": m.group(2)})]
        m = RE_UNKNOWN.match(text)
        if m:
            return [Event("unknown_command", {"name": m.group(1)})]
        if RE_PASSWORD.match(text):
            return [Event("password_required")]
        m = RE_ATTACKED.match(text)
        if m and len(m.group(1)) <= 64 and len(m.group(2)) <= 64:
            return [Event("friendly_fire", {"attacker": m.group(1), "victim": m.group(2)})]
        return []

    def _dump_field(self, cls: str, name: str, kind: str | None, raw: str | None) -> None:
        dump = self._dump
        section = self._dump_section
        value = _value(kind, raw)
        if section == "localplayer":
            m = re.match(r"m_iAmmo\[(\d+)\]$", name)
            if m:
                dump["ammo"][int(m.group(1))] = value
            elif name not in dump["player"] or dump["player"][name] is None:
                dump["player"][name] = value
            dump["player_class"] = cls
        elif section == "localplayerweapon":
            dump["weapon_class"] = cls
            if name not in dump["weapon"]:
                dump["weapon"][name] = value

    def _finish_dump(self) -> Event:
        dump = self._dump
        self._dump = None
        self._dump_section = None
        return Event("dump", dump)

    def _status_line(self, text: str) -> bool:
        status = self._status
        m = RE_STATUS_MAP.match(text)
        if m:
            status["map"] = m.group(1).lower()
            return True
        m = RE_STATUS_PLAYERS.match(text)
        if m:
            status["humans"], status["bots"], status["max"] = (int(m.group(i)) for i in (1, 2, 3))
            return True
        if RE_STATUS_END.match(text):
            return True
        m = RE_STATUS_ROW.match(text)
        if m and not RE_STATUS_HEADER.match(text):
            bot = m.group(3) == "BOT"
            rest = m.group(4)
            if not bot and rest.rstrip().endswith("loopback"):
                status["local"] = True
            status["rows"].append({"userid": int(m.group(1)), "name": m.group(2), "bot": bot,
                                   "loopback": (not bot) and rest.rstrip().endswith("loopback")})
            return True
        if RE_STATUS_HEADER.match(text) or text == "" or text.startswith(("version", "udp/ip", "os ", "os  ",
                                                                          "steamid", "account", "sourcetv")):
            return True
        return False


def _is_local(address: str) -> bool:
    host = address.rsplit(":", 1)[0].strip("[]")
    return host in ("127.0.0.1", "localhost", "loopback", "::1")
