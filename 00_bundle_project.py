from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent

# Unterordner "packed" definieren und automatisch erstellen, falls nicht vorhanden
PACKED_DIR = ROOT / "packed"
PACKED_DIR.mkdir(parents=True, exist_ok=True)

# Aktuellen Zeitstempel generieren (z. B. 2026-10-22_14-30-00)
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# OUTPUT-Pfad im Unterordner "packed" mit Datum und Uhrzeit nach "PROJECT"
OUTPUT = PACKED_DIR / f"Anno_Island_Reskinner_PROJECT_{timestamp}.txt"

EXTENSIONS = {
    ".py",
    # ".xml",
    # ".json",
    # ".ini",
    # ".config",
    # ".md",
    ".txt",
    ".yml",
}

# Dateinamen, die direkt ausgeschlossen werden sollen
EXCLUDE_FILES = {
    "00_build_onefile.py",
    "00_bundle_project.py",
    "00_unpack_project.py",
    "z_errorlog.md",
    "00_errorlog.md",
    "FUNDING.yml",
    ".gitignore",
}

EXCLUDE = {
    OUTPUT.name,
}

EXCLUDE_DIRS = {
    "__pycache__",
    ".git",
    ".idea",
    ".vscode",
    "venv",
    ".venv",
    "build",
    "custom_profiles",
    "dist",
    "old",
    "Documentation",
    "packed",  # Verhindert, dass der packed-Ordner durchsucht wird
    "RdaConsole",
    "FileDBReader",
    "IslandSkinningFiles",
    "map_tools",
    "map_xml_assets_test",
    "tests",
}


def should_include(path: Path) -> bool:
    if path.name in EXCLUDE:
        return False

    # Hier wird geprüft, ob die Datei in der Ausschlussliste steht
    if path.name in EXCLUDE_FILES:
        return False

    if path.suffix.lower() not in EXTENSIONS:
        return False

    if any(part in EXCLUDE_DIRS for part in path.parts):
        return False

    return True


files = [
    path
    for path in ROOT.rglob("*")
    if path.is_file() and should_include(path)
]

files.sort(
    key=lambda path: str(path.relative_to(ROOT)).lower()
)


with OUTPUT.open(
    "w",
    encoding="utf-8",
    newline="\n",
) as out:

    # Verbesserte, unmissverständliche Instruktion für KI-Agenten
    out.write("=" * 80 + "\n")
    out.write("CRITICAL INSTRUCTIONS FOR AI AGENTS (Gemini, ChatGPT, Claude, Codex, Copilot, etc.):\n")
    out.write("1. This file is a project bundle container.\n")
    out.write("2. When asked to modify a specific file from this bundle, DO NOT output this entire bundle text.\n")
    out.write("3. Instead, ALWAYS output the ENTIRE, complete modified target file (e.g. the specific .py file) from start to finish.\n")
    out.write("4. NEVER use placeholders (like '# ... rest of the code ...') or partial code snippets.\n")
    out.write("=" * 80 + "\n\n")

    out.write("ANNO ISLAND RESKINNER PROJECT BUNDLE\n")

    for path in files:

        relative_path = path.relative_to(ROOT)

        print(f"Adding: {relative_path}")

        try:
            content = path.read_text(
                encoding="utf-8"
            )
        except UnicodeDecodeError:
            content = path.read_text(
                encoding="utf-8",
                errors="replace",
            )

        out.write(
            f"===== FILE: {relative_path} =====\n"
        )

        out.write(content)

        if not content.endswith("\n"):
            out.write("\n")

        out.write(
            f"===== END FILE: {relative_path} =====\n\n"
        )


size_mb = OUTPUT.stat().st_size / 1024 / 1024

print()
print(f"Created: {OUTPUT}")
print(f"Files:   {len(files)}")
print(f"Size:    {size_mb:.2f} MB")