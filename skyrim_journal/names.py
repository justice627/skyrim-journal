"""Form id naming.

The save stores form ids, not names. A names file is a JSON object mapping
``"<PluginFileName>:<hex local id>"`` (the format ``refs.describe_form_id`` renders; plugin
name is case-insensitive, the id may have any number of leading zeros) to
``{"edid": "...", "name": "...", "type": "QUST"}``. All three fields are optional; ``name`` is
shown, falling back to ``edid``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass


class NamesFileError(ValueError):
    pass


@dataclass(frozen=True)
class NameEntry:
    edid: str = ""
    name: str = ""
    type: str = ""

    @property
    def label(self) -> str:
        return self.name or self.edid


# Verified on the sample save itself (see tests): gold/lockpick counts match the misc stats,
# PlayerFaction is the first faction of the player NPC_, ArgonianRace matches the header's
# race editor id, WindhelmWorld is the player's worldspace and the location in the file name.
BUILTIN: dict[str, dict[str, str]] = {
    "Skyrim.esm:00000F": {"name": "Gold", "type": "MISC"},
    "Skyrim.esm:00000A": {"name": "Lockpick", "type": "MISC"},
    "Skyrim.esm:000DB1": {"edid": "PlayerFaction", "type": "FACT"},
    "Skyrim.esm:013740": {"edid": "ArgonianRace", "type": "RACE"},
    "Skyrim.esm:01691D": {"edid": "WindhelmWorld", "type": "WRLD"},
}


def normalize_key(key: str) -> tuple[str, int] | None:
    plugin, sep, ident = key.rpartition(":")
    if not sep or not plugin:
        return None
    try:
        return plugin.strip().lower(), int(ident.strip(), 16)
    except ValueError:
        return None


def _entry(key: str, value: object) -> NameEntry:
    if not isinstance(value, dict):
        raise NamesFileError(f"entry {key!r} must be an object")
    for f in ("edid", "name", "type"):
        if f in value and not isinstance(value[f], str):
            raise NamesFileError(f"entry {key!r}: field {f!r} must be a string")
    return NameEntry(value.get("edid", ""), value.get("name", ""), value.get("type", ""))


class NameBook:
    def __init__(self, user: dict[str, object] | None = None):
        self._by_key: dict[tuple[str, int], NameEntry] = {}
        for src in (BUILTIN, user or {}):          # user entries override built-ins
            for k, v in src.items():
                if k.startswith("_"):              # exporter metadata, e.g. "_meta"
                    continue
                nk = normalize_key(k)
                if nk is None:
                    raise NamesFileError(f"bad key {k!r}: expected '<Plugin>:<hex id>'")
                self._by_key[nk] = _entry(k, v)
        self.user_entries = len(user or {})

    @classmethod
    def load(cls, path: str | None) -> "NameBook":
        if not path:
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except OSError as e:
            raise NamesFileError(f"cannot read names file {path}: {e}") from e
        except json.JSONDecodeError as e:
            raise NamesFileError(f"names file {path} is not valid JSON: {e}") from e
        if not isinstance(data, dict):
            raise NamesFileError("names file must be a JSON object")
        return cls(data)

    def lookup(self, described: str | None) -> NameEntry | None:
        """``described`` is a ``plugin:id`` string as rendered by describe_form_id."""
        if not described:
            return None
        nk = normalize_key(described)
        e = self._by_key.get(nk) if nk else None
        return e if e is not None and e.label else None

    def label(self, described: str | None) -> str:
        """Name (or editor id) if known, otherwise the raw ``plugin:id`` in backticks."""
        if described is None:
            return "unresolved"
        e = self.lookup(described)
        return e.label if e else f"`{described}`"
