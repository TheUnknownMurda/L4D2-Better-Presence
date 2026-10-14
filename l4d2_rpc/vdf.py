"""Reader for Valve's KeyValues text format (Steam's .vdf files, the game's mission and language files).

    "key"   "value"
    "block" { "key" "value" }   // comments, and [$WIN32]-style conditions after a value

Keys are kept as written; lookups through `get()` ignore case, like the engine does.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(
    r'\s+|//[^\n]*|"((?:[^"\\]|\\.)*)"|(\{)|(\})|(\[[^\]\n]*\])|([^\s{}"\[]+)',
)
_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}


class KeyValues(dict):
    """A block: a dict that also offers case-insensitive lookups."""

    def get(self, key, default=None):  # noqa: D401 - same contract as dict.get
        if key in self:
            return self[key]
        lower = key.lower()
        for k, v in self.items():
            if k.lower() == lower:
                return v
        return default

    def path(self, *keys, default=None):
        node = self
        for key in keys:
            if not isinstance(node, KeyValues):
                return default
            node = node.get(key)
            if node is None:
                return default
        return node


def _unescape(text: str) -> str:
    return re.sub(r"\\(.)", lambda m: _ESCAPES.get(m.group(1), "\\" + m.group(1)), text)


def _tokens(text: str):
    for m in _TOKEN.finditer(text):
        quoted, open_, close, cond, bare = m.groups()
        if quoted is not None:
            yield "str", _unescape(quoted)
        elif open_:
            yield "{", None
        elif close:
            yield "}", None
        elif cond:
            yield "cond", cond
        elif bare:
            yield "str", bare


def parse(text: str, keep_condition=lambda cond: cond.upper() not in ("[$X360]", "[$OSX]", "[$LINUX]")) -> KeyValues:
    """Parse KeyValues text. Values followed by a condition that `keep_condition` rejects are skipped.

    When a key appears twice in a block the last kept value wins, except for blocks, which are merged.
    Never raises on malformed text: whatever could be read is returned.
    """
    root = KeyValues()
    stack = [root]
    pending_key: str | None = None
    last: tuple[KeyValues, str, object] | None = None  # (block, key, previous value) of the latest pair
    for kind, value in _tokens(text):
        current = stack[-1]
        if kind == "cond":
            if last is not None and not keep_condition(value):
                block, key, previous = last
                if previous is None:
                    block.pop(key, None)
                else:
                    block[key] = previous
            last = None
            continue
        if kind == "{":
            child = KeyValues()
            key = pending_key if pending_key is not None else ""
            existing = current.get(key) if key in current else None
            if isinstance(existing, KeyValues):
                child = existing
            else:
                current[key] = child
            stack.append(child)
            pending_key = None
            last = None
            continue
        if kind == "}":
            if len(stack) > 1:
                stack.pop()
            pending_key = None
            last = None
            continue
        if pending_key is None:
            pending_key = value
        else:
            previous = current.get(pending_key) if pending_key in current else None
            current[pending_key] = value
            last = (current, pending_key, previous)
            pending_key = None
    return root


def parse_file(path, encoding: str | None = None) -> KeyValues:
    """Parse a file, guessing UTF-16 (language files have a BOM) or UTF-8."""
    with open(path, "rb") as f:
        raw = f.read()
    return parse(decode(raw, encoding))


def decode(raw: bytes, encoding: str | None = None) -> str:
    if encoding:
        return raw.decode(encoding, "replace")
    if raw[:2] == b"\xff\xfe":
        return raw[2:].decode("utf-16-le", "replace")
    if raw[:3] == b"\xef\xbb\xbf":
        return raw[3:].decode("utf-8", "replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", "replace")
