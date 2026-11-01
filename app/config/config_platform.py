"""Platform helpers (Windows / Linux) for external tools and file managers."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = os.name == "nt"
EXE_SUFFIX = ".exe" if IS_WINDOWS else ""
RDA_CONSOLE_NAME = f"RdaConsole{EXE_SUFFIX}"
FILE_DB_READER_NAME = f"FileDBReader{EXE_SUFFIX}"


def ensure_executable(path) -> None:
    """Make sure a helper program has the executable bit (no-op on Windows).

    ZIP extraction and some file managers drop the x-bit on Linux.
    """
    if IS_WINDOWS or not path:
        return
    try:
        candidate = Path(str(path))
        if candidate.is_file() and not os.access(candidate, os.X_OK):
            candidate.chmod(candidate.stat().st_mode | 0o111)
    except OSError:
        pass


def find_bundled_tool(base_dirs, folder: str, name: str) -> str:
    """Look for a helper program in <base>/tools/<folder>/<name>."""
    for base in base_dirs:
        candidate = Path(base) / "tools" / folder / name
        if candidate.is_file():
            return str(candidate)
    return ""


def open_folder(path) -> None:
    """Open a folder in the platform's file manager."""
    if IS_WINDOWS:
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(
            ["xdg-open", str(path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
