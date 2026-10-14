"""Survival mode on a real (anonymised) recording: Dead Center "Gun Shop" round, death, next round, then a new
Survival game on "Concert" left before starting the timer."""

import unittest

from helpers import Replay, stamp

from l4d2_rpc.config import DEFAULTS
from l4d2_rpc.presence import build_activity


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
        self.assertEqual(card["state"], "💀 Dead — the round goes on")
        s = self.r.until("18:52:39")
        self.assertEqual(s.attempt, 2)
        self.assertIsNone(s.round_start)
        card, _ = build_activity(s, dict(DEFAULTS), stamp("18:52:39"))
        self.assertEqual(card["state"], "🔁 Round #2")
        s = self.r.until("18:53:20")
        self.assertIsNotNone(s.round_start)  # a Boomer appeared: the second round is on
        card, _ = build_activity(s, dict(DEFAULTS), stamp("18:53:20"))
        self.assertEqual(card["assets"]["large_text"], "Dead Center · round 2")


if __name__ == "__main__":
    unittest.main()
