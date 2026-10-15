"""The parser and the state tracker on real (anonymised) console recordings of two solo games."""

import unittest

from helpers import Replay, stamp

from l4d2_rpc.config import DEFAULTS
from l4d2_rpc.presence import build_activity


class NewGameChangelevelMenu(unittest.TestCase):
    """Session 1: Dead Center, Easy. New game, in game, safe room, next chapter, back to the menu."""

    def setUp(self):
        self.r = Replay("solo_newgame_changelevel_menu.log")

    def test_story(self):
        s = self.r.until("17:18:02")
        self.assertEqual(s.phase, "loading")
        self.assertEqual(s.map, "c1m1_hotel")
        self.assertTrue(s.listen_server)
        self.assertFalse(s.remote)

        s = self.r.until("17:18:14")
        self.assertEqual(s.phase, "ingame")
        self.assertEqual(s.difficulty, "Easy")

        s = self.r.until("17:19:46")
        self.assertEqual(s.character, "Ellis")  # bots were Nick, Coach and Rochelle
        self.assertIn("Jockey", s.specials_alive)
        self.assertEqual(s.humans, 1)

        s = self.r.until("17:24:31")
        self.assertIsNotNone(s.safe_room_since)

        s = self.r.until("17:24:40")
        self.assertEqual(s.phase, "loading")
        self.assertEqual(s.map, "c1m2_streets")  # predicted from the campaign's chapter order
        self.assertIsNone(s.safe_room_since)

        s = self.r.until("17:24:57")
        self.assertEqual(s.phase, "ingame")
        self.assertEqual(s.map, "c1m2_streets")
        self.assertEqual(s.campaign_start, stamp("17:18:01.580"))  # the campaign timer kept running

        s = self.r.until("17:25:19")
        self.assertEqual(s.phase, "menu")
        self.assertEqual(s.last_campaign, 1)

    def test_cards(self):
        self.r.until("17:19:46")
        card, _ = build_activity(self.r.tracker.state, dict(DEFAULTS), stamp("17:19:46"))
        self.assertEqual(card["details"], "Dead Center · Hotel · Easy")
        self.assertEqual(card["assets"]["small_text"], "Ellis")
        self.assertEqual(card["assets"]["large_text"], "Left 4 Dead 2")
        self.assertEqual(card["timestamps"]["start"], int(stamp("17:18:01.580")))
        self.r.until("17:25:19")
        card, _ = build_activity(self.r.tracker.state, dict(DEFAULTS), stamp("17:25:19"))
        self.assertEqual(card["details"], "In the main menu")
        self.assertEqual(card["state"], "Last game: Dead Center")


class SoloVitals(unittest.TestCase):
    """Session 2: Dark Carnival, Easy, -g15. Weapons, pause, incap, revive, death, restart, menu."""

    def setUp(self):
        self.r = Replay("solo_vitals.log")

    def test_first_dump(self):
        # In this recording the first dump came before the first status; the real program asks for status first
        s = self.r.until("17:30:57")
        self.assertEqual(s.phase, "ingame")  # synced from status (companion started mid-game)
        self.assertEqual(s.map, "c2m1_highway")
        self.assertEqual(s.character, "Rochelle")
        self.assertEqual(s.health, 100)
        self.assertEqual(s.weapon_class, "CShotgun_Chrome")
        self.assertEqual((s.clip, s.reserve), (5, 72))
        self.assertEqual(s.team, 2)
        card, _ = build_activity(s, dict(DEFAULTS, state_rotation=["vitals"]), stamp("17:30:57"))
        self.assertEqual(card["state"], "❤️ 100 HP · 🔫 Chrome Shotgun 5/72")

    def test_pause(self):
        s = self.r.until("17:31:22")
        self.assertFalse(s.paused)
        s = self.r.until("17:31:26")
        self.assertTrue(s.paused)  # m_nTickBase stuck at 3310
        card, key = build_activity(s, dict(DEFAULTS), stamp("17:31:26"))
        self.assertEqual(card["state"], "⏸️ Paused")

    def test_incap_and_revive(self):
        s = self.r.until("17:33:35")
        self.assertTrue(s.incapacitated)
        self.assertEqual(s.weapon_class, "CPistol")
        card, _ = build_activity(s, dict(DEFAULTS), stamp("17:33:35"))
        self.assertEqual(card["state"], "🩸 Incapacitated — needs help!")
        s = self.r.until("17:33:43")
        self.assertFalse(s.incapacitated)
        self.assertEqual(s.health, 1)
        self.assertEqual(s.revives, 1)
        card, _ = build_activity(s, dict(DEFAULTS), stamp("17:33:43"))
        self.assertEqual(card["state"], "🦯 Revived — limping, 1 HP")  # under 30 HP

    def test_death_retry_menu(self):
        s = self.r.until("17:37:48")
        self.assertTrue(s.dead)  # "Player: … - Damage Given" printed at death
        card, _ = build_activity(s, dict(DEFAULTS), stamp("17:37:48"))
        self.assertEqual(card["state"], "💀 Dead")  # solo
        s = self.r.until("17:37:56")
        self.assertFalse(s.dead)
        self.assertEqual(s.attempt, 2)
        self.assertEqual(s.health, 100)
        card, _ = build_activity(s, dict(DEFAULTS), stamp("17:37:56"))
        self.assertEqual(card["state"], "🔁 Retry #2")
        self.assertEqual(card["assets"]["large_text"], "Attempt 2")
        s = self.r.until("17:38:08")
        self.assertEqual(s.phase, "menu")
        self.assertEqual(s.last_campaign, 2)

    def test_no_secrets_in_cards(self):
        """Steam IDs, addresses and the player's own name never reach the card."""
        cfg = dict(DEFAULTS)
        for hms in ("17:30:55", "17:31:26", "17:33:35", "17:36:12", "17:37:48", "17:38:08"):
            s = self.r.until(hms)
            card, _ = build_activity(s, cfg, stamp(hms))
            text = repr(card)
            for secret in ("STEAM_", "192.0.2", "loopback", "Player"):
                self.assertNotIn(secret, text, hms)


if __name__ == "__main__":
    unittest.main()
