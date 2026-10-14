"""Client for the Source engine's network console (the `-netconport` launch option).

Plain text over TCP on this computer: we send console commands, one per line, and receive every line the game
prints in its console. The game must also have `-netconpassword`: the first line we send is `PASS <password>`.
Only read-only commands are sent (status, cvar reads, g15_dumpplayer); see FINDINGS.md.
"""

from __future__ import annotations

import logging
import queue
import socket
import threading
import time

log = logging.getLogger("l4d2rpc")


class NetconClient:
    def __init__(self, host: str, port: int, password: str = "", timeout: float = 3.0):
        self.host, self.port, self.password, self.timeout = host, port, password, timeout
        self.lines: "queue.Queue[tuple[float, str]]" = queue.Queue()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self.connected = False
        self.closed_reason = ""

    def connect(self) -> None:
        sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        sock.settimeout(1.0)
        self._sock = sock
        self.connected = True
        self.closed_reason = ""
        if self.password:
            self.send(f"PASS {self.password}")
        self._thread = threading.Thread(target=self._read_loop, name="netcon", daemon=True)
        self._thread.start()

    def send(self, command: str) -> bool:
        sock = self._sock
        if sock is None:
            return False
        try:
            with self._lock:
                sock.sendall((command + "\n").encode("utf-8"))
            return True
        except OSError as e:
            self._closed(str(e))
            return False

    def close(self) -> None:
        sock, self._sock = self._sock, None
        self.connected = False
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    def _closed(self, reason: str) -> None:
        if self.connected:
            self.closed_reason = reason
        self.connected = False

    def _read_loop(self) -> None:
        buf = b""
        while self.connected and self._sock is not None:
            try:
                chunk = self._sock.recv(65536)
            except socket.timeout:
                continue
            except OSError as e:
                self._closed(str(e))
                break
            if not chunk:
                self._closed("the game closed the console connection")
                break
            buf += chunk
            now = time.time()
            while b"\n" in buf:
                raw, buf = buf.split(b"\n", 1)
                self.lines.put((now, raw.rstrip(b"\r").decode("utf-8", "replace")))
        self.connected = False
