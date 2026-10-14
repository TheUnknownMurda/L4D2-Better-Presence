"""Minimal read-only decoder for Valve VTF textures (largest mipmap, first frame) -> PNG, through Pillow.

Used to extract the game's HUD portraits (materials/vgui/s_panel_*.vtf) for comparison. Formats handled:
DXT1, DXT3, DXT5 (decoded by Pillow's DDS reader), BGRA8888, BGR888, RGBA8888, RGB888.

Usage:
    python tools/vtf.py <pak01_dir.vpk> <materials/…/file.vtf> <out.png>
"""

from __future__ import annotations

import io
import struct
import sys

from PIL import Image

FORMATS = {0: "RGBA8888", 2: "RGB888", 3: "BGR888", 12: "BGRA8888", 13: "DXT1", 14: "DXT3", 15: "DXT5",
           16: "BGRX8888", 20: "DXT1"}


def _size(fmt: str, w: int, h: int) -> int:
    if fmt == "DXT1":
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 8
    if fmt in ("DXT3", "DXT5"):
        return max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * 16
    return w * h * (3 if fmt in ("RGB888", "BGR888") else 4)


def _dds(fmt: str, w: int, h: int, data: bytes) -> Image.Image:
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000
    pixel_format = struct.pack("<II4s5I", 32, 0x4, fmt.encode(), 0, 0, 0, 0, 0)
    header = struct.pack("<7I44s", 124, flags, h, w, len(data), 0, 0, b"\0" * 44) + pixel_format
    header += struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    return Image.open(io.BytesIO(b"DDS " + header + data))


def decode(raw: bytes) -> Image.Image:
    if raw[:4] != b"VTF\0":
        raise ValueError("not a VTF file")
    major, minor, header_size = struct.unpack_from("<III", raw, 4)
    width, height, _flags, frames = struct.unpack_from("<HHIH", raw, 16)
    hi_fmt_id = struct.unpack_from("<I", raw, 52)[0]
    mip_count = raw[56]
    lo_fmt_id = struct.unpack_from("<I", raw, 57)[0]
    lo_w, lo_h = raw[61], raw[62]
    fmt = FORMATS.get(hi_fmt_id)
    if fmt is None:
        raise ValueError(f"unsupported VTF format {hi_fmt_id}")
    if (major, minor) >= (7, 3):
        count = struct.unpack_from("<I", raw, 68)[0]
        start = None
        for i in range(count):
            tag, offset = raw[80 + i * 8:83 + i * 8], struct.unpack_from("<I", raw, 84 + i * 8)[0]
            if tag == b"\x30\0\0":
                start = offset
        if start is None:
            raise ValueError("no image data")
    else:
        lo_fmt = FORMATS.get(lo_fmt_id, "DXT1")
        start = header_size + (_size(lo_fmt, lo_w, lo_h) if lo_w and lo_h and lo_fmt_id != 0xFFFFFFFF else 0)
    # Mipmaps are stored smallest first: skip all but the largest
    for level in range(mip_count - 1, 0, -1):
        start += _size(fmt, max(1, width >> level), max(1, height >> level)) * max(1, frames)
    data = raw[start:start + _size(fmt, width, height)]
    if fmt.startswith("DXT"):
        return _dds(fmt, width, height, data).convert("RGBA")
    if fmt == "BGRA8888":
        return Image.frombytes("RGBA", (width, height), data, "raw", "BGRA")
    if fmt == "BGRX8888":
        return Image.frombytes("RGB", (width, height), data, "raw", "BGRX")
    if fmt == "BGR888":
        return Image.frombytes("RGB", (width, height), data, "raw", "BGR")
    return Image.frombytes("RGBA" if fmt == "RGBA8888" else "RGB", (width, height), data)


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(__doc__)
        return 2
    sys.path.insert(0, __import__("os").path.dirname(__file__))
    from vpk import Vpk
    decode(Vpk(argv[1]).read(argv[2])).save(argv[3])
    print(f"saved {argv[3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
