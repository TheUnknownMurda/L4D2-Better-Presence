"""What Windows shows from the outside: the game's process, keyboard/mouse idle time, a single-instance lock.

ctypes only. Nothing is opened inside the game: the process list and the process start time are all we ask.
Process helpers adapted from Dead by Daylight Better Presence (dbd_rpc/game.py, MIT, same author).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import time
from dataclasses import dataclass

GAME_EXE = "left4dead2.exe"

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_u32 = ctypes.WinDLL("user32", use_last_error=True)

TH32CS_SNAPPROCESS = 0x2
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
ERROR_ALREADY_EXISTS = 183


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", wt.LONG),
        ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * 260),
    ]


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]


_k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
_k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
_k32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
_k32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
_k32.OpenProcess.restype = wt.HANDLE
_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
_k32.CloseHandle.argtypes = [wt.HANDLE]
_k32.CreateMutexW.restype = wt.HANDLE
_k32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
_k32.GetTickCount.restype = wt.DWORD
_k32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
_k32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
PROCESS_TERMINATE = 0x0001
_u32.GetLastInputInfo.argtypes = [ctypes.POINTER(_LASTINPUTINFO)]


@dataclass(frozen=True)
class GameProcess:
    pid: int
    start_time: float  # epoch seconds


def _filetime(ft: wt.FILETIME) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def process_start_time(pid: int) -> float | None:
    handle = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        times = (wt.FILETIME * 4)()
        if not _k32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            return None
        return (_filetime(times[0]) - 116444736000000000) / 1e7
    finally:
        _k32.CloseHandle(handle)


def process_cpu_seconds(pid: int) -> float | None:
    """Kernel + user CPU time used so far by a process (to measure our own cost)."""
    handle = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        times = (wt.FILETIME * 4)()
        if not _k32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
            return None
        return (_filetime(times[2]) + _filetime(times[3])) / 1e7
    finally:
        _k32.CloseHandle(handle)


def find_game(exe: str = GAME_EXE) -> GameProcess | None:
    snapshot = _k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == INVALID_HANDLE_VALUE or not snapshot:
        return None
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        ok = _k32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == exe.lower():
                pid = int(entry.th32ProcessID)
                return GameProcess(pid, process_start_time(pid) or time.time())
            ok = _k32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        _k32.CloseHandle(snapshot)
    return None


def terminate_python(pid: int) -> bool:
    """Ends a process only if it is python.exe/pythonw.exe (a PID file can be stale and point elsewhere)."""
    handle = _k32.OpenProcess(PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(len(buf))
        if not _k32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return False
        if buf.value.lower().rsplit("\\", 1)[-1] not in ("python.exe", "pythonw.exe"):
            return False
        return bool(_k32.TerminateProcess(handle, 0))
    finally:
        _k32.CloseHandle(handle)


def idle_seconds() -> float:
    """Seconds since the last keyboard or mouse input on this computer."""
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
    if not _u32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return ((_k32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0


class SingleInstance:
    """A named mutex: a second copy of the program sees it and quits."""

    def __init__(self, name: str = "Local\\L4D2RPC.Companion"):
        self.handle = _k32.CreateMutexW(None, False, name)
        self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS

    def release(self) -> None:
        if self.handle:
            _k32.CloseHandle(self.handle)
            self.handle = None
