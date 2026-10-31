"""Small persistent scope patch store for Gamedata, MapName and RD3D XML.

The original XML is immutable. A sibling *_patch.json contains only named
editor scopes. Opening an editor materializes Original + every saved scope.
Reset removes exactly one scope and rebuilds the generated *_patched.xml.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import threading

import app.backend.xml_backend as ET
from app.functions.function_xml_repair import parse_xml_tolerant

SCHEMA = 1


def local_tag(node):
    return node.tag.rsplit("}", 1)[-1] if isinstance(node.tag, str) else ""


def child(node, name):
    return next((item for item in node if local_tag(item) == name), None)


def patch_path(original):
    original = Path(original)
    name = original.name
    if name.endswith("_original.xml"):
        name = name[:-len("_original.xml")] + "_patch.json"
    else:
        name = original.stem + "_patch.json"
    return original.with_name(name)


def generated_path(original):
    original = Path(original)
    name = original.name
    if name.endswith("_original.xml"):
        name = name[:-len("_original.xml")] + "_patched.xml"
    else:
        name = original.stem + "_patched.xml"
    return original.with_name(name)


def _atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.stem}_", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_json(path, value):
    data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    _atomic_bytes(path, data + b"\n")


def _atomic_xml(path, tree):
    fd, name = tempfile.mkstemp(prefix=f".{Path(path).stem}_", suffix=".tmp", dir=Path(path).parent)
    os.close(fd)
    temporary = Path(name)
    try:
        tree.write(temporary, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
        # The generated file may intentionally contain parser-hostile source
        # bytes restored from the immutable original. Validate through the same
        # lossless tolerant parser used to load the source.
        parse_xml_tolerant(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class PatchStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._handlers = {}

    def register(self, kind, scope, handler):
        self._handlers[(str(kind), str(scope))] = handler

    def read(self, original):
        path = patch_path(original)
        if not path.is_file():
            return {"schema": SCHEMA, "scopes": {}}
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("scopes"), dict):
            raise ValueError(f"Unsupported patch format: {path}")
        return data

    def scope(self, original, scope, default=None):
        return deepcopy(self.read(original)["scopes"].get(str(scope), default))

    def save_scope(self, kind, original, scope, payload):
        """Replace one editor scope and regenerate the complete patched XML."""
        with self._lock:
            data = self.read(original)
            if payload in (None, {}, [], ""):
                data["scopes"].pop(str(scope), None)
            else:
                data["scopes"][str(scope)] = payload
            self._write_patch(original, data)
            return self.materialize(kind, original)

    def reset_scope(self, kind, original, scope):
        """Remove only the requested editor scope; preserve every other change."""
        return self.save_scope(kind, original, scope, None)

    def _write_patch(self, original, data):
        path = patch_path(original)
        if data["scopes"]:
            _atomic_json(path, data)
        else:
            path.unlink(missing_ok=True)

    def materialize(self, kind, original, target=None):
        """Build a fresh view from immutable original XML plus all patch scopes."""
        with self._lock:
            original = Path(original)
            tree = parse_xml_tolerant(original)[0]
            scopes = self.read(original)["scopes"]
            priority = {
                "gamedata_slots": 10, "a7minfo_slots": 10,
                "rd3d_instances": 10, "rd3d_object_paths": 20,
                "gamedata_objects": 20, "gamedata_regional": 30,
                "rd3d_settings": 30,
            }
            for scope, payload in sorted(scopes.items(), key=lambda item: priority.get(item[0], 100)):
                handler = self._handlers.get((str(kind), str(scope)))
                if handler is None:
                    raise ValueError(f"No patch handler for {kind}/{scope}.")
                handler(tree, deepcopy(payload))
            target = Path(target) if target else generated_path(original)
            _atomic_xml(target, tree)
            return tree

    def view_without(self, kind, original, excluded_scopes):
        """Build Original + Patch while omitting selected editor scopes."""
        with self._lock:
            tree = parse_xml_tolerant(original)[0]
            excluded = {str(scope) for scope in excluded_scopes}
            scopes = self.read(original)["scopes"]
            priority = {
                "gamedata_slots": 10, "a7minfo_slots": 10,
                "rd3d_instances": 10, "rd3d_object_paths": 20,
                "gamedata_objects": 20, "gamedata_regional": 30,
                "rd3d_settings": 30,
            }
            for scope, payload in sorted(scopes.items(), key=lambda item: priority.get(item[0], 100)):
                if scope in excluded:
                    continue
                handler = self._handlers.get((str(kind), str(scope)))
                if handler is None:
                    raise ValueError(f"No patch handler for {kind}/{scope}.")
                handler(tree, deepcopy(payload))
            return tree

    def view(self, kind, original):
        """Return Original + Patch in memory without relying on a stale cache."""
        with self._lock:
            tree = parse_xml_tolerant(original)[0]
            scopes = self.read(original)["scopes"]
            priority = {
                "gamedata_slots": 10, "a7minfo_slots": 10,
                "rd3d_instances": 10, "rd3d_object_paths": 20,
                "gamedata_objects": 20, "gamedata_regional": 30,
                "rd3d_settings": 30,
            }
            for scope, payload in sorted(scopes.items(), key=lambda item: priority.get(item[0], 100)):
                handler = self._handlers.get((str(kind), str(scope)))
                if handler is None:
                    raise ValueError(f"No patch handler for {kind}/{scope}.")
                handler(tree, deepcopy(payload))
            return tree


def apply_guid_map(tree, payload):
    id_tag = str(payload.get("id_tag", "ID"))
    guid_tag = str(payload.get("guid_tag", "guid"))
    values = {str(key): str(value) for key, value in payload.get("values", {}).items()}
    for node in tree.getroot().iter():
        identifier, guid = child(node, id_tag), child(node, guid_tag)
        key = (identifier.text or "").strip() if identifier is not None else ""
        if key in values and guid is not None:
            guid.text = values[key]


def apply_tag_values(tree, payload):
    values = payload.get("values", {})
    for node in tree.getroot().iter():
        name = local_tag(node)
        if name in values:
            node.text = str(values[name])


def apply_gamedata_regional(tree, payload):
    """Apply Regional Settings and insert VegetationPropSetName when absent."""
    values = {str(key): str(value) for key, value in payload.get("values", {}).items()}
    found = set()
    for node in tree.getroot().iter():
        name = local_tag(node)
        if name in values:
            node.text = values[name]
            found.add(name)
    if "GlobalAmbientName" in values and "GlobalAmbientName" not in found:
        raise ValueError("GlobalAmbientName was not found in gamedata_original.xml.")
    if "VegetationPropSetName" in values and "VegetationPropSetName" not in found:
        session = next((node for node in tree.getroot().iter()
                        if local_tag(node) == "SessionSettings"), None)
        if session is None:
            raise ValueError("SessionSettings was not found; VegetationPropSetName cannot be inserted.")
        namespace = ""
        if isinstance(session.tag, str) and session.tag.startswith("{"):
            namespace = session.tag.split("}", 1)[0] + "}"
        node = ET.Element(namespace + "VegetationPropSetName")
        node.text = values["VegetationPropSetName"]
        session.append(node)

def apply_indexed_children(tree, payload):
    parent_tag = str(payload["parent_tag"])
    container_tag = payload.get("container_tag")
    values = {int(key): str(value) for key, value in payload.get("values", {}).items()}
    matched = 0
    for parent in tree.getroot().iter():
        if local_tag(parent) != parent_tag:
            continue
        if container_tag:
            ancestors = {item: owner for owner in tree.getroot().iter() for item in owner}
            owner = ancestors.get(parent)
            if owner is None or local_tag(owner) != str(container_tag):
                continue
        children = list(parent)
        for index, value in values.items():
            if not 0 <= index < len(children):
                raise ValueError(
                    f"{container_tag or '*'} / {parent_tag} index {index} is out of range.")
            children[index].text = value
        matched += 1
    if matched != 1:
        raise ValueError(
            f"Expected exactly one {container_tag + '/' if container_tag else ''}{parent_tag} "
            f"container, found {matched}.")


def apply_subtree(tree, payload):
    """Replace one named subtree; payload contains only that changed subtree."""
    parent_tag = str(payload["parent_tag"])
    child_tag = str(payload["child_tag"])
    replacement = ET.fromstring(payload["xml"])
    for parent in tree.getroot().iter():
        if local_tag(parent) != parent_tag:
            continue
        old = child(parent, child_tag)
        if old is None:
            parent.append(deepcopy(replacement))
        else:
            index = list(parent).index(old)
            new = deepcopy(replacement)
            new.tail = old.tail
            parent.remove(old)
            parent.insert(index, new)
        break


def _object_records(root):
    result = {}
    for parent in root.iter():
        for node in list(parent):
            identifier, guid, position = child(node, "ID"), child(node, "guid"), child(node, "Position")
            if identifier is not None and guid is not None and position is not None:
                key = (identifier.text or "").strip()
                if key:
                    result[key] = (parent, node)
    return result


def _object_container(root):
    candidates = []
    for parent in root.iter():
        count = sum(1 for node in parent
                    if child(node, "ID") is not None and child(node, "guid") is not None
                    and child(node, "Position") is not None)
        if count:
            candidates.append((count, parent))
    if not candidates:
        raise ValueError("No Gamedata object container was found.")
    return max(candidates, key=lambda item: item[0])[1]


def build_gamedata_slot_patch(original_tree, current_tree):
    original = _object_records(original_tree.getroot())
    current = _object_records(current_tree.getroot())
    upserts = {}
    for object_id, (_parent, node) in current.items():
        old = original.get(object_id)
        if old is None or ET.tostring(old[1]) != ET.tostring(node):
            upserts[object_id] = ET.tostring(node, encoding="unicode")
    removed = sorted(set(original) - set(current))
    groups = [
        ET.tostring(node, encoding="unicode")
        for node in current_tree.getroot().iter()
        if local_tag(node) == "ObjectGroups"
    ]
    return {"upserts": upserts, "removed": removed, "object_groups": groups}


def apply_gamedata_slots(tree, payload):
    records = _object_records(tree.getroot())
    for object_id in payload.get("removed", []):
        record = records.get(str(object_id))
        if record is not None:
            record[0].remove(record[1])
    records = _object_records(tree.getroot())
    container = _object_container(tree.getroot())
    for object_id, xml in payload.get("upserts", {}).items():
        replacement = ET.fromstring(xml)
        record = records.get(str(object_id))
        if record is None:
            container.append(replacement)
        else:
            parent, old = record
            index = list(parent).index(old)
            replacement.tail = old.tail
            parent.remove(old)
            parent.insert(index, replacement)
    replacements = [ET.fromstring(xml) for xml in payload.get("object_groups", [])]
    existing = [node for node in tree.getroot().iter() if local_tag(node) == "ObjectGroups"]
    if len(existing) != len(replacements):
        raise ValueError("ObjectGroups container count differs from the slot patch.")
    parents = {child_node: parent for parent in tree.getroot().iter() for child_node in parent}
    for old, replacement in zip(existing, replacements):
        parent = parents[old]
        index = list(parent).index(old)
        replacement.tail = old.tail
        parent.remove(old)
        parent.insert(index, replacement)


def build_a7minfo_slot_patch(current_tree):
    slot_objects = next((node for node in current_tree.getroot().iter()
                         if local_tag(node) == "SlotObjects"), None)
    return {"xml": ET.tostring(slot_objects, encoding="unicode") if slot_objects is not None else None}


def apply_a7minfo_slots(tree, payload):
    old = next((node for node in tree.getroot().iter() if local_tag(node) == "SlotObjects"), None)
    xml = payload.get("xml")
    if old is None and not xml:
        return
    parents = {child_node: parent for parent in tree.getroot().iter() for child_node in parent}
    if old is not None:
        parent = parents[old]
        index = list(parent).index(old)
        tail = old.tail
        parent.remove(old)
        if xml:
            replacement = ET.fromstring(xml)
            replacement.tail = tail
            parent.insert(index, replacement)
        return
    metadata = next((node for node in tree.getroot().iter()
                     if local_tag(node) == "ObjectMetaInfo"), None)
    if metadata is None:
        raise ValueError("A7MInfo has no ObjectMetaInfo container for SlotObjects.")
    metadata.append(ET.fromstring(xml))


PATCH_STORE = PatchStore()
PATCH_STORE.register("gamedata", "gamedata_slots", apply_gamedata_slots)
PATCH_STORE.register("a7minfo", "a7minfo_slots", apply_a7minfo_slots)
PATCH_STORE.register("gamedata", "gamedata_objects", apply_guid_map)
PATCH_STORE.register("mapname", "gamedata_objects", apply_guid_map)
PATCH_STORE.register("gamedata", "gamedata_regional", apply_gamedata_regional)
PATCH_STORE.register("rd3d", "rd3d_settings", apply_tag_values)
PATCH_STORE.register("rd3d", "rd3d_object_paths", apply_indexed_children)
PATCH_STORE.register("rd3d", "rd3d_instances", apply_subtree)
