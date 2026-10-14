"""
A stand-in for the Discord app for the tests, on a pipe of its own: the user's real Discord is never involved.

Copied from FL Studio Better Presence (tests/fake_discord.py, MIT, same author).
"""
import _winapi
import json
import struct
import threading
import time
import uuid

HANDSHAKE, FRAME, CLOSE, PING, PONG = range(5)
ERROR_PIPE_CONNECTED = 535
BYTE_MODE_BLOCKING = 0  # PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT, like Discord's pipe


class FakeDiscord:

    def __init__(self, refuse=False, reject_activities=False, prefix=None, odd_answers=False):
        self.prefix = prefix or rf"\\.\pipe\l4d2rpc-test-{uuid.uuid4().hex}-"
        self.refuse = refuse
        self.reject_activities = reject_activities
        self.odd_answers = odd_answers  # answers shaped unlike Discord's, which mustn't stop the app
        self.client_id = None
        self.activities = []  # (time, activity) for each update received
        self.pongs = []
        self.connections = 0
        self.connected = threading.Event()
        self.disconnected = threading.Event()
        self._handle = None
        self._kick = False
        self._stopping = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    @property
    def last(self):
        return self.activities[-1][1] if self.activities else None

    def ping(self):
        with self._lock:
            self._send(PING, {"nonce": "ping"})

    def kick(self):
        """Closes the connection, the way Discord does when it quits."""
        self._kick = True

    def stop(self):
        self._stopping = True
        self._kick = True
        try:
            # Wakes the server up if it is waiting for a client
            _winapi.CloseHandle(_winapi.CreateFile(self.prefix + "0", _winapi.GENERIC_READ, 0, _winapi.NULL,
                                                   _winapi.OPEN_EXISTING, 0, _winapi.NULL))
        except OSError:
            pass
        self._thread.join(2)

    def _serve(self):
        while not self._stopping:
            handle = _winapi.CreateNamedPipe(
                self.prefix + "0", _winapi.PIPE_ACCESS_DUPLEX, BYTE_MODE_BLOCKING,
                _winapi.PIPE_UNLIMITED_INSTANCES, 65536, 65536, 0, _winapi.NULL)
            try:
                _winapi.ConnectNamedPipe(handle, False)
            except OSError as error:
                if error.winerror != ERROR_PIPE_CONNECTED:
                    raise
            if self._stopping:
                _winapi.CloseHandle(handle)
                break
            self._handle = handle
            self._kick = False
            self.connections += 1
            self.disconnected.clear()
            try:
                self._talk()
            except OSError:
                pass  # the client left
            finally:
                with self._lock:
                    self._handle = None
                _winapi.CloseHandle(handle)
                self.connected.clear()
                self.disconnected.set()

    def _talk(self):
        while not self._kick:
            op, message = self._read()
            if op is None:
                time.sleep(0.01)
            elif op == HANDSHAKE:
                if self.refuse:
                    self._reply(CLOSE, {"code": 4000, "message": "Invalid Client ID"})
                    return
                self.client_id = message.get("client_id")
                user = "Tester" if self.odd_answers else {"username": "tester", "global_name": "Tester"}
                self._reply(FRAME, {"cmd": "DISPATCH", "evt": "READY", "data": {"v": 1, "user": user}})
                self.connected.set()
            elif op == FRAME and message.get("cmd") == "SET_ACTIVITY":
                activity = message["args"].get("activity")
                self.activities.append((time.monotonic(), activity))
                if self.odd_answers:
                    self._reply(FRAME, {"cmd": "SET_ACTIVITY", "evt": "ERROR", "nonce": message["nonce"],
                                        "data": ["not", "an", "object"]})
                elif self.reject_activities:
                    self._reply(FRAME, {"cmd": "SET_ACTIVITY", "evt": "ERROR", "nonce": message["nonce"],
                                        "data": {"code": 4000, "message": "child \"activity\" fails"}})
                else:
                    self._reply(FRAME, {"cmd": "SET_ACTIVITY", "evt": None, "nonce": message["nonce"],
                                        "data": activity})
            elif op == PONG:
                self.pongs.append(message)
            elif op == CLOSE:
                return

    def _read(self):
        """The next message, or (None, None) when there is none yet."""
        available = _winapi.PeekNamedPipe(self._handle, 0)[0]
        if available < 8:
            return None, None
        op, length = struct.unpack("<II", self._read_exactly(8))
        return op, json.loads(self._read_exactly(length))

    def _read_exactly(self, size):
        data = b""
        while len(data) < size:
            chunk, _ = _winapi.ReadFile(self._handle, size - len(data))
            data += chunk
        return data

    def _reply(self, op, payload):
        with self._lock:
            self._send(op, payload)

    def _send(self, op, payload):
        if self._handle is None:
            return
        data = json.dumps(payload).encode("utf-8")
        _winapi.WriteFile(self._handle, struct.pack("<II", op, len(data)) + data)
