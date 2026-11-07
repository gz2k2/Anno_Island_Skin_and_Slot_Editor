"""Persist and validate user-defined River Slot GUID pairs.

This module owns the JSON format stored beside the application configuration.
Writes are atomic so invalid or interrupted updates cannot replace the last
valid list.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from app.config.config_slot import (
    MINE_CAVE_GUID,
    MINE_SLOT_GUIDS,
    MINE_WORKAREA_GUID,
    BUILTIN_SINGLE_SLOT_GUIDS,
    RIVER_GUID_FAMILIES,
)


def custom_river_slots_path(config_file: str | Path) -> Path:
    """Return the River Slot list path beside the supplied application config."""
    return Path(config_file).expanduser().resolve().parent / "config_custom_riverslots.json"


def _migrate_legacy_river_slots(path: Path) -> None:
    if path.exists():
        return
    for filename in ("config_riverslots.json", "custom_river_slots.json"):
        legacy_path = path.with_name(filename)
        if not legacy_path.is_file():
            continue
        try:
            os.replace(legacy_path, path)
            return
        except OSError:
            continue


def validate_custom_river_slots(
    rows: object, additional_reserved_guids=(),
) -> list[dict[str, str]]:
    """Validate named River Slot pairs and return normalized records.

    Each record must contain a unique name and two distinct positive numeric
    GUIDs. GUIDs may not collide with configured built-in or personal families.
    """
    if not isinstance(rows, list):
        raise ValueError("River Slots must be a list.")

    reserved_guids = {
        str(guid)
        for family_name, family in RIVER_GUID_FAMILIES.items()
        if not family_name.startswith("custom:")
        for guid in (family["primary"], family["workarea"])
    }
    reserved_guids.update(str(guid) for guid in BUILTIN_SINGLE_SLOT_GUIDS | MINE_SLOT_GUIDS)
    reserved_guids.update((str(MINE_WORKAREA_GUID), str(MINE_CAVE_GUID)))
    reserved_guids.update(str(guid) for guid in additional_reserved_guids)
    names: set[str] = set()
    used_guids = set(reserved_guids)
    result = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Invalid River Slot record at row {index}.")
        fields = ("name", "river_slot_guid", "work_area_guid")
        if any(not isinstance(row.get(field), str) or not row[field].strip() for field in fields):
            raise ValueError(f"Name, RiverSlot and Work Area GUIDs are required (row {index}).")
        record = {field: row[field].strip() for field in fields}
        name_key = record["name"].casefold()
        if name_key in names:
            raise ValueError(f"Duplicate River Slot name at row {index}.")
        names.add(name_key)
        for field, label in (("river_slot_guid", "RiverSlot"), ("work_area_guid", "Work Area")):
            guid = record[field]
            if not guid.isdigit() or int(guid) <= 0:
                raise ValueError(f"{label} GUID must be a positive numeric GUID (row {index}).")
            if guid in used_guids:
                raise ValueError(f"GUID {guid} is already used by another slot (row {index}).")
            used_guids.add(guid)
        result.append(record)
    return result


def load_custom_river_slots(config_file: str | Path) -> list[dict[str, str]]:
    """Load and validate River Slot entries, returning an empty list if absent."""
    path = custom_river_slots_path(config_file)
    _migrate_legacy_river_slots(path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Unsupported custom River Slots file format.")
    return validate_custom_river_slots(data.get("river_slots"))


def save_custom_river_slots(
    config_file: str | Path, rows: object,
) -> Path:
    """Validate and atomically save River Slot entries beside the config file."""
    records = validate_custom_river_slots(rows)
    path = custom_river_slots_path(config_file)
    _migrate_legacy_river_slots(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix="custom_river_slots_", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"schema": 1, "river_slots": records}, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path