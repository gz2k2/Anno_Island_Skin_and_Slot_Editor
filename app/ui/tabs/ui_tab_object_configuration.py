from __future__ import annotations

from app.functions.function_custom_content import (
    get_combined_categories,
    get_combined_category_rows,
    get_combined_object_database,
    get_combined_regions,
    get_category_for_object,
    get_regions_for_category,
    get_regions_for_object,
    display_category,
    display_regions,
)

from concurrent.futures import ThreadPoolExecutor, as_completed
import random
import math
import json
import shutil
import copy
import hashlib
import os
import queue
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
import app.backend.xml_backend as ET
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

from app.config.config_rd3d import (
    DEFAULT_RD3D_CATEGORY,
    RD3D_CATEGORIES,
    rd3d_category_for_object,
    rd3d_regions_for_category,
)
from app.database.database_props import RD3D_OBJECT_DATABASE
from app.config.config_colors import TYPE_CATEGORY_COLOR_FAMILIES, TYPE_CATEGORY_COLORS, DEFAULT_TYPE_COLOR
from app.functions.function_map_selection import MapSelectionMixin
from app.functions.function_place_object import PlaceObjectMixin, ObjectMapSession, world_from_click
from app.functions.function_density import DensitySession
from app.templates.template_map_view import MapViewTemplate
from app.templates.template_profiles import ProfilesTemplate, ProfileArchiveStore
from app.templates.template_popup import PopupTemplate
from app.templates.template_statuswindow import StatusWindowTemplate
from app.templates.template_category_picker import CategoryPickerTemplate
from app.templates.template_table import TemplateTable, TableColumn, RD3D_OBJECT_COLUMNS, build_rd3d_style_row
from app.templates.template_treeview import TreeviewTemplate

# -----------------------------------------------------------------------------
# Object Map dot Level of Detail (LOD)
# -----------------------------------------------------------------------------
# Edit these values to tune dot grouping without changing the render function.
# Pixel values are screen-space cell sizes. Objects of the same Category inside
# one cell are rendered once. Hit testing and XML data still use all objects.
# Keep zoom limits ascending and pixel values >= 1.
OBJECT_MAP_LOD_FAR_ZOOM_LIMIT = 2.0
OBJECT_MAP_LOD_MID_ZOOM_LIMIT = 3.0
OBJECT_MAP_LOD_FAR_PIXELS = 4
OBJECT_MAP_LOD_MID_PIXELS = 2
OBJECT_MAP_LOD_NEAR_PIXELS = 1


def object_map_lod_pixels(zoom):
    """Return the configured Object Map LOD cell size for one zoom value."""
    if zoom < OBJECT_MAP_LOD_FAR_ZOOM_LIMIT:
        return max(1, int(OBJECT_MAP_LOD_FAR_PIXELS))
    if zoom < OBJECT_MAP_LOD_MID_ZOOM_LIMIT:
        return max(1, int(OBJECT_MAP_LOD_MID_PIXELS))
    return max(1, int(OBJECT_MAP_LOD_NEAR_PIXELS))


# Object Table 1/2 use localized display titles while preserving the shared
# column keys, widths, alignment, colors, and row behavior.
_OBJECT_TABLE_COLUMN_TITLES = {"Type": "Category", "Path": "Object"}
OBJECT_TABLE_COLUMNS = tuple(
    TableColumn(
        key=column.key,
        title=_OBJECT_TABLE_COLUMN_TITLES.get(column.title, column.title),
        width=column.width,
        weight=column.weight,
        anchor=column.anchor,
        text_color=column.text_color,
    )
    for column in RD3D_OBJECT_COLUMNS
)


class TmcXmlRamCache:
    """Session-scoped XML documents; no Tk calls and no I/O during editing."""

    def __init__(self, folder, workers=4):
        self.folder = Path(folder)
        self.workers = max(1, min(int(workers or 1), 32))
        self.documents = {}
        self.groups = []
        self.errors = []

    @staticmethod
    def _entries(tree):
        entries = []
        tag = lambda n: n.tag.rsplit('}', 1)[-1].lower() if isinstance(n.tag, str) else ''
        for ground in tree.getroot().iter():
            if tag(ground) != 'groundobjects':
                continue
            for entry in ground:
                oid = next((n for n in entry if tag(n) == 'id'), None)
                filename = next((n for n in entry if tag(n) == 'filename'), None)
                if oid is not None and filename is not None:
                    entries.append(((oid.text or '').strip(), filename))
        return entries

    @staticmethod
    def _parse(path):
        return ET.parse(path, parser=ET.XMLParser(
            target=ET.TreeBuilder(insert_comments=True, insert_pis=True)))

    def load(self, progress):
        """Read TMC original/patched XML pairs strictly sequentially."""
        progress(0, 0)
        paths = sorted(self.folder.rglob('*_original.xml'), key=lambda p: str(p).casefold())
        total = len(paths)
        progress(0, total)
        grouped = {}
        for index, original in enumerate(paths, 1):
            try:
                baseline = self._parse(original)
                patched = original.with_name(
                    original.name[:-len('_original.xml')] + '_patched.xml'
                )
                working = self._parse(patched) if patched.is_file() else copy.deepcopy(baseline)
                before, current = self._entries(baseline), self._entries(working)
                # Patched TMC files may contain fewer GroundObjects after Density
                # deletion. Objects Table 2 therefore indexes the current working
                # entries instead of requiring a one-to-one original count.
                self.documents[original] = {
                    'original': baseline, 'working': working, 'target': patched,
                }
                for ordinal, (oid, current_name) in enumerate(current):
                    current_text = current_name.text or ''
                    key = (oid, current_text, current_text)
                    grouped.setdefault(key, []).append((original, ordinal))
            except (OSError, ET.ParseError, ValueError, UnicodeError) as exc:
                self.errors.append(f'{original}: {exc}')
            progress(index, total)
        self.groups = [
            (oid, old, current, refs)
            for (oid, old, current), refs in grouped.items()
        ]
        return self

    def save(self, values, progress):
        if len(values) != len(self.groups):
            raise ValueError('Cache/table row count mismatch')
        edits = {}
        for value, (_, _, _, refs) in zip(values, self.groups):
            for path, ordinal in refs:
                edits.setdefault(path, {})[ordinal] = value
        saved = changed = 0
        errors = []
        paths = list(edits)
        for index, path in enumerate(paths, 1):
            record = self.documents[path]
            temporary = None
            try:
                tree = copy.deepcopy(record['working'])
                entries = self._entries(tree)
                count = 0
                for ordinal, value in edits[path].items():
                    node = entries[ordinal][1]
                    if (node.text or '') != value:
                        node.text = value
                        count += 1
                if count:
                    fd, name = tempfile.mkstemp(prefix='.tmc_patch_', suffix='.xml', dir=path.parent)
                    os.close(fd)
                    temporary = Path(name)
                    tree.write(temporary, encoding='utf-8', xml_declaration=False, short_empty_elements=True)
                    # Validate/reload before replacing the destination. A parse
                    # failure leaves the previous patched file untouched.
                    reloaded = self._parse(temporary)
                    os.replace(temporary, record['target'])
                    record['working'] = reloaded
                    saved += 1
                    changed += count
            except (OSError, ET.ParseError, ValueError) as exc:
                errors.append(f'{path}: {exc}')
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            progress(index, len(paths))
        return saved, changed, errors


class Rd3dXmlRamCache:
    """RD3D original/working trees owned by the XML worker, never by Tk."""

    def __init__(self, original):
        self.path = Path(original)
        self.target = self.path.with_name('rd3d_patched.xml')

    @staticmethod
    def _names(tree):
        tag = lambda n: n.tag.rsplit('}', 1)[-1] if isinstance(n.tag, str) else ''
        grid = next((n for n in tree.getroot().iter() if tag(n) == 'PropGrid'), None)
        if grid is None:
            raise ValueError('PropGrid was not found.')
        names = next((n for n in grid if tag(n) == 'FileNames'), None)
        if names is None:
            raise ValueError('PropGrid/FileNames was not found.')
        return list(names), grid

    def _signature(self):
        try:
            return hashlib.sha256(self.target.read_bytes()).digest()
        except FileNotFoundError:
            return None

    def load(self, progress):
        progress(0, 3)
        self.original = TmcXmlRamCache._parse(self.path)
        progress(1, 3)
        self.signature = self._signature()
        self.working = TmcXmlRamCache._parse(self.target) if self.signature is not None else copy.deepcopy(self.original)
        if self._signature() != self.signature:
            raise ValueError('RD3D changed during loading. Please retry.')
        original_nodes, grid = self._names(self.original)
        current_nodes, grid = self._names(self.working)
        if len(original_nodes) > len(current_nodes):
            raise ValueError('Patched FileNames lost original indices. No files were changed.')
        self.original_values = [(n.text or '').strip() for n in original_nodes]
        self.original_values.extend((n.text or '').strip() for n in current_nodes[len(original_nodes):])
        self.values = [(n.text or '').strip() for n in current_nodes]
        self.usage = [0] * len(current_nodes)
        tag = lambda n: n.tag.rsplit('}', 1)[-1] if isinstance(n.tag, str) else ''
        instances = next((n for n in grid if tag(n) == 'Instances'), None)
        if instances is not None:
            for instance in instances:
                node = next((n for n in instance if tag(n) == 'Index'), None)
                try:
                    index = int(node.text or '') if node is not None else -1
                except ValueError:
                    continue
                if 0 <= index < len(self.usage):
                    self.usage[index] += 1
        progress(3, 3)
        return self

    def save(self, values, progress):
        if len(values) != len(self.values) or any(not v for v in values):
            raise ValueError('Invalid FileNames values/count.')
        # Other editors still write RD3D directly. Never overwrite their changes
        # with a stale cache: reload the cache explicitly after such a conflict.
        if self._signature() != self.signature:
            raise ValueError('rd3d_patched.xml changed outside Objects Table 1. '
                             'Use Reload Cache, then reapply your edits.')
        tree = copy.deepcopy(self.working)
        nodes, _ = self._names(tree)
        changed = sum(a != b for a, b in zip(self.values, values))
        if not changed:
            progress(3, 3)
            return 0
        for node, value in zip(nodes, values):
            node.text = value
        progress(1, 3)
        fd, name = tempfile.mkstemp(prefix='.rd3d_patch_', suffix='.xml', dir=self.path.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            tree.write(temporary, encoding='utf-8', xml_declaration=False, short_empty_elements=True)
            reloaded = TmcXmlRamCache._parse(temporary)
            signature = hashlib.sha256(temporary.read_bytes()).digest()
            progress(2, 3)
            if self._signature() != self.signature:
                raise ValueError('RD3D changed while saving. No cached edits were installed.')
            os.replace(temporary, self.target)
            self.working = reloaded
            self.values = list(values)
            self.signature = signature
        finally:
            temporary.unlink(missing_ok=True)
        progress(3, 3)
        return changed




class ObjectConfigurationTabMixin(MapSelectionMixin, PlaceObjectMixin):
    """Independent object-map implementation for the Object Configuration tab.

    The map intentionally owns separate state, parsing, drawing and event
    handlers. It does not call or reuse the existing rd3d.data map functions.
    """

    def _build_object_configuration_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        ctk.CTkLabel(
            header,
            text="Object Configuration",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(anchor="w")

        objects_1 = ctk.CTkFrame(tab)
        objects_1.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(
            objects_1,
            text="Objects (rd3d)",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 8))
        objects_1_buttons = ctk.CTkFrame(objects_1, fg_color="transparent")
        objects_1_buttons.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(
            objects_1_buttons, text="Objects Table (rd3d)", width=180, height=38,
            font=ctk.CTkFont(weight="bold"),
            command=self._open_object_configuration_table_1,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            objects_1_buttons, text="Show Object Map (rd3d)", width=180, height=38,
            font=ctk.CTkFont(weight="bold"),
            command=self._open_object_configuration_map,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            objects_1_buttons, text="Change Density (rd3d)", width=180, height=38,
            font=ctk.CTkFont(weight="bold"), command=self._open_object_density,
        ).pack(side="left")

        objects_2 = ctk.CTkFrame(tab)
        objects_2.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        ctk.CTkLabel(
            objects_2,
            text="Objects (tmc)",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 8))
        objects_2_buttons = ctk.CTkFrame(objects_2, fg_color="transparent")
        objects_2_buttons.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(
            objects_2_buttons, text="Objects Table (tmc)", width=180, height=38,
            font=ctk.CTkFont(weight="bold"),
            command=self._open_object_configuration_table_2,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            objects_2_buttons, text="Show Object Map (tmc)", width=180, height=38,
            font=ctk.CTkFont(weight="bold"),
            command=self._open_tmc_object_map,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            objects_2_buttons, text="Change Density (tmc)", width=180, height=38,
            font=ctk.CTkFont(weight="bold"),
            command=self._open_tmc_density,
        ).pack(side="left")

        self._tmc_ram_initialize(tab)
        self.object_configuration_table1_window = None
        self.object_configuration_table1_table = None
        self.object_configuration_table1_rows = []
        self.object_configuration_table1_info_var = tk.StringVar(value="Load rd3d_original.xml to display objects.")
        self.object_configuration_table1_replace_from_var = tk.StringVar()
        self.object_configuration_table1_replace_to_var = tk.StringVar()
        self.object_configuration_table1_replace_from_menu = None
        self.object_configuration_table1_replace_to_entry = None

        self.object_configuration_table2_window = None
        self.object_configuration_table2_table = None
        self.object_configuration_table2_rows = []
        self.object_configuration_table2_info_var = tk.StringVar(value="Select the Meshes folder to display TMC GroundObjects.")
        self.object_configuration_table2_replace_from_var = tk.StringVar()
        self.object_configuration_table2_replace_to_var = tk.StringVar()
        self.object_configuration_table2_replace_from_menu = None
        self.object_configuration_table2_replace_to_entry = None

        self.object_configuration_map_window = None
        self.object_configuration_map_canvas = None
        self.object_configuration_map_legend = None
        self.object_configuration_map_points = []
        self.object_configuration_map_screen_points = []
        self.object_configuration_map_file_names = []
        self.object_configuration_map_category_colors = {}
        self.object_configuration_map_category_visible = {}
        self.object_configuration_map_category_buttons = {}
        self.object_configuration_map_hover_point = None
        self.object_configuration_map_after_id = None
        self.object_configuration_map_pan_start = None
        self.object_configuration_map_zoom = MapViewTemplate.DEFAULT_POINT_ZOOM
        self.object_configuration_map_pan_x = 0.0
        self.object_configuration_map_pan_y = 0.0
        self.object_configuration_map_shared_zoom = MapViewTemplate.DEFAULT_SHARED_ZOOM
        self.object_configuration_map_shared_pan_x = 0.0
        self.object_configuration_map_shared_pan_y = 0.0
        self.object_configuration_map_image_source = None
        self.object_configuration_map_image_tk = None
        self.object_configuration_map_image_cache = {}
        self.object_configuration_map_hover_item = None
        # Object Map rendering indexes. All XML/RAM points remain intact; these
        # structures only accelerate viewport rendering and hit testing.
        self.object_configuration_map_world_grid = {}
        self.object_configuration_map_world_grid_signature = None
        self.object_configuration_map_world_cell_size = 16.0
        self.object_configuration_map_screen_grid = {}
        self.object_configuration_map_screen_cell_size = 16
        self.object_configuration_map_dot_image = None
        self.object_configuration_map_dot_photo = None
        self.object_configuration_map_rendered_count = 0
        self.object_configuration_map_redraw_generation = 0
        self.object_configuration_map_info_var = tk.StringVar(
            value="Load rd3d_original.xml to display object instances."
        )
        self.object_configuration_map_selection_var = tk.StringVar(
            value="Hover or click a point to display its index, prop and position."
        )
        self.object_configuration_map_allow_dot_movement_var = tk.BooleanVar(value=False)

    def _show_object_operation_status(self, text="Loading..."):
        """Display the shared themed status popup."""
        return StatusWindowTemplate.create(
            self, text=text, title="Status", heading="Status",
            modal=True, topmost=True,
        )

    @staticmethod
    def _hide_object_operation_status(popup):
        StatusWindowTemplate.close(popup)


    def _rd3d_table1_has_unsaved_changes(self):
        cache = getattr(self, "rd3d_ram_cache", None)
        rows = getattr(self, "object_configuration_table1_rows", [])
        if cache is None or not rows or len(rows) != len(cache.values):
            return False
        return any(
            variable.get().strip() != str(cache.values[index]).strip()
            for index, (_row_index, _original, variable, _count) in enumerate(rows)
        )

    def _rd3d_has_unsaved_work(self):
        session = getattr(self, "_map_edit_session", None)
        return bool(
            (session is not None and getattr(session, "dirty", False))
            or self._rd3d_table1_has_unsaved_changes()
        )

    def _rd3d_discard_working_copy(self, clear_cache=True):
        """Discard RD3D/Object Map/Table 1/Density RAM only. TMC is untouched."""
        self._map_edit_session = None
        self._density_session = None
        self._density_cache = None
        rows = getattr(self, "object_configuration_table1_rows", [])
        cache = getattr(self, "rd3d_ram_cache", None)
        if cache is not None and len(rows) == len(cache.values):
            for index, (_row_index, _original, variable, _count) in enumerate(rows):
                variable.set(str(cache.values[index]))
        self.object_configuration_map_points = []
        self.object_configuration_map_screen_points = []
        self.object_configuration_map_file_names = []
        self.object_configuration_map_world_grid = {}
        self.object_configuration_map_world_grid_signature = None
        self.object_configuration_map_screen_grid = {}
        self.object_configuration_map_hover_point = None
        self.object_configuration_map_image_source = None
        self.object_configuration_map_image_tk = None
        self.object_configuration_map_image_cache = {}
        self.object_configuration_map_dot_image = None
        self.object_configuration_map_dot_photo = None
        self.object_configuration_map_rendered_count = 0
        if clear_cache:
            self.rd3d_ram_cache = None
            self.object_configuration_table1_rows = []
        return True

    def _open_object_configuration_table_1(self):
        # Keep the user intent while RD3D is loaded asynchronously. The completion
        # handler will continue opening the table, so a second click is unnecessary.
        self._object_table1_open_pending = True
        status = self._show_object_operation_status("Loading...")
        try:
            opened = self._open_object_configuration_table_1_impl()
            self.update_idletasks()
            window = getattr(self, "object_configuration_table1_window", None)
            if window is not None and window.winfo_exists():
                self._object_table1_open_pending = False
                window.update_idletasks()
                window.lift()
            return opened
        finally:
            self._hide_object_operation_status(status)

    def _open_object_configuration_table_1_impl(self):
        if not self._load_object_configuration_table_1_data():
            return False
        if self.object_configuration_table1_window is not None and self.object_configuration_table1_window.winfo_exists():
            self.object_configuration_table1_window.deiconify(); PopupTemplate.safe_activate(self.object_configuration_table1_window); self._render_object_configuration_table_1(); return True
        built=PopupTemplate.create_window(self,title="Objects Table 1",heading="Objects Table 1",close_command=self._close_object_configuration_table_1)
        window=built["window"]; self.object_configuration_table1_window=window
        window.grid_columnconfigure(0,weight=1); window.grid_rowconfigure(3,weight=1)
        ctk.CTkLabel(window,textvariable=self.object_configuration_table1_info_var,text_color=PopupTemplate.SECONDARY_TEXT_COLOR).grid(row=1,column=0,padx=PopupTemplate.HEADER_PADX,pady=(0,8),sticky="w")
        bar=ctk.CTkFrame(window); bar.grid(row=2,column=0,padx=PopupTemplate.HEADER_PADX,pady=(0,10),sticky="ew"); bar.grid_columnconfigure(1,weight=1); bar.grid_columnconfigure(3,weight=1)
        self._build_object_profiles(bar, 1)
        ctk.CTkButton(
            bar,
            text="Mass Replace",
            width=PopupTemplate.BUTTON_WIDTH,
            height=PopupTemplate.BUTTON_HEIGHT,
            command=lambda: self._open_object_mass_replace_popup(1),
        ).grid(row=1, column=0, padx=12, pady=(10, 10), sticky="w")
        self._build_object_configuration_treeview(window, 1)
        actions=ctk.CTkFrame(window,fg_color="transparent"); actions.grid(row=5,column=0,padx=PopupTemplate.HEADER_PADX,pady=(0,16),sticky="ew"); actions.grid_columnconfigure(0,weight=1)
        ctk.CTkButton(actions,text="Reset",width=PopupTemplate.BUTTON_WIDTH,height=PopupTemplate.BUTTON_HEIGHT,fg_color=PopupTemplate.DANGER_BUTTON_FG_COLOR,hover_color=PopupTemplate.DANGER_BUTTON_HOVER_COLOR,command=self._reset_object_configuration_table_1).grid(row=0,column=1,padx=(0,8),sticky="e")
        ctk.CTkButton(actions,text="Save",width=PopupTemplate.BUTTON_WIDTH,height=PopupTemplate.BUTTON_HEIGHT,font=ctk.CTkFont(size=PopupTemplate.BUTTON_FONT_SIZE,weight="bold"),command=self._save_object_configuration_table_1).grid(row=0,column=2,sticky="e")
        self._render_object_configuration_table_1()
        return True

    def _close_object_configuration_table_1(self):
        self._object_table1_open_pending = False
        window = self.object_configuration_table1_window
        if self._rd3d_table1_has_unsaved_changes():
            if not messagebox.askyesno(
                "Objects Table 1",
                "Objects Table 1 contains unsaved RD3D path changes.\n\n"
                "Closing this popup will discard those table changes from RAM.\n\n"
                "Close and discard the unsaved changes?",
                parent=window,
                default="no",
            ):
                return
            cache = self.rd3d_ram_cache
            if cache is not None and len(self.object_configuration_table1_rows) == len(cache.values):
                for index, (_row_index, _original, variable, _count) in enumerate(self.object_configuration_table1_rows):
                    variable.set(str(cache.values[index]))
            # Restore Object Map path/category preview from the persisted RD3D RAM baseline.
            if cache is not None:
                self.object_configuration_map_file_names = list(cache.values)
        if window is not None and window.winfo_exists():
            window.destroy()
        self.object_configuration_table1_window = None
        self.object_configuration_table1_table = None
        popup = getattr(self, "_object_mass_replace_window", None)
        PopupTemplate.close_window(popup)
        self._object_mass_replace_window = None


    def _build_object_configuration_treeview(self, window, number):
        frame = ctk.CTkFrame(window)
        frame.grid(row=3, column=0, padx=PopupTemplate.HEADER_PADX, pady=(0, 8), sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        columns = (
            ("identifier", "category", "count", "object")
            if number == 1
            else ("category", "identifier", "count", "object")
        )
        headings = {
            "identifier": "Index" if number == 1 else "Object ID",
            "category": "Category",
            "count": "Count",
            "object": "Object",
        }
        widgets = TreeviewTemplate.create(
            frame,
            columns=columns,
            headings=headings,
            widths={"category": 145, "identifier": 110, "count": 80, "object": 420},
            min_widths={"category": 110, "identifier": 85, "count": 70, "object": 220},
            max_widths={"category": 240, "identifier": 190, "count": 120, "object": 720},
            stretch={"object"},
            selectmode="browse",
            on_select=lambda _event, n=number: self._object_configuration_tree_select(n),
            sortable=True,
            dynamic_width=True,
        )
        tree = widgets["tree"]
        setattr(self, f"object_configuration_table{number}_table", tree)
        setattr(self, f"_object_table{number}_row_map", {})
        setattr(self, f"_object_table{number}_editor_var", tk.StringVar(master=self))
        editor = ctk.CTkFrame(window)
        editor.grid(row=4, column=0, padx=PopupTemplate.HEADER_PADX, pady=(0, 8), sticky="ew")
        editor.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(editor, text="Object", width=75, anchor="w").grid(row=0, column=0, padx=(10, 8), pady=8)
        entry = ctk.CTkEntry(editor, textvariable=getattr(self, f"_object_table{number}_editor_var"))
        entry.grid(row=0, column=1, padx=(0, 8), pady=8, sticky="ew")
        entry.bind("<Return>", lambda _event, n=number: self._object_configuration_tree_apply(n))
        ctk.CTkButton(
            editor, text="Apply", width=90,
            command=lambda n=number: self._object_configuration_tree_apply(n),
        ).grid(row=0, column=2, padx=(0, 10), pady=8)

    def _object_configuration_tree_select(self, number):
        tree = getattr(self, f"object_configuration_table{number}_table", None)
        selection = tree.selection() if tree is not None else ()
        row_map = getattr(self, f"_object_table{number}_row_map", {})
        row = row_map.get(selection[0]) if selection else None
        if row is None:
            return
        variable = row[2]
        getattr(self, f"_object_table{number}_editor_var").set(variable.get())

    def _object_configuration_tree_apply(self, number):
        tree = getattr(self, f"object_configuration_table{number}_table", None)
        selection = tree.selection() if tree is not None else ()
        row_map = getattr(self, f"_object_table{number}_row_map", {})
        row = row_map.get(selection[0]) if selection else None
        if row is None:
            messagebox.showwarning(
                f"Objects Table {number}", "Select a row first.",
                parent=getattr(self, f"object_configuration_table{number}_window", None),
            )
            return
        value = getattr(self, f"_object_table{number}_editor_var").get().strip()
        if not value:
            messagebox.showerror(
                f"Objects Table {number}", "Object must not be empty.",
                parent=getattr(self, f"object_configuration_table{number}_window", None),
            )
            return
        row[2].set(value)
        getattr(self, f"_render_object_configuration_table_{number}")()
        if tree.exists(selection[0]):
            tree.selection_set(selection[0]); tree.focus(selection[0]); tree.see(selection[0])
        self.status_var.set(f"Objects Table {number}: Object updated in RAM; click Save")

    def _render_object_configuration_table_1(self):
        tree = self.object_configuration_table1_table
        if tree is None or not tree.winfo_exists():
            return
        tree.delete(*tree.get_children())
        row_map = {}
        for row_number, (index, original, variable, count) in enumerate(self.object_configuration_table1_rows):
            current = variable.get().strip()
            category = self._classify_object_configuration_path(current)
            color = self._object_configuration_color_for_category(category)
            tree.tag_configure(category, foreground=color)
            tree._template_tag_styles[category] = {"foreground": color}
            iid = f"table1_{row_number}"
            tree.insert("", "end", iid=iid, values=(index, category, count, current), tags=(category,))
            row_map[iid] = (index, original, variable, count)
        self._object_table1_row_map = row_map
        tree.schedule_autosize()

    @staticmethod
    def _object_configuration_table_1_type(value): return (value or "").split(", Variations:",1)[0].strip()

    def _object_configuration_database_categories(self):
        # Metadata is precomputed once in function_custom_content._snapshot().
        # Opening the picker is now O(categories), not O(categories * objects).
        result = []
        for row in get_combined_category_rows(self.CONFIG_FILE):
            category = row["category"]
            regions = row["regions"]
            result.append({
                "category": category,
                "display_category": display_category(category, self.CONFIG_FILE),
                "variations": row["variations"],
                "regions": regions,
                "display_regions": display_regions(regions, self.CONFIG_FILE),
            })
        return result

    def _object_configuration_picker_color(self, category):
        return self._object_configuration_color_for_category(category)

    def _open_object_configuration_category_picker(self, target_var, owner):
        popup_owner = owner or self
        picker = CategoryPickerTemplate.create(
            popup_owner,
            categories=self._object_configuration_database_categories(),
            selected=target_var.get().strip(),
            color_provider=self._object_configuration_picker_color,
            on_select=target_var.set,
            title="Select Replace-To Category",
        )
        try:
            owner_window = popup_owner.winfo_toplevel()
            picker.transient(owner_window)
            PopupTemplate.apply_native_titlebar_controls(picker)
            picker.lift(owner_window)
            PopupTemplate.request_focus(picker, delay_ms=100)
        except (tk.TclError, AttributeError):
            pass

    def _object_configuration_database_paths(self, category):
        paths, seen = [], set()
        for _source_category, path, _count in get_combined_object_database(self.CONFIG_FILE):
            path = (path or "").strip()
            key = path.casefold()
            if path and key not in seen and self._classify_object_configuration_path(path) == category:
                seen.add(key); paths.append(path)
        return paths

    def _object_mass_replace_rows(self, number):
        """Return Categories with the number of placed object instances."""
        rows = (
            self.object_configuration_table1_rows
            if number == 1 else self.object_configuration_table2_rows
        )
        categories = {}
        for row in rows:
            variable = row[2] if number == 1 else row[4]
            category = self._classify_object_configuration_path(variable.get().strip())
            try:
                placed_count = int(row[3])
            except (TypeError, ValueError):
                placed_count = 0
            categories[category] = categories.get(category, 0) + max(0, placed_count)
        return [
            (category, categories[category])
            for category in sorted(categories, key=str.casefold)
        ]

    def _open_object_mass_replace_popup(self, number):
        owner = getattr(self, f"object_configuration_table{number}_window", None)
        current = getattr(self, "_object_mass_replace_window", None)
        if current is not None and current.winfo_exists():
            PopupTemplate.close_window(current)
        built = PopupTemplate.create_window(
            owner or self,
            title=f"Objects Table {number} - Mass Replace",
            heading="Mass Replace Categories",
            geometry="980x650",
            min_size=(760, 440),
            resizable=True,
        )
        popup = built["window"]
        # This dialog belongs above its object table, not merely above App.
        # Restore the window-manager ownership relation removed by the generic
        # independent-titlebar setup. Do not use permanent global topmost.
        if owner is not None and owner.winfo_exists():
            popup.transient(owner)
            PopupTemplate.apply_native_titlebar_controls(popup)
        PopupTemplate.request_focus(popup, delay_ms=100)
        self._object_mass_replace_window = popup
        popup.grid_columnconfigure(0, weight=1)
        popup.grid_rowconfigure(1, weight=1)
        scroll = ctk.CTkScrollableFrame(popup)
        scroll.grid(row=1, column=0, padx=18, pady=(0, 10), sticky="nsew")
        scroll.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(
            scroll, text="From Category", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, padx=(8, 12), pady=(4, 8), sticky="w")
        ctk.CTkLabel(
            scroll, text="Count", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=1, padx=8, pady=(4, 8), sticky="e")
        ctk.CTkLabel(
            scroll, text="To", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=2, padx=8, pady=(4, 8), sticky="w")
        ctk.CTkLabel(
            scroll, text="Select", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=3, padx=(8, 8), pady=(4, 8), sticky="w")
        mappings = []
        for row_index, (category, count) in enumerate(self._object_mass_replace_rows(number), start=1):
            color = self._object_configuration_color_for_category(category)
            ctk.CTkLabel(
                scroll, text=category, text_color=color, anchor="w"
            ).grid(row=row_index, column=0, padx=(8, 12), pady=5, sticky="ew")
            ctk.CTkLabel(
                scroll, text=str(count), anchor="e", width=90
            ).grid(row=row_index, column=1, padx=8, pady=5, sticky="e")
            target = tk.StringVar(master=self)
            entry = ctk.CTkEntry(scroll, textvariable=target)
            entry.grid(row=row_index, column=2, padx=8, pady=5, sticky="ew")
            ctk.CTkButton(
                scroll, text="Select...", width=100,
                command=lambda var=target: self._open_object_configuration_category_picker(var, popup),
            ).grid(row=row_index, column=3, padx=(8, 8), pady=5)
            mappings.append((category, target))
        self._object_mass_replace_mappings = mappings
        actions = ctk.CTkFrame(popup, fg_color="transparent")
        actions.grid(row=2, column=0, padx=18, pady=(0, 16), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            actions, text="Save", width=120,
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self._save_object_mass_replace_popup(number),
        ).grid(row=0, column=1, sticky="e")
        PopupTemplate.schedule(popup, 50, lambda: PopupTemplate.safe_activate(popup))

    def _save_object_mass_replace_popup(self, number):
        mappings = getattr(self, "_object_mass_replace_mappings", ())
        selected = []
        for from_type, target_var in mappings:
            to_type = self._object_configuration_table_1_type(target_var.get())
            if not to_type:
                continue
            if from_type == to_type:
                continue
            targets = self._object_configuration_database_paths(to_type)
            if not targets:
                messagebox.showerror(
                    f"Objects Table {number}",
                    f"No target paths of Category '{to_type}' are available.",
                    parent=self._object_mass_replace_window,
                )
                return
            selected.append((from_type, to_type, targets))
        if not selected:
            messagebox.showinfo(
                f"Objects Table {number}", "No category mappings were selected.",
                parent=self._object_mass_replace_window,
            )
            return
        rows = self.object_configuration_table1_rows if number == 1 else self.object_configuration_table2_rows
        changed = 0
        for from_type, _to_type, targets in selected:
            source_rows = [
                row for row in rows
                if self._classify_object_configuration_path(
                    (row[2] if number == 1 else row[4]).get().strip()
                ) == from_type
            ]
            for offset, row in enumerate(source_rows):
                variable = row[2] if number == 1 else row[4]
                variable.set(targets[offset % len(targets)])
                changed += 1
        getattr(self, f"_render_object_configuration_table_{number}")()
        self.status_var.set(
            f"Objects Table {number}: Mass Replace applied to {changed} entries in RAM; click table Save to write XML"
        )
        popup = getattr(self, "_object_mass_replace_window", None)
        PopupTemplate.close_window(popup)
        self._object_mass_replace_window = None
        messagebox.showinfo(
            "Mass Replace",
            f"Mass Replace was saved successfully.\n\n"
            f"Updated entries: {changed}\n"
            "The changes are stored in the table RAM. Click the table Save button to write the XML files.",
            parent=getattr(self, f"object_configuration_table{number}_window", None),
        )

    def _reset_object_configuration_table_1(self):
        owner = self.object_configuration_table1_window
        if not messagebox.askyesno(
            "Reset Objects Table 1",
            "Reset all Object values in Objects Table 1 to their original values?\n\n"
            "All unsaved table changes will be discarded.",
            parent=owner,
            default="no",
            icon="warning",
        ):
            return
        for _index, original, variable, _count in self.object_configuration_table1_rows:
            variable.set(original)
        self._render_object_configuration_table_1()
        self._rd3d_ram_preview_paths()
        self.status_var.set("Objects Table 1 reset to original values (RAM only)")


    def _open_object_configuration_table_2(self):
        status = self._show_object_operation_status("Loading...")
        try:
            self._open_object_configuration_table_2_impl()
            self.update_idletasks()
            window = getattr(self, "object_configuration_table2_window", None)
            if window is not None and window.winfo_exists():
                window.update_idletasks()
                window.lift()
        finally:
            self._hide_object_operation_status(status)

    def _open_object_configuration_table_2_impl(self):
        if not self._load_object_configuration_table_2_data():
            return
        window = self.object_configuration_table2_window
        if window is not None and window.winfo_exists():
            window.deiconify(); PopupTemplate.safe_activate(window)
            self._render_object_configuration_table_2()
            return
        built = PopupTemplate.create_window(
            self, title="Objects Table 2", heading="Objects Table 2",
            close_command=self._close_object_configuration_table_2,
        )
        window = built["window"]
        self.object_configuration_table2_window = window
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(
            window, textvariable=self.object_configuration_table2_info_var,
            text_color=PopupTemplate.SECONDARY_TEXT_COLOR,
        ).grid(row=1, column=0, padx=PopupTemplate.HEADER_PADX, pady=(0, 8), sticky="w")

        bar = ctk.CTkFrame(window)
        bar.grid(row=2, column=0, padx=PopupTemplate.HEADER_PADX, pady=(0, 10), sticky="ew")
        bar.grid_columnconfigure(1, weight=1); bar.grid_columnconfigure(3, weight=1)
        self._build_object_profiles(bar, 2)
        ctk.CTkButton(
            bar,
            text="Mass Replace",
            width=PopupTemplate.BUTTON_WIDTH,
            height=PopupTemplate.BUTTON_HEIGHT,
            command=lambda: self._open_object_mass_replace_popup(2),
        ).grid(row=1, column=0, padx=12, pady=(10, 10), sticky="w")
        self._build_object_configuration_treeview(window, 2)
        actions=ctk.CTkFrame(window,fg_color="transparent")
        actions.grid(row=5,column=0,padx=PopupTemplate.HEADER_PADX,pady=(0,16),sticky="ew")
        actions.grid_columnconfigure(0,weight=1)
        ctk.CTkButton(actions,text="Reset",width=PopupTemplate.BUTTON_WIDTH,height=PopupTemplate.BUTTON_HEIGHT,fg_color=PopupTemplate.DANGER_BUTTON_FG_COLOR,hover_color=PopupTemplate.DANGER_BUTTON_HOVER_COLOR,command=self._reset_object_configuration_table_2).grid(row=0,column=1,padx=(0,8),sticky="e")
        ctk.CTkButton(actions,text="Save",width=PopupTemplate.BUTTON_WIDTH,height=PopupTemplate.BUTTON_HEIGHT,font=ctk.CTkFont(size=PopupTemplate.BUTTON_FONT_SIZE,weight="bold"),command=self._save_object_configuration_table_2).grid(row=0,column=2,sticky="e")
        self._render_object_configuration_table_2()

    def _close_object_configuration_table_2(self):
        window = self.object_configuration_table2_window
        if window is not None and window.winfo_exists():
            window.destroy()
        self.object_configuration_table2_window = None
        self.object_configuration_table2_table = None
        popup = getattr(self, "_object_mass_replace_window", None)
        PopupTemplate.close_window(popup)
        self._object_mass_replace_window = None

    @staticmethod
    def _object_configuration_tmc_ground_objects(root):
        rows = []
        for ground_objects in root.iter():
            tag = ground_objects.tag.rsplit("}", 1)[-1].lower() if isinstance(ground_objects.tag, str) else ""
            if tag != "groundobjects":
                continue
            for entry in list(ground_objects):
                object_id = filename = None
                for child in list(entry):
                    if not isinstance(child.tag, str):
                        continue
                    child_tag = child.tag.rsplit("}", 1)[-1].lower()
                    if child_tag == "id":
                        object_id = (child.text or "").strip()
                    elif child_tag == "filename":
                        filename = (child.text or "").strip()
                if object_id and filename:
                    rows.append((object_id, filename))
        return rows


    def _render_object_configuration_table_2(self):
        tree = self.object_configuration_table2_table
        if tree is None or not tree.winfo_exists():
            return
        tree.delete(*tree.get_children())
        row_map = {}
        for row_number, (index, object_id, original, count, variable) in enumerate(self.object_configuration_table2_rows):
            current = variable.get().strip()
            category = self._classify_object_configuration_path(current)
            color = self._object_configuration_color_for_category(category)
            tree.tag_configure(category, foreground=color)
            tree._template_tag_styles[category] = {"foreground": color}
            iid = f"table2_{row_number}"
            tree.insert("", "end", iid=iid, values=(category, object_id or index, count, current), tags=(category,))
            row_map[iid] = (object_id or index, original, variable, count)
        self._object_table2_row_map = row_map
        tree.schedule_autosize()

    def _object_configuration_table_2_stats(self):
        stats = {}
        for _index, _object_id, _original, count, variable in self.object_configuration_table2_rows:
            category = self._classify_object_configuration_path(variable.get().strip())
            values = stats.setdefault(category, {"variations": 0, "placed": 0})
            values["variations"] += 1
            values["placed"] += count
        return stats

    def _reset_object_configuration_table_2(self):
        owner = self.object_configuration_table2_window
        if not messagebox.askyesno(
            "Reset Objects Table 2",
            "Reset all Object values in Objects Table 2 to their original values?\n\n"
            "All unsaved table changes will be discarded.",
            parent=owner,
            default="no",
            icon="warning",
        ):
            return
        for _index, _object_id, original, _count, variable in self.object_configuration_table2_rows:
            variable.set(original)
        self._render_object_configuration_table_2()
        self.status_var.set("Objects Table 2 reset to original values (RAM only)")


    @staticmethod
    def _tmc_map_split_numbers(value):
        return tuple(part for part in str(value or "").replace(",", ".").split() if part)

    def _load_tmc_object_map_points(self):
        root_value = self.tmc_data_meshes_var.get().strip()
        root = Path(root_value) if root_value else None
        if root is None or not root.exists():
            raise FileNotFoundError("Please select an existing TMC meshes folder first.")
        files = [root] if root.is_file() else sorted(root.rglob("*_patched.xml"))
        if not files and root.is_dir():
            files = sorted(root.rglob("*_original.xml"))
        # Prefer patched per relative stem, but keep original-only pages.
        if root.is_dir():
            selected = {}
            for path in sorted(root.rglob("*.xml")):
                name = path.name
                if not (name.endswith("_original.xml") or name.endswith("_patched.xml")):
                    continue
                key = str(path.relative_to(root)).replace("_patched.xml", ".xml").replace("_original.xml", ".xml")
                if key not in selected or name.endswith("_patched.xml"):
                    selected[key] = path
            files = list(selected.values())
        points = []
        errors = []
        for path in files:
            try:
                tree, _repaired, _repairs = self._parse_xml_tolerant(path)
                root_node = tree.getroot()
                for ground in root_node.iter():
                    if self._object_configuration_local_tag(ground) != "GroundObjects":
                        continue
                    for group in list(ground):
                        values = {self._object_configuration_local_tag(child): (child.text or "").strip()
                                  for child in list(group)}
                        filename = values.get("FileName", "").strip()
                        positions = self._tmc_map_split_numbers(values.get("PositionsXZ"))
                        rotations = self._tmc_map_split_numbers(values.get("RotationsY"))
                        coverages = self._tmc_map_split_numbers(values.get("Coverages"))
                        if not filename or len(positions) % 2:
                            continue
                        category = get_category_for_object(filename, self.CONFIG_FILE)
                        for index in range(len(positions) // 2):
                            try:
                                x, z = float(positions[index * 2]), float(positions[index * 2 + 1])
                            except ValueError:
                                continue
                            points.append({
                                "x": x, "z": z, "path": filename, "category": category,
                                "id": values.get("ID", ""),
                                "rotation": rotations[index] if index < len(rotations) else "",
                                "coverage": coverages[index] if index < len(coverages) else "",
                                "source": str(path),
                            })
            except (OSError, ET.ParseError, UnicodeError, ValueError) as exc:
                errors.append(f"{path.name}: {exc}")
        # The same GroundObject can be repeated in several TMC LOD pages.
        # Keep one visual point per complete instance identity so the map does
        # not render stacked duplicate dots for identical world objects.
        unique = {}
        for point in points:
            key = (
                point["path"].strip().replace("\\", "/").casefold(),
                point["x"], point["z"], point["id"],
                point["rotation"], point["coverage"],
            )
            existing = unique.get(key)
            if existing is None:
                point["sources"] = [point["source"]]
                unique[key] = point
            else:
                existing["sources"].append(point["source"])
        return list(unique.values()), files, errors, root

    def _open_tmc_object_map(self):
        status = self._show_object_operation_status("Loading TMC GroundObjects...")
        try:
            try:
                bounds = MapViewTemplate.read_playable_area(
                    self.gamedata_file_var.get().strip(), parser=self._parse_xml_tolerant)
                points, files, errors, root = self._load_tmc_object_map_points()
            except (OSError, ET.ParseError, UnicodeError, ValueError) as exc:
                messagebox.showerror("Object Map (tmc)", str(exc))
                return
            self.tmc_object_map_bounds = bounds
            self.tmc_object_map_points = points
            self.tmc_object_map_zoom = 1.0
            self.tmc_object_map_pan_x = self.tmc_object_map_pan_y = 0.0
            self.tmc_object_map_pan_start = None
            self.tmc_object_map_visible = {p["category"]: True for p in points}
            categories = sorted(self.tmc_object_map_visible, key=str.casefold)
            self.tmc_object_map_colors = {c: TYPE_CATEGORY_COLORS[i % len(TYPE_CATEGORY_COLORS)]
                                          for i, c in enumerate(categories)}
            self.tmc_object_map_image_source, self.tmc_object_map_image_path = MapViewTemplate.load_background(
                (root if root.is_dir() else root.parent,
                 (root if root.is_dir() else root.parent).parent,
                 Path(self.gamedata_file_var.get().strip()).parent), direct_first=True)
            self.tmc_object_map_image_tk = None
            window = getattr(self, "tmc_object_map_window", None)
            if window is not None and window.winfo_exists():
                window.destroy()
            self.tmc_object_map_info_var = tk.StringVar(
                value=f"{len(points)} TMC GroundObject instances from {len(files)} XML files"
                      + (f"; {len(errors)} files skipped" if errors else ""))
            self.tmc_object_map_selection_var = tk.StringVar(
                value="Move the pointer over a dot to display TMC object details. Read-only view.")
            built = MapViewTemplate.build_map_window(
                self, title="Object Map (tmc)", heading="Object Map (tmc)",
                info_variable=self.tmc_object_map_info_var,
                selection_variable=self.tmc_object_map_selection_var,
                close_command=self._close_tmc_object_map,
                redraw_command=self._redraw_tmc_object_map,
                legend_builder=lambda: None,
                maximize_button_attribute="tmc_object_map_maximize_button",
            )
            self.tmc_object_map_window = built["window"]
            self.tmc_object_map_canvas = built["canvas"]
            self.tmc_object_map_legend = built["legend"]
            self._rebuild_tmc_object_map_legend()
            MapViewTemplate.bind_map_mouse(
                self.tmc_object_map_canvas,
                configure=self._redraw_tmc_object_map,
                motion=self._tmc_object_map_motion,
                leave=lambda _e: self.tmc_object_map_selection_var.set(
                    "Move the pointer over a dot to display TMC object details. Read-only view."),
                wheel=self._tmc_object_map_wheel,
                pan_start=self._tmc_object_map_pan_begin,
                pan_move=self._tmc_object_map_pan_move,
                pan_end=self._tmc_object_map_pan_end,
                redraw=self._redraw_tmc_object_map,
                owner=self.tmc_object_map_window,
            )
            self._redraw_tmc_object_map()
        finally:
            self._hide_object_operation_status(status)

    def _close_tmc_object_map(self):
        window = getattr(self, "tmc_object_map_window", None)
        if window is not None and window.winfo_exists():
            window.destroy()
        self.tmc_object_map_window = None
        self.tmc_object_map_canvas = None
        return True

    def _tmc_object_map_geometry(self):
        canvas = self.tmc_object_map_canvas
        width, height = max(2, canvas.winfo_width()), max(2, canvas.winfo_height())
        min_x, max_x, min_z, max_z = self.tmc_object_map_bounds
        scale = min((width - 2 * MapViewTemplate.MAP_MARGIN) / max(max_x - min_x, 1e-9),
                    (height - 2 * MapViewTemplate.MAP_MARGIN) / max(max_z - min_z, 1e-9)) * self.tmc_object_map_zoom
        iw, ih = (max_x - min_x) * scale, (max_z - min_z) * scale
        left = (width - iw) / 2 + self.tmc_object_map_pan_x
        top = (height - ih) / 2 + self.tmc_object_map_pan_y
        return min_x, min_z, scale, left, top, iw, ih

    def _redraw_tmc_object_map(self, *_args):
        canvas = getattr(self, "tmc_object_map_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        min_x, min_z, scale, left, top, iw, ih = self._tmc_object_map_geometry()
        source = self.tmc_object_map_image_source
        if source is not None:
            self.tmc_object_map_image_tk, vx, vy = MapViewTemplate.cached_viewport_photo(
                source, left, top, iw, ih, canvas.winfo_width(), canvas.winfo_height(), {})
            if self.tmc_object_map_image_tk is not None:
                canvas.create_image(vx, vy, image=self.tmc_object_map_image_tk, anchor="nw")
        canvas.create_rectangle(left, top, left + iw, top + ih,
                                outline=MapViewTemplate.BACKGROUND_BORDER_COLOR)
        self.tmc_object_map_screen_points = []
        radius = 3
        for point in self.tmc_object_map_points:
            if not self.tmc_object_map_visible.get(point["category"], True):
                continue
            sx = left + (point["x"] - min_x) * scale
            # World +Z points upward in the existing RD3D/MapView contract,
            # while Tk canvas +Y points downward. Invert Z so TMC points use
            # exactly the same island/background orientation as every map view.
            sy = top + ih - (point["z"] - min_z) * scale
            if -radius <= sx <= canvas.winfo_width() + radius and -radius <= sy <= canvas.winfo_height() + radius:
                color = self.tmc_object_map_colors.get(point["category"], DEFAULT_TYPE_COLOR)
                canvas.create_oval(sx-radius, sy-radius, sx+radius, sy+radius,
                                   fill=color, outline="#111111", width=1)
                self.tmc_object_map_screen_points.append((sx, sy, point))
        MapViewTemplate.draw_zoom_indicator(canvas, self.tmc_object_map_zoom)

    def _tmc_object_map_motion(self, event):
        nearest = None
        best = MapViewTemplate.HOVER_HIT_RADIUS ** 2
        for sx, sy, point in getattr(self, "tmc_object_map_screen_points", ()):
            distance = (sx-event.x)**2 + (sy-event.y)**2
            if distance <= best:
                best, nearest = distance, point
        if nearest is None:
            self.tmc_object_map_selection_var.set(
                "Move the pointer over a dot to display TMC object details. Read-only view.")
        else:
            self.tmc_object_map_selection_var.set(
                f'{nearest["category"]} | X/Z: {nearest["x"]:g} / {nearest["z"]:g} | '
                f'ID: {nearest["id"] or "-"} | RotationY: {nearest["rotation"] or "-"} | '
                f'Coverage: {nearest["coverage"] or "-"}\n{nearest["path"]}\n'
                f'TMC sources / LOD copies: {len(nearest.get("sources", (nearest["source"],)))}\n'
                f'{nearest["source"]}')

    def _tmc_object_map_wheel(self, event):
        delta = 1 if getattr(event, "delta", 0) > 0 or getattr(event, "num", 0) == 4 else -1
        self.tmc_object_map_zoom = min(20.0, max(0.25, self.tmc_object_map_zoom * (1.15 if delta > 0 else 1/1.15)))
        self._redraw_tmc_object_map()
        return "break"

    def _tmc_object_map_pan_begin(self, event):
        self.tmc_object_map_pan_start = MapViewTemplate.begin_pan(
            event, self.tmc_object_map_pan_x, self.tmc_object_map_pan_y)

    def _tmc_object_map_pan_move(self, event):
        result = MapViewTemplate.move_pan(self.tmc_object_map_pan_start, event)
        if result is not None:
            self.tmc_object_map_pan_x, self.tmc_object_map_pan_y = result
            self._redraw_tmc_object_map()

    def _tmc_object_map_pan_end(self, _event):
        self.tmc_object_map_pan_start = None

    def _rebuild_tmc_object_map_legend(self):
        legend = self.tmc_object_map_legend
        for widget in legend.winfo_children():
            widget.destroy()
        for index, category in enumerate(sorted(self.tmc_object_map_visible, key=str.casefold)):
            visible = self.tmc_object_map_visible[category]
            color = self.tmc_object_map_colors[category]
            MapViewTemplate.build_legend_button(
                legend, text=category, color=color, visible=visible,
                command=lambda c=category: self._toggle_tmc_object_map_category(c),
                row=index // 5, column=index % 5)

    def _toggle_tmc_object_map_category(self, category):
        self.tmc_object_map_visible[category] = not self.tmc_object_map_visible[category]
        self._rebuild_tmc_object_map_legend()
        self._redraw_tmc_object_map()

    def _open_object_configuration_map(self):
        status = self._show_object_operation_status("Loading...")
        try:
            self._open_object_configuration_map_impl()
            self.update_idletasks()
            window = getattr(self, "object_configuration_map_window", None)
            if window is not None and window.winfo_exists():
                window.update_idletasks()
                window.lift()
        finally:
            self._hide_object_operation_status(status)

    def _open_object_configuration_map_impl(self):
        if not self._load_object_configuration_map_data():
            return

        window = self.object_configuration_map_window
        if window is not None and window.winfo_exists():
            window.deiconify()
            window.lift()
            PopupTemplate.safe_activate(window)
            self._rebuild_object_configuration_map_legend()
            self._schedule_object_configuration_map_redraw()
            return

        built = MapViewTemplate.build_map_window(
            self,
            title="Object Map",
            object_edit_help=True,
            heading="Object Map",
            info_variable=self.object_configuration_map_info_var,
            selection_variable=self.object_configuration_map_selection_var,
            close_command=self._close_object_configuration_map,
            redraw_command=self._schedule_object_configuration_map_redraw,
            legend_builder=lambda: None,
            maximize_button_attribute="object_configuration_map_maximize_button",
        )
        # Assign the built map widgets before creating shared movement controls.
        # The template stores Undo state/history on the canvas.
        self.object_configuration_map_window = built["window"]
        self.object_configuration_map_canvas = built["canvas"]
        self.object_configuration_map_legend = built["legend"]
        header = built['header']
        maximize = built['maximize_button']
        if maximize is not None:
            maximize.grid_configure(column=5)
        self.object_configuration_map_allow_dot_movement_var.set(False)
        MapViewTemplate.build_dot_movement_checkbox(
            header, self.object_configuration_map_allow_dot_movement_var,
            column=2, command=self._object_map_dot_movement_changed,
            canvas=self.object_configuration_map_canvas,
        )
        ctk.CTkButton(header, text='Save', width=90,
            height=PopupTemplate.BUTTON_HEIGHT, command=lambda:self._map_edit_run('save')).grid(
                row=0,column=3,padx=(8,4),sticky='e')
        ctk.CTkButton(header, text='Reset', width=90,
            height=PopupTemplate.BUTTON_HEIGHT, fg_color='#C42B1C', hover_color='#A4262C',
            command=self._confirm_object_map_reset).grid(
                row=0,column=4,padx=4,sticky='e')
        # Dragging needs an edit document immediately. ObjectMapSession accepts
        # the existing RD3D RAM cache; it does not accept cache=/canvas= keywords.
        try:
            cache, session = self._map_session_current()
            self._map_edit_session = session if session is not None else ObjectMapSession(cache)
            self._density_session = self._map_edit_session
            self._density_cache = cache
            self.object_configuration_map_points = self._map_preview_points(self._map_edit_session)
        except (ValueError, IndexError, OSError) as exc:
            self._map_edit_session = None
            messagebox.showerror('Object Map', str(exc), parent=self.object_configuration_map_window)
            self.object_configuration_map_window.destroy()
            self.object_configuration_map_window = None
            return
        self._bind_object_configuration_map_canvas()
        self._rebuild_object_configuration_map_legend()
        self._schedule_object_configuration_map_redraw()

    def _close_object_configuration_map(self):
        if self._tmc_ram_is_busy():
            messagebox.showwarning('Object Map','An XML operation is in progress.')
            return False
        window = self.object_configuration_map_window
        if self._rd3d_has_unsaved_work():
            if not messagebox.askyesno(
                "Object Map",
                "There are unsaved RD3D changes in Object Map, Objects Table 1 or Density.\n\n"
                "Closing Object Map will discard the shared RD3D working copy from RAM. "
                "TMC / Objects Table 2 data will not be changed.\n\n"
                "Close and discard the unsaved RD3D changes?",
                parent=window,
                default="no",
            ):
                return False
        self._map_selection_area = None
        self._map_selection_dragging = False
        for attribute in ('_density_window','_place_window','_region_window'):
            child_window = getattr(self, attribute, None)
            if child_window is not None and child_window.winfo_exists():
                child_window.destroy()
            setattr(self, attribute, None)
        table1 = getattr(self, "object_configuration_table1_window", None)
        if table1 is not None and table1.winfo_exists():
            table1.destroy()
        self.object_configuration_table1_window = None
        self.object_configuration_table1_table = None
        self._rd3d_discard_working_copy(clear_cache=True)
        if self.object_configuration_map_after_id is not None:
            try:
                self.after_cancel(self.object_configuration_map_after_id)
            except (tk.TclError, ValueError):
                pass
        self.object_configuration_map_after_id = None
        if window is not None and window.winfo_exists():
            window.destroy()
        self.object_configuration_map_window = None
        self.object_configuration_map_canvas = None
        self.object_configuration_map_legend = None
        self.status_var.set("Object Map closed; RD3D working copy/cache cleared. TMC cache unchanged.")
        return True

    @staticmethod
    def _object_configuration_local_tag(element):
        return element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""

    @staticmethod
    def _parse_object_configuration_position(text):
        parts = (text or "").strip().replace(";", " ").split()
        if len(parts) < 3:
            return None
        try:
            return tuple(float(value.replace(",", ".")) for value in parts[:3])
        except ValueError:
            return None

    def _load_object_configuration_map_data(self):
        pending=getattr(self,'_map_edit_session',None)
        if pending is not None and pending.dirty and pending.cache is self.rd3d_ram_cache:
            if pending.cache.path == Path(self.rd3d_file_var.get().strip()):
                self.object_configuration_map_points=self._map_preview_points(pending)
                self.object_configuration_map_file_names=pending.paths()
                return True
        try:
            bounds = MapViewTemplate.read_playable_area(
                self.gamedata_file_var.get().strip(), parser=self._parse_xml_tolerant)
        except (OSError, ET.ParseError, UnicodeError, ValueError) as exc:
            messagebox.showerror('Object Map', f'PlayableArea could not be loaded:\n{exc}')
            return False
        self.object_configuration_map_bounds = bounds
        path = Path(self.rd3d_file_var.get().strip())
        if not path.is_file():
            messagebox.showerror(
                "Object Map",
                "Please load an existing rd3d_original.xml file first.",
            )
            return False
        try:
            tree, _repaired, _repairs = self._parse_xml_tolerant(path)
        except (ET.ParseError, OSError, UnicodeError) as exc:
            messagebox.showerror("Object Map", f"rd3d_original.xml could not be read:\n{exc}")
            return False

        root = tree.getroot()
        prop_grid = next(
            (node for node in root.iter() if self._object_configuration_local_tag(node) == "PropGrid"),
            None,
        )
        if prop_grid is None:
            messagebox.showerror("Object Map", "PropGrid was not found in rd3d_original.xml.")
            return False

        file_names_node = next(
            (node for node in list(prop_grid) if self._object_configuration_local_tag(node) == "FileNames"),
            None,
        )
        instances_node = next(
            (node for node in list(prop_grid) if self._object_configuration_local_tag(node) == "Instances"),
            None,
        )
        self.object_configuration_map_file_names = [
            (node.text or "").strip() for node in list(file_names_node)
        ] if file_names_node is not None else []
        patched_path = path.with_name("rd3d_patched.xml")
        if patched_path.is_file():
            try:
                patched_root = self._parse_xml_tolerant(patched_path)[0].getroot()
                patched_grid = next((node for node in patched_root.iter() if self._object_configuration_local_tag(node) == "PropGrid"), None)
                patched_names = next((node for node in list(patched_grid) if self._object_configuration_local_tag(node) == "FileNames"), None) if patched_grid is not None else None
                candidate = [(node.text or "").strip() for node in list(patched_names)] if patched_names is not None else []
                if len(candidate) >= len(self.object_configuration_map_file_names):
                    self.object_configuration_map_file_names = candidate
                    patched_instances = next((node for node in patched_grid
                        if self._object_configuration_local_tag(node) == 'Instances'), None)
                    if patched_instances is not None:
                        instances_node = patched_instances
            except (ET.ParseError, OSError, UnicodeError):
                pass

        points = []
        if instances_node is not None:
            for instance in list(instances_node):
                index_node = next(
                    (node for node in list(instance) if self._object_configuration_local_tag(node) == "Index"),
                    None,
                )
                position_node = next(
                    (node for node in list(instance) if self._object_configuration_local_tag(node) == "Position"),
                    None,
                )
                if index_node is None or position_node is None:
                    continue
                try:
                    prop_index = int((index_node.text or "").strip())
                except ValueError:
                    continue
                position = self._parse_object_configuration_position(position_node.text)
                if position is None:
                    continue
                x, y, z = position
                path_text = (
                    self.object_configuration_map_file_names[prop_index]
                    if 0 <= prop_index < len(self.object_configuration_map_file_names)
                    else ""
                )
                category = self._classify_object_configuration_path(path_text)
                points.append((prop_index, x, z, y, (position_node.text or "").strip(), category))

        self.object_configuration_map_points = points
        categories = []
        for point in points:
            if point[5] not in categories:
                categories.append(point[5])
        self.object_configuration_map_category_visible = {
            category: self.object_configuration_map_category_visible.get(category, True)
            for category in categories
        }
        for category in categories:
            self._object_configuration_color_for_category(category)

        self.object_configuration_map_zoom = MapViewTemplate.DEFAULT_POINT_ZOOM
        self.object_configuration_map_pan_x = 0.0
        self.object_configuration_map_pan_y = 0.0
        self.object_configuration_map_shared_zoom = MapViewTemplate.DEFAULT_SHARED_ZOOM
        self.object_configuration_map_shared_pan_x = 0.0
        self.object_configuration_map_shared_pan_y = 0.0
        self.object_configuration_map_selection_var.set(
            "Hover or click a point to display its index, prop and position."
        )
        self._load_object_configuration_map_background(path)
        self.object_configuration_map_info_var.set(
            f"{len(points)} Instances | {len(categories)} Categories | X/Z | PlayableArea: {bounds}"
            + (f" | Background: {self.object_configuration_map_image_path.name}" if self.object_configuration_map_image_path else " | No background image found")
        )
        return True

    def _classify_object_configuration_path(self, path_text):
        return get_category_for_object(path_text, self.CONFIG_FILE)

    def _object_configuration_color_for_category(self, category):
        """Return the one shared Category/Type color used by Object Map and tables."""
        category = str(category or DEFAULT_RD3D_CATEGORY)
        color = self.object_configuration_map_category_colors.get(category)
        if color is None:
            color = self._object_configuration_category_color(category)
            self.object_configuration_map_category_colors[category] = color
        return color

    def _object_configuration_category_color(self, _category):
        """Allocate Object Map/Table category colors exclusively from config_colors.py."""
        used = set(self.object_configuration_map_category_colors.values())
        families = {
            name: [color for color in colors if color]
            for name, colors in TYPE_CATEGORY_COLOR_FAMILIES.items()
        }
        rounds = max((len(colors) for colors in families.values()), default=0)
        for shade_index in range(rounds):
            available = [
                colors[shade_index]
                for colors in families.values()
                if shade_index < len(colors) and colors[shade_index] not in used
            ]
            if available:
                return random.choice(available)
        palette = [color for color in TYPE_CATEGORY_COLORS if color]
        available = [color for color in palette if color not in used]
        return random.choice(available or palette) if palette else DEFAULT_TYPE_COLOR

    def _load_object_configuration_map_background(self, rd3d_path):
        rd3d_path = Path(rd3d_path)
        self.object_configuration_map_image_tk = None
        (self.object_configuration_map_image_source,
         self.object_configuration_map_image_path) = MapViewTemplate.load_background(
            (rd3d_path.parent, rd3d_path.parent.parent), direct_first=True)

    def _confirm_object_map_reset(self):
        """Confirm and restore all original Object Map instance data."""
        owner = self.object_configuration_map_window
        if not messagebox.askyesno(
            'Reset Object Map',
            'Warning: All original object data will be restored from rd3d_original.xml.\n\n'
            'All current unsaved Object Map changes will be discarded. Continue?',
            parent=owner,
            default='no',
            icon='warning',
        ):
            return
        self._map_edit_run('restore')

    def _bind_object_configuration_map_canvas(self):
        MapViewTemplate.bind_map_mouse(
            self.object_configuration_map_canvas,
            configure=self._schedule_object_configuration_map_redraw,
            motion=self._on_object_configuration_map_motion,
            leave=self._on_object_configuration_map_leave,
            left_start=self._object_map_drag_start,
            left_move=self._object_map_drag_motion,
            left_end=self._object_map_drag_end,
            selection_start=self._map_selection_start,
            selection_move=self._map_selection_move,
            selection_end=self._map_selection_end,
            lasso_point=self._map_lasso_point,
            wheel=self._on_object_configuration_map_wheel,
            context=self._open_object_configuration_map_context_menu,
            pan_start=self._start_object_configuration_map_pan,
            pan_move=self._move_object_configuration_map_pan,
            pan_end=self._end_object_configuration_map_pan,
            redraw=self._schedule_object_configuration_map_redraw,
            owner=self.object_configuration_map_window,
            escape=self._map_selection_clear,
        )

    def _open_object_configuration_map_context_menu(self, event):
        if self._map_selection_menu(event):
            return "break"
        hit = self._nearest_object_configuration_map_point(event)
        entries = [
            {"label": "Add Object", "command": lambda e=event: self._place_object_open(e)},
            {
                "label": "Remove Object",
                "state": "normal" if hit is not None else "disabled",
                "command": lambda e=event, target=hit: self._map_delete_at(e, hit=target),
            },
        ]
        return MapViewTemplate.show_context_menu(
            self.object_configuration_map_window, event, entries
        )

    def _rebuild_object_configuration_map_legend(self):
        legend = self.object_configuration_map_legend
        if legend is None or not legend.winfo_exists():
            return
        for widget in legend.winfo_children():
            widget.destroy()
        self.object_configuration_map_category_buttons = {}
        categories = sorted(
            self.object_configuration_map_category_visible,
            key=str.casefold,
        )
        for index, category in enumerate(categories):
            visible = self.object_configuration_map_category_visible.get(category, True)
            color = self.object_configuration_map_category_colors[category]
            button = MapViewTemplate.build_legend_button(
                legend, text=category, color=color, visible=visible,
                command=lambda value=category: self._toggle_object_configuration_map_category(value),
                row=index // MapViewTemplate.LEGEND_COLUMNS,
                column=index % MapViewTemplate.LEGEND_COLUMNS,
            )
            self.object_configuration_map_category_buttons[category] = button

    def _toggle_object_configuration_map_category(self, category):
        self.object_configuration_map_category_visible[category] = not self.object_configuration_map_category_visible.get(category, True)
        self._rebuild_object_configuration_map_legend()
        self._schedule_object_configuration_map_redraw()

    @staticmethod
    def _object_configuration_ctrl_pressed(event):
        return bool(getattr(event, "state", 0) & 0x0004)

    def _draw_object_configuration_map_zoom_preview(self):
        """Draw only the background while a wheel zoom sequence is active.

        MapViewTemplate calls this callback once per wheel event and once after
        its debounce. The expensive dot bitmap and spatial hit grids are rebuilt
        only by that final callback.
        """
        canvas = self.object_configuration_map_canvas
        if canvas is None or not canvas.winfo_exists():
            return
        if not MapViewTemplate.zoom_active(canvas):
            self._schedule_object_configuration_map_redraw()
            return

        width = max(2, canvas.winfo_width())
        height = max(2, canvas.winfo_height())
        min_x, max_x, min_z, max_z = self.object_configuration_map_bounds
        span_x = max_x - min_x
        span_z = max_z - min_z
        if span_x <= 0 or span_z <= 0:
            return

        padding = MapViewTemplate.MAP_MARGIN
        base_scale = min(
            (width - 2 * padding) / span_x,
            (height - 2 * padding) / span_z,
        )
        shared_scale = base_scale * self.object_configuration_map_shared_zoom
        image_width = span_x * shared_scale
        image_height = span_z * shared_scale
        image_left = (
            (width - image_width) / 2
            + self.object_configuration_map_shared_pan_x
        )
        image_top = (
            (height - image_height) / 2
            + self.object_configuration_map_shared_pan_y
        )

        # Replace only background items. The existing dot bitmap stays allocated
        # and hidden by MapViewTemplate until the final full redraw.
        canvas.delete("map_background")
        source = self.object_configuration_map_image_source
        if source is not None:
            (
                self.object_configuration_map_image_tk,
                visible_left,
                visible_top,
            ) = MapViewTemplate.cached_viewport_photo(
                source,
                image_left,
                image_top,
                image_width,
                image_height,
                width,
                height,
                self.object_configuration_map_image_cache,
            )
            if self.object_configuration_map_image_tk is not None:
                canvas.create_image(
                    visible_left,
                    visible_top,
                    image=self.object_configuration_map_image_tk,
                    anchor="nw",
                    tags=("map_content", "map_background"),
                )
        canvas.create_rectangle(
            image_left,
            image_top,
            image_left + image_width,
            image_top + image_height,
            outline=MapViewTemplate.BACKGROUND_BORDER_COLOR,
            width=MapViewTemplate.BACKGROUND_BORDER_WIDTH,
            tags=("map_content", "map_background"),
        )
        canvas.tag_lower("map_background")
        MapViewTemplate.draw_zoom_indicator(
            canvas, self.object_configuration_map_shared_zoom
        )

    def _on_object_configuration_map_wheel(self, event):
        (
            self.object_configuration_map_shared_zoom,
            self.object_configuration_map_shared_pan_x,
            self.object_configuration_map_shared_pan_y,
        ) = MapViewTemplate.handle_focus_zoom_event(
            self.object_configuration_map_canvas,
            self.object_configuration_map_bounds,
            self.object_configuration_map_shared_zoom,
            self.object_configuration_map_shared_pan_x,
            self.object_configuration_map_shared_pan_y,
            event,
            self._draw_object_configuration_map_zoom_preview,
        )
        return "break"

    def _start_object_configuration_map_pan(self, event):
        # Middle mouse is reserved globally by MapViewTemplate for pure pan.
        # This guard must run before place, selection and object-delete logic.
        if MapViewTemplate.middle_pan_active(self.object_configuration_map_canvas, event):
            self.object_configuration_map_pan_start = MapViewTemplate.begin_pan(
                event,
                self.object_configuration_map_shared_pan_x,
                self.object_configuration_map_shared_pan_y,
            )
            self.object_configuration_map_canvas.configure(cursor="fleur")
            return "break"
        if self._map_selection_menu(event):
            self.object_configuration_map_pan_start = None
            return 'break'
        if self._map_delete_at(event):
            self.object_configuration_map_pan_start = None
            return 'break'
        self.object_configuration_map_pan_start = MapViewTemplate.begin_pan(
            event, self.object_configuration_map_shared_pan_x, self.object_configuration_map_shared_pan_y)
        self.object_configuration_map_canvas.configure(cursor="fleur")
        return "break"

    def _move_object_configuration_map_pan(self, event):
        position = MapViewTemplate.move_pan(self.object_configuration_map_pan_start, event)
        if position is not None:
            old_x, old_y = self.object_configuration_map_shared_pan_x, self.object_configuration_map_shared_pan_y
            self.object_configuration_map_shared_pan_x, self.object_configuration_map_shared_pan_y = position
            dx, dy = position[0] - old_x, position[1] - old_y
            MapViewTemplate.move_pan_background(
                self.object_configuration_map_canvas, dx, dy
            )
        return "break"

    def _end_object_configuration_map_pan(self, _event):
        self.object_configuration_map_pan_start = None
        if self.object_configuration_map_canvas is not None:
            self.object_configuration_map_canvas.configure(cursor="crosshair")
        return "break"

    def _schedule_object_configuration_map_redraw(self, _event=None):
        self.object_configuration_map_redraw_generation += 1
        generation = self.object_configuration_map_redraw_generation
        if self.object_configuration_map_after_id is not None:
            try:
                self.after_cancel(self.object_configuration_map_after_id)
            except (ValueError, tk.TclError):
                pass
        self.object_configuration_map_after_id = self.after(
            MapViewTemplate.REDRAW_DELAY_MS,
            lambda value=generation: self._draw_object_configuration_map_if_current(value),
        )

    def _draw_object_configuration_map_if_current(self, generation):
        if generation != self.object_configuration_map_redraw_generation:
            return
        self.object_configuration_map_after_id = None
        self._draw_object_configuration_map()

    def _object_map_ensure_world_grid(self):
        points = self.object_configuration_map_points
        signature = (id(points), len(points))
        if signature == self.object_configuration_map_world_grid_signature:
            return
        cell_size = self.object_configuration_map_world_cell_size
        min_x, _max_x, min_z, _max_z = self.object_configuration_map_bounds
        grid = {}
        for point in points:
            cell = (
                int(math.floor((point[1] - min_x) / cell_size)),
                int(math.floor((point[2] - min_z) / cell_size)),
            )
            grid.setdefault(cell, []).append(point)
        self.object_configuration_map_world_grid = grid
        self.object_configuration_map_world_grid_signature = signature

    def _object_map_view_candidates(self, image_left, image_top, image_width, image_height,
                                    canvas_width, canvas_height):
        self._object_map_ensure_world_grid()
        min_x, max_x, min_z, max_z = self.object_configuration_map_bounds
        span_x, span_z = max_x - min_x, max_z - min_z
        if image_width <= 0 or image_height <= 0:
            return []
        visible_min_x = max(min_x, min_x + (0 - image_left) / image_width * span_x)
        visible_max_x = min(max_x, min_x + (canvas_width - image_left) / image_width * span_x)
        visible_max_z = min(max_z, max_z - (0 - image_top) / image_height * span_z)
        visible_min_z = max(min_z, max_z - (canvas_height - image_top) / image_height * span_z)
        if visible_min_x > visible_max_x or visible_min_z > visible_max_z:
            return []
        cell_size = self.object_configuration_map_world_cell_size
        cell_min_x = int(math.floor((visible_min_x - min_x) / cell_size))
        cell_max_x = int(math.floor((visible_max_x - min_x) / cell_size))
        cell_min_z = int(math.floor((visible_min_z - min_z) / cell_size))
        cell_max_z = int(math.floor((visible_max_z - min_z) / cell_size))
        visible_categories = self.object_configuration_map_category_visible
        result = []
        for cell_x in range(cell_min_x, cell_max_x + 1):
            for cell_z in range(cell_min_z, cell_max_z + 1):
                for point in self.object_configuration_map_world_grid.get((cell_x, cell_z), ()):
                    if (visible_min_x <= point[1] <= visible_max_x
                            and visible_min_z <= point[2] <= visible_max_z
                            and visible_categories.get(point[5], True)):
                        result.append(point)
        return result

    def _object_map_build_screen_grid(self, screen_points):
        cell_size = self.object_configuration_map_screen_cell_size
        grid = {}
        for point in screen_points:
            cell = (int(point[0] // cell_size), int(point[1] // cell_size))
            grid.setdefault(cell, []).append(point)
        self.object_configuration_map_screen_grid = grid

    def _object_map_nearest_from_grid(self, event, hover=False):
        cell_size = self.object_configuration_map_screen_cell_size
        radius = MapViewTemplate.HOVER_HIT_RADIUS if hover else MapViewTemplate.HIT_RADIUS
        cell_x, cell_y = int(event.x // cell_size), int(event.y // cell_size)
        cell_radius = max(1, int(math.ceil(radius / cell_size)))
        nearest = None
        nearest_distance = radius * radius + 1
        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                for point in self.object_configuration_map_screen_grid.get((cell_x + dx, cell_y + dy), ()):
                    distance = (point[0] - event.x) ** 2 + (point[1] - event.y) ** 2
                    if distance < nearest_distance:
                        nearest, nearest_distance = point, distance
        return nearest if nearest_distance <= radius * radius else None

    def _draw_object_configuration_map(self):
        try:
            self._draw_object_configuration_map_content()
        finally:
            self._map_selection_draw()

    def _draw_object_configuration_map_content(self):
        self.object_configuration_map_screen_points = []
        self.object_configuration_map_screen_grid = {}
        canvas = self.object_configuration_map_canvas
        if canvas is None or not canvas.winfo_exists():
            return
        canvas.delete("all")
        width, height = max(2, canvas.winfo_width()), max(2, canvas.winfo_height())
        no_positions = not self.object_configuration_map_points

        min_x, max_x, min_z, max_z = self.object_configuration_map_bounds
        span_x, span_z = max_x - min_x, max_z - min_z
        padding = MapViewTemplate.MAP_MARGIN
        base_scale = min((width - 2 * padding) / span_x, (height - 2 * padding) / span_z)
        shared_scale = base_scale * self.object_configuration_map_shared_zoom
        image_width, image_height = span_x * shared_scale, span_z * shared_scale
        image_left = (width - image_width) / 2 + self.object_configuration_map_shared_pan_x
        image_top = (height - image_height) / 2 + self.object_configuration_map_shared_pan_y

        source = self.object_configuration_map_image_source
        if source is not None:
            self.object_configuration_map_image_tk, visible_left, visible_top = (
                MapViewTemplate.cached_viewport_photo(
                    source, image_left, image_top, image_width, image_height,
                    width, height, self.object_configuration_map_image_cache,
                )
            )
            if self.object_configuration_map_image_tk is not None:
                canvas.create_image(
                    visible_left, visible_top, image=self.object_configuration_map_image_tk,
                    anchor="nw", tags=("map_content", "map_background"),
                )
        canvas.create_rectangle(
            image_left, image_top, image_left + image_width, image_top + image_height,
            outline=MapViewTemplate.BACKGROUND_BORDER_COLOR,
            width=MapViewTemplate.BACKGROUND_BORDER_WIDTH,
            tags=("map_content", "map_background"),
        )
        if no_positions:
            canvas.create_text(
                width / 2, height / 2, text="No Position found.",
                fill=MapViewTemplate.EMPTY_TEXT_COLOR, tags=("map_content", "empty_text"),
            )

        candidates = self._object_map_view_candidates(
            image_left, image_top, image_width, image_height, width, height,
        )
        screen_points = []
        for prop_index, x, z, y, position_text, category in candidates:
            screen_x = image_left + ((x - min_x) / span_x) * image_width
            screen_y = image_top + ((max_z - z) / span_z) * image_height
            screen_points.append(
                (screen_x, screen_y, prop_index, x, z, y, position_text, category)
            )
        self.object_configuration_map_screen_points = screen_points

        # Render normal dots into one transparent bitmap. Hover, movement and
        # selection remain separate Canvas items and therefore stay interactive.
        dot_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dot_layer)
        zoom = self.object_configuration_map_shared_zoom
        lod_pixels = object_map_lod_pixels(zoom)
        seen = set()
        radius = max(1, int(MapViewTemplate.DOT_RADIUS))
        rendered = 0
        rendered_points = []
        for point in screen_points:
            key = (int(point[0] // lod_pixels), int(point[1] // lod_pixels), point[-1])
            if key in seen:
                continue
            seen.add(key)
            rendered_points.append(point)
            color = self.object_configuration_map_category_colors[point[-1]]
            x, y = point[0], point[1]
            draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=color, outline=MapViewTemplate.DOT_OUTLINE_COLOR,
            )
            rendered += 1
        # Only visible LOD representatives are selectable by hover/click/drag.
        self._object_map_build_screen_grid(rendered_points)
        self.object_configuration_map_dot_image = dot_layer
        self.object_configuration_map_dot_photo = ImageTk.PhotoImage(dot_layer)
        canvas.create_image(
            0, 0, image=self.object_configuration_map_dot_photo, anchor="nw",
            tags=("map_content", "map_point", "object_dot_layer"),
        )
        self.object_configuration_map_rendered_count = rendered

        self.object_configuration_map_hover_item = MapViewTemplate.create_hover_marker(canvas)
        if self.object_configuration_map_hover_point is not None:
            hovered = next(
                (point for point in rendered_points
                 if point[2:] == self.object_configuration_map_hover_point),
                None,
            )
            color = self.object_configuration_map_category_colors.get(hovered[-1]) if hovered else None
            MapViewTemplate.position_hover_marker(
                canvas, self.object_configuration_map_hover_item, hovered, color,
            )

        MapViewTemplate.draw_zoom_indicator(
            canvas, self.object_configuration_map_shared_zoom
        )

        total_visible = len(screen_points)
        self.object_configuration_map_info_var.set(
            f"{len(self.object_configuration_map_points)} Instances | "
            f"{total_visible} in viewport | {rendered} rendered | LOD {lod_pixels}px"
            + (f" | Background: {self.object_configuration_map_image_path.name}"
               if self.object_configuration_map_image_path else " | No background image found")
        )

    def _object_map_dot_movement_changed(self):
        enabled = bool(self.object_configuration_map_allow_dot_movement_var.get())
        if not enabled:
            MapViewTemplate.dot_drag_cancel(self.object_configuration_map_canvas)
        MapViewTemplate.set_dot_movement_cursor(self.object_configuration_map_canvas, enabled)
        MapViewTemplate.update_dot_movement_undo(self.object_configuration_map_canvas, enabled)

    def _object_map_drag_start(self, event):
        return MapViewTemplate.dot_drag_start(
            event,
            self.object_configuration_map_canvas,
            bool(self.object_configuration_map_allow_dot_movement_var.get()),
            lambda drag_event: self._nearest_object_configuration_map_point(drag_event, hover=True),
            lambda hit: hit[4] if len(hit) > 4 and isinstance(hit[4], str) and hit[4].startswith("#") else None,
        )

    def _object_map_drag_motion(self, event):
        return MapViewTemplate.dot_drag_motion(
            event, self.object_configuration_map_canvas,
            bool(self.object_configuration_map_allow_dot_movement_var.get()),
        )

    def _object_map_drag_end(self, event):
        return MapViewTemplate.dot_drag_end(
            event,
            self.object_configuration_map_canvas,
            bool(self.object_configuration_map_allow_dot_movement_var.get()),
            self._object_map_commit_drag,
        )

    def _object_map_commit_drag(self, event, hit):
        try:
            x,z=MapViewTemplate.world_from_event(
                event, self.object_configuration_map_canvas, self.object_configuration_map_bounds,
                self.object_configuration_map_shared_zoom,
                self.object_configuration_map_shared_pan_x,
                self.object_configuration_map_shared_pan_y,
            )
            if self._map_edit_session is None:
                cache, _session = self._map_session_current()
                self._map_edit_session = ObjectMapSession(cache)
            area=getattr(self,'_map_selection_area',None)
            selected=[]
            if area is not None:
                polygon = getattr(self, "_map_lasso_points", ())
                if len(polygon) >= 3:
                    selected = [
                        point for point in self.object_configuration_map_points
                        if MapViewTemplate.point_in_polygon(point[1], point[2], polygon)
                    ]
                else:
                    x1,x2,z1,z2=area
                    selected=[point for point in self.object_configuration_map_points
                              if x1<=point[1]<=x2 and z1<=point[2]<=z2]
            if selected:
                dx,dz=x-hit[3],z-hit[4]
                old_positions=[]
                for index,old_x,old_z,_y,position_text,_category in selected:
                    ordinal=self._map_edit_session.resolve_instance_ordinal(index,position_text)
                    if ordinal is None:raise ValueError('A selected object no longer exists.')
                    old_positions.append((ordinal,old_x,old_z))
                for ordinal,old_x,old_z in old_positions:
                    self._map_edit_session.move_instance(ordinal,old_x+dx,old_z+dz)
                moved_count=len(old_positions)
            else:
                ordinal=self._map_edit_session.resolve_instance_ordinal(hit[2],hit[6])
                if ordinal is None:raise ValueError('The selected object no longer exists.')
                old_positions=[(ordinal,hit[3],hit[4])]
                self._map_edit_session.move_instance(ordinal,x,z)
                moved_count=1
            self._density_session=self._map_edit_session
            self.object_configuration_map_points=self._map_preview_points(self._map_edit_session)
            self.object_configuration_map_hover_point=None
            if area is not None and selected:
                self._map_selection_area=(area[0]+dx,area[1]+dx,area[2]+dz,area[3]+dz)
            self._rebuild_object_configuration_map_legend()
            self._schedule_object_configuration_map_redraw()
            self.status_var.set(f'{moved_count} object(s) moved. Height recalculated; use Object Map Save to write changes.')
            def undo_move():
                for moved_ordinal,old_x,old_z in old_positions:
                    self._map_edit_session.move_instance(moved_ordinal,old_x,old_z)
                self._density_session=self._map_edit_session
                self.object_configuration_map_points=self._map_preview_points(self._map_edit_session)
                self.object_configuration_map_hover_point=None
                if area is not None and selected:self._map_selection_area=area
                self._rebuild_object_configuration_map_legend()
                self._schedule_object_configuration_map_redraw()
                self.status_var.set('Last object movement undone in RAM.')
            return undo_move
        except (ValueError,OSError) as exc:
            messagebox.showerror('Move Object',str(exc),parent=self.object_configuration_map_window)
        return "break"

    def _nearest_object_configuration_map_point(self, event, hover=False):
        return self._object_map_nearest_from_grid(event, hover=hover)

    def _on_object_configuration_map_motion(self, event):
        MapViewTemplate.set_dot_movement_cursor(
            self.object_configuration_map_canvas,
            bool(self.object_configuration_map_allow_dot_movement_var.get()), event,
        )
        if MapViewTemplate.middle_pan_active(self.object_configuration_map_canvas, event):
            return "break"
        nearest = self._nearest_object_configuration_map_point(event, hover=True)
        hover = nearest[2:] if nearest else None
        if hover != self.object_configuration_map_hover_point:
            self.object_configuration_map_hover_point = hover
            color = self.object_configuration_map_category_colors.get(nearest[-1]) if nearest else None
            MapViewTemplate.position_hover_marker(
                self.object_configuration_map_canvas, self.object_configuration_map_hover_item, nearest, color
            )

    def _on_object_configuration_map_leave(self, _event):
        MapViewTemplate.set_dot_movement_cursor(
            self.object_configuration_map_canvas,
            bool(self.object_configuration_map_allow_dot_movement_var.get()),
        )
        if self.object_configuration_map_hover_point is not None:
            self.object_configuration_map_hover_point = None
            MapViewTemplate.position_hover_marker(
                self.object_configuration_map_canvas, self.object_configuration_map_hover_item, None
            )

    def _on_object_configuration_map_click(self, event):
        self._map_selection_clear()
        nearest = self._nearest_object_configuration_map_point(event, hover=False)
        if nearest is None:
            return
        _sx, _sy, prop_index, x, z, y, position_text, category = nearest
        prop_path = (
            self.object_configuration_map_file_names[prop_index]
            if 0 <= prop_index < len(self.object_configuration_map_file_names)
            else ""
        )
        self.object_configuration_map_selection_var.set(
            f"Index {prop_index} | {category} | X {x:.3f} Z {z:.3f} Y {y:.3f}\n"
            f"{prop_path or 'No prop path found'} | Position: {position_text}"
        )

    def _tmc_ram_initialize(self, tab):
        self.rd3d_ram_cache = None
        self.tmc_ram_cache = None
        self.tmc_ram_thread = None
        self.tmc_ram_events = queue.Queue()
        self.tmc_ram_folder = None
        self.tmc_ram_progress = None
        # Internal cache state. It is shown in the table/status dialogs when
        # relevant, not as a loose label in the Object Configuration tab.
        self.tmc_ram_info = tk.StringVar(value="XML cache: no island loaded")
        self.after(75, self._tmc_ram_poll)

    def _tmc_ram_is_busy(self):
        # Includes the interval between worker exit and completion handling.
        return self.tmc_ram_thread is not None

    def _tmc_ram_begin(self, operation, worker):
        if self._tmc_ram_is_busy():
            return False
        if operation in ('Loading', 'RD3D Loading', 'Reload Loading'):
            phase = ('RD3D and TMC XML files' if operation == 'Reload Loading' else
                     'TMC XML files' if operation == 'Loading' else 'RD3D XML')
            self._xml_loading_show(f'Loading {phase} into memory...')
        if self.tmc_ram_progress is not None:
            self.tmc_ram_progress.set(0)
        self.tmc_ram_info.set(f"XML cache: {operation}...")
        self._set_running(True, "xml")
        def run():
            try:
                result = worker(lambda done, total: self.tmc_ram_events.put(
                    ('progress', (operation, done, total))))
                self.tmc_ram_events.put(('done', (operation, result, None)))
            except Exception as exc:
                self.tmc_ram_events.put(('done', (operation, None, str(exc))))
        self.tmc_ram_thread = threading.Thread(target=run, daemon=True, name='TmcXmlCache')
        self.tmc_ram_thread.start()
        return True

    def _tmc_ram_preload(self):
        if self._rd3d_ram_preload():
            return
        value = self.tmc_data_meshes_var.get().strip()
        if not value or self._tmc_ram_is_busy():
            return
        folder = Path(value)
        if not folder.is_dir():
            return
        if self.tmc_ram_folder == folder and self.tmc_ram_cache is not None:
            return
        try:
            workers = int(self.tmc_parallel_var.get().strip())
        except (TypeError, ValueError):
            workers = 4
        workers = max(1, min(workers, 32))
        self._tmc_ram_begin(
            'Loading', lambda progress: TmcXmlRamCache(folder, workers).load(progress)
        )

    def _tmc_ram_poll(self):
        # Only this main-thread after callback accesses Tk widgets/variables.
        self.after(75, self._tmc_ram_poll)
        for _ in range(100):
            try:
                kind, payload = self.tmc_ram_events.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                operation, done, total = payload
                if operation in ('Loading', 'RD3D Loading', 'Reload Loading'):
                    phase = ('RD3D and TMC cache phases' if operation == 'Reload Loading' else
                             'TMC XML files' if operation == 'Loading' else 'RD3D loading steps')
                    text = (f'Loading {phase}: {done}/{total} ({int(done * 100 / total)}%)'
                            if total else 'Scanning TMC XML files...')
                    self._xml_loading_show(text, done / total if total else None)
                fraction = done / total if total else 0
                if self.tmc_ram_progress is not None:
                    self.tmc_ram_progress.set(fraction)
                self.tmc_ram_info.set(f"XML cache: {operation} {done}/{total}")
                if operation == 'RD3D Density' and getattr(
                    self, '_density_save_progress_popup', False
                ):
                    text = (
                        f"Saving density: {done}/{total} "
                        f"({int(done * 100 / total)}%)"
                        if total else "Saving density..."
                    )
                    self._xml_loading_show(text, fraction if total else None)
                continue
            operation, result, error = payload
            self.tmc_ram_thread = None
            if not (self.worker and self.worker.is_alive()):
                self._set_running(False, 'xml')
            if error:
                self.tmc_ram_info.set(f"XML cache error: {error}")
                if operation in ('Loading', 'RD3D Loading', 'Reload Loading'):
                    self._xml_loading_finish(error)
                if operation == 'RD3D Loading':
                    self._density_open_pending = False
                    pending_job = getattr(self, '_density_open_poll_job', None)
                    if pending_job is not None:
                        try:
                            self.after_cancel(pending_job)
                        except (tk.TclError, ValueError):
                            pass
                        self._density_open_poll_job = None
                if operation == 'RD3D Density' and getattr(
                    self, '_density_save_progress_popup', False
                ):
                    self._density_save_progress_popup = False
                    self._xml_loading_finish(error)
                messagebox.showerror('XML cache', error)
                continue
            if self.tmc_ram_progress is not None:
                self.tmc_ram_progress.set(1)
            if operation in ('Profile Add', 'Profile Save', 'Profile Load'):
                self._object_profiles_complete(operation, result)
                continue
            if operation == 'Reload Loading':
                self._object_cache_reload_complete(result)
                continue
            if operation.startswith('RD3D '):
                try:
                    self._rd3d_ram_complete(operation, result)
                finally:
                    if operation == 'RD3D Loading':
                        self._xml_loading_finish()
                    elif operation == 'RD3D Density' and getattr(
                        self, '_density_save_progress_popup', False
                    ):
                        self._density_save_progress_popup = False
                        self._xml_loading_finish()
                continue
            if operation == 'Loading':
                # A different island may have been selected while loading.
                if str(result.folder) != self.tmc_data_meshes_var.get().strip():
                    self._tmc_ram_preload()
                    continue
                self.tmc_ram_cache = result
                self.tmc_ram_folder = result.folder
                self.object_configuration_table2_rows = [
                    (i, oid, old, len(refs), tk.StringVar(value=current))
                    for i, (oid, old, current, refs) in enumerate(result.groups)]
                self.tmc_ram_info.set(
                    f"XML cache: {len(result.documents)} files | {len(result.groups)} rows | {len(result.errors)} errors")
                self.object_configuration_table2_info_var.set(self.tmc_ram_info.get())
                if result.errors:
                    messagebox.showwarning('XML cache', 'Files excluded from editing:\n' + '\n'.join(result.errors[:10]))
                self._render_object_configuration_table_2()
                self._xml_loading_finish()
            else:
                if self.tmc_ram_folder != Path(self.tmc_data_meshes_var.get().strip()):
                    self._tmc_ram_preload()
                saved, changed, errors = result
                self.tmc_ram_info.set(f"Saved: {saved} files | {changed} changes | {len(errors)} errors")
                self.status_var.set(self.tmc_ram_info.get())
                if errors:
                    messagebox.showwarning('Objects Table 2',
                        f'Partial save: {saved} files saved. Failed files remain retryable.\n' + '\n'.join(errors[:10]))
                else:
                    messagebox.showinfo('Objects Table 2', self.tmc_ram_info.get())

    def _load_object_configuration_table_2_data(self):
        # Once loaded, opening the editor never scans or parses XML again.
        folder = Path(self.tmc_data_meshes_var.get().strip())
        if self.tmc_ram_cache is not None and self.tmc_ram_folder == folder:
            return True
        self._tmc_ram_preload()
        self.object_configuration_table2_info_var.set('Loading XML cache. Open the table when loading has completed.')
        return False

    def _save_object_configuration_table_2(self, notify=True):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning('Objects Table 2', 'A file operation is running. Save after it completes.')
            return False
        if self._tmc_ram_is_busy():
            return False
        cache = self.tmc_ram_cache
        if cache is None or cache.folder != Path(self.tmc_data_meshes_var.get().strip()):
            messagebox.showerror('Objects Table 2', 'Load the current island XML cache first.')
            return False
        # Read Tk variables once on the UI thread. The worker receives strings.
        values = [row[4].get().strip() for row in self.object_configuration_table2_rows]
        if any(not value for value in values):
            messagebox.showerror('Objects Table 2', 'Filename must not be empty.')
            return False
        return self._tmc_ram_begin('Saving', lambda progress: cache.save(values, progress))


    def _rd3d_ram_preload(self):
        value = self.rd3d_file_var.get().strip()
        if not value or self._tmc_ram_is_busy():
            return False
        path = Path(value)
        if self.rd3d_ram_cache is not None and self.rd3d_ram_cache.path == path:
            return False
        if not path.is_file():
            return False
        return self._tmc_ram_begin('RD3D Loading', lambda progress: Rd3dXmlRamCache(path).load(progress))

    def _object_cache_reload(self):
        if self._tmc_ram_is_busy() or (self.worker and self.worker.is_alive()):
            messagebox.showwarning('Reload Cache', 'A file operation is in progress.')
            return
        rd_value = self.rd3d_file_var.get().strip()
        tmc_value = self.tmc_data_meshes_var.get().strip()
        rd_path = Path(rd_value) if rd_value else None
        tmc_folder = Path(tmc_value) if tmc_value else None
        if rd_path is None and tmc_folder is None:
            messagebox.showwarning('Reload Cache', 'Select an RD3D XML file or a Meshes folder first.')
            return
        dirty = []
        rd = self.rd3d_ram_cache
        rows = self.object_configuration_table1_rows
        if rd is not None and (len(rows) != len(rd.values) or any(
            row[2].get().strip() != saved for row, saved in zip(rows, rd.values)
        )):
            dirty.append('Objects Table 1')
        tmc = self.tmc_ram_cache
        rows = self.object_configuration_table2_rows
        if tmc is not None:
            # Compare against working XML, not the initial groups: Save updates
            # working documents while the initial group values remain unchanged.
            entries = {path: tmc._entries(record['working'])
                       for path, record in tmc.documents.items()}
            if len(rows) != len(tmc.groups) or any(
                row[4].get().strip() != (entries[path][ordinal][1].text or '').strip()
                for row, (_, _, _, refs) in zip(rows, tmc.groups)
                for path, ordinal in refs
            ):
                dirty.append('Objects Table 2')
        if dirty and not messagebox.askyesno(
            'Reload Cache',
            'Discard unsaved changes in ' + ' and '.join(dirty)
            + ' and reload RD3D and TMC data from disk?',
        ):
            return
        def reload_worker(progress):
            result = {'rd3d': None, 'tmc': None, 'errors': [],
                      'rd_path': rd_path, 'tmc_folder': tmc_folder}
            for phase, path, cache_type in (
                (0, rd_path, Rd3dXmlRamCache), (1, tmc_folder, TmcXmlRamCache)
            ):
                if path is None:
                    progress(phase + 1, 2)
                    continue
                try:
                    valid = path.is_file() if phase == 0 else path.is_dir()
                    if not valid:
                        raise ValueError(f'Path not found: {path}')
                    def report(done, total, phase=phase):
                        progress(phase + (done / total if total else 0), 2)
                    result['rd3d' if phase == 0 else 'tmc'] = cache_type(path).load(report)
                except Exception as exc:
                    result['errors'].append(('RD3D' if phase == 0 else 'TMC') + ': ' + str(exc))
                progress(phase + 1, 2)
            return result
        self._tmc_ram_begin('Reload Loading', reload_worker)

    def _object_cache_reload_complete(self, result):
        errors = list(result['errors'])
        rd = result['rd3d']
        if rd is not None:
            if str(rd.path) != self.rd3d_file_var.get().strip():
                errors.append('RD3D selection changed during reload; result ignored.')
            else:
                self.rd3d_ram_cache = rd
                self.object_configuration_table1_rows = [
                    (i, old, tk.StringVar(value=current), count)
                    for i, (old, current, count) in enumerate(
                        zip(rd.original_values, rd.values, rd.usage))]
                self.object_configuration_table1_info_var.set(f'Objects: {len(rd.values)} FileNames | cache reloaded')
                self._render_object_configuration_table_1()
                self._rd3d_ram_preview_paths()
        tmc = result['tmc']
        if tmc is not None:
            if str(tmc.folder) != self.tmc_data_meshes_var.get().strip():
                errors.append('Meshes selection changed during reload; result ignored.')
            else:
                self.tmc_ram_cache = tmc
                self.tmc_ram_folder = tmc.folder
                self.object_configuration_table2_rows = [
                    (i, oid, old, len(refs), tk.StringVar(value=current))
                    for i, (oid, old, current, refs) in enumerate(tmc.groups)]
                self.object_configuration_table2_info_var.set(
                    f'{len(tmc.documents)} XML files | {len(tmc.groups)} rows | cache reloaded')
                self._render_object_configuration_table_2()
                errors.extend(tmc.errors)
        text = 'RD3D and TMC cache reload completed.'
        if errors:
            text += '\n\nWarnings/errors:\n' + '\n'.join(errors[:10])
        self.tmc_ram_info.set('Cache reload completed' + (' with warnings' if errors else ''))
        self.status_var.set(self.tmc_ram_info.get())
        self._xml_loading_finish('Cache reload completed with warnings' if errors else None)
        if errors:
            messagebox.showwarning('Reload Cache', text)
        else:
            messagebox.showinfo('Reload Cache', text)


    def _rd3d_ram_complete(self, operation, result):
        if operation == 'RD3D Map Edit':
            self._map_edit_complete(result)
            return
        if operation == 'RD3D Density':
            self._object_density_complete(result)
            return
        if operation == 'RD3D Loading':
            if str(result.path) != self.rd3d_file_var.get().strip():
                self._tmc_ram_preload()
                return
            self.rd3d_ram_cache = result
            self.object_configuration_table1_rows = [
                (index, old, tk.StringVar(value=current), count)
                for index, (old, current, count) in enumerate(
                    zip(result.original_values, result.values, result.usage))]
            self.object_configuration_table1_info_var.set(
                f'Objects: {len(result.values)} FileNames | original above, editable RAM value below')
            self._render_object_configuration_table_1()
            self.tmc_ram_info.set(f'RD3D cache: {len(result.values)} paths loaded')
            if getattr(self, "_object_table1_open_pending", False):
                # Run on the Tk event loop after the cache completion callback has
                # fully returned; do not require the user to press the button again.
                self.after_idle(self._open_object_configuration_table_1)
            if getattr(self, '_density_open_pending', False):
                self._density_open_pending = False
                # _xml_loading_finish() closes the loading status after 250 ms.
                # Open Change Density only afterwards, otherwise its init worker
                # makes the close callback see a busy state and the old status
                # window remains visible.
                self.after(350, self._open_object_density)
            self._tmc_ram_preload()
        else:
            self.tmc_ram_info.set(f'Objects Table 1 saved: {result} changed paths')
            self.status_var.set(self.tmc_ram_info.get())
            messagebox.showinfo('Objects Table 1', self.tmc_ram_info.get())
            # Do not rebuild Tk variables: edits made after the Save click must
            # remain visible and can be saved with the next snapshot.
            if self.rd3d_ram_cache.path != Path(self.rd3d_file_var.get().strip()):
                self._tmc_ram_preload()

    def _load_object_configuration_table_1_data(self):
        cache = self.rd3d_ram_cache
        if cache is not None and cache.path == Path(self.rd3d_file_var.get().strip()):
            return True
        self._rd3d_ram_preload()
        self.object_configuration_table1_info_var.set('RD3D cache is loading. Open the table after loading completes.')
        return False

    def _save_object_configuration_table_1(self, notify=True):
        if self._tmc_ram_is_busy() or (self.worker and self.worker.is_alive()):
            messagebox.showwarning('Objects Table 1', 'A file operation is in progress.')
            return False
        cache = self.rd3d_ram_cache
        if cache is None or cache.path != Path(self.rd3d_file_var.get().strip()):
            messagebox.showerror('Objects Table 1', 'Load the current RD3D cache first.')
            return False
        values = [row[2].get().strip() for row in self.object_configuration_table1_rows]
        if any(not value for value in values):
            messagebox.showerror('Objects Table 1', 'Path must not be empty.')
            return False
        return self._tmc_ram_begin('RD3D Saving', lambda progress: cache.save(values, progress))


    def _rd3d_ram_preview_paths(self):
        """Update an already open map from editable RAM paths, without XML reads."""
        values = [row[2].get().strip() for row in self.object_configuration_table1_rows]
        self.object_configuration_map_file_names = values
        points = []
        for index, x, z, y, position, _category in self.object_configuration_map_points:
            path = values[index] if 0 <= index < len(values) else ''
            category = self._classify_object_configuration_path(path)
            self._object_configuration_color_for_category(category)
            self.object_configuration_map_category_visible.setdefault(category, True)
            points.append((index, x, z, y, position, category))
        self.object_configuration_map_points = points
        window = self.object_configuration_map_window
        if window is not None and window.winfo_exists():
            self._rebuild_object_configuration_map_legend()
            self._schedule_object_configuration_map_redraw()

    def _build_xml_loading_indicator(self, parent, row):
        """Separate XML progress, never reuse the extraction progress bar."""
        if not hasattr(self, '_xml_loading_text'):
            self._xml_loading_text = tk.StringVar(master=self, value='XML memory cache: idle')
            self._xml_loading_bars = []
            self._xml_loading_window = None
            self._xml_loading_depth = 0
        frame = ctk.CTkFrame(parent, fg_color='transparent')
        frame.grid(row=row, column=0, padx=12, pady=(0, 10), sticky='ew')
        frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(frame, textvariable=self._xml_loading_text, anchor='w').grid(
            row=0, column=0, pady=(0, 4), sticky='ew')
        bar = ctk.CTkProgressBar(frame)
        bar.grid(row=1, column=0, sticky='ew')
        bar.set(0)
        self._xml_loading_bars.append(bar)

    def _xml_loading_show(self, text, fraction=None):
        """Main-thread only; use the shared themed progress status window."""
        if not StatusWindowTemplate.exists(self._xml_loading_window):
            self._xml_loading_window = StatusWindowTemplate.create(
                self, text=text, title="Loading XML into memory",
                heading="Loading XML into memory", progress=True,
                fraction=fraction, modal=False, topmost=True, force_paint=False,
            )
        else:
            StatusWindowTemplate.update(
                self._xml_loading_window, text=text, fraction=fraction
            )
        self._xml_loading_error = None
        self._xml_loading_text.set(text)
        for bar in self._xml_loading_bars:
            bar.stop()
            if fraction is None:
                bar.configure(mode='indeterminate')
                bar.start()
            else:
                bar.configure(mode='determinate')
                bar.set(max(0.0, min(1.0, fraction)))

    def _xml_loading_finish(self, error=None):
        if error is not None:
            self._xml_loading_error = error
            self._xml_loading_text.set(f'XML loading failed: {error}')
            if StatusWindowTemplate.exists(self._xml_loading_window):
                StatusWindowTemplate.update(
                    self._xml_loading_window,
                    text=f'XML loading failed: {error}', fraction=0,
                )
        self.after(250, lambda: self._xml_loading_close_if_idle(error))

    def _xml_loading_close_if_idle(self, error=None):
        if self._xml_loading_depth or self._tmc_ram_is_busy():
            # A follow-up worker may have started between finish() and this
            # callback. Retry instead of leaving the loading window orphaned.
            self.after(150, lambda: self._xml_loading_close_if_idle(error))
            return
        error = error or getattr(self, '_xml_loading_error', None)
        for bar in self._xml_loading_bars:
            bar.stop()
            bar.configure(mode='determinate')
            bar.set(0 if error else 1)
        if error is None:
            self._xml_loading_text.set('XML loading completed')
        if StatusWindowTemplate.exists(self._xml_loading_window):
            StatusWindowTemplate.close(self._xml_loading_window)
        self._xml_loading_window = None



    def _object_profiles_folder(self, number):
        if number not in (1, 2):
            raise ValueError('Invalid objects table.')
        return ProfileArchiveStore.folder(Path(self.CONFIG_FILE).resolve().parent, f'objects_table_{number}')

    def _object_profiles_mapname(self, number):
        # Prefer the data source actually owned by this table, not a stale A7M.
        if number == 1:
            value = self.rd3d_file_var.get().strip()
            if value:
                return Path(value).parent.name
        else:
            value = self.tmc_data_meshes_var.get().strip()
            if value:
                return Path(value).parent.name
        value = self.unpack_file_var.get().strip()
        if value:
            return Path(value).stem
        raise ValueError('Select an island first.')

    @staticmethod
    def _object_profiles_valid_name(name):
        return ProfileArchiveStore.validate_name(name)

    def _build_object_profiles(self, parent, number):
        if not hasattr(self, '_object_profile_controls'):
            self._object_profile_controls = {}
        component = ProfilesTemplate(
            parent, owner=lambda: self._object_profiles_owner(number),
            on_load=lambda name: self._object_profiles_load(number, name),
            on_add=lambda suffix: self._object_profiles_add(number, suffix),
            on_save=lambda name: self._object_profiles_save(number, name),
            on_delete=lambda name: self._object_profiles_delete(number, name),
            can_act=lambda: self._object_profiles_available(number),
            name_prefix=lambda: self._object_profiles_mapname(number),
            button_height=PopupTemplate.BUTTON_HEIGHT,
            secondary_text_color=PopupTemplate.SECONDARY_TEXT_COLOR,
        )
        component.grid(row=0, column=0, columnspan=5, padx=12, pady=(12, 4), sticky='ew')
        self._object_profile_controls[number] = dict(
            component=component, menu=component.menu, selection=component.selection,
            load=component.buttons['load'], delete=component.buttons['delete'],
            save=component.buttons['save'], catalog={}, loaded=None)
        self._object_profiles_refresh(number)

    def _object_profiles_available(self, number):
        if self._tmc_ram_is_busy() or (self.worker and self.worker.is_alive()):
            messagebox.showwarning('Object Profiles', 'A file operation is in progress.',
                                   parent=self._object_profiles_owner(number))
            return False
        return True

    def _object_profiles_owner(self, number):
        return getattr(self, f'object_configuration_table{number}_window', None) or self

    def _object_profiles_refresh(self, number, selected=None):
        controls = self._object_profile_controls[number]
        if not controls['component'].winfo_exists():
            return
        try:
            catalog = ProfileArchiveStore.catalog(self._object_profiles_folder(number))
        except OSError as exc:
            catalog = {}
            messagebox.showerror('Object Profiles', f'Cannot access profiles:\n{exc}',
                                 parent=self._object_profiles_owner(number))
        controls['catalog'] = catalog
        controls['component'].set_profiles(catalog, selected=selected)

    def _object_profiles_context(self, number):
        if self._tmc_ram_is_busy() or (self.worker and self.worker.is_alive()):
            raise ValueError('A file operation is in progress.')
        cache = self.rd3d_ram_cache if number == 1 else self.tmc_ram_cache
        source = self.rd3d_file_var.get().strip() if number == 1 else self.tmc_data_meshes_var.get().strip()
        if cache is None or not source or (cache.path if number == 1 else cache.folder) != Path(source):
            raise ValueError('Load the current island XML cache first.')
        return cache







    def _object_profiles_add(self, number, suffix):
        self._object_profiles_store_indices(number, suffix=suffix)

    def _object_profiles_save(self, number, name):
        self._object_profiles_store_indices(number, selected=name)

    def _object_profiles_delete(self, number, name):
        """Confirmation is provided once by ProfilesTemplate, default No."""
        controls = self._object_profile_controls[number]
        path = controls['catalog'].get(name)
        if path is None or not self._object_profiles_available(number):
            return
        try:
            path.unlink()
        except OSError as exc:
            messagebox.showerror('Object Profiles', str(exc), parent=self._object_profiles_owner(number))
            return
        controls['loaded'] = None
        self._object_profiles_refresh(number)
        self.status_var.set(f'Objects Table {number}: profile deleted: {name}')



    def _object_profiles_load(self, number, name):
        controls = self._object_profile_controls[number]
        path = controls['catalog'].get(name)
        if path is None:
            return
        try:
            cache = self._object_profiles_context(number)
            current = self._object_profiles_index_document(number)
            snapshot = dict(current['categories'])
            def load_profile(progress):
                progress(0, 1)
                document = json.loads(path.read_text(encoding='utf-8'))
                self._object_profiles_validate_indices(document, current, allow_other_map=True)
                progress(1, 1)
                return number, name, cache, snapshot, self._object_profile_categories(document), document
            self._tmc_ram_begin('Profile Load', load_profile)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Object Profiles', str(exc), parent=self._object_profiles_owner(number))

    def _object_profiles_complete(self, operation, result):
        if operation in ('Profile Add', 'Profile Save'):
            number, name = result
            self._object_profiles_refresh(number, name)
            self.status_var.set(f'Objects Table {number}: JSON profile saved: {name}')
            return
        number, name, cache, snapshot, categories, document = result
        controls = self._object_profile_controls[number]
        try:
            current_cache = self._object_profiles_context(number)
            current = self._object_profiles_index_document(number)
            if current_cache is not cache or current['categories'] != snapshot:
                raise ValueError('The island or table changed while loading. Select the profile again.')
            self._object_profiles_validate_indices(document, current, allow_other_map=True)
            if document.get('mapname') != current['mapname']:
                if not controls['component'].confirm_map_load(
                    document.get('mapname', ''), current['mapname']
                ):
                    controls['selection'].set(controls.get('loaded') or 'Select profile...')
                    controls['component']._sync_buttons()
                    return
                # Recheck after the modal dialog: no stale/concurrent changes.
                latest = self._object_profiles_index_document(number)
                if self._object_profiles_context(number) is not cache or latest != current:
                    raise ValueError('The table changed during confirmation. Load the profile again.')

            position = 2 if number == 1 else 4
            available_by_category = {}
            for category in set(categories.values()):
                choices = self._object_configuration_database_paths(category)
                if not choices:
                    raise ValueError(
                        f"No current Object paths are available for Category '{category}'."
                    )
                available_by_category[category] = choices
            for row in getattr(self, f'object_configuration_table{number}_rows'):
                category = categories[str(row[0])]
                row[position].set(random.choice(available_by_category[category]))
            getattr(self, f'_render_object_configuration_table_{number}')()
            if number == 1:
                self._rd3d_ram_preview_paths()
            controls['loaded'] = name
            controls['selection'].set(name)
            controls['component']._sync_buttons()
            self.status_var.set(f'Objects Table {number}: Category profile loaded with random Objects: {name} | RAM only; click Save')
            controls['component'].notify_loaded(name)
        except ValueError as exc:
            controls['selection'].set(controls.get('loaded') or 'Select profile...')
            messagebox.showerror('Object Profiles', str(exc), parent=self._object_profiles_owner(number))

    def _object_profiles_index_document(self, number):
        """Build a profile that stores only the Category for every table index."""
        rows = getattr(self, f'object_configuration_table{number}_rows')
        if not rows:
            raise ValueError('No object rows are loaded.')
        position = 2 if number == 1 else 4
        categories = {}
        identity = []
        for row in rows:
            key = str(row[0])
            if key in categories:
                raise ValueError('Duplicate table index: ' + key)
            object_path = row[position].get().strip()
            if not object_path:
                raise ValueError('Object paths must not be empty.')
            categories[key] = self._classify_object_configuration_path(object_path)
            identity.append((key, row[1]) if number == 1 else (key, row[1], row[2]))
        identity.sort(key=lambda item: item[0])
        signature = hashlib.sha256(
            json.dumps(identity, ensure_ascii=False).encode('utf-8')
        ).hexdigest()
        return dict(
            version=3,
            profile_mode='category_random',
            table=number,
            mapname=self._object_profiles_mapname(number),
            signature=signature,
            categories=categories,
        )

    def _object_profiles_validate_indices(self, document, current, allow_other_map=False):
        if not isinstance(document, dict) or document.get('version') not in (2, 3):
            raise ValueError('Unsupported JSON profile version.')
        if document.get('table') != current['table']:
            raise ValueError('This profile belongs to another objects table.')
        other_map = document.get('mapname') != current['mapname']
        if other_map and not allow_other_map:
            raise ValueError('This profile belongs to another map.')
        if not (other_map and allow_other_map) and document.get('signature') != current['signature']:
            raise ValueError('The original table indices do not match this profile.')
        stored = document.get('categories') if document.get('version') == 3 else document.get('values')
        if not isinstance(stored, dict) or set(stored) != set(current['categories']):
            raise ValueError('The profile indices do not match the current table.')
        if any(not isinstance(value, str) or not value.strip() for value in stored.values()):
            raise ValueError('Invalid or empty profile Categories.')

    def _object_profile_categories(self, document):
        """Return Category values, converting legacy v2 object-path profiles."""
        if document.get('version') == 3:
            return dict(document['categories'])
        return {
            key: self._classify_object_configuration_path(path)
            for key, path in document['values'].items()
        }

    def _object_profiles_store_indices(self, number, suffix=None, selected=None):
        try:
            self._object_profiles_context(number)
            controls = self._object_profile_controls[number]
            document = self._object_profiles_index_document(number)
            overwrite = selected is not None
            revision = None
            if overwrite:
                name = selected
                target = controls['catalog'].get(name)
                if target is None or controls['selection'].get() != name:
                    raise ValueError('Please select an existing JSON profile first.')
                revision = ProfileArchiveStore.revision(target)
            else:
                suffix = self._object_profiles_valid_name(suffix.strip())
                name = self._object_profiles_valid_name(document['mapname'] + '_' + suffix)
                folder = self._object_profiles_folder(number)
                catalog = ProfileArchiveStore.catalog(folder)
                if any(existing.casefold() == name.casefold() for existing in catalog):
                    raise ValueError('A profile with this name already exists. Use Save to overwrite it.')
                target = folder / (name + '.json')
            def store(progress):
                ProfileArchiveStore.write_json(target, document, overwrite=overwrite,
                    expected_revision=revision, progress=progress)
                return number, name
            operation = 'Profile Save' if overwrite else 'Profile Add'
            self._tmc_ram_begin(operation, controls['component'].track_worker(store, label='Saving Category profile'))
        except (OSError, ValueError) as exc:
            messagebox.showerror('Object Profiles', str(exc), parent=self._object_profiles_owner(number))

    def _schedule_density_open_when_ready(self):
        pending_job = getattr(self, '_density_open_poll_job', None)
        if pending_job is not None:
            return

        def poll():
            self._density_open_poll_job = None
            if not getattr(self, '_density_open_pending', False):
                return
            try:
                if not self.winfo_exists():
                    self._density_open_pending = False
                    return
            except (tk.TclError, AttributeError):
                self._density_open_pending = False
                return

            cache = self.rd3d_ram_cache
            selected_path = Path(self.rd3d_file_var.get().strip())
            if cache is not None and cache.path == selected_path:
                self._density_open_pending = False
                self.after_idle(self._open_object_density)
                return

            # If another XML operation delayed the preload, retry as soon as the
            # shared worker becomes idle. No information dialog is shown.
            if not self._tmc_ram_is_busy():
                started = self._rd3d_ram_preload()
                if not started and not selected_path.is_file():
                    self._density_open_pending = False
                    messagebox.showerror(
                        'Change Density',
                        'The selected RD3D XML file does not exist.',
                        parent=self,
                    )
                    return
            self._density_open_poll_job = self.after(150, poll)

        self._density_open_poll_job = self.after(0, poll)

    @staticmethod
    def _tmc_density_tag(node):
        return node.tag.rsplit('}', 1)[-1].lower() if isinstance(node.tag, str) else ''

    def _tmc_density_scan_tree(self, tree, source):
        instances = []
        for ground in tree.getroot().iter():
            if self._tmc_density_tag(ground) != 'groundobjects':
                continue
            for entry in list(ground):
                fields = {self._tmc_density_tag(child): child for child in list(entry)}
                filename_node = fields.get('filename')
                positions_node = fields.get('positionsxz')
                if filename_node is None or positions_node is None:
                    continue
                filename = (filename_node.text or '').strip()
                positions = (positions_node.text or '').split()
                if not filename or len(positions) % 2:
                    continue
                rotations = (fields.get('rotationsy').text or '').split() if fields.get('rotationsy') is not None else []
                coverages = (fields.get('coverages').text or '').split() if fields.get('coverages') is not None else []
                count = len(positions) // 2
                if rotations and len(rotations) != count:
                    raise ValueError(f'{source.name}: RotationsY count does not match PositionsXZ.')
                if coverages and len(coverages) != count:
                    raise ValueError(f'{source.name}: Coverages count does not match PositionsXZ.')
                category = get_category_for_object(filename, self.CONFIG_FILE)
                for index in range(count):
                    instances.append((category, ground, entry, fields, index, filename))
        return instances

    def _tmc_density_load_documents(self):
        folder = Path(self.tmc_data_meshes_var.get().strip())
        if not folder.is_dir():
            raise FileNotFoundError('Please select an existing TMC meshes folder first.')
        originals = sorted(folder.rglob('*_original.xml'), key=lambda path: str(path).casefold())
        if not originals:
            raise FileNotFoundError('No *_original.xml files were found in the selected meshes folder.')
        docs = {}
        errors = []
        for original in originals:
            patched = original.with_name(original.name[:-len('_original.xml')] + '_patched.xml')
            source = patched if patched.is_file() else original
            try:
                working = TmcXmlRamCache._parse(source)
                baseline = TmcXmlRamCache._parse(original)
                self._tmc_density_scan_tree(working, source)
                docs[original] = {'original': original, 'patched': patched, 'tree': working, 'baseline': baseline, 'dirty': False}
            except (OSError, ET.ParseError, UnicodeError, ValueError) as exc:
                errors.append(f'{source.name}: {exc}')
        if not docs:
            raise ValueError('No valid TMC XML files could be loaded.\n' + '\n'.join(errors[:10]))
        return folder, docs, errors

    def _open_tmc_density(self):
        window = getattr(self, '_tmc_density_window', None)
        if window is not None and window.winfo_exists():
            window.deiconify(); window.lift(); PopupTemplate.safe_activate(window)
            return
        status = self._show_object_operation_status('Loading TMC density data...')
        try:
            try:
                folder, docs, errors = self._tmc_density_load_documents()
            except (OSError, ET.ParseError, UnicodeError, ValueError) as exc:
                messagebox.showerror('Change Density (tmc)', str(exc))
                return
            self._tmc_density_folder = folder
            self._tmc_density_docs = docs
            self._tmc_density_errors = errors
            self._tmc_density_dirty = False
            self._tmc_density_percent = tk.StringVar(master=self, value='10')
            self._tmc_density_info = tk.StringVar(master=self)
            built = PopupTemplate.create_window(
                self, title='Change Density (tmc)', heading='Change Density (tmc)',
                close_command=self._close_tmc_density, maximize=True)
            self._tmc_density_window = window = built['window']
            window.grid_columnconfigure(0, weight=1)
            window.grid_rowconfigure(3, weight=1)
            bar = ctk.CTkFrame(window, fg_color='transparent')
            bar.grid(row=1, column=0, padx=18, pady=(0, 8), sticky='ew')
            ctk.CTkLabel(bar, text='Density reduction (%)').pack(side='left', padx=(0, 10))
            ctk.CTkEntry(bar, textvariable=self._tmc_density_percent, width=90).pack(side='left')
            ctk.CTkButton(bar, text='Reset', width=90,
                          command=self._confirm_tmc_density_reset).pack(side='right', padx=(8, 0))
            ctk.CTkButton(bar, text='Save', width=90,
                          command=self._save_tmc_density).pack(side='right')
            ctk.CTkLabel(window, textvariable=self._tmc_density_info, anchor='w').grid(
                row=2, column=0, padx=18, pady=(0, 8), sticky='ew')
            self._tmc_density_rows = ctk.CTkScrollableFrame(window)
            self._tmc_density_rows.grid(row=3, column=0, padx=18, pady=(0, 16), sticky='nsew')
            self._tmc_density_rows.grid_columnconfigure(0, weight=1)
            self._refresh_tmc_density()
        finally:
            self._hide_object_operation_status(status)

    def _tmc_density_category_instances(self):
        groups = {}
        for doc in self._tmc_density_docs.values():
            for item in self._tmc_density_scan_tree(doc['tree'], doc['patched']):
                groups.setdefault(item[0], []).append((doc, *item[1:]))
        return groups

    def _refresh_tmc_density(self):
        groups = self._tmc_density_category_instances()
        self._tmc_density_groups = groups
        frame = self._tmc_density_rows
        for widget in frame.winfo_children():
            widget.destroy()
        total = sum(len(items) for items in groups.values())
        suffix = ' | Unsaved changes' if self._tmc_density_dirty else ''
        error_text = f' | {len(self._tmc_density_errors)} file errors' if self._tmc_density_errors else ''
        self._tmc_density_info.set(
            f'{total} TMC GroundObject instances in {len(groups)} categories{error_text}{suffix}')
        for row, category in enumerate(sorted(groups, key=str.casefold)):
            ctk.CTkLabel(frame, text=category, anchor='w').grid(
                row=row, column=0, padx=(8, 12), pady=4, sticky='ew')
            ctk.CTkLabel(frame, text=str(len(groups[category])), width=80).grid(
                row=row, column=1, padx=4, pady=4)
            ctk.CTkButton(frame, text='- xx%', width=82,
                          command=lambda c=category: self._reduce_tmc_density(c)).grid(
                row=row, column=2, padx=4, pady=4)
            ctk.CTkButton(frame, text='Delete', width=82,
                          fg_color='#B3261E', hover_color='#8C1D18',
                          command=lambda c=category: self._delete_tmc_density(c)).grid(
                row=row, column=3, padx=(4, 8), pady=4)

    def _tmc_density_remove_refs(self, references):
        # Group by XML entry and remove descending indices from all parallel arrays.
        grouped = {}
        for doc, ground, entry, fields, index, filename in references:
            grouped.setdefault((id(doc), id(entry)), [doc, ground, entry, fields, []])[4].append(index)
        removed = 0
        for doc, ground, entry, fields, indices in grouped.values():
            positions = (fields['positionsxz'].text or '').split()
            rotations = (fields.get('rotationsy').text or '').split() if fields.get('rotationsy') is not None else []
            coverages = (fields.get('coverages').text or '').split() if fields.get('coverages') is not None else []
            for index in sorted(set(indices), reverse=True):
                if index * 2 + 1 >= len(positions):
                    continue
                del positions[index * 2:index * 2 + 2]
                if index < len(rotations): del rotations[index]
                if index < len(coverages): del coverages[index]
                removed += 1
                doc['dirty'] = True
            if positions:
                fields['positionsxz'].text = ' '.join(positions)
                if fields.get('rotationsy') is not None: fields['rotationsy'].text = ' '.join(rotations)
                if fields.get('coverages') is not None: fields['coverages'].text = ' '.join(coverages)
            else:
                ground.remove(entry)
        return removed

    def _reduce_tmc_density(self, category):
        thread = getattr(self, '_tmc_density_save_thread', None)
        if thread is not None and thread.is_alive():
            return
        try:
            percent = float(self._tmc_density_percent.get().strip().replace(',', '.'))
            if not 0 < percent <= 100:
                raise ValueError('Density reduction must be greater than 0 and at most 100.')
            refs = list(self._tmc_density_groups.get(category, ()))
            count = min(len(refs), max(1, round(len(refs) * percent / 100.0))) if refs else 0
            # Stable selection makes repeated preview/reset behavior reproducible.
            rng = random.Random(f'{category}|{len(refs)}|{percent:g}')
            selected = rng.sample(refs, count) if count else []
            removed = self._tmc_density_remove_refs(selected)
            self._tmc_density_dirty = self._tmc_density_dirty or bool(removed)
            self._refresh_tmc_density()
            self.status_var.set(f'TMC density reduced: {category}, -{removed} instances.')
        except ValueError as exc:
            messagebox.showerror('Change Density (tmc)', str(exc), parent=self._tmc_density_window)

    def _delete_tmc_density(self, category):
        thread = getattr(self, '_tmc_density_save_thread', None)
        if thread is not None and thread.is_alive():
            return
        refs = list(self._tmc_density_groups.get(category, ()))
        if not refs:
            return
        if not messagebox.askyesno(
            'Delete TMC objects',
            f'Delete all {len(refs)} instances of "{category}" from the TMC working copy?',
            parent=self._tmc_density_window, default='no', icon='warning'):
            return
        removed = self._tmc_density_remove_refs(refs)
        self._tmc_density_dirty = self._tmc_density_dirty or bool(removed)
        self._refresh_tmc_density()
        self.status_var.set(f'TMC category deleted: {category}, {removed} instances.')

    def _confirm_tmc_density_reset(self):
        thread = getattr(self, '_tmc_density_save_thread', None)
        if thread is not None and thread.is_alive():
            return
        if not messagebox.askyesno(
            'Reset TMC density',
            'Restore all TMC GroundObjects from the original XML files?\n\n'
            'All unsaved TMC density changes will be discarded.',
            parent=self._tmc_density_window, default='no', icon='warning'):
            return
        changed = False
        for doc in self._tmc_density_docs.values():
            # Reset only files that currently have a patch or were edited in RAM.
            if doc['dirty'] or doc['patched'].is_file():
                doc['tree'] = copy.deepcopy(doc['baseline'])
                doc['dirty'] = True
                changed = True
        self._tmc_density_dirty = changed
        self._refresh_tmc_density()
        self.status_var.set('TMC density reset to original data. Click Save to write the reset.')

    @staticmethod
    def _tmc_density_write_documents(documents, events):
        dirty = [doc for doc in documents if doc.get('dirty')]
        total = len(dirty)
        saved = 0
        for index, doc in enumerate(dirty, 1):
            patched = doc['patched']
            temporary = None
            try:
                fd, name = tempfile.mkstemp(
                    prefix='.tmc_density_', suffix='.xml', dir=patched.parent)
                os.close(fd)
                temporary = Path(name)
                doc['tree'].write(
                    temporary, encoding='utf-8', xml_declaration=False,
                    short_empty_elements=True)
                if not temporary.is_file() or temporary.stat().st_size == 0:
                    raise OSError(f'Empty temporary XML: {temporary.name}')
                # Validate before atomically replacing the previous patch.
                validated = TmcXmlRamCache._parse(temporary)
                os.replace(temporary, patched)
                doc['tree'] = validated
                doc['dirty'] = False
                saved += 1
                events.put(('progress', (index, total, patched.name)))
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
        return saved, total

    def _save_tmc_density(self):
        if getattr(self, '_tmc_density_save_thread', None) is not None:
            return
        dirty_docs = [doc for doc in self._tmc_density_docs.values() if doc.get('dirty')]
        if not dirty_docs:
            self._tmc_density_info.set('No TMC density changes to save.')
            return

        # Never serialize large TMC XML trees on Tk's main thread. Doing so can
        # block native message processing long enough for the packaged app to be
        # terminated without a Python traceback.
        self._tmc_density_save_events = queue.Queue()
        self._tmc_density_info.set(f'Saving 0/{len(dirty_docs)} changed TMC XML files...')
        self._xml_loading_show(f'Saving TMC density: 0/{len(dirty_docs)}', 0.0)
        self._set_running(True, 'xml')

        def worker():
            try:
                result = self._tmc_density_write_documents(
                    dirty_docs, self._tmc_density_save_events)
                self._tmc_density_save_events.put(('done', (result, None)))
            except Exception as exc:
                self._tmc_density_save_events.put(
                    ('done', (None, f'{type(exc).__name__}: {exc}')))

        self._tmc_density_save_thread = threading.Thread(
            target=worker, daemon=True, name='TmcDensitySave')
        self._tmc_density_save_thread.start()
        self.after(75, self._poll_tmc_density_save)

    def _poll_tmc_density_save(self):
        events = getattr(self, '_tmc_density_save_events', None)
        if events is None:
            return
        finished = None
        for _ in range(100):
            try:
                kind, payload = events.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                done, total, name = payload
                self._tmc_density_info.set(
                    f'Saving {done}/{total} changed TMC XML files: {name}')
                self._xml_loading_show(
                    f'Saving TMC density: {done}/{total}', done / total if total else 1.0)
            else:
                finished = payload
        if finished is None:
            thread = getattr(self, '_tmc_density_save_thread', None)
            if thread is not None and thread.is_alive():
                self.after(75, self._poll_tmc_density_save)
                return
            # A worker must always enqueue a terminal event. If it did not, give
            # the user a visible diagnostic instead of silently leaving a lock.
            finished = (None, 'TMC density save worker stopped without a result.')

        result, error = finished
        self._tmc_density_save_thread = None
        self._tmc_density_save_events = None
        self._set_running(False, 'xml')
        self._xml_loading_finish(error)
        if error:
            self._tmc_density_info.set(f'TMC density save failed: {error}')
            messagebox.showerror(
                'Change Density (tmc)', f'TMC density could not be saved:\n{error}',
                parent=self._tmc_density_window)
            return

        saved, total = result
        self._tmc_density_dirty = any(
            doc.get('dirty') for doc in self._tmc_density_docs.values())
        self.tmc_ram_cache = None
        self.tmc_ram_folder = None
        self._refresh_tmc_density()
        text = f'TMC density saved: {saved}/{total} changed XML files.'
        self.status_var.set(text)
        self.tmc_ram_info.set(text + ' Reload TMC data.')
        map_window = getattr(self, 'tmc_object_map_window', None)
        if map_window is not None and map_window.winfo_exists():
            self._close_tmc_object_map()

    def _close_tmc_density(self):
        window = getattr(self, '_tmc_density_window', None)
        thread = getattr(self, '_tmc_density_save_thread', None)
        if thread is not None and thread.is_alive():
            messagebox.showwarning(
                'Change Density (tmc)', 'TMC density files are currently being saved.',
                parent=window)
            return False
        if self._tmc_density_dirty:
            if not messagebox.askyesno(
                'Change Density (tmc)',
                'Discard all unsaved TMC density changes?',
                parent=window, default='no', icon='warning'):
                return False
        if window is not None and window.winfo_exists():
            window.destroy()
        self._tmc_density_window = None
        self._tmc_density_docs = None
        return True

    def _open_object_density(self):
        if not self._object_profiles_available(1):
            return
        if not self._load_object_configuration_table_1_data():
            # Remember the user's click. Cache loading continues in the existing
            # background worker; the popup opens automatically when data is ready.
            self._density_open_pending = True
            self._schedule_density_open_when_ready()
            return
        self._density_open_pending = False
        window = getattr(self, '_density_window', None)
        if window is not None and window.winfo_exists():
            if window.state() == 'iconic':
                window.deiconify()
            window.lift()
            PopupTemplate.request_focus(window, delay_ms=100)
            return
        self._density_session = getattr(self,'_map_edit_session',None)
        self._density_cache = self.rd3d_ram_cache
        owner = getattr(self, 'object_configuration_map_window', None)
        if owner is None or not owner.winfo_exists():
            owner = self
        built = PopupTemplate.create_window(owner,
            title='Change Density', heading='Change Density', close_command=self._object_density_close)
        self._density_window = window = built['window']
        window.transient(owner)
        PopupTemplate.apply_native_titlebar_controls(window)
        window.lift()
        PopupTemplate.request_focus(window, delay_ms=100)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(3, weight=1)
        bar = ctk.CTkFrame(window, fg_color='transparent')
        bar.grid(row=1,column=0,padx=18,pady=(0,8),sticky='ew')
        ctk.CTkLabel(bar,text='Density (%)').pack(side='left',padx=(0,10))
        self._density_percent = tk.StringVar(master=self,value='10')
        ctk.CTkEntry(bar,textvariable=self._density_percent,width=100).pack(side='left')
        self._density_info = tk.StringVar(master=self,
            value='Changes apply to all indices of a Type. Preview only until Save. Restore reloads original instances; click Save to keep them. Terrain/collisions are not validated.')
        ctk.CTkLabel(window,textvariable=self._density_info,justify='left',wraplength=950,
            text_color=PopupTemplate.SECONDARY_TEXT_COLOR).grid(row=2,column=0,padx=18,pady=(0,8),sticky='w')
        self._density_table = TemplateTable(window, (
            TableColumn('type','Category',anchor='w'),
            TableColumn('indices','Indices',width=360,anchor='w'),
            TableColumn('count','Count',width=100),
            TableColumn('density','Change Density',anchor='w')),
            row_builder=self._object_density_row)
        self._density_table.grid(row=3,column=0,padx=18,pady=(0,8),sticky='nsew')
        actions=ctk.CTkFrame(window,fg_color='transparent')
        actions.grid(row=4,column=0,padx=18,pady=(0,18),sticky='e')
        ctk.CTkButton(actions,text='Reset',width=110,
            fg_color=PopupTemplate.DANGER_BUTTON_FG_COLOR,
            hover_color=PopupTemplate.DANGER_BUTTON_HOVER_COLOR,
            command=self._confirm_object_density_reset).pack(side='left',padx=(0,8))
        ctk.CTkButton(actions,text='Save',width=110,
            command=lambda:self._object_density_run('save')).pack(side='left')
        self._object_density_refresh()
        self._object_density_run('init')

    def _object_density_row(self, row, data, _index):
        # Match content-sized header and body geometry; no column stretches.
        for col,column in enumerate(self._density_table.columns):
            row.grid_columnconfigure(col,weight=column.weight,
                                     minsize=column.width + 2*TemplateTable.CELL_PADX)
        font=ctk.CTkFont(size=TemplateTable.BODY_FONT_SIZE)
        index_lines = max(1, str(data['indices']).count('\n') + 1)
        row.configure(height=max(self._density_table.row_height, index_lines * 20 + 10))
        for col,key in ((0,'type'),(1,'indices'),(2,'count')):
            width=self._density_table.columns[col].width
            label = ctk.CTkLabel(
                row, text=str(data[key]), width=width, anchor='w', justify='left', font=font,
                wraplength=width if key == 'indices' else 0,
                text_color=data['color'] if key=='type' else TemplateTable.BODY_TEXT_COLOR,
            )
            label.grid(row=0,column=col,padx=TemplateTable.CELL_PADX,pady=5,sticky='nw')
        actions=ctk.CTkFrame(row,fg_color='transparent')
        actions.grid(row=0,column=3,padx=TemplateTable.CELL_PADX,pady=5,sticky='w')
        for label,increase in (('-',False),('+',True)):
            ctk.CTkButton(actions,text=label,width=self._density_button_width,height=28,
                command=lambda category=data['type'],up=increase:self._object_density_apply(category,up)).pack(side='left',padx=2)
        ctk.CTkButton(
            actions, text='Delete', width=72, height=28,
            fg_color=PopupTemplate.DANGER_BUTTON_FG_COLOR,
            hover_color=PopupTemplate.DANGER_BUTTON_HOVER_COLOR,
            command=lambda category=data['type']: self._object_density_delete(category),
        ).pack(side='left',padx=(6,2))

    def _object_density_refresh(self):
        window=getattr(self,'_density_window',None)
        if window is None or not window.winfo_exists():
            return
        session=self._density_session
        counts=session.usage if session is not None else self._density_cache.usage
        groups={}
        paths=session.paths() if session is not None else self._density_cache.values
        for index,path in enumerate(paths):
            category=self._classify_object_configuration_path(path)
            groups.setdefault(category,[]).append(index)
        self._density_groups=groups
        def format_indices(indices, per_line=12):
            values = [str(value) for value in indices]
            return '\n'.join(
                ', '.join(values[start:start + per_line])
                for start in range(0, len(values), per_line)
            )
        data=[dict(type=category,indices=format_indices(indices),
            count=sum(counts[i] for i in indices),color=self._object_configuration_picker_color(category))
            for category,indices in sorted(groups.items(), key=lambda item: item[0].casefold())]
        body_font=ctk.CTkFont(size=TemplateTable.BODY_FONT_SIZE)
        header_font=ctk.CTkFont(size=TemplateTable.HEADER_FONT_SIZE,weight=TemplateTable.HEADER_FONT_WEIGHT)
        def measured(key,title):
            longest=max((body_font.measure(str(row[key])) for row in data),default=0)
            return math.ceil(max(longest,header_font.measure(title)))+12
        button_font=ctk.CTkFont(size=TemplateTable.BUTTON_FONT_SIZE)
        self._density_button_width=math.ceil(max(button_font.measure('-'),button_font.measure('+')))+24
        # Minus, plus and the red Delete control, including button padding.
        action_width=max(
            2*(self._density_button_width+4) + 72 + 10,
            math.ceil(header_font.measure('Change Density'))+12,
        )
        columns=(TableColumn('type','Category',width=measured('type','Category'),anchor='w'),
                 TableColumn('indices','Indices',width=min(360, measured('indices','Indices')),anchor='w'),
                 TableColumn('count','Count',width=measured('count','Count'),anchor='w'),
                 TableColumn('density','Change Density',width=action_width,anchor='w'))
        table=self._density_table
        table.columns=columns
        for widget in table.header.winfo_children():
            widget.destroy()
        for col,column in enumerate(columns):
            table.header.grid_columnconfigure(col,weight=column.weight,
                minsize=column.width+2*TemplateTable.HEADER_PADX)
        table._build_header()
        table.set_rows(data)

    def _object_density_apply(self, category, increase):
        self._object_density_run('change',category,increase)

    def _object_density_delete(self, category):
        # Reuse the existing density preview path: -100% for this category.
        self._object_density_run(
            'change', category, increase=False, percent_override=100.0
        )

    def _confirm_object_density_reset(self):
        window=getattr(self,'_density_window',None)
        if window is None or not window.winfo_exists():
            return
        confirmed=messagebox.askyesno(
            'Reset Density',
            'Reset all density changes to the original object instances?\n\n'
            'The Object Map dots will not be recalculated until Save is clicked.',
            icon='warning',
            parent=window,
        )
        if confirmed:
            self._object_density_run('restore')

    def _object_density_run(self, action, category=None, increase=False, percent_override=None):
        try:
            cache=self._object_profiles_context(1)
            if cache is not self._density_cache:
                raise ValueError('The RD3D cache changed. Close and reopen Change Density.')
            percent=None
            if action=='change':
                percent=(float(percent_override) if percent_override is not None else float(self._density_percent.get().strip().replace(',','.')))
                if not 0 < percent <= 100:
                    raise ValueError('Density (%) must be greater than 0 and at most 100.')
            indices=tuple(self._density_groups.get(category,()))
            paths=self._map_edit_session.paths() if getattr(self,'_map_edit_session',None) is not None else cache.values
            categories={index:self._classify_object_configuration_path(path) for index,path in enumerate(paths)}
            session=getattr(self,'_map_edit_session',None)
            def work(progress):
                current=session.fork() if session is not None else ObjectMapSession(cache)
                if action=='init':
                    progress(1,1)
                    text='Density preview ready. Changes remain in memory until Save.'
                elif action=='change':
                    before,after=current.change(indices,percent,increase,progress)
                    text=f'{category}: {before} -> {after} instances. Preview only; click Save.'
                elif action=='restore':
                    progress(0,1)
                    current.restore()
                    progress(1,1)
                    text='Original instances reloaded from rd3d_original.xml. Preview only; click Save.'
                else:
                    current.save(progress)
                    text='Density saved to rd3d_patched.xml.'
                # Rebuilding all map points and redrawing the dots is intentionally
                # deferred until Save. +/- and Reset only update the in-memory session
                # and the counts shown in this window.
                points=current.map_points(categories) if action=='save' else None
                return current,points,text,action
            density_save_popup = action == 'save'
            if density_save_popup:
                self._xml_loading_show('Saving density to rd3d_patched.xml...', 0)
                self._density_save_progress_popup = True
            started = self._tmc_ram_begin('RD3D Density',work)
            if not started and density_save_popup:
                self._density_save_progress_popup = False
                self._xml_loading_finish('Density save could not be started.')
        except (ValueError,IndexError) as exc:
            messagebox.showerror('Change Density',str(exc),parent=self._density_window)

    def _object_density_complete(self,result):
        session,points,text,action=result
        if action=='save':
            # Save is the only density action that recalculates and redraws map dots.
            self._map_edit_complete((session,action,points))
        else:
            # Keep the edited XML/session in RAM without touching the Object Map.
            self._map_edit_session=session
            self._density_session=session
            self._density_cache=session.cache
            self._object_density_refresh()
            self.status_var.set(text)
            self.tmc_ram_info.set(text)
        window=getattr(self,'_density_window',None)
        if window is not None and window.winfo_exists():self._density_info.set(text)

    def _object_density_close(self):
        if self._tmc_ram_is_busy():
            messagebox.showwarning('Change Density','An XML operation is in progress.')
            return
        session = getattr(self, '_density_session', None)
        if session is not None and getattr(session, 'dirty', False):
            if not messagebox.askyesno(
                'Change Density',
                'There are unsaved RD3D changes in the shared Object Map/Density working copy.\n\n'
                'Closing Density and discarding will remove all unsaved RD3D Object Map/Density edits from RAM. '
                'TMC data is not affected.\n\nDiscard the unsaved RD3D changes?',
                parent=self._density_window,
                default='no',
            ):
                return
            self._rd3d_discard_working_copy(clear_cache=False)
        if self._density_window is not None and self._density_window.winfo_exists():
            self._density_window.destroy()
        self._density_window = None
        # Preview belongs to Object Map; closing this subwindow does not discard it.
