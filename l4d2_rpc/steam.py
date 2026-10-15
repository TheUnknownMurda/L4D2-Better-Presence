"""Read-only look at Steam's files: where the game is installed, and the game's launch options
(port and password of the network console, -g15). Nothing is ever written to Steam or to the game."""

from __future__ import annotations

import shlex
import winreg
from dataclasses import dataclass
from pathlib import Path

from . import vdf

APP_ID = "550"
STEAM_ID64_BASE = 76561197960265728


@dataclass
class LaunchOptions:
    raw: str = ""
    netcon_port: int | None = None
    netcon_password: str | None = None
    g15: bool = False
    source: str = ""  # the file they were read from


def steam_path() -> Path | None:
    for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
        try:
            with winreg.OpenKey(hive, key) as k:
                for name in ("SteamPath", "InstallPath"):
                    try:
                        value, _ = winreg.QueryValueEx(k, name)
                        if value and Path(value).exists():
                            return Path(value)
                    except OSError:
                        continue
        except OSError:
            continue
    default = Path(r"C:\Program Files (x86)\Steam")
    return default if default.exists() else None


def active_account_id() -> int | None:
    """The 32-bit account id of the Steam user currently logged in (0 when none)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam\ActiveProcess") as k:
            value, _ = winreg.QueryValueEx(k, "ActiveUser")
            return int(value) or None
    except (OSError, ValueError):
        return None


def game_dir(steam: Path | None = None) -> Path | None:
    steam = steam or steam_path()
    if not steam:
        return None
    libraries = [steam]
    try:
        folders = vdf.parse_file(steam / "steamapps" / "libraryfolders.vdf").get("libraryfolders") or {}
        for entry in folders.values():
            if isinstance(entry, dict) and entry.get("path"):
                libraries.append(Path(entry["path"]))
    except OSError:
        pass
    for lib in libraries:
        manifest = lib / "steamapps" / f"appmanifest_{APP_ID}.acf"
        if manifest.exists():
            try:
                installdir = vdf.parse_file(manifest).path("AppState", "installdir") or "Left 4 Dead 2"
            except OSError:
                installdir = "Left 4 Dead 2"
            path = lib / "steamapps" / "common" / installdir
            if path.exists():
                return path
    return None


def parse_launch_options(raw: str) -> LaunchOptions:
    opts = LaunchOptions(raw=raw or "")
    try:
        args = shlex.split(raw or "", posix=False)
    except ValueError:
        args = (raw or "").split()
    for i, arg in enumerate(args):
        low = arg.lower()
        nxt = args[i + 1].strip('"') if i + 1 < len(args) else None
        if low == "-netconport" and nxt and nxt.isdigit():
            opts.netcon_port = int(nxt)
        elif low == "-netconpassword" and nxt:
            opts.netcon_password = nxt
        elif low == "-g15":
            opts.g15 = True
    return opts


def launch_options(steam: Path | None = None, account_id: int | None = None) -> LaunchOptions | None:
    """The game's launch options as Steam stores them for the logged-in user (or the most recent one)."""
    steam = steam or steam_path()
    if not steam:
        return None
    userdata = steam / "userdata"
    candidates: list[Path] = []
    account_id = account_id or active_account_id()
    if account_id:
        candidates.append(userdata / str(account_id) / "config" / "localconfig.vdf")
    try:
        others = sorted(userdata.glob("*/config/localconfig.vdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        candidates += [p for p in others if p not in candidates]
    except OSError:
        pass
    for path in candidates:
        if not path.exists():
            continue
        try:
            text = vdf.decode(path.read_bytes())
        except OSError:
            continue
        apps = vdf.parse(text).path("UserLocalConfigStore", "Software", "Valve", "Steam", "apps")
        block = apps.get(APP_ID) if apps else None
        if isinstance(block, dict):
            opts = parse_launch_options(block.get("LaunchOptions") or "")
            opts.source = str(path)
            return opts
    return None


def masked(raw: str) -> str:
    """The launch options with the console password hidden, for screens people may share."""
    args = (raw or "").split()
    return " ".join("••••••" if i and args[i - 1].lower() == "-netconpassword" else a for i, a in enumerate(args))


def suggested_launch_options(password: str, port: int = 27015, current: str = "") -> str:
    """The launch options line to paste in Steam, keeping any other option already there."""
    kept = []
    skip = False
    try:
        args = shlex.split(current or "", posix=False)
    except ValueError:
        args = (current or "").split()
    for arg in args:
        if skip:
            skip = False
            continue
        if arg.lower() in ("-netconport", "-netconpassword"):
            skip = True
            continue
        if arg.lower() == "-g15":
            continue
        kept.append(arg)
    return " ".join(kept + ["-netconport", str(port), "-netconpassword", password, "-g15"])
