"""
Talks to the Discord desktop app on this computer the way games show their status: through a local pipe,
with JSON messages that each follow an 8-byte header. No Discord library is needed, no account token.

Adapted from FL Studio Better Presence (src/flbp/discord_ipc.py, MIT, same author): the connection lives in its
own thread, so a busy or frozen Discord never makes the program wait. Changes here: the activity is attached to
the game's PID (like Sons of the Forest Better Presence), and every answer from Discord is logged.
"""
import ctypes
import ctypes.wintypes as wt
import json
import logging
import msvcrt
import os
import struct
import threading
import time
import uuid

log = logging.getLogger("l4d2rpc")
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.PeekNamedPipe.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.c_void_p,
                                   ctypes.POINTER(wt.DWORD), ctypes.c_void_p]

# The kinds of message
HANDSHAKE, FRAME, CLOSE, PING, PONG = range(5)

# Discord listens on discord-ipc-0, or on the next free number when several Discord apps run (Stable, PTB,
# Canary). Tests point the program to a fake Discord with L4D2RPC_DISCORD_PIPE.
PIPE_PREFIX = os.environ.get("L4D2RPC_DISCORD_PIPE", r"\\.\pipe\discord-ipc-")
PIPE_COUNT = 10

UPDATE_INTERVAL = 4  # seconds between two updates at the very least: Discord accepts 5 every 20 seconds
RETRY_INTERVAL = 5  # first wait before looking for Discord again; doubles up to MAX_RETRY_INTERVAL
MAX_RETRY_INTERVAL = 60
REFUSED_RETRY_INTERVAL = 60  # seconds before trying again after Discord refused the application
REPLY_TIMEOUT = 5  # seconds Discord has to answer


class Status:
    OFF = "off"  # nothing to show, so not connected
    NO_DISCORD = "no_discord"  # something to show, but the Discord app isn't running
    CONNECTED = "connected"  # the status is shown
    REFUSED = "refused"  # Discord refused the connection, with the reason in DiscordClient.error


def _dict(value):
    """The value when it is a JSON object, or an empty one: Discord's answers are read without trusting them."""
    return value if isinstance(value, dict) else {}


def discord_running(pipe_prefix=None):
    """True when a Discord app is listening, without connecting to it."""
    folder, _, name = (pipe_prefix or PIPE_PREFIX).rpartition("\\")
    try:
        return any(pipe.startswith(name) for pipe in os.listdir(folder + "\\"))
    except OSError:
        return False


class DiscordClient:
    """Shows an activity in the user's Discord status, and shows it again when Discord restarts."""

    def __init__(self, client_id, pipe_prefix=None, pid=None):
        self.client_id = client_id
        self.pipe_prefix = pipe_prefix or PIPE_PREFIX
        self.pid = pid or os.getpid()
        self.status = Status.OFF
        self.user = ""  # the user's Discord name, once connected
        self.error = ""  # why Discord refused the connection or the last activity, if it did
        self.sent_count = 0
        self._wanted = None  # the activity to show, or None
        self._sent = None  # the activity Discord shows
        self._pipe = None
        self._failure = Status.NO_DISCORD  # why the last connection failed, shown until the next try
        self._retry = RETRY_INTERVAL
        self._next_connect = 0.0
        self._next_update = 0.0
        self._wake = threading.Event()
        self._stopping = False
        self._thread = threading.Thread(target=self._run, name="Discord", daemon=True)
        self._thread.start()

    def show(self, activity, pid=None):
        """The activity to show, or None for none. Only the latest one counts when they come quickly."""
        if pid and pid != self.pid:
            self.pid = pid
        if activity != self._wanted:
            self._wanted = activity
            self._wake.set()

    def stop(self, timeout=2.0):
        """Closes the connection, which removes the status from Discord at once."""
        self._stopping = True
        self._wake.set()
        self._thread.join(timeout)

    # -----------------------------------------------------------------------------------------------------------
    # In the connection's thread

    def _run(self):
        while not self._stopping:
            self._wake.wait(self._wait_time())
            self._wake.clear()
            try:
                self._step()
            except Exception as error:  # Discord closed, froze, or answered something unexpected
                if not isinstance(error, (OSError, ValueError)):
                    log.exception("Unexpected answer from Discord")
                if self.status == Status.CONNECTED:
                    log.info("Lost the connection to Discord (%s). Retrying in %d s.", error or "closed", self._retry)
                self._disconnect()
                self._fail(Status.NO_DISCORD, str(error), self._retry)
        self._disconnect()

    def _wait_time(self):
        """How long the thread can sleep: until show() is called, a retry or an update is due, or a ping comes."""
        if self._wanted is None and self._pipe is None:
            return None
        now = time.monotonic()
        if self._pipe is None:
            return max(0.05, self._next_connect - now)
        if self._wanted != self._sent and self._next_update > now:
            return min(1.0, self._next_update - now)
        return 1.0

    def _step(self):
        wanted = self._wanted
        if wanted is None:
            # Closing the connection is the quickest way to remove the status
            if self._pipe is not None:
                log.info("Card cleared.")
            self._disconnect()
            self.status = Status.OFF
            return
        if self._pipe is None:
            if time.monotonic() < self._next_connect:
                self.status = self._failure
                return
            if not self._connect():
                return
        self._read_waiting()
        if wanted != self._sent and time.monotonic() >= self._next_update:
            self._set_activity(wanted)

    def _fail(self, status, error, retry_in):
        self.status = self._failure = status
        self.error = error
        self._next_connect = time.monotonic() + retry_in
        if status == Status.NO_DISCORD:
            self._retry = min(MAX_RETRY_INTERVAL, self._retry * 2)

    def _connect(self):
        for number in range(PIPE_COUNT):
            try:
                self._pipe = open(f"{self.pipe_prefix}{number}", "r+b", buffering=0)
                break
            except OSError:
                continue
        else:
            if self._failure != Status.NO_DISCORD or self.status == Status.OFF:
                log.info("Discord is not running (the desktop app is needed). Retrying in %d s.", self._retry)
            self._fail(Status.NO_DISCORD, "", self._retry)
            return False
        self._send(HANDSHAKE, {"v": 1, "client_id": self.client_id})
        op, message = self._read(time.monotonic() + REPLY_TIMEOUT)
        if op != FRAME or message.get("evt") != "READY":
            # An unknown application id is refused this way
            self._disconnect()
            reason = str(message.get("message") or "Discord refused the connection.")
            log.warning("Discord refused the connection: %s (client_id %s). Retrying in %d s.",
                        reason, self.client_id, REFUSED_RETRY_INTERVAL)
            self._fail(Status.REFUSED, reason, REFUSED_RETRY_INTERVAL)
            return False
        user = _dict(_dict(message.get("data")).get("user"))
        self.user = str(user.get("global_name") or user.get("username") or "")
        self.status = Status.CONNECTED
        self.error = ""
        self._retry = RETRY_INTERVAL
        log.info("Connected to Discord%s.", f" as {self.user}" if self.user else "")
        return True

    def _set_activity(self, activity):
        nonce = uuid.uuid4().hex
        self._send(FRAME, {"cmd": "SET_ACTIVITY", "args": {"pid": self.pid, "activity": activity}, "nonce": nonce})
        self._next_update = time.monotonic() + UPDATE_INTERVAL
        reply = self._read_reply(nonce)
        # Kept even when refused: the same activity would be refused again
        self._sent = activity
        self.sent_count += 1
        if reply.get("evt") == "ERROR":
            self.error = str(_dict(reply.get("data")).get("message") or "Discord refused the status.")
            log.warning("Discord refused the card: %s | %s", self.error, json.dumps(activity, ensure_ascii=False))
        else:
            self.error = ""
            log.info("Card sent: %s | %s", activity.get("details", ""), activity.get("state", ""))

    def _disconnect(self):
        if self._pipe is not None:
            try:
                self._pipe.close()
            except OSError:
                pass
            self._pipe = None
        self._sent = None

    def _send(self, op, payload):
        # ASCII JSON: any text gets through, emoji included
        data = json.dumps(payload, separators=(",", ":")).encode("ascii")
        message = memoryview(struct.pack("<II", op, len(data)) + data)
        while message:
            written = self._pipe.write(message)
            message = message[written:]

    def _available(self):
        """The number of bytes Discord sent that are waiting to be read."""
        available = wt.DWORD()
        handle = msvcrt.get_osfhandle(self._pipe.fileno())
        if not kernel32.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
            raise ConnectionError("Discord closed the connection.")
        return available.value

    def _read_exactly(self, size, deadline):
        data = bytearray()
        while len(data) < size:
            available = self._available()
            if available:
                data += self._pipe.read(min(available, size - len(data)))
            elif time.monotonic() > deadline:
                raise TimeoutError("Discord didn't answer.")
            else:
                time.sleep(0.01)
        return bytes(data)

    def _read(self, deadline):
        op, length = struct.unpack("<II", self._read_exactly(8, deadline))
        payload = self._read_exactly(length, deadline)
        message = json.loads(payload.decode("utf-8")) if payload else {}
        return op, message if isinstance(message, dict) else {}

    def _handle(self, op, message):
        """Answers Discord's pings, and returns the message when it is an answer or an event."""
        if op == PING:
            self._send(PONG, message)
            return None
        if op == CLOSE:
            raise ConnectionError(message.get("message") or "Discord closed the connection.")
        return message

    def _read_waiting(self):
        while self._available():
            self._handle(*self._read(time.monotonic() + REPLY_TIMEOUT))

    def _read_reply(self, nonce):
        deadline = time.monotonic() + REPLY_TIMEOUT
        while True:
            message = self._handle(*self._read(deadline))
            if message is not None and message.get("nonce") == nonce:
                return message
