"""Fast dynamic merge of built-in RD3D data and user-defined object content."""
from __future__ import annotations

import json
from pathlib import Path
import time

from app.config.config_rd3d import (
    DEFAULT_RD3D_CATEGORY, RD3D_CATEGORIES, RD3D_REGIONS,
    rd3d_category_for_object, rd3d_regions_for_object,
)
from app.database.database_props import RD3D_OBJECT_DATABASE

_FILE_CACHE = {}
_SNAPSHOT_CACHE = {}
SIGNATURE_CHECK_INTERVAL_SECONDS = 0.5
CUSTOM_MARKER = " (c)"


def _base_folder(config_file):
    return Path(config_file).expanduser().resolve().parent


def custom_objects_path(config_file):
    return _base_folder(config_file) / "custom_objects.json"


def custom_object_options_path(config_file):
    return _base_folder(config_file) / "custom_object_options.json"


def _signature(path):
    try:
        stat = path.stat()
        return (stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None


def _json_cached(path, default, *, strict=False):
    signature = _signature(path)
    if signature is None:
        _FILE_CACHE.pop(path, None)
        return default
    cached = _FILE_CACHE.get(path)
    if cached is not None and cached[0] == signature:
        if isinstance(cached[1], Exception):
            if strict:
                raise cached[1]
            return default
        return cached[1]
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        _FILE_CACHE[path] = (signature, exc)
        if strict:
            raise
        return default
    _FILE_CACHE[path] = (signature, value)
    return value


def _split_values(value):
    return tuple(part.strip() for part in str(value or "").split(",") if part.strip())


def _unique(values):
    result, seen = [], set()
    for value in values:
        value = str(value or "").strip(); key = value.casefold()
        if value and key not in seen:
            seen.add(key); result.append(value)
    return result


def load_custom_objects(config_file, *, strict=False):
    data = _json_cached(custom_objects_path(config_file), {}, strict=strict)
    try:
        if not isinstance(data, dict) or data.get("schema") != 1:
            if not data and not custom_objects_path(config_file).exists(): return []
            raise ValueError("Unsupported custom objects file format.")
        rows = data.get("objects")
        if not isinstance(rows, list): raise ValueError("Objects must be a list.")
        result, seen = [], set()
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict): raise ValueError(f"Invalid object record at row {index}.")
            record = {key: str(row.get(key, "")).strip() for key in ("region", "category", "object")}
            if not all(record.values()): raise ValueError(f"Region, Category and Object must not be empty (row {index}).")
            identity = tuple(record[k].casefold() for k in ("region", "category", "object"))
            if identity in seen: raise ValueError(f"Duplicate object record at row {index}.")
            seen.add(identity); result.append(record)
        return result
    except ValueError:
        if strict: raise
        return []


def load_custom_object_options(config_file, *, strict=False):
    path = custom_object_options_path(config_file)
    data = _json_cached(path, {}, strict=strict)
    try:
        if not isinstance(data, dict) or data.get("schema") != 1:
            if not data and not path.exists(): return {"region": [], "category": []}
            raise ValueError("Unsupported custom selection options format.")
        result = {}
        for field in ("region", "category"):
            values = data.get(field)
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() or "," in v for v in values):
                raise ValueError(f"Invalid custom {field} options.")
            result[field] = sorted(_unique(values), key=str.casefold)
        return result
    except ValueError:
        if strict: raise
        return {"region": [], "category": []}


def _snapshot(config_file):
    config_key = str(config_file)
    now = time.monotonic()
    cached = _SNAPSHOT_CACHE.get(config_key)
    if cached is not None and now - cached[0] < SIGNATURE_CHECK_INTERVAL_SECONDS:
        return cached[2]
    signatures = (
        _signature(custom_objects_path(config_file)),
        _signature(custom_object_options_path(config_file)),
    )
    if cached is not None and cached[1] == signatures:
        _SNAPSHOT_CACHE[config_key] = (now, signatures, cached[2])
        return cached[2]

    objects = load_custom_objects(config_file)
    options = load_custom_object_options(config_file)
    by_path = {row["object"].casefold(): row for row in objects}

    # (c) means explicitly user-created option. Merely assigning a custom object
    # to an existing built-in category/region must not mark that built-in value.
    custom_categories = {value.casefold() for value in options["category"]}
    custom_regions = {value.casefold() for value in options["region"]}
    builtin_categories = {value.casefold() for value in RD3D_CATEGORIES}
    # Existing built-in categories that contain at least one custom object get (*).
    custom_object_builtin_categories = {
        row["category"].casefold() for row in objects
        if row["category"].casefold() in builtin_categories
        and row["category"].casefold() not in custom_categories
    }

    database = tuple(
        (source, path, count)
        for source, path, count in RD3D_OBJECT_DATABASE
        if str(path or "").strip().casefold() not in by_path
    ) + tuple((row["region"], row["object"], 0) for row in objects)

    categories = tuple(sorted(_unique(
        list(RD3D_CATEGORIES) + options["category"] +
        [row["category"] for row in objects]
    ), key=str.casefold))
    region_values = list(RD3D_REGIONS) + options["region"]
    for row in objects:
        region_values.extend(_split_values(row["region"]))
    regions = tuple(sorted(_unique(region_values), key=str.casefold))

    # Precompute all metadata in one database pass. Previously the category
    # picker scanned every object once per category, causing O(categories*objects).
    category_paths = {category: set() for category in categories}
    category_regions = {category: set() for category in categories}
    path_categories = {}
    path_regions = {}
    for _source, path, _count in database:
        path = str(path or "").strip()
        if not path:
            continue
        key = path.casefold()
        custom_row = by_path.get(key)
        if custom_row is not None:
            category = custom_row["category"]
            object_regions = _split_values(custom_row["region"])
        else:
            category = rd3d_category_for_object(path) or DEFAULT_RD3D_CATEGORY
            object_regions = tuple(rd3d_regions_for_object(path))
        path_categories[key] = category
        path_regions[key] = object_regions
        category_paths.setdefault(category, set()).add(key)
        category_regions.setdefault(category, set()).update(object_regions)

    category_rows = tuple({
        "category": category,
        "variations": len(category_paths.get(category, ())),
        "regions": tuple(
            region for region in regions
            if region.casefold() in {
                value.casefold() for value in category_regions.get(category, ())
            }
        ),
    } for category in sorted(category_paths, key=str.casefold))

    snapshot = dict(
        objects=objects, options=options, by_path=by_path, database=database,
        categories=categories, regions=regions,
        custom_categories=custom_categories, custom_regions=custom_regions,
        custom_object_builtin_categories=custom_object_builtin_categories,
        path_categories=path_categories, path_regions=path_regions,
        category_rows=category_rows,
    )
    _SNAPSHOT_CACHE[config_key] = (now, signatures, snapshot)
    return snapshot

def invalidate_custom_content_cache(config_file=None):
    """Optional immediate invalidation after writes; file signatures also auto-invalidate."""
    _FILE_CACHE.clear()
    if config_file is None: _SNAPSHOT_CACHE.clear()
    else: _SNAPSHOT_CACHE.pop(str(config_file), None)


def get_combined_object_database(config_file): return _snapshot(config_file)["database"]
def get_combined_categories(config_file): return _snapshot(config_file)["categories"]
def get_combined_regions(config_file): return _snapshot(config_file)["regions"]


def get_category_for_object(path, config_file):
    key = str(path or "").strip().casefold()
    snapshot = _snapshot(config_file)
    category = snapshot["path_categories"].get(key)
    return category if category is not None else (
        rd3d_category_for_object(path) or DEFAULT_RD3D_CATEGORY
    )


def get_regions_for_object(path, config_file):
    key = str(path or "").strip().casefold()
    snapshot = _snapshot(config_file)
    regions = snapshot["path_regions"].get(key)
    return regions if regions is not None else tuple(rd3d_regions_for_object(path))


def get_combined_category_rows(config_file):
    return _snapshot(config_file)["category_rows"]


def is_custom_category(value, config_file):
    return str(value or "").strip().casefold() in _snapshot(config_file)["custom_categories"]


def is_custom_region(value, config_file):
    return str(value or "").strip().casefold() in _snapshot(config_file)["custom_regions"]


def is_custom_object(path, config_file):
    return str(path or "").strip().casefold() in _snapshot(config_file)["by_path"]


def display_object(path, config_file):
    path = str(path or "").strip()
    return path + CUSTOM_MARKER if path and is_custom_object(path, config_file) else path


def display_category(value, config_file):
    value = str(value or "").strip()
    if not value:
        return value
    snapshot = _snapshot(config_file)
    key = value.casefold()
    if key in snapshot["custom_categories"]:
        return value + CUSTOM_MARKER
    if key in snapshot["custom_object_builtin_categories"]:
        return value + " (*)"
    return value


def display_region(value, config_file):
    value = str(value or "").strip()
    return value + CUSTOM_MARKER if value and is_custom_region(value, config_file) else value


def display_regions(values, config_file):
    return tuple(display_region(value, config_file) for value in values)


def get_regions_for_category(category, config_file):
    target = str(category or "").strip().casefold()
    for row in _snapshot(config_file)["category_rows"]:
        if row["category"].casefold() == target:
            return row["regions"]
    return ()
