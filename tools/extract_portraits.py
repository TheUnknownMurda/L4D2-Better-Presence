"""Save the eight survivor portraits of a Steam Workshop preview GIF as PNG files, ready to host.

Source chosen by Sam (2026-10-14): the preview of the workshop item "Survivor Better Materials"
(https://steamcommunity.com/sharedfiles/filedetails/?id=2968256804), a 512x512 GIF with one survivor per frame.
The art belongs to its authors: the files go to assets/portraits/ (not versioned) for personal use only.

Usage:
    python tools/extract_portraits.py
Then host the files (e.g. like the cover image) and put the links in config.json -> "character_images".
"""

from __future__ import annotations

import io
import urllib.request
from pathlib import Path

from PIL import Image, ImageSequence

GIF_URL = ("https://images.steamusercontent.com/ugc/2216394743367178406/"
           "0AF6E0723B3BC46EAF1D08AA85BD570C408CC74C/")
FRAME_ORDER = ["Ellis", "Rochelle", "Coach", "Nick", "Louis", "Zoey", "Francis", "Bill"]  # checked by eye
OUT = Path(__file__).resolve().parent.parent / "assets" / "portraits"


def main() -> int:
    req = urllib.request.Request(GIF_URL, headers={"User-Agent": "L4D2-Better-Presence-tool"})
    gif = Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read()))
    frames = [f.convert("RGB").copy() for f in ImageSequence.Iterator(gif)]
    if len(frames) != len(FRAME_ORDER):
        print(f"Expected {len(FRAME_ORDER)} frames, got {len(frames)}: the preview changed, check the order.")
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    for name, frame in zip(FRAME_ORDER, frames):
        path = OUT / f"{name.lower()}.png"
        frame.save(path, optimize=True)
        print(f"{path}  {frame.size[0]}x{frame.size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
