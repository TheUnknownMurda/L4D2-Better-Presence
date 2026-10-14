# Findings — Left 4 Dead 2

What was measured, when, and the proof (command, file or recording). "Not verified" = not measured on Sam's PC yet.
Raw recordings live in `recordings/` (not versioned); anonymised cuts are in `tests/fixtures/`
(`python tools/make_fixtures.py`).

## Install (verified on the PC, 2026-10-14)

| Item | Value | Proof |
|---|---|---|
| Store | Steam, appid `550` | `steamapps/appmanifest_550.acf` |
| Folder | `C:\Program Files (x86)\Steam\steamapps\common\Left 4 Dead 2` | manifest `installdir` |
| Executable | `left4dead2.exe` (folder root) | `ls` |
| Version | `PatchVersion=2.2.4.3`, `NetworkVersion=2.1.0.0`, buildid `23990068`, `Exe build: 11:44:59 Jun 30 2026 (10097)` | `left4dead2/steam.inf`, manifest, console `version` |
| Engine | Source (L4D2 branch), 32-bit, `bin/engine.dll`, `bin/vscript.dll` | `ls bin` |
| Game language | `french` | manifest `UserConfig.language`, registry `HKCU\Software\Valve\Steam\Language`, cvar `cl_language` |
| Steam account | `userdata/<account id>` | manifest `LastOwner` |
| Anti-cheat | VAC (Valve multiplayer) → no injection, no client mod, no memory reading | project rule |
| Add-ons | `mwrmovement.vpk` (Melty mod "Modern Warfare 4 Dead", VScript), workshop `2646883501`, `278735311` | `left4dead2/addonlist.txt` |
| Files written while playing | `cfg/config.cfg`, `save/game_instructor_counts.txt`, `serverconfig.vdf` (`z_difficulty "normal"`) | timestamps |

Launch options found at the start: `-netconport 27015` (origin unknown). No `console.log`, no `autoexec.cfg`.

## Discord (verified 2026-10-14)

`GET https://discord.com/api/v9/applications/detectable` (12.9 MB, HTTP 200):
- **Left 4 Dead 2**: application `356954277803065354`, executables `left 4 dead 2/left4dead2.exe` and
  `left4dead2.exe` (arguments `-game left4dead2`), `bin/l4d2_workshop_manager.exe`, Steam SKU `550`.
- Left 4 Dead (1): `425749516583698432`.
- No native Rich Presence for L4D2 (no `rpc_origins`); no L4D2 Rich Presence project found on GitHub.

Discord on the PC: **Discord Canary** desktop app (`%LOCALAPPDATA%\DiscordCanary\app-1.0.1228`), pipe
`\\.\pipe\discord-ipc-0`. The account seen through the pipe changed during the session ("account A" at 18:05,
"account B" from 18:09): Canary's account switcher; the card goes to the active account.

## Process and window (verified 2026-10-14)

- Command line: `"…\left4dead2.exe" -steam -netconport 27015 -netconpassword … -g15`.
- Window title: `Left 4 Dead 2 - Direct3D 9` in menu and in game (useless).
- The console port accepts connections ~50 s after the process starts (log 18:09:23 → 18:10:16).

## Network console `-netconport` (verified 2026-10-14)

Proof: `recordings/session1.log`, probe `tools/netcon_probe.py`.

- Listens on **TCP `0.0.0.0:27015`** (all interfaces, `netstat -ano`). The Windows firewall has two "Left 4 Dead 2"
  rules allowing TCP and UDP, all ports, Domain/Private/**Public**. Without `-netconpassword` **anyone on the local
  network can type commands in the game** → the password is mandatory.
- With `-netconpassword X`: without `PASS X` the console answers
  `This server is password protected for console access. Must send PASS command`; after `PASS X` everything works.
- Plain text, one command per line; several clients at once; **every client receives all console output**.
- When the game exits the TCP connection is reset (`WinError 10054`), no line is printed.

### Commands and variables

| Command | Answer | Use |
|---|---|---|
| `z_difficulty` | `"z_difficulty" = "Easy" ( def. "Normal" )`, flags `client replicated` | difficulty ✅ |
| `host_map` | `"host_map" = "c1m1_hotel.bsp"`; `""` before the first game; **keeps the old map after going back to the menu** | not used |
| `status` | nothing in the menu; in game: `hostname: Sam`, `os : Windows Listen`, `map : c2m1_highway at ( x, y, z )`, `players : 1 humans, 0 bots (4 max)`, rows `#  2 1 "Sam" STEAM_1:… loopback`, `# 3 "Coach" BOT active` … and **specials alive**: `#10 "Charger" BOT active` | character by elimination, specials, players (contains IDs and positions → never shown) |
| `name`, `cl_language` | `"name" = "Sam"`, `"cl_language" = "french"` | own name (to recognise own lines), language ✅ |
| `mp_gamemode` | `Unknown command "mp_gamemode"` (menu) / `Unknown command: mp_gamemode` (in game) | ❌ mode unreadable |
| `find mode` | no readable mode variable | ❌ |
| `sv_gametypes` | `""` | ❌ |
| `net_showevents`, `con_logfile` | `Unknown command` | ❌ |
| `cl_showevents` | exists, flag `cheat` | ❌ |
| `kill` | `Can't use cheat command kill in multiplayer, unless the server has sv_cheats set to 1.` | (cheat) |
| `g15_dumpplayer` | without `-g15`: `Must run with -g15 to enable support for the LCD Keyboard` (flag `client`, not `cheat`) | see below |

### Lines the console prints by itself

| Moment | Exact line(s) |
|---|---|
| Local game started from the menu | `---- Host_NewGame ----`, `Host_NewGame on map c1m1_hotel` |
| Map loaded | `Left 4 Dead 2` / `Map: c1m1_hotel` / `Players: 1 (0 bots) / 4 humans` / `Build: 10097` / `Server Number: 2` |
| Local game | `   VAC secure mode disabled.`, `Sending UDP connect to public IP 127.0.0.1:27015` |
| Player in | `#Cstrike_TitlesTXT_Game_connected` (also after each chapter change) |
| Safe room door closed | `Saving weapon_…` (×10), ~9 s before `---- Host_Changelevel ----` |
| Next chapter | `---- Host_Changelevel ----`, then the `Map: c1m2_streets` block, then `#Cstrike_TitlesTXT_Game_connected` |
| Friendly fire | `Sam attacked Nick` |
| Local player died | `Player: Sam - Damage Given` / `-------------------------` / `Damage Given to "Tank" - 700 in 3 hits` … / `Player: Sam - Damage Taken` … |
| Chapter restarts after a wipe (solo: after the player died) | `Initializing Director's script` ×2 (also printed during every map load), then `Damage Given to "Sam" - 0 in 1 hit` |
| Director (local server only) | `Initiating Ambush`, `Initiating Reserved Wanderers` |
| Back to the menu | `BinkOpen( …\media\l4d2_background05.bik )` then `Dropped Sam from server (Server shutting down)` |
| Settings saved | `Host_WriteConfiguration: Wrote cfg/config.cfg` |

Nothing is printed for: pause, special infected spawning, game mode. Loading takes ~10 s between `Host_NewGame`
and `Map:` (c1m1), ~12 s for a chapter change.

Add-on VScripts print to the same console (`[MWRMove] 0.1.0 running`, `[MW Movement] …`), but only when the
server is local.

## `-netconpassword` and `-g15` (verified 2026-10-14, session 2)

Launch options set by Sam: `-netconport 27015 -netconpassword <16 hex> -g15`. `-g15` causes no error
(no `g15.dll` shipped, the game runs normally).

**`g15_dumpplayer`** prints ~300 lines in ~7 ms: sections `(localplayer)` (`C_TerrorPlayer::…`), `(localteam)`,
`(playerresource)`, `(localplayerweapon)` (weapon class, e.g. `CShotgun_Chrome::…`), then `Other replacements:`.
Line format: `C_TerrorPlayer::m_iHealth integer (100)`. **char fields are printed as raw bytes**:
`m_MoveType\x02`, and after death `m_lifeState\x01` followed by binary garbage (the parser drops control
characters and ignores what follows a field name; found by the tests on the real recording).

Proof: `recordings/session2.log` (`g15_dumpplayer;status;z_difficulty` every 2 s, 208 dumps), timeline
`python tools/analyze_netcon.py recordings/session2.log`. Solo, Dark Carnival (`c2m1_highway`), Easy.

| Info | Field | Values seen |
|---|---|---|
| Health | `m_iHealth` | 100 → 99 → 81 … 15; first-aid kit → 80 |
| **Incapacitated** | `m_iHealth` > 100 and weapon `CPistol` | 297, 291, 288… (bleeding), then `m_iHealth=1` + `m_flMaxspeed=150` once revived |
| Temporary health | absent | ❌ |
| Speed | `m_flMaxspeed` | 220 normal, 150 hurt, 75 crouched, 115 (with `m_fFlags=641`, cause unknown), 900 dead |
| **Dead** | `deadflag` | `true`, `m_iHideHUD=2056` |
| Team | `m_iTeamNum` | 2 survivors (3 infected, 1 spectator: not seen) |
| **Weapon in hand** | class of `(localplayerweapon)` | `CShotgun_Chrome`, `CSubMachinegun`, `CPistol` (dual: clip 30), `CTerrorMeleeWeapon` (type not given), `CChainsaw`, `CMolotov`, `CItem_VomitJar`, `CFirstAidKit`, `CPainPills`, `CItem_Adrenaline`, `CItemUpgradePackExplosive`, `CPumpShotgun` |
| Clip | `m_iClip1` | 8 pump, 50 SMG, 15 pistol, -1 items; chainsaw = fuel 30 |
| Reserve | `C_TerrorPlayer::m_iAmmo[m_iPrimaryAmmoType]` | 72 (type 7), 650 → 412 (type 5) |
| Reloading | `m_bInReload` | true/false |
| **Pause (solo)** | `m_nTickBase` unchanged between dumps | 3310 from 17:31:21 to 17:31:48; 14387 from 17:37:59 to 17:38:04 |
| Character | `m_nModelIndex` = 185 | map-dependent: unusable |

All weapon client classes (43, incl. infected claws `CTankClaw`, `CHunterClaw`…) were read from
`left4dead2/bin/client.dll` (file on disk, not memory).

## Names (verified 2026-10-14, `tools/build_data.py`)

- Chapters: `update/pak01_dir.vpk` → `missions/campaign1.txt` … `campaign14.txt` (`modes/coop/<n>/Map`,
  `DisplayName "#L4D360UI_LevelName_COOP_C1M1"`). 14 campaigns, 57 maps.
- Strings: `left4dead2/pak01_dir.vpk` → `resource/l4d360ui_<lang>.txt`, `resource/left4dead2_<lang>.txt`, and the
  loose `update/resource/l4d360ui_tu_<lang>.txt` (campaigns 6–14). FR examples: "Centre de la mort", "1: Hôtel",
  difficulties Facile/Normal/Avancé/Expert (EN Easy/Normal/Advanced/Expert).
- Weapons: the game only names the L4D1 weapons (`L4D_Weapon_*`) and melee types. Other English names are the
  Left 4 Dead Wiki page titles (all checked through its API on 2026-10-14, except "Fireworks Crate" which has no
  page); other French names are the project's.
- Images (`--images`): Left 4 Dead Wiki page images (`prop=pageimages`) for 14 campaigns and 16 characters, Steam
  `library_600x900.jpg`/`header.jpg`; each link checked HTTP 200. Cover image: Sam's own link
  (`images.guns.lol/…/R7kq6VUsjDtVC7alNkrjk.png`, PNG, 790 KB, HTTP 200, 90 characters).

## Survival mode (verified 2026-10-14, `recordings/survival_session.log`, fixture `tests/fixtures/survival.log`)

Solo Survival on "Gun Shop" (`c1m2_streets`), one round, death, a second round, back to the menu, then a new
Survival game on "Concert" (`c2m5_concert`) left before starting the timer.

- **The mode is recognisable at load**, by two lines:
  - while the map loads (local server): `Couldn't find any entities named survival_start_explain, which
    point_template survival_start_explain_template is specifying.` and `Precache called on a point_template that
    has no templates: survival_start_explain_template`;
  - right after `#Cstrike_TitlesTXT_Game_connected`: `Unknown command: survival_record` (a command the server sends
    to the client; expected on remote servers too — not verified).
- `z_difficulty` reads `"normal"` (lower case) in Survival.
- **Nothing is printed when the round's timer starts** (no console line, no change in `g15_dumpplayer`'s
  player/team/resource fields). Before the start no infected spawn, so the first special in `status` or the first
  damage marks it: round 1 → first damage 18:51:05 (100 → 52 HP), specials at 18:51:09; round 2 → Boomer at
  18:53:19. The real start is a few seconds earlier: the card's round timer can be a little short.
- Death: same `Player: … - Damage Given` report; the round restarts ~9 s later with `Initializing Director's script`
  ×2 (counted as round 2). No survival time or medal is printed.
- First `g15_dumpplayer` right after connecting: `m_iTeamNum 0`, `m_iHealth 0`, `deadflag true` (not spawned yet):
  ignored, otherwise the card showed "Dead" in the new game (found by the tests).
- Survival map names come from `missions/campaignN.txt` → `modes/survival` (`#L4D360UI_LevelName_SURVIVAL_C1M2` =
  "Gun Shop" / "L'armerie"); 43 maps.

### Survival best times: not readable from outside (verified 2026-10-14)

- `Steam/appcache/stats/UserGameStatsSchema_550.bin` (459 KB): 682 `Stat.*` names; per-map stats exist only for
  Scavenge (`Stat.TotalTime.Scavenge.c1m4_atrium`…); for Survival only `Stat.SurvivalGamesPlayed.Total`. No best
  time, no medal per map.
- `https://steamcommunity.com/stats/L4D2/leaderboards/?xml=1` → `No public global leaderboards available`.
- The mission files' `x360leaderboard`/`besttime` blocks are for the Xbox 360 version.
→ The companion keeps its own: round length = detected start → local death (solo: the round ends with the player:
death 18:52:29, restart 18:52:38) or → local death / restart − 9 s online (not verified online). Saved in
`%LOCALAPPDATA%\L4D2RPC\survival_records.json`.

## Survivor portraits (verified 2026-10-14)

Sam asked for the portraits of a screen recording (a Steam Workshop page, "Survivor Better Materials",
id 2968256804). Findings:
- The game's own HUD portraits are `materials/vgui/s_panel_<internal>.vtf` (`update/pak01_dir.vpk`), internal names
  coach, mechanic (Ellis), gambler (Nick), producer (Rochelle), namvet (Bill), teenangst (Zoey), biker (Francis),
  manager (Louis); plus `_incap` variants and `s_panel_dead.vtf`. Decoded with `tools/vtf.py`: the four L4D2
  survivors are front-facing and identical to the recording; **the four L4D1 survivors are side profiles**.
- The wiki hosts the same files (`File:S_panel_coach.png` … 128x128).
- The front-facing L4D1 portraits only exist in the workshop preview: a 512x512 GIF, 8 frames of 1 s, order Ellis,
  Rochelle, Coach, Nick, Louis, Zoey, Francis, Bill (`images.steamusercontent.com/ugc/2216394743367178406/…`).
  `tools/extract_portraits.py` saves them; Sam hosted the 8 PNGs on guns.lol. Each of the 8 links answered HTTP 200
  (PNG 512x512) and matched its local frame exactly (mean grey difference 0.0). They are the defaults of
  `character_images`.

## Steam (verified 2026-10-14)

- `https://steamcommunity.com/miniprofile/<account id>/json` in game: **no** `in_game` block (only `playtime`).
- No Game State Integration (no `gamestate_integration` string in the DLLs).
- Launch options are in `userdata/<account>/config/localconfig.vdf` →
  `UserLocalConfigStore/Software/Valve/Steam/apps/550/LaunchOptions`; parsing the 137 KB file takes 44 ms.
  Active account: `HKCU\Software\Valve\Steam\ActiveProcess\ActiveUser`.

## Real runs of the companion (2026-10-14, `%LOCALAPPDATA%\L4D2RPC\l4d2rpc.log`, copy in `recordings/companion_run1.log`)

Solo, No Mercy then Dead Center, Discord Canary. Event → `Card sent` delay from the log:

| Situation | Event | Card sent |
|---|---|---|
| Menu | game detected 18:09:23 | 18:09:26 |
| Paused | — | 18:16:54 (`⏸️ Paused`) |
| Incapacitated / revived / dead / retry #2, #3 | — | 18:17:43, 18:17:48, 18:18:04, 18:18:09 |
| Tank | — | 18:18:38 |
| Safe room → next chapter | 18:21:16 `Loading c8m2_subway` | 18:21:11 safe room, 18:21:17 `2/5 The Subway · ⏳ Loading…` |
| Back to menu | 18:22:00 | 18:22:00 |
| New game (cover known) | 18:26:52.800 `Loading c1m1_hotel` | 18:26:52.812 |

**Discord sometimes does not answer `SET_ACTIVITY` within 5 s**: 18:16:25 and 18:22:17 (first card of a newly
loaded campaign), 18:25:38 (first card with the new cover image), 18:30:59 (in game). The first client copied from
FL Studio disconnected on that timeout, so the "Loading…" card of a new game was lost (Sam saw nothing during the
load). Fix: a reply that does not start within 5 s no longer drops the connection (`NoReply`). Cause not
identified: likely Discord fetching a new external image before answering (3 of 4 cases), and the card is tied to
the companion's PID instead of the game's (`card_owner`) in case Discord waits on the busy game process.

Later the same evening (log 19:09–19:16):
- Survival seen on Sam's profile (screenshot: "Survival · Street", "🔥 TANK! · 💖 100 HP · Assault Rifle 42/312",
  Death Toll poster, Louis portrait, timer 0:49): one single card with `card_owner: companion`.
- Survival round on Gun Shop: `Survival round on c1m2_streets: 2:14 (new best).` → card
  `💀 Round over — 2:14 · 🏆 new best!`, then `🔁 Round #2`, then `⏱️ Waiting to start the round · best 2:14`;
  `survival_records.json` written.
- Loading a Survival map first shows the campaign card (`Dead Center · Streets | ⏳ Loading…`) for ~18 s: the
  Survival lines only arrive with the end of the load.
- Game closed at 19:16: console lost 19:16:34, `Game closed: clearing the card.` 19:16:36 (log; not confirmed on
  the profile).
- CPU: companion 0.45 s of CPU over 60 s in game = **0.76 % of one core**, 26 MB of memory (PowerShell
  `TotalProcessorTime`, 18:35).

Still to verify on the PC: reconnection after a Discord restart, card gone from the profile after closing the game
(seen only in the log), online games, Versus, finale/rescue, buttons (needs a 2nd account).
