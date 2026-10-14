# Résultats de la reconnaissance — Left 4 Dead 2

Chaque entrée : date, ce qui a été mesuré, la preuve (commande ou fichier).
« Non vérifié » = pas encore mesuré sur le PC de Sam.

## Installation (vérifié sur le PC le 2026-10-14)

| Info | Valeur | Preuve |
|---|---|---|
| Boutique | Steam, appid `550` | `steamapps/appmanifest_550.acf` |
| Dossier | `C:\Program Files (x86)\Steam\steamapps\common\Left 4 Dead 2` | idem, `installdir` |
| Exécutable | `left4dead2.exe` (racine du dossier) | `ls` du dossier |
| Version | `PatchVersion=2.2.4.3`, `NetworkVersion=2.1.0.0`, buildid `23990068` | `left4dead2/steam.inf`, manifeste |
| Moteur | Source (branche L4D2), 32 bits, `bin/engine.dll`, `bin/vscript.dll`, rendu `shaderapivk.dll`/`dxvk_d3d9.dll` présents | `ls bin` |
| Langue du jeu | `french` | manifeste (`UserConfig.language`), registre `HKCU\Software\Valve\Steam\Language` |
| Compte Steam | `<SteamID64>` (dossier `userdata/<account id>`) | manifeste `LastOwner` |
| Options de lancement | **`-netconport 27015`** (déjà présentes, origine inconnue) | `userdata/<account id>/config/localconfig.vdf`, bloc `550` |
| Addons actifs | `mwrmovement.vpk` (mod Melty « Modern Warfare 4 Dead »), workshop `2646883501`, `278735311` | `left4dead2/addonlist.txt` |
| Fichiers écrits en jouant | `cfg/config.cfg` (réglages), `save/game_instructor_counts.txt`, `serverconfig.vdf` (`z_difficulty "normal"`), `ems/mwrmove/*` (écrits par le mod Melty) | dates de modification du 2026-10-09 |
| Anti-triche | VAC (multijoueur Valve) — **aucune injection, aucun mod client, aucune lecture mémoire** | règle du projet |

Pas de `console.log` (l'option `-condebug` n'est pas active), pas d'`autoexec.cfg`.

## Discord (vérifié le 2026-10-14)

`GET https://discord.com/api/v9/applications/detectable` (12,9 Mo, HTTP 200) :

- **Left 4 Dead 2** : ID d'application `356954277803065354`, exécutables
  `left 4 dead 2/left4dead2.exe` et `left4dead2.exe` (arguments `-game left4dead2`),
  `bin/l4d2_workshop_manager.exe`, SKU Steam `550`, `hook: true`, `overlay: true`.
- Left 4 Dead (1) : `425749516583698432`, `left4dead.exe`.

Discord installé : **Discord Canary** (`%LOCALAPPDATA%\DiscordCanary\app-1.0.1228`), application de bureau, donc l'IPC local est disponible.

Rich Presence native de L4D2 dans Discord : non vérifié (lancer le jeu et regarder le profil).

## Noms officiels dans les fichiers du jeu (vérifié le 2026-10-14)

Lus en lecture seule avec `tools/vpk.py` :

- Campagnes et chapitres : `update/pak01_dir.vpk` → `missions/campaign1.txt` … `campaign14.txt`
  (`DisplayTitle "#L4D360UI_CampaignName_C1"`, puis par mode `coop`/`versus`/`survival`/`scavenge`…
  `Map "c1m1_hotel"`, `DisplayName "#L4D360UI_LevelName_COOP_C1M1"`).
- Textes : `left4dead2/pak01_dir.vpk` → `resource/l4d360ui_<langue>.txt` (C1 à C5) et fichiers
  libres `update/resource/l4d360ui_tu_<langue>.txt` (toutes les campagnes, dont C7–C14).
- Exemples FR : `L4D360UI_CampaignName_C1` = « Centre de la mort », `C2` = « Lugubre carnaval »,
  `L4D360UI_LevelName_COOP_C1M1` = « 1: Hôtel », difficultés « Facile / Normal / Avancé / Expert »,
  modes « Campagne / Réalisme / Survie / Versus / Collecte ».

## Processus et fenêtre (vérifié le 2026-10-14, jeu au menu)

- Ligne de commande : `"…\Left 4 Dead 2\left4dead2.exe" -steam -netconport 27015`
  (`Get-CimInstance Win32_Process -Filter "Name='left4dead2.exe'"`).
- Titre de fenêtre : `Left 4 Dead 2 - Direct3D 9` (identique au menu et en jeu : inutile).

## Console réseau `-netconport` (vérifié le 2026-10-14, session 1)

Preuve : `recordings/session1.log` (non versionné), sonde `tools/netcon_probe.py`.

- Écoute **TCP sur `0.0.0.0:27015`** (toutes les interfaces), PID du jeu (`netstat -ano`).
  Le pare-feu Windows a deux règles « Left 4 Dead 2 » qui autorisent TCP et UDP, tous ports,
  profils Domaine/Privé/**Public**. Sans `-netconpassword`, **n'importe qui sur le réseau local
  peut envoyer des commandes au jeu**. → mot de passe obligatoire.
- Pas de mot de passe demandé (option absente). Texte brut, une commande par ligne `\n`.
- Plusieurs connexions simultanées acceptées ; **chaque connexion reçoit toute la sortie de la
  console**, y compris les réponses aux commandes des autres connexions.
- `version` → `Version 2.2.4.3 (left4dead2)`, `Exe build: 11:44:59 Jun 30 2026 (10097) (550)`.

### Commandes et variables (au menu puis en solo)

| Commande | Résultat | Utilité |
|---|---|---|
| `z_difficulty` | `"z_difficulty" = "Easy" ( def. "Normal" )`, drapeaux `client replicated` | difficulté ✅ |
| `host_map` | `"host_map" = "c1m1_hotel.bsp"` en jeu ; `""` avant la 1re partie ; **reste à l'ancienne carte après retour au menu** | carte (avec les lignes de connexion) |
| `status` | rien au menu ; en jeu : `map : c1m1_hotel at ( 2301, 6862, 2718 )`, `players : 1 humans, 0 bots (4 max)`, liste `# 6 1 "Sam" STEAM_1:… active … loopback`, puis `# 7 "Nick" BOT active`… **et les infectés spéciaux en vie** : `#10 "Charger" BOT active`, `#11 "Spitter" BOT active`, `#12 "Jockey" BOT active` | personnage (par élimination en solo), infectés présents, nombre de joueurs. Contient position, SteamID, pseudos → vie privée |
| `mp_gamemode` | `Unknown command "mp_gamemode"` (menu) / `Unknown command: mp_gamemode` (en jeu) | ❌ mode illisible ainsi |
| `sv_gametypes` | `""` (variable serveur) | ❌ |
| `cl_language` | `"french"` | langue du jeu ✅ |
| `net_showevents`, `con_logfile` | `Unknown command` | ❌ |
| `cl_showevents` | existe mais drapeau `cheat` | ❌ |
| `kill` | `Can't use cheat command kill in multiplayer, unless the server has sv_cheats set to 1.` | (c'est une triche en L4D2) |
| `g15_dumpplayer` | `Must run with -g15 to enable support for the LCD Keyboard` (drapeau `client`, pas `cheat`) | à tester avec `-g15` |

### Lignes écrites par la console pendant la partie

| Moment | Ligne(s) exacte(s) |
|---|---|
| Lancement d'une partie locale | `---- Host_NewGame ----` puis `Host_NewGame on map c1m1_hotel` |
| Connexion terminée (carte chargée) | `Left 4 Dead 2` / `Map: c1m1_hotel` / `Players: 1 (0 bots) / 4 humans` / `Build: 10097` / `Server Number: 2` |
| Partie locale | `   VAC secure mode disabled.` ; `Sending UDP connect to public IP 127.0.0.1:27015` |
| Entrée en jeu | `#Cstrike_TitlesTXT_Game_connected` |
| Fin de chapitre (porte de la pièce sécurisée) | `Saving weapon_…` (×10) puis `---- Host_Changelevel ----` puis le bloc `Map: c1m2_streets` |
| Tir allié | `Sam attacked Nick` |
| Retour au menu | `BinkOpen( …\media\l4d2_background05.bik )` puis `Dropped Sam from server (Server shutting down)` |
| Réglages | `Host_WriteConfiguration: Wrote cfg/config.cfg` |

Délai : la ligne `Map:` arrive ~10 s après `Host_NewGame` (chargement). Événements reçus
instantanément (TCP).

Rien n'est écrit pour : la pause (Échap), l'arrivée d'un infecté spécial, le mode de jeu.
Mort / mise à terre : pas encore observées.

### Addons qui écrivent dans la console

Le mod Melty « MW Movement » (VScript, côté serveur local) écrit `[MWRMove] 0.1.0 running` et
`[MW Movement] …`. Preuve qu'un script VScript d'addon peut écrire dans la console, lisible par
netcon — mais uniquement quand le serveur est local (solo / partie hébergée).

## `-netconpassword` et `-g15` (vérifié le 2026-10-14, session 2)

Options de lancement réglées par Sam : `-netconport 27015 -netconpassword <16 hex> -g15`.
Ligne de commande relevée : `… left4dead2.exe -steam -netconport 27015 -netconpassword … -g15`.

- Sans mot de passe : `This server is password protected for console access. Must send PASS command`.
  Avec `PASS <mot de passe>` en première ligne : tout fonctionne.
- `-g15` ne provoque aucune erreur visible (pas de `g15.dll`, le jeu tourne normalement).
- **`g15_dumpplayer`** (drapeau `client`, pas `cheat`) écrit ~300 lignes en 7 ms : sections
  `(localplayer)` (`C_TerrorPlayer::…`), `(localteam)`, `(playerresource)`,
  `(localplayerweapon)` (classe de l'arme en main, ex. `CShotgun_Chrome::…`), puis `Other replacements:`.
  Format d'une ligne : `C_TerrorPlayer::m_iHealth integer (100)`.

Preuve : `recordings/session2.log` (relevé `g15_dumpplayer;status;z_difficulty` toutes les 2 s,
208 relevés), chronologie `python tools/analyze_netcon.py recordings/session2.log`.
Partie solo, « Lugubre carnaval » (`c2m1_highway`), Facile.

### Ce que donne le relevé

| Info | Champ | Valeurs observées |
|---|---|---|
| Santé | `C_TerrorPlayer::m_iHealth` | 100 → 99 → 81 … 15 ; soin trousse → 80 |
| **À terre** | `m_iHealth` > 100 et arme = `CPistol` | 297, 291, 288… (saigne), puis `m_iHealth=1` + `m_flMaxspeed=150` une fois relevé |
| Santé temporaire (pilules, relevé) | absente du relevé | ❌ (seulement `m_iHealth`) |
| Boiter | `m_flMaxspeed` | 220 normal, 150 blessé, 75 accroupi, 115 (avec `m_fFlags=641`, cause non identifiée) |
| **Mort** | `deadflag` | `true`, `m_flMaxspeed=900`, `m_iHideHUD=2056` |
| Équipe | `m_iTeamNum` | 2 = survivants (3 = infectés, non observé) |
| **Arme en main** | classe de `(localplayerweapon)` | `CShotgun_Chrome`, `CSubMachinegun`, `CPistol`, `CTerrorMeleeWeapon` (sans le type de mêlée), `CChainsaw`, `CMolotov`, `CItem_VomitJar`, `CFirstAidKit`, `CPainPills`, `CItem_Adrenaline`, `CItemUpgradePackExplosive` |
| Chargeur | `m_iClip1` | 8 (pompe), 50 (SMG), 15 (pistolet), -1 (objets) ; tronçonneuse = carburant 30 |
| Réserve | `C_TerrorPlayer::m_iAmmo[m_iPrimaryAmmoType]` | 72 (type 7, fusil à pompe), 650 → 412 (type 5, SMG) |
| Rechargement | `m_bInReload` | `true` / `false` |
| **Pause (solo)** | `m_nTickBase` figé entre deux relevés | 3310 de 17:31:21 à 17:31:48 ; 14387 de 17:37:59 à 17:38:04 (Échap puis retour menu) |
| Personnage | `m_nModelIndex` = 185 | dépend de la carte : inutilisable seul |

`status` (même relevé) : `hostname: Sam` en solo ; liste des bots survivants
(`Coach`, `Nick`, `Ellis` → Sam joue Rochelle, par élimination) et **infectés spéciaux en vie** :
`Charger`, `Spitter`, `Jockey`, `Hunter`, `Smoker`, `Boomer`, **`Tank`** (17:33:54 → 17:35:15).
La Witch n'apparaît pas (ce n'est pas un joueur).

### Lignes de console nouvelles (session 2)

| Moment | Ligne(s) |
|---|---|
| Mort du joueur | `Player: Sam - Damage Given` / `-------------------------` / `Damage Given to "Tank" - 700 in 3 hits` … / `Player: Sam - Damage Taken` / `Damage Taken from "Charger" - 40 in 3 hits` … |
| Redémarrage du chapitre (mort en solo) | `Initializing Director's script` puis nouveau rapport `Damage Given to "Sam" - 0 in 1 hit` ; santé 100 + `CPistol` |
| Directeur (serveur local seulement) | `Initiating Ambush`, `Initiating Reserved Wanderers` |
| Tir allié | `Sam attacked Ellis`, `Sam attacked Coach` |
| Retour au menu | `BinkOpen( …\media\l4d2_background01.bik )` puis `Dropped Sam from server (Server shutting down)` |
| Jeu fermé | la connexion TCP est coupée (`WinError 10054`), aucune ligne |

### Mode de jeu : illisible directement

`mp_gamemode` → `Unknown command`, `find mode` ne liste aucune variable de mode lisible.
Pistes : `status` → `players : … (4 max)` (Campagne/Réalisme/Survie) contre `(8 max)`
(Versus/Collecte, non vérifié) ; `m_iTeamNum = 3` → Versus/Collecte côté infectés (non vérifié).

## Steam (vérifié le 2026-10-14)

- `https://steamcommunity.com/miniprofile/<account id>/json` (en jeu) ne renvoie **pas** de bloc
  `in_game` (seulement `playtime`) : rich presence Steam illisible ainsi pour ce compte.
- Le jeu n'a pas de Game State Integration (aucune chaîne `gamestate_integration` dans les DLL,
  recherche du 2026-10-14).

## À mesurer (non vérifié)

- Partie en ligne (serveur distant) : lignes `Connected to …`, `status`, `g15_dumpplayer` ?
- Versus / Collecte / Survie / Réalisme : `(8 max)`, équipe 3, classe d'arme des infectés.
- Finale, sauvetage, fin de campagne (générique).
- Coût CPU du relevé toutes les 2 s (jeu et compagnon).
- VAC : aucun rapport de bannissement trouvé pour `-netconport`/`-g15` (options du moteur),
  mais pas de déclaration officielle de Valve.
