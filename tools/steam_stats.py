"""Read-only dump of Steam's local stats cache for a game (binary KeyValues files in Steam/appcache/stats).

    UserGameStatsSchema_<appid>.bin           stat ids, names, types, bit names
    UserGameStats_<accountid>_<appid>.bin     the logged-in user's values

Usage:
    python tools/steam_stats.py schema [filter]      list stats of the schema (id, type, name, bits)
    python tools/steam_stats.py values [filter]      the user's values with their names
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from l4d2_rpc import steam  # noqa: E402

APP_ID = "550"
NONE, STRING, INT32, FLOAT32, PTR, WSTRING, COLOR, UINT64, END, INT64 = 0, 1, 2, 3, 4, 5, 6, 7, 8, 10


def parse_binary_kv(data: bytes, pos: int = 0) -> tuple[dict, int]:
    out: dict = {}
    while pos < len(data):
        kind = data[pos]
        pos += 1
        if kind == END:
            return out, pos
        end = data.index(b"\0", pos)
        key = data[pos:end].decode("utf-8", "replace")
        pos = end + 1
        if kind == NONE:
            value, pos = parse_binary_kv(data, pos)
        elif kind == STRING:
            end = data.index(b"\0", pos)
            value = data[pos:end].decode("utf-8", "replace")
            pos = end + 1
        elif kind in (INT32, COLOR, PTR):
            value = struct.unpack_from("<i", data, pos)[0]
            pos += 4
        elif kind == FLOAT32:
            value = struct.unpack_from("<f", data, pos)[0]
            pos += 4
        elif kind in (UINT64, INT64):
            value = struct.unpack_from("<Q" if kind == UINT64 else "<q", data, pos)[0]
            pos += 8
        else:
            raise ValueError(f"unknown binary KV type {kind} at {pos - 1}")
        out[key] = value
    return out, pos


def load(name: str) -> dict:
    path = steam.steam_path() / "appcache" / "stats" / name
    return parse_binary_kv(path.read_bytes())[0]


def schema_stats() -> dict:
    root = load(f"UserGameStatsSchema_{APP_ID}.bin")
    return root.get(APP_ID, root).get("stats", {})


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) < 2 or argv[1] not in ("schema", "values"):
        print(__doc__)
        return 2
    needle = re.compile(argv[2], re.I) if len(argv) > 2 else None
    stats = schema_stats()
    if argv[1] == "schema":
        for sid, st in stats.items():
            name = st.get("name", "")
            bits = st.get("bits") or {}
            text = f"{sid:>4} type={st.get('type')} {name} {st.get('display', {}).get('name', '') if isinstance(st.get('display'), dict) else ''}"
            if needle is None or needle.search(text) or any(needle.search(str(b)) for b in bits.values()):
                print(text)
                for bid, b in bits.items():
                    print(f"       bit {bid}: {b.get('name') if isinstance(b, dict) else b}")
        return 0
    folder = steam.steam_path() / "appcache" / "stats"
    account = steam.active_account_id()
    files = [folder / f"UserGameStats_{account}_{APP_ID}.bin"] if account else []
    files += sorted(folder.glob(f"UserGameStats_*_{APP_ID}.bin"), key=lambda f: f.stat().st_mtime, reverse=True)
    values = load(next(f for f in files if f.exists()).name)
    print({k: (v if not isinstance(v, dict) else f"<{len(v)} keys>") for k, v in values.items()})
    data = values.get("data") or values.get("cache") or values
    for sid, value in (data.items() if isinstance(data, dict) else []):
        st = stats.get(str(sid), {})
        name = st.get("name", "?")
        if needle is None or needle.search(name):
            print(f"{sid:>4} {name} = {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
