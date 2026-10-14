"""Turn a netcon recording (tools/netcon_probe.py) into a readable timeline.

Prints only changes: g15_dumpplayer fields of interest, status player/bot list,
and console lines that are not query noise.

Usage:
    python tools/analyze_netcon.py recordings/session2.log [--all-fields]
"""

from __future__ import annotations

import re
import sys

FIELD_RE = re.compile(r"^(\S+) (C\w+)::(\w+(?:\[\d+\])?(?:\.\w)?)(?: \w+ \((.*)\))?$")
SECTION_RE = re.compile(r"^(\S+) \((localplayer|localteam|playerresource|localplayerweapon)\)$")
STATUS_ROW_RE = re.compile(r'^(\S+) #\s*(\d+)(?: \d+)? "([^"]*)" (BOT|STEAM_\S+)')
NOISE_RE = re.compile(
    r'^\S+ ( client replicated| - Difficulty| - Current map|"z_difficulty"|>>> |#end|# userid|hostname|version'
    r'|udp/ip|os  |map  |players|$|SCRIPT PERF|Couldn.t find any entities|Invalid counterterrorist'
    r'|Attempted to precache|prop_door_rotating|Other replacements|Saving weapon|Recreating weapon|Removing weapon)'
)

INTERESTING = {
    "localplayer": ["m_iHealth", "m_iTeamNum", "m_lifeState", "deadflag", "m_flMaxspeed", "m_iHideHUD",
                    "m_nModelIndex", "m_fFlags", "m_flStamina", "m_iFOV", "m_bDucked"],
    "localplayerweapon": ["m_iClip1", "m_iPrimaryAmmoType", "m_iState", "m_bInReload", "m_isDualWielding",
                          "m_nModelIndex", "m_iViewModelIndex"],
}


def main(path: str, all_fields: bool) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    section = None
    snap: dict[str, str] = {}
    snap_time = ""
    last: dict[str, str] = {}
    status_rows: list[str] = []
    last_status = ""
    ammo: dict[str, str] = {}

    def flush_snapshot() -> None:
        nonlocal snap, last
        if not snap:
            return
        ammo_type = snap.get("localplayerweapon.m_iPrimaryAmmoType")
        if ammo_type is not None and ammo_type.isdigit():
            snap["reserve_ammo"] = ammo.get(f"m_iAmmo[{ammo_type}]", "?")
        changes = {k: v for k, v in snap.items() if last.get(k) != v}
        if changes:
            print(f"{snap_time} DUMP " + ", ".join(f"{k}={v}" for k, v in sorted(changes.items())))
        last = dict(snap)
        snap = {}

    for line in lines:
        m = SECTION_RE.match(line)
        if m:
            if m.group(2) == "localplayer":
                flush_snapshot()
                snap_time = m.group(1)
                ammo.clear()
            section = m.group(2)
            continue
        m = FIELD_RE.match(line)
        if m and section:
            _, cls, field, value = m.groups()
            value = value or ""
            if field.startswith("m_iAmmo["):
                ammo[field] = value
                continue
            if section == "localplayerweapon":
                snap["weapon_class"] = cls
            if all_fields or field in INTERESTING.get(section, []):
                snap[f"{section}.{field}"] = value
            continue
        m = STATUS_ROW_RE.match(line)
        if m:
            status_rows.append(f"{m.group(3)}({'bot' if m.group(4) == 'BOT' else 'human'})")
            continue
        if line.endswith("#end"):
            joined = " ".join(status_rows)
            if joined != last_status:
                print(f"{line[:12]} STATUS {joined}")
                last_status = joined
            status_rows = []
            continue
        if section and line[13:].strip() == "":
            continue
        if not NOISE_RE.match(line) and "::" not in line:
            section = None
            print(line)
    flush_snapshot()
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], "--all-fields" in sys.argv))
