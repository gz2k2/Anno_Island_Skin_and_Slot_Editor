"""Detect an island's original region from MapSource/SourceMap.

Only the path stored inside the map XML is inspected. The referenced .a7me
file does not need to exist. No XML or texture files are modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET


REGION_NAMES = {
    "moderate": "The Old World",
    "colony01": "The New World",
    "colony02": "Enbesa",
    "colony03": "Arctic",
    "scenario03": "The Old World",
    "scnenario03": "The Old World",  # Accepted spelling from configuration.
    "scenario02": "Enbesa Scenario02",
}


@dataclass(frozen=True)
class RegionInfo:
    source_map: str = ""
    region_key: str = ""
    region_name: str = ""


def region_from_source_map(source_map: str) -> RegionInfo:
    """Match complete path components, ignoring case and slash direction."""
    source_map = str(source_map or "").strip()
    parts = [p.casefold() for p in re.split(r"[\\/]+", source_map) if p]
    # Match folders only, not incidental substrings inside an island filename.
    keys = {part for part in parts[:-1] if part in REGION_NAMES}
    names = {REGION_NAMES[key] for key in keys}
    if len(names) != 1:
        return RegionInfo(source_map=source_map)
    key = next(part for part in parts[:-1] if part in keys)
    return RegionInfo(source_map, key, REGION_NAMES[key])


def region_from_xml_root(root) -> RegionInfo:
    """Read SourceMap, including XML documents with namespaces."""
    paths = []
    for element in root.iter():
        if str(element.tag).rsplit("}", 1)[-1] == "SourceMap":
            text = (element.text or "").strip()
            if text:
                paths.append(text)
    if not paths:
        return RegionInfo()
    infos = [region_from_source_map(path) for path in paths]
    if len(set(paths)) > 1:
        # Do not silently select one of several conflicting source paths.
        return RegionInfo()
    return infos[0]


def read_region(mapname_original_xml, parser=None) -> RegionInfo:
    """Read a map XML. Optional parser may return the app's (tree, ..., ...) tuple.

    Missing files and malformed XML raise exceptions for standalone callers.
    The application mixin below records errors without interrupting loading.
    """
    path = Path(mapname_original_xml)
    parsed = parser(path) if parser is not None else ET.parse(path)
    tree = parsed[0] if isinstance(parsed, tuple) else parsed
    root = tree.getroot() if hasattr(tree, "getroot") else tree
    return region_from_xml_root(root)


class RegionDetectionMixin:
    """Keep original-region metadata synchronized with the selected map XML."""

    def _initialize_region_detection(self):
        self.original_region_info = RegionInfo()
        self.original_region_name = ""
        self.original_region_key = ""
        self.original_source_map = ""
        self.original_region_error = ""
        self._region_path_trace = self.mapname_file_var.trace_add(
            "write", self._refresh_original_region
        )
        self._refresh_original_region()

    def _refresh_original_region(self, *_args):
        # Clear first: missing/unknown files must not retain the previous island.
        info = RegionInfo()
        self.original_region_error = ""
        path = self.mapname_file_var.get().strip()
        if path:
            try:
                info = read_region(path, parser=self._parse_xml_tolerant)
            except Exception as exc:
                self.original_region_error = f"{type(exc).__name__}: {exc}"
        self.original_region_info = info
        self.original_region_name = info.region_name
        self.original_region_key = info.region_key
        self.original_source_map = info.source_map
        for method_name in ("_update_texture_detected_region", "_update_regional_detected_region"):
            update_display = getattr(self, method_name, None)
            if callable(update_display):
                update_display()
        return info
