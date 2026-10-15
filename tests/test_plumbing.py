"""Config, Steam files, the Discord client (on a fake Discord), the send pacing and the console client."""

import json
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

import helpers  # noqa: F401

from fake_discord import FakeDiscord
from l4d2_rpc import config, discord_ipc, install, steam, system, vdf
from l4d2_rpc.app import FAST_UPDATE_SECONDS, SLOW_UPDATE_SECONDS, Sender
from l4d2_rpc.netcon import NetconClient


class Config(unittest.TestCase):
    def test_defaults(self):
        cfg, problems = config.validate({})
        self.assertEqual(problems, [])
        self.assertEqual(cfg["client_id"], "356954277803065354")
        self.assertEqual(cfg["language"], "en")

    def test_bad_values_fall_back_with_a_message(self):
        cfg, problems = config.validate({"language": "de", "timer": "forever", "rotate_seconds": 1,
                                         "emoji": "yes", "buttons": [{"label": "x" * 40, "url": "http://a"}],
                                         "state_rotation": ["vitals", "nope"], "mystery": 1, "_comment": "ok"})
        self.assertEqual(cfg["language"], "en")
        self.assertEqual(cfg["timer"], "campaign")
        self.assertEqual(cfg["rotate_seconds"], 5)  # clamped
        self.assertTrue(cfg["emoji"])
        self.assertEqual(cfg["buttons"], [])
        self.assertEqual(len(problems), 6)
        self.assertTrue(any('"mystery"' in p for p in problems))

    def test_example_file_is_valid(self):
        raw = json.loads(config.EXAMPLE_PATH.read_text(encoding="utf-8"))
        cfg, problems = config.validate(raw)
        self.assertEqual(problems, [])
        self.assertEqual(set(k for k in raw if not k.startswith("_")), set(config.DEFAULTS))

    def test_broken_json(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.json"
            path.write_text("{ not json", encoding="utf-8")
            cfg, problems = config.load(path)
            self.assertEqual(cfg["language"], "en")
            self.assertIn("not valid JSON", problems[0])


class SteamFiles(unittest.TestCase):
    def test_launch_options(self):
        o = steam.parse_launch_options("-novid -netconport 27015 -netconpassword abc123 -g15")
        self.assertEqual((o.netcon_port, o.netcon_password, o.g15), (27015, "abc123", True))
        o = steam.parse_launch_options("-netconport 27015")
        self.assertEqual((o.netcon_port, o.netcon_password, o.g15), (27015, None, False))
        self.assertEqual(steam.parse_launch_options("").netcon_port, None)

    def test_suggested_line_keeps_other_options(self):
        line = steam.suggested_launch_options("newpw", 27015, "-novid -netconport 27015 -netconpassword old -g15")
        self.assertEqual(line, "-novid -netconport 27015 -netconpassword newpw -g15")

    def test_localconfig(self):
        text = ('"UserLocalConfigStore"\n{\n "Software"\n {\n  "Valve"\n  {\n   "Steam"\n   {\n    "apps"\n    {\n'
                '     "550"\n     {\n      "LaunchOptions"\t\t"-netconport 27015 -netconpassword 0a1b -g15"\n     }\n'
                '    }\n   }\n  }\n }\n}\n')
        with tempfile.TemporaryDirectory() as d:
            cfgdir = Path(d) / "userdata" / "123" / "config"
            cfgdir.mkdir(parents=True)
            (cfgdir / "localconfig.vdf").write_text(text, encoding="utf-8")
            o = steam.launch_options(Path(d), account_id=123)
        self.assertEqual((o.netcon_port, o.netcon_password, o.g15), (27015, "0a1b", True))

    def test_keyvalues_conditions_and_comments(self):
        kv = vdf.parse('"lang" { "Tokens" { // c\n "a" "x360" [$X360]\n "a" "pc" [$WIN32]\n "B" "b\\"q" } }')
        tokens = kv.path("lang", "tokens")
        self.assertEqual(tokens.get("a"), "pc")
        self.assertEqual(tokens.get("b"), 'b"q')


class InstallSteps(unittest.TestCase):
    def test_launch_options_kept_when_complete(self):
        opts = steam.parse_launch_options("-novid -netconport 27015 -netconpassword abc -g15")
        self.assertEqual(install.launch_options_line(opts), (opts.raw, False))

    def test_existing_password_reused(self):
        line, change = install.launch_options_line(steam.parse_launch_options("-netconport 27016 -netconpassword abc"))
        self.assertTrue(change)
        self.assertEqual(line, "-netconport 27016 -netconpassword abc -g15")

    def test_new_password_when_none(self):
        line, change = install.launch_options_line(None)
        self.assertTrue(change)
        o = steam.parse_launch_options(line)
        self.assertEqual((o.netcon_port, len(o.netcon_password), o.g15), (27015, 16, True))

    def test_never_terminates_a_non_python_process(self):
        # A stale PID file could point anywhere: a non-Python process must be refused
        self.assertFalse(system.terminate_python(4))  # "System"


class DiscordOnFakePipe(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDiscord()
        self.client = discord_ipc.DiscordClient("356954277803065354", pipe_prefix=self.fake.prefix, pid=1234)

    def tearDown(self):
        self.client.stop()
        self.fake.stop()

    def wait(self, condition, timeout=8):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if condition():
                return True
            time.sleep(0.05)
        return False

    def test_send_then_clear(self):
        card = {"type": 0, "details": "Dead Center · 1/4 Hotel", "state": "❤️ 81 HP"}
        self.client.show(card)
        self.assertTrue(self.wait(lambda: self.fake.last == card))
        self.assertEqual(self.fake.client_id, "356954277803065354")
        self.client.show(None)  # closing the pipe removes the card
        self.assertTrue(self.wait(lambda: self.fake.disconnected.is_set()))

    def test_reconnects_after_discord_restart(self):
        self.client.show({"type": 0, "details": "one", "state": "two"})
        self.assertTrue(self.wait(lambda: self.fake.connections == 1 and self.fake.last is not None))
        self.fake.kick()
        self.assertTrue(self.wait(lambda: self.fake.connections == 2, timeout=15))
        self.assertTrue(self.wait(lambda: len(self.fake.activities) >= 2, timeout=10))


class DiscordRefusals(unittest.TestCase):
    def test_refused_application(self):
        fake = FakeDiscord(refuse=True)
        client = discord_ipc.DiscordClient("1", pipe_prefix=fake.prefix)
        try:
            client.show({"type": 0, "details": "x1", "state": "y1"})
            end = time.monotonic() + 5
            while time.monotonic() < end and client.status != discord_ipc.Status.REFUSED:
                time.sleep(0.05)
            self.assertEqual(client.status, discord_ipc.Status.REFUSED)
            self.assertIn("Invalid Client ID", client.error)
        finally:
            client.stop()
            fake.stop()

    def test_rejected_card_is_logged_not_fatal(self):
        fake = FakeDiscord(reject_activities=True)
        client = discord_ipc.DiscordClient("1", pipe_prefix=fake.prefix)
        try:
            with self.assertLogs("l4d2rpc", level="WARNING") as logs:
                client.show({"type": 0, "details": "x1", "state": "y1"})
                end = time.monotonic() + 6
                while time.monotonic() < end and not client.error:
                    time.sleep(0.05)
            self.assertIn("refused the card", "\n".join(logs.output))
            self.assertEqual(client.status, discord_ipc.Status.CONNECTED)
        finally:
            client.stop()
            fake.stop()


class Pacing(unittest.TestCase):
    class Recorder:
        def __init__(self):
            self.shown = []

        def show(self, activity, pid=None):
            self.shown.append(activity)

    def test_important_fast_minor_slow(self):
        rec = self.Recorder()
        s = Sender(rec)
        a1, a2, a3 = {"state": "1"}, {"state": "2"}, {"state": "3"}
        self.assertTrue(s.offer(a1, ("ingame", "k1"), 0))
        self.assertFalse(s.offer(a1, ("ingame", "k1"), 1))  # unchanged: nothing sent
        self.assertFalse(s.offer(a2, ("ingame", "k1"), FAST_UPDATE_SECONDS))  # minor: waits
        self.assertTrue(s.offer(a2, ("ingame", "k1"), SLOW_UPDATE_SECONDS))
        t = SLOW_UPDATE_SECONDS
        self.assertFalse(s.offer(a3, ("ingame", "k2"), t + 1))  # important but too soon
        self.assertTrue(s.offer(a3, ("ingame", "k2"), t + FAST_UPDATE_SECONDS))  # within 5 s
        self.assertTrue(s.offer(None, None, t + FAST_UPDATE_SECONDS + 0.1))  # clearing is immediate
        self.assertEqual(rec.shown, [a1, a2, a3, None])


class FakeNetcon:
    """A TCP server speaking like the game's console: demands PASS, answers z_difficulty."""

    def __init__(self, password="pw"):
        self.password = password
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.port = self.server.getsockname()[1]
        self.received = []
        self.conn = None
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        conn, _ = self.server.accept()
        self.conn = conn
        authed = False
        buf = b""
        while True:
            try:
                chunk = conn.recv(1024)
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                cmd = line.decode()
                self.received.append(cmd)
                if cmd.startswith("PASS "):
                    authed = cmd[5:] == self.password
                elif not authed:
                    conn.sendall(b"This server is password protected for console access. Must send PASS command\n")
                elif cmd == "z_difficulty":
                    conn.sendall(b'"z_difficulty" = "Hard" ( def. "Normal" )\r\n client replicated\n')

    def close(self):
        if self.conn:
            self.conn.close()
        self.server.close()


class Netcon(unittest.TestCase):
    def read_lines(self, client, n, timeout=3):
        out, end = [], time.monotonic() + timeout
        while len(out) < n and time.monotonic() < end:
            try:
                out.append(client.lines.get(timeout=0.1)[1])
            except Exception:
                pass
        return out

    def test_password_and_answer(self):
        fake = FakeNetcon()
        client = NetconClient("127.0.0.1", fake.port, "pw")
        client.connect()
        client.send("z_difficulty")
        self.assertEqual(self.read_lines(client, 1)[0], '"z_difficulty" = "Hard" ( def. "Normal" )')
        self.assertEqual(fake.received[0], "PASS pw")
        fake.close()
        end = time.monotonic() + 3
        while client.connected and time.monotonic() < end:
            time.sleep(0.05)
        self.assertFalse(client.connected)  # game closed -> noticed
        client.close()

    def test_wrong_password(self):
        fake = FakeNetcon()
        client = NetconClient("127.0.0.1", fake.port, "nope")
        client.connect()
        client.send("z_difficulty")
        self.assertIn("password protected", self.read_lines(client, 1)[0])
        client.close()
        fake.close()


if __name__ == "__main__":
    unittest.main()
