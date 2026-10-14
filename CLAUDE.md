# L4D2 Better Presence — Rich Presence Discord pour Left 4 Dead 2

Brief du projet. Si la session est coupée : lis ce fichier, puis `FINDINGS.md`, et continue
là où « État actuel » s'arrête. Le cahier des charges complet est `../_Prompt Better Presence.md`.

## Comment travailler avec moi

- Je suis Sam. Je ne suis pas développeur : je code avec toi. Explique simplement, un terme
  technique = une demi-phrase d'explication.
- Windows 11, antivirus Bitdefender. Commandes exactes, prêtes à copier, en disant où les taper.
- Lance toi-même sondes, tests et vraie connexion à Discord. Quand une mesure demande une action
  de ma part (lancer le jeu, changer de chapitre, mourir…), dis exactement quoi faire, attends ma
  confirmation, puis mesure.
- Demande avant tout ce qui est risqué : toucher au dossier du jeu, aux options de lancement Steam,
  au registre, installer un outil global, supprimer des fichiers.
- Réponses en français. Code, commentaires, commits en anglais. README, console, carte en français.
- Rien d'inventé : ce qui n'est pas mesuré est marqué « non vérifié » avec le moyen de le vérifier.
  Distinguer : vérifié par les tests / vérifié sur le PC (carte vue dans Discord) / non testé.
- Un commit à chaque étape qui marche.

## Le jeu (vérifié le 2026-10-14, détails dans FINDINGS.md)

- Steam, appid 550, `C:\Program Files (x86)\Steam\steamapps\common\Left 4 Dead 2\left4dead2.exe`,
  version 2.2.4.3, moteur Source, langue française.
- **VAC** : aucune injection, aucun mod client, aucune lecture mémoire. Seulement : interfaces
  officielles du moteur (console), fichiers, infos Windows, écran.
- Discord : application officielle « Left 4 Dead 2 » `356954277803065354` (liste de détection).
- Options de lancement actuelles : `-netconport 27015` (console TCP du moteur).

## Stack

Python 3.13 (installé : `%LOCALAPPDATA%\Programs\Python\Python313`), bibliothèque
standard uniquement. Tests : `python -m unittest discover -s tests`. Pas de ruff/pyflakes installés :
`python -m compileall`.

## Architecture (prévue, à confirmer après la proposition)

- `l4d2_rpc/` : le programme (lecture de la source → état → carte → Discord).
- `tools/` : sondes (`netcon_probe.py`), lecteur VPK (`vpk.py`), génération des tables de noms.
- `data/` : noms officiels générés depuis les fichiers du jeu.
- `tests/` : unittest, faux Discord.

## Projets de référence (dossier parent, licence MIT)

- Client IPC Discord : `FL Studio Better Presence/src/flbp/discord_ipc.py` (le plus robuste :
  thread, délais, statut) + `pid` et `_finish()` de `Sons of the Forest Better Presence/sotf_rpc/`
  + règles de nettoyage de `MeltyRPC/src/discord/ipc.ts`.
- Lecture de journal : `Outlast Trials Better Presence/main.py` (suivi de fichier, rotation).
- Rotation de la ligne 2, cadence d'envoi 5 s / 15 s, verrou, journal : `Sons of the Forest Better Presence/sotf_rpc/`.
- Processus et fenêtre au premier plan : `Dead by Daylight Better Presence/dbd_rpc/game.py`.
- `doctor` : `Crash Bandicoot N.Sane Trilogy Better Presence/crash_presence/cli/diagnostics.py`.

## Règles techniques

Voir `../_Prompt Better Presence.md` (`<regles_discord>`, `<sources_de_donnees>`, `<pieges_connus>`).
Rappels : jamais d'écriture dans le jeu ni ses sauvegardes ; pas de séquence `\uXXXX` écrite
par les outils ; PowerShell lancé par le code sur une ligne, sans `-EncodedCommand`.

## État actuel — étape 1, reconnaissance (2026-10-14)

- Fait : installation repérée, application Discord officielle trouvée, noms officiels localisés
  dans les VPK, sondes `tools/vpk.py` et `tools/netcon_probe.py` écrites.
- En cours : mesures en jeu (console réseau, contenu de la console).
- Ensuite : proposition + maquette (étape 2), puis arrêt pour l'OK de Sam.
