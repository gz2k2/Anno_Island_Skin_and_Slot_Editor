
"""Percentage luminance adjustment of island tintmap DDS files.

The patcher intentionally supports DXT1/BC1 tintmaps only. It keeps a byte-for-byte
backup beside every changed file and always rebuilds from that backup, so changing
brightness repeatedly never applies corrections cumulatively.
Only the original backup and active DDS are retained; no variant cache is written.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import threading
import os
import hashlib
import math
import json
import shutil
import struct
import tempfile

from PIL import Image

_NATIVE_ENCODER_IMPORT_ERROR = None
try:
    from bc7enc import pack_dds as _native_pack_dds
except (ImportError, OSError) as exc:
    _native_pack_dds = None
    _NATIVE_ENCODER_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

_NATIVE_ENCODER_RUNTIME_ERROR = None
_NATIVE_ENCODER_ERROR_LOCK = threading.Lock()


def tintmap_encoder_status():
    """Return the active DDS encoder and any native-loader/runtime failure."""
    if _native_pack_dds is not None and _NATIVE_ENCODER_RUNTIME_ERROR is None:
        return {
            "native": True,
            "name": "bc7enc native DXT1",
            "detail": "Native accelerated DDS compression is available.",
        }
    error = _NATIVE_ENCODER_RUNTIME_ERROR or _NATIVE_ENCODER_IMPORT_ERROR
    return {
        "native": False,
        "name": "Python DXT1 fallback (slow)",
        "detail": error or "The native bc7enc encoder is unavailable.",
    }

BACKUP_SUFFIX = ".tintmap_original"
PATCH_STATE_FILENAME = "tintmap_patch_state.json"
PATCH_ROUTINE_VERSION = 7
TINTMAP_PRESET_FILENAME = "config_tintmap_brightness_presets.json"
DEFAULT_TINTMAP_PRESETS = (
    {"brightness_percent": -25, "comment": "Old World > Enbesa (default)"},
    {"brightness_percent": -30, "comment": "New World > Enbesa (default)"},
)
TINTMAP_MAX_WORKERS = 8


def tintmap_presets_path(config_file: str | Path) -> Path:
    """Return the Tint Map preset path beside the application configuration."""
    return Path(config_file).expanduser().resolve().parent / TINTMAP_PRESET_FILENAME


def validate_tintmap_presets(rows: object) -> list[dict]:
    """Accept only explicit percentage presets; legacy regional presets stay separate."""
    if not isinstance(rows, list):
        raise ValueError("Tint Map presets must be a list.")
    result = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid brightness preset.")
        percent = validate_brightness_percent(row.get("brightness_percent"))
        result.append({"brightness_percent": percent, "comment": str(row.get("comment", "")).strip()})
    return result


def validate_brightness_percent(value) -> int:
    """Reject non-finite, out-of-range or non-5% values without silent rounding."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Brightness must be -90% to +90% in 5% steps.") from None
    if isinstance(value, bool) or not math.isfinite(number) or not -90 <= number <= 90 or number % 5:
        raise ValueError("Brightness must be -90% to +90% in 5% steps.")
    return int(number)


def load_tintmap_presets(config_file: str | Path) -> list[dict]:
    """Load percentage presets without reinterpreting old RGB/region settings."""
    path = tintmap_presets_path(config_file)
    if not path.exists():
        return validate_tintmap_presets([
            dict(record) for record in DEFAULT_TINTMAP_PRESETS
        ])
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or data.get("schema") != 2:
        raise ValueError("Unsupported brightness preset format.")
    records = validate_tintmap_presets(data.get("presets"))
    existing = {
        (record["comment"].casefold(), record["brightness_percent"])
        for record in records
    }
    changed = False
    for default in DEFAULT_TINTMAP_PRESETS:
        key = (default["comment"].casefold(), default["brightness_percent"])
        if key not in existing:
            records.append(dict(default))
            existing.add(key)
            changed = True
    if changed:
        save_tintmap_presets(config_file, records)
    return records


def save_tintmap_presets(
    config_file: str | Path, rows: object,
) -> Path:
    """Validate and atomically save Tint Map presets beside the config file."""
    records = validate_tintmap_presets(rows)
    path = tintmap_presets_path(config_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix="tintmap_presets_", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"schema": 2, "presets": records}, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path

@dataclass(frozen=True)
class TintmapPatchResult:
    tintmaps_folder: Path
    found: int
    changed: int
    restored: int
    skipped: int
    failed: int
    errors: tuple[str, ...]


def find_tintmaps_folder(a7m_path: str | Path, status_callback=None) -> Path:
    """Resolve root/_gamedata/<mapname>/tintmaps case-insensitively."""
    a7m = Path(a7m_path)
    if status_callback is not None:
        status_callback("folder", "Checking selected island file", str(a7m))
    if not a7m.is_file() or a7m.suffix.casefold() != ".a7m":
        raise FileNotFoundError("Select an existing .a7m island file first.")
    gamedata_root = a7m.parent / "_gamedata"
    if status_callback is not None:
        status_callback("folder", "Locating _gamedata folder", str(gamedata_root))
    if not gamedata_root.is_dir():
        raise FileNotFoundError(f"_gamedata folder not found: {gamedata_root}")
    if status_callback is not None:
        status_callback("folder", "Locating island map folder", a7m.stem)
    map_folder = next(
        (p for p in gamedata_root.iterdir()
         if p.is_dir() and p.name.casefold() == a7m.stem.casefold()),
        None,
    )
    if map_folder is None:
        raise FileNotFoundError(
            f"Map folder not found below _gamedata: {a7m.stem}"
        )
    if status_callback is not None:
        status_callback("folder", "Locating tintmaps folder", str(map_folder))
    tintmaps = next(
        (p for p in map_folder.iterdir()
         if p.is_dir() and p.name.casefold() == "tintmaps"),
        None,
    )
    if tintmaps is None:
        raise FileNotFoundError(f"Tintmaps folder not found: {map_folder / 'tintmaps'}")
    if status_callback is not None:
        status_callback("folder_found", "Tintmaps folder found", str(tintmaps))
    return tintmaps


def _dds_format(path: Path) -> str:
    with path.open("rb") as stream:
        header = stream.read(148)
    if len(header) < 128 or header[:4] != b"DDS ":
        return "INVALID"
    fourcc = header[84:88].rstrip(b"\0").decode("ascii", "replace")
    if fourcc == "DX10" and len(header) >= 148:
        dxgi = struct.unpack_from("<I", header, 128)[0]
        return "BC1" if dxgi in (71, 72) else f"DXGI_{dxgi}"
    return "DXT1" if fourcc == "DXT1" else (fourcc or "UNCOMPRESSED")


def _rgb565(rgb):
    r, g, b = rgb
    return ((r * 31 + 127) // 255 << 11) | ((g * 63 + 127) // 255 << 5) | ((b * 31 + 127) // 255)


def _from565(value):
    return (
        ((value >> 11) & 31) * 255 // 31,
        ((value >> 5) & 63) * 255 // 63,
        (value & 31) * 255 // 31,
    )


def _encode_dxt1_block(pixels):
    # Select endpoints along the block's luminance range. For opaque tintmaps
    # endpoint0 must be greater than endpoint1 to force DXT1 four-colour mode.
    darkest = min(pixels, key=lambda c: 2126*c[0] + 7152*c[1] + 722*c[2])
    lightest = max(pixels, key=lambda c: 2126*c[0] + 7152*c[1] + 722*c[2])
    c0, c1 = _rgb565(lightest), _rgb565(darkest)
    if c0 == c1:
        c0 = min(65535, c0 + 1) if c0 < 65535 else c0
        c1 = max(0, c1 - 1) if c0 == c1 else c1
    if c0 < c1:
        c0, c1 = c1, c0
    p0, p1 = _from565(c0), _from565(c1)
    palette = (
        p0, p1,
        tuple((2*p0[i] + p1[i]) // 3 for i in range(3)),
        tuple((p0[i] + 2*p1[i]) // 3 for i in range(3)),
    )
    indices = 0
    for i, pixel in enumerate(pixels):
        index = min(range(4), key=lambda j: sum((pixel[k]-palette[j][k])**2 for k in range(3)))
        indices |= index << (2*i)
    return struct.pack("<HHI", c0, c1, indices)


def _expected_dxt1_payload_size(width: int, height: int) -> int:
    return ((width + 3) // 4) * ((height + 3) // 4) * 8


def _encode_dxt1_native(rgb: Image.Image) -> bytes:
    if _native_pack_dds is None:
        raise RuntimeError("Native BC1 encoder is unavailable")

    rgba = rgb.convert("RGBA")
    width, height = rgba.size
    payload = bytes(_native_pack_dds(rgba.tobytes(), width, height, "DXT1"))
    expected_size = _expected_dxt1_payload_size(width, height)
    if len(payload) != expected_size:
        raise ValueError(
            f"Native DXT1 encoder returned {len(payload)} bytes; "
            f"expected {expected_size} bytes for {width}x{height}."
        )
    return payload


def _encode_dxt1_python(rgb: Image.Image) -> bytes:
    rgb = rgb.convert("RGB")
    width, height = rgb.size
    if width % 4 or height % 4:
        raise ValueError(f"DXT1 dimensions must be divisible by four: {width}x{height}")
    pixels = rgb.load()
    output = bytearray()
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            block = [pixels[bx+x, by+y] for y in range(4) for x in range(4)]
            output.extend(_encode_dxt1_block(block))
    return bytes(output)


def _encode_dxt1(rgb: Image.Image) -> bytes:
    global _NATIVE_ENCODER_RUNTIME_ERROR
    if _native_pack_dds is not None and _NATIVE_ENCODER_RUNTIME_ERROR is None:
        try:
            return _encode_dxt1_native(rgb)
        except Exception as exc:
            # Fall back for compatibility, but preserve the real reason so the
            # UI can clearly report that subsequent files use the slow encoder.
            with _NATIVE_ENCODER_ERROR_LOCK:
                if _NATIVE_ENCODER_RUNTIME_ERROR is None:
                    _NATIVE_ENCODER_RUNTIME_ERROR = f"{type(exc).__name__}: {exc}"
    return _encode_dxt1_python(rgb)


def _transform_image(image: Image.Image, brightness_percent=0) -> Image.Image:
    """Scale original luminance Y only; R/B contain encoded chroma, not RGB."""
    percent = validate_brightness_percent(brightness_percent)
    factor = 1.0 + percent / 100.0
    identity = list(range(256))
    luminance = [max(0, min(255, round(value * factor))) for value in identity]
    return image.convert("RGB").point(identity + luminance + identity)


def _patch_one(path: Path, brightness_percent=0) -> str:
    backup = path.with_name(path.name + BACKUP_SUFFIX)
    if brightness_percent == 0:
        if backup.is_file():
            shutil.copy2(backup, path)
            return "restored"
        return "skipped"
    source = backup if backup.is_file() else path
    fmt = _dds_format(source)
    if fmt not in {"DXT1", "BC1"}:
        return f"skipped:{fmt}"
    if not backup.exists():
        shutil.copy2(path, backup)
    with source.open("rb") as stream:
        raw = stream.read()
    header_size = 148 if raw[84:88] == b"DX10" else 128
    with Image.open(source) as decoded:
        transformed = _transform_image(decoded, brightness_percent)
    payload = _encode_dxt1(transformed)
    expected = transformed.width * transformed.height // 2
    if len(payload) != expected:
        raise RuntimeError(f"Unexpected DXT1 payload size: {len(payload)} != {expected}")
    # Tintmaps in the supplied set have one mipmap. Refuse other layouts rather
    # than silently discarding levels that the game may need.
    mipmaps = struct.unpack_from("<I", raw, 28)[0] or 1
    if mipmaps != 1:
        raise ValueError(f"DDS has {mipmaps} mipmaps; only one-level tintmaps are supported")
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as temp:
            temp.write(raw[:header_size])
            temp.write(payload)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return "changed"



def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class _PatchState:
    """Persist successful per-file operations; never trust a stale file hash."""

    def __init__(self, folder):
        self.folder = folder
        self.path = folder / PATCH_STATE_FILENAME
        self.lock = threading.Lock()
        self.entries = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data.get("schema") != 1 or not isinstance(data.get("files"), dict):
                    raise ValueError("Unsupported patch state format")
                self.entries = data["files"]
                for entry in self.entries.values():
                    if not isinstance(entry, dict) or not all(
                        key in entry for key in ("version", "sha256")
                    ):
                        raise ValueError("Invalid patch state entry")
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f"Invalid tintmap patch state: {self.path}: {exc}") from exc

    def store(self, key, entry):
        with self.lock:
            updated = dict(self.entries)
            if entry is None:
                updated.pop(key, None)
            else:
                updated[key] = entry
            fd, temporary = tempfile.mkstemp(prefix="tintmap_state_", suffix=".tmp", dir=self.folder)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump({"schema": 1, "files": updated}, stream, indent=2, sort_keys=True)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
                self.entries = updated
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)

    def patch(self, path, brightness_percent=0):
        key = path.relative_to(self.folder).as_posix()
        with self.lock:
            entry = self.entries.get(key)
        backup = path.with_name(path.name + BACKUP_SUFFIX)
        if entry is not None:
            if _sha256(path) != entry["sha256"]:
                raise ValueError("Conflict: DDS was externally modified; file was not overwritten")
            if not backup.is_file():
                raise ValueError("Conflict: original backup is missing; file was not overwritten")

        # Preserve originals even for identity selections. Never convert an active
        # variant: all new variants are derived from this immutable source.
        if not backup.is_file():
            _atomic_copy(path, backup)
        original_hash = _sha256(backup)
        identity = brightness_percent == 0
        if identity:
            if _sha256(path) == original_hash:
                self.store(key, None)
                return "skipped:Original already active"
            _atomic_copy(backup, path)
            self.store(key, None)
            return "restored"

        if _dds_format(backup) not in {"DXT1", "BC1"}:
            return "skipped:Unsupported DDS format"
        # No retained variants: encode directly from the immutable original.
        # The writer stages only a temporary file and atomically replaces active DDS.
        if (entry is not None
                and entry.get("brightness_percent") == brightness_percent
                and entry.get("version") == PATCH_ROUTINE_VERSION
                and entry.get("original_sha256") == original_hash):
            return "skipped:Brightness already applied"
        result = _patch_one(path, brightness_percent)
        if result != "changed":
            return result
        self.store(key, {"brightness_percent": brightness_percent,
                         "version": PATCH_ROUTINE_VERSION,
                         "original_sha256": original_hash,
                         "sha256": _sha256(path)})
        return "changed:Applied brightness from original"


def _atomic_copy(source, destination):
    """Replace one file only after its complete copy is available."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp",
                                     dir=destination.parent)
    os.close(fd)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)



def patch_island_tintmaps(a7m_path, brightness_percent=0, workers=None, progress_callback=None):
    """Apply percentage luminance adjustment from immutable original backups."""
    brightness_percent = validate_brightness_percent(brightness_percent)
    encoder = tintmap_encoder_status()
    if progress_callback is not None:
        progress_callback("encoder", encoder["name"], encoder["detail"], encoder["native"])
    folder = find_tintmaps_folder(a7m_path, status_callback=progress_callback)
    if progress_callback is not None:
        progress_callback("scan_start", "Scanning tintmaps folder for DDS files", str(folder))
    files = []
    scanned = 0
    for path in folder.rglob("*"):
        scanned += 1
        if path.is_file() and path.suffix.casefold() == ".dds":
            files.append(path)
        if progress_callback is not None and (scanned == 1 or scanned % 100 == 0):
            progress_callback("scan", scanned, len(files), str(path))
    files.sort(key=lambda p: str(p).casefold())
    if progress_callback is not None:
        progress_callback("scan_done", scanned, len(files), str(folder))
    if not files:
        raise FileNotFoundError(f"No DDS files found below: {folder}")
    patch_state = _PatchState(folder)
    worker_count = max(1, min(int(workers or TINTMAP_MAX_WORKERS), TINTMAP_MAX_WORKERS, len(files)))
    counts = {"changed": 0, "restored": 0, "skipped": 0, "failed": 0}
    errors = []
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="Tintmap") as executor:
        futures = {executor.submit(patch_state.patch, p, brightness_percent): p for p in files}
        completed = 0
        for future in as_completed(futures):
            path = futures[future]
            try:
                state = future.result()
                counts[state.split(":", 1)[0]] += 1
            except Exception as exc:
                state = "failed"
                counts["failed"] += 1
                errors.append(f"{path}: {exc}")
            completed += 1
            if progress_callback is not None:
                progress_callback("patch", completed, len(files), path, state)
    return TintmapPatchResult(folder, len(files), counts["changed"], counts["restored"],
                              counts["skipped"], counts["failed"], tuple(errors))
