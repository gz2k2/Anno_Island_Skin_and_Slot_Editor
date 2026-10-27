"""Filtered, cancellable map-package export. No Tk calls."""
from pathlib import Path
import os
import re
import shutil
import tempfile
import time
import uuid


class MapExportCancelled(RuntimeError):
    pass


def excluded_name(name):
    """Keep *.xml.lnk; exclude actual XML, originals and backup artifacts."""
    name = name.casefold()
    return (name.endswith(('.xml', '.data')) or '_original' in name or '_backup' in name
            or name in {'backup', 'backups', '.backup', '.backups'}
            or bool(re.search(r'\.(?:bak|backup|old)(?:\.|$)', name))
            or name.endswith('~'))


def validate_export_paths(source, destination):
    destination = Path(destination)
    if destination.is_symlink() or (hasattr(destination, 'is_junction') and destination.is_junction()):
        raise ValueError('The export destination must not be a linked directory.')
    source, destination = Path(source).resolve(), destination.resolve()
    if not source.is_dir():
        raise ValueError(f'Map source folder does not exist: {source}')
    if source == destination or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError('The export map folder must be outside the source map folder and must not contain it.')
    return source, destination


def export_map(source, destination, stop_event, progress, *, overwrite=False):
    """Stage a complete filtered copy before replacing a confirmed old export.

    progress(done_bytes, total_bytes, relative_path, done_files, total_files).
    Cancellation/failure before installation leaves an existing export intact.
    """
    source, destination = validate_export_paths(source, destination)
    def check_stop():
        if stop_event.is_set():
            raise MapExportCancelled('Map export cancelled.')
    check_stop()
    if destination.exists() and (not overwrite or not destination.is_dir()):
        raise FileExistsError(f'Export destination already exists: {destination}')
    progress(0, 0, 'Scanning map files...', 0, 0)
    files, directories = [], []
    def walk_error(error):
        raise error
    for folder, dirs, names in os.walk(source, followlinks=False, onerror=walk_error):
        check_stop()
        folder = Path(folder)
        dirs[:] = sorted(
            (n for n in dirs if not excluded_name(n) and n.casefold() != '_tintmap_variants'),
            key=str.casefold,
        )
        for name in dirs:
            path = folder / name
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise ValueError(f'Linked directories are not supported: {path}')
            directories.append(path.relative_to(source))
        for name in sorted(names, key=str.casefold):
            if excluded_name(name):
                continue
            path = folder / name
            if path.is_symlink():
                raise ValueError(f'Symbolic links are not supported: {path}')
            if not path.is_file():
                raise ValueError(f'Not a regular file: {path}')
            files.append((path, path.relative_to(source), path.stat().st_size))
    total = sum(size for _, _, size in files)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.map_export_', dir=destination.parent))
    previous = None
    done = count = 0
    last = 0.0
    warnings = []
    try:
        for relative in directories:
            check_stop()
            (staging / relative).mkdir(parents=True, exist_ok=True)
        for path, relative, size in files:
            check_stop()
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with path.open('rb') as src, target.open('xb') as dst:
                while True:
                    check_stop()
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    dst.write(chunk)
                    done += len(chunk)
                    now = time.monotonic()
                    if now - last >= 0.1:
                        progress(done, total, str(relative), count, len(files))
                        last = now
            shutil.copystat(path, target)
            count += 1
        check_stop()
        if destination.exists():
            if not overwrite or not destination.is_dir() or destination.is_symlink():
                raise FileExistsError(f'Export destination changed: {destination}')
            previous = destination.with_name('.map_previous_' + uuid.uuid4().hex)
            destination.rename(previous)
        try:
            staging.rename(destination)
        except Exception:
            if previous is not None:
                previous.rename(destination)
                previous = None
            raise
        if previous is not None:
            try:
                shutil.rmtree(previous)
            except OSError as exc:
                warnings.append(f'Previous export retained at {previous}: {exc}')
        progress(total, total, 'Export completed', count, len(files))
        return count, done, warnings
    finally:
        if staging.exists():
            shutil.rmtree(staging)
