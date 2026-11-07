"""Persist and validate user-defined single Island Slots."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from app.config.config_slot import (
    BUILTIN_SINGLE_SLOT_GUIDS,
    BUILTIN_SLOT_NAMES,
    MINE_CAVE_GUID,
    MINE_SLOT_GUIDS,
    MINE_WORKAREA_GUID,
    RIVER_GUID_FAMILIES,
)


def custom_slots_path(config_file: str | Path) -> Path:
    """Return the custom single-slot path beside the application config."""
    return Path(config_file).expanduser().resolve().parent / "config_custom_slots.json"


def validate_custom_slots(rows: object, reserved_guids=()) -> list[dict[str, str]]:
    """Validate named single-slot GUIDs and return normalized records."""
    if not isinstance(rows, list):
        raise ValueError("Custom Slots must be a list.")

    reserved = set(BUILTIN_SINGLE_SLOT_GUIDS)
    reserved.update(str(guid) for guid in MINE_SLOT_GUIDS)
    reserved.update((str(MINE_CAVE_GUID), str(MINE_WORKAREA_GUID)))
    reserved.update(
        str(guid)
        for family_name, family in RIVER_GUID_FAMILIES.items()
        if not family_name.startswith("custom:")
        for guid in (family["primary"], family["workarea"])
    )
    reserved.update(str(guid) for guid in reserved_guids)

    names = {name.casefold() for name in BUILTIN_SLOT_NAMES}
    used_guids = reserved.copy()
    result = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Invalid Custom Slot at row {index}.")
        name = row.get("name")
        guid = row.get("guid")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Name is required (row {index}).")
        if not isinstance(guid, str) or not guid.strip():
            raise ValueError(f"GUID is required (row {index}).")
        record = {"name": name.strip(), "guid": guid.strip()}
        name_key = record["name"].casefold()
        if name_key in names:
            raise ValueError(f"Duplicate or reserved Slot name at row {index}.")
        names.add(name_key)
        if not record["guid"].isdigit() or int(record["guid"]) <= 0:
            raise ValueError(f"GUID must be a positive numeric GUID (row {index}).")
        if record["guid"] in used_guids:
            raise ValueError(f"GUID {record['guid']} is already used by another slot (row {index}).")
        used_guids.add(record["guid"])
        result.append(record)
    return result


def load_custom_slots(config_file: str | Path) -> list[dict[str, str]]:
    """Load and validate custom single slots, returning an empty list if absent."""
    path = custom_slots_path(config_file)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Unsupported Custom Slots file format.")
    return validate_custom_slots(data.get("slots"))


def save_custom_slots(config_file: str | Path, rows: object) -> Path:
    """Validate and atomically save custom single slots beside config.ini."""
    records = validate_custom_slots(rows)
    path = custom_slots_path(config_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix="custom_slots_", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"schema": 1, "slots": records}, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path
