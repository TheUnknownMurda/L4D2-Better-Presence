"""Minimal read-only reader for Valve VPK archives (v1 and v2).

Used by the data-generation tools to pull localisation and mission files out
of the game's pak01_dir.vpk. Never writes to the game folder.

Usage:
    python tools/vpk.py list  <pak01_dir.vpk> [substring]
    python tools/vpk.py cat   <pak01_dir.vpk> <path/inside/vpk>
"""

from __future__ import annotations

import os
import struct
import sys
from dataclasses import dataclass

VPK_SIGNATURE = 0x55AA1234
DIR_ARCHIVE = 0x7FFF


@dataclass
class Entry:
    path: str
    crc: int
    preload: bytes
    archive_index: int
    offset: int
    length: int


class Vpk:
    def __init__(self, dir_path: str):
        self.dir_path = dir_path
        self.entries: dict[str, Entry] = {}
        with open(dir_path, "rb") as f:
            sig, version, tree_size = struct.unpack("<III", f.read(12))
            if sig != VPK_SIGNATURE:
                raise ValueError(f"not a VPK file: {dir_path}")
            if version == 2:
                f.read(16)
                header_size = 28
            elif version == 1:
                header_size = 12
            else:
                raise ValueError(f"unsupported VPK version {version}")
            tree = f.read(tree_size)
        self.data_start = header_size + tree_size
        self._parse_tree(tree)

    def _parse_tree(self, tree: bytes) -> None:
        pos = 0

        def read_str() -> str:
            nonlocal pos
            end = tree.index(b"\0", pos)
            s = tree[pos:end].decode("utf-8", "replace")
            pos = end + 1
            return s

        while True:
            ext = read_str()
            if not ext:
                break
            while True:
                folder = read_str()
                if not folder:
                    break
                while True:
                    name = read_str()
                    if not name:
                        break
                    crc, preload_len, arch, off, length, term = struct.unpack_from("<IHHIIH", tree, pos)
                    pos += 18
                    if term != 0xFFFF:
                        raise ValueError("corrupt VPK tree")
                    preload = tree[pos:pos + preload_len]
                    pos += preload_len
                    full = (name if folder.strip() == "" else f"{folder}/{name}") + (f".{ext}" if ext.strip() else "")
                    self.entries[full.lower()] = Entry(full, crc, preload, arch, off, length)

    def read(self, path: str) -> bytes:
        e = self.entries[path.lower().replace("\\", "/")]
        data = e.preload
        if e.length:
            if e.archive_index == DIR_ARCHIVE:
                archive, offset = self.dir_path, self.data_start + e.offset
            else:
                archive = self.dir_path.replace("_dir.vpk", f"_{e.archive_index:03d}.vpk")
                offset = e.offset
            with open(archive, "rb") as f:
                f.seek(offset)
                data += f.read(e.length)
        return data


def decode_text(raw: bytes) -> str:
    """Decode a Valve text file: UTF-16 LE with BOM (localisation) or UTF-8."""
    if raw[:2] == b"\xff\xfe":
        return raw[2:].decode("utf-16-le", "replace")
    if raw[:3] == b"\xef\xbb\xbf":
        return raw[3:].decode("utf-8", "replace")
    return raw.decode("utf-8", "replace")


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in ("list", "cat"):
        print(__doc__)
        return 2
    vpk = Vpk(argv[2])
    if argv[1] == "list":
        needle = argv[3].lower() if len(argv) > 3 else ""
        for key in sorted(vpk.entries):
            if needle in key:
                print(vpk.entries[key].path)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(decode_text(vpk.read(argv[3])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
