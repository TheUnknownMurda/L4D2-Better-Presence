"""The game state, rebuilt from console events. Pure: the caller passes the time.

Rules come from the recordings in FINDINGS.md:
- `Host_NewGame on map X` starts a game from the menu, `---- Host_Changelevel ----` moves to the next chapter,
  `#Cstrike_TitlesTXT_Game_connected` means the player is in, the menu video or `Dropped … (…)` means back to menu.
- `g15_dumpplayer`: health above 100 while a survivor = incapacitated (297 → 1 once revived), `deadflag` = dead,
  `m_nTickBase` unchanged between two dumps = the (single-player) game is paused.
- `status`: bots named after survivors give the player's character by elimination; bots named after special
  infected are the specials alive right now (the Tank included).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import data
from .parser import Event

L4D2_SET = ["Coach", "Ellis", "Nick", "Rochelle"]
L4D1_SET = ["Bill", "Zoey", "Francis", "Louis"]
TEAM_SPECTATOR, TEAM_SURVIVOR, TEAM_INFECTED = 1, 2, 3
INCAP_HEALTH_FLOOR = 100  # a survivor's health never goes above 100 unless incapacitated (then ~300)
SAFE_ROOM_SECONDS = 30  # the "safe room reached" state lasts until the next chapter loads, at most this long
RETRY_MIN_SECONDS = 15  # a director restart this soon after a chapter start is part of the load, not a retry
DUMP_STALE_SECONDS = 12  # without a fresh dump, health/weapon are no longer shown
PAUSE_MIN_GAP = 1.5  # two dumps this far apart with the same tick count = paused
MAX_INCAPS = 2  # default survivor_max_incapacitated_count: the next one after 2 revives is death
RESULTS_SCREEN_SECONDS = 9  # Survival: death -> next round's "Initializing Director's script" (measured 9 s)


@dataclass
class GameState:
    phase: str = "closed"  # closed | menu | loading | ingame
    map: str | None = None
    mode: str | None = None  # "survival" when recognised, else unknown (campaign, realism…)
    round_start: float | None = None  # Survival: when the round was seen starting
    round_end: float | None = None  # Survival: when the round ended (solo: the player's death)
    last_round: float | None = None  # Survival: length of the round that just ended, seconds
    last_round_record: bool = False  # …and whether it beat the best time
    survival_best: float | None = None  # Survival: best time on this map (set by the app from its records)
    remote: bool = False  # on another computer's server (online)
    listen_server: bool = False  # this computer hosts the game (solo or local lobby)
    difficulty: str | None = None  # Easy | Normal | Hard | Impossible
    game_language: str | None = None
    player_name: str | None = None
    humans: int | None = None
    max_players: int | None = None
    survivor_bots: list[str] = field(default_factory=list)
    specials_alive: list[str] = field(default_factory=list)
    character: str | None = None
    team: int | None = None
    health: int | None = None
    dead: bool = False
    incapacitated: bool = False
    revives: int = 0  # incaps survived since the last first-aid kit (heuristic, see FINDINGS.md)
    weapon_class: str | None = None
    clip: int | None = None
    reserve: int | None = None
    reloading: bool = False
    paused: bool = False
    safe_room_since: float | None = None
    retry_since: float | None = None
    revived_since: float | None = None
    attempt: int = 1
    session_start: float | None = None  # game process start
    campaign_start: float | None = None
    chapter_start: float | None = None
    last_campaign: int | None = None
    last_dump: float | None = None
    last_tick: int | None = None
    last_tick_time: float | None = None

    # -------- derived
    @property
    def map_info(self):
        return data.map_info(self.map)

    @property
    def campaign(self) -> int | None:
        info = self.map_info
        return info.campaign if info else None

    @property
    def survival(self) -> bool:
        return self.mode == "survival"

    @property
    def round_waiting(self) -> bool:
        """Survival: in the map, the timer not started yet (no special infected, no damage so far)."""
        return self.survival and self.phase == "ingame" and self.round_start is None

    @property
    def tank(self) -> bool:
        return "Tank" in self.specials_alive

    @property
    def last_life(self) -> bool:
        return (self.team == TEAM_SURVIVOR and not self.dead and not self.incapacitated
                and self.revives >= MAX_INCAPS)

    @property
    def solo(self) -> bool:
        return self.listen_server and not self.remote and (self.humans or 1) <= 1

    def vitals_fresh(self, now: float) -> bool:
        return self.last_dump is not None and now - self.last_dump <= DUMP_STALE_SECONDS


class Tracker:
    """Applies events to a GameState."""

    def __init__(self, session_start: float | None = None):
        self.state = GameState(session_start=session_start)
        self._chapter_dumps = 0
        self._death_time: float | None = None
        self.finished_rounds: list[tuple[str, float, float]] = []  # (map, seconds, end time) for the app to save

    # ------------------------------------------------------------------ lifecycle
    def game_started(self, session_start: float, now: float) -> None:
        s = self.state
        s.session_start = session_start
        if s.phase == "closed":
            s.phase = "menu"

    def game_closed(self) -> None:
        self.state = GameState()
        self._chapter_dumps = 0

    # ------------------------------------------------------------------ events
    def apply(self, ev: Event, now: float) -> None:
        handler = getattr(self, f"_on_{ev.kind}", None)
        if handler:
            handler(ev.data, now)

    def tick(self, now: float) -> None:
        s = self.state
        if s.safe_room_since is not None and now - s.safe_room_since > SAFE_ROOM_SECONDS:
            s.safe_room_since = None
        if s.phase == "ingame" and not s.vitals_fresh(now):
            s.paused = False

    # ------------------------------------------------------------------ handlers
    def _reset_vitals(self) -> None:
        s = self.state
        s.health = None
        s.dead = False
        s.incapacitated = False
        s.weapon_class = None
        s.clip = None
        s.reserve = None
        s.reloading = False
        s.paused = False
        s.team = None
        s.last_dump = None
        s.last_tick = None
        s.last_tick_time = None
        s.specials_alive = []
        s.safe_room_since = None
        s.retry_since = None
        s.revived_since = None

    def _start_chapter(self, map_name: str | None, now: float, new_game: bool) -> None:
        s = self.state
        previous_campaign = s.campaign
        if map_name:
            s.map = map_name
        s.phase = "loading"
        s.chapter_start = now
        s.attempt = 1
        s.mode = None
        self._reset_round()
        self._chapter_dumps = 0
        self._reset_vitals()
        if new_game or s.campaign_start is None or (s.campaign and s.campaign != previous_campaign):
            s.campaign_start = now
            s.revives = 0
            s.character = None

    def _on_new_game(self, d: dict, now: float) -> None:
        s = self.state
        s.listen_server = True
        s.remote = False
        self._start_chapter(d["map"], now, new_game=True)

    def _on_changelevel(self, d: dict, now: float) -> None:
        # The next map's name only comes with `Map: …` once loaded: meanwhile, show the next chapter
        self._start_chapter(data.next_map(self.state.map), now, new_game=False)

    def _on_connecting(self, d: dict, now: float) -> None:
        s = self.state
        if d.get("remote"):
            # Joining someone else's server from the menu: a new game for us
            s.remote = True
            s.listen_server = False
            if s.phase in ("menu", "closed"):
                s.phase = "loading"
                s.campaign_start = None

    def _on_server_map(self, d: dict, now: float) -> None:
        """`Map: X`, printed once the map is loaded, before the player is in."""
        s = self.state
        if s.phase in ("menu", "closed"):
            self._start_chapter(d["map"], now, new_game=True)
        elif s.map != d["map"]:
            self._start_chapter(d["map"], now, new_game=False)
        s.phase = "loading"

    def _on_server_players(self, d: dict, now: float) -> None:
        self.state.max_players = d.get("max") or self.state.max_players

    def _on_connected(self, d: dict, now: float) -> None:
        s = self.state
        if s.map:
            s.phase = "ingame"

    def _back_to_menu(self) -> None:
        s = self.state
        if s.campaign:
            s.last_campaign = s.campaign
        session = s.session_start
        last = s.last_campaign
        name, difficulty, language = s.player_name, s.difficulty, s.game_language
        self.state = GameState(phase="menu", session_start=session, last_campaign=last, player_name=name,
                               difficulty=difficulty, game_language=language)
        self._chapter_dumps = 0

    def _on_dropped(self, d: dict, now: float) -> None:
        s = self.state
        # Only our own disconnection matters (other players leaving print the same line on a server)
        if s.player_name is None or d.get("name") == s.player_name:
            self._back_to_menu()

    def _on_disconnect(self, d: dict, now: float) -> None:
        self._back_to_menu()

    def _on_menu(self, d: dict, now: float) -> None:
        if self.state.phase != "closed":
            self._back_to_menu()

    def _on_damage_report(self, d: dict, now: float) -> None:
        s = self.state
        if s.phase == "ingame" and (s.player_name is None or d.get("player") == s.player_name):
            if s.team == TEAM_SURVIVOR or s.team is None:
                if not s.dead:
                    self._died(now)
                s.dead = True
                s.incapacitated = False

    def _on_director_init(self, d: dict, now: float) -> None:
        s = self.state
        # Seen when a chapter restarts after the team died (solo: when the player died)
        if s.retry_since is not None and now - s.retry_since < RETRY_MIN_SECONDS:
            return  # the director prints this line twice per restart
        if s.phase == "ingame" and s.chapter_start is not None and now - s.chapter_start > RETRY_MIN_SECONDS:
            s.attempt += 1
            s.retry_since = now
            s.revived_since = None
            if s.survival and s.round_start is not None and s.round_end is None:
                # Not finished at our death (others alive, or we were incapacitated): it ended before this restart
                end = self._death_time or now - RESULTS_SCREEN_SECONDS
                self._finish_round(max(end, s.round_start), now)
            self._reset_round()
            s.dead = False
            s.incapacitated = False
            s.revives = 0
            s.safe_room_since = None
            s.specials_alive = []

    def _on_safe_room(self, d: dict, now: float) -> None:
        s = self.state
        if s.phase == "ingame" and s.safe_room_since is None:
            s.safe_room_since = now

    def _reset_round(self) -> None:
        s = self.state
        s.round_start = None
        s.round_end = None
        s.last_round = None
        s.last_round_record = False
        self._death_time = None

    def _finish_round(self, end: float, now: float) -> None:
        s = self.state
        s.round_end = end
        s.last_round = end - s.round_start
        if s.map:
            self.finished_rounds.append((s.map, s.last_round, end))

    def _died(self, now: float) -> None:
        """The local player just died."""
        s = self.state
        self._death_time = now
        if s.survival and s.round_start is not None and s.round_end is None and s.solo:
            self._finish_round(now, now)  # alone with bots, the round ends with us

    def _on_survival(self, d: dict, now: float) -> None:
        if self.state.phase in ("loading", "ingame"):
            self.state.mode = "survival"

    def _survival_started(self, now: float) -> None:
        """No infected spawn before a Survival round starts: the first special or the first damage marks it.
        It is seen a few seconds after the real start (the game prints nothing at that moment)."""
        s = self.state
        if s.survival and s.phase == "ingame" and s.round_start is None and not s.dead:
            s.round_start = now

    def _on_cvar(self, d: dict, now: float) -> None:
        s = self.state
        name, value = d["name"], d["value"]
        if name == "z_difficulty" and value:
            s.difficulty = value.capitalize()
        elif name == "name" and value:
            s.player_name = value
        elif name == "cl_language" and value:
            s.game_language = value.lower()

    def _on_status(self, d: dict, now: float) -> None:
        s = self.state
        rows = d.get("rows") or []
        if not d.get("map"):
            return
        if s.phase in ("menu", "closed"):
            # The companion started (or reconnected) while a map was already running
            self._start_chapter(d["map"], now, new_game=True)
            s.phase = "ingame"
        s.listen_server = bool(d.get("local"))
        if s.listen_server:
            s.remote = False
        if d.get("max"):
            s.max_players = d["max"]
        humans = [r for r in rows if not r["bot"]]
        bots = [r["name"] for r in rows if r["bot"]]
        s.humans = len(humans) if rows else d.get("humans")
        specials = set(data.special_infected())
        s.specials_alive = sorted({b for b in bots if b in specials}, key=data.special_infected().index)
        if s.specials_alive:
            self._survival_started(now)
        s.survivor_bots = [b for b in bots if b in L4D2_SET or b in L4D1_SET]
        s.character = self._guess_character(s, humans)

    @staticmethod
    def _guess_character(s: GameState, humans: list[dict]) -> str | None:
        if s.team not in (None, TEAM_SURVIVOR) or len(humans) != 1:
            return None
        bots = set(s.survivor_bots)
        for team_set in (L4D2_SET, L4D1_SET):
            if bots and bots <= set(team_set) and len(bots) == len(team_set) - 1:
                return (set(team_set) - bots).pop()
        return None

    def _on_dump(self, d: dict, now: float) -> None:
        s = self.state
        player = d.get("player") or {}
        if s.phase != "ingame":
            # A dump with a living player means we are in a map (companion started mid-game)
            if s.map and player.get("m_iTeamNum") in (TEAM_SURVIVOR, TEAM_INFECTED) and s.phase == "loading":
                s.phase = "ingame"
            else:
                return
        team = player.get("m_iTeamNum")
        if team not in (TEAM_SPECTATOR, TEAM_SURVIVOR, TEAM_INFECTED):
            return  # team 0 right after connecting: not spawned yet (seen with deadflag true and 0 HP)
        health = player.get("m_iHealth")
        dead = bool(player.get("deadflag"))
        s.team = team
        was_incap = s.incapacitated
        previous_health = s.health
        incap = (team == TEAM_SURVIVOR and not dead and health is not None and health > INCAP_HEALTH_FLOOR)
        if was_incap and not incap and not dead:
            s.revives += 1
            s.revived_since = now
        if (not incap and not was_incap and previous_health is not None and health is not None
                and health > previous_health and not s.dead):
            s.revives = 0  # health only goes up with a first-aid kit
        if (health is not None and previous_health is not None and health < previous_health and not dead
                and team == TEAM_SURVIVOR):
            self._survival_started(now)
        s.incapacitated = incap
        if dead and not s.dead:
            self._died(now)
        s.dead = dead
        if dead or incap:
            s.revived_since = None
        if dead:
            s.revives = 0
        s.health = health
        s.weapon_class = d.get("weapon_class")
        weapon = d.get("weapon") or {}
        s.clip = weapon.get("m_iClip1")
        ammo_type = weapon.get("m_iPrimaryAmmoType")
        s.reserve = (d.get("ammo") or {}).get(ammo_type) if isinstance(ammo_type, int) and ammo_type >= 0 else None
        s.reloading = bool(weapon.get("m_bInReload"))
        tick = player.get("m_nTickBase")
        if tick is not None and s.last_tick is not None and tick == s.last_tick and s.last_tick_time is not None:
            s.paused = now - s.last_tick_time >= PAUSE_MIN_GAP
        else:
            s.paused = False
            s.last_tick_time = now
        s.last_tick = tick
        s.last_dump = now
        self._chapter_dumps += 1
        if s.dead is False and s.retry_since is not None and now - s.retry_since > 20:
            s.retry_since = None
