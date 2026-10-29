from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import secrets
import math
import statistics
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import app.backend.xml_backend as ET
from app.config.config_slot import (
    RIVER_GUID_FAMILIES,
    RIVER_GUID_ROLE,
    SINGLE_SLOT_GUIDS,
    NATIVE_DEPOSIT_SLOT_NAMES,
    MINE_WORKAREA_GUID, MINE_SLOT_GUIDS,
    MINE_WORKAREA_GROUP, MINE_PRIMARY_GROUP,
    MINE_MIN_DISTANCE, MINE_MAX_DISTANCE,
    SLOT_DEFINITIONS,
    TEMPLATE_METADATA,
    template_element,
    river_pair,
)


from app.functions.function_place_object import world_from_click
from app.functions.function_slot_validation import validate_slot_trees
from app.templates.template_map_view import MapViewTemplate
from app.templates.template_popup import PopupTemplate
from app.templates.template_statuswindow import StatusWindowTemplate

class SlotSaveCancelled(Exception):
    """Internal control flow: the user closed/cancelled the save review."""


RIVERSLOT_DONT_USE_ORIENTATIONS = {
    "→": 0,
    "↑": 90,
    "←": 180,
    "↓": -90,
}

# Test object: use the native Clay template, but write River GUID 117741.
# This is intentionally a single object without the normal Riverslot work-area.
RIVER_TEST_ORIENTATIONS = {
    "→": 0,
    "↑": 90,
    "←": 180,
    "↓": -90,
}

# MineSlot arrows are rendered 90 degrees counter-clockwise in the Slot Map.
# Feed the inverse 90-degree offset into creation so each menu icon matches
# the arrow that will be displayed afterwards. Riverslot uses its own mapping.
MINE_MENU_ORIENTATIONS = {
    "→": -90,
    "↑": 0,
    "←": 90,
    "↓": 180,
}

MINE_SLOT_VARIANTS = (
    ("MineSlot (OW, NW Gold)", "1000029"),
    ("MineSlot (NW)", "614"),
    ("MineSlot (Arctic)", "116037"),
)

SLOT_MULTI_INSERT_SPACING = 8.0


def tag(node):
    return node.tag.rsplit("}", 1)[-1] if isinstance(node.tag, str) else ""


def direct(node, name):
    return next((child for child in list(node) if tag(child).lower() == name.lower()), None)


def text(node, name, default=""):
    child = direct(node, name)
    return (child.text or "").strip() if child is not None else default


def set_text(node, name, value):
    child = direct(node, name)
    if child is None:
        raise ValueError(f"Slot template is missing <{name}>.")
    child.text = str(value)


def replace_exact_text(node, replacements):
    """Replace cloned source IDs wherever a child stores the exact scalar value."""
    for child in node.iter():
        value = (child.text or "").strip()
        if value in replacements:
            child.text = replacements[value]


def parse_position(value):
    parts = (value or "").replace(";", " ").split()
    if len(parts) < 3:
        raise ValueError(f"Invalid position: {value!r}")
    return tuple(float(part.replace(",", ".")) for part in parts[:3])


def game_number(value):
    if abs(value) < 0.0000001:
        value = 0.0
    return format(value, ".9g").replace(".", ",")


def format_position(values):
    return " ".join(game_number(value) for value in values)


def object_records(root):
    records = []
    for parent in root.iter():
        for node in list(parent):
            guid, object_id, pos = text(node, "guid"), text(node, "ID"), text(node, "Position")
            if guid and object_id and pos:
                try:
                    parsed = parse_position(pos)
                except ValueError:
                    continue
                records.append({"parent": parent, "node": node, "guid": guid, "id": object_id,
                                "position": parsed, "folder": text(node, "ObjectFolderID")})
    return records



def game_object_container(root):
    """Return the exact native <GameObject>/<objects> runtime container."""
    for game_object in root.iter():
        if tag(game_object) == "GameObject":
            result = direct(game_object, "objects")
            if result is not None:
                return result
    raise ValueError("Gamedata XML has no <GameObject>/<objects> container.")


def prepare_native_deposit(clone, object_id, position):
    """Apply the same normalization as C# DepositSlotService.Add()."""
    set_text(clone, "ID", object_id)
    set_text(clone, "ObjectFolderID", "0")
    set_text(clone, "Position", format_position(position))
    mesh = direct(clone, "Mesh")
    sequence = direct(mesh, "SequenceData") if mesh is not None else None
    start = direct(sequence, "CurrentSequenceStartTime") if sequence is not None else None
    if start is None:
        raise ValueError("Native deposit template lacks CurrentSequenceStartTime.")
    start.text = "0"
    return clone

def object_container(root):
    candidates = []
    for parent in root.iter():
        count = sum(bool(text(node, "guid") and text(node, "ID") and text(node, "Position")) for node in list(parent))
        if count:
            candidates.append((count, parent))
    if not candidates:
        raise ValueError("No compatible Gamedata object container was found.")
    return max(candidates, key=lambda item: item[0])[1]


def all_ids(map_root, game_root):
    used = {record["id"] for record in object_records(game_root)}
    used.update((node.text or "").strip() for node in map_root.iter()
                if tag(node) == "ObjectId" and (node.text or "").strip())
    return used


def new_unique_id(used):
    for _ in range(10000):
        value = str(-secrets.randbelow((1 << 63) - 1) - 1)
        if value not in used:
            used.add(value)
            return value
    raise RuntimeError("Could not allocate a unique signed 64-bit object ID.")


def allocate_verified_unique_id(map_root, game_root, used):
    """Allocate an ID and verify it against both live XML trees before use."""
    for _ in range(10000):
        candidate = new_unique_id(used)
        in_map = any(
            (node.text or "").strip() == candidate
            for node in map_root.iter()
            if tag(node) == "ObjectId"
        )
        in_game = any(record["id"] == candidate for record in object_records(game_root))
        if not in_map and not in_game:
            return candidate
    raise RuntimeError("Could not allocate a verified unique signed 64-bit object ID.")


def new_folder_id(records):
    values = [int(record["folder"]) for record in records if record["folder"].lstrip("-").isdigit()]
    return str(max(values, default=0) + 1)


def slot_objects(root, create=False):
    result = next((node for node in root.iter() if tag(node) == "SlotObjects"), None)
    if result is None and create:
        metadata = next((node for node in root.iter() if tag(node) == "ObjectMetaInfo"), None)
        if metadata is None:
            metadata = ET.Element("ObjectMetaInfo")
            append_pretty(root, metadata)
        result = ET.Element("SlotObjects")
        append_pretty(metadata, result)
    return result


def map_group_container(root, group_id, create=False):
    slots = slot_objects(root, create=create)
    if slots is None:
        raise ValueError("MapName XML has no <SlotObjects> container.")
    children = list(slots)
    for index, block in enumerate(children):
        value = direct(block, "value")
        if value is not None and text(value, "id") == str(group_id):
            if index + 1 < len(children) and direct(children[index + 1], "value") is None:
                return children[index + 1]
            if create:
                container = ET.Element("None")
                insert_pretty(slots, index + 1, container)
                return container
    if not create:
        raise ValueError(f"MapName SlotObjects group {group_id} was not found.")
    header = ET.Element("None")
    value = ET.SubElement(header, "value")
    ET.SubElement(value, "id").text = str(group_id)
    append_pretty(slots, header)
    container = ET.Element("None")
    append_pretty(slots, container)
    return container


def _xml_indent_parts(parent):
    """Infer child and closing indentation for populated and empty parents."""
    children = list(parent)
    if children:
        child_indent = parent.text if parent.text and "\n" in parent.text else None
        closing_indent = (
            children[-1].tail
            if children[-1].tail and "\n" in children[-1].tail else None
        )
        if child_indent is None:
            own_space = (parent.tail or "\n").rsplit("\n", 1)[-1]
            child_indent = "\n" + own_space + "  "
        if closing_indent is None:
            child_space = child_indent.rsplit("\n", 1)[-1]
            closing_indent = "\n" + child_space[:-2]
    else:
        # In an empty parsed element, parent.text is usually the whitespace before
        # its closing tag, not the indentation of a child that does not yet exist.
        own_space = ""
        if parent.tail and "\n" in parent.tail:
            own_space = parent.tail.rsplit("\n", 1)[-1]
        elif parent.text and "\n" in parent.text:
            own_space = parent.text.rsplit("\n", 1)[-1]
        child_indent = "\n" + own_space + "  "
        closing_indent = "\n" + own_space
    child_space = child_indent.rsplit("\n", 1)[-1]
    closing_space = closing_indent.rsplit("\n", 1)[-1]
    unit = child_space[len(closing_space):] if child_space.startswith(closing_space) else "  "
    return child_indent, closing_indent, unit or "  "


def _format_new_subtree(node, node_indent, unit):
    """Add line breaks inside one newly generated subtree only."""
    children = list(node)
    if not children:
        return
    child_indent = node_indent + unit
    node.text = "\n" + child_indent
    for index, child in enumerate(children):
        _format_new_subtree(child, child_indent, unit)
        child.tail = "\n" + (node_indent if index == len(children) - 1 else child_indent)


def append_pretty(parent, node):
    """Append a generated node using the surrounding XML's whitespace style."""
    child_indent_text, closing_indent_text, unit = _xml_indent_parts(parent)
    child_indent = child_indent_text.rsplit("\n", 1)[-1]
    children = list(parent)
    if children:
        children[-1].tail = child_indent_text
    elif not parent.text or not parent.text.strip():
        parent.text = child_indent_text
    _format_new_subtree(node, child_indent, unit)
    node.tail = closing_indent_text
    parent.append(node)
    return node


def insert_pretty(parent, index, node):
    """Insert a generated node between siblings while preserving line breaks."""
    child_indent_text, closing_indent_text, unit = _xml_indent_parts(parent)
    child_indent = child_indent_text.rsplit("\n", 1)[-1]
    children = list(parent)
    _format_new_subtree(node, child_indent, unit)
    if index < len(children):
        node.tail = child_indent_text
    else:
        if children:
            children[-1].tail = child_indent_text
        node.tail = closing_indent_text
    parent.insert(index, node)
    return node


def append_map_entry(root, group_id, object_id, guid, pos):
    container = map_group_container(root, group_id, create=True)
    item = ET.Element("None")
    ET.SubElement(item, "ObjectId").text = object_id
    ET.SubElement(item, "ObjectGuid").text = guid
    ET.SubElement(item, "Position").text = pos
    append_pretty(container, item)


def remove_map_ids(root, ids):
    removed = 0
    for parent in root.iter():
        for node in list(parent):
            if text(node, "ObjectId") in ids:
                parent.remove(node)
                removed += 1
    return removed


def remove_game_ids(root, ids):
    """Remove complete Gamedata object records whose direct <ID> is selected."""
    removed = 0
    ids = set(ids)
    for parent in root.iter():
        for node in list(parent):
            if text(node, "ID") in ids and text(node, "guid"):
                parent.remove(node)
                removed += 1
    return removed


def position_samples_from_xml(path, parser=None):
    path = Path(path)
    if not path.is_file():
        return []
    try:
        tree = parser(path)[0] if parser else ET.parse(path)
    except (OSError, ET.ParseError, UnicodeError, ValueError):
        return []
    samples = []
    for node in tree.getroot().iter():
        if tag(node) != "Position" or not (node.text or "").strip():
            continue
        try:
            sample = parse_position(node.text)
        except ValueError:
            continue
        if all(abs(value) < 1000000 for value in sample):
            samples.append(sample)
    return samples


def estimate_nearby_height(x, z, samples, max_radius=12.0, max_samples=8):
    nearby = []
    for sx, sy, sz in samples:
        distance = ((sx - x) ** 2 + (sz - z) ** 2) ** 0.5
        if distance <= max_radius:
            nearby.append((distance, sy))
    if not nearby:
        return None
    nearby.sort(key=lambda item: item[0])
    nearby = nearby[:max_samples]
    median = statistics.median(value for _, value in nearby)
    mad = statistics.median(abs(value - median) for _, value in nearby)
    tolerance = max(1.5, 3.5 * mad)
    filtered = [(distance, value) for distance, value in nearby if abs(value - median) <= tolerance]
    if not filtered:
        return None
    if filtered[0][0] < 0.001:
        return filtered[0][1]
    weighted = [(1.0 / max(distance * distance, 0.01), value) for distance, value in filtered]
    return sum(weight * value for weight, value in weighted) / sum(weight for weight, _ in weighted)



def rotate_clone_y(node, center, degrees):
    """Rotate all X/Z coordinates and object quaternions around the template anchor."""
    if not degrees:
        return
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    cx, _cy, cz = center
    for child in node.iter():
        if tag(child) in {"Position", "p", "Minimum", "Maximum"} and (child.text or "").strip():
            try:
                x, y, z = parse_position(child.text)
            except ValueError:
                continue
            rx, rz = x - cx, z - cz
            child.text = format_position((cx + rx * cosine - rz * sine, y, cz + rx * sine + rz * cosine))
        elif tag(child) == "Orientation" and (child.text or "").strip():
            values = (child.text or "").replace(",", ".").split()
            if len(values) != 4:
                continue
            try:
                qx, qy, qz, qw = map(float, values)
            except ValueError:
                continue
            half = angle / 2.0
            sy, cy = math.sin(half), math.cos(half)
            # Left-multiply by a world-space yaw quaternion (0, sy, 0, cy).
            nx = cy * qx + sy * qz
            ny = cy * qy + sy * qw
            nz = cy * qz - sy * qx
            nw = cy * qw - sy * qy
            child.text = " ".join(game_number(value) for value in (nx, ny, nz, nw))
        elif tag(child) == "Direction" and (child.text or "").strip():
            raw = (child.text or "").strip().replace(",", ".")
            try:
                current = float(raw)
            except ValueError:
                continue
            child.text = game_number((current + angle) % (2.0 * math.pi))


def relocate_clone(node, dx, dz, height_at):
    top = parse_position(text(node, "Position"))
    for child in node.iter():
        if tag(child) not in {"Position", "p", "Minimum", "Maximum"} or not (child.text or "").strip():
            continue
        try:
            ox, oy, oz = parse_position(child.text)
        except ValueError:
            continue
        nx, nz = ox + dx, oz + dz
        ground = height_at(nx, nz)
        ny = oy + (ground - top[1]) if ground is not None else oy
        child.text = format_position((nx, ny, nz))



def has_bezier_curve(node):
    return any(tag(child) == "BezierCurve" for child in node.iter())


def river_family_for_guid(guid):
    info = RIVER_GUID_ROLE.get(str(guid))
    return info[0] if info else None


def translate_bezier_world_geometry(node, dx, dy, dz):
    """Translate absolute Bezier positions/bounds; tangent vectors stay unchanged."""
    for child in node.iter():
        if tag(child) not in {"p", "Minimum", "Maximum"} or not (child.text or "").strip():
            continue
        x, y, z = parse_position(child.text)
        child.text = format_position((x + dx, y + dy, z + dz))


def validate_pair(map_root, game_root):
    """Compatibility wrapper around the shared validation/export gate."""
    report = validate_slot_trees(map_root, game_root)
    report.require_ok()
    return report.warnings


class IslandSlotEditingMixin:
    def _island_slot_init(self):
        if getattr(self, "_island_slot_initialized", False):
            return
        self._island_slot_initialized = True
        self.island_slot_selected_ids = set()
        self.island_slot_selection_start = None
        self.island_slot_selection_rect = None
        self.island_slot_selection_world_bounds = None
        self._island_slot_ram_game_tree = None
        self._island_slot_ram_map_tree = None
        self._island_slot_generated_deposit_ids = set()
        self._mine_placement = None

    def _island_slot_bind(self, canvas):
        """Compatibility hook; mouse bindings are owned by MapViewTemplate."""
        self._island_slot_init()

    def _island_slot_has_unsaved_changes(self):
        """Return True while the Slot Map owns an unsaved RAM working copy."""
        return bool(
            self._island_slot_ram_game_tree is not None
            or self._island_slot_ram_map_tree is not None
            or getattr(self, "_slot_map_pending_moves", {})
            or getattr(self, "_island_slot_generated_deposit_ids", set())
        )

    def _island_slot_discard_working_copy(self):
        """Discard every Slot Map edit/cache that must not survive popup close."""
        self._island_slot_ram_game_tree = None
        self._island_slot_ram_map_tree = None
        self._slot_map_pending_moves = {}
        self._island_slot_generated_deposit_ids.clear()
        self.island_slot_selected_ids.clear()
        self.island_slot_selection_start = None
        self.island_slot_selection_rect = None
        self.island_slot_selection_world_bounds = None
        self._island_slot_snapshot = None
        self._island_slot_cancel_mine_placement()

    def _island_slot_world(self, event):
        canvas = self.slot_map_canvas
        return MapViewTemplate.world_from_event(
            event, canvas, self.slot_map_bounds, self.slot_map_shared_zoom,
            self.slot_map_shared_pan_x, self.slot_map_shared_pan_y,
        )

    def _island_slot_nearest(self, event, radius=8):
        return MapViewTemplate.point_from_event(
            event,
            self.slot_map_screen_points,
            hover=(radius <= MapViewTemplate.HOVER_HIT_RADIUS),
            visible=lambda point: self.slot_map_guid_visible.get(point[3], True),
        )

    def _island_slot_popup_menu(self, event, hit=None):
        # Defensive initialization also makes direct/programmatic popup calls safe.
        self._island_slot_init()
        # Hidden GUID groups are removed from the interactive data set as well,
        # so stale rectangle selections can never remove invisible slots.
        visible_ids = {
            point[0] for point in self.slot_map_points
            if self.slot_map_guid_visible.get(point[1], True)
        }
        self.island_slot_selected_ids.intersection_update(visible_ids)
        entries = []
        issue = hit[8] if hit is not None and len(hit) > 8 else None
        if issue:
            entries.extend((
                {"label": f"Warning: {issue} (ObjectId: {hit[2]}, GUID: {hit[3]})", "state": "disabled"},
                {"kind": "separator"},
            ))
        if hit:
            entries.append({"label": "Remove Slot", "command": lambda h=hit: self._island_slot_remove_ids({h[2]})})
            if str(hit[3]) in RIVER_GUID_ROLE or str(hit[3]) in MINE_SLOT_GUIDS:
                entries.append({
                    "label": "Rotate",
                    "command": lambda h=hit: self._island_slot_rotate_90(h),
                })
        if self.island_slot_selected_ids:
            entries.append({
                "label": f"Remove selected ({len(self.island_slot_selected_ids)})",
                "command": lambda: self._island_slot_remove_ids(set(self.island_slot_selected_ids)),
            })
        if hit or self.island_slot_selected_ids:
            entries.append({"kind": "separator"})
        slot_entries = []
        for name in SLOT_DEFINITIONS:
            if name == "Riverslot":
                # The old paired Riverslot insertion is intentionally hidden.
                # Keep its implementation internally as Riverslot_dont_use only.
                continue
            slot_entries.append({
                "label": name,
                "command": lambda n=name, e=event: self._island_slot_add_at_event(e, n),
            })
        slot_entries.append({
            "kind": "cascade", "label": "Riverslot",
            "entries": [
                {
                    "label": label,
                    "command": lambda d=degrees, e=event: self._island_slot_add_riverslot_at_event(e, d),
                }
                for label, degrees in RIVER_TEST_ORIENTATIONS.items()
            ],
        })
# old riverslot start. comment out later 
#        slot_entries.append({
#            "kind": "cascade", "label": "Riverslot_dont_use (2 points)",
#            "entries": [
#                {
#                    "label": arrow,
#                    "command": lambda n=arrow, e=event: self._island_slot_add_at_event(e, n),
#                }
#                for arrow in RIVERSLOT_DONT_USE_ORIENTATIONS
#            ],
#        })
# old riverslot end
        for mine_name, mine_guid in MINE_SLOT_VARIANTS:
            slot_entries.append({
                "label": mine_name,
                "command": lambda n=mine_name, g=mine_guid, e=event: self._island_slot_add_mineslot_at_event(e, n, g),
            })
        entries.append({"kind": "cascade", "label": "Add Slot", "entries": slot_entries})
        custom_entries = [
            {"label": label, "command": lambda n=label, b=base_type, e=event: self._island_slot_add_custom_at_event(e, n, b)}
            for label, base_type in (
                ("custom clay slot", "clay slot"),
                ("custom oil slot", "oil slot"),
                ("custom gas slot", "gas slot (arctic)"),
            )
        ]
        entries.append({"kind": "cascade", "label": "Add Custom Slot", "entries": custom_entries})
        entries.append({"kind": "separator"})
        entries.append({
            "label": "Change GUID",
            "state": "normal" if hit else "disabled",
            "command": (lambda h=hit: self._island_slot_change_guid(h)) if hit else None,
        })
        return MapViewTemplate.show_context_menu(self.slot_map_window, event, entries)

    def _island_slot_change_guid(self, hit):
        """Change one Slot Map object's GUID in Gamedata and MapName RAM only."""
        if not hit or len(hit) < 4:
            return
        object_id = str(hit[2]).strip()
        old_guid = str(hit[3]).strip()
        value = simpledialog.askstring(
            "Change GUID",
            f"ObjectId: {object_id}\nCurrent GUID: {old_guid}\n\nNew GUID:",
            parent=self.slot_map_window,
            initialvalue=old_guid,
        )
        if value is None:
            return
        new_guid = value.strip()
        if not new_guid or not new_guid.isdigit() or int(new_guid) <= 0:
            messagebox.showerror(
                "Change GUID", "GUID must be a positive integer.",
                parent=self.slot_map_window,
            )
            return
        if new_guid == old_guid:
            return
        try:
            game_original, map_original, game_patched, map_patched = self._island_slot_sources()
            if self._island_slot_ram_game_tree is None or self._island_slot_ram_map_tree is None:
                game_source = game_patched if game_patched.is_file() else game_original
                map_source = map_patched if map_patched.is_file() else map_original
                self._island_slot_ram_game_tree = self._slot_parse_xml(game_source)[0]
                self._island_slot_ram_map_tree = self._slot_parse_xml(map_source)[0]
            game_root = self._island_slot_ram_game_tree.getroot()
            map_root = self._island_slot_ram_map_tree.getroot()
            game_record = self._slot_find_game_record(game_root, object_id)
            map_record = self._slot_find_map_record(map_root, object_id)
            if game_record is None or map_record is None:
                raise ValueError(
                    f"ObjectId {object_id} must exist in both Gamedata and MapName before its GUID can be changed."
                )
            game_guid = direct(game_record, "guid")
            map_guid = direct(map_record, "ObjectGuid")
            if game_guid is None or map_guid is None:
                raise ValueError(f"ObjectId {object_id} has no editable GUID fields.")
            game_guid.text = new_guid
            map_guid.text = new_guid
        except (OSError, ET.ParseError, UnicodeError, ValueError) as exc:
            messagebox.showerror("Change GUID", str(exc), parent=self.slot_map_window)
            return
        self.status_var.set(
            f"Changed ObjectId {object_id} GUID from {old_guid} to {new_guid} in RAM; "
            "click Save to write both XML files."
        )
        self._refresh_open_slot_map()

    def _island_slot_right_click(self, event):
        if self._mine_placement is not None:
            self._island_slot_cancel_mine_placement()
            return "break"
        self._island_slot_popup_menu(event, self._island_slot_nearest(event))
        return "break"

    def _island_slot_add_custom_at_event(self, event, label, base_type):
        value = simpledialog.askstring(
            "Custom Slot GUID",
            f"Enter the GUID for {label}:",
            parent=self.slot_map_window,
        )
        if value is None:
            return
        guid = value.strip()
        if not guid or not guid.isdigit() or int(guid) <= 0:
            messagebox.showerror(
                "Custom Slot GUID",
                "GUID must be a positive integer.",
                parent=self.slot_map_window,
            )
            return
        try:
            x, z = self._island_slot_world(event)
            samples, source = self._island_slot_height_samples()
            y = estimate_nearby_height(x, z, samples)
            if y is None:
                nearest = min(
                    self.slot_map_points,
                    key=lambda p: (p[2]-x)**2 + (p[4]-z)**2,
                    default=None,
                )
                y = nearest[3] if nearest else parse_position(
                    text(template_element(base_type), "Position")
                )[1]
                source = "existing slot" if nearest else "template fallback"
            self._island_slot_add(
                base_type, (x, y, z), samples=samples, source=source,
                custom_guid=guid, display_name=label,
            )
        except (OSError, ET.ParseError, UnicodeError, ValueError, RuntimeError) as exc:
            messagebox.showerror(
                "Add Custom Slot", str(exc), parent=self.slot_map_window
            )

    @staticmethod
    def _slot_add_status_paint(handle):
        """Force status popup creation/repaint before synchronous slot work continues."""
        if not handle:
            return
        window = handle.get("window") if isinstance(handle, dict) else handle
        if window is None:
            return
        try:
            window.update_idletasks()
            window.update()
            window.lift()
        except tk.TclError:
            pass

    def _island_slot_add_directional_template_at_event(self, event, display_name, guid, degrees):
        """Insert one or more directional River/Mine slots using the Clay template."""
        amount = simpledialog.askinteger(
            "Add Island Slot",
            f"How many '{display_name}' elements should be inserted?",
            parent=self.slot_map_window,
            initialvalue=1,
            minvalue=1,
            maxvalue=1000,
        )
        if amount is None:
            return
        progress_window = StatusWindowTemplate.create(
            self.slot_map_window,
            text=f"Adding: {display_name}\nAdding 0/{amount}...",
            title="Add Island Slot", heading="Add Island Slot",
            progress=True, fraction=0, modal=True, topmost=True,
        )
        self._slot_add_status_paint(progress_window)
        try:
            x, z = self._island_slot_world(event)
            samples, source = self._island_slot_height_samples()
            fallback_y = estimate_nearby_height(x, z, samples)
            if fallback_y is None:
                nearest = min(
                    self.slot_map_points,
                    key=lambda p: (p[2] - x) ** 2 + (p[4] - z) ** 2,
                    default=None,
                )
                fallback_y = nearest[3] if nearest else parse_position(
                    text(template_element("clay slot"), "Position")
                )[1]
                source = "existing slot" if nearest else "template fallback"

            spacing = SLOT_MULTI_INSERT_SPACING
            target_positions = self._island_slot_distribution_positions(
                x, z, amount, spacing=spacing
            )
            inserted_amount = len(target_positions)
            if inserted_amount < amount:
                messagebox.showwarning(
                    "Add Island Slot",
                    f"Only {inserted_amount} of {amount} slots fit inside the lasso "
                    f"with the current minimum distance of {spacing:g}.\n\n"
                    f"The {inserted_amount} fitting slots will be added.",
                    parent=self.slot_map_window,
                )
            if inserted_amount == 0:
                return

            direction = (math.radians(degrees) + math.pi / 2.0) % (2.0 * math.pi)
            for index, (target_x, target_z) in enumerate(target_positions):
                StatusWindowTemplate.update(
                    progress_window,
                    text=f"Adding: {display_name}\nAdding {index + 1}/{inserted_amount}...",
                    fraction=index / inserted_amount,
                )
                self._slot_add_status_paint(progress_window)
                target_y = estimate_nearby_height(target_x, target_z, samples)
                if target_y is None:
                    target_y = fallback_y
                self._island_slot_add(
                    "clay slot",
                    (target_x, target_y, target_z),
                    samples=samples,
                    source=source,
                    custom_guid=str(guid),
                    display_name=display_name,
                    rotation_override=degrees,
                    direction_override=direction,
                )
                StatusWindowTemplate.update(
                    progress_window,
                    fraction=(index + 1) / inserted_amount,
                )
            self.status_var.set(
                f"Added {inserted_amount} x {display_name} with minimum X/Z distance {spacing:g}."
            )
        except (OSError, ET.ParseError, UnicodeError, ValueError, RuntimeError) as exc:
            messagebox.showerror(f"Add {display_name}", str(exc), parent=self.slot_map_window)
        finally:
            StatusWindowTemplate.close(progress_window)

    def _island_slot_add_riverslot_at_event(self, event, degrees):
        self._island_slot_add_directional_template_at_event(
            event, "Riverslot", "117741", degrees
        )

    def _island_slot_add_mineslot_at_event(self, event, display_name, guid):
        """Start two-click mine placement; do not change XML yet."""
        self._island_slot_cancel_mine_placement(silent=True)
        x, z = self._island_slot_world(event)
        x, z = math.floor(x) + 0.5, math.floor(z) + 0.5
        samples, source = self._island_slot_height_samples()
        y = estimate_nearby_height(x, z, samples)
        if y is None or y <= 0:
            messagebox.showerror(
                "Add Mine Slot", "Mine entrance must be placed on emerged terrain.",
                parent=self.slot_map_window)
            return
        self._mine_placement = {
            "name": display_name, "guid": str(guid),
            "entrance": (x, y, z), "samples": samples, "source": source,
        }
        self.slot_map_allow_dot_movement_var.set(False)
        self._slot_map_dot_movement_changed()
        self.slot_map_canvas.focus_set()
        self.status_var.set(
            f"Mine entrance selected at X/Z {x:g} / {z:g}. "
            "Left-click to place the Work Area; right-click or Esc to cancel.")
        self._island_slot_draw_mine_preview(None)

    def _island_slot_cancel_mine_placement(self, _event=None, silent=False):
        active = getattr(self, "_mine_placement", None) is not None
        self._mine_placement = None
        canvas = getattr(self, "slot_map_canvas", None)
        if canvas is not None:
            try: canvas.delete("mine_placement_preview")
            except tk.TclError: pass
        if active and not silent:
            self.status_var.set("Mine placement cancelled. No XML data was changed.")
        return "break" if _event is not None else None

    def _island_slot_draw_mine_preview(self, event):
        placement = getattr(self, "_mine_placement", None)
        canvas = getattr(self, "slot_map_canvas", None)
        if placement is None or canvas is None:
            return False
        canvas.delete("mine_placement_preview")
        ex, _ey, ez = placement["entrance"]
        if event is None:
            wx, wz = ex, ez
        else:
            wx, wz = self._island_slot_world(event)
        width, height = max(canvas.winfo_width(), 200), max(canvas.winfo_height(), 200)
        min_x, max_x, min_z, max_z = self.slot_map_bounds
        span_x, span_z = max_x - min_x, max_z - min_z
        margin = MapViewTemplate.MAP_MARGIN
        scale = min((width - 2 * margin) / span_x, (height - 2 * margin) / span_z)
        image_w = span_x * scale * self.slot_map_shared_zoom
        image_h = span_z * scale * self.slot_map_shared_zoom
        image_x = (width - image_w) / 2 + self.slot_map_shared_pan_x
        image_y = (height - image_h) / 2 + self.slot_map_shared_pan_y
        def screen(world_x, world_z):
            return (
                image_x + ((world_x - min_x) / span_x) * image_w,
                image_y + ((max_z - world_z) / span_z) * image_h,
            )
        sx, sy = screen(ex, ez)
        tx, ty = screen(wx, wz)
        distance = math.hypot(wx - ex, wz - ez)
        valid = MINE_MIN_DISTANCE <= distance <= MINE_MAX_DISTANCE
        color = "#39D98A" if valid else "#FF5C5C"
        canvas.create_line(sx, sy, tx, ty, fill=color, width=2,
                           dash=(6, 4), tags=("mine_placement_preview",))
        for px, py, radius in ((sx, sy, 6), (tx, ty, 5)):
            canvas.create_oval(px-radius, py-radius, px+radius, py+radius,
                               fill=color, outline="#111111", width=1,
                               tags=("mine_placement_preview",))
        canvas.create_text((sx+tx)/2, (sy+ty)/2-10,
                           text=f"{distance:.1f}", fill=color,
                           tags=("mine_placement_preview",))
        canvas.tag_raise("mine_placement_preview")
        return True

    def _island_slot_mine_motion(self, event):
        if self._mine_placement is None:
            return False
        self._island_slot_draw_mine_preview(event)
        return True

    def _island_slot_mine_left_click(self, event):
        placement = getattr(self, "_mine_placement", None)
        if placement is None:
            return False
        wx, wz = self._island_slot_world(event)
        entrance = placement["entrance"]
        distance = math.hypot(wx - entrance[0], wz - entrance[2])
        if not MINE_MIN_DISTANCE <= distance <= MINE_MAX_DISTANCE:
            messagebox.showerror(
                "Add Mine Slot",
                f"Work Area distance must be between {MINE_MIN_DISTANCE:g} and {MINE_MAX_DISTANCE:g}.",
                parent=self.slot_map_window)
            return True
        wy = estimate_nearby_height(wx, wz, placement["samples"])
        if wy is None or wy <= 0:
            messagebox.showerror(
                "Add Mine Slot", "Work Area must be placed on emerged terrain.",
                parent=self.slot_map_window)
            return True
        status = StatusWindowTemplate.create(
            self.slot_map_window,
            text=f"Adding: {placement['name']}\nCreating Mine and Work Area...",
            title="Add Mine Slot", heading="Add Mine Slot",
            progress=True, fraction=0, modal=True, topmost=True)
        self._slot_add_status_paint(status)
        try:
            self._island_slot_commit_mine_pair(
                placement, entrance, (wx, wy, wz), status)
            self._island_slot_cancel_mine_placement(silent=True)
        except (OSError, ET.ParseError, UnicodeError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Add Mine Slot", str(exc), parent=self.slot_map_window)
        finally:
            StatusWindowTemplate.close(status)
        return True

    def _island_slot_commit_mine_pair(self, placement, entrance, mountain, status):
        """Atomically generate Mine, Work Area and a nine-point terrain path."""
        go, mo, gp, mp = self._island_slot_sources()
        if self._island_slot_ram_game_tree is None or self._island_slot_ram_map_tree is None:
            self._island_slot_ram_game_tree = self._slot_parse_xml(gp if gp.is_file() else go)[0]
            self._island_slot_ram_map_tree = self._slot_parse_xml(mp if mp.is_file() else mo)[0]
        game_tree, map_tree = deepcopy(self._island_slot_ram_game_tree), deepcopy(self._island_slot_ram_map_tree)
        game_root, map_root = game_tree.getroot(), map_tree.getroot()
        records = object_records(game_root); container = game_object_container(game_root)
        mine_source = next((r for r in records if r["guid"] == placement["guid"]), None)
        mine = deepcopy(mine_source["node"] if mine_source else template_element("clay slot"))
        work_source = next((r for r in records if r["guid"] == MINE_WORKAREA_GUID), None)
        workarea = deepcopy(work_source["node"] if work_source else template_element("Riverslot_workarea"))
        used = all_ids(map_root, game_root)
        mine_id = allocate_verified_unique_id(map_root, game_root, used)
        work_id = allocate_verified_unique_id(map_root, game_root, used)
        folder = new_folder_id(records)
        for node, oid, guid, position in ((mine,mine_id,placement["guid"],entrance),(workarea,work_id,MINE_WORKAREA_GUID,mountain)):
            set_text(node,"ID",oid); set_text(node,"Position",format_position(position))
            guid_node=direct(node,"guid"); guid_node.text=guid
            folder_node=direct(node,"ObjectFolderID")
            if folder_node is None:
                folder_node=ET.Element("ObjectFolderID"); node.insert(2,folder_node)
            folder_node.text=folder
        direction = math.atan2(
            mountain[0] - entrance[0],
            mountain[2] - entrance[2],
        )
        # Mesh/Orientation controls the visible unbuilt mine graphic and is
        # handled separately below. The constructed mine building uses Direction
        # and has a native +90-degree asset-axis offset for GUID 1000029.
        mine_direction = direction
        if placement["guid"] == "1000029":
            mine_direction = (direction + math.pi / 2.0) % (2.0 * math.pi)
        for node, node_direction in (
            (mine, mine_direction),
            (workarea, direction),
        ):
            dn = direct(node, "Direction")
            if dn is None:
                dn = ET.Element("Direction")
                pos = direct(node, "Position")
                node.insert(list(node).index(pos) + 1, dn)
            dn.text = game_number(node_direction)

        # Direction and the Slot Map arrow are already correct. Do not rotate
        # the cloned quaternion relatively. Build the MineSlot yaw quaternion
        # directly from that Direction. Native 1000029 uses yaw = -Direction
        # (for example Direction +PI/2 corresponds to Orientation Y -0.7071).
        if placement["guid"] == "1000029":
            mesh = direct(mine, "Mesh")
            orientation = direct(mesh, "Orientation") if mesh is not None else None
            if orientation is None:
                raise ValueError("MineSlot 1000029 template has no Mesh/Orientation.")
            # Runtime facing swaps the map's X/Z angle basis. Convert the
            # already-correct Mine -> Work Area direction by reflecting the angle
            # across the X/Z diagonal: up->up, right->right, left->left, down->down.
            orientation_direction = math.pi / 2.0 - direction
            half_yaw = orientation_direction / 2.0
            orientation.text = " ".join(game_number(value) for value in (
                0.0,
                -math.sin(half_yaw),
                0.0,
                math.cos(half_yaw),
            ))

        curve=next((n for n in workarea.iter() if tag(n)=="BezierCurve"),None)
        if curve is None: raise ValueError("Work Area template has no BezierCurve.")
        for child in list(curve): curve.remove(child)
        points=[]
        for index in range(9):
            f=index/8; x=mountain[0]+(entrance[0]-mountain[0])*f; z=mountain[2]+(entrance[2]-mountain[2])*f
            y=estimate_nearby_height(x,z,placement["samples"])
            if y is None or y <= 0: raise ValueError("Mine path crosses invalid or underwater terrain.")
            points.append((x,y,z))
        for index,point in enumerate(points):
            a=points[max(0,index-1)]; b=points[min(8,index+1)]; tangent=tuple((b[i]-a[i])/6 for i in range(3))
            item=ET.SubElement(curve,"None"); ET.SubElement(item,"p").text=format_position(point)
            ET.SubElement(item,"i").text=format_position(tuple(-v for v in tangent)); ET.SubElement(item,"o").text=format_position(tangent)
        path=curve.getparent(); minimum=direct(path,"Minimum"); maximum=direct(path,"Maximum")
        minimum.text=format_position(tuple(min(p[i] for p in points) for i in range(3)))
        maximum.text=format_position(tuple(max(p[i] for p in points) for i in range(3)))
        StatusWindowTemplate.update(status,fraction=.7)
        append_pretty(container,mine); append_pretty(container,workarea)
        append_map_entry(map_root,MINE_PRIMARY_GROUP,mine_id,placement["guid"],format_position(entrance))
        append_map_entry(map_root,MINE_WORKAREA_GROUP,work_id,MINE_WORKAREA_GUID,format_position(mountain))
        validate_pair(map_root,game_root)
        self._island_slot_ram_game_tree,self._island_slot_ram_map_tree=game_tree,map_tree
        StatusWindowTemplate.update(status,fraction=1)
        self.status_var.set(f"Added {placement['name']} with Work Area | IDs: {mine_id}, {work_id} | Folder: {folder}")
        self._refresh_open_slot_map()

    def _island_slot_distribution_positions(
            self, click_x, click_z, amount, spacing=SLOT_MULTI_INSERT_SPACING):
        """Return click-first positions, random in selection, then near selection."""
        positions = [(click_x, click_z)]
        if amount <= 1:
            return positions
        bounds = getattr(self, "island_slot_selection_world_bounds", None)
        if bounds is None:
            columns = max(1, math.ceil(math.sqrt(amount)))
            rows = math.ceil(amount / columns)
            start_x = click_x - ((columns - 1) * spacing / 2.0)
            start_z = click_z - ((rows - 1) * spacing / 2.0)
            return [
                (start_x + (index % columns) * spacing,
                 start_z + (index // columns) * spacing)
                for index in range(amount)
            ]

        min_x, max_x, min_z, max_z = bounds
        randomizer = secrets.SystemRandom()
        existing = [(point[2], point[4]) for point in getattr(self, "slot_map_points", [])]

        def free(px, pz):
            return all(
                math.hypot(px - ox, pz - oz) >= spacing
                for ox, oz in existing + positions
            )

        # Randomly fill the marked world-space rectangle first.
        max_attempts = max(500, amount * 100)
        attempts = 0
        while len(positions) < amount and attempts < max_attempts:
            attempts += 1
            px = randomizer.uniform(min_x, max_x)
            pz = randomizer.uniform(min_z, max_z)
            polygon = getattr(self, "island_slot_lasso_world_points", ())
            if len(polygon) >= 3 and not MapViewTemplate.point_in_polygon(px, pz, polygon):
                continue
            if free(px, pz):
                positions.append((px, pz))

        polygon = getattr(self, "island_slot_lasso_world_points", ())
        if len(polygon) >= 3 and len(positions) < amount:
            # Lasso never spills into its bounding rectangle or outside polygon.
            # The caller warns and inserts the positions that did fit.
            return positions

        # Rectangle selection keeps the existing fallback outside a full area.
        ring = 1
        while len(positions) < amount:
            outer_min_x = min_x - ring * spacing
            outer_max_x = max_x + ring * spacing
            outer_min_z = min_z - ring * spacing
            outer_max_z = max_z + ring * spacing
            candidates = []
            x = outer_min_x
            while x <= outer_max_x + 1e-9:
                candidates.extend(((x, outer_min_z), (x, outer_max_z)))
                x += spacing
            z = outer_min_z + spacing
            while z < outer_max_z - 1e-9:
                candidates.extend(((outer_min_x, z), (outer_max_x, z)))
                z += spacing
            randomizer.shuffle(candidates)
            for px, pz in candidates:
                if free(px, pz):
                    positions.append((px, pz))
                    if len(positions) >= amount:
                        break
            ring += 1
        return positions

    def _island_slot_add_at_event(self, event, name):
        # A Riverslot_dont_use entry represents one orientation-specific river pair
        # and must therefore always be inserted exactly once.
        if name in RIVERSLOT_DONT_USE_ORIENTATIONS:
            amount = 1
        else:
            amount = simpledialog.askinteger(
                "Add Island Slot",
                f"How many '{name}' elements should be inserted?",
                parent=self.slot_map_window,
                initialvalue=1,
                minvalue=1,
                maxvalue=1000,
            )
            if amount is None:
                return
        progress_window = None
        try:
            progress_window = StatusWindowTemplate.create(
                self.slot_map_window,
                text=f"Adding: {name}\nAdding 0/{amount}...",
                title="Add Island Slot", heading="Add Island Slot",
                progress=True, fraction=0, modal=True, topmost=True,
            )
            self._slot_add_status_paint(progress_window)

            x, z = self._island_slot_world(event)
            slot_type = "Riverslot" if name in RIVERSLOT_DONT_USE_ORIENTATIONS else name
            samples, source = self._island_slot_height_samples()
            y = estimate_nearby_height(x, z, samples)
            if y is None:
                nearest = min(
                    self.slot_map_points,
                    key=lambda p: (p[2] - x) ** 2 + (p[4] - z) ** 2,
                    default=None,
                )
                y = nearest[3] if nearest else parse_position(
                    text(template_element(slot_type), "Position")
                )[1]
                source = "existing slot" if nearest else "template fallback"

            spacing = SLOT_MULTI_INSERT_SPACING
            target_positions = self._island_slot_distribution_positions(
                x, z, amount, spacing=spacing
            )
            inserted_amount = len(target_positions)
            if inserted_amount < amount:
                messagebox.showwarning(
                    "Add Island Slot",
                    f"Only {inserted_amount} of {amount} slots fit inside the lasso "
                    f"with the current minimum distance of {spacing:g}.\n\n"
                    f"The {inserted_amount} fitting slots will be added.",
                    parent=self.slot_map_window,
                )
            if inserted_amount == 0:
                return

            for index, (target_x, target_z) in enumerate(target_positions):
                StatusWindowTemplate.update(
                    progress_window,
                    text=f"Adding: {name}\nAdding {index + 1}/{inserted_amount}...",
                    fraction=(index + 1) / inserted_amount,
                )
                self._slot_add_status_paint(progress_window)

                target_y = estimate_nearby_height(target_x, target_z, samples)
                if target_y is None:
                    target_y = y
                self._island_slot_add(
                    name,
                    (target_x, target_y, target_z),
                    samples=samples,
                    source=source,
                )
                # The shared template remains topmost while the Slot Map redraws.
                StatusWindowTemplate.update(
                    progress_window, fraction=(index + 1) / amount
                )
            self.status_var.set(
                f"Added {inserted_amount} x {name} with minimum X/Z distance {spacing:g}."
            )
        except (OSError, ET.ParseError, UnicodeError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Add Island Slot", str(exc), parent=self.slot_map_window)
        finally:
            StatusWindowTemplate.close(progress_window)

    def _island_slot_height_samples(self):
        parser = getattr(self, "_parse_xml_tolerant", None)
        rd3d_value = getattr(getattr(self, "rd3d_file_var", None), "get", lambda: "")().strip()
        rd3d_path = Path(rd3d_value) if rd3d_value else None
        if rd3d_path and rd3d_path.is_file():
            patched = rd3d_path.with_name(rd3d_path.name.replace("_original.xml", "_patched.xml"))
            samples = position_samples_from_xml(patched if patched.is_file() else rd3d_path, parser)
            if samples:
                return samples, f"RD3D ({len(samples)} samples)"
        tmc_value = getattr(getattr(self, "tmc_data_meshes_var", None), "get", lambda: "")().strip()
        tmc_root = Path(tmc_value) if tmc_value else None
        if tmc_root and tmc_root.exists():
            files = [tmc_root] if tmc_root.is_file() else sorted(tmc_root.rglob("*.xml"))
            samples = []
            for path in files:
                samples.extend(position_samples_from_xml(path, parser))
            if samples:
                return samples, f"TMC ({len(samples)} samples)"
        return [], ""

    def _island_slot_sources(self):
        game_original = Path(self.gamedata_file_var.get().strip())
        map_original = Path(self.mapname_file_var.get().strip())
        if not game_original.is_file() or not map_original.is_file():
            raise FileNotFoundError("Load Gamedata and MapName original XML first.")
        game_patched = game_original.with_name("gamedata_patched.xml")
        map_patched = map_original.with_name(map_original.name.replace("_original.xml", "_patched.xml") if map_original.name.endswith("_original.xml") else map_original.stem + "_patched.xml")
        return game_original, map_original, game_patched, map_patched


    def _island_slot_add(self, name, target, samples=None, source="",
                         custom_guid=None, display_name=None, rotation_override=None,
                         direction_override=None):
        go, mo, gp, mp = self._island_slot_sources()
        if self._island_slot_ram_game_tree is None or self._island_slot_ram_map_tree is None:
            self._island_slot_ram_game_tree = self._slot_parse_xml(gp if gp.is_file() else go)[0]
            self._island_slot_ram_map_tree = self._slot_parse_xml(mp if mp.is_file() else mo)[0]
        game_tree = self._island_slot_ram_game_tree
        map_tree = self._island_slot_ram_map_tree
        game_root, map_root = game_tree.getroot(), map_tree.getroot()
        records = object_records(game_root)
        self._template_game_root = game_root
        rotation = RIVERSLOT_DONT_USE_ORIENTATIONS.get(name, 0) if rotation_override is None else rotation_override
        slot_type = "Riverslot" if name in RIVERSLOT_DONT_USE_ORIENTATIONS else name
        spec = SLOT_DEFINITIONS[slot_type]
        same = [record for record in records if record["guid"] == spec["guid"]]
        template_source = "same-island"
        if slot_type in NATIVE_DEPOSIT_SLOT_NAMES:
            templates = [(game_object_container(game_root), template_element(slot_type))]
            template_source = "C# native deposit template"
        elif same:
            primary = same[0]
            if "pair_guid" in spec:
                partners = [r for r in records if r["guid"] == spec["pair_guid"] and r["folder"] == primary["folder"]]
                if len(partners) == 1:
                    templates = [(primary["parent"], deepcopy(primary["node"])), (partners[0]["parent"], deepcopy(partners[0]["node"]))]
                else:
                    templates = None
            else:
                templates = [(primary["parent"], deepcopy(primary["node"]))]
        else:
            templates = None
        if not templates:
            container = object_container(game_root)
            if slot_type == "Riverslot":
                slot, workarea = river_pair()
                templates = [(container, slot), (container, workarea)]
            else:
                templates = [(container, template_element(name))]
            template_source = f"config_slot.py ({TEMPLATE_METADATA[slot_type]['source']})"
        used = all_ids(map_root, game_root)
        folder = new_folder_id(records) if slot_type == "Riverslot" else None
        primary_position = parse_position(text(templates[0][1], "Position"))
        if rotation:
            for _parent, clone in templates:
                rotate_clone_y(clone, primary_position, rotation)
            primary_position = parse_position(text(templates[0][1], "Position"))
        dx, dz = target[0] - primary_position[0], target[2] - primary_position[2]
        def height_at(x, z):
            return estimate_nearby_height(x, z, samples or []) if samples else target[1]
        additions = []
        new_ids = [allocate_verified_unique_id(map_root, game_root, used) for _ in templates]
        id_map = {text(clone, "ID"): oid for (_parent, clone), oid in zip(templates, new_ids)}
        for index, ((parent, clone), planned_oid) in enumerate(zip(templates, new_ids)):
            # Final live-tree guard: if the planned ID appeared since allocation,
            # transparently remap the clone to another verified unique ID.
            live_used = all_ids(map_root, game_root)
            oid = planned_oid
            if oid in live_used:
                oid = allocate_verified_unique_id(map_root, game_root, used | live_used)
                for source_id, mapped_id in tuple(id_map.items()):
                    if mapped_id == planned_oid:
                        id_map[source_id] = oid
            used.add(oid)
            replace_exact_text(clone, id_map)
            if slot_type in NATIVE_DEPOSIT_SLOT_NAMES:
                final_y = height_at(target[0], target[2])
                final_position = (target[0], final_y if final_y is not None else target[1], target[2])
                prepare_native_deposit(clone, oid, final_position)
            else:
                set_text(clone, "ID", oid)
                if folder is not None:
                    set_text(clone, "ObjectFolderID", folder)
                relocate_clone(clone, dx, dz, height_at)
            if custom_guid is not None and index == 0:
                set_text(clone, "guid", custom_guid)
            if direction_override is not None and index == 0:
                direction_node = next(
                    (child for child in clone.iter() if tag(child) == "Direction"),
                    None,
                )
                if direction_node is None:
                    raise ValueError("The selected template has no <Direction> field.")
                direction_node.text = game_number(direction_override)
            append_pretty(parent, clone)
            guid, pos = text(clone, "guid"), text(clone, "Position")
            group = spec["group"] if index == 0 else spec["pair_group"]
            append_map_entry(map_root, group, oid, guid, pos)
            additions.append((oid, guid, pos))
            if slot_type in NATIVE_DEPOSIT_SLOT_NAMES:
                self._island_slot_generated_deposit_ids.add(oid)
        self._island_slot_ram_game_tree = game_tree
        self._island_slot_ram_map_tree = map_tree
        added_name = display_name or name
        guid_status = f" | GUID: {custom_guid}" if custom_guid is not None else ""
        self.status_var.set(
            f"Added {added_name}: {len(additions)} object(s){guid_status} | "
            f"Template: {template_source} | Height: {source or 'fallback'}"
        )
        if template_source.startswith("config_slot.py"):
            messagebox.showwarning(
                "Built-in Slot Template",
                f"The target island had no complete {name} template. A verified built-in template was used:\n\n"
                f"{template_source}\n\nThe XML structure was validated, but cross-region gameplay remains experimental. Test the island in game.",
                parent=self.slot_map_window,
            )
        self._refresh_open_slot_map()

    def _island_slot_rotate_90(self, hit):
        """Rotate a River slot 90 degrees clockwise in RAM; persist only on Save."""
        if not hit or len(hit) < 4:
            return
        object_id = str(hit[2]).strip()
        guid = str(hit[3]).strip()
        if guid not in RIVER_GUID_ROLE and guid not in MINE_SLOT_GUIDS:
            return
        try:
            go, mo, gp, mp = self._island_slot_sources()
            game_source = gp if gp.is_file() else go
            map_source = mp if mp.is_file() else mo
            if self._island_slot_ram_game_tree is None:
                self._island_slot_ram_game_tree = self._slot_parse_xml(game_source)[0]
            if self._island_slot_ram_map_tree is None:
                self._island_slot_ram_map_tree = self._slot_parse_xml(map_source)[0]
            game_root = self._island_slot_ram_game_tree.getroot()
            map_root = self._island_slot_ram_map_tree.getroot()
            records = object_records(game_root)
            by_id = {record["id"]: record for record in records}
            selected = by_id.get(object_id)
            if selected is None:
                raise ValueError(f"River ObjectId {object_id} no longer exists in Gamedata RAM.")
            center = selected["position"]

            # Single Riverslot has no paired MapName/Gamedata work-area. A legacy
            # 2-point Riverslot is recognized from the already resolved UI pair list.
            rotate_ids = {object_id}
            for primary_id, workarea_id, _family in getattr(self, "slot_map_river_pairs", []):
                if object_id == primary_id:
                    rotate_ids.add(workarea_id)
                    break
                if object_id == workarea_id:
                    rotate_ids.add(primary_id)
                    center = by_id.get(primary_id, selected)["position"]
                    break

            for rotate_id in rotate_ids:
                record = by_id.get(rotate_id)
                if record is None:
                    continue
                rotate_clone_y(record["node"], center, 90)
                map_record = self._slot_find_map_record(map_root, rotate_id)
                if map_record is not None:
                    set_text(map_record, "Position", text(record["node"], "Position"))

            pending = getattr(self, "_slot_map_pending_moves", {}) or {}
            for rotate_id in rotate_ids:
                pending.pop(rotate_id, None)
            self._slot_map_pending_moves = pending
            self.status_var.set(
                f"Rotated River slot ObjectId {object_id} by 90 degrees in RAM; click Save to persist."
            )
            self._refresh_open_slot_map()
        except (OSError, ET.ParseError, UnicodeError, ValueError, RuntimeError) as exc:
            messagebox.showerror("Rotate River Slot", str(exc), parent=self.slot_map_window)

    def _island_slot_remove_ids(self, ids):
        """Remove slots from the shared RAM model; persist only on explicit Save."""
        try:
            go, mo, gp, mp = self._island_slot_sources()
            game_source = gp if gp.is_file() else go
            map_source = mp if mp.is_file() else mo
            if self._island_slot_ram_game_tree is None:
                self._island_slot_ram_game_tree = self._slot_parse_xml(game_source)[0]
            if self._island_slot_ram_map_tree is None:
                self._island_slot_ram_map_tree = self._slot_parse_xml(map_source)[0]
            game_tree = self._island_slot_ram_game_tree
            map_tree = self._island_slot_ram_map_tree
            game_root, map_root = game_tree.getroot(), map_tree.getroot()
            records = object_records(game_root)
            selected = [record for record in records if record["id"] in ids]
            if not selected:
                raise ValueError("The selected slot no longer exists in the current RAM model.")
            # Remove exactly the requested ObjectIds. River partner resolution is
            # intentionally not part of Remove; no missing/ambiguous partner check.
            expanded = set(ids)
            if not messagebox.askyesno(
                "Remove Island Slot",
                f"Remove {len(expanded)} synchronized object(s) from the preview?\n\n"
                "The XML files will not be changed until Save is clicked.",
                parent=self.slot_map_window,
                default="no",
            ):
                return
            removed_game = remove_game_ids(game_root, expanded)
            removed_map = remove_map_ids(map_root, expanded)
            expected = len(expanded)
            if removed_game != expected or removed_map != expected:
                raise ValueError(
                    "RAM removal was incomplete: "
                    f"Gamedata {removed_game}/{expected}, "
                    f"MapName {removed_map}/{expected}. Nothing has been saved."
                )
            pending = getattr(self, "_slot_map_pending_moves", {}) or {}
            for object_id in expanded:
                pending.pop(object_id, None)
            self._slot_map_pending_moves = pending
            self._island_slot_generated_deposit_ids.difference_update(expanded)
        except (OSError, ET.ParseError, UnicodeError, ValueError) as exc:
            messagebox.showerror("Remove Island Slot", str(exc), parent=self.slot_map_window)
            return
        self.island_slot_selected_ids.difference_update(expanded)
        self.status_var.set(
            f"Removed {len(expanded)} slot object(s) from MapName and Gamedata RAM; "
            "click Save to write both XML files."
        )
        self._refresh_open_slot_map()

    @staticmethod
    def _slot_find_map_record(root, object_id):
        for node in root.iter():
            if text(node, "ObjectId") == object_id:
                return node
        return None

    @staticmethod
    def _slot_find_game_record(root, object_id):
        for node in root.iter():
            if text(node, "ID") == object_id:
                return node
        return None

    @staticmethod
    def _slot_default_accepted_finding(error):
        """No validation finding is accepted implicitly."""
        return False

    def _slot_call_on_ui_sync(self, callback):
        """Execute a Tk callback on the UI thread and return its result."""
        if threading.current_thread() is threading.main_thread():
            return callback()
        finished = threading.Event()
        result = {}
        def run():
            try:
                result["value"] = callback()
            except BaseException as exc:
                result["error"] = exc
            finally:
                finished.set()
        self.after(0, run)
        finished.wait()
        if "error" in result:
            raise result["error"]
        return result.get("value")

    def _slot_review_save_stoppers(self, map_tree, game_tree):
        """Review/edit/accept exact validation blockers before atomic Save."""
        if threading.current_thread() is not threading.main_thread():
            return self._slot_call_on_ui_sync(
                lambda: self._slot_review_save_stoppers(map_tree, game_tree)
            )
        report = validate_slot_trees(
            map_tree.getroot(), game_tree.getroot(),
            strict_deposit_ids=self._island_slot_generated_deposit_ids,
        )
        if not report.errors:
            return set()

        owner = self.slot_map_window if getattr(self, "slot_map_window", None) is not None else self
        window = tk.Toplevel(owner)
        window.title("Save Slot Integration - Review")
        window.geometry("1120x650")
        window.minsize(900, 520)
        window.transient(owner)
        window.grab_set()
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)
        result = {"accepted": None}
        accepted = {
            error for error in report.errors
            if self._slot_default_accepted_finding(error)
        }
        current_errors = []

        header = tk.Frame(window, padx=18, pady=14)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        tk.Label(header, text="⚠", fg="#d18b00", font=("Segoe UI Symbol", 28, "bold")).grid(
            row=0, column=0, rowspan=2, padx=(0, 14), sticky="n"
        )
        tk.Label(header, text="Review slot integration blockers", font=("Segoe UI", 16, "bold"), anchor="w").grid(row=0, column=1, sticky="ew")
        tk.Label(
            header,
            text=("Correct MapName/Gamedata GUIDs where appropriate, or explicitly mark "
                  "a known legacy difference as Accepted. Acceptances apply only to this save."),
            justify="left", anchor="w", wraplength=920,
        ).grid(row=1, column=1, sticky="ew", pady=(4, 0))

        summary_var = tk.StringVar()
        tk.Label(window, textvariable=summary_var, anchor="w", padx=18, fg="#9a6700").grid(row=1, column=0, sticky="ew", pady=(0, 6))

        table_frame = tk.Frame(window, padx=18)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        table = ttk.Treeview(table_frame, columns=("state", "category", "object_id", "detail"), show="headings", selectmode="extended")
        for key, caption in (("state", "State"), ("category", "Type"), ("object_id", "ObjectId"), ("detail", "Details")):
            table.heading(key, text=caption)
        table.column("state", width=95, stretch=False)
        table.column("category", width=150, stretch=False)
        table.column("object_id", width=200, stretch=False)
        table.column("detail", width=620, minwidth=360, stretch=True)
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        table.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        editor = ttk.LabelFrame(window, text="Selected ObjectId", padding=12)
        editor.grid(row=3, column=0, padx=18, pady=(10, 0), sticky="ew")
        editor.grid_columnconfigure(1, weight=1)
        editor.grid_columnconfigure(3, weight=1)
        object_var = tk.StringVar(value="-")
        map_guid_var = tk.StringVar()
        game_guid_var = tk.StringVar()
        ttk.Label(editor, text="ObjectId:").grid(row=0, column=0, sticky="w")
        ttk.Label(editor, textvariable=object_var).grid(row=0, column=1, sticky="w", padx=(6, 18))
        ttk.Label(editor, text="MapName GUID:").grid(row=1, column=0, sticky="w", pady=(10, 0))
        map_entry = ttk.Entry(editor, textvariable=map_guid_var)
        map_entry.grid(row=1, column=1, sticky="ew", padx=(6, 18), pady=(10, 0))
        ttk.Label(editor, text="Gamedata GUID:").grid(row=1, column=2, sticky="w", pady=(10, 0))
        game_entry = ttk.Entry(editor, textvariable=game_guid_var)
        game_entry.grid(row=1, column=3, sticky="ew", padx=(6, 0), pady=(10, 0))
        detail_var = tk.StringVar(value="Select an entry to inspect or edit it.")
        tk.Label(editor, textvariable=detail_var, justify="left", anchor="w", wraplength=1040).grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 0))

        def selected_errors():
            return [current_errors[int(table.item(item, "tags")[0])] for item in table.selection() if table.item(item, "tags")]

        def selected_error():
            errors = selected_errors()
            return errors[0] if errors else None

        def object_id_from_error(error):
            import re
            match = re.search(r"ObjectId\s+(-?\d+)|ObjectId:\s*(-?\d+)", error)
            return next((value for value in match.groups() if value), "") if match else ""

        def load_selection(_event=None):
            error = selected_error()
            if error is None:
                return
            oid = object_id_from_error(error)
            object_var.set(oid or "-")
            map_node = self._slot_find_map_record(map_tree.getroot(), oid) if oid else None
            game_node = self._slot_find_game_record(game_tree.getroot(), oid) if oid else None
            map_guid_var.set(text(map_node, "ObjectGuid") if map_node is not None else "")
            game_guid_var.set(text(game_node, "guid") if game_node is not None else "")
            map_entry.configure(state="normal" if map_node is not None else "disabled")
            game_entry.configure(state="normal" if game_node is not None else "disabled")
            detail_var.set(error)

        def refresh(preserve_error=None):
            nonlocal current_errors
            report_now = validate_slot_trees(
                map_tree.getroot(), game_tree.getroot(),
                strict_deposit_ids=self._island_slot_generated_deposit_ids,
            )
            current_errors = list(report_now.errors)
            accepted.intersection_update(current_errors)
            accepted.update(
                error for error in current_errors
                if self._slot_default_accepted_finding(error)
            )
            for item in table.get_children():
                table.delete(item)
            selected_item = None
            for index, error in enumerate(current_errors):
                category, oid, detail = self._slot_warning_parts(error)
                state = "Accepted" if error in accepted else "Stopper"
                item = table.insert("", "end", values=(state, category, oid, detail), tags=(str(index),))
                if error == preserve_error:
                    selected_item = item
            unresolved = sum(error not in accepted for error in current_errors)
            summary_var.set(f"{len(current_errors)} finding(s) | {unresolved} unresolved stopper(s) | {len(accepted)} accepted")
            if selected_item:
                table.selection_set(selected_item)
                table.focus(selected_item)
                load_selection()
            elif current_errors:
                first = table.get_children()[0]
                table.selection_set(first)
                table.focus(first)
                load_selection()
            else:
                object_var.set("-")
                map_guid_var.set("")
                game_guid_var.set("")
                detail_var.set("Validation completed without blockers.")

        def apply_guid_changes():
            error = selected_error()
            oid = object_id_from_error(error or "")
            if not oid:
                messagebox.showwarning("GUID change", "The selected finding has no editable ObjectId.", parent=window)
                return
            for root, id_tag, guid_tag, value in (
                (map_tree.getroot(), "ObjectId", "ObjectGuid", map_guid_var.get().strip()),
                (game_tree.getroot(), "ID", "guid", game_guid_var.get().strip()),
            ):
                node = self._slot_find_map_record(root, oid) if id_tag == "ObjectId" else self._slot_find_game_record(root, oid)
                if node is None:
                    continue
                if not value or not value.isdigit() or int(value) <= 0:
                    messagebox.showwarning("GUID change", f"{guid_tag} must be a positive integer.", parent=window)
                    return
                set_text(node, guid_tag, value)
            refresh()

        def set_accepted():
            errors = selected_errors()
            if errors:
                accepted.update(errors)
                refresh(errors[0])

        def set_stopper():
            errors = selected_errors()
            if errors:
                accepted.difference_update(errors)
                refresh(errors[0])

        table.bind("<<TreeviewSelect>>", load_selection)

        actions = tk.Frame(window, padx=18, pady=14)
        actions.grid(row=4, column=0, sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        ttk.Button(actions, text="Apply GUID changes", command=apply_guid_changes).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="Set accepted", command=set_accepted).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(actions, text="Set stopper", command=set_stopper).grid(row=0, column=3, padx=(0, 8))
        def continue_save():
            unresolved = [error for error in current_errors if error not in accepted]
            if unresolved:
                messagebox.showwarning("Save Slot Integration", f"{len(unresolved)} stopper(s) are still unresolved.", parent=window)
                return
            result["accepted"] = set(accepted)
            PopupTemplate.close_window(window)
        ttk.Button(actions, text="Cancel", command=lambda: PopupTemplate.close_window(window)).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(actions, text="Continue Save", command=continue_save).grid(row=0, column=5)
        refresh()
        PopupTemplate.schedule(window, 30, lambda: PopupTemplate.safe_activate(window))
        owner.wait_window(window)
        return result["accepted"]

    def _island_slot_atomic_write(self, game_tree, map_tree, game_target, map_target):
        accepted = self._slot_review_save_stoppers(map_tree, game_tree)
        if accepted is None:
            raise SlotSaveCancelled()
        initial_report = validate_slot_trees(
            map_tree.getroot(), game_tree.getroot(),
            strict_deposit_ids=self._island_slot_generated_deposit_ids,
        )
        unresolved = [error for error in initial_report.errors if error not in accepted]
        if unresolved:
            raise ValueError("Slot validation failed:\n- " + "\n- ".join(unresolved))
        warnings = list(initial_report.warnings) + [f"Accepted: {error}" for error in initial_report.errors]
        game_tmp = game_target.with_suffix(game_target.suffix + ".tmp")
        map_tmp = map_target.with_suffix(map_target.suffix + ".tmp")
        game_backup = game_target.with_suffix(game_target.suffix + ".rollback")
        map_backup = map_target.with_suffix(map_target.suffix + ".rollback")
        installed_game = installed_map = False
        try:
            game_tree.write(game_tmp, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
            map_tree.write(map_tmp, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
            check_game = self._slot_parse_xml(game_tmp)[0]
            check_map = self._slot_parse_xml(map_tmp)[0]
            written_report = validate_slot_trees(
                check_map.getroot(), check_game.getroot(),
                strict_deposit_ids=self._island_slot_generated_deposit_ids,
            )
            unresolved_written = [error for error in written_report.errors if error not in accepted]
            if unresolved_written:
                raise ValueError("Serialized slot validation failed:\n- " + "\n- ".join(unresolved_written))
            written_warnings = list(written_report.warnings) + [
                f"Accepted: {error}" for error in written_report.errors
            ]
            warnings = list(dict.fromkeys(warnings + written_warnings))
            if game_target.exists():
                game_target.replace(game_backup)
            if map_target.exists():
                map_target.replace(map_backup)
            try:
                game_tmp.replace(game_target); installed_game = True
                map_tmp.replace(map_target); installed_map = True
            except Exception:
                if installed_game:
                    game_target.unlink(missing_ok=True)
                if installed_map:
                    map_target.unlink(missing_ok=True)
                if game_backup.exists():
                    game_backup.replace(game_target)
                if map_backup.exists():
                    map_backup.replace(map_target)
                raise
            # Verify the installed destinations themselves before removing rollback
            # files. This detects replacement/path issues in addition to temp-file
            # serialization errors.
            installed_game_tree = self._slot_parse_xml(game_target)[0]
            installed_map_tree = self._slot_parse_xml(map_target)[0]
            installed_report = validate_slot_trees(
                installed_map_tree.getroot(), installed_game_tree.getroot(),
                strict_deposit_ids=self._island_slot_generated_deposit_ids,
            )
            unresolved_installed = [
                error for error in installed_report.errors if error not in accepted
            ]
            if unresolved_installed:
                game_target.unlink(missing_ok=True)
                map_target.unlink(missing_ok=True)
                if game_backup.exists():
                    game_backup.replace(game_target)
                if map_backup.exists():
                    map_backup.replace(map_target)
                raise ValueError(
                    "Installed slot XML validation failed:\n- "
                    + "\n- ".join(unresolved_installed)
                )
            game_backup.unlink(missing_ok=True)
            map_backup.unlink(missing_ok=True)
        finally:
            for temporary in (game_tmp, map_tmp):
                temporary.unlink(missing_ok=True)
            # A failure before installation must also restore renamed originals.
            if game_backup.exists() and not game_target.exists():
                game_backup.replace(game_target)
            if map_backup.exists() and not map_target.exists():
                map_backup.replace(map_target)
        return warnings

    def _island_slot_capture_snapshot(self):
        """Remember the current patched/original slot XML state for Reset."""
        go, mo, gp, mp = self._island_slot_sources()
        self._island_slot_snapshot = {
            gp: (gp.read_bytes() if gp.is_file() else None),
            mp: (mp.read_bytes() if mp.is_file() else None),
        }

    def _show_slot_save_status(self):
        """Show the shared themed status window before Slot Map saving starts."""
        owner = self.slot_map_window if self.slot_map_window is not None else self
        return StatusWindowTemplate.create(
            owner, text="Saving…", title="Status", heading="Status",
            modal=False, topmost=True,
        )


    def _island_slot_save(self):
        """Start Slot Map save asynchronously and keep its status popup open."""
        if getattr(self, "_island_slot_save_running", False):
            return
        self._island_slot_save_running = True
        save_status = self._show_slot_save_status()
        self._slot_add_status_paint(save_status)

        def run():
            try:
                self._island_slot_save_background()
            finally:
                self.after(0, lambda: self._island_slot_save_finished(save_status))

        threading.Thread(
            target=run, daemon=True, name="SlotMapSave"
        ).start()

    def _island_slot_save_finished(self, save_status):
        StatusWindowTemplate.close(save_status)
        self._island_slot_save_running = False

    def _island_slot_save_cancelled(self):
        self.status_var.set("Slot integration save cancelled; no files were changed.")

    def _island_slot_save_failed(self, error):
        messagebox.showerror("Save Slot Integration", error, parent=self.slot_map_window)

    def _island_slot_save_succeeded(self, warnings, synchronized, deleted_orphans):
        if warnings:
            self.status_var.set(
                f"Slot integration saved with {len(warnings)} warning(s); "
                f"{synchronized} Gamedata position(s) synchronized; "
                f"{deleted_orphans} orphaned Gamedata object(s) deleted."
            )
            messagebox.showwarning(
                "Save Slot Integration",
                "Slot integration was saved successfully, but validation reported "
                f"{len(warnings)} warning(s):\n\n" + "\n".join(warnings) +
                f"\n\nSynchronized Gamedata positions: {synchronized}"
                f"\nDeleted orphaned Gamedata objects: {deleted_orphans}",
                parent=self.slot_map_window,
            )
        else:
            self.status_var.set(
                f"Slot integration saved and validated; {synchronized} Gamedata position(s) synchronized; "
                f"{deleted_orphans} orphaned Gamedata object(s) deleted."
            )
            messagebox.showinfo(
                "Save Slot Integration",
                "Slot integration saved and validated successfully.\n\n"
                f"Synchronized Gamedata positions: {synchronized}\n"
                f"Deleted orphaned Gamedata objects: {deleted_orphans}",
                parent=self.slot_map_window,
            )

    def _island_slot_save_background(self):
        """Perform Slot Map XML preparation, validation and writes off the UI thread."""
        try:
            game_original, map_original, game_patched, map_patched = self._island_slot_sources()
            game_source = game_patched if game_patched.is_file() else game_original
            map_source = map_patched if map_patched.is_file() else map_original
            game_tree = self._island_slot_ram_game_tree or self._slot_parse_xml(game_source)[0]
            map_tree = self._island_slot_ram_map_tree or self._slot_parse_xml(map_source)[0]
            pending = dict(getattr(self, "_slot_map_pending_moves", {}) or {})
            warnings = []
            deleted_orphans = 0

            # First apply unsaved drag positions to MapName. MapName is the visual
            # Slot Map model and therefore the authoritative source for positions.
            if pending:
                pending = {
                    object_id: format_position(parse_position(position))
                    for object_id, position in pending.items()
                }
                # Only explicitly moved objects are updated; no partner lookup.
                records_by_id = {
                    record["id"]: record for record in object_records(game_tree.getroot())
                }
                river_translations = {}
                for object_id, new_position in pending.items():
                    record = records_by_id.get(object_id)
                    if record is None or not has_bezier_curve(record["node"]):
                        continue
                    new_pos = parse_position(new_position)
                    delta = tuple(new_pos[i] - record["position"][i] for i in range(3))
                    river_translations[object_id] = (record["node"], delta)
                applied = set()
                for parent in map_tree.getroot().iter():
                    id_node = direct(parent, "ObjectId")
                    position_node = direct(parent, "Position")
                    if id_node is None or position_node is None:
                        continue
                    object_id = (id_node.text or "").strip()
                    if object_id in pending:
                        position_node.text = pending[object_id]
                        applied.add(object_id)
                missing = set(pending) - applied
                if missing:
                    game_guid_by_id = {
                        record["id"]: record["guid"]
                        for record in object_records(game_tree.getroot())
                    }
                    missing_details = [
                        f"ObjectId: {object_id} | GUID: "
                        f"{game_guid_by_id.get(object_id, 'unknown')}"
                        for object_id in sorted(missing)
                    ]
                    warnings.append(
                        "Moved slot object(s) are missing in MapName. "
                        "The remaining changes were saved anyway:\n"
                        + "\n".join(missing_details)
                    )

            # Collect every current MapName position, even when no pending move is
            # present. This repairs a patch left mismatched by an earlier failed Save.
            map_positions = {}
            conflicting_map_ids = set()
            for parent in map_tree.getroot().iter():
                id_node = direct(parent, "ObjectId")
                position_node = direct(parent, "Position")
                if id_node is None or position_node is None:
                    continue
                object_id = (id_node.text or "").strip()
                if not object_id:
                    continue
                normalized = format_position(parse_position(position_node.text))
                previous = map_positions.get(object_id)
                if previous is not None and previous != normalized:
                    conflicting_map_ids.add(object_id)
                else:
                    map_positions[object_id] = normalized
            if conflicting_map_ids:
                raise ValueError(
                    "MapName contains conflicting positions for ObjectId(s): "
                    + ", ".join(sorted(conflicting_map_ids))
                )

            # Detect Gamedata slot records that were referenced by the original
            # MapName but are no longer referenced by the current MapName. This
            # deliberately excludes unrelated Gamedata objects.
            original_map_tree = self._slot_parse_xml(map_original)[0]
            original_map_ids = {
                text(parent, "ObjectId")
                for parent in original_map_tree.getroot().iter()
                if text(parent, "ObjectId")
            }
            current_map_ids = set(map_positions)
            orphan_records = [
                record for record in object_records(game_tree.getroot())
                if record["id"] in original_map_ids
                and record["id"] not in current_map_ids
            ]
            if orphan_records:
                orphan_records.sort(key=lambda record: record["id"])
                details = "\n".join(
                    f"ObjectId: {record['id']} | GUID: {record['guid']}"
                    for record in orphan_records
                )
                delete_orphans = messagebox.askyesno(
                    "Orphaned Gamedata Slot Objects",
                    "The following slot objects are no longer referenced in MapName, "
                    "but still exist in Gamedata:\n\n"
                    + details
                    + "\n\nDelete these objects from Gamedata?\n\n"
                      "Yes: delete the listed Gamedata objects and continue saving.\n"
                      "No: keep the Gamedata objects and continue saving.",
                    parent=self.slot_map_window,
                    default="no",
                )
                if delete_orphans:
                    orphan_ids = {record["id"] for record in orphan_records}
                    deleted_orphans = remove_game_ids(game_tree.getroot(), orphan_ids)

            # Translate geometry belonging to the moved object itself only.
            for node, (dx, dy, dz) in (river_translations if pending else {}).values():
                translate_bezier_world_geometry(node, dx, dy, dz)

            # Mirror authoritative MapName positions into all matching Gamedata
            # records. This runs on every Save, not only while the RAM pending buffer
            # exists, so retrying after a previous failed Save repairs the mismatch.
            game_ids = set()
            synchronized = 0
            for parent in game_tree.getroot().iter():
                id_node = direct(parent, "ID")
                position_node = direct(parent, "Position")
                if id_node is None or position_node is None:
                    continue
                object_id = (id_node.text or "").strip()
                if object_id not in map_positions:
                    continue
                game_ids.add(object_id)
                target = map_positions[object_id]
                current = format_position(parse_position(position_node.text))
                if current != target:
                    position_node.text = target
                    synchronized += 1

            # The atomic writer opens the interactive review before either target
            # file is replaced. Do not pre-validate here: that would bypass the
            # GUID editor / Accepted workflow and fall back to a standard error box.
            written_warnings = self._island_slot_atomic_write(
                game_tree, map_tree, game_patched, map_patched
            )
            warnings = list(dict.fromkeys(warnings + written_warnings))
            self._island_slot_ram_game_tree = None
            self._island_slot_ram_map_tree = None
            self._island_slot_generated_deposit_ids.clear()
            self._island_slot_capture_snapshot()
            self._slot_map_pending_moves = {}
            self.after(0, self._refresh_open_slot_map)
        except SlotSaveCancelled:
            self.after(0, self._island_slot_save_cancelled)
            return
        except (OSError, ET.ParseError, UnicodeError, ValueError, RuntimeError) as exc:
            self.after(0, lambda error=str(exc): self._island_slot_save_failed(error))
            return
        self.after(
            0,
            lambda w=list(warnings), s=synchronized, d=deleted_orphans:
                self._island_slot_save_succeeded(w, s, d),
        )


    @staticmethod
    def _slot_warning_parts(message):
        """Return a compact category, object id and readable warning detail."""
        value = str(message).strip().lstrip("- ")
        object_id = ""
        import re
        match = re.search(r"ObjectId\s+(-?\d+)|ObjectId:\s*(-?\d+)", value)
        if match:
            object_id = next(group for group in match.groups() if group)
        lowered = value.casefold()
        if "has no gamedata object" in lowered:
            category = "Missing Gamedata"
        elif "guid mismatch" in lowered:
            category = "GUID mismatch"
        elif "position mismatch" in lowered:
            category = "Position mismatch"
        elif "river" in lowered or "bezier" in lowered:
            category = "River pair"
        elif "category" in lowered:
            category = "Slot category"
        else:
            category = "Integration"
        return category, object_id or "-", value

    def _show_slot_validation_warning(self, title, messages, summary=None):
        """Show non-blocking integration findings in a readable warning window."""
        messages = [str(message).strip().lstrip("- ") for message in messages if str(message).strip()]
        if not messages:
            return
        owner = self.slot_map_window if getattr(self, "slot_map_window", None) is not None else self
        window = tk.Toplevel(owner)
        window.title(title)
        window.geometry("980x520")
        window.minsize(760, 380)
        window.transient(owner)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)

        header = tk.Frame(window, padx=18, pady=14)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        tk.Label(header, text="⚠", fg="#d18b00", font=("Segoe UI Symbol", 28, "bold")).grid(
            row=0, column=0, rowspan=2, padx=(0, 14), sticky="n"
        )
        tk.Label(header, text="Slot integration warnings", font=("Segoe UI", 15, "bold"), anchor="w").grid(
            row=0, column=1, sticky="ew"
        )
        description = summary or (
            "The reset was completed, but the restored original XML files contain "
            "slot differences. Review the entries below."
        )
        tk.Label(header, text=description, justify="left", anchor="w", wraplength=820).grid(
            row=1, column=1, sticky="ew", pady=(4, 0)
        )

        count_text = f"{len(messages)} warning{'s' if len(messages) != 1 else ''}"
        tk.Label(window, text=count_text, anchor="w", padx=18, fg="#9a6700").grid(
            row=1, column=0, sticky="ew", pady=(0, 6)
        )

        table_frame = tk.Frame(window, padx=18)
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        table = ttk.Treeview(
            table_frame,
            columns=("category", "object_id", "detail"),
            show="headings",
            selectmode="browse",
        )
        table.heading("category", text="Type")
        table.heading("object_id", text="ObjectId")
        table.heading("detail", text="Details")
        table.column("category", width=150, minwidth=125, stretch=False)
        table.column("object_id", width=190, minwidth=160, stretch=False, anchor="w")
        table.column("detail", width=570, minwidth=320, stretch=True)
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        for message in messages:
            table.insert("", "end", values=self._slot_warning_parts(message))

        detail_var = tk.StringVar(value="Select an entry to display its complete message.")
        detail = tk.Label(
            window, textvariable=detail_var, justify="left", anchor="nw",
            padx=18, pady=8, wraplength=920, relief="groove",
        )
        detail.grid(row=3, column=0, padx=18, pady=(10, 0), sticky="ew")
        def show_selected(_event=None):
            selection = table.selection()
            if selection:
                detail_var.set(table.item(selection[0], "values")[2])
        table.bind("<<TreeviewSelect>>", show_selected)

        actions = tk.Frame(window, padx=18, pady=14)
        actions.grid(row=4, column=0, sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        def copy_all():
            text_value = "\n".join(f"- {message}" for message in messages)
            window.clipboard_clear()
            window.clipboard_append(text_value)
        ttk.Button(actions, text="Copy all", command=copy_all).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="Close", command=lambda: PopupTemplate.close_window(window)).grid(row=0, column=2)
        window.protocol("WM_DELETE_WINDOW", lambda: PopupTemplate.close_window(window))
        PopupTemplate.schedule(window, 30, lambda: PopupTemplate.safe_activate(window))

    def _island_slot_reset(self):
        """Rebuild both patched slot XML files directly from their _original sources."""
        if not messagebox.askyesno(
            "Reset Slot Integration",
            "Reload the complete slot configuration from the _original XML files?\n\n"
            "All slot changes in the patched files will be discarded.",
            parent=self.slot_map_window,
            default="no",
        ):
            return
        try:
            game_original, map_original, game_patched, map_patched = self._island_slot_sources()
            if not game_original.is_file() or not map_original.is_file():
                raise FileNotFoundError("The required _original XML files were not found.")
            for source, target in ((game_original, game_patched), (map_original, map_patched)):
                data = source.read_bytes()
                temp = target.with_suffix(target.suffix + ".reset_tmp")
                temp.write_bytes(data)
                temp.replace(target)
            # Reset must restore the original files even when the originals
            # contain legacy cross-file differences. Those findings are warnings,
            # not a failed reset.
            restored_game = self._slot_parse_xml(game_patched)[0]
            restored_map = self._slot_parse_xml(map_patched)[0]
            report = validate_slot_trees(restored_map.getroot(), restored_game.getroot())
            reset_warnings = list(report.errors) + list(report.warnings)
            self._island_slot_ram_game_tree = None
            self._island_slot_ram_map_tree = None
            self._island_slot_capture_snapshot()
        except (OSError, ET.ParseError, UnicodeError, RuntimeError) as exc:
            messagebox.showerror("Reset Slot Integration", str(exc), parent=self.slot_map_window)
            return
        self.island_slot_selected_ids.clear()
        self._refresh_open_slot_map()
        if reset_warnings:
            self.status_var.set(
                f"Slot configuration reloaded with {len(reset_warnings)} integration warning(s)."
            )
            self._show_slot_validation_warning(
                "Reset Slot Integration - Warnings",
                reset_warnings,
                "The original XML files were restored successfully. The entries below "
                "describe existing cross-file differences and did not block the reset.",
            )
        else:
            self.status_var.set("Slot configuration reloaded from the _original XML files.")

    def _island_slot_selection_clear(self, _event=None):
        if getattr(self, "_mine_placement", None) is not None:
            return self._island_slot_cancel_mine_placement(_event)
        self.island_slot_selection_start = None
        self.island_slot_lasso_points = []
        self.island_slot_lasso_world_points = []
        self.island_slot_selection_world_bounds = None
        self.island_slot_selected_ids = set()
        canvas = getattr(self, "slot_map_canvas", None)
        if canvas is not None and canvas.winfo_exists():
            if self.island_slot_selection_rect:
                canvas.delete(self.island_slot_selection_rect)
            canvas.delete("slot_selection")
            canvas.delete("slot_lasso")
        self.island_slot_selection_rect = None
        return "break" if _event is not None else None

    def _island_slot_lasso_point(self, event):
        points = getattr(self, "island_slot_lasso_points", None)
        if points is None:
            points = self.island_slot_lasso_points = []
        if not points:
            self.island_slot_selection_start = None
            self.island_slot_selection_world_bounds = None
            self.island_slot_selected_ids = set()
            if self.island_slot_selection_rect:
                self.slot_map_canvas.delete(self.island_slot_selection_rect)
                self.island_slot_selection_rect = None
        points.append((event.x, event.y))
        if len(points) >= 3:
            self.island_slot_selected_ids = {
                point[2] for point in self.slot_map_screen_points
                if MapViewTemplate.point_in_polygon(point[0], point[1], points)
            }
            world = [self._island_slot_world(
                type("LassoPoint", (), {"x": x, "y": y})()
            ) for x, y in points]
            self.island_slot_lasso_world_points = list(world)
            xs = [point[0] for point in world]; zs = [point[1] for point in world]
            self.island_slot_selection_world_bounds = (
                min(xs), max(xs), min(zs), max(zs)
            )
        self._island_slot_lasso_draw()
        self.slot_map_selection_var.set(
            f"Lasso points: {len(points)} | Selected island slot objects: "
            f"{len(self.island_slot_selected_ids)}"
        )
        return "break"

    def _island_slot_lasso_draw(self):
        canvas = getattr(self, "slot_map_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("slot_lasso")
        points = getattr(self, "island_slot_lasso_points", ())
        for x, y in points:
            canvas.create_oval(x - 4, y - 4, x + 4, y + 4,
                               fill="#4da3ff", outline="#ffffff",
                               tags="slot_lasso")
        if len(points) >= 2:
            coordinates = [value for point in points for value in point]
            canvas.create_line(*coordinates, fill="#4da3ff", width=2,
                               dash=(4, 2), tags="slot_lasso")
        if len(points) >= 3:
            canvas.create_line(points[-1][0], points[-1][1], points[0][0], points[0][1],
                               fill="#4da3ff", width=2, dash=(4, 2), tags="slot_lasso")

    def _island_slot_select_start(self, event):
        self.island_slot_lasso_points = []
        self.island_slot_lasso_world_points = []
        self.slot_map_canvas.delete("slot_lasso")
        self.island_slot_selection_start = (event.x, event.y)
        return "break"

    def _island_slot_select_move(self, event):
        if self.island_slot_selection_start is None:
            return "break"
        x0, y0 = self.island_slot_selection_start
        if self.island_slot_selection_rect:
            self.slot_map_canvas.delete(self.island_slot_selection_rect)
        self.island_slot_selection_rect = self.slot_map_canvas.create_rectangle(x0, y0, event.x, event.y, outline="#4da3ff", dash=(4, 2), width=2)
        return "break"

    def _island_slot_select_end(self, event):
        if self.island_slot_selection_start is None:
            return "break"
        x0, y0 = self.island_slot_selection_start
        left, right = sorted((x0, event.x)); top, bottom = sorted((y0, event.y))
        self.island_slot_selected_ids = {
            point[2] for point in self.slot_map_screen_points
            if left <= point[0] <= right and top <= point[1] <= bottom
        }
        start_event = type("SelectionPoint", (), {"x": x0, "y": y0})()
        world_a = self._island_slot_world(start_event)
        world_b = self._island_slot_world(event)
        min_x, max_x = sorted((world_a[0], world_b[0]))
        min_z, max_z = sorted((world_a[1], world_b[1]))
        self.island_slot_selection_world_bounds = (min_x, max_x, min_z, max_z)
        self.island_slot_selection_start = None
        # Keep the rectangle visible after selection and subsequent map redraws.
        if self.island_slot_selection_rect:
            self.slot_map_canvas.coords(
                self.island_slot_selection_rect, left, top, right, bottom
            )
        self.slot_map_selection_var.set(f"Selected island slot objects: {len(self.island_slot_selected_ids)} | Right click for Add/Remove")
        return "break"
