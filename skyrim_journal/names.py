"""Form id naming.

The save stores form ids, not names. A names file is a JSON object mapping
``"<PluginFileName>:<hex local id>"`` (the format ``refs.describe_form_id`` renders; plugin
name is case-insensitive, the id may have any number of leading zeros) to
``{"edid": "...", "name": "...", "type": "QUST"}``. All three fields are optional; ``name`` is
shown, falling back to ``edid``.

Newer exports add optional fields: PERK ``playable``/``hidden``/``next`` (key of the next rank),
QUST ``quest_type``/``objectives``/``complete_stages``/``fail_stages`` (and, from exporter 1.2,
``objective_text``: ``{"<objective index>": "<display text>"}``), and a top-level
``_perk_trees`` object (see ``NameBook.perk_trees``). Other keys starting with ``_`` are
exporter metadata and are ignored.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field


class NamesFileError(ValueError):
    pass


@dataclass(frozen=True)
class NameEntry:
    edid: str = ""
    name: str = ""
    type: str = ""
    # PERK
    playable: bool | None = None
    hidden: bool | None = None
    next: str | None = None
    # QUST (None = the names file predates these fields)
    quest_type: int | None = None
    objectives: int | None = None
    complete_stages: tuple[int, ...] | None = None
    fail_stages: tuple[int, ...] | None = None
    objective_text: dict[int, str] | None = field(default=None, compare=False)

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
    extra: dict[str, object] = {}
    for f in ("playable", "hidden"):
        if f in value:
            if not isinstance(value[f], bool):
                raise NamesFileError(f"entry {key!r}: field {f!r} must be true or false")
            extra[f] = value[f]
    if "next" in value:
        if not isinstance(value["next"], str):
            raise NamesFileError(f"entry {key!r}: field 'next' must be a string")
        extra["next"] = value["next"]
    for f in ("quest_type", "objectives"):
        if f in value:
            if not isinstance(value[f], int) or isinstance(value[f], bool):
                raise NamesFileError(f"entry {key!r}: field {f!r} must be an integer")
            extra[f] = value[f]
    for f in ("complete_stages", "fail_stages"):
        if f in value:
            extra[f] = _int_list(key, f, value[f])
    if "objective_text" in value:
        extra["objective_text"] = _objective_text(key, value["objective_text"])
    return NameEntry(value.get("edid", ""), value.get("name", ""), value.get("type", ""), **extra)


@dataclass(frozen=True)
class PerkTree:
    key: str
    skill: str          # AVIF editor id
    skill_name: str     # AVIF display name (may be empty)
    perks: tuple[str, ...]


def _objective_text(key: str, v: object) -> dict[int, str]:
    if not isinstance(v, dict) or not all(isinstance(t, str) for t in v.values()):
        raise NamesFileError(f"entry {key!r}: field 'objective_text' must map objective "
                             "indexes to strings")
    try:
        return {int(i): t for i, t in v.items()}
    except ValueError:
        raise NamesFileError(f"entry {key!r}: field 'objective_text' has a non-numeric "
                             "objective index") from None


def _int_list(key: str, f: str, v: object) -> tuple[int, ...]:
    if not isinstance(v, list) or not all(isinstance(x, int) and not isinstance(x, bool) for x in v):
        raise NamesFileError(f"entry {key!r}: field {f!r} must be a list of integers")
    return tuple(v)


def _perk_trees(raw: object) -> dict[str, PerkTree]:
    if not isinstance(raw, dict):
        raise NamesFileError("'_perk_trees' must be an object")
    out = {}
    for k, v in raw.items():
        if not isinstance(v, dict) or not isinstance(v.get("perks"), list) \
                or not all(isinstance(p, str) for p in v["perks"]):
            raise NamesFileError(f"'_perk_trees' entry {k!r}: expected an object with a 'perks' "
                                 "list of keys")
        out[k] = PerkTree(k, str(v.get("skill") or ""), str(v.get("skill_name") or ""),
                          tuple(v["perks"]))
    return out


class NameBook:
    def __init__(self, user: dict[str, object] | None = None):
        self._by_key: dict[tuple[str, int], NameEntry] = {}
        self._trees: dict[str, PerkTree] = {}
        for src in (BUILTIN, user or {}):          # user entries override built-ins
            for k, v in src.items():
                if k == "_perk_trees":
                    self._trees = _perk_trees(v)
                    continue
                if k.startswith("_"):              # exporter metadata, e.g. "_meta"
                    continue
                nk = normalize_key(k)
                if nk is None:
                    raise NamesFileError(f"bad key {k!r}: expected '<Plugin>:<hex id>'")
                self._by_key[nk] = _entry(k, v)
        self.user_entries = len(user or {})
        self._by_edid: dict[tuple[str, str], list[tuple[str, int]]] | None = None

    @property
    def has_perk_trees(self) -> bool:
        return bool(self._trees)

    def perk_trees(self) -> list[PerkTree]:
        """Skill perk trees from the exporter's ``_perk_trees`` (empty if absent)."""
        return list(self._trees.values())

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

    def find_by_edid(self, edid: str, type: str) -> list[tuple[str, int]]:
        """(lower-case plugin, local id) of every ``type`` entry with this editor id
        (case-insensitive), in names-file order."""
        if self._by_edid is None:
            self._by_edid = {}
            for (plugin, ident), e in self._by_key.items():
                if e.edid:
                    self._by_edid.setdefault((e.type, e.edid.lower()), []).append((plugin, ident))
        return list(self._by_edid.get((type, edid.lower()), []))

    def entry(self, key: str) -> NameEntry | None:
        """Entry for a ``plugin:id`` key even if it has no name or edid."""
        nk = normalize_key(key) if key else None
        return self._by_key.get(nk) if nk else None

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
