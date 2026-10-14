# Left 4 Dead 2 · Detailed Discord Rich Presence

Shows on your Discord profile what you are doing in **Left 4 Dead 2**, live: campaign and chapter, your health
and the weapon in your hands, specials alive, Tank fights, when you are down, dead, paused or in the safe room.
No mod, no injection, nothing read from the game's memory: it only talks to the game's own console.

```
Playing Left 4 Dead 2                             [campaign poster]  [your survivor]
Dark Carnival · 1/5 Highway                        ← details: where you are
❤️ 81 HP · 🔫 Submachine Gun 50/650                 ← state: what moves (changes every 20 s):
🧟 Specials: Charger, Jockey                           health & weapon / specials alive / team (online)
12:34 elapsed                                      (2 of 4 online)
```

| Situation | Line 1 (`details`) | Line 2 (`state`) | Images |
|---|---|---|---|
| Main menu | In the main menu | Last game: Dark Carnival (or Getting ready) | your cover image, tooltip "Left 4 Dead 2" |
| Loading | Dark Carnival · 1/5 Highway | ⏳ Loading… | poster, tooltip "Easy difficulty" |
| In game | Dark Carnival · 1/5 Highway | rotates: ❤️ 81 HP · 🔫 Submachine Gun 50/650 / 🧟 Specials: Charger, Jockey / 👥 2 players + 2 bots (online only) | poster + your survivor (Rochelle) |
| Finale | Dead Center · Finale: Atrium | same | same |
| Tank alive | same | 🔥 TANK! · ❤️ 64 HP · 🔫 Submachine Gun 50/650 | same |
| Incapacitated | same | 🩸 Incapacitated — needs help! | same |
| Just revived | same | 🦯 Revived — limping, 1 HP (20 s) | same |
| Two revives without a kit | same | 🖤 1 HP (last life) · 🔫 Pistol 15 | same |
| Paused (solo) | same | ⏸️ Paused | same |
| Dead | same | 💀 Dead (solo) / 💀 Dead — waiting for a rescue | same |
| Chapter restarts | same | 🔁 Retry #2 (20 s), then "attempt 2" in the poster tooltip | same |
| Safe room door closed | same | 🚪 Reached the safe room | same |
| Survival, timer not started | Survival · Gun Shop | ⏱️ Waiting to start the round · best 3:21 (no timer) | poster (tooltip: the campaign) + survivor |
| Survival, round on | Survival · Gun Shop | same rotation and alerts as in game, plus 🏆 Best here: 3:21 (or 🏆 Beating the best (3:21)!); **the timer counts the round** | same |
| Survival, dead (solo) | same | 💀 Round over — 2:47 · 🏆 new best! (timer stops), then 🔁 Round #2 | same |
| Survival, dead (online, team still up) | same | 💀 Dead — the round goes on | same |
| Versus, as infected | The Parish · 1/5 Waterfront | 🧟 Playing as the Hunter · 250 HP | poster + Hunter |
| No keyboard/mouse for 5 min | same | 💤 Idle | same |
| Game closed, Ctrl+C, window closed | — | the card disappears | — |

## Installation (5 minutes)

### What you need

- **Windows 10 or 11** and **Left 4 Dead 2** on Steam.
- **Discord**, the desktop app (Stable, PTB or Canary), running on the same PC. The browser version cannot show
  game activities.
- **Python 3.10 or newer**: <https://www.python.org/downloads/> → *Download Python*, run the installer and tick
  *Add python.exe to PATH*. Nothing else to install: the program only uses Python's standard library.

No Discord application to create: the card uses Discord's own "Left 4 Dead 2" application, so you get one
enriched "Playing Left 4 Dead 2" instead of two activities.

### Steps

1. **Put this folder somewhere it can stay**, for example `Documents\L4D2 Better Presence`.
2. **Double-click `Setup.bat`.** It prints a line of Steam launch options with a new random password and copies
   it to the clipboard. In Steam: *Library* → right-click **Left 4 Dead 2** → *Properties…* → *General* →
   **Launch options**: replace the content with Ctrl+V. Any option you already had is kept.
   *Check:* the box now contains `-netconport 27015 -netconpassword <16 characters> -g15`.
3. **Double-click `L4D2RPC.bat`.** A console opens: `Waiting for Left 4 Dead 2…`.
4. **Start Left 4 Dead 2 from Steam.**
   *Check:* the console prints `Game detected`, then `Connected to the game console` (it can take up to a minute
   while the game starts), and `Card sent: In the main menu | …`. Your Discord profile shows the card.
5. In Discord, make sure **Settings → Activity Privacy → "Share my activity"** is on.
6. *Optional:* **double-click `Startup-on.bat`** to start it silently with Windows from now on. It then waits in
   the background for the game, at almost no cost. `Startup-off.bat` undoes it.

`Doctor.bat` checks everything (Python, Discord, the game, its launch options, the console) and says what to fix.

### Not working?

| Problem | Fix |
|---|---|
| Nothing on Discord | Discord desktop app open? "Share my activity" on (step 5)? Run `Doctor.bat`. The log `%LOCALAPPDATA%\L4D2RPC\l4d2rpc.log` lists every card sent and Discord's answer. |
| The card stays on "In the main menu" in game | The game was started without the launch options: redo step 2, then **restart the game**. The console says `The game was not started with -netconport`. |
| `The game refused the console password` | The launch options changed while the game was running: restart the game. |
| No health or weapon, only the chapter | `-g15` is missing from the launch options (step 2), then restart the game. |
| Two activities on the profile | You changed `client_id`: keep the default `356954277803065354` (Discord's own L4D2 application), or hide the game in Discord → *Settings → Registered Games*. |
| Images missing (empty squares) | Discord fetches each image the first time it sees it: wait a few seconds. If your `cover_image` link stopped working, change it or set it to `""` (Steam art is used). |
| Card late by a few seconds when a new campaign loads | Normal the first time a campaign's poster is used: Discord downloads it before answering. |
| Windows "protected your PC" on a `.bat` | *More info* → *Run anyway*. The scripts only start Python. |
| Bitdefender (or another antivirus) blocks something | Nothing here hides a process or downloads code. Add the project folder to the exceptions if needed. `Startup-on.bat` creates a normal shortcut in your Startup folder. |
| Windows firewall question about Left 4 Dead 2 | The game's console listens on port 27015 (TCP). It is password-protected by step 2. Answering "Cancel" is fine: the program connects locally. |

### Uninstall

1. Double-click `Startup-off.bat` if you turned on the start with Windows.
2. In Steam, remove `-netconport 27015 -netconpassword … -g15` from the game's launch options.
3. Delete the folder, and `%LOCALAPPDATA%\L4D2RPC` (the log and your survival best times).

Nothing was ever written to the game folder or to Steam.

## What the card shows

- **Line 1**: campaign and chapter with the game's own names (`1/5 Highway`, `Finale: Atrium`), or "In the main
  menu". During a chapter change it already shows the next chapter.
- **Line 2**: a strong state while it lasts — 💀 dead, 🩸 incapacitated, ⏸️ paused (solo), 🦯 just revived,
  🚪 safe room, 🔥 Tank alive, 🔁 retry, 👀 spectating, 🧟 playing a special infected, 💤 idle — otherwise it
  rotates every 20 s between your health and weapon (with ammo: clip/reserve), the specials alive, and the team
  (online only).
- **Big image**: the campaign poster; tooltip: difficulty, attempt number, "online".
- **Small image**: your survivor's portrait (found by elimination: the three bots are known, so you are the fourth)
  or the special infected you play in Versus.
- **Timer**: since the start of the campaign (kept across chapters), or as set in `timer`.
- **Online**: "(2 of 4)" next to line 2.
- Sending pace: an important change (map, strong state) reaches Discord within 5 s, health and ammo at most every
  15 s (Discord drops updates that come too fast).

Never shown: other players' names, server names or addresses, Steam IDs, your position.

## How it works (and why not another way)

Left 4 Dead 2 is protected by **VAC**, Valve's anti-cheat. So: no mod, no DLL, no memory reading.

1. The Source engine has an official **network console**: started with `-netconport 27015`, the game accepts
   console commands over a local TCP connection and sends back everything it prints in its console.
   `-netconpassword` locks it with a password (without it, anyone on your network could type commands in your
   game). The program reads both from Steam's own settings file, so you never type the password twice.
2. The console prints, by itself, when a game starts (`Host_NewGame on map c2m1_highway`), when the next chapter
   loads (`---- Host_Changelevel ----`), when you are in (`#Cstrike_TitlesTXT_Game_connected`), when you die
   (`Player: … - Damage Given`) and when you leave. The program reacts at once.
3. Every 2 s in game it asks two **read-only** commands:
   - `g15_dumpplayer` (an old feature for Logitech G15 keyboard screens, enabled by `-g15`): your health, team,
     weapon class, clip, reserve ammo, and a tick counter that stops when the game is paused.
   - `status` (every other time): the map, the players and the bots — bots named after survivors give your
     character, bots named after specials are the specials alive (the Tank included).
4. Names (campaigns, chapters, difficulties, weapons) come from the game's own files (`tools/build_data.py`).
5. The card goes to the Discord desktop app through its local pipe (IPC), with Discord's official
   "Left 4 Dead 2" application ID.

Why not…
- **a mod or VScript add-on**: against the no-mod rule, and VScript only runs when you host the game.
- **reading memory**: VAC.
- **screen OCR**: heavy, and the console already gives more.
- **`-condebug` (console.log)**: the same text, but without being able to ask anything.
- **Steam's own rich presence**: not readable from outside for this account (tested).

Measured on the PC: see `FINDINGS.md` (every line format above comes from a real recording).

## Configuration (`config.json`, optional)

Created on first run from `config.example.json`. Every key is optional; a wrong value is reported in the log and
replaced by its default.

| Key | Default | Role |
|---|---|---|
| `client_id` | `"356954277803065354"` | Discord application. The default is Discord's own Left 4 Dead 2 app (one card, no duplicate). |
| `language` | `"en"` | `"en"`, `"fr"`, or `"auto"` (French if the game is in French, else English). |
| `status_display` | `"name"` | What the member list shows next to your name: `"name"` (Left 4 Dead 2), `"state"` (line 2) or `"details"` (line 1). |
| `timer` | `"campaign"` | `"campaign"` (kept across chapters), `"chapter"`, `"session"` (since the game started), `"none"`. |
| `emoji` | `true` | Emoji markers (❤️ 🔫 🧟 💀…). |
| `images` | `true` | Poster and survivor images. |
| `character_images` | your 8 guns.lol portraits | Survivor portraits by name (`"Coach": "https://…"`). A survivor missing here uses the game's HUD portrait from the wiki. |
| `cover_image` | your guns.lol link | Image used in the menu and when a map has no poster (`https://`, ≤256 characters). `""` = Steam's art. |
| `buttons` | `[]` | Up to 2 `{"label": "…", "url": "https://…"}` (label ≤32 characters). You cannot see your own buttons. |
| `state_rotation` | `["vitals", "specials", "vitals", "team", "record"]` | Order of line 2 when nothing urgent happens. Items without anything to say are skipped. |
| `rotate_seconds` | `20` | Seconds per rotation step (5 minimum). |
| `idle_minutes` | `5` | Minutes without keyboard/mouse before 💤 Idle (`0` = never). |
| `show_health` | `true` | Health on line 2. |
| `show_weapon` | `true` | Weapon in hand. |
| `show_ammo` | `true` | Clip/reserve after the weapon. |
| `show_specials` | `true` | Specials alive and the Tank alert. |
| `show_team` | `true` | "2 players + 2 bots" online (never in solo). |
| `show_character` | `true` | Your survivor's image. |
| `show_difficulty` | `true` | Difficulty in the poster tooltip. |
| `show_attempts` | `true` | 🔁 Retry and "attempt n". |
| `show_records` | `true` | Survival best times (🏆). |
| `show_online` | `true` | "(2 of 4)" and "online". |
| `show_pause` | `true` | ⏸️ Paused. |
| `show_idle` | `true` | 💤 Idle. |
| `card_owner` | `"companion"` | Process Discord ties the card to: `"companion"` (this program) or `"game"`. |
| `netcon_host` | `"127.0.0.1"` | Where the game's console is (this PC). |
| `netcon_port` | `0` | `0` = read `-netconport` from Steam. |
| `netcon_password` | `""` | `""` = read `-netconpassword` from Steam. |
| `poll_seconds` | `2` | Seconds between two reads of health/weapon in game (1–10). |

## Tools

| Command | What it does |
|---|---|
| `L4D2RPC.bat` | Runs with a console (log on screen). Ctrl+C or closing the window removes the card. |
| `L4D2RPC-silent.bat` | Runs without a window (`pythonw`). |
| `Setup.bat` | Prints and copies the launch options with a new password. |
| `Doctor.bat` | Checks Python, Discord, the game, the launch options and the console. |
| `Startup-on.bat` / `Startup-off.bat` | Start (or not) silently with Windows (a shortcut in `shell:startup`). |
| `L4D2RPC.bat --dry-run` | Computes the card without sending it. |
| `L4D2RPC.bat --simulate` | A fake game through every situation, on your real profile (add `--dry-run` to only print). |
| `L4D2RPC.bat --dump` | Raw console answer and state read from the running game. |
| `L4D2RPC.bat -v` | Logs every console line and event. |
| `python tools/build_data.py [--images]` | Rebuilds the name tables from the game files (and the image links from the Left 4 Dead Wiki). |
| `python tools/extract_portraits.py` | Saves the 8 portraits of the "Survivor Better Materials" workshop preview to `assets/portraits/` (to host them yourself). |
| `python tools/vtf.py <vpk> <file.vtf> <out.png>` | Converts one of the game's textures to PNG. |
| `python tools/netcon_probe.py` | Records the game console (reconnaissance). |
| `python tools/analyze_netcon.py <recording>` | Turns a recording into a readable timeline. |
| `python -m unittest discover -s tests` | Tests (on anonymised real recordings, with a fake Discord). |

## Limits

- **Game mode**: only **Survival** is recognised (from lines printed when its map loads). Campaign, Realism and
  Scavenge cannot be told apart: the game does not expose the mode to its client console. Versus shows when you
  play infected.
- **Survival timer**: the game prints nothing when the round starts; the card starts its timer at the first special
  infected or the first damage, a few seconds after the real start.
- **Survival best times** are the program's own: the game's records (and medals) cannot be read from outside —
  Steam's stats have no per-map survival time and L4D2's leaderboards are not public. Every round played while the
  program runs is measured (detected start → your death in solo, or → your death / the next round online) and the
  best per map is kept in `%LOCALAPPDATA%\L4D2RPC\survival_records.json`. Being measured from the detected
  start, they can be a few seconds shorter than the game's. Records made before installing it are unknown.
- **Temporary health** (pills, adrenaline) is not in the dump: only permanent health is shown.
- **Melee weapon type** (katana, bat…) is not in the dump: "Melee weapon".
- **The Witch** is not a player, so `status` does not list her.
- **Your character** is only known when the other three survivors are bots.
- **"Last life"** is deduced (two revives without a first-aid kit, the game's default rule); starting the program
  mid-game loses the count.
- **Pause** only exists in solo; in online games the game never pauses.
- **Online games, Versus, Scavenge and finales**: built from the same console lines but not yet tested on the PC.
- **VAC**: `-netconport`, `-netconpassword` and `-g15` are engine launch options and the commands are read-only;
  no ban was ever reported for them, but Valve has not said anything about them either.

## Licences

MIT (see `LICENSE`). Discord IPC client and fake Discord adapted from *FL Studio Better Presence*, process helpers
from *Dead by Daylight Better Presence* (same author, MIT).

Fan project, not affiliated with Valve. Left 4 Dead 2 names come from the game's files; campaign posters and
special infected images are hot-linked from the [Left 4 Dead Wiki](https://left4dead.fandom.com) (CC BY-SA) and
Steam. The default survivor portraits come from the preview of the Steam Workshop item
[Survivor Better Materials](https://steamcommunity.com/sharedfiles/filedetails/?id=2968256804) (art by its authors),
hosted by Sam for personal use; they are not part of this repository.
