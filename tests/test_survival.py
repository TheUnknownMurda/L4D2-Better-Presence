"""Survival mode on a real (anonymised) recording: Dead Center "Gun Shop" round, death, next round, then a new
Survival game on "Concert" left before starting the timer."""

import unittest

from helpers import Replay, stamp

from l4d2_rpc.config import DEFAULTS
from l4d2_rpc.parser import ConsoleParser
from l4d2_rpc.presence import build_activity
from l4d2_rpc.records import SurvivalRecords, clock, parse_manual, parse_time
from l4d2_rpc.simulate import dump_lines, status_lines
from l4d2_rpc.state import Tracker


class SurvivalRecording(unittest.TestCase):
    def setUp(self):
        self.r = Replay("survival.log")

    def test_new_survival_game_waits_for_the_round(self):
        self.r.until("18:54:02")
        self.assertEqual(self.r.tracker.state.phase, "menu")
        s = self.r.until("18:54:23")
        self.assertEqual(s.map, "c2m5_concert")
        self.assertEqual(s.mode, "survival")  # "survival_start_explain_template" while loading
        s = self.r.until("18:54:31")
        self.assertEqual(s.phase, "ingame")
        self.assertTrue(s.round_waiting)  # "Unknown command: survival_record", no special yet
        s = self.r.until("18:54:34")  # first dump with the player spawned (the one before had team 0)
        card, _ = build_activity(s, dict(DEFAULTS), stamp("18:54:34"))
        self.assertEqual(card["details"], "Survival · Concert")
        self.assertEqual(card["state"], "⏱️ Waiting to start the round")
        self.assertNotIn("timestamps", card)  # no timer before the round starts
        self.assertEqual(card["assets"]["large_text"], "Dark Carnival")
        s = self.r.until("18:54:55")
        self.assertEqual(s.phase, "menu")
        self.assertIsNone(s.mode)

    def test_round_start_death_and_next_round(self):
        # The recording started mid-game: tell the tracker it is a Survival map, as the load lines would have
        s = self.r.until("18:50:46")
        s.mode = "survival"
        s = self.r.until("18:51:04")
        self.assertTrue(s.round_waiting)
        s = self.r.until("18:51:06")
        self.assertAlmostEqual(s.round_start, stamp("18:51:05.442"), delta=0.1)  # first damage (100 -> 52 HP)
        card, _ = build_activity(s, dict(DEFAULTS), stamp("18:51:06"))
        self.assertEqual(card["timestamps"]["start"], int(s.round_start))
        self.assertEqual(card["details"], "Survival · Gun Shop")
        s = self.r.until("18:52:30")
        self.assertTrue(s.dead)
        card, _ = build_activity(s, dict(DEFAULTS), stamp("18:52:30"))
        # Solo: the round ends with the player (18:51:05 -> 18:52:29)
        self.assertEqual(card["state"], "💀 Round over — 1:23")
        self.assertNotIn("timestamps", card)
        [(map_name, seconds, _end)] = self.r.tracker.finished_rounds
        self.assertEqual(map_name, "c1m2_streets")
        self.assertAlmostEqual(seconds, 83.8, delta=0.2)
        s = self.r.until("18:52:39")
        self.assertEqual(s.attempt, 2)
        self.assertIsNone(s.round_start)
        card, _ = build_activity(s, dict(DEFAULTS), stamp("18:52:39"))
        self.assertEqual(card["state"], "🔁 Round #2")
        s = self.r.until("18:53:20")
        self.assertIsNotNone(s.round_start)  # a Boomer appeared: the second round is on
        card, _ = build_activity(s, dict(DEFAULTS), stamp("18:53:20"))
        self.assertEqual(card["assets"]["large_text"], "Dead Center · round 2")


class LoadingCard(unittest.TestCase):
    """Sam: a Survival load showed the campaign's chapter ("Dead Center · Streets") until the game was in."""

    def test_survival_load_does_not_name_the_campaign_chapter(self):
        parser, tracker = ConsoleParser(), Tracker()
        t = 1000.0
        tracker.game_started(t, t)

        def feed(lines, when):
            for line in lines:
                for ev in parser.feed(line):
                    tracker.apply(ev, when)

        feed(['"z_difficulty" = "Normal"', "---- Host_NewGame ----", "Host_NewGame on map c1m2_streets"], t)
        self.assertIsNone(tracker.state.difficulty)  # the old difficulty is not shown while the new game loads
        card, _ = build_activity(tracker.state, dict(DEFAULTS), t + 1)
        self.assertEqual((card["details"], card["state"]), ("Dead Center", "⏳ Loading…"))
        feed(["Map: c1m2_streets", "#Cstrike_TitlesTXT_Game_connected"], t + 15)
        card, _ = build_activity(tracker.state, dict(DEFAULTS), t + 15)
        self.assertEqual((card["details"], card["state"]), ("Dead Center", "⏳ Loading…"))
        feed(["Unknown command: survival_record"] + status_lines("c1m2_streets", bots=("Ellis", "Rochelle", "Coach"))
             + dump_lines(health=100, tick=5), t + 16)
        card, _ = build_activity(tracker.state, dict(DEFAULTS), t + 16)
        self.assertEqual(card["details"], "Survival · Gun Shop")

    def test_campaign_load_shows_the_chapter_once_in(self):
        parser, tracker = ConsoleParser(), Tracker()
        t = 1000.0
        tracker.game_started(t, t)
        for line in ["Host_NewGame on map c1m2_streets", "Map: c1m2_streets", "#Cstrike_TitlesTXT_Game_connected",
                     '"z_difficulty" = "Hard"'] + dump_lines(health=100, tick=5):
            for ev in parser.feed(line):
                tracker.apply(ev, t)
        card, _ = build_activity(tracker.state, dict(DEFAULTS), t + 2)
        self.assertEqual(card["details"], "Dead Center · Streets · Advanced")


class BestTimes(unittest.TestCase):
    def feed(self, tracker, parser, lines, t):
        for line in lines:
            for ev in parser.feed(line):
                tracker.apply(ev, t)

    def start_survival(self, humans=None):
        parser, tracker = ConsoleParser(), Tracker()
        t = 1000.0
        tracker.game_started(t, t)
        self.feed(tracker, parser, ["Host_NewGame on map c1m2_streets",
                                    "Precache called on a point_template that has no templates: "
                                    "survival_start_explain_template", "Map: c1m2_streets",
                                    "#Cstrike_TitlesTXT_Game_connected", "Unknown command: survival_record"]
                  + status_lines("c1m2_streets", humans=humans, bots=("Ellis", "Rochelle", "Coach"))
                  + dump_lines(health=100, tick=1), t)
        return parser, tracker

    def test_rotation_and_waiting_line_show_the_best(self):
        parser, tracker = self.start_survival()
        s = tracker.state
        s.survival_best = 201.0
        cfg = dict(DEFAULTS, state_rotation=["record"])
        card, _ = build_activity(s, cfg, 1001)
        self.assertEqual(card["state"], "⏱️ Waiting to start the round · best 3:21")
        self.feed(tracker, parser, status_lines("c1m2_streets", bots=("Ellis", "Rochelle", "Coach", "Hunter"))
                  + dump_lines(health=90, tick=50), 1010)
        self.assertEqual(s.round_start, 1010)
        card, _ = build_activity(s, cfg, 1100)
        self.assertEqual(card["state"], "🏆 Best here: 3:21")
        self.feed(tracker, parser, dump_lines(health=90, tick=900), 1300)
        card, _ = build_activity(s, cfg, 1300)
        self.assertEqual(card["state"], "🏆 Beating the best (3:21)!")

    def test_team_round_ends_at_restart(self):
        """Online, our death does not end the round: it is closed by the next round's restart."""
        parser, tracker = self.start_survival(humans=[("Sam", "loopback"), ("Friend", "198.51.100.3:27005")])
        self.feed(tracker, parser, status_lines("c1m2_streets", humans=[("Sam", "loopback"),
                                                                        ("Friend", "198.51.100.3:27005")],
                                                bots=("Ellis", "Rochelle", "Hunter")), 1010)
        self.feed(tracker, parser, dump_lines(health=0, dead=True, tick=500), 1100)
        card, _ = build_activity(tracker.state, dict(DEFAULTS), 1101)
        self.assertEqual(card["state"], "💀 Dead — the round goes on")
        self.assertEqual(tracker.finished_rounds, [])
        self.feed(tracker, parser, ["Initializing Director's script"], 1200)
        [(_, seconds, _)] = tracker.finished_rounds
        self.assertEqual(seconds, 90)  # our death, not the restart

    def test_records_typed_from_the_game_menu(self):
        parsed, bad = parse_manual({"Gun Shop": "4:32", "L'armerie": "3:00", "c2m5_concert": "1:02:05",
                                    "Port": "5:00", "Nowhere": "1:00", "Mall Atrium": "soon"})
        self.assertEqual(parsed, {"c1m2_streets": 272.0, "c2m5_concert": 3725.0})  # the best of two names kept
        self.assertEqual(sorted(bad), ["Mall Atrium", "Nowhere", "Port"])  # "Port" is two maps: use the code
        self.assertEqual(parse_time("0:59"), 59)
        self.assertIsNone(parse_time("1:75"))

    def test_typed_record_raises_the_bar(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            r = SurvivalRecords(Path(d) / "survival_records.json")
            self.assertFalse(r.add("c1m2_streets", 200, 1_791_000_000, floor=272))  # better than ours, not the game's
            self.assertTrue(r.add("c1m2_streets", 300, 1_791_000_100, floor=272))

    def test_records_file(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "survival_records.json"
            r = SurvivalRecords(path)
            self.assertIsNone(r.best("c1m2_streets"))
            self.assertTrue(r.add("c1m2_streets", 83.8, 1_791_000_000))
            self.assertFalse(r.add("c1m2_streets", 60, 1_791_000_100))
            self.assertTrue(SurvivalRecords(path).add("C1M2_STREETS", 201.4, 1_791_000_200))
            again = SurvivalRecords(path)
            self.assertEqual(again.best("c1m2_streets"), 201.4)
            self.assertEqual(again.data["c1m2_streets"]["rounds"], 3)
        self.assertEqual(clock(201.4), "3:21")
        self.assertEqual(clock(3725), "1:02:05")


if __name__ == "__main__":
    unittest.main()
