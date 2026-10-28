import os
import shutil
import subprocess
import sys
from pathlib import Path

# ============================================================
# Configuration
# ============================================================
LAUNCHER_NAME = "Anno_Island_Editor.py"
APP_NAME_BASE = "Anno_Island_Skin_and_Slot_Editor"
VERSION_FILE = "version.txt"
REQUIREMENTS_FILE = "requirements.txt"
WINDOWED = True
ONEFILE = True
CLEAN_BUILD = True

# Optional:
ICON_FILE = None
# Example:
# ICON_FILE = "icon.ico"

# Bundled read-only resources.
DATA_DIRS = (
    "material_sets",
)
DATA_FILES = (
    VERSION_FILE,
)

# The project is now a real package hierarchy. These package roots are made
# explicit for PyInstaller; normal imports are still discovered automatically.
HIDDEN_IMPORTS = (
    "app.main",
    "app.ui.ui",
    "app.backend.xml_backend",
    "app.config.config_colors",
    "app.config.config_gamedata",
    "app.config.config_rd3d",
    "app.config.config_slot",
    "app.database.database_props",
    "app.functions.function_custom_content",
    "app.functions.function_density",
    "app.functions.function_island_slots",
    "app.functions.function_map_export",
    "app.functions.function_map_selection",
    "app.functions.function_place_object",
    "app.functions.function_region",
    "app.functions.function_slot_validation",
    "app.functions.function_xml_repair",
    "app.functions.functions_tintmaps",
    "app.templates.template_category_picker",
    "app.templates.template_map_view",
    "app.templates.template_popup",
    "app.templates.template_profiles",
    "app.templates.template_statuswindow",
    "app.templates.template_table",
    "app.templates.template_treeview",
    "app.ui.tabs.ui_tab_custom_content",
    "app.ui.tabs.ui_tab_files_and_folders",
    "app.ui.tabs.ui_tab_finalize",
    "app.ui.tabs.ui_tab_helpers",
    "app.ui.tabs.ui_tab_material_sets",
    "app.ui.tabs.ui_tab_object_configuration",
    "app.ui.tabs.ui_tab_regional_settings",
    "app.ui.tabs.ui_tab_settings",
    "app.ui.tabs.ui_tab_slot_configuration",
    "app.ui.tabs.ui_tab_start",
    "app.ui.tabs.ui_tab_texture_settings",
)

# Tests are intentionally not bundled into the application EXE.
EXCLUDED_MODULES = (
    "tests",
)

# ============================================================
# Paths
# ============================================================
BASE_DIR = Path(__file__).resolve().parent


def read_version():
    version_path = BASE_DIR / VERSION_FILE
    try:
        version = version_path.read_text(encoding="utf-8-sig").strip()
    except OSError as exc:
        raise RuntimeError(f"Could not read version file: {version_path}") from exc

    if not version:
        raise RuntimeError(f"Version file is empty: {version_path}")

    invalid_chars = '<>:"/\\|?*'
    if any(char in version for char in invalid_chars) or any(ord(char) < 32 for char in version):
        raise RuntimeError(f"Version contains invalid filename characters: {version!r}")

    return version


APP_VERSION = read_version()
APP_NAME = f"{APP_NAME_BASE}_v{APP_VERSION}"

LAUNCHER_PATH = BASE_DIR / LAUNCHER_NAME
APP_DIR = BASE_DIR / "app"
BUILD_DIR = BASE_DIR / "build"
DIST_DIR = BASE_DIR / "dist"
SPEC_FILE = BASE_DIR / f"{APP_NAME}.spec"
REQUIREMENTS_PATH = BASE_DIR / REQUIREMENTS_FILE


# ============================================================
# Helper
# ============================================================
def print_header(text):
    print()
    print("=" * 70)
    print(text)
    print("=" * 70)
    print()


def module_path(module_name):
    """Return the source path for a dotted local module name."""
    return BASE_DIR.joinpath(*module_name.split(".")).with_suffix(".py")


def install_requirements():
    """Install all build/runtime dependencies from requirements.txt."""
    if not REQUIREMENTS_PATH.is_file():
        print(f"ERROR: Requirements file not found: {REQUIREMENTS_PATH}")
        return False

    print_header("Installing requirements")
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        str(REQUIREMENTS_PATH),
    ]
    print(" ".join(f'"{item}"' if " " in item else item for item in command))
    try:
        subprocess.run(command, cwd=BASE_DIR, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print()
        print(f"ERROR: Could not install requirements: {exc}")
        return False
    return True


def check_project():
    """Validate the refactored package layout before deleting old outputs."""
    missing = []

    if not LAUNCHER_PATH.is_file():
        missing.append(str(LAUNCHER_PATH))
    if not APP_DIR.is_dir():
        missing.append(str(APP_DIR))
    if not REQUIREMENTS_PATH.is_file():
        missing.append(str(REQUIREMENTS_PATH))

    package_dirs = (
        APP_DIR,
        APP_DIR / "backend",
        APP_DIR / "config",
        APP_DIR / "database",
        APP_DIR / "functions",
        APP_DIR / "templates",
        APP_DIR / "ui",
        APP_DIR / "ui" / "tabs",
    )
    for package_dir in package_dirs:
        init_file = package_dir / "__init__.py"
        if not init_file.is_file():
            missing.append(str(init_file))

    module_files = [module_path(name) for name in HIDDEN_IMPORTS]
    missing.extend(str(path) for path in module_files if not path.is_file())

    for directory in DATA_DIRS:
        path = BASE_DIR / directory
        if not path.is_dir():
            missing.append(str(path))

    for filename in DATA_FILES:
        path = BASE_DIR / filename
        if not path.is_file():
            missing.append(str(path))

    if missing:
        print("ERROR: Required project files/resources are missing:")
        print("\n".join(missing))
        return False

    try:
        python_files = [LAUNCHER_PATH, *APP_DIR.rglob("*.py")]
        for path in python_files:
            compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
    except (OSError, UnicodeError, SyntaxError) as exc:
        print(f"ERROR: Project validation failed: {exc}")
        return False

    for package in ("customtkinter", "PIL"):
        try:
            __import__(package)
        except ImportError:
            print(f"ERROR: Missing dependency: {package}.")
            print("Install customtkinter and pillow before building.")
            return False

    return True


def check_pyinstaller():
    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("PyInstaller is not installed.")
        print()
        print("Install it with:")
        print()
        print("    pip install pyinstaller")
        print()
        return False


def clean_old_build():
    print("Cleaning old build files...")
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if SPEC_FILE.exists():
        SPEC_FILE.unlink()


def build():
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(LAUNCHER_PATH),
        "--name",
        APP_NAME,
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(BASE_DIR),
        "--clean",
        "--noconfirm",
        "--paths",
        str(BASE_DIR),
        "--collect-all",
        "customtkinter",
        "--collect-all",
        "PIL",
    ]

    for directory in DATA_DIRS:
        source = BASE_DIR / directory
        command.extend(["--add-data", f"{source}{os.pathsep}{directory}"])

    for filename in DATA_FILES:
        source = BASE_DIR / filename
        command.extend(["--add-data", f"{source}{os.pathsep}."])

    for module_name in HIDDEN_IMPORTS:
        command.extend(["--hidden-import", module_name])

    for module_name in EXCLUDED_MODULES:
        command.extend(["--exclude-module", module_name])

    if ONEFILE:
        command.append("--onefile")
    if WINDOWED:
        command.append("--windowed")

    if ICON_FILE:
        icon_path = BASE_DIR / ICON_FILE
        if icon_path.is_file():
            command.extend(["--icon", str(icon_path)])
        else:
            print(f"WARNING: Icon not found: {icon_path}")

    print_header("PyInstaller command")
    print(" ".join(f'"{item}"' if " " in item else item for item in command))

    print_header("Building EXE")
    try:
        subprocess.run(command, cwd=BASE_DIR, check=True)
    except subprocess.CalledProcessError as exc:
        print()
        print("BUILD FAILED")
        print()
        print(f"PyInstaller returned exit code {exc.returncode}.")
        return False

    return True


def show_result():
    exe_path = DIST_DIR / f"{APP_NAME}.exe"

    print_header("BUILD SUCCESSFUL")
    if exe_path.is_file():
        size_mb = exe_path.stat().st_size / 1024 / 1024
        print("EXE:")
        print(exe_path)
        print()
        print(f"Size: {size_mb:.1f} MB")
    else:
        print("Build completed, but EXE was not found.")
        print()
        print("Expected:")
        print(exe_path)


def main():
    print_header("Anno Island Reskinner - OneFile Builder")
    print("Python:")
    print(sys.executable)
    print()
    print("Launcher:")
    print(LAUNCHER_PATH)
    print()
    print("Application package:")
    print(APP_DIR)

    if not REQUIREMENTS_PATH.is_file():
        print(f"ERROR: Requirements file not found: {REQUIREMENTS_PATH}")
        return 1
    if not install_requirements():
        return 1
    if not check_project():
        return 1
    if not check_pyinstaller():
        return 1
    if CLEAN_BUILD:
        clean_old_build()
    if not build():
        return 1

    show_result()
    return 0


if __name__ == "__main__":
    sys.exit(main())
