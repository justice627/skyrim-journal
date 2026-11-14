"""Form id helpers: render a resolved 32-bit form id as ``plugin:localid``."""
from __future__ import annotations

from .body import SaveBody


def read_refid(b: bytes, form_ids: list[int]) -> int | None:
    """Decode a 3-byte packed RefID (big-endian: 2-bit source, 22-bit value) to a form id."""
    v = int.from_bytes(b[:3], "big")
    src, val = v >> 22, v & 0x3FFFFF
    if src == 0:
        return form_ids[val - 1] if 1 <= val <= len(form_ids) else None
    if src == 1:
        return val
    if src == 2:
        return 0xFF000000 | val
    return None


def describe_form_id(fid: int | None, plugins: list[str], light_plugins: list[str]) -> str | None:
    """0xFE = light plugin (next 12 bits = light index, low 12 bits = local id);
    0xFF = save-created; otherwise the top byte is the full plugin index."""
    if fid is None:
        return None
    top = fid >> 24
    if top == 0xFF:
        return f"created:{fid & 0xFFFFFF:06X}"
    if top == 0xFE:
        li = (fid >> 12) & 0xFFF
        name = light_plugins[li] if li < len(light_plugins) else f"?light[{li}]"
        return f"{name}:{fid & 0xFFF:03X}"
    name = plugins[top] if top < len(plugins) else f"?plugin[{top}]"
    return f"{name}:{fid & 0xFFFFFF:06X}"


def describe(body: SaveBody, fid: int | None) -> str | None:
    return describe_form_id(fid, body.plugins, body.light_plugins)
