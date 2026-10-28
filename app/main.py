from __future__ import annotations

from app.functions.function_custom_content import (
    get_combined_categories,
    get_combined_object_database,
    get_combined_regions,
    get_category_for_object,
    get_regions_for_category,
    get_regions_for_object,
)
from app.functions.function_region import RegionDetectionMixin

import configparser
import csv
import colorsys
import hashlib
import ctypes
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import queue
import re
import random
import shutil
import subprocess
import sys
import threading
import time
import app.backend.xml_backend as ET
from app.functions.function_xml_repair import parse_xml_tolerant, sanitize_xml_text
import webbrowser
import urllib.request
import urllib.error
from PIL import Image, ImageTk
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from app.ui.ui import UIMixin
from app.templates.template_popup import PopupTemplate

APP_NAME = "Anno 1800 Island Skin and Slot Editor by gz2k2"

try:
    from app.config.config_gamedata import (
        GLOBAL_AMBIENT_OPTIONS,
        VEGETATION_PROP_SET_OPTIONS,
        DEFAULT_GLOBAL_AMBIENT,
        DEFAULT_VEGETATION_PROP_SET,
    )
except ImportError as exc:
    raise RuntimeError(
        "config_gamedata.py is missing. Place it in the same folder as the application/script."
    ) from exc


try:
    from app.config.config_rd3d import RD3D_CATEGORIES, DEFAULT_RD3D_CATEGORY, rd3d_category_for_object
except ImportError as exc:
    raise RuntimeError(
        "config_rd3d.py is missing. Place it in the same folder as the application/script."
    ) from exc
try:
    from app.database.database_props import RD3D_OBJECT_DATABASE
except ImportError as exc:
    raise RuntimeError(
        "database_props.py is missing. Place it in the same folder as the application/script."
    ) from exc
try:
    from app.config.config_colors import TYPE_CATEGORY_COLORS, TYPE_CATEGORY_COLOR_FAMILIES, DEFAULT_TYPE_COLOR
except ImportError as exc:
    raise RuntimeError(
        "config_colors.py is missing. Place it in the same folder as the application/script."
    ) from exc

def get_app_dir() -> Path:
    """Return the persistent application directory.

    In a normal Python run this is the directory containing the .py file.
    In a PyInstaller build this is the directory containing the launched .exe,
    not PyInstaller's temporary extraction directory.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_DIR = get_app_dir()

def get_bundle_dir() -> Path:
    """Return the directory containing bundled read-only resources.

    In a PyInstaller onefile build this is the temporary extraction directory
    (sys._MEIPASS). During a normal Python run it is the script directory.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parent.parent

BUNDLE_DIR = get_bundle_dir()

BUNDLED_XML_DIR = BUNDLE_DIR / "data" / "xml"
BUNDLED_XML_FORMATS = {
    "gamedata": BUNDLED_XML_DIR / "Island_Gamedata_v3.xml",
    "rd3d": BUNDLED_XML_DIR / "Island_RD3D.xml",
    "a7minfo": BUNDLED_XML_DIR / "a7minfo.xml",
    "tmc": BUNDLED_XML_DIR / "tmc.xml",
}

VERSION_FILE = BUNDLE_DIR / "version.txt"
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/gz2k2/Anno_Island_Skin_and_Slot_Editor/refs/heads/main/version.txt"
UPDATE_PAGE_URL = "https://github.com/gz2k2/Anno_Island_Skin_and_Slot_Editor"

def read_local_version() -> str:
    try:
        value = VERSION_FILE.read_text(encoding="utf-8-sig").strip()
        return value or "unknown"
    except (OSError, UnicodeError):
        return "unknown"

def version_key(version: str):
    """Create a numeric comparison key from versions such as 0.69.12 or v0.69.12."""
    parts = re.findall(r"\d+", (version or "").strip())
    return tuple(int(part) for part in parts) if parts else ()

APP_VERSION = read_local_version()
APP_TITLE = f"{APP_NAME} v{APP_VERSION}" if APP_VERSION != "unknown" else APP_NAME
CONFIG_FILE = APP_DIR / "config.ini"
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class CancelledError(RuntimeError):
    pass


class App(RegionDetectionMixin, UIMixin, ctk.CTk):
    # Constants required by the decoupled UI layer.
    APP_NAME = APP_NAME
    APP_TITLE = APP_TITLE
    APP_VERSION = APP_VERSION
    UPDATE_PAGE_URL = UPDATE_PAGE_URL
    CONFIG_FILE = CONFIG_FILE

    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1200x900")
        self.minsize(940, 700)

        self.events: queue.Queue = queue.Queue()
        self.process: subprocess.Popen | None = None
        self.parallel_processes: set[subprocess.Popen] = set()
        self.parallel_processes_lock = threading.Lock()
        self.console_helper_threads: set[threading.Thread] = set()
        self.console_helper_threads_lock = threading.Lock()
        self.worker: threading.Thread | None = None
        self.stop_event = threading.Event()

        self.rda_var = tk.StringVar()
        self.fdb_var = tk.StringVar()
        self.gamedata_format_var = tk.StringVar(value=str(BUNDLED_XML_FORMATS["gamedata"]))
        self.rd3d_format_var = tk.StringVar(value=str(BUNDLED_XML_FORMATS["rd3d"]))
        self.a7minfo_format_var = tk.StringVar(value=str(BUNDLED_XML_FORMATS["a7minfo"]))
        self.tmc_format_var = tk.StringVar(value=str(BUNDLED_XML_FORMATS["tmc"]))
        self.tmc_parallel_var = tk.StringVar(value="4")
        self.gamefiles_var = tk.StringVar()
        self.island_export_custom_var = tk.StringVar()
        self.island_export_create_links_var = tk.BooleanVar(value=True)
        self.original_maps_var = tk.StringVar()
        self.default_custom_maps_var = tk.StringVar()
        self.custom_map_folder_var = tk.StringVar()
        self.map_export_folder_var = tk.StringVar()
        self.custom_material_sets_folder_var = tk.StringVar()
        self.custom_objects_folder_var = tk.StringVar()
        self.unpack_file_var = tk.StringVar()
        self.pack_file_var = tk.StringVar()
        self.unpack_a7minfo_var = tk.BooleanVar(value=True)
        self.unpack_gamedata_var = tk.BooleanVar(value=True)
        self.unpack_rd3d_var = tk.BooleanVar(value=True)
        self.unpack_tmc_var = tk.BooleanVar(value=True)
        self.backup_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Ready")
        self.rd3d_save_info_var = tk.StringVar(value="")
        self.gamedata_file_var = tk.StringVar()
        self.mapname_file_var = tk.StringVar()
        self._initialize_region_detection()
        # Files and Folders tab uses the same path variables as the functional tabs.
        # rd3d_file_var and tmc_data_meshes_var are initialized below and likewise shared.
        self.global_ambient_var = tk.StringVar(value="-")
        self.vegetation_prop_set_var = tk.StringVar(value="-")
        self.new_global_ambient_var = tk.StringVar(value=DEFAULT_GLOBAL_AMBIENT)
        self.new_vegetation_var = tk.StringVar(value=DEFAULT_VEGETATION_PROP_SET)
        self.rd3d_file_var = tk.StringVar()
        self.material_set_var = tk.StringVar(value="-")
        self.new_material_set_var = tk.StringVar()
        self.material_set_dropdown_var = tk.StringVar(value="Select XML...")
        self.rd3d_file_names = []
        self.rd3d_objects_window = None
        self.rd3d_database_window = None
        self.rd3d_database_table = None
        self.rd3d_database_sort_column = "type"
        self.rd3d_database_sort_reverse = False
        self.rd3d_current_table = None
        self.rd3d_new_table = None
        self.rd3d_file_table = None
        self.rd3d_map_points = []
        self.rd3d_map_after_id = None
        self.rd3d_map_image_path = None
        self.rd3d_map_image_source = None
        self.rd3d_map_image_tk = None
        self.rd3d_map_zoom = 0.8
        self.rd3d_map_pan_x = 0.0
        self.rd3d_map_pan_y = 0.0
        self.rd3d_map_shared_zoom = 1.0
        self.rd3d_map_shared_pan_x = 0.0
        self.rd3d_map_shared_pan_y = 0.0
        self.rd3d_map_pan_start = None
        self.rd3d_map_hover_point = None
        self.rd3d_map_category_visible = {
            category: True for category in get_combined_categories(self.CONFIG_FILE)
        }
        self.rd3d_map_category_buttons = {}
        self.rd3d_category_colors = {}
        self.rd3d_found_categories = []
        self.rd3d_map_window = None
        self.rd3d_map_canvas = None
        self.rd3d_map_maximize_button = None
        self.rd3d_map_info_var = tk.StringVar(
            value="Positions from <Instances> are displayed using X and Z."
        )
        self.rd3d_map_selection_var = tk.StringVar(
            value="Click a point to display its index, prop, and position."
        )
        self.tmc_data_meshes_var = tk.StringVar()
        self.tmc_data_rows = []
        self.tmc_data_file_rows = {}
        self.tmc_data_status_var = tk.StringVar(value="Select the folder containing the TMC XML subfolders.")

        self._build_ui()
        self._load_config()
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(700, self._start_version_check)

    def _start_version_check(self):
        """Check the published version without blocking the Tk UI."""
        threading.Thread(target=self._version_check_worker, daemon=True).start()

    def _version_check_worker(self):
        if APP_VERSION == "unknown":
            return
        try:
            request = urllib.request.Request(
                REMOTE_VERSION_URL,
                headers={"User-Agent": f"Anno-Island-Tool/{APP_VERSION}"},
            )
            with urllib.request.urlopen(request, timeout=4) as response:
                remote_version = response.read(256).decode("utf-8-sig", errors="replace").strip()
        except (OSError, urllib.error.URLError, ValueError):
            # Version checks are optional. Startup continues silently when offline.
            return
        current_key = version_key(APP_VERSION)
        remote_key = version_key(remote_version)
        if current_key and remote_key and remote_key > current_key:
            self.after(0, lambda: self._show_update_available(remote_version))





    def _save_gamedata_object_changes(self, window):
        original = Path(self.gamedata_file_var.get().strip())
        if not original.is_file():
            messagebox.showerror("Gamedata Objects", "gamedata_original.xml is not available.", parent=window)
            return

        guid_changes = {}
        for id_var, guid_var in window.object_edit_rows:
            object_id = id_var.get().strip()
            new_guid = guid_var.get().strip()
            if not object_id or not new_guid:
                messagebox.showerror("Gamedata Objects", "ID and GUID values must not be empty.", parent=window)
                return
            guid_changes[object_id] = new_guid

        try:
            # Always rebuild gamedata_patched.xml from the complete original.
            tree, _, _ = self._parse_xml_tolerant(original)
            root = tree.getroot()
            gamedata_changed = 0
            for parent in root.iter():
                children = list(parent)
                id_node = next((c for c in children if isinstance(c.tag, str) and c.tag.rsplit("}", 1)[-1].lower() == "id"), None)
                guid_node = next((c for c in children if isinstance(c.tag, str) and c.tag.rsplit("}", 1)[-1].lower() == "guid"), None)
                object_id = (id_node.text or "").strip() if id_node is not None else ""
                if object_id in guid_changes and guid_node is not None:
                    new_guid = guid_changes[object_id]
                    if (guid_node.text or "").strip() != new_guid:
                        guid_node.text = new_guid
                        gamedata_changed += 1

            gamedata_patched = original.with_name("gamedata_patched.xml")
            tree.write(gamedata_patched, encoding="utf-8", xml_declaration=False, short_empty_elements=True)

            mapname_original = Path(self.mapname_file_var.get().strip())
            mapname_patched = None
            mapname_changed = 0
            if mapname_original.is_file():
                map_tree, _, _ = self._parse_xml_tolerant(mapname_original)
                map_root = map_tree.getroot()
                for parent in map_root.iter():
                    children = list(parent)
                    id_node = next((c for c in children if isinstance(c.tag, str) and c.tag.rsplit("}", 1)[-1].lower() == "objectid"), None)
                    guid_node = next((c for c in children if isinstance(c.tag, str) and c.tag.rsplit("}", 1)[-1].lower() == "objectguid"), None)
                    object_id = (id_node.text or "").strip() if id_node is not None else ""
                    if object_id in guid_changes and guid_node is not None:
                        new_guid = guid_changes[object_id]
                        if (guid_node.text or "").strip() != new_guid:
                            guid_node.text = new_guid
                            mapname_changed += 1
                map_tmp = mapname_patched.with_suffix(mapname_patched.suffix + ".tmp")
                map_tree.write(map_tmp, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
                self._parse_xml_tolerant(map_tmp)
                map_tmp.replace(mapname_patched)

        except (OSError, ET.ParseError, UnicodeError) as exc:
            messagebox.showerror("Gamedata Objects", f"The changes could not be saved:\n{exc}", parent=window)
            return

        text = (
            "Object changes saved.\n\n"
            f"Gamedata: {gamedata_patched.name}\n"
            f"Changed GUID entries: {gamedata_changed}"
        )
        if mapname_patched is not None:
            text += f"\n\nMap file: {mapname_patched.name}\nChanged ObjectGuid entries: {mapname_changed}"
        else:
            text += "\n\nNo mapname_original.xml was selected, so no map file was written."
        self.status_var.set(f"Objects saved: {gamedata_changed} GUID change(s)")
        messagebox.showinfo("Gamedata Objects", text, parent=window)


    @staticmethod
    def _collect_gamedata_objects(root):
        """Return every sibling ID/GUID pair in source order."""
        rows = []
        for parent in root.iter():
            object_id = None
            guid = None
            for child in list(parent):
                if not isinstance(child.tag, str):
                    continue
                tag = child.tag.rsplit("}", 1)[-1].lower()
                if tag == "id":
                    object_id = (child.text or "").strip()
                elif tag == "guid":
                    guid = (child.text or "").strip()
            if object_id and guid:
                rows.append((object_id, guid))
        return rows


    @staticmethod
    @staticmethod
    def _sanitize_xml_text(text: str) -> tuple[str, int]:
        """Compatibility wrapper for the shared XML character sanitizer."""
        return sanitize_xml_text(text)

    @staticmethod
    def _parse_xml_tolerant(path: Path):
        """Compatibility wrapper for the shared tolerant XML parser."""
        return parse_xml_tolerant(path)

    def _select_gamedata_file(self):
        value = filedialog.askopenfilename(
            title="Select gamedata_original.xml",
            filetypes=[("gamedata_original.xml", "gamedata_original.xml"), ("XML", "*.xml")],
        )
        if value:
            self.gamedata_file_var.set(value)
            self._autodetect_mapname_original(Path(value))
            self._load_gamedata_xml()

    def _autodetect_mapname_original(self, gamedata_path: Path):
        """Find <mapname>_original.xml one folder above gamedata_original.xml."""
        gamedata_path = Path(gamedata_path)
        if not gamedata_path.is_file():
            return

        # Expected layout:
        # X:\mapname\mapname_original.xml
        # X:\mapname\mapname\gamedata_original.xml
        #
        # Therefore the map XML is in the parent of the folder containing
        # gamedata_original.xml.
        data_folder = gamedata_path.parent
        search_folder = data_folder.parent
        if not search_folder.is_dir():
            return

        # Usually the inner data folder has the map name.
        map_name = data_folder.name
        expected = search_folder / f"{map_name}_original.xml"
        if expected.is_file():
            self.mapname_file_var.set(str(expected))
            return

        # Also try the outer folder name for layouts where both names differ.
        outer_name = search_folder.name
        expected_outer = search_folder / f"{outer_name}_original.xml"
        if expected_outer.is_file():
            self.mapname_file_var.set(str(expected_outer))
            return

        # Fallback only when there is exactly one plausible *_original.xml.
        candidates = [
            candidate for candidate in search_folder.glob("*_original.xml")
            if candidate.name.lower() not in {
                "gamedata_original.xml",
                "rd3d_original.xml",
                "a7minfo_original.xml",
            }
        ]
        if len(candidates) == 1:
            self.mapname_file_var.set(str(candidates[0]))

    def _select_mapname_file(self):
        initial = Path(self.gamedata_file_var.get().strip()).parent.parent if self.gamedata_file_var.get().strip() else None
        value = filedialog.askopenfilename(
            title="Select mapname_original.xml",
            initialdir=str(initial) if initial and initial.is_dir() else None,
            filetypes=[("mapname_original.xml", "*_original.xml"), ("XML", "*.xml")],
        )
        if value:
            self.mapname_file_var.set(value)

    @staticmethod
    def _dropdown_display_for_value(options, xml_value, current_display):
        """Return the configured dropdown display label for an XML value."""
        xml_value = (xml_value or "").strip()
        if not xml_value:
            return current_display
        for display, value in options.items():
            if value == xml_value:
                return display
        # Keep dropdown configuration authoritative: if a patched XML contains
        # a value unknown to config_gamedata.py, retain the current valid item.
        return current_display

    def _update_gamedata_dropdowns_from_patched(self, original_path: Path):
        """Update New content dropdowns from gamedata_patched.xml when available."""
        patched_path = Path(original_path).with_name("gamedata_patched.xml")
        if not patched_path.is_file():
            return
        try:
            tree, _, _ = self._parse_xml_tolerant(patched_path)
        except (ET.ParseError, OSError, UnicodeError):
            return

        ambient = None
        vegetation = None
        for element in tree.getroot().iter():
            if not isinstance(element.tag, str):
                continue
            tag = element.tag.rsplit("}", 1)[-1]
            value = (element.text or "").strip()
            if tag == "GlobalAmbientName" and value and ambient is None:
                ambient = value
            elif tag == "VegetationPropSetName" and value and vegetation is None:
                vegetation = value
            if ambient is not None and vegetation is not None:
                break

        if ambient is not None:
            self.new_global_ambient_var.set(
                self._dropdown_display_for_value(
                    GLOBAL_AMBIENT_OPTIONS, ambient, self.new_global_ambient_var.get()
                )
            )
        if vegetation is not None:
            self.new_vegetation_var.set(
                self._dropdown_display_for_value(
                    VEGETATION_PROP_SET_OPTIONS, vegetation, self.new_vegetation_var.get()
                )
            )

    def _load_gamedata_xml(self, show_errors=True):
        self._xml_loading_depth += 1
        try:
            self._xml_loading_show('Reading gamedata XML...')
            return self._load_gamedata_xml_with_progress_body(show_errors=show_errors)
        except Exception as exc:
            self._xml_loading_finish(str(exc))
            raise
        finally:
            self._xml_loading_depth -= 1
            self._xml_loading_finish()

    def _load_gamedata_xml_with_progress_body(self, show_errors=True):
        path = Path(self.gamedata_file_var.get().strip())
        if path.is_file() and not self.mapname_file_var.get().strip():
            self._autodetect_mapname_original(path)
        if not path.is_file():
            self.global_ambient_var.set("-")
            self.vegetation_prop_set_var.set("-")
            if show_errors:
                messagebox.showerror("Gamedata", "Please select an existing gamedata_original.xml file.")
            return False
        try:
            tree, repaired, repairs = self._parse_xml_tolerant(path)
            root = tree.getroot()
            repair_note = ""
            if repaired:
                repair_note = f" | preserved unchanged: {repairs} unsupported XML item(s)"
            values = {"GlobalAmbientName": [], "VegetationPropSetName": []}
            for element in root.iter():
                tag = element.tag.rsplit("}", 1)[-1]
                if tag in values:
                    text = (element.text or "").strip()
                    if text and text not in values[tag]:
                        values[tag].append(text)
            self.global_ambient_var.set("\n".join(values["GlobalAmbientName"]) or "Not found")
            self.vegetation_prop_set_var.set("\n".join(values["VegetationPropSetName"]) or "Not found")
            self._update_gamedata_dropdowns_from_patched(path)
            self.status_var.set(f"Gamedata loaded: {path.name}{repair_note}")
            return True
        except (ET.ParseError, OSError) as exc:
            self.global_ambient_var.set("Error while reading")
            self.vegetation_prop_set_var.set("Error while reading")
            self.status_var.set(f"Gamedata blocked: {path.name} | {exc}")
            if show_errors:
                if isinstance(exc, ET.ParseError):
                    details = self._format_xml_parse_error(path, exc)
                else:
                    details = f"File: {path}\nRead error: {exc}"
                messagebox.showerror(
                    "Gamedata XML blocked",
                    "The Gamedata XML is structurally invalid and was not loaded.\n"
                    "No patched XML can be generated from this input.\n\n" + details,
                )
            return False

    @staticmethod
    def _insert_xml_child_preserve_layout(parent, element, after_tags=()):
        """Insert a child while preserving the surrounding FileDBReader XML whitespace."""
        children = list(parent)
        insert_at = None
        for preferred in after_tags:
            insert_at = next(
                (index + 1 for index, child in enumerate(children)
                 if isinstance(child.tag, str)
                 and child.tag.rsplit("}", 1)[-1] == preferred),
                None,
            )
            if insert_at is not None:
                break

        # ElementTree stores indentation in .text/.tail. Copy the indentation
        # pattern from neighboring children so the new element stays on its own line.
        child_indent = None
        if children:
            for child in children:
                if child.tail and "\n" in child.tail:
                    child_indent = child.tail
                    break
        if child_indent is None:
            child_indent = "\n      "

        if insert_at is None:
            insert_at = len(children)

        if insert_at < len(children):
            next_child = children[insert_at]
            element.tail = child_indent
            parent.insert(insert_at, element)
        else:
            # When appending, the old final child owns the parent's closing-tag
            # indentation. Transfer that tail to the new final child and give
            # the old final child normal sibling indentation.
            closing_indent = "\n    "
            if children and children[-1].tail:
                closing_indent = children[-1].tail
                children[-1].tail = child_indent
            element.tail = closing_indent
            parent.append(element)

    def _save_gamedata_patch(self):
        """Update the latest complete Gamedata state without losing slot edits."""
        original = Path(self.gamedata_file_var.get().strip())
        if not original.is_file():
            messagebox.showerror(
                "Gamedata",
                "Please load an existing gamedata_original.xml file first.",
            )
            return False

        ambient_display = self.new_global_ambient_var.get()
        vegetation_display = self.new_vegetation_var.get()
        ambient = GLOBAL_AMBIENT_OPTIONS.get(ambient_display)
        vegetation = VEGETATION_PROP_SET_OPTIONS.get(vegetation_display)

        if not ambient or not vegetation:
            messagebox.showerror("Gamedata", "The selected values are invalid.")
            return False

        patched_file = original.with_name("gamedata_patched.xml")
        # Regional Settings must extend the latest patched state. Falling back to
        # gamedata_original.xml is allowed only before the first patched save.
        source_file = patched_file if patched_file.is_file() else original

        try:
            # Load the complete latest XML. This preserves Slot Map objects and
            # every other edit already stored in gamedata_patched.xml.
            tree, repaired, repairs = self._parse_xml_tolerant(source_file)
            root = tree.getroot()

            ambient_count = 0
            vegetation_count = 0

            # Change only the requested elements. Everything else remains in
            # the loaded XML tree and is written to the patched output.
            for element in root.iter():
                tag = element.tag
                if isinstance(tag, str) and "}" in tag:
                    tag = tag.rsplit("}", 1)[-1]

                if tag == "GlobalAmbientName":
                    element.text = ambient
                    ambient_count += 1
                elif tag == "VegetationPropSetName":
                    element.text = vegetation
                    vegetation_count += 1

            vegetation_inserted = False
            if ambient_count == 0:
                messagebox.showerror(
                    "Gamedata",
                    "GlobalAmbientName was not found in the current Gamedata XML.",
                )
                return False

            if vegetation_count == 0:
                # VegetationPropSetName is optional. Insert it in the native
                # Content/GameSessionManager/SessionSettings location.
                session_settings = None
                for content in root.iter():
                    tag = content.tag.rsplit("}", 1)[-1] if isinstance(content.tag, str) else ""
                    if tag != "Content":
                        continue
                    session_settings = next(
                        (element for element in content.iter()
                         if isinstance(element.tag, str)
                         and element.tag.rsplit("}", 1)[-1] == "SessionSettings"),
                        None,
                    )
                    if session_settings is not None:
                        break
                if session_settings is None:
                    messagebox.showerror(
                        "Gamedata",
                        "VegetationPropSetName is missing and Content/GameSessionManager/SessionSettings "
                        "was not found, so it cannot be inserted safely.",
                    )
                    return False
                namespace = ""
                if isinstance(session_settings.tag, str) and session_settings.tag.startswith("{"):
                    namespace = session_settings.tag.split("}", 1)[0] + "}"
                element = ET.Element(f"{namespace}VegetationPropSetName")
                element.text = vegetation
                self._insert_xml_child_preserve_layout(
                    session_settings,
                    element,
                    after_tags=("HasAirGrid", "PlayableArea", "GlobalAmbientName"),
                )
                vegetation_count = 1
                vegetation_inserted = True

            # Apply GUID edits from the Objects popup by stable ID. ID itself is read-only.
            guid_changes = {}
            objects_window = getattr(self, "gamedata_objects_window", None)
            if objects_window is not None and objects_window.winfo_exists():
                for id_var, guid_var in objects_window.object_edit_rows:
                    object_id = id_var.get().strip()
                    new_guid = guid_var.get().strip()
                    if object_id and new_guid:
                        guid_changes[object_id] = new_guid

            for parent in root.iter():
                children = list(parent)
                id_node = next((c for c in children if isinstance(c.tag, str) and c.tag.rsplit("}", 1)[-1].lower() == "id"), None)
                guid_node = next((c for c in children if isinstance(c.tag, str) and c.tag.rsplit("}", 1)[-1].lower() == "guid"), None)
                object_id = (id_node.text or "").strip() if id_node is not None else ""
                if object_id in guid_changes and guid_node is not None:
                    guid_node.text = guid_changes[object_id]

            # Mirror the same ID->GUID changes into mapname_original.xml where
            # the equivalent fields are ObjectId and ObjectGuid.
            mapname_original = Path(self.mapname_file_var.get().strip())
            mapname_patched = None
            mapname_changed = 0
            if guid_changes and mapname_original.is_file():
                mapname_patched = mapname_original.with_name(
                    mapname_original.name.replace("_original.xml", "_patched.xml")
                    if mapname_original.name.endswith("_original.xml")
                    else f"{mapname_original.stem}_patched.xml"
                )
                mapname_source = (
                    mapname_patched if mapname_patched.is_file() else mapname_original
                )
                map_tree, _, _ = self._parse_xml_tolerant(mapname_source)
                map_root = map_tree.getroot()
                for parent in map_root.iter():
                    children = list(parent)
                    id_node = next((c for c in children if isinstance(c.tag, str) and c.tag.rsplit("}", 1)[-1].lower() == "objectid"), None)
                    guid_node = next((c for c in children if isinstance(c.tag, str) and c.tag.rsplit("}", 1)[-1].lower() == "objectguid"), None)
                    object_id = (id_node.text or "").strip() if id_node is not None else ""
                    if object_id in guid_changes and guid_node is not None:
                        new_guid = guid_changes[object_id]
                        if (guid_node.text or "").strip() != new_guid:
                            guid_node.text = new_guid
                            mapname_changed += 1
                mapname_patched = mapname_original.with_name(
                    mapname_original.name.replace("_original.xml", "_patched.xml")
                    if mapname_original.name.endswith("_original.xml")
                    else f"{mapname_original.stem}_patched.xml"
                )
                map_tree.write(mapname_patched, encoding="utf-8", xml_declaration=False, short_empty_elements=True)

            # Write and parse a temporary complete XML before replacing the latest
            # patched state. This prevents a partial Regional Save from damaging it.
            patched_tmp = patched_file.with_suffix(patched_file.suffix + ".tmp")
            tree.write(
                patched_tmp,
                encoding="utf-8",
                xml_declaration=False,
                short_empty_elements=True,
            )
            self._parse_xml_tolerant(patched_tmp)
            patched_tmp.replace(patched_file)

        except (OSError, ET.ParseError, UnicodeError) as exc:
            messagebox.showerror(
                "Gamedata",
                f"gamedata_patched.xml could not be saved:\n{exc}",
            )
            return False

        repair_note = ""
        if repaired:
            repair_note = (
                f"\n\nWhile reading the current XML, {repairs} invalid "
                "unsupported XML item(s) were preserved unchanged."
            )

        self.status_var.set(f"Saved: {patched_file}")
        messagebox.showinfo(
            "Gamedata",
            "Patched gamedata saved successfully.\n\n"
            f"File: {patched_file}\n"
            f"GlobalAmbientName updated: {ambient_count}\n"
            f"VegetationPropSetName {'inserted' if vegetation_inserted else 'updated'}: {vegetation_count}"
            + (f"\nGUID mappings changed in map file: {mapname_changed}" if mapname_patched else "")
            + (f"\nMap file: {mapname_patched}" if mapname_patched else "")
            + f"{repair_note}",
        )
        return True


    def _custom_material_sets_dir(self):
        value = self.custom_material_sets_folder_var.get().strip()
        return Path(value).expanduser() if value else None

    def _material_set_search_dirs(self):
        """Bundled material sets plus the user-configured custom folder."""
        folders = [BUNDLE_DIR / "data" / "material_sets"]
        custom_folder = self._custom_material_sets_dir()
        if custom_folder is not None:
            folders.append(custom_folder)
        return tuple(folders)

    def _material_set_dropdown_files(self):
        """Return unique stems from bundled and configured custom material sets."""
        names = set()
        for folder in self._material_set_search_dirs():
            if not folder.is_dir():
                continue
            for pattern in ("*.materialset", "*.xml"):
                names.update(path.stem for path in folder.glob(pattern) if path.is_file())
        return sorted(names, key=str.lower)

    def _find_material_set_dropdown_file(self, filename):
        """Resolve a dropdown item; configured custom files override bundled data."""
        filename = (filename or "").strip()
        if not filename:
            return None
        folders = []
        custom_folder = self._custom_material_sets_dir()
        if custom_folder is not None:
            folders.append(custom_folder)
        folders.append(BUNDLE_DIR / "data" / "material_sets")
        for folder in folders:
            for suffix in (".materialset", ".xml"):
                candidate = folder / f"{filename}{suffix}"
                if candidate.is_file():
                    return candidate
        return None

    def _is_custom_material_set_name(self, filename):
        filename = str(filename or "").strip()
        folder = self._custom_material_sets_dir()
        if not filename or folder is None:
            return False
        return any((folder / f"{filename}{suffix}").is_file() for suffix in (".materialset", ".xml"))

    def _on_material_set_dropdown_selected(self, filename):
        """Write the selected material-set path into the editable New value."""
        filename = (filename or "").strip()
        if not filename or filename == "No material set files found":
            return
        
        self.new_material_set_var.set(
            f"data/config/engine/material_sets/{filename}.xml"
        )
        label = getattr(self, "regional_material_set_custom_label", None)
        if label is not None:
            label.configure(text="Custom" if self._is_custom_material_set_name(filename) else "")







    def _select_rd3d_file(self):
        value = filedialog.askopenfilename(
            title="Select rd3d_original.xml",
            filetypes=[("rd3d_original.xml", "rd3d_original.xml"), ("XML", "*.xml")],
        )
        if value:
            self.rd3d_file_var.set(value)
            self._load_rd3d_xml()

    def _load_rd3d_patch_values(self, original_path, expected_count):
        """Load right-side New values exclusively from rd3d_patched.xml."""
        patched_path = original_path.with_name("rd3d_patched.xml")

        if not patched_path.is_file():
            return None, None, "No rd3d_patched.xml found; New values use the original data"

        try:
            patched_root = self._parse_xml_tolerant(patched_path)[0].getroot()
        except (ET.ParseError, OSError) as exc:
            return None, None, f"rd3d_patched.xml could not be read: {exc}"

        material_value = None
        file_values = None

        # MaterialSetFileName from the complete patched RD3D XML.
        material_node = next(
            (
                element
                for element in patched_root.iter()
                if isinstance(element.tag, str)
                and element.tag.rsplit("}", 1)[-1].lower() == "materialsetfilename"
                and (element.text or "").strip()
            ),
            None,
        )
        if material_node is not None:
            material_value = (material_node.text or "").strip()

        # FileNames must specifically come from PropGrid/FileNames, not from an
        # unrelated FileNames element elsewhere in rd3d_patched.xml.
        for propgrid in patched_root.iter():
            if not isinstance(propgrid.tag, str):
                continue
            if propgrid.tag.rsplit("}", 1)[-1].lower() != "propgrid":
                continue

            container = next(
                (
                    child
                    for child in list(propgrid)
                    if isinstance(child.tag, str)
                    and child.tag.rsplit("}", 1)[-1].lower() == "filenames"
                ),
                None,
            )
            if container is None:
                continue

            candidate_values = [
                (child.text or "").strip()
                for child in list(container)
                if isinstance(child.tag, str)
                and child.tag.rsplit("}", 1)[-1].lower() == "none"
            ]
            if len(candidate_values) == expected_count and all(candidate_values):
                file_values = candidate_values
                break

        if material_value is not None and file_values is not None:
            status = "Loaded MaterialSetFileName and New values from rd3d_patched.xml"
        elif material_value is not None:
            status = "Loaded MaterialSetFileName from rd3d_patched.xml; FileNames list ignored"
        elif file_values is not None:
            status = "Loaded New values from rd3d_patched.xml; MaterialSetFileName not found"
        else:
            status = "No valid MaterialSetFileName/FileNames values found in rd3d_patched.xml"

        return material_value, file_values, status

    def _load_rd3d_xml(self, show_errors=True):
        self._xml_loading_depth += 1
        try:
            self._xml_loading_show('Reading RD3D XML...')
            return self._load_rd3d_xml_with_progress_body(show_errors=show_errors)
        except Exception as exc:
            self._xml_loading_finish(str(exc))
            raise
        finally:
            self._xml_loading_depth -= 1
            self._xml_loading_finish()

    def _load_rd3d_xml_with_progress_body(self, show_errors=True):
        path = Path(self.rd3d_file_var.get().strip())
        if not path.is_file():
            self.material_set_var.set("-")
            self._set_rd3d_file_names([])
            if show_errors:
                messagebox.showerror("rd3d.data", "Please select an existing rd3d_original.xml file.")
            return False
        try:
            tree, repaired, repairs = self._parse_xml_tolerant(path)
            root = tree.getroot()
            if repaired:
                self.status_var.set(f"XML loaded with preserved original content: {path.name} ({repairs} unsupported item(s))")
            found = []
            prop_grid = next((e for e in root.iter() if e.tag.rsplit("}", 1)[-1] == "PropGrid"), None)
            file_node = next((e for e in list(prop_grid) if e.tag.rsplit("}", 1)[-1] == "FileNames"), None) if prop_grid is not None else None
            instance_node = next((e for e in list(prop_grid) if e.tag.rsplit("}", 1)[-1] == "Instances"), None) if prop_grid is not None else None
            file_names = [(e.text or "").strip() for e in list(file_node)] if file_node is not None else []
            usage = [0] * len(file_names)
            if instance_node is not None:
                for instance in list(instance_node):
                    idx_node = next((e for e in list(instance) if e.tag.rsplit("}", 1)[-1] == "Index"), None)
                    try:
                        idx = int((idx_node.text or "").strip()) if idx_node is not None else -1
                        if 0 <= idx < len(usage): usage[idx] += 1
                    except ValueError:
                        pass
            for element in root.iter():
                if element.tag.rsplit("}", 1)[-1] == "MaterialSetFileName":
                    text = (element.text or "").strip()
                    if text and text not in found: found.append(text)
            display = "\n".join(found) or "Not found"
            self.material_set_var.set(display)

            patch_material, patch_file_names, patch_status = self._load_rd3d_patch_values(
                path,
                len(file_names),
            )
            new_file_names = patch_file_names if patch_file_names is not None else file_names
            self._set_rd3d_file_names(file_names, usage, new_file_names)
            if patch_material:
                self.new_material_set_var.set(patch_material)
            elif len(found) == 1:
                self.new_material_set_var.set(found[0])

            map_points = []
            if instance_node is not None:
                for instance in list(instance_node):
                    index_node = next(
                        (child for child in list(instance)
                         if child.tag.rsplit("}", 1)[-1] == "Index"),
                        None,
                    )
                    position_node = next(
                        (child for child in list(instance)
                         if child.tag.rsplit("}", 1)[-1] == "Position"),
                        None,
                    )
                    if index_node is None or position_node is None:
                        continue
                    try:
                        prop_index = int((index_node.text or "").strip())
                    except ValueError:
                        continue
                    position = self._parse_rd3d_position(position_node.text)
                    if position is None:
                        continue
                    x, y, z = position
                    map_points.append(
                        (prop_index, x, z, y, (position_node.text or "").strip())
                    )

            self.rd3d_map_points = map_points
            self.rd3d_map_zoom = 0.8
            self.rd3d_map_pan_x = 0.0
            self.rd3d_map_pan_y = 0.0
            self.rd3d_map_shared_zoom = 1.0
            self.rd3d_map_shared_pan_x = 0.0
            self.rd3d_map_shared_pan_y = 0.0
            self.rd3d_map_info_var.set(
                f"{len(map_points)} Instances | displayed using X and Z | "
                f"Categories: {', '.join(self.rd3d_found_categories) or 'none'}"
            )
            self.rd3d_map_selection_var.set(
                "Click a point to display its index, prop, and position."
            )
            self._load_rd3d_map_background(path)
            self._schedule_rd3d_map_redraw()

            self.status_var.set(
                f"RD3D loaded: {path.name} | {len(file_names)} Props | "
                f"{len(map_points)} map points | {patch_status}"
            )
            return True
        except (ET.ParseError, OSError) as exc:
            self.material_set_var.set("Error while reading")
            self._set_rd3d_file_names([])
            if show_errors:
                messagebox.showerror("rd3d.data", f"The XML file could not be read:\n{exc}")
            return False

    def _classify_prop(self, path):
        return get_category_for_object(path, self.CONFIG_FILE)

    def _rd3d_refresh_found_categories(self):
        found = []
        seen = set()
        for _index, _original, variable, _count in self.rd3d_file_names:
            category = self._classify_prop(variable.get().strip())
            if category not in seen:
                seen.add(category)
                found.append(category)
        self.rd3d_found_categories = found
        self.rd3d_map_category_visible = {
            category: self.rd3d_map_category_visible.get(category, True)
            for category in found
        }
        for category in found:
            if category not in self.rd3d_category_colors:
                self.rd3d_category_colors[category] = self._random_rd3d_category_color()

    @staticmethod
    def _random_color_from_families(used_colors):
        """Choose an unused color, using each hue family before another shade."""
        used = {str(color).casefold() for color in used_colors if color}
        families = {
            name: [color for color in colors if color]
            for name, colors in TYPE_CATEGORY_COLOR_FAMILIES.items()
        }
        max_shades = max((len(colors) for colors in families.values()), default=0)
        for shade_index in range(max_shades):
            available = [
                colors[shade_index]
                for colors in families.values()
                if shade_index < len(colors)
                and colors[shade_index].casefold() not in used
            ]
            if available:
                return random.choice(available)
        palette = [color for color in TYPE_CATEGORY_COLORS if color]
        available = [color for color in palette if color.casefold() not in used]
        return random.choice(available or palette) if palette else DEFAULT_TYPE_COLOR

    def _random_rd3d_category_color(self):
        """Use every hue family once before assigning another shade of a used hue."""
        return self._random_color_from_families(self.rd3d_category_colors.values())
    def _rd3d_replace_from_values(self):
        """Return labels as 'Type, Variations: xx, Placed: yy'.

        Variations is the number of FileNames rows currently classified as the Type.
        Placed is the sum of their instance/usage Count values.
        """
        stats = {}
        for _index, _original, path_var, count in self.rd3d_file_names:
            object_type = self._classify_prop(path_var.get().strip())
            values = stats.setdefault(object_type, {"variations": 0, "placed": 0})
            values["variations"] += 1
            values["placed"] += count
        return [
            f"{object_type}, Variations: {stats[object_type]['variations']}, "
            f"Placed: {stats[object_type]['placed']}"
            for object_type in sorted(stats, key=str.casefold)
        ]

    @staticmethod
    def _rd3d_replace_from_type(display_value):
        """Extract Type from 'Type, Variations: xx, Placed: yy'."""
        return (display_value or "").split(", Variations:", 1)[0].strip()

    def _rd3d_replace_to_values(self):
        """Return 'Type, Count' labels using the number of unique database paths per Type."""
        paths_by_type = {}
        for _source_category, path, _count in get_combined_object_database(self.CONFIG_FILE):
            path = (path or "").strip()
            if not path:
                continue
            object_type = self._classify_prop(path)
            paths_by_type.setdefault(object_type, set()).add(path.casefold())
        return [
            f"{object_type}, Variations: {len(paths_by_type[object_type])}"
            for object_type in sorted(paths_by_type, key=str.casefold)
        ]

    @staticmethod
    def _rd3d_replace_to_type(display_value):
        """Extract Type from 'Type, Variations: xx'."""
        return (display_value or "").split(", Variations:", 1)[0].strip()



    def _replace_rd3d_object_type_paths(self, window):
        from_display = window.rd3d_replace_from_var.get().strip()
        from_type = self._rd3d_replace_from_type(from_display)
        to_display = window.rd3d_replace_to_var.get().strip()
        to_type = self._rd3d_replace_to_type(to_display)
        if not from_type or from_type == "No types found" or not to_type or to_type == "No types found":
            messagebox.showerror("Replace RD3D Type", "Please select valid From and To types.", parent=window)
            return
        source_rows = [row for row in self.rd3d_file_names if self._classify_prop(row[2].get().strip()) == from_type]
        if not source_rows:
            messagebox.showinfo("Replace RD3D Type", f"No editable entries of Type '{from_type}' were found.", parent=window)
            return
        target_paths, seen = [], set()
        for _source_category, path, _count in get_combined_object_database(self.CONFIG_FILE):
            path = (path or "").strip()
            key = path.casefold()
            if path and self._classify_prop(path) == to_type and key not in seen:
                seen.add(key)
                target_paths.append(path)
        if not target_paths:
            messagebox.showerror("Replace RD3D Type", f"The database contains no paths of Type '{to_type}'.", parent=window)
            return
        # Randomize the database variations before assigning them. Every unique
        # target path is still used at most once before duplicates are allowed.
        # If more source rows exist than unique target variations, start another
        # independently shuffled cycle instead of repeating a fixed sequence.
        assignments = []
        while len(assignments) < len(source_rows):
            cycle = target_paths.copy()
            random.shuffle(cycle)
            assignments.extend(cycle)
        assignments = assignments[:len(source_rows)]

        # Also randomize which matching source row receives which variation, so
        # replacement is not tied to FileNames/table order.
        randomized_source_rows = source_rows.copy()
        random.shuffle(randomized_source_rows)
        for (_index, _original, variable, _count), target_path in zip(
            randomized_source_rows, assignments
        ):
            variable.set(target_path)
        duplicate_count = max(0, len(source_rows) - len(target_paths))
        self._rd3d_refresh_found_categories()
        self._render_rd3d_file_names()
        self._refresh_rd3d_replace_from_menu(window)
        self._rebuild_rd3d_map_category_buttons()
        self._schedule_rd3d_map_redraw()
        self.status_var.set(f"RD3D Type replaced: {from_type} -> {to_type} | {len(source_rows)} entries | {duplicate_count} duplicates")
        messagebox.showinfo("Replace RD3D Type", f"Replaced entries: {len(source_rows)}\nFrom: {from_type}\nTo: {to_type}\nUnique target paths: {len(target_paths)}\nDuplicate assignments required: {duplicate_count}\n\nClick Save to write the changes.", parent=window)






    def _set_rd3d_file_names(self, values, usage=None, new_values=None):
        usage = usage or [0] * len(values)
        if new_values is None or len(new_values) != len(values):
            new_values = values
        self.rd3d_file_names = []
        for index, value in enumerate(values):
            variable = tk.StringVar(value=new_values[index])
            count = usage[index] if index < len(usage) else 0
            self.rd3d_file_names.append((index, value, variable, count))
        self._rd3d_refresh_found_categories()
        if self.rd3d_objects_window is not None and self.rd3d_objects_window.winfo_exists():
            self._render_rd3d_file_names()
        self._rebuild_rd3d_map_category_buttons()










    def _reset_rd3d_object_paths(self):
        """Reset only the editable second Path lines to rd3d_original.xml values."""
        changed = 0
        for _index, original, variable, _count in self.rd3d_file_names:
            if variable.get().strip() != original:
                variable.set(original)
                changed += 1
        self._rd3d_refresh_found_categories()
        self._render_rd3d_file_names()
        if self.rd3d_objects_window is not None and self.rd3d_objects_window.winfo_exists():
            self._refresh_rd3d_replace_from_menu(self.rd3d_objects_window)
        self._rebuild_rd3d_map_category_buttons()
        self._schedule_rd3d_map_redraw()
        self.status_var.set(f"RD3D object paths reset: {changed} change(s) reverted")

    def _save_rd3d_object_paths(self):
        """Save the editable second Path lines to the complete rd3d_patched.xml."""
        original = Path(self.rd3d_file_var.get().strip())
        if not original.is_file():
            messagebox.showerror(
                "RD3D Objects", "Please load an existing rd3d_original.xml file first.",
                parent=self.rd3d_objects_window,
            )
            return
        if not self.rd3d_file_names:
            messagebox.showerror(
                "RD3D Objects", "No FileNames list has been loaded.",
                parent=self.rd3d_objects_window,
            )
            return

        values = []
        changed = 0
        for index, original_value, variable, _count in self.rd3d_file_names:
            value = variable.get().strip()
            if not value:
                messagebox.showerror(
                    "RD3D Objects", f"The editable Path at index {index} must not be empty.",
                    parent=self.rd3d_objects_window,
                )
                return
            values.append(value)
            if value != original_value:
                changed += 1

        patched = original.with_name("rd3d_patched.xml")
        # Preserve other changes already present in the patched file, especially
        # MaterialSetFileName. If no patched file exists, start from the original.
        source = patched if patched.is_file() else original
        try:
            tree, _repaired, _repairs = self._parse_xml_tolerant(source)
            root = tree.getroot()
            file_names = None
            for propgrid in root.iter():
                if not isinstance(propgrid.tag, str) or propgrid.tag.rsplit("}", 1)[-1].lower() != "propgrid":
                    continue
                file_names = next(
                    (child for child in list(propgrid)
                     if isinstance(child.tag, str)
                     and child.tag.rsplit("}", 1)[-1].lower() == "filenames"),
                    None,
                )
                if file_names is not None:
                    break
            if file_names is None:
                raise RuntimeError("PropGrid/FileNames was not found.")
            children = list(file_names)
            if len(children) != len(values):
                raise RuntimeError(
                    f"FileNames count mismatch: GUI {len(values)}, XML {len(children)}."
                )
            for child, value in zip(children, values):
                child.text = value
            tree.write(
                patched, encoding="utf-8", xml_declaration=False,
                short_empty_elements=True,
            )
        except (OSError, ET.ParseError, UnicodeError, RuntimeError) as exc:
            messagebox.showerror(
                "RD3D Objects", f"rd3d_patched.xml could not be saved:\n{exc}",
                parent=self.rd3d_objects_window,
            )
            return

        self._rd3d_refresh_found_categories()
        self._rebuild_rd3d_map_category_buttons()
        self._schedule_rd3d_map_redraw()
        self.status_var.set(
            f"RD3D object paths saved: {changed} changed path(s) | {patched.name}"
        )
        self.rd3d_save_info_var.set(
            f"Saved: {patched.name} | {len(values)} paths | {changed} changed"
        )
        messagebox.showinfo(
            "RD3D Objects",
            f"Paths saved to:\n{patched}\n\nChanged paths: {changed}",
            parent=self.rd3d_objects_window,
        )

    @staticmethod
    def _parse_rd3d_position(text):
        parts = (text or "").strip().split()
        if len(parts) < 3:
            return None
        try:
            x = float(parts[0].replace(",", "."))
            y = float(parts[1].replace(",", "."))
            z = float(parts[2].replace(",", "."))
            return x, y, z
        except ValueError:
            return None

    def _rd3d_map_color(self, index):
        prop_path = ""
        if 0 <= index < len(self.rd3d_file_names):
            prop_path = self.rd3d_file_names[index][2].get().strip()
        return self._rd3d_category_color(self._classify_prop(prop_path))

    def _toggle_rd3d_map_category(self, category):
        current = self.rd3d_map_category_visible.get(category, True)
        self.rd3d_map_category_visible[category] = not current
        self._rebuild_rd3d_map_category_buttons()
        self._schedule_rd3d_map_redraw()

    def _rd3d_category_color(self, category):
        if category not in self.rd3d_category_colors:
            self.rd3d_category_colors[category] = self._random_rd3d_category_color()
        return self.rd3d_category_colors[category]

    @staticmethod
    def _rd3d_ctrl_pressed(event):
        # Tk uses the ControlMask bit (0x0004) on Windows and Linux.
        return bool(getattr(event, "state", 0) & 0x0004)






    def _load_rd3d_map_background(self, rd3d_path):
        self.rd3d_map_image_path = None
        self.rd3d_map_image_source = None
        self.rd3d_map_image_tk = None

        candidates = [
            rd3d_path.parent / "activemapimage.png",
            rd3d_path.parent.parent / "activemapimage.png",
        ]
        for parent in (rd3d_path.parent, rd3d_path.parent.parent):
            if parent.is_dir():
                candidates.extend(parent.rglob("activemapimage.png"))

        seen = set()
        image_path = None
        for candidate in candidates:
            key = str(candidate).lower()
            if key in seen:
                continue
            seen.add(key)
            if candidate.is_file():
                image_path = candidate
                break

        if image_path is None:
            self.rd3d_map_info_var.set(
                f"{len(self.rd3d_map_points)} Instances | No activemapimage.png found"
            )
            return

        try:
            with Image.open(image_path) as image:
                self.rd3d_map_image_source = image.convert("RGBA").copy()
            self.rd3d_map_image_path = image_path
            self.rd3d_map_info_var.set(
                f"{len(self.rd3d_map_points)} Instances | Background: {image_path.name} | X/Z display"
            )
        except (OSError, ValueError) as exc:
            self.rd3d_map_info_var.set(
                f"activemapimage.png could not be loaded: {exc}"
            )






    def _save_rd3d_patch(self):
        """Create a complete rd3d_patched.xml from rd3d_original.xml."""
        original = Path(self.rd3d_file_var.get().strip())
        if not original.is_file():
            messagebox.showerror(
                "rd3d.data",
                "Please load an existing rd3d_original.xml file first.",
            )
            return

        material_value = self.new_material_set_var.get().strip()
        if not material_value:
            messagebox.showerror(
                "rd3d.data",
                "Please enter a MaterialSetFileName value.",
            )
            return

        if not self.rd3d_file_names:
            messagebox.showerror(
                "rd3d.data",
                "No FileNames list has been loaded.",
            )
            return

        file_name_values = []
        changed_paths = 0
        for index, original_value, variable, _count in self.rd3d_file_names:
            new_value = variable.get().strip()
            if not new_value:
                messagebox.showerror(
                    "rd3d.data",
                    f"The path at index {index} must not be empty.",
                )
                return
            file_name_values.append(new_value)
            if new_value != original_value:
                changed_paths += 1

        patched_file = original.with_name("rd3d_patched.xml")

        try:
            tree, repaired, repairs = self._parse_xml_tolerant(original)
            root = tree.getroot()

            material_elements = []
            file_names_elements = []

            for element in root.iter():
                tag = element.tag
                if isinstance(tag, str) and "}" in tag:
                    tag = tag.rsplit("}", 1)[-1]

                if tag == "MaterialSetFileName":
                    material_elements.append(element)
                elif tag == "FileNames":
                    # Only use FileNames below PropGrid. This prevents unrelated
                    # lists with the same tag name from being overwritten.
                    file_names_elements.append(element)

            material_inserted = False
            if not material_elements:
                # Some RD3D XML files do not contain MaterialSetFileName yet.
                # In that case insert it into <Content>/<Terrain>, directly after
                # <Levels> when possible (matching the native RD3D layout).
                terrain = None
                for content in root.iter():
                    content_tag = content.tag.rsplit("}", 1)[-1] if isinstance(content.tag, str) else ""
                    if content_tag != "Content":
                        continue
                    terrain = next(
                        (child for child in list(content)
                         if isinstance(child.tag, str)
                         and child.tag.rsplit("}", 1)[-1] == "Terrain"),
                        None,
                    )
                    if terrain is not None:
                        break

                if terrain is None:
                    messagebox.showerror(
                        "rd3d.data",
                        "MaterialSetFileName is missing and <Content>/<Terrain> "
                        "was not found, so the element cannot be inserted safely.",
                    )
                    return

                # Preserve an XML namespace if Terrain uses one.
                namespace = ""
                if isinstance(terrain.tag, str) and terrain.tag.startswith("{"):
                    namespace = terrain.tag.split("}", 1)[0] + "}"
                material_element = ET.Element(f"{namespace}MaterialSetFileName")
                material_element.text = material_value

                # Use the shared whitespace-aware insertion helper. ElementTree
                # stores indentation in element.text/element.tail; plain insert()
                # would concatenate MaterialSetFileName and MaterialIDs2.
                self._insert_xml_child_preserve_layout(
                    terrain,
                    material_element,
                    after_tags=("Levels",),
                )

                material_elements = [material_element]
                material_inserted = True

            # Find the FileNames list belonging to PropGrid explicitly.
            propgrid_file_names = []
            for propgrid in root.iter():
                tag = propgrid.tag
                if isinstance(tag, str) and "}" in tag:
                    tag = tag.rsplit("}", 1)[-1]
                if tag != "PropGrid":
                    continue
                for child in list(propgrid):
                    child_tag = child.tag
                    if isinstance(child_tag, str) and "}" in child_tag:
                        child_tag = child_tag.rsplit("}", 1)[-1]
                    if child_tag == "FileNames":
                        propgrid_file_names.append(child)

            if not propgrid_file_names:
                messagebox.showerror(
                    "rd3d.data",
                    "PropGrid/FileNames was not found in rd3d_original.xml.",
                )
                return

            # Apply MaterialSetFileName to the complete original XML tree.
            for element in material_elements:
                element.text = material_value

            # Replace the complete PropGrid/FileNames list while preserving the
            # rest of rd3d_original.xml unchanged in the parsed XML tree.
            for file_names_element in propgrid_file_names:
                children = list(file_names_element)
                if len(children) != len(file_name_values):
                    messagebox.showerror(
                        "rd3d.data",
                        "The number of editable FileNames does not match the FileNames "
                        "list in rd3d_original.xml.\n\n"
                        f"GUI: {len(file_name_values)}\n"
                        f"XML: {len(children)}",
                    )
                    return

                for child, value in zip(children, file_name_values):
                    child.text = value

            tree.write(
                patched_file,
                encoding="utf-8",
                xml_declaration=False,
                short_empty_elements=True,
            )

        except (OSError, ET.ParseError, UnicodeError) as exc:
            messagebox.showerror(
                "rd3d.data",
                f"rd3d_patched.xml could not be saved:\n{exc}",
            )
            return

        repair_text = ""
        if repaired:
            repair_text = f" | preserved XML items: {repairs}"

        material_action = "inserted" if material_inserted else "updated"
        self.status_var.set(
            f"RD3D patched XML saved: {len(file_name_values)} paths, "
            f"{changed_paths} changed | MaterialSetFileName {material_action}{repair_text}"
        )
        self.rd3d_save_info_var.set(
            f"Saved: {patched_file.name} | "
            f"{len(file_name_values)} paths | {changed_paths} changed"
        )
        messagebox.showinfo(
            "rd3d.data",
            f"Patched RD3D saved:\n{patched_file}\n\n"
            f"FileNames entries: {len(file_name_values)}\n"
            f"Changed paths: {changed_paths}\n"
            f"MaterialSetFileName: {material_value} ({material_action})"
            + (f"\nPreserved unsupported XML items: {repairs}" if repaired else ""),
        )
















    def _select_tmc_data_meshes(self):
        value = filedialog.askdirectory(title="Select TMC data folder")
        if not value:
            return
        folder = Path(value)
        self.tmc_data_meshes_var.set(str(folder))
        self._load_tmc_data()

    @staticmethod
    def _tmc_ground_object_elements(root):
        out = []
        for ground_objects in root.iter():
            if (not isinstance(ground_objects.tag, str)
                    or ground_objects.tag.rsplit("}", 1)[-1].lower() != "groundobjects"):
                continue
            for entry in list(ground_objects):
                id_node = filename_node = None
                for child in list(entry):
                    if not isinstance(child.tag, str):
                        continue
                    tag = child.tag.rsplit("}", 1)[-1].lower()
                    if tag == "id":
                        id_node = child
                    elif tag == "filename":
                        filename_node = child
                if id_node is not None and filename_node is not None:
                    object_id = (id_node.text or "").strip()
                    filename = (filename_node.text or "").strip()
                    if object_id and filename:
                        out.append((object_id, filename, filename_node))
        return out

    def _load_tmc_data(self, show_errors=True):
        folder = Path(self.tmc_data_meshes_var.get().strip())
        if not folder.is_dir():
            if show_errors:
                messagebox.showerror("tmc-data", "Please select an existing TMC data folder.")
            return False

        files = sorted(folder.rglob("*_original.xml"), key=lambda path: str(path).lower())
        counts = {}
        order = []
        file_rows = {}
        errors = 0
        for path in files:
            try:
                entries = self._tmc_ground_object_elements(
                    self._parse_xml_tolerant(path)[0].getroot()
                )
            except (ET.ParseError, OSError, UnicodeError):
                errors += 1
                continue
            if entries:
                file_rows[path] = [(object_id, filename) for object_id, filename, _node in entries]
            for object_id, filename, _node in entries:
                key = (object_id, filename)
                if key not in counts:
                    counts[key] = 0
                    order.append(key)
                counts[key] += 1

        patched = {}
        for path, originals in file_rows.items():
            patched_path = path.with_name(path.name.replace("_original.xml", "_patched.xml"))
            if not patched_path.is_file():
                continue
            try:
                entries = self._tmc_ground_object_elements(
                    self._parse_xml_tolerant(patched_path)[0].getroot()
                )
            except (ET.ParseError, OSError, UnicodeError):
                continue
            for index, (_object_id, filename, _node) in enumerate(entries):
                if index < len(originals):
                    patched.setdefault(originals[index], filename)

        self.tmc_data_rows = [
            (object_id, filename, counts[(object_id, filename)],
             tk.StringVar(value=patched.get((object_id, filename), filename)))
            for object_id, filename in order
        ]
        self.tmc_data_file_rows = file_rows
        self._render_tmc_data_rows()
        self._refresh_tmc_replace_menus()
        self.tmc_data_status_var.set(
            f"{len(files)} original XML files scanned | {len(order)} unique entries | "
            f"{sum(counts.values())} occurrences" + (f" | {errors} read errors" if errors else "")
        )
        return True


    def _tmc_replace_from_values(self):
        stats = {}
        for _object_id, _original, count, variable in self.tmc_data_rows:
            object_type = self._classify_prop(variable.get().strip())
            values = stats.setdefault(object_type, {"variations": 0, "placed": 0})
            values["variations"] += 1
            values["placed"] += count
        return [
            f"{object_type}, Variations: {stats[object_type]['variations']}, "
            f"Placed: {stats[object_type]['placed']}"
            for object_type in sorted(stats, key=str.casefold)
        ]

    def _tmc_replace_to_values(self):
        paths_by_type = {}
        for _source_category, path, _count in get_combined_object_database(self.CONFIG_FILE):
            path = (path or "").strip()
            if not path:
                continue
            object_type = self._classify_prop(path)
            paths_by_type.setdefault(object_type, set()).add(path.casefold())
        return [
            f"{object_type}, Variations: {len(paths_by_type[object_type])}"
            for object_type in sorted(paths_by_type, key=str.casefold)
        ]

    @staticmethod
    def _tmc_replace_type(display_value):
        return (display_value or "").split(", Variations:", 1)[0].strip()

    def _refresh_tmc_replace_menus(self):
        if not hasattr(self, "tmc_replace_from_menu"):
            return
        from_values = self._tmc_replace_from_values() or ["No types found"]
        to_values = self._tmc_replace_to_values() or ["No types found"]
        previous_from = self._tmc_replace_type(self.tmc_replace_from_var.get())
        previous_to = self._tmc_replace_type(self.tmc_replace_to_var.get())
        self.tmc_replace_from_menu.configure(values=from_values)
        self.tmc_replace_to_menu.configure(values=to_values)
        from_match = next((v for v in from_values if self._tmc_replace_type(v) == previous_from), None)
        to_match = next((v for v in to_values if self._tmc_replace_type(v) == previous_to), None)
        self.tmc_replace_from_var.set(from_match or from_values[0])
        self.tmc_replace_to_var.set(to_match or to_values[0])

    def _replace_tmc_object_type_paths(self):
        from_type = self._tmc_replace_type(self.tmc_replace_from_var.get())
        to_type = self._tmc_replace_type(self.tmc_replace_to_var.get())
        if not from_type or from_type == "No types found" or not to_type or to_type == "No types found":
            messagebox.showerror("Replace TMC Type", "Please select valid From and To types.")
            return
        source_rows = [
            row for row in self.tmc_data_rows
            if self._classify_prop(row[3].get().strip()) == from_type
        ]
        if not source_rows:
            messagebox.showinfo("Replace TMC Type", f"No editable entries of Type '{from_type}' were found.")
            return
        target_paths, seen = [], set()
        for _source_category, path, _count in get_combined_object_database(self.CONFIG_FILE):
            path = (path or "").strip()
            key = path.casefold()
            if path and self._classify_prop(path) == to_type and key not in seen:
                seen.add(key)
                target_paths.append(path)
        if not target_paths:
            messagebox.showerror("Replace TMC Type", f"The database contains no paths of Type '{to_type}'.")
            return
        assignments = []
        while len(assignments) < len(source_rows):
            cycle = target_paths.copy()
            random.shuffle(cycle)
            assignments.extend(cycle)
        random.shuffle(source_rows)
        for (_object_id, _original, _count, variable), target_path in zip(
            source_rows, assignments[:len(source_rows)]
        ):
            variable.set(target_path)
        duplicates = max(0, len(source_rows) - len(target_paths))
        self._render_tmc_data_rows()
        self._refresh_tmc_replace_menus()
        self.status_var.set(
            f"TMC Type replaced: {from_type} -> {to_type} | "
            f"{len(source_rows)} entries | {duplicates} duplicates"
        )
        messagebox.showinfo(
            "Replace TMC Type",
            f"Replaced entries: {len(source_rows)}\nFrom: {from_type}\nTo: {to_type}\n"
            f"Unique target paths: {len(target_paths)}\n"
            f"Duplicate assignments required: {duplicates}\n\nClick Save to write the changes."
        )








    # Backward-compatible name used by older builds.



    def _reset_tmc_data(self):
        for _object_id, original, _count, variable in self.tmc_data_rows:
            variable.set(original)
        self._render_tmc_data_rows()
        self._refresh_tmc_replace_menus()
        self.status_var.set("tmc-data reset to original values")

    def _save_tmc_data(self):
        if not self.tmc_data_file_rows:
            messagebox.showerror("tmc-data", "Load TMC data first.")
            return
        replacements = {
            (object_id, original): variable.get().strip()
            for object_id, original, _count, variable in self.tmc_data_rows
        }
        if any(not value for value in replacements.values()):
            messagebox.showerror("tmc-data", "Filename must not be empty.")
            return

        saved = 0
        unchanged = 0
        changed_entries = 0
        for original_path, _rows in self.tmc_data_file_rows.items():
            try:
                tree = self._parse_xml_tolerant(original_path)[0]
                entries = self._tmc_ground_object_elements(tree.getroot())
            except (ET.ParseError, OSError, UnicodeError) as exc:
                messagebox.showerror("tmc-data", f"Could not read {original_path}:\n{exc}")
                return
            file_changed = False
            for object_id, filename, node in entries:
                new_value = replacements.get((object_id, filename), filename)
                if new_value != filename:
                    node.text = new_value
                    file_changed = True
                    changed_entries += 1
            target = original_path.with_name(
                original_path.name.replace("_original.xml", "_patched.xml")
            )
            if file_changed:
                try:
                    tree.write(target, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
                except OSError as exc:
                    messagebox.showerror("tmc-data", f"Could not save {target}:\n{exc}")
                    return
                saved += 1
            else:
                try:
                    if target.exists():
                        target.unlink()
                except OSError:
                    pass
                unchanged += 1

        self.status_var.set(
            f"tmc-data saved: {saved} changed patched XML files | {changed_entries} changed entries"
        )
        messagebox.showinfo(
            "tmc-data",
            f"Changed patched XML files created: {saved}\n"
            f"Unchanged TMC XML files: {unchanged}\n"
            f"Changed FileName entries: {changed_entries}",
        )



    def _select_gamefiles_folder(self):
        initial = self.gamefiles_var.get().strip()
        value = filedialog.askdirectory(
            title="Select Anno 1800 maindata folder",
            initialdir=initial if initial and Path(initial).is_dir() else None,
        )
        if not value:
            return
        folder = Path(value)
        if folder.name.lower() != "maindata":
            messagebox.showerror("Exports", "Please select the maindata folder containing the data*.rda files.")
            return
        if not any(folder.glob("data*.rda")):
            messagebox.showerror("Exports", "No data*.rda files were found in the selected maindata folder.")
            return
        self.gamefiles_var.set(str(folder))
        self._save_config()
        self.status_var.set(f"Gamefiles folder: {folder}")

    def _export_rda_archives(self):
        maindata = Path(self.gamefiles_var.get().strip())
        if not maindata.is_dir() or maindata.name.lower() != "maindata":
            messagebox.showerror("Exports", "Please select a valid Anno 1800 maindata folder first.")
            return None, None
        rda_console = Path(self.rda_var.get().strip())
        if not rda_console.is_file():
            messagebox.showerror("Exports", "RdaConsole.exe is not configured. Please configure it in Settings.")
            return None, None
        archives = [maindata / f"data{i}.rda" for i in range(34) if (maindata / f"data{i}.rda").is_file()]
        if not archives:
            messagebox.showerror("Exports", "No data0.rda through data33.rda files were found.")
            return None, None
        return maindata, archives

    def _start_export_material_sets(self):
        if self._busy():
            return
        maindata, archives = self._export_rda_archives()
        if maindata is None:
            return
        target = filedialog.askdirectory(title="Select target folder for material_sets export")
        if not target:
            return
        self._start_filtered_rda_export(
            maindata, Path(target), archives, "material_sets/", "material_sets"
        )

    def _start_export_island_data(
        self, region_name: str, folder_filter: str,
        replace_map_textures_with_links: bool = False,
        minimize_console: bool = False,
        create_a7m_source_csv: bool = False,
    ):
        if self._busy():
            return
        folder_filter = folder_filter.strip().strip("/\\")
        if not folder_filter:
            messagebox.showerror("Exports", "Please enter a filter path for the Custom export.")
            return
        maindata, archives = self._export_rda_archives()
        if maindata is None:
            return
        target = filedialog.askdirectory(title=f"Select target folder for {region_name} island data")
        if not target:
            return
        self._start_filtered_rda_export(
            maindata, Path(target), archives, folder_filter.replace("\\", "/") + "/", region_name,
            replace_map_textures_with_links=replace_map_textures_with_links,
            create_a7m_source_csv=create_a7m_source_csv,
        )

    def _start_filtered_rda_export(
        self, maindata: Path, target: Path, archives: list[Path],
        folder_filter: str, export_name: str,
        replace_map_textures_with_links: bool = False,
        minimize_console: bool = False,
        create_a7m_source_csv: bool = False,
    ):
        target.mkdir(parents=True, exist_ok=True)
        self.stop_event.clear()
        self._clear_log(self.exports_log)
        self.exports_progress.set(0)
        self._set_running(True, "exports")
        self.status_var.set(f"Exporting {export_name}...")
        self.worker = threading.Thread(
            target=self._filtered_rda_export_worker,
            args=(
                maindata, target, archives, folder_filter, export_name,
                replace_map_textures_with_links, minimize_console,
                create_a7m_source_csv,
            ), daemon=True,
        )
        self.worker.start()

    def _filtered_rda_export_worker(
        self, maindata: Path, target: Path, archives: list[Path],
        folder_filter: str, export_name: str,
        replace_map_textures_with_links: bool = False,
        minimize_console: bool = False,
        create_a7m_source_csv: bool = False,
    ):
        ok = False
        try:
            self._event(
                "log_exports",
                f"Export: {export_name}\nGamefiles: {maindata}\nTarget: {target}\nFilter: {folder_filter}\n\n",
            )
            total = len(archives)
            a7m_source_rows = []

            def a7m_snapshot():
                result = {}
                if target.is_dir():
                    for path in target.rglob("*.a7m"):
                        if path.is_file():
                            try:
                                stat = path.stat()
                                result[path] = (stat.st_mtime_ns, stat.st_size)
                            except OSError:
                                pass
                return result

            for index, archive in enumerate(archives, start=1):
                if self.stop_event.is_set():
                    raise CancelledError("Stop requested")
                self._event("status", f"Exporting {export_name}: {archive.name} ({index}/{total})")
                self._event("log_exports", f"[{index}/{total}] {archive.name}\n")
                before_a7m = a7m_snapshot() if create_a7m_source_csv else {}
                self._run([
                    self.rda_var.get(), "extract", "-f", str(archive),
                    "-o", str(target), "--filter", folder_filter, "-y",
                ], maindata, "exports", minimize_console=minimize_console)
                if create_a7m_source_csv:
                    after_a7m = a7m_snapshot()
                    for path, metadata in sorted(after_a7m.items(), key=lambda item: str(item[0]).casefold()):
                        if before_a7m.get(path) != metadata:
                            a7m_source_rows.append((archive.name, str(path.resolve())))
                self._event("progress_exports", index / total)

            if create_a7m_source_csv:
                csv_path = target / "all_maps_a7m_sources.csv"
                with csv_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
                    writer = csv.writer(csv_file, delimiter=";")
                    writer.writerow(("RDA", "A7M Path"))
                    writer.writerows(a7m_source_rows)
                self._event("log_exports", f"\nA7M source CSV created: {csv_path} | {len(a7m_source_rows)} entries\n")

            if replace_map_textures_with_links:
                self._event(
                    "log_exports",
                    "\nReplacing .ctt files in normalmaps with .lnk files...\n",
                )
                replaced, skipped = self._replace_exported_map_textures_with_links(target)
                self._event(
                    "log_exports",
                    f"Texture link conversion completed: {replaced} replaced, {skipped} skipped.\n",
                )

            self._event("log_exports", f"\n{export_name} export completed successfully.\n")
            ok = True
        except CancelledError as exc:
            self._event("log_exports", f"\nCancelled: {exc}\n")
        except Exception as exc:
            self._event("log_exports", f"\nERROR: {exc}\n")
        finally:
            self._event("done", ("exports", ok, self.stop_event.is_set()))

    @staticmethod
    def _replace_exported_map_textures_with_links(target: Path):
        """Replace exported CTT/DDS files inside normalmaps with text .lnk files.

        RdaConsole exports the archive's data/ tree below the selected target.
        The link content is therefore reconstructed from the path below the
        exported 'data' directory, using Anno-style forward slashes.
        """
        target = Path(target)
        replaced = 0
        skipped = 0
        candidates = []
        for path in target.rglob("*"):
            if not path.is_file() or path.suffix.casefold() not in {".ctt", ".dds"}:
                continue
            parent_names = {part.casefold() for part in path.parent.parts}
            if "normalmaps" not in parent_names:
                continue
            candidates.append(path)

        for source in sorted(candidates, key=lambda item: str(item).casefold()):
            parts = source.parts
            data_index = next(
                (index for index, part in enumerate(parts) if part.casefold() == "data"),
                None,
            )
            if data_index is None:
                # Normally RdaConsole outputs the archive data/ tree. Do not
                # invent a game path if that path anchor is unexpectedly absent.
                skipped += 1
                continue
            # The .lnk content starts exactly at the archive's data\ root.
            # Example: data/sessions/islands/.../normalmaps/0/0x0.ctt
            game_path = "/".join(parts[data_index:])
            link_path = source.with_name(source.name + ".lnk")
            link_path.write_text(game_path, encoding="utf-8")
            source.unlink()
            replaced += 1
        return replaced, skipped





    def _create_custom_island(self, source=None, selected_a7m=None):
        if self._busy():
            return
        if source is None:
            source_default = self.custom_map_folder_var.get().strip()
            source_value = filedialog.askdirectory(
                title="Select source map folder",
                initialdir=source_default if source_default and Path(source_default).is_dir() else None,
            )
            if not source_value:
                return
            source = Path(source_value)
        else:
            source = Path(source)
        if not source.is_dir():
            messagebox.showerror("Create Custom Island", f"Source folder does not exist:\n{source}")
            return
        if selected_a7m is None:
            try:
                selected_a7m = self._start_choose_source_variant(source)
            except OSError as exc:
                messagebox.showerror("Create Custom Island", str(exc))
                return
            if selected_a7m is None:
                return
        else:
            selected_a7m = Path(selected_a7m)
        old_name = selected_a7m.stem

        dialog = PopupTemplate.create_window(
            self, title="Create Custom Island", geometry="520x180", min_size=(520,180),
            resizable=False, modal=True, add_header=False, maximize=False,
        )["window"]
        dialog.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dialog,
            text="New Folder / Map Name",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 8), sticky="w")

        name_var = tk.StringVar(value=f"{old_name}_skinned")
        name_entry = ctk.CTkEntry(dialog, textvariable=name_var)
        name_entry.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="ew")
        def _focus_name_entry():
            if not PopupTemplate.window_exists(dialog) or not PopupTemplate.window_exists(name_entry):
                return
            try:
                name_entry.select_range(0, "end")
            except (tk.TclError, AttributeError):
                pass
        PopupTemplate.request_focus(dialog, widget=name_entry, delay_ms=50)
        PopupTemplate.schedule(dialog, 55, _focus_name_entry)

        result = {"name": None}

        def accept_name():
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showerror("Create Custom Island", "Please enter a new folder / map name.", parent=dialog)
                return
            if any(char in new_name for char in '<>:"/\\|?*'):
                messagebox.showerror("Create Custom Island", "The map name contains characters that are not valid in a Windows folder name.", parent=dialog)
                return
            result["name"] = new_name
            PopupTemplate.close_window(dialog)

        ctk.CTkButton(dialog, text="OK", width=110, command=accept_name).grid(
            row=2, column=0, padx=20, pady=(0, 18), sticky="e"
        )
        name_entry.bind("<Return>", lambda _event: accept_name())
        self.wait_window(dialog)

        new_name = result["name"]
        if not new_name:
            return

        target_default = self.default_custom_maps_var.get().strip()
        if not target_default:
            messagebox.showwarning(
                "Create Custom Island",
                "Please configure Temporary Map Folder in Settings first.",
            )
            return
        destination_root = Path(target_default).expanduser()
        try:
            destination_root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(
                "Create Custom Island",
                f"Could not create Temporary Map Folder:\n{destination_root}\n\n{exc}",
            )
            return
        destination = destination_root / new_name

        if destination.resolve().is_relative_to(source.resolve()):
            messagebox.showerror("Create Custom Island", "The target must be outside the source folder.")
            return
        try:
            copy_directories, copy_files = self._start_variant_copy_plan(source, selected_a7m, new_name)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Create Custom Island", f"Could not prepare selected variant:\n{exc}")
            return
        if destination.exists():
            messagebox.showerror(
                "Create Custom Island",
                f"The target folder already exists:\n{destination}",
            )
            return

        progress_window = PopupTemplate.create_window(
            self, title="Create Custom Island", geometry="680x210", min_size=(680,210),
            resizable=False, modal=True, add_header=False, maximize=False,
        )["window"]
        progress_window.protocol("WM_DELETE_WINDOW", lambda: None)
        progress_window.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            progress_window,
            text="Copying Custom Island...",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 8), sticky="w")

        copy_file_var = tk.StringVar(value="Preparing files...")
        ctk.CTkLabel(
            progress_window,
            textvariable=copy_file_var,
            anchor="w",
            justify="left",
            wraplength=630,
        ).grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")

        copy_progress = ctk.CTkProgressBar(progress_window)
        copy_progress.grid(row=2, column=0, padx=20, pady=(0, 6), sticky="ew")
        copy_progress.set(0)

        copy_count_var = tk.StringVar(value="0 / 0")
        ctk.CTkLabel(
            progress_window,
            textvariable=copy_count_var,
            text_color="gray70",
        ).grid(row=3, column=0, padx=20, pady=(0, 18), sticky="e")

        # Force the popup to become visible before the first potentially large copy.
        progress_window.update_idletasks()
        progress_window.update()

        try:
            total_files = len(copy_files)
            copy_count_var.set(f"0 / {total_files}")

            destination.mkdir(parents=True, exist_ok=False)

            # Create all directories first, including empty directories.
            for relative_dir in copy_directories:
                (destination / relative_dir).mkdir(parents=True, exist_ok=True)

            # Copy file by file so the user can see exactly what is being copied.
            for index, (source_file, relative_file) in enumerate(copy_files, start=1):
                target_file = destination / relative_file
                target_file.parent.mkdir(parents=True, exist_ok=True)

                copy_file_var.set(str(relative_file))
                copy_count_var.set(f"{index} / {total_files}")
                copy_progress.set(index / total_files if total_files else 1)

                # Process the redraw before starting this file copy.
                progress_window.update_idletasks()
                progress_window.update()

                shutil.copy2(source_file, target_file)

            copy_file_var.set("Renaming island files and folders...")
            copy_progress.set(1)
            progress_window.update_idletasks()
            progress_window.update()

            # Variant paths were filtered and renamed in the copy plan.
            # Shared containers such as _gamedata keep their original names.
            # Automatically load the newly created A7M into the Start tab.
            new_a7m_path = destination / f"{new_name}.a7m"
            if new_a7m_path.is_file():
                self.unpack_file_var.set(str(new_a7m_path))
                self.pack_file_var.set(str(new_a7m_path))
                self._event("files_folders_ready", str(new_a7m_path))
                self.status_var.set(f"Custom island created and A7M selected: {new_a7m_path}")
            else:
                self.status_var.set(f"Custom island created: {destination}")

            if progress_window.winfo_exists():
                progress_window.grab_release()
                progress_window.destroy()

            messagebox.showinfo(
                "Create Custom Island",
                "Custom island created successfully.\n\n"
                f"Source: {source}\n"
                f"Target: {destination}\n\n"
                f"Map name: {old_name} -> {new_name}",
            )

        except (OSError, shutil.Error) as exc:
            try:
                if progress_window.winfo_exists():
                    progress_window.grab_release()
                    progress_window.destroy()
            except tk.TclError:
                pass

            # Remove a partially copied target when creation failed.
            try:
                if destination.exists():
                    shutil.rmtree(destination)
            except OSError:
                pass
            messagebox.showerror(
                "Create Custom Island",
                f"The custom island could not be created:\n{exc}",
            )

    def _refresh_files_and_folders_from_map(self, a7m_file: Path, show_missing=False):
        self._xml_loading_depth += 1
        try:
            self._xml_loading_show('Detecting island XML files...', 0.05)
            return self._refresh_files_and_folders_from_map_with_progress_body(a7m_file, show_missing=show_missing)
        except Exception as exc:
            self._xml_loading_finish(str(exc))
            raise
        finally:
            self._xml_loading_depth -= 1
            self._xml_loading_finish()

    def _refresh_files_and_folders_from_map_with_progress_body(self, a7m_file: Path, show_missing=False):
        """Populate paths and rebuild caches for exactly the selected island."""
        a7m_file = Path(a7m_file)
        if not a7m_file.is_file() or a7m_file.suffix.casefold() != ".a7m":
            return []
        resolved = str(a7m_file.resolve())
        if getattr(self, "_island_cache_a7m_path", None) != resolved:
            self._invalidate_island_runtime_cache(a7m_file)
        root = a7m_file.parent
        map_name = a7m_file.stem
        data_dir = root / map_name
        paths = [
            ("gamedata_original.xml", data_dir / "gamedata_original.xml", self.gamedata_file_var, "file"),
            ("mapname_original.xml", root / f"{map_name}_original.xml", self.mapname_file_var, "file"),
            ("rd3d_original.xml", data_dir / "rd3d_original.xml", self.rd3d_file_var, "file"),
            ("Meshes folder", root / "_gamedata" / map_name / "meshes", self.tmc_data_meshes_var, "folder"),
        ]
        missing = []
        total_paths = len(paths)
        for path_index, (label, path, variable, kind) in enumerate(paths, start=1):
            self._xml_loading_show(
                f"Detecting island files: {label} ({path_index}/{total_paths})",
                0.05 + (0.25 * path_index / total_paths),
            )
            exists = path.is_file() if kind == "file" else path.is_dir()
            if exists:
                variable.set(str(path))
            else:
                # Clear stale paths from a previously selected island.
                variable.set("")
                missing.append((label, path))
        # File/folder detection must also refresh the data models consumed by
        # Regional Settings, rd3d.data and tmc-data. Merely setting StringVars
        # leaves their displayed content stale.
        if self.gamedata_file_var.get().strip():
            self._xml_loading_show("Loading gamedata_original.xml...", 0.40)
            self._load_gamedata_xml(show_errors=False)
            self.after_idle(self._refresh_slot_configuration_from_files)
        else:
            self.after_idle(self._refresh_slot_configuration_from_files)
        if self.rd3d_file_var.get().strip():
            self._xml_loading_show("Loading rd3d_original.xml...", 0.66)
            self._load_rd3d_xml(show_errors=False)
        self._xml_loading_show("Starting RD3D/TMC memory cache...", 0.86)
        self._tmc_ram_preload()
        self._xml_loading_show("Island XML files loaded.", 1.0)
        # The removed tmc-data tab has no render widgets. Object Configuration
        # and Finalize consume the shared Meshes path directly and load on demand.

        if show_missing and missing:
            details = "\n".join(f"- {label}: {path}" for label, path in missing)
            messagebox.showinfo(
                "Files and Folders",
                "The selected island does not appear to be fully unpacked yet.\n\n"
                "Missing files/folders:\n" + details +
                "\n\nUse the Start tab to unpack the island first.",
            )
        return missing

    def _select_files_folders_a7m(self):
        if self._busy():
            return
        """Select the map A7M from Files and Folders and auto-populate related paths."""
        current = self.unpack_file_var.get().strip()
        value = filedialog.askopenfilename(
            title="Select A7M file",
            initialdir=str(Path(current).parent) if current and Path(current).parent.is_dir() else None,
            filetypes=[("Anno island", "*.a7m"), ("All files", "*.*")],
        )
        if not value:
            return
        a7m = Path(value)
        previous = self.unpack_file_var.get().strip()
        if not previous or Path(previous) != a7m:
            self._invalidate_island_runtime_cache(a7m)
        self.unpack_file_var.set(str(a7m))
        self.pack_file_var.set(str(a7m))
        self._autodetect_unpack_meshes_folder(a7m)
        self._refresh_files_and_folders_from_map(a7m, show_missing=True)

    def _select_unpack_file(self):
        value = filedialog.askopenfilename(filetypes=[("Anno island", "*.a7m"), ("All files", "*.*")])
        if value:
            self.unpack_file_var.set(value)
            self.pack_file_var.set(value)
            self._autodetect_unpack_meshes_folder(Path(value))
            self._refresh_files_and_folders_from_map(Path(value))

    def _autodetect_unpack_meshes_folder(self, a7m_file: Path):
        """Detect root/_gamedata/<mapname>/meshes for the selected A7M."""
        a7m_file = Path(a7m_file)
        if not a7m_file.is_file() or a7m_file.suffix.lower() != ".a7m":
            return False

        root = a7m_file.parent
        map_name = a7m_file.stem
        gamedata_root = root / "_gamedata"

        # Required/normal layout:
        # root/mapname.a7m
        # root/_gamedata/mapname/meshes
        expected = gamedata_root / map_name / "meshes"
        if expected.is_dir():
            meshes = expected
        elif gamedata_root.is_dir():
            # Case-insensitive map-name/meshes lookup first.
            meshes = None
            for map_folder in gamedata_root.iterdir():
                if not map_folder.is_dir() or map_folder.name.casefold() != map_name.casefold():
                    continue
                candidate = next(
                    (child for child in map_folder.iterdir()
                     if child.is_dir() and child.name.casefold() == "meshes"),
                    None,
                )
                if candidate is not None:
                    meshes = candidate
                    break
            if meshes is None:
                # Last fallback only when _gamedata contains exactly one meshes folder.
                candidates = sorted(
                    (folder for folder in gamedata_root.rglob("*")
                     if folder.is_dir() and folder.name.casefold() == "meshes"),
                    key=lambda folder: str(folder).casefold(),
                )
                if len(candidates) != 1:
                    return False
                meshes = candidates[0]
        else:
            return False

        self.tmc_data_meshes_var.set(str(meshes))
        self.status_var.set(f"Meshes folder detected: {meshes}")
        return True

    def _select_pack_file(self):
        value = filedialog.askopenfilename(filetypes=[("Anno island", "*.a7m"), ("All files", "*.*")])
        if value:
            self.pack_file_var.set(value)

    def _select_pack_meshes_folder(self):
        initial = self.tmc_data_meshes_var.get().strip()
        value = filedialog.askdirectory(
            title="Select Meshes folder",
            initialdir=initial if initial and Path(initial).is_dir() else None,
        )
        if value:
            self.tmc_data_meshes_var.set(value)
            # The tmc-data tab uses the same path variable, so both tabs always
            # reference the same selected meshes folder.
            self._load_tmc_data(show_errors=False)

    def _select_pack_folder(self):
        value = filedialog.askdirectory(title="Select island folder")
        if value:
            self.pack_file_var.set(value)

    def _select_exe(self, variable, expected):
        value = filedialog.askopenfilename(title=expected, filetypes=[(expected, expected), ("Programs", "*.exe")])
        if value:
            variable.set(value)
            self._save_config()

    def _select_fdb(self):
        self._select_exe(self.fdb_var, "FileDBReader.exe")

    def _start_unpack(self):
        if self._busy():
            return
        source = Path(self.unpack_file_var.get().strip())
        if not source.is_file() or source.suffix.lower() != ".a7m":
            messagebox.showerror("Unpack", "Please select an existing .a7m file.")
            return
        errors = self._validate_settings()
        if errors:
            self._show_settings_errors(errors)
            return
        self._autodetect_unpack_meshes_folder(source)
        self._prepare_job("unpack")
        self.worker = threading.Thread(target=self._unpack_worker, args=(source,), daemon=True)
        self.worker.start()

    def _delete_pack_xml_files(self):
        """Remove generated XML/data files and backup/original files from the map folder."""
        if self._busy():
            return
        try:
            root, _a7m_file, _data_dir = self._resolve_island(
                Path(self.pack_file_var.get().strip())
            )
        except ValueError as exc:
            messagebox.showerror("CleanUp", str(exc))
            return

        cleanup_files = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.casefold()
            suffix = path.suffix.casefold()
            if (
                suffix == ".xml"
                or suffix == ".data"
                or "_backup" in name
                or "_original" in name
            ):
                cleanup_files.append(path)

        cleanup_files.sort(key=lambda path: str(path).casefold())
        if not cleanup_files:
            messagebox.showinfo(
                "CleanUp",
                f"No cleanup files were found in:\n{root}",
            )
            return

        xml_count = sum(path.suffix.casefold() == ".xml" for path in cleanup_files)
        data_count = sum(path.suffix.casefold() == ".data" for path in cleanup_files)
        backup_count = sum("_backup" in path.name.casefold() for path in cleanup_files)
        original_count = sum(
            "_original" in path.name.casefold() for path in cleanup_files
        )

        if not messagebox.askyesno(
            "CleanUp",
            "Delete cleanup files in this map folder and all subfolders?\n\n"
            f"Folder: {root}\n\n"
            f"XML files: {xml_count}\n"
            f"DATA files: {data_count}\n"
            f"Backup files: {backup_count}\n"
            f"Original files: {original_count}\n"
            f"Total files: {len(cleanup_files)}\n\n"
            "This cannot be undone.",
        ):
            return

        deleted = 0
        errors = []
        for cleanup_file in cleanup_files:
            try:
                cleanup_file.unlink()
                deleted += 1
            except OSError as exc:
                errors.append(f"{cleanup_file}: {exc}")

        self.status_var.set(f"CleanUp: deleted {deleted} file(s) from {root}")
        if errors:
            preview = "\n".join(errors[:10])
            if len(errors) > 10:
                preview += f"\n... and {len(errors) - 10} more error(s)"
            messagebox.showwarning(
                "CleanUp",
                f"Deleted: {deleted}\nFailed: {len(errors)}\n\n{preview}",
            )
        else:
            messagebox.showinfo(
                "CleanUp",
                f"CleanUp completed successfully.\n\n"
                f"Deleted files: {deleted}\n"
                f"Map folder:\n{root}",
            )

    def _start_pack(self):
        if self._busy():
            return
        try:
            root, a7m_file, data_dir = self._resolve_island(Path(self.pack_file_var.get().strip()))
        except ValueError as exc:
            messagebox.showerror("Pack", str(exc))
            return
        errors = self._validate_settings()
        if errors:
            self._show_settings_errors(errors)
            return
        self._prepare_job("pack")
        self.worker = threading.Thread(target=self._pack_worker, args=(root, a7m_file, data_dir), daemon=True)
        self.worker.start()

    def _prepare_job(self, mode):
        self.stop_event.clear()
        self.status_var.set("Preparing...")
        self._set_running(True, mode)
        progress = self.unpack_progress if mode == "unpack" else self.pack_progress
        progress.set(0)
        self._clear_log(self.unpack_log if mode == "unpack" else self.pack_log)

    def _unpack_worker(self, source: Path):
        ok = False
        try:
            root = source.parent
            data_dir = root / source.stem
            self._event("status", f"Unpacking {source.name}...")
            self._event("log_unpack", f"Source: {source}\nTarget folder: {data_dir}\n\n")
            if data_dir.exists() and any(data_dir.iterdir()):
                if not self._ask_worker_yes_no("Folder already exists", f"The folder is not empty:\n{data_dir}\n\nContinue using or overwrite existing files?"):
                    raise CancelledError("Cancelled by user")
            data_dir.mkdir(parents=True, exist_ok=True)

            self._run([self.rda_var.get(), "extract", "-f", str(source), "-o", str(data_dir), "-y"], root, "unpack")

            # The meshes directory may not exist until the A7M has been extracted.
            # Re-detect the external island layout before starting TMC conversion.
            if self._autodetect_unpack_meshes_folder(source):
                self._event(
                    "log_unpack",
                    f"Meshes folder detected: {self.tmc_data_meshes_var.get()}\n",
                )
            self._event("progress_unpack", 0.30)

            gamedata = self._find_data_file(data_dir, "gamedata.data")
            rd3d = self._find_data_file(data_dir, "rd3d.data")

            if self.unpack_gamedata_var.get():
                if not gamedata:
                    raise RuntimeError("gamedata.data was not found in the unpacked folder.")
                self._event("log_unpack", "\nUnpacking gamedata.data...\n")
                self._run(
                    [self.fdb_var.get(), "decompress", "-f", str(gamedata), "-y", "-i", self.gamedata_format_var.get()],
                    data_dir, "unpack",
                )
                game_xml = self._locate_generated_xml(data_dir, gamedata, "gamedata")
                gamedata_original = data_dir / "gamedata_original.xml"
                self._rename_replace(game_xml, gamedata_original)
                self._event("gamedata_ready", str(gamedata_original))
            else:
                self._event("log_unpack", "\nSkipping gamedata.data (disabled).\n")
            self._event("progress_unpack", 0.50)

            if self.unpack_rd3d_var.get():
                if not rd3d:
                    raise RuntimeError("rd3d.data was not found in the unpacked folder.")
                self._event("log_unpack", "\nUnpacking rd3d.data...\n")
                self._run(
                    [self.fdb_var.get(), "decompress", "-f", str(rd3d), "-y", "-i", self.rd3d_format_var.get()],
                    data_dir, "unpack",
                )
                rd3d_xml = self._locate_generated_xml(data_dir, rd3d, "rd3d")
                rd3d_original = data_dir / "rd3d_original.xml"
                self._rename_replace(rd3d_xml, rd3d_original)
                self._event("rd3d_ready", str(rd3d_original))
            else:
                self._event("log_unpack", "\nSkipping rd3d.data (disabled).\n")
            self._event("progress_unpack", 0.65)

            if self.unpack_tmc_var.get():
                self._unpack_tmc_files(data_dir)
            else:
                self._event("log_unpack", "\nSkipping TMC files (disabled).\n")
            self._event("progress_unpack", 0.82)

            info = source.with_suffix(".a7minfo")
            if self.unpack_a7minfo_var.get() and info.is_file():
                self._run([self.fdb_var.get(), "decompress", "-f", str(info), "-y", "-i", self.a7minfo_format_var.get()], root, "unpack")
                info_xml = self._locate_generated_xml(root, info, source.stem)
                mapname_original = root / f"{source.stem}_original.xml"
                self._rename_replace(info_xml, mapname_original)
                self._event("mapname_ready", str(mapname_original))
                self._event("log_unpack", f"MapName XML ready: {mapname_original.name}\n")
            self._event("progress_unpack", 1.0)
            self._event("files_folders_ready", str(source))
            self._event("log_unpack", "\nUnpacking completed successfully.\n")
            ok = True
        except CancelledError as exc:
            self._event("log_unpack", f"\nCancelled: {exc}\n")
        except Exception as exc:
            self._event("log_unpack", f"\nERROR: {exc}\n")
        finally:
            self._event("done", ("unpack", ok, self.stop_event.is_set()))

    def _pack_worker(self, root: Path, a7m_file: Path, data_dir: Path):
        ok = False
        try:
            self._event("status", f"Packing {a7m_file.name}...")
            self._event("log_pack", f"Island root: {root}\nData folder: {data_dir}\nTarget file: {a7m_file}\n\n")

            # XMLTest used to create gamedata.xml / rd3d.xml from original+patch.
            # Our editors already create the complete *_patched.xml, so stage
            # those files under the legacy names expected by the known-good
            # pack_island workflow.
            game_patched = data_dir / "gamedata_patched.xml"
            rd3d_patched = data_dir / "rd3d_patched.xml"
            for required in (game_patched, rd3d_patched):
                if not required.is_file():
                    raise RuntimeError(f"Required patched file is missing: {required}")

            game_pack_xml = data_dir / "gamedata.xml"
            rd3d_pack_xml = data_dir / "rd3d.xml"
            shutil.copy2(game_patched, game_pack_xml)
            shutil.copy2(rd3d_patched, rd3d_pack_xml)
            self._event("log_pack", f"Prepared pack XML: {game_patched.name} -> {game_pack_xml.name}\n")
            self._event("progress_pack", 0.18)
            self._event("log_pack", f"Prepared pack XML: {rd3d_patched.name} -> {rd3d_pack_xml.name}\n")
            self._event("progress_pack", 0.36)

            game_output = self._compress_data(game_pack_xml, self.gamedata_format_var.get(), data_dir, "pack")
            rd3d_output = self._compress_data(rd3d_pack_xml, self.rd3d_format_var.get(), data_dir, "pack")
            self._event("progress_pack", 0.55)

            self._pack_tmc_files(data_dir)
            self._event("progress_pack", 0.68)

            final_game = data_dir / "gamedata.data"
            final_rd3d = data_dir / "rd3d.data"
            self._install_binary(game_output, final_game)
            self._install_binary(rd3d_output, final_rd3d)

            if self.backup_var.get() and a7m_file.exists():
                self._backup(a7m_file)
            self._run([
                self.rda_var.get(), "pack", "-f", str(final_game), str(final_rd3d),
                "-o", str(a7m_file), "-y", "-v", "2"
            ], root, "pack")
            self._event("progress_pack", 0.82)

            info_patched = root / f"{a7m_file.stem}_patched.xml"
            if info_patched.is_file():
                info_pack_xml = root / f"{a7m_file.stem}.xml"
                shutil.copy2(info_patched, info_pack_xml)
                self._event(
                    "log_pack",
                    f"Prepared A7MINFO XML: {info_patched.name} -> {info_pack_xml.name}\n",
                )
                info_output = self._compress_a7minfo(info_pack_xml, root, "pack")
                final_info = a7m_file.with_suffix(".a7minfo")
                if self.backup_var.get() and final_info.exists():
                    self._backup(final_info)
                self._rename_replace(info_output, final_info)
                self._event("log_pack", f"A7MINFO created from patched XML: {final_info.name}\n")
            else:
                self._event("log_pack", f"A7MINFO skipped: {info_patched.name} is missing.\n")

            self._event("progress_pack", 1.0)
            self._event("log_pack", "\nPacking completed successfully.\n")
            ok = True
        except CancelledError as exc:
            self._event("log_pack", f"\nCancelled: {exc}\n")
        except Exception as exc:
            self._event("log_pack", f"\nERROR: {exc}\n")
        finally:
            self._event("done", ("pack", ok, self.stop_event.is_set()))

    def _unpack_tmc_files(self, data_dir: Path):
        """Find and decompress TMC files only in the selected meshes folder."""
        selected_meshes = Path(self.tmc_data_meshes_var.get().strip())
        if not selected_meshes.is_dir():
            # data_dir is root/<mapname>; the TMC folder is outside it at
            # root/_gamedata/<mapname>/meshes.
            expected = data_dir.parent / "_gamedata" / data_dir.name / "meshes"
            if expected.is_dir():
                selected_meshes = expected
                self.tmc_data_meshes_var.set(str(selected_meshes))
            else:
                gamedata_root = data_dir.parent / "_gamedata"
                candidates = sorted(
                    (folder for folder in gamedata_root.rglob("*")
                     if folder.is_dir() and folder.name.casefold() == "meshes")
                    if gamedata_root.is_dir() else (),
                    key=lambda folder: str(folder).casefold(),
                )
                if len(candidates) == 1:
                    selected_meshes = candidates[0]
                    self.tmc_data_meshes_var.set(str(selected_meshes))
        if not selected_meshes.is_dir():
            raise RuntimeError(
                "TMC unpack could not find the meshes folder. Expected layout:\n"
                f"{data_dir.parent / '_gamedata' / data_dir.name / 'meshes'}"
            )

        self._event(
            "log_unpack",
            "\nStarting TMC search...\n"
            f"Selected Meshes folder: {selected_meshes}\n",
        )
        search_roots = [selected_meshes]

        tmc_files: list[Path] = []
        seen_files: set[str] = set()
        for search_root in search_roots:
            self._event("log_unpack", f"Searching: {search_root}\n")
            for candidate in search_root.rglob("*"):
                if not candidate.is_file() or candidate.suffix.lower() != ".tmc":
                    continue
                try:
                    unique_key = str(candidate.resolve()).lower()
                except OSError:
                    unique_key = str(candidate.absolute()).lower()
                if unique_key not in seen_files:
                    seen_files.add(unique_key)
                    tmc_files.append(candidate)
        tmc_files.sort(key=lambda path: str(path).lower())
        if not tmc_files:
            self._event("log_unpack", "\nNo TMC files found.\n")
            return

        try:
            worker_count = int(self.tmc_parallel_var.get().strip())
        except ValueError:
            worker_count = 4
        worker_count = max(1, min(worker_count, 32, len(tmc_files)))
        self._event(
            "log_unpack",
            f"\nTMC files found: {len(tmc_files)}\nParallel TMC workers: {worker_count}\n\n",
        )

        successful = 0
        failures: list[tuple[Path, str]] = []
        completed = 0
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="TMC") as executor:
            futures = {
                executor.submit(self._unpack_single_tmc, tmc_file): tmc_file
                for tmc_file in tmc_files
            }
            for future in as_completed(futures):
                tmc_file = futures[future]
                if self.stop_event.is_set():
                    for pending in futures:
                        pending.cancel()
                    raise CancelledError("Stop requested")
                completed += 1
                try:
                    original_xml = future.result()
                    successful += 1
                    self._event(
                        "log_unpack",
                        f"[{completed}/{len(tmc_files)}] OK: {tmc_file.name}\n",
                    )
                except CancelledError:
                    for pending in futures:
                        pending.cancel()
                    raise
                except Exception as exc:
                    failures.append((tmc_file, str(exc)))
                    self._event(
                        "log_unpack",
                        f"[{completed}/{len(tmc_files)}] FAILED: {tmc_file}\n  {exc}\n",
                    )

        with self.parallel_processes_lock:
            remaining_processes = [process for process in self.parallel_processes if process.poll() is None]
        if remaining_processes:
            for process in remaining_processes:
                self._kill_specific_process(process)
        with self.parallel_processes_lock:
            self.parallel_processes.clear()

        self._event(
            "log_unpack",
            f"\nTMC conversion completed:\n"
            f"  Successful: {successful}\n"
            f"  Failed: {len(failures)}\n"
            f"  Workers: {worker_count}\n",
        )
        if failures:
            self._event("log_unpack", "\nTMC FILES WITH ERRORS:\n")
            for failed_file, error in failures:
                self._event("log_unpack", f"  - {failed_file}\n    {error}\n")

    def _unpack_single_tmc(self, tmc_file: Path) -> Path:
        if self.stop_event.is_set():
            raise CancelledError("Stop requested")
        self._run_parallel_process(
            [
                self.fdb_var.get(), "decompress", "-f", str(tmc_file),
                "-i", self.tmc_format_var.get(), "-y",
            ],
            tmc_file.parent,
            "unpack",
        )
        if self.stop_event.is_set():
            raise CancelledError("Stop requested")

        generated_xml = tmc_file.with_suffix(".xml")
        if not generated_xml.is_file():
            possible_xml_files = sorted(
                [candidate for candidate in tmc_file.parent.iterdir()
                 if candidate.is_file()
                 and candidate.suffix.lower() == ".xml"
                 and candidate.stem.lower() == tmc_file.stem.lower()],
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            if possible_xml_files:
                generated_xml = possible_xml_files[0]
        if not generated_xml.is_file():
            raise RuntimeError(f"FileDBReader did not create an XML file for the TMC file: {tmc_file}")

        original_xml = tmc_file.with_name(f"{tmc_file.stem}_original.xml")
        self._rename_replace(generated_xml, original_xml)
        return original_xml

    @staticmethod
    def _find_process_window(process_id: int, timeout: float = 3.0):
        """Find a visible top-level window that belongs to the given process."""
        if os.name != "nt":
            return None

        user32 = ctypes.windll.user32
        found = []
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )

        def enum_callback(hwnd, _lparam):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == process_id and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
                return False
            return True

        callback = callback_type(enum_callback)
        end_time = time.monotonic() + timeout
        while time.monotonic() < end_time:
            found.clear()
            user32.EnumWindows(callback, 0)
            if found:
                return found[0]
            time.sleep(0.05)
        return None

    def _console_background_worker(self, process_id: int):
        try:
            self._send_console_behind_app(process_id)
        finally:
            current = threading.current_thread()
            with self.console_helper_threads_lock:
                self.console_helper_threads.discard(current)

    def _send_console_behind_app(self, process_id: int):
        """Place a FileDBReader console behind the app without touching Tk's event queue."""
        if os.name != "nt":
            return

        hwnd = self._find_process_window(process_id, timeout=1.5)
        if not hwnd:
            return

        user32 = ctypes.windll.user32
        HWND_BOTTOM = 1
        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOACTIVATE = 0x0010
        SWP_ASYNCWINDOWPOS = 0x4000

        user32.SetWindowPos(
            hwnd,
            HWND_BOTTOM,
            0,
            0,
            0,
            0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS,
        )

    def _run_parallel_process(self, command: list[str], cwd: Path, mode: str):
        """Run FileDBReader in its own visible Windows console window."""
        if self.stop_event.is_set():
            raise CancelledError("Stop requested")

        # Do not mirror FileDBReader console output/commands into the Tk log.
        # With many parallel TMC jobs that can flood Tk's event queue and make
        # the application sluggish even after the subprocesses have finished.

        # TMC/FileDBReader should run in a real, visible console window.
        # With parallel workers, every active conversion gets its own console.
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 2  # SW_SHOWMINIMIZED
            process = subprocess.Popen(
                [str(x) for x in command],
                cwd=str(cwd),
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            # Fallback for non-Windows development/testing environments.
            process = subprocess.Popen(
                [str(x) for x in command],
                cwd=str(cwd),
            )

        with self.parallel_processes_lock:
            self.parallel_processes.add(process)

        try:
            while True:
                if self.stop_event.is_set():
                    self._kill_specific_process(process)
                    raise CancelledError("Stop requested")

                code = process.poll()
                if code is not None:
                    break

                time.sleep(0.1)

            if self.stop_event.is_set():
                raise CancelledError("Stop requested")

            if code != 0:
                raise RuntimeError(
                    f"FileDBReader exited with code {code}."
                )

        finally:
            with self.parallel_processes_lock:
                self.parallel_processes.discard(process)

    def _kill_specific_process(self, process: subprocess.Popen):
        if process.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                process.kill()
        except OSError:
            pass

    def _wait_for_console_helpers(self, timeout: float = 2.0):
        """Let console-positioning helpers finish so none remain after TMC processing."""
        end_time = time.monotonic() + timeout
        while time.monotonic() < end_time:
            with self.console_helper_threads_lock:
                helpers = [thread for thread in self.console_helper_threads if thread.is_alive()]
            if not helpers:
                return
            for thread in helpers:
                thread.join(timeout=0.05)

    def _pack_one_tmc_file(self, patched: Path):
        """Compress and atomically install one changed TMC file."""
        if self.stop_event.is_set():
            raise CancelledError("Stop requested")
        stem = patched.name[:-len("_patched.xml")]
        generated = patched.with_name(f"{patched.stem}.tmc")
        target = patched.with_name(f"{stem}.tmc")
        if generated.exists():
            generated.unlink()

        command = [
            self.fdb_var.get(), "compress", "-f", str(patched), "-c", "3",
            "-i", self.tmc_format_var.get(), "-o", ".tmc", "-y",
        ]
        self._event("log_pack", f"> {subprocess.list2cmdline([str(x) for x in command])}\n")
        startupinfo = None
        flags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            flags = subprocess.CREATE_NO_WINDOW
        process = subprocess.Popen(
            [str(x) for x in command], cwd=str(patched.parent),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            encoding="utf-8", errors="replace", startupinfo=startupinfo,
            creationflags=flags,
        )
        assert process.stdout
        try:
            for line in process.stdout:
                self._event("log_pack", line)
                if self.stop_event.is_set():
                    process.kill()
                    raise CancelledError("Stop requested")
            code = process.wait()
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        if self.stop_event.is_set():
            raise CancelledError("Stop requested")
        if code != 0:
            raise RuntimeError(
                f"TMC compression failed for {patched.name} with exit code {code}."
            )
        if not generated.is_file() or generated.stat().st_size == 0:
            raise RuntimeError(f"No valid TMC file was created from {patched.name}.")
        if self.backup_var.get() and target.exists():
            self._backup(target)
        self._rename_replace(generated, target)
        return patched

    def _pack_tmc_files(self, data_dir: Path):
        """Compress changed TMC XML files in parallel and install each result atomically."""
        selected_meshes = Path(self.tmc_data_meshes_var.get().strip())
        if not selected_meshes.is_dir():
            self._event("log_pack", "No valid Meshes folder selected; TMC packing skipped.\n")
            return
        patched_files = sorted(
            (path for path in selected_meshes.rglob("*_patched.xml") if path.is_file()),
            key=lambda path: str(path).casefold(),
        )
        total = len(patched_files)
        self._event(
            "log_pack",
            f"Searching changed TMC XML recursively in: {selected_meshes}\n"
            f"Patched XML files found: {total}\n",
        )
        if not patched_files:
            self._event("log_pack", "No changed TMC files found; existing .tmc files remain unchanged.\n")
            return
        try:
            workers = int(self.tmc_parallel_var.get().strip())
        except (TypeError, ValueError):
            workers = 4
        workers = max(1, min(workers, 32, total))
        self._event(
            "log_pack",
            f"Starting TMC packing with {workers} parallel worker(s).\n",
        )
        packed = 0
        errors = []
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="PackTMC") as executor:
            jobs = {executor.submit(self._pack_one_tmc_file, path): path for path in patched_files}
            for job in as_completed(jobs):
                patched = jobs[job]
                if self.stop_event.is_set():
                    for pending in jobs:
                        pending.cancel()
                    raise CancelledError("Stop requested")
                try:
                    job.result()
                    packed += 1
                    self._event(
                        "log_pack",
                        f"TMC {packed}/{total} packed: {patched.relative_to(selected_meshes)}\n",
                    )
                except CancelledError:
                    raise
                except Exception as exc:
                    errors.append(f"{patched}: {exc}")
        if errors:
            raise RuntimeError(
                f"TMC packing failed for {len(errors)} file(s):\n" + "\n".join(errors[:20])
            )
        self._event("log_pack", f"TMC packing completed: {packed} changed TMC file(s).\n")

    def _compress_data(self, source: Path, format_file: str, cwd: Path, mode: str) -> Path:
        """Compress XML to FileDB .data using the same command style as pack_island.txt."""
        source = Path(source)
        cwd = Path(cwd)

        # FileDBReader uses the input stem for its output. Remove only the output
        # corresponding to this XML so a stale file can never be mistaken for a
        # successful conversion.
        expected = cwd / f"{source.stem}.data"
        if expected.exists():
            expected.unlink()

        started = time.time()
        self._run([
            self.fdb_var.get(), "compress", "-f", str(source),
            "-i", format_file, "-c", "3", "-y", "-o", "data",
        ], cwd, mode)

        if expected.is_file() and expected.stat().st_size > 0:
            return expected

        # Version-tolerant fallback: accept only a fresh .data generated by this run.
        candidates = sorted(
            (item for item in cwd.glob("*.data")
             if item.is_file() and item.stat().st_size > 0
             and item.stat().st_mtime >= started - 2.0),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
        preferred = [item for item in candidates if item.stem.lower() == source.stem.lower()]
        result = preferred[0] if preferred else (candidates[0] if len(candidates) == 1 else None)
        if result is None:
            raise RuntimeError(
                f"FileDBReader did not create a valid DATA file from {source.name}."
            )
        return result

    def _compress_a7minfo(self, source: Path, cwd: Path, mode: str) -> Path:
        self._run([
            self.fdb_var.get(), "compress", "-f", str(source), "-o", "a7minfo",
            "-i", self.a7minfo_format_var.get(), "-c", "3", "-y"
        ], cwd, mode)
        expected = cwd / f"{source.stem}.a7minfo"
        if expected.is_file() and expected.stat().st_size > 0:
            return expected
        candidates = sorted(cwd.glob("*.a7minfo"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            raise RuntimeError("FileDBReader did not create an A7MINFO file.")
        return candidates[0]

    def _install_binary(self, source: Path, destination: Path):
        if source.resolve() == destination.resolve():
            return
        if self.backup_var.get() and destination.exists():
            self._backup(destination)
        self._rename_replace(source, destination)

    def _backup(self, path: Path):
        backup = path.with_name(f"{path.stem}_original{path.suffix}")
        if backup.exists():
            stamp = time.strftime("%Y%m%d_%H%M%S")
            backup = path.with_name(f"{path.stem}_backup_{stamp}{path.suffix}")
        shutil.copy2(path, backup)
        self._event("log_pack", f"Backup: {backup.name}\n")

    def _run(self, command: list[str], cwd: Path, mode: str, minimize_console: bool = False):
        if self.stop_event.is_set():
            raise CancelledError("Stop requested")
        self._event(f"log_{mode}", f"> {subprocess.list2cmdline([str(x) for x in command])}\n")
        startupinfo = None
        flags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            flags = subprocess.CREATE_NO_WINDOW
        # RdaConsole calls Console.Clear() after extraction. If stdout is redirected
        # to a PIPE, Windows gives it a pipe handle instead of a real console screen
        # buffer and RdaConsole can crash with "The handle is invalid".
        # Therefore RdaConsole is executed without redirected stdout/stderr.
        is_rda_console = Path(str(command[0])).name.lower() == "rdaconsole.exe"
        if is_rda_console and os.name == "nt":
            flags = subprocess.CREATE_NEW_CONSOLE
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 2 if minimize_console else 1  # SW_SHOWMINIMIZED / SW_SHOWNORMAL
            self._event(
                f"log_{mode}",
                "RdaConsole runs in a real console window"
                + (" (minimized).\n" if minimize_console else ".\n"),
            )
            self.process = subprocess.Popen(
                [str(x) for x in command],
                cwd=str(cwd),
                startupinfo=startupinfo,
                creationflags=flags,
            )
            code = self.process.wait()
            self.process = None
            if self.stop_event.is_set():
                raise CancelledError("Stop requested")
            if code != 0:
                raise RuntimeError(f"RdaConsole wurde mit Exitcode {code} beendet.")
            return

        self.process = subprocess.Popen(
            [str(x) for x in command], cwd=str(cwd), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            startupinfo=startupinfo, creationflags=flags,
        )
        assert self.process.stdout
        for line in self.process.stdout:
            self._event(f"log_{mode}", line)
            if self.stop_event.is_set():
                self._kill_process()
                raise CancelledError("Stop requested")
        code = self.process.wait()
        self.process = None
        if self.stop_event.is_set():
            raise CancelledError("Stop requested")
        if code != 0:
            raise RuntimeError(f"Prozess wurde mit Exitcode {code} beendet.")

    def _resolve_island(self, selected: Path):
        if selected.is_file() and selected.suffix.lower() == ".a7m":
            root = selected.parent
            a7m = selected
            data_dir = root / selected.stem
        elif selected.is_dir():
            if (selected.parent / f"{selected.name}.a7m").is_file():
                data_dir = selected
                root = selected.parent
                a7m = root / f"{selected.name}.a7m"
            else:
                a7ms = list(selected.glob("*.a7m"))
                if len(a7ms) != 1:
                    raise ValueError("The selected folder must contain exactly one .a7m file, or it must be the data folder next to an .a7m file with the same name.")
                root = selected
                a7m = a7ms[0]
                data_dir = root / a7m.stem
        else:
            raise ValueError("Please select an existing .a7m file or island folder.")
        if not data_dir.is_dir():
            raise ValueError(f"The unpacked data folder was not found:\n{data_dir}")
        return root, a7m, data_dir

    @staticmethod
    def _find_data_file(root: Path, name: str):
        direct = root / name
        if direct.is_file():
            return direct
        matches = list(root.rglob(name))
        return matches[0] if matches else None

    @staticmethod
    def _locate_generated_xml(cwd: Path, source: Path, preferred_stem: str):
        expected = cwd / f"{source.stem}.xml"
        if expected.is_file():
            return expected
        preferred = cwd / f"{preferred_stem}.xml"
        if preferred.is_file():
            return preferred
        candidates = sorted(cwd.glob("*.xml"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            raise RuntimeError(f"No generated XML file was found for {source.name} found.")
        return candidates[0]

    @staticmethod
    def _rename_replace(source: Path, destination: Path):
        if destination.exists() and source.resolve() != destination.resolve():
            destination.unlink()
        if source.resolve() != destination.resolve():
            source.replace(destination)

    def _validate_settings(self):
        values = [
            ("RdaConsole.exe", self.rda_var.get()),
            ("FileDBReader.exe", self.fdb_var.get()),
            ("Bundled Island_Gamedata XML", BUNDLED_XML_FORMATS["gamedata"]),
            ("Bundled Island_RD3D XML", BUNDLED_XML_FORMATS["rd3d"]),
            ("Bundled a7minfo.xml", BUNDLED_XML_FORMATS["a7minfo"]),
            ("Bundled tmc.xml", BUNDLED_XML_FORMATS["tmc"]),
        ]
        return [f"{name}: not found ({value or 'no path'})" for name, value in values if not Path(value).is_file()]

    def _validate_settings_dialog(self):
        errors = self._validate_settings()
        if errors:
            self._show_settings_errors(errors)
        else:
            messagebox.showinfo("Settings", "All required programs and bundled XML formats are available.")

    def _show_settings_errors(self, errors):
        self.tabs.set("Settings")
        messagebox.showerror("Settings incomplete", "Please correct the following paths:\n\n" + "\n".join(errors))

    def _ask_worker_yes_no(self, title, text):
        response = queue.Queue(maxsize=1)
        self._event("ask_yes_no", (title, text, response))
        return response.get()

    def _event(self, kind, value):
        self.events.put((kind, value))

    def _poll(self):
        # Schedule the next queue check first. A failed optional view refresh can
        # no longer prevent the queued completion event from being processed.
        self.after(100, self._poll)
        # Never drain an unlimited number of worker events in one Tk callback.
        # A bounded batch keeps window dragging, painting and input responsive.
        max_events_per_poll = 50
        processed_events = 0

        while processed_events < max_events_per_poll:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break

            processed_events += 1

            if kind == "log_start_colored":
                text, color = value
                self._write_colored(self.start_log, str(text), str(color), auto_scroll=True)
            elif kind == "log_finalize_colored":
                text, color = value
                self._write_colored(self.finalize_log, str(text), str(color), auto_scroll=True)
            elif kind == "log_start":
                self._write(self.start_log, str(value), auto_scroll=True)
            elif kind == "log_finalize":
                self._write(self.finalize_log, str(value), auto_scroll=True)
            elif kind == "log_exports":
                self._write(self.exports_log, str(value), auto_scroll=True)
            elif kind == "progress_start":
                self.start_progress.set(float(value))
            elif kind == "progress_finalize":
                self.finalize_progress.set(float(value))
            elif kind == "progress_exports":
                self.exports_progress.set(float(value))
            elif kind == "status":
                self.status_var.set(str(value))
            elif kind == "gamedata_ready":
                self.gamedata_file_var.set(str(value))
                self._load_gamedata_xml(show_errors=False)
                self._refresh_slot_configuration_from_files()
            elif kind == "mapname_ready":
                self.mapname_file_var.set(str(value))
            elif kind == "files_folders_ready":
                try:
                    self._refresh_files_and_folders_from_map(Path(str(value)))
                except Exception as exc:
                    self._write(
                        self.start_log,
                        f"\nWARNING: Files and Folders were set, but an optional view refresh failed: {exc}\n",
                        auto_scroll=True,
                    )
                    self.status_var.set(f"Files and Folders refreshed with warning: {exc}")
            elif kind == "tmc_meshes_ready":
                self.tmc_data_meshes_var.set(str(value))
                self._load_tmc_data(show_errors=False)
            elif kind == "rd3d_ready":
                self.rd3d_file_var.set(str(value))
                self._load_rd3d_xml(show_errors=False)
            elif kind == "ask_yes_no":
                title, text, response = value
                response.put(messagebox.askyesno(title, text))
            elif kind == "export_map_success":
                self._last_export_map_destination = Path(str(value))
            elif kind == "done":
                mode, ok, stopped = value
                try:
                    self._set_running(False, mode)
                finally:
                    # Do not let a later status/log/messagebox error leave the
                    # Finalize actions disabled after Unpack, Pack or Export.
                    self._configure_widget_state(getattr(self, "finalize_btn", None), "normal")
                    self._configure_widget_state(getattr(self, "finalize_cleanup_btn", None), "normal")
                # Scroll once after the operation instead of once for every line.
                log_widget = {
                    "start": self.start_log,
                    "finalize": self.finalize_log,
                    "exports": self.exports_log,
                }.get(mode)
                if log_widget is not None:
                    log_widget.see("end")
                if stopped:
                    self.status_var.set("Cancelled")
                elif ok:
                    if mode == "start":
                        self._configure_widget_state(getattr(self, "start_btn", None), "normal")
                        self._configure_widget_state(getattr(self, "start_stop_btn", None), "disabled")
                        self._configure_widget_state(getattr(self, "finalize_btn", None), "normal")
                        self._configure_widget_state(getattr(self, "finalize_cleanup_btn", None), "normal")
                        self.status_var.set("Unpacking completed successfully")
                        messagebox.showinfo(
                            "Start",
                            "Unpacking completed successfully.\n\n"
                            "Files and folders were refreshed. Start and Finalize are ready.",
                        )
                    else:
                        self.status_var.set("Done")
                        export_destination = getattr(self, "_last_export_map_destination", None)
                        if mode == "finalize" and export_destination is not None:
                            self._last_export_map_destination = None
                            if messagebox.askyesno(
                                "Export Map",
                                "Map exported successfully.\n\nOpen folder?\n\n"
                                f"{export_destination}",
                            ):
                                try:
                                    os.startfile(str(export_destination))
                                except OSError as exc:
                                    messagebox.showerror(
                                        "Export Map",
                                        f"The export folder could not be opened:\n{export_destination}\n\n{exc}",
                                    )
                        else:
                            messagebox.showinfo("Done", "Operation completed successfully.")
                else:
                    self.status_var.set("Error. Details siehe Log.")
                    messagebox.showerror("Error", "The operation failed. See the log for details.")


    @staticmethod
    def _write(widget, text, auto_scroll=True):
        widget.configure(state="normal")
        widget.insert("end", text)
        if auto_scroll:
            widget.see("end")
        widget.configure(state="disabled")

    @staticmethod
    def _write_colored(widget, text, color, auto_scroll=True):
        widget.configure(state="normal")
        tag_name = f"log_color_{str(color).replace('#', '')}"
        widget.tag_config(tag_name, foreground=color)
        widget.insert("end", text, tag_name)
        if auto_scroll:
            widget.see("end")
        widget.configure(state="disabled")

    @staticmethod
    def _clear_log(widget):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.configure(state="disabled")

    def _busy(self):
        if self._tmc_ram_is_busy():
            messagebox.showwarning("XML cache", "XML loading or saving is in progress. Editing remains available; conflicting file operations are blocked.")
            return True
        if self.worker and self.worker.is_alive():
            messagebox.showwarning("Operation in progress", "Please stop the running operation first.")
            return True
        return False

    @staticmethod
    def _configure_widget_state(widget, state):
        """Best-effort widget state update without aborting the whole UI reset."""
        if widget is None:
            return
        try:
            if hasattr(widget, "winfo_exists") and not widget.winfo_exists():
                return
            widget.configure(state=state)
        except (tk.TclError, AttributeError, RuntimeError):
            # A tab may have been removed or a popup/widget may already be gone.
            # Remaining controls still have to be restored.
            return

    def _set_running(self, running: bool, mode: str):
        state = "disabled" if running else "normal"
        action_widgets = [
            getattr(self, "start_btn", None),
            getattr(self, "finalize_btn", None),
            getattr(self, "finalize_cleanup_btn", None),
            getattr(self, "finalize_export_material_btn", None),
            getattr(self, "finalize_export_map_btn", None),
            getattr(self, "exports_material_btn", None),
        ]
        action_widgets.extend(getattr(self, "exports_island_buttons", ()))
        action_widgets.extend(getattr(self, "exports_island_entries", ()))
        for widget in action_widgets:
            self._configure_widget_state(widget, state)

        stops = {
            "start": getattr(self, "start_stop_btn", None),
            "finalize": getattr(self, "finalize_stop_btn", None),
            "exports": getattr(self, "exports_stop_btn", None),
        }
        for stop_mode, button in stops.items():
            stop_state = "normal" if running and stop_mode == mode else "disabled"
            self._configure_widget_state(button, stop_state)

        # Explicit final safeguard requested for Finalize: after every completed
        # operation, both Finalize actions are guaranteed to return to normal.
        if not running:
            self._configure_widget_state(getattr(self, "finalize_btn", None), "normal")
            self._configure_widget_state(getattr(self, "finalize_cleanup_btn", None), "normal")

    def _stop(self):
        self.stop_event.set()
        self.status_var.set("Cancelling...")
        self._kill_process()
        with self.parallel_processes_lock:
            processes = list(self.parallel_processes)
        for process in processes:
            self._kill_specific_process(process)

    def _kill_process(self):
        process = self.process
        if not process or process.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                process.kill()
        except OSError:
            pass

    def _load_config(self):
        config = configparser.ConfigParser(interpolation=None)
        try:
            if not CONFIG_FILE.exists():
                return
            config.read(CONFIG_FILE, encoding="utf-8")
            paths = config["Paths"] if config.has_section("Paths") else {}
            options = config["Options"] if config.has_section("Options") else {}
            self.rda_var.set(paths.get("rda_console", ""))
            self.fdb_var.set(paths.get("file_db_reader", ""))
            self.gamefiles_var.set(paths.get("gamefiles", ""))
            self.island_export_custom_var.set(paths.get("island_export_custom", ""))
            self.original_maps_var.set(paths.get("original_maps", ""))
            self.default_custom_maps_var.set(paths.get("temporary_map_folder", paths.get("default_custom_maps", "")))
            self.custom_map_folder_var.set(paths.get("custom_map_folder", ""))
            self.map_export_folder_var.set(paths.get("map_export_folder", ""))
            self.custom_material_sets_folder_var.set(paths.get("custom_material_sets_folder", ""))
            self.custom_objects_folder_var.set(paths.get("custom_objects_folder", ""))
            self.unpack_a7minfo_var.set(config.getboolean("Options", "unpack_a7minfo", fallback=True))
            self.unpack_gamedata_var.set(config.getboolean("Options", "unpack_gamedata", fallback=True))
            self.unpack_rd3d_var.set(config.getboolean("Options", "unpack_rd3d", fallback=True))
            self.unpack_tmc_var.set(config.getboolean("Options", "unpack_tmc", fallback=True))
            self.backup_var.set(config.getboolean("Options", "backup", fallback=True))
            self.tmc_parallel_var.set(str(config.getint("Options", "tmc_parallel_processes", fallback=4)))
        except (OSError, configparser.Error, ValueError) as exc:
            messagebox.showwarning("Configuration", f"config.ini could not be loaded:\n{exc}")

    def _save_config(self):
        config = configparser.ConfigParser(interpolation=None)
        config["Paths"] = {
            "rda_console": self.rda_var.get().strip(),
            "file_db_reader": self.fdb_var.get().strip(),
            "gamefiles": self.gamefiles_var.get().strip(),
            "island_export_custom": self.island_export_custom_var.get().strip(),
            "original_maps": self.original_maps_var.get().strip(),
            "default_custom_maps": self.default_custom_maps_var.get().strip(),
            "temporary_map_folder": self.default_custom_maps_var.get().strip(),
            "custom_map_folder": self.custom_map_folder_var.get().strip(),
            "map_export_folder": self.map_export_folder_var.get().strip(),
            "custom_material_sets_folder": self.custom_material_sets_folder_var.get().strip(),
            "custom_objects_folder": self.custom_objects_folder_var.get().strip(),
        }
        config["Options"] = {
            "unpack_a7minfo": str(self.unpack_a7minfo_var.get()),
            "unpack_gamedata": str(self.unpack_gamedata_var.get()),
            "unpack_rd3d": str(self.unpack_rd3d_var.get()),
            "unpack_tmc": str(self.unpack_tmc_var.get()),
            "backup": str(self.backup_var.get()),
            "tmc_parallel_processes": self.tmc_parallel_var.get().strip() or "4",
        }
        try:
            with CONFIG_FILE.open("w", encoding="utf-8") as handle:
                config.write(handle)
            return True
        except OSError as exc:
            messagebox.showerror("Configuration", f"config.ini could not be saved:\n{exc}")
            return False

    def _save_config_with_feedback(self):
        if self._save_config():
            self.status_var.set("Settings saved")

    def _close(self):
        if self._tmc_ram_is_busy():
            messagebox.showwarning("XML cache", "Finish the XML load/save operation before closing the application.")
            return
        if self.rd3d_database_window is not None and self.rd3d_database_window.winfo_exists():
            self._close_rd3d_database_window()
        if self.rd3d_objects_window is not None and self.rd3d_objects_window.winfo_exists():
            self._close_rd3d_objects_window()
        if self.rd3d_map_window is not None and self.rd3d_map_window.winfo_exists():
            self._close_rd3d_map_window()
        slot_map_window = getattr(self, "slot_map_window", None)
        if slot_map_window is not None and slot_map_window.winfo_exists():
            self._close_slot_map()
        object_map_window = getattr(self, "object_configuration_map_window", None)
        if object_map_window is not None and object_map_window.winfo_exists():
            self._close_object_configuration_map()
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Exit", "Cancel the running operation and exit the program?"):
                return
            self._stop()
        self._save_config()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
