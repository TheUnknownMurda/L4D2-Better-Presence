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

## À mesurer en jeu (non vérifié)

- La console réseau répond-elle sur `127.0.0.1:27015` (TCP) ? Sur quelle interface écoute-t-elle
  (`netstat -ano | findstr 27015`) ? Mot de passe exigé ?
- Ce que la console affiche pendant une partie (chargement de carte, transitions, mort, fin).
- Commandes de lecture utiles sans triche : `status`, `mp_gamemode`, `z_difficulty`, `host_map`,
  `net_showevents` (événements de jeu reçus par le client).
- Titre de la fenêtre et ligne de commande du processus.
