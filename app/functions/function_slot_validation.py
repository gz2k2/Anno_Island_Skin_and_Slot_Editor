"""Pure XML validation and export gate for island slot integration.

This module intentionally has no Tk dependency. It validates single resource slots
and paired river slots before patched XML is installed or exported.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import math
import app.backend.xml_backend as ET
from app.config.config_slot import RIVER_GUID_FAMILIES, RIVER_GUID_ROLE, SINGLE_SLOT_GUIDS


@dataclass
class SlotGateReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    river_pairs: list[tuple[str, str, str]] = field(default_factory=list)
    checked_map_entries: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def require_ok(self) -> "SlotGateReport":
        if self.errors:
            raise ValueError("Slot validation failed:\n- " + "\n- ".join(self.errors))
        return self


def local_tag(node):
    return node.tag.rsplit("}", 1)[-1] if isinstance(node.tag, str) else ""


def direct(node, name):
    target = name.casefold()
    return next((child for child in list(node) if local_tag(child).casefold() == target), None)


def direct_text(node, name, default=""):
    child = direct(node, name)
    return (child.text or "").strip() if child is not None else default


def parse_position(value):
    parts = (value or "").replace(";", " ").split()
    if len(parts) != 3:
        raise ValueError(f"Position must contain three values: {value!r}")
    result = tuple(float(part.replace(",", ".")) for part in parts)
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"Position contains non-finite values: {value!r}")
    return result


def close_position(a, b, tolerance=0.05):
    return all(abs(x - y) <= tolerance for x, y in zip(a, b))


def game_records(root):
    records = {}
    for parent in root.iter():
        for node in list(parent):
            object_id = direct_text(node, "ID")
            guid = direct_text(node, "guid")
            position = direct_text(node, "Position")
            if not (object_id and guid and position):
                continue
            if object_id in records:
                raise ValueError(f"Duplicate Gamedata ID {object_id}.")
            records[object_id] = {
                "id": object_id,
                "guid": guid,
                "position": parse_position(position),
                "folder": direct_text(node, "ObjectFolderID"),
                "node": node,
            }
    return records


def map_records(root):
    records = {}
    category = None
    slot_blocks = [node for node in root.iter() if local_tag(node) == "SlotObjects"]
    if len(slot_blocks) != 1:
        raise ValueError(f"Expected exactly one SlotObjects block, found {len(slot_blocks)}.")
    for block in list(slot_blocks[0]):
        value = direct(block, "value")
        if value is not None:
            category = direct_text(value, "id")
            continue
        for node in list(block):
            object_id = direct_text(node, "ObjectId")
            if not object_id:
                continue
            record = {
                "id": object_id,
                "guid": direct_text(node, "ObjectGuid"),
                "position": parse_position(direct_text(node, "Position")),
                "category": category,
                "node": node,
            }
            previous = records.get(object_id)
            if previous and (previous["guid"], previous["position"], previous["category"]) != (record["guid"], record["position"], record["category"]):
                raise ValueError(f"Conflicting duplicate MapName ObjectId {object_id}.")
            records.setdefault(object_id, record)
    return records


def bezier_points(node):
    points = []
    for child in node.iter():
        if local_tag(child) == "p" and (child.text or "").strip():
            points.append(parse_position(child.text))
    return points


def bezier_bounds(node):
    minimum = next((parse_position(child.text) for child in node.iter() if local_tag(child) == "Minimum" and (child.text or "").strip()), None)
    maximum = next((parse_position(child.text) for child in node.iter() if local_tag(child) == "Maximum" and (child.text or "").strip()), None)
    return minimum, maximum


def has_bezier(node):
    return any(local_tag(child) == "BezierCurve" for child in node.iter())


def bounds_contain(points, minimum, maximum, tolerance=0.05):
    return minimum is not None and maximum is not None and all(
        minimum[i] - tolerance <= point[i] <= maximum[i] + tolerance
        for point in points for i in range(3)
    )


def _structural_custom_match(primary, workarea):
    points = bezier_points(workarea["node"])
    if len(points) < 2:
        return False
    endpoints = (points[0], points[-1])
    return (
        (close_position(endpoints[0], workarea["position"]) and close_position(endpoints[1], primary["position"]))
        or (close_position(endpoints[1], workarea["position"]) and close_position(endpoints[0], primary["position"]))
    )


def resolve_river_pairs(game, map_data, report=None):
    """Resolve usable River pairs without validating or reporting River findings."""
    pairs = []
    used = set()
    for family_name, family in RIVER_GUID_FAMILIES.items():
        primaries = [record for record in game.values() if record["guid"] == family["primary"]]
        workareas = [record for record in game.values() if record["guid"] == family["workarea"]]
        for primary in primaries:
            if family.get("folder_pairing") and primary["folder"]:
                matches = [
                    work for work in workareas
                    if work["folder"] == primary["folder"] and work["id"] not in used
                ]
            else:
                folder_matches = [
                    work for work in workareas
                    if primary["folder"] and work["folder"] == primary["folder"]
                    and work["id"] not in used
                ]
                matches = folder_matches if len(folder_matches) == 1 else [
                    work for work in workareas
                    if work["id"] not in used and _structural_custom_match(primary, work)
                ]
            if len(matches) != 1:
                continue
            work = matches[0]
            used.update((primary["id"], work["id"]))
            if primary["id"] in map_data and work["id"] in map_data:
                pairs.append((primary["id"], work["id"], family_name))
    return pairs


def validate_native_deposit(record, report):
    """Validate the runtime fields required by the working C# deposit templates."""
    node = record["node"]
    object_id = record["id"]
    guid = record["guid"]
    if direct_text(node, "ObjectFolderID") != "0":
        report.errors.append(f"Native deposit {object_id} ({guid}) must use ObjectFolderID 0.")
    participant = direct(node, "ParticipantID")
    if participant is None or direct_text(participant, "id") != "8":
        report.errors.append(f"Native deposit {object_id} ({guid}) must use ParticipantID 8.")
    mesh = direct(node, "Mesh")
    flags = direct(mesh, "Flags") if mesh is not None else None
    sequence = direct(mesh, "SequenceData") if mesh is not None else None
    if flags is None or direct_text(flags, "flags") != "1":
        report.errors.append(f"Native deposit {object_id} ({guid}) must use Mesh/Flags/flags 1.")
    if sequence is None or direct_text(sequence, "CurrentSequenceStartTime") != "0":
        report.errors.append(f"Native deposit {object_id} ({guid}) must use CurrentSequenceStartTime 0.")
    for component in ("Blocking", "Building", "QuestObject", "Infolayer", "RandomMapObject", "Selection", "SoundEmitter"):
        if direct(node, component) is None:
            report.errors.append(f"Native deposit {object_id} ({guid}) is missing <{component}>.")
    sound = direct(node, "SoundEmitter")
    if sound is not None and direct_text(sound, "TimeBudget") != "500":
        report.errors.append(f"Native deposit {object_id} ({guid}) must use SoundEmitter/TimeBudget 500.")

def validate_slot_trees(map_root, game_root, strict_deposit_ids=None) -> SlotGateReport:
    report = SlotGateReport()
    strict_deposit_ids = {str(value) for value in (strict_deposit_ids or ())}
    try:
        game = game_records(game_root)
        mapped = map_records(map_root)
    except ValueError as exc:
        report.errors.append(str(exc))
        return report
    report.checked_map_entries = len(mapped)

    # Cross-file integrity applies uniformly to every object listed in MapName
    # SlotObjects, including River primary/work-area objects. River-specific
    # pair/category/Bezier validation remains disabled.
    for object_id, entry in mapped.items():
        record = game.get(object_id)
        if record is None:
            report.errors.append(f"MapName ObjectId {object_id} has no Gamedata object.")
            continue
        if record["guid"] != entry["guid"]:
            report.errors.append(
                f"GUID mismatch for ObjectId {object_id}: "
                f"MapName {entry['guid']} / Gamedata {record['guid']}."
            )
        if not close_position(record["position"], entry["position"], tolerance=0.000001):
            report.errors.append(f"Position mismatch for ObjectId {object_id}.")
        if entry["guid"] in SINGLE_SLOT_GUIDS and entry["category"] != "1":
            report.errors.append(
                f"Single resource slot {object_id} ({entry['guid']}) must be in category 1."
            )
        # Original game files legitimately contain several runtime variants of
        # GUID 100417/100849. Enforce the canonical creation template only for
        # deposits generated in the current editing session.
        if object_id in strict_deposit_ids and entry["guid"] in {"100417", "100849"}:
            validate_native_deposit(record, report)

    # Detect the reverse missing-counterpart case for known slot families. The
    # complete Gamedata also contains many non-slot objects, so only configured
    # slot GUIDs can be checked safely in this direction.
    river_guids = {
        str(guid)
        for family in RIVER_GUID_FAMILIES.values()
        for guid in (family["primary"], family["workarea"])
    }
    known_slot_guids = {str(guid) for guid in SINGLE_SLOT_GUIDS} | river_guids
    for object_id, record in game.items():
        if record["guid"] in known_slot_guids and object_id not in mapped:
            report.errors.append(
                f"Gamedata ObjectId {object_id} ({record['guid']}) has no MapName object."
            )

    # Metadata-only River pairing. This emits no River errors or warnings.
    report.river_pairs = resolve_river_pairs(game, mapped, report)
    return report


def validate_slot_export_files(map_path, game_path) -> SlotGateReport:
    map_root = ET.parse(Path(map_path)).getroot()
    game_root = ET.parse(Path(game_path)).getroot()
    return validate_slot_trees(map_root, game_root)

VALID_GATE_STAGES = frozenset({"save", "finalize", "pack"})


def validate_slot_gate(stage, map_path, game_path) -> SlotGateReport:
    """Run the same strict file gate at Save, Finalize or Pack boundaries."""
    stage = str(stage).strip().casefold()
    if stage not in VALID_GATE_STAGES:
        raise ValueError(f"Unknown slot gate stage {stage!r}; expected save, finalize or pack.")
    try:
        report = validate_slot_export_files(map_path, game_path)
    except (OSError, ET.ParseError, UnicodeError, ValueError) as exc:
        report = SlotGateReport(errors=[f"{stage.capitalize()} gate could not read slot XML: {exc}"])
    if report.errors:
        report.errors = [f"[{stage}] {error}" for error in report.errors]
    if report.warnings:
        report.warnings = [f"[{stage}] {warning}" for warning in report.warnings]
    return report
