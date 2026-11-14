"""Fill the ``<Alias=...>`` and ``<Global=...>`` tags in quest objective text.

Other tags (``<Alias.Race=...>``, ``<BaseName>``, ...) are left exactly as they are. A tag that
cannot be filled is shown as ``[Name]``; nothing is guessed.
"""
from __future__ import annotations

import re
from typing import Callable

TAG = re.compile(r"<(Alias|Alias\.ShortName|Alias\.Name|Global)=([^<>=]+)>")


def render_tags(text: str, alias_value: Callable[[str], str | None],
                global_value: Callable[[str], float | None]) -> str:
    """``alias_value(name)`` gives the display text of an alias by its name in the quest (None if
    unknown); ``global_value(editor id)`` gives the value of a global (None if unknown)."""
    def sub(m: re.Match) -> str:
        kind, name = m.group(1), m.group(2).strip()
        if kind == "Global":
            v = global_value(name)
            if v is None:
                return f"[{name}]"
            return str(int(round(v))) if abs(v - round(v)) < 1e-4 else f"{v:g}"
        return alias_value(name) or f"[{name}]"
    return TAG.sub(sub, text)
