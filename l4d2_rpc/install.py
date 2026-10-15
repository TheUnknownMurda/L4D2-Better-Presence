"""Install.bat / Uninstall.bat: everything a new user needs, step by step, in one window.

Install: checks, the Steam launch options (copied to the clipboard, the password kept if already set), start with
Windows (a shortcut in the Startup folder), and starts the program now in the background.
Uninstall: stops it, removes the shortcut, says which launch options to remove, optionally deletes its data.
Nothing is ever written to the game folder or to Steam.
"""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from . import config as config_mod
from . import steam, system
from .discord_ipc import discord_running

ROOT = Path(__file__).resolve().parent.parent
STARTUP_LINK_NAME = "L4D2 Better Presence.lnk"
PID_FILE = config_mod.log_dir() / "companion.pid"
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200


def _ok(text: str) -> None:
    print(f"  [OK] {text}")


def _warn(text: str) -> None:
    print(f"  [!]  {text}")


def _ask_yes(question: str, default: bool, ask=input) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    try:
        answer = ask(f"{question} {hint} ").strip().lower()
    except EOFError:
        return default
    return default if not answer else answer in ("y", "yes", "o", "oui")


# ------------------------------------------------------------------------------------------------ launch options
def launch_options_line(opts: steam.LaunchOptions | None) -> tuple[str, bool]:
    """(line to paste, whether something must change). An existing password is kept, so pasting is not needed
    again after a reinstall."""
    if opts and opts.netcon_port and opts.netcon_password and opts.g15:
        return opts.raw, False
    password = (opts.netcon_password if opts and opts.netcon_password else None) or secrets.token_hex(8)
    port = opts.netcon_port if opts and opts.netcon_port else 27015
    return steam.suggested_launch_options(password, port, opts.raw if opts else ""), True


def copy_to_clipboard(text: str) -> bool:
    try:
        subprocess.run(["clip"], input=text.encode("ascii"), check=True)
        return True
    except (OSError, subprocess.CalledProcessError, UnicodeEncodeError):
        return False


# ------------------------------------------------------------------------------------------------ startup shortcut
def startup_link() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / \
        STARTUP_LINK_NAME


def pythonw_path() -> Path | None:
    candidate = Path(sys.executable).with_name("pythonw.exe")
    return candidate if candidate.exists() else (Path(shutil.which("pythonw")) if shutil.which("pythonw") else None)


def create_startup_link() -> str | None:
    """Creates the Startup shortcut; returns an error message or None."""
    pythonw = pythonw_path()
    if not pythonw:
        return f"pythonw.exe not found next to {sys.executable}."
    link = startup_link()

    def q(p) -> str:  # single-quoted PowerShell string (no double quotes: antivirus-friendly one-liner)
        return "'" + str(p).replace("'", "''") + "'"

    command = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut({q(link)});"
               f"$s.TargetPath={q(pythonw)};$s.Arguments='-m l4d2_rpc';$s.WorkingDirectory={q(ROOT)};"
               f"$s.Description='L4D2 Better Presence';$s.Save()")
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True)
    if result.returncode != 0 or not link.exists():
        return result.stderr.strip() or "the shortcut was not created"
    return None


def remove_startup_link() -> bool:
    link = startup_link()
    if link.exists():
        link.unlink()
        return True
    return False


# ------------------------------------------------------------------------------------------------ background process
def is_running() -> bool:
    lock = system.SingleInstance()
    running = lock.already_running
    lock.release()
    return running


def start_background() -> str | None:
    pythonw = pythonw_path()
    if not pythonw:
        return "pythonw.exe not found"
    subprocess.Popen([str(pythonw), "-m", "l4d2_rpc"], cwd=str(ROOT), close_fds=True,
                     creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)
    return None


def stop_running() -> bool:
    try:
        pid = int(PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return False
    stopped = system.terminate_python(pid)
    try:
        PID_FILE.unlink()
    except OSError:
        pass
    return stopped


# ------------------------------------------------------------------------------------------------ install
def run_install(ask=input) -> int:
    print("L4D2 Better Presence - install\n")
    print("1. Checks")
    _ok(f"Python {sys.version.split()[0]}")
    if discord_running():
        _ok("Discord desktop app is running")
    else:
        _warn("Discord desktop app not found. Start it (the browser version cannot show game activities).")
    game = steam.game_dir()
    if game:
        _ok(f"Left 4 Dead 2 found: {game}")
    else:
        _warn("Left 4 Dead 2 not found in your Steam libraries (install it from Steam).")

    print("\n2. Steam launch options (they let this program read the game's console)")
    opts = steam.launch_options()
    line, must_change = launch_options_line(opts)
    if not must_change:
        _ok("Already set: " + line)
    else:
        copied = copy_to_clipboard(line)
        print("   In Steam: Library > right-click Left 4 Dead 2 > Properties... > General > LAUNCH OPTIONS.")
        print("   Replace what is in the box with this line" + (" (already copied: just press Ctrl+V):" if copied
                                                                 else ":"))
        print(f"\n      {line}\n")
        print("   If the game is running, restart it afterwards.")
        try:
            ask("   Press Enter once it is pasted in Steam... ")
        except EOFError:
            pass
        check = steam.launch_options()
        if check and check.netcon_port and check.netcon_password and check.g15:
            _ok("Steam has the launch options")
        else:
            _warn("Steam does not show them yet (Steam saves them when the Properties window closes). "
                  "Run Doctor.bat later to check.")

    print("\n3. Start with Windows")
    if _ask_yes("   Start L4D2 Better Presence silently with Windows (recommended)?", True, ask):
        error = create_startup_link()
        if error:
            _warn(f"Could not create the Startup shortcut: {error}")
        else:
            _ok("It will start with Windows and wait for the game (almost no CPU while waiting).")
    else:
        remove_startup_link()
        _ok("Not started with Windows: double-click L4D2RPC.bat before playing.")

    print("\n4. Starting it now")
    if is_running():
        _ok("Already running")
    else:
        error = start_background()
        if error:
            _warn(f"Could not start it: {error}. Double-click L4D2RPC.bat instead.")
        else:
            _ok("Running in the background")

    print("\nAll set. Start Left 4 Dead 2 from Steam: your Discord profile shows the card within a minute.")
    print("In Discord, keep Settings > Activity Privacy > 'Share my activity' on.")
    print("Something wrong? Double-click Doctor.bat. Log: " + str(config_mod.log_dir() / "l4d2rpc.log"))
    return 0


# ------------------------------------------------------------------------------------------------ uninstall
def run_uninstall(ask=input) -> int:
    print("L4D2 Better Presence - uninstall\n")
    _ok("Stopped the running program" if stop_running() else "The program was not running")
    _ok("Removed the start with Windows" if remove_startup_link() else "It did not start with Windows")
    opts = steam.launch_options()
    if opts and (opts.netcon_port or opts.netcon_password or opts.g15):
        print("\n   In Steam (Library > right-click Left 4 Dead 2 > Properties... > General > LAUNCH OPTIONS),")
        print("   remove: -netconport … -netconpassword … -g15")
        print(f"   They are now: {opts.raw}")
    data = config_mod.log_dir()
    if data.exists() and _ask_yes(f"\n   Also delete the log and your Survival best times ({data})?", False, ask):
        shutil.rmtree(data, ignore_errors=True)
        _ok("Deleted")
    print("\nDone. You can now delete this folder. Nothing was ever written to the game or to Steam.")
    return 0
