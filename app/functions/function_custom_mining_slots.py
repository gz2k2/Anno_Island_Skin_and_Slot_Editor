
"""Persist and validate user-defined custom Mining Slots."""
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


def custom_mining_slots_path(config_file: str | Path) -> Path:
    """Return the custom Mining Slot path beside the application config."""
    return Path(config_file).expanduser().resolve().parent / "config_custom_mining_slots.json"


def validate_custom_mining_slots(rows: object, reserved_guids=()) -> list[dict[str, str]]:
    """Validate named Mining Slots with Slot, Cave and outer Work Area GUIDs."""
    if not isinstance(rows, list):
        raise ValueError("Custom Mining Slots must be a list.")
    reserved = set(BUILTIN_SINGLE_SLOT_GUIDS)
    reserved.update(str(guid) for guid in MINE_SLOT_GUIDS)
    reserved.update((str(MINE_CAVE_GUID), str(MINE_WORKAREA_GUID)))
    reserved.update(str(guid) for guid in reserved_guids)
    names = {name.casefold() for name in BUILTIN_SLOT_NAMES}
    used_guids = reserved.copy()
    result = []
    fields = (
        ("guid", "Slot GUID"),
        ("work_area_1_guid", "Work Area 1 (Cave) GUID"),
        ("work_area_2_guid", "Work Area 2 GUID"),
    )
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"Invalid Custom Mining Slot at row {index}.")
        name = str(row.get("name", "")).strip()
        if not name:
            raise ValueError(f"Name is required (row {index}).")
        name_key = name.casefold()
        if name_key in names:
            raise ValueError(f"Duplicate or reserved Mining Slot name at row {index}.")
        names.add(name_key)
        record = {"name": name}
        for field, label in fields:
            guid = str(row.get(field, "")).strip()
            if not guid.isdigit() or int(guid) <= 0:
                raise ValueError(f"{label} must be a positive numeric GUID (row {index}).")
            if guid in used_guids:
                raise ValueError(f"GUID {guid} is already used by another slot (row {index}).")
            used_guids.add(guid)
            record[field] = guid
        result.append(record)
    return result


def load_custom_mining_slots(config_file: str | Path) -> list[dict[str, str]]:
    """Load and validate custom single slots, returning an empty list if absent."""
    path = custom_mining_slots_path(config_file)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("schema") != 1:
        raise ValueError("Unsupported Custom Mining Slots file format.")
    return validate_custom_mining_slots(data.get("mining_slots"))


def save_custom_mining_slots(config_file: str | Path, rows: object) -> Path:
    """Validate and atomically save custom single slots beside config.ini."""
    records = validate_custom_mining_slots(rows)
    path = custom_mining_slots_path(config_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix="custom_mining_slots_", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"schema": 1, "mining_slots": records}, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path
