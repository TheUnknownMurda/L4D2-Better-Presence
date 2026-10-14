"""State -> card: Discord's limits, every simulated situation, languages and options."""

import unittest

import helpers  # noqa: F401  (adds the project to sys.path)

from l4d2_rpc.config import DEFAULTS
from l4d2_rpc.parser import ConsoleParser
from l4d2_rpc.presence import PAD, _length, build_activity, truncate
from l4d2_rpc.simulate import dump_lines, scenario, status_lines
from l4d2_rpc.state import Tracker

T0 = 1_791_993_600.0


def run_scenario(cfg):
    parser, tracker = ConsoleParser(), Tracker()
    now = T0
    tracker.game_started(now - 60, now)
    cards = []
    for step in scenario():
        if step.process == "closed":
            tracker.game_closed()
        for line in step.lines:
            for ev in parser.feed(line):
                tracker.apply(ev, now)
        tracker.tick(now)
        cards.append((step.title, build_activity(tracker.state, cfg, now, step.idle)[0]))
        now += step.seconds
    return cards


def check_limits(test, card):
    if card is None:
        return
    for key in ("details", "state"):
        if key in card:
            test.assertTrue(2 <= _length(card[key]) <= 128, (key, card[key]))
    for key, value in card.get("assets", {}).items():
        if key.endswith("_text"):
            test.assertLessEqual(_length(value), 128)
        else:
            test.assertTrue(value.startswith("https://") and len(value) <= 256, value)
    for b in card.get("buttons", []):
        test.assertLessEqual(_length(b["label"]), 32)
        test.assertTrue(b["url"].startswith("https://"))
    test.assertLessEqual(len(card.get("buttons", [])), 2)
    if "timestamps" in card:
        test.assertIsInstance(card["timestamps"]["start"], int)
        test.assertLess(card["timestamps"]["start"], 10_000_000_000)  # seconds, not milliseconds


class Truncate(unittest.TestCase):
    def test_short_is_padded(self):
        self.assertEqual(truncate("a"), "a" + PAD)
        self.assertIsNone(truncate("   "))
        self.assertIsNone(truncate(None))

    def test_long_is_cut_with_ellipsis(self):
        out = truncate("x" * 300)
        self.assertEqual(_length(out), 128)
        self.assertTrue(out.endswith("…"))

    def test_emoji_count_double_and_never_split(self):
        out = truncate("🧟" * 100)  # 200 UTF-16 units
        self.assertLessEqual(_length(out), 128)
        self.assertTrue(out.endswith("…"))
        out.encode("utf-8")  # no lone surrogate

    def test_newlines_and_controls(self):
        self.assertEqual(truncate("line one\nline two\x07"), "line one | line two")


class Scenario(unittest.TestCase):
    def test_every_situation_english(self):
        cards = dict(run_scenario(dict(DEFAULTS)))
        for title, card in cards.items():
            check_limits(self, card)
        self.assertEqual(cards["Main menu (game just started)"]["details"], "In the main menu")
        self.assertEqual(cards["Loading a solo game"]["state"], "⏳ Loading…")
        self.assertEqual(cards["In game: health and weapon"]["state"], "❤️ 81 HP · 🔫 Submachine Gun 50/650")
        self.assertTrue(cards["Tank!"]["state"].startswith("🔥 TANK!"))
        self.assertEqual(cards["Incapacitated"]["state"], "🩸 Incapacitated — needs help!")
        self.assertEqual(cards["Paused (Esc in solo)"]["state"], "⏸️ Paused")
        self.assertEqual(cards["Dead"]["state"], "💀 Dead")
        self.assertEqual(cards["Chapter restarts (retry)"]["state"], "🔁 Retry #2")
        self.assertEqual(cards["Safe room reached"]["state"], "🚪 Reached the safe room")
        self.assertEqual(cards["Next chapter loading"]["details"], "Dark Carnival · 2/5 Fairground")
        self.assertEqual(cards["Finale"]["details"], "Dark Carnival · Finale: Concert")
        self.assertEqual(cards["Idle (no keyboard/mouse for 5 min)"]["state"], "💤 Idle")
        self.assertEqual(cards["Back to the main menu"]["state"], "Last game: Dark Carnival")
        online = cards["Online co-op on a server"]
        self.assertEqual(online["party"]["size"], [3, 4])
        self.assertIn("online", online["assets"]["large_text"])
        self.assertNotIn("small_image", online.get("assets", {}))  # character unknown with other humans
        versus = cards["Versus, playing a Hunter"]
        self.assertTrue(versus["state"].startswith("🧟 Playing as the Hunter"))
        self.assertEqual(versus["assets"]["small_text"], "Hunter")
        self.assertIsNone(cards["Game closed"])

    def test_rotation_shows_specials(self):
        parser, tracker = ConsoleParser(), Tracker()
        tracker.game_started(T0, T0)
        lines = ["Host_NewGame on map c2m1_highway", "Map: c2m1_highway", "#Cstrike_TitlesTXT_Game_connected"]
        lines += status_lines(bots=("Coach", "Nick", "Ellis", "Charger", "Jockey")) + dump_lines(health=81)
        for line in lines:
            for ev in parser.feed(line):
                tracker.apply(ev, T0)
        cfg = dict(DEFAULTS)
        seen = [build_activity(tracker.state, cfg, T0 + k * 20)[0]["state"] for k in range(4)]
        self.assertIn("🧟 Specials: Charger, Jockey", seen)
        self.assertIn("❤️ 81 HP · 🔫 Submachine Gun 50/650", seen)
        self.assertIn("🤖 Solo with 3 bots", seen)
        # The key does not change with the rotation: those updates go at the slow pace
        keys = {build_activity(tracker.state, cfg, T0 + k * 20)[1] for k in range(4)}
        self.assertEqual(len(keys), 1)

    def test_french_and_no_emoji(self):
        cfg = dict(DEFAULTS, language="fr", emoji=False)
        cards = dict(run_scenario(cfg))
        for card in cards.values():
            check_limits(self, card)
        self.assertEqual(cards["Main menu (game just started)"]["details"], "Au menu principal")
        self.assertEqual(cards["In game: health and weapon"]["details"], "Lugubre carnaval · 1/5 Autoroute")
        self.assertEqual(cards["In game: health and weapon"]["state"], "81 PV · Mitrailleuse 50/650")
        self.assertEqual(cards["Incapacitated"]["state"], "À terre — a besoin d'aide !")
        self.assertEqual(cards["Finale"]["details"], "Lugubre carnaval · Finale : Concert")
        self.assertEqual(cards["In game: health and weapon"]["assets"]["large_text"], "Difficulté Facile")

    def test_language_auto_follows_game(self):
        cfg = dict(DEFAULTS, language="auto")
        parser, tracker = ConsoleParser(), Tracker()
        tracker.game_started(T0, T0)
        for line in ['"cl_language" = "french"', "Host_NewGame on map c1m1_hotel"]:
            for ev in parser.feed(line):
                tracker.apply(ev, T0)
        card, _ = build_activity(tracker.state, cfg, T0)
        self.assertEqual(card["details"], "Centre de la mort · 1/4 Hôtel")

    def test_privacy_switches(self):
        cfg = dict(DEFAULTS, show_health=False, show_weapon=False, show_specials=False, show_team=False,
                   show_character=False, show_difficulty=False, show_online=False, images=True)
        for title, card in run_scenario(cfg):
            if card is None:
                continue
            text = repr(card)
            self.assertNotIn("HP", text, title)
            self.assertNotIn("Specials", text, title)
            self.assertNotIn("Rochelle", text, title)
            self.assertNotIn("party", card, title)

    def test_options(self):
        cfg = dict(DEFAULTS, status_display="details", timer="none", images=False,
                   buttons=[{"label": "Left 4 Dead 2 on Steam", "url": "https://store.steampowered.com/app/550/"}])
        cards = dict(run_scenario(cfg))
        card = cards["In game: health and weapon"]
        self.assertEqual(card["status_display_type"], 2)
        self.assertNotIn("timestamps", card)
        self.assertNotIn("assets", card)
        self.assertEqual(card["buttons"][0]["label"], "Left 4 Dead 2 on Steam")


class LastLife(unittest.TestCase):
    """Two revives without a first-aid kit = black and white (heuristic)."""

    def test_two_revives_then_heal(self):
        parser, tracker = ConsoleParser(), Tracker()
        tracker.game_started(T0, T0)
        lines = ["Host_NewGame on map c1m1_hotel", "Map: c1m1_hotel", "#Cstrike_TitlesTXT_Game_connected"]
        lines += status_lines("c1m1_hotel", bots=("Nick", "Coach", "Rochelle"))
        t = T0
        for line in lines:
            for ev in parser.feed(line):
                tracker.apply(ev, t)
        for i, health in enumerate([40, 297, 1, 1, 280, 1, 1]):
            t += 3
            for line in dump_lines(health=health, tick=1000 + i * 100):
                for ev in parser.feed(line):
                    tracker.apply(ev, t)
        s = tracker.state
        self.assertEqual(s.revives, 2)
        self.assertTrue(s.last_life)
        t += 22  # past the "revived" banner (20 s), with a fresh dump
        for line in dump_lines(health=1, tick=4000):
            for ev in parser.feed(line):
                tracker.apply(ev, t)
        card, _ = build_activity(s, dict(DEFAULTS, state_rotation=["vitals"]), t)
        self.assertEqual(card["state"], "🖤 1 HP (last life) · 🔫 Submachine Gun 50/650")
        t += 3
        for line in dump_lines(health=80, tick=5000):  # first-aid kit
            for ev in parser.feed(line):
                tracker.apply(ev, t)
        self.assertFalse(tracker.state.last_life)


if __name__ == "__main__":
    unittest.main()
