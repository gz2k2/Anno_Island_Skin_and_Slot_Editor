from __future__ import annotations
from app.backend.patch_store import PATCH_STORE

from app.functions.function_custom_content import (
    get_combined_categories,
    get_combined_object_database,
    get_combined_regions,
    get_category_for_object,
    get_regions_for_category,
    get_regions_for_object,
)

import tkinter as tk
from tkinter import filedialog, messagebox
import webbrowser
import app.backend.xml_backend as ET
from pathlib import Path

import customtkinter as ctk
from app.templates.template_popup import PopupTemplate
from PIL import Image, ImageTk

from app.config.config_gamedata import GLOBAL_AMBIENT_OPTIONS, VEGETATION_PROP_SET_OPTIONS
from app.config.config_rd3d import DEFAULT_RD3D_CATEGORY
from app.database.database_props import RD3D_OBJECT_DATABASE
from app.templates.template_map_view import MapViewTemplate
from app.ui.tabs.ui_tab_regional_settings import RegionalSettingsTabMixin
from app.ui.tabs.ui_tab_texture_settings import TextureSettingsTabMixin
from app.ui.tabs.ui_tab_slot_configuration import SlotConfigurationTabMixin
from app.ui.tabs.ui_tab_object_configuration import ObjectConfigurationTabMixin
from app.ui.tabs.ui_tab_material_sets import MaterialSetsTabMixin
from app.ui.tabs.ui_tab_finalize import FinalizeTabMixin
from app.ui.tabs.ui_tab_start import StartTabMixin
from app.ui.tabs.ui_tab_files_and_folders import FilesAndFoldersTabMixin
from app.ui.tabs.ui_tab_settings import SettingsTabMixin
from app.ui.tabs.ui_tab_helpers import HelpersTabMixin
from app.ui.tabs.ui_tab_custom_content import CustomContentTabMixin


class UIMixin(CustomContentTabMixin, HelpersTabMixin, SettingsTabMixin, MaterialSetsTabMixin, RegionalSettingsTabMixin, TextureSettingsTabMixin, SlotConfigurationTabMixin, ObjectConfigurationTabMixin, FinalizeTabMixin, StartTabMixin, FilesAndFoldersTabMixin):
    """CustomTkinter/Tk presentation layer for the Anno Island Reskinner.

    Business rules, XML processing, file operations, worker threads, and state
    mutation intentionally remain in the main App class.
    """
    def _show_update_available(self, remote_version):
        existing = getattr(self, "_update_available_window", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.deiconify()
                    existing.lift()
                    existing.focus_force()
                    return
            except (tk.TclError, AttributeError):
                self._update_available_window = None

        # Do not use PopupTemplate here. The update check can finish while the
        # main window is still completing its startup/map cycle. A transient
        # templated popup can therefore follow a temporary owner withdraw and
        # disappear immediately on Windows.
        window = ctk.CTkToplevel(self)
        self._update_available_window = window
        window.title("Update available")
        window.geometry("520x250")
        window.minsize(520, 250)
        window.resizable(False, False)
        window.attributes("-topmost", True)
        window.grid_columnconfigure(0, weight=1)

        def close_update_popup():
            if getattr(self, "_update_available_window", None) is window:
                self._update_available_window = None
            try:
                if window.winfo_exists():
                    window.destroy()
            except (tk.TclError, AttributeError):
                pass

        def show_update_popup():
            try:
                if not window.winfo_exists():
                    return
                window.deiconify()
                window.lift()
                window.attributes("-topmost", True)
                window.focus_force()
            except (tk.TclError, AttributeError):
                pass

        window.protocol("WM_DELETE_WINDOW", close_update_popup)
        ctk.CTkLabel(
            window,
            text="A new version is available",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(22, 14), sticky="w")
        ctk.CTkLabel(
            window,
            text=(
                f"Current version: {self.APP_VERSION}\n"
                f"New version: {remote_version}\n"
                f"Link: {self.UPDATE_PAGE_URL}"
            ),
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, padx=24, pady=(0, 18), sticky="ew")
        buttons = ctk.CTkFrame(window, fg_color="transparent")
        buttons.grid(row=2, column=0, padx=24, pady=(0, 22), sticky="e")
        ctk.CTkButton(
            buttons,
            text="Open download page",
            width=160,
            command=lambda: webbrowser.open(self.UPDATE_PAGE_URL),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            buttons,
            text="Close",
            width=90,
            fg_color="#555555",
            hover_color="#666666",
            command=close_update_popup,
        ).pack(side="left")

        # CustomTkinter adjusts the native Windows title bar after creation and
        # can briefly withdraw the toplevel. Re-show it after those callbacks.
        window.after_idle(show_update_popup)
        window.after(150, show_update_popup)
        window.after(500, show_update_popup)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text=self.APP_NAME, font=ctk.CTkFont(size=25, weight="bold")
        ).grid(row=0, column=0, padx=22, pady=(16, 2), sticky="w")
        ctk.CTkLabel(
            header,
            text="Unpack A7M/A7MINFO, apply XML patches, and repack island files",
            text_color="gray70",
        ).grid(row=1, column=0, padx=22, pady=(0, 14), sticky="w")

        ctk.CTkButton(
            header,
            text="Support me",
            width=110,
            height=34,
            fg_color="#8B3F32",
            hover_color="#A64B3B",
            command=lambda: webbrowser.open("http://ko-fi.com/gz2k2"),
        ).grid(row=0, column=1, rowspan=2, padx=(10, 6), pady=14, sticky="e")

        ctk.CTkButton(
            header,
            text="GitHub",
            width=100,
            height=34,
            fg_color="#000000",
            hover_color="#242424",
            border_width=1,
            border_color="#444444",
            command=lambda: webbrowser.open("https://github.com/gz2k2"),
        ).grid(row=0, column=2, rowspan=2, padx=(6, 22), pady=14, sticky="e")

        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=1, column=0, padx=18, pady=14, sticky="nsew")
        start_tab = self.tabs.add("Start")
        files_and_folders_tab = self.tabs.add("Files and Folders")
        regional_settings_tab = self.tabs.add("Regional Settings")
        slot_configuration_tab = self.tabs.add("Slot Configuration")
        object_configuration_tab = self.tabs.add("Object Configuration")
        texture_settings_tab = self.tabs.add("Texture Settings")
        finalize_tab = self.tabs.add("Finalize")
        material_sets_tab = self.tabs.add("Material Sets")
        custom_content_tab = self.tabs.add("Custom Content")
        exports_tab = self.tabs.add("Helpers")
        settings_tab = self.tabs.add("Settings")
        # Separate the editing workflow from the additional tools visually.
        material_tab_button = self.tabs._segmented_button._buttons_dict["Material Sets"]
        material_tab_button.grid_configure(padx=(18, 0))
        self._tools_tab_separator = tk.Frame(
            self.tabs._segmented_button,
            background="#A6A6A6",
            borderwidth=0,
            highlightthickness=0,
            takefocus=0,
        )
        self._tools_tab_separator.place(
            in_=material_tab_button, x=-10, rely=0.15, width=2, relheight=0.70,
        )
        # Separate Settings from Helpers using the same visual treatment.
        settings_tab_button = self.tabs._segmented_button._buttons_dict["Settings"]
        settings_tab_button.grid_configure(padx=(18, 0))
        self._settings_tab_separator = tk.Frame(
            self.tabs._segmented_button,
            background="#A6A6A6",
            borderwidth=0,
            highlightthickness=0,
            takefocus=0,
        )
        self._settings_tab_separator.place(
            in_=settings_tab_button, x=-10, rely=0.15, width=2, relheight=0.70,
        )
        self._build_start_tab(start_tab)
        self._build_files_and_folders_tab(files_and_folders_tab)
        self._build_regional_settings_tab(regional_settings_tab)
        self._build_slot_configuration_tab(slot_configuration_tab)
        self._build_object_configuration_tab(object_configuration_tab)
        self._build_texture_settings_tab(texture_settings_tab)
        self._build_finalize_tab(finalize_tab)
        self._build_material_sets_tab(material_sets_tab)
        self._build_custom_content_tab(custom_content_tab)
        self._build_helpers_tab(exports_tab)
        self._build_settings_tab(settings_tab)

        footer = ctk.CTkFrame(self, corner_radius=0)
        footer.grid(row=2, column=0, sticky="ew")
        ctk.CTkLabel(footer, textvariable=self.status_var).pack(side="left", padx=20, pady=7)


    def _build_gamedata_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)

        source = ctk.CTkFrame(tab)
        source.grid(row=0, column=0, padx=5, pady=(5, 10), sticky="ew")
        source.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(source, text="gamedata_original.xml:").grid(
            row=0, column=0, padx=(15, 8), pady=14, sticky="w"
        )
        ctk.CTkEntry(source, textvariable=self.gamedata_file_var).grid(
            row=0, column=1, padx=8, pady=14, sticky="ew"
        )
        ctk.CTkButton(source, text="Browse", width=110, command=self._select_gamedata_file).grid(
            row=0, column=2, padx=5, pady=14
        )
        ctk.CTkButton(source, text="Reload", width=110, command=self._load_gamedata_xml).grid(
            row=0, column=3, padx=5, pady=14
        )
        ctk.CTkLabel(source, text="mapname_original.xml:").grid(
            row=1, column=0, padx=(15, 8), pady=(0, 14), sticky="w"
        )
        ctk.CTkEntry(source, textvariable=self.mapname_file_var).grid(
            row=1, column=1, columnspan=3, padx=8, pady=(0, 14), sticky="ew"
        )
        ctk.CTkButton(source, text="Browse", width=110, command=self._select_mapname_file).grid(
            row=1, column=4, padx=(5, 15), pady=(0, 8)
        )
        object_actions = ctk.CTkFrame(source, fg_color="transparent")
        object_actions.grid(row=2, column=1, columnspan=3, padx=8, pady=(0, 14), sticky="w")
        ctk.CTkButton(
            object_actions, text="Objects", width=160, height=34,
            command=self._open_gamedata_objects,
        ).pack(side="left")
        ctk.CTkButton(
            object_actions, text="Open overview map", width=175, height=34,
            fg_color="#555555", hover_color="#666666",
            command=self._open_gamedata_overview_map,
        ).pack(side="left", padx=(8, 0))

        info = ctk.CTkFrame(tab)
        info.grid(row=1, column=0, padx=5, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(
            info,
            text=("GlobalAmbientName and VegetationPropSetName settings have moved to "
                  "the Regional Settings tab."),
            text_color="gray70", justify="left",
        ).pack(anchor="w", padx=15, pady=12)

    def _open_gamedata_objects(self):
        original = Path(self.gamedata_file_var.get().strip())
        if not original.is_file():
            messagebox.showerror("Gamedata Objects", "Please load an existing gamedata_original.xml file first.")
            return
        try:
            original_tree, _, _ = self._parse_xml_tolerant(original)
            original_rows = self._collect_gamedata_objects(original_tree.getroot())
        except (ET.ParseError, OSError, UnicodeError) as exc:
            messagebox.showerror("Gamedata Objects", f"gamedata_original.xml could not be read:\n{exc}")
            return

        patched = original.with_name("gamedata_patched.xml")
        patched_rows = None
        if patched.is_file():
            try:
                patched_tree, _, _ = self._parse_xml_tolerant(patched)
                patched_rows = self._collect_gamedata_objects(patched_tree.getroot())
            except (ET.ParseError, OSError, UnicodeError):
                patched_rows = None
        source_rows = patched_rows if patched_rows is not None else original_rows

        # GUID overview: unique GUIDs with an occurrence counter.
        guid_counts = {}
        guid_order = []
        for _object_id, guid in original_rows:
            if guid not in guid_counts:
                guid_counts[guid] = 0
                guid_order.append(guid)
            guid_counts[guid] += 1

        popup = PopupTemplate.create_window(
            self,
            title="Update available",
            heading="Update available",
            geometry="520x250",
            resizable=False,
            modal=False,
            close_command=window.destroy if False else None,
        )
        window = popup["window"]
        window.title("Gamedata Objects")
        window.geometry("1050x760")
        window.minsize(850, 560)
        window.transient(self)
        window.grid_columnconfigure((0, 1), weight=1, uniform="object_columns")
        window.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(window, text="Objects", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=18, pady=(16, 4), sticky="w"
        )

        guid_frame = ctk.CTkFrame(window)
        guid_frame.grid(row=1, column=0, columnspan=2, padx=18, pady=(4, 10), sticky="ew")
        guid_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(guid_frame, text="GUID overview", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=12, pady=(10, 4), sticky="w"
        )
        guid_text = "   |   ".join(f"{guid} ({guid_counts[guid]}x)" for guid in guid_order)
        ctk.CTkLabel(guid_frame, text=guid_text or "No GUIDs found", justify="left", anchor="w", wraplength=980).grid(
            row=1, column=0, padx=12, pady=(0, 10), sticky="ew"
        )

        mass_replace = ctk.CTkFrame(window)
        mass_replace.grid(row=2, column=0, columnspan=2, padx=18, pady=(0, 10), sticky="ew")
        mass_replace.grid_columnconfigure(1, weight=1)
        mass_replace.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(
            mass_replace, text="Mass Replace", font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, columnspan=5, padx=12, pady=(10, 6), sticky="w")
        ctk.CTkLabel(mass_replace, text="Original GUID:").grid(
            row=1, column=0, padx=(12, 6), pady=(0, 10), sticky="w")
        original_guid_var = tk.StringVar()
        ctk.CTkEntry(mass_replace, textvariable=original_guid_var).grid(
            row=1, column=1, padx=(0, 12), pady=(0, 10), sticky="ew")
        ctk.CTkLabel(mass_replace, text="New GUID:").grid(
            row=1, column=2, padx=(0, 6), pady=(0, 10), sticky="w")
        new_guid_var = tk.StringVar()
        ctk.CTkEntry(mass_replace, textvariable=new_guid_var).grid(
            row=1, column=3, padx=(0, 12), pady=(0, 10), sticky="ew")

        def mass_replace_guids():
            old_guid = original_guid_var.get().strip()
            new_guid = new_guid_var.get().strip()
            if not old_guid or not new_guid:
                messagebox.showerror(
                    "Mass Replace", "Please enter both Original GUID and New GUID.", parent=window)
                return
            if old_guid == new_guid:
                messagebox.showinfo("Mass Replace", "Original GUID and New GUID are identical.", parent=window)
                return

            replaced = 0
            for _id_var, guid_var in window.object_edit_rows:
                if guid_var.get().strip() == old_guid:
                    guid_var.set(new_guid)
                    replaced += 1

            if replaced:
                self.status_var.set(f"Mass Replace: {old_guid} -> {new_guid} ({replaced} entries)")
                messagebox.showinfo(
                    "Mass Replace",
                    f"Replaced {replaced} entr{'y' if replaced == 1 else 'ies'}.\n\n"
                    f"{old_guid} -> {new_guid}\n\n"
                    "Click Save to write the changes to the patched XML files.",
                    parent=window,
                )
            else:
                messagebox.showinfo(
                    "Mass Replace", f"GUID {old_guid} was not found in New values.", parent=window)

        ctk.CTkButton(
            mass_replace, text="Replace All", width=120, command=mass_replace_guids
        ).grid(row=1, column=4, padx=(0, 12), pady=(0, 10))

        ctk.CTkLabel(
            window,
            text=f"Objects: {len(original_rows)} ID/GUID entries | Unique GUIDs: {len(guid_order)}",
            text_color="gray70",
        ).grid(row=3, column=0, columnspan=2, padx=18, pady=(0, 8), sticky="w")

        left = ctk.CTkFrame(window)
        left.grid(row=4, column=0, padx=(18, 6), pady=(0, 18), sticky="nsew")
        right = ctk.CTkFrame(window)
        right.grid(row=4, column=1, padx=(6, 18), pady=(0, 18), sticky="nsew")
        for panel in (left, right):
            panel.grid_columnconfigure(0, weight=1)
            panel.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(left, text="Current values", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=10, pady=(10, 6), sticky="w")
        ctk.CTkLabel(right, text="New values", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=10, pady=(10, 6), sticky="w")
        self._gamedata_objects_header(left, 1)
        self._gamedata_objects_header(right, 1)

        left_table = ctk.CTkScrollableFrame(left, fg_color="transparent")
        left_table.grid(row=2, column=0, padx=5, pady=(0, 8), sticky="nsew")
        right_table = ctk.CTkScrollableFrame(right, fg_color="transparent")
        right_table.grid(row=2, column=0, padx=5, pady=(0, 8), sticky="nsew")
        for table in (left_table, right_table):
            table.grid_columnconfigure(0, weight=2)
            table.grid_columnconfigure(1, weight=1)

        for row_index, (object_id, guid) in enumerate(original_rows):
            ctk.CTkLabel(left_table, text=object_id, anchor="w").grid(row=row_index, column=0, padx=6, pady=3, sticky="ew")
            ctk.CTkLabel(left_table, text=guid, anchor="w").grid(row=row_index, column=1, padx=6, pady=3, sticky="ew")

        window.object_edit_rows = []
        window.object_original_rows = list(original_rows)
        self.gamedata_objects_window = window
        for row_index, (object_id, guid) in enumerate(source_rows):
            id_var = tk.StringVar(value=object_id)
            guid_var = tk.StringVar(value=guid)
            ctk.CTkLabel(
                right_table, textvariable=id_var, anchor="w", justify="left"
            ).grid(row=row_index, column=0, padx=6, pady=3, sticky="ew")
            ctk.CTkEntry(right_table, textvariable=guid_var).grid(row=row_index, column=1, padx=4, pady=2, sticky="ew")
            window.object_edit_rows.append((id_var, guid_var))

        # Synchronize both vertical scroll areas. Mouse wheel, scrollbar
        # arrows, scrollbar track clicks and dragging either scrollbar thumb
        # all move both tables to the same vertical fraction.
        left_canvas = left_table._parent_canvas
        right_canvas = right_table._parent_canvas

        sync_guard = {"active": False}

        def sync_from_left(first, last):
            if sync_guard["active"]:
                return
            sync_guard["active"] = True
            try:
                left_table._scrollbar.set(first, last)
                right_canvas.yview_moveto(first)
                right_table._scrollbar.set(first, last)
            finally:
                sync_guard["active"] = False

        def sync_from_right(first, last):
            if sync_guard["active"]:
                return
            sync_guard["active"] = True
            try:
                right_table._scrollbar.set(first, last)
                left_canvas.yview_moveto(first)
                left_table._scrollbar.set(first, last)
            finally:
                sync_guard["active"] = False

        # Replace CTkScrollableFrame's normal yscroll callbacks so a movement
        # originating from either canvas automatically mirrors to the other.
        left_canvas.configure(yscrollcommand=sync_from_left)
        right_canvas.configure(yscrollcommand=sync_from_right)

        def scrollbar_command(*args):
            if not args:
                return
            sync_guard["active"] = True
            try:
                if args[0] == "moveto" and len(args) > 1:
                    fraction = float(args[1])
                    left_canvas.yview_moveto(fraction)
                    right_canvas.yview_moveto(fraction)
                elif args[0] == "scroll" and len(args) > 2:
                    amount = int(args[1])
                    what = args[2]
                    left_canvas.yview_scroll(amount, what)
                    right_canvas.yview_scroll(amount, what)
            finally:
                sync_guard["active"] = False

            # Explicitly update both scrollbar thumbs after direct movement.
            left_first, left_last = left_canvas.yview()
            right_first, right_last = right_canvas.yview()
            left_table._scrollbar.set(left_first, left_last)
            right_table._scrollbar.set(right_first, right_last)

        left_table._scrollbar.configure(command=scrollbar_command)
        right_table._scrollbar.configure(command=scrollbar_command)

        def synchronized_wheel(event):
            if getattr(event, "num", None) == 4:
                units = -3
            elif getattr(event, "num", None) == 5:
                units = 3
            else:
                units = -1 * int(event.delta / 120) * 3 if event.delta else 0
            if units:
                scrollbar_command("scroll", units, "units")
            return "break"

        # Bind recursively so the wheel also works while the pointer is over an
        # entry/label inside either scrollable table, not only over the canvas.
        def bind_wheel_recursive(widget):
            widget.bind("<MouseWheel>", synchronized_wheel, add="+")
            widget.bind("<Button-4>", synchronized_wheel, add="+")
            widget.bind("<Button-5>", synchronized_wheel, add="+")
            for child in widget.winfo_children():
                bind_wheel_recursive(child)

        bind_wheel_recursive(left_table)
        bind_wheel_recursive(right_table)

        save_bar = ctk.CTkFrame(window, fg_color="transparent")
        save_bar.grid(row=5, column=0, columnspan=2, padx=18, pady=(0, 16), sticky="ew")
        save_bar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            save_bar,
            text="Reset",
            width=120,
            height=38,
            fg_color="#555555",
            hover_color="#666666",
            command=lambda: self._reset_gamedata_object_changes(window),
        ).grid(row=0, column=1, padx=(0, 8), sticky="e")
        ctk.CTkButton(
            save_bar,
            text="Save",
            width=150,
            height=38,
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self._save_gamedata_object_changes(window),
        ).grid(row=0, column=2, sticky="e")

    def _reset_gamedata_object_changes(self, window):
        """Remove only the Gamedata Objects popup patch scope."""
        try:
            original = Path(self.gamedata_file_var.get().strip())
            if original.is_file():
                PATCH_STORE.reset_scope("gamedata", original, "gamedata_objects")
            map_original = Path(self.mapname_file_var.get().strip())
            if map_original.is_file():
                PATCH_STORE.reset_scope("mapname", map_original, "gamedata_objects")
        except (OSError, ET.ParseError, UnicodeError, ValueError) as exc:
            messagebox.showerror("Gamedata Objects", str(exc), parent=window)
            return
        self._load_gamedata_objects_into_popup(window)
        self.status_var.set("Gamedata Objects patch reset; all other patches were preserved.")

    def _gamedata_objects_header(parent, row):
        header = ctk.CTkFrame(parent, corner_radius=4)
        header.grid(row=row, column=0, padx=5, pady=(0, 4), sticky="ew")
        header.grid_columnconfigure(0, weight=2)
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="ID", font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=0, padx=6, pady=6, sticky="ew")
        ctk.CTkLabel(header, text="GUID", font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=1, padx=6, pady=6, sticky="ew")

    @staticmethod
    def _gamedata_value_box(parent, row, title, variable):
        ctk.CTkLabel(parent, text=title, font=ctk.CTkFont(weight="bold")).grid(
            row=row, column=0, padx=18, pady=(5, 6), sticky="w"
        )
        ctk.CTkLabel(
            parent,
            textvariable=variable,
            anchor="w",
            justify="left",
            wraplength=410,
            fg_color=("gray86", "gray20"),
            corner_radius=6,
        ).grid(row=row + 1, column=0, padx=18, pady=(0, 18), ipady=10, sticky="ew")

    def _open_rd3d_map_window(self):
        if self.rd3d_map_window is not None and self.rd3d_map_window.winfo_exists():
            self.rd3d_map_window.deiconify()
            self.rd3d_map_window.transient(self)
            self.rd3d_map_window.attributes("-topmost", True)
            self.rd3d_map_window.lift()
            PopupTemplate.safe_activate(self.rd3d_map_window)
            self.rd3d_map_window.after(
                250,
                lambda: self._release_rd3d_map_topmost(self.rd3d_map_window),
            )
            self._schedule_rd3d_map_redraw()
            return

        popup = PopupTemplate.create_window(
            self,
            title="Update available",
            heading="Update available",
            geometry="520x250",
            resizable=False,
            modal=False,
            close_command=window.destroy if False else None,
        )
        window = popup["window"]
        self.rd3d_map_window = window
        window.transient(self)
        window.attributes("-topmost", True)
        window.title("RD3D Overview Map")
        window.geometry("1100x780")
        window.minsize(760, 520)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(4, weight=1)
        window.protocol("WM_DELETE_WINDOW", self._close_rd3d_map_window)
        window.bind("<Map>", self._update_rd3d_map_maximize_button, add="+")
        window.bind("<Configure>", self._update_rd3d_map_maximize_button, add="+")

        title_row = ctk.CTkFrame(window, fg_color="transparent")
        title_row.grid(row=0, column=0, padx=18, pady=(12, 4), sticky="ew")
        title_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            title_row,
            text="Overview map",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            title_row,
            text="Minimize",
            width=90,
            height=30,
            fg_color="#555555",
            hover_color="#666666",
            command=self._minimize_rd3d_map_window,
        ).grid(row=0, column=1, padx=(8, 4), sticky="e")

        self.rd3d_map_maximize_button = None
        ctk.CTkLabel(
            window,
            textvariable=self.rd3d_map_info_var,
            text_color="gray70",
            justify="left",
        ).grid(row=1, column=0, padx=18, pady=(0, 8), sticky="w")

        legend = ctk.CTkFrame(window, fg_color="transparent")
        legend.grid(row=2, column=0, padx=18, pady=(0, 8), sticky="w")
        self.rd3d_map_legend = legend
        self._rebuild_rd3d_map_category_buttons()
        controls_help = ctk.CTkFrame(window, corner_radius=8)
        controls_help.grid(row=3, column=0, padx=18, pady=(0, 8), sticky="ew")
        controls_help.grid_columnconfigure((0, 1), weight=1, uniform="map_help")

        ctk.CTkLabel(
            controls_help,
            text="Points only",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")
        ctk.CTkLabel(
            controls_help,
            text=("Mouse wheel: zoom points in 0.01 steps\n"
                  "Right mouse button + drag: pan points"),
            justify="left",
            text_color="gray70",
        ).grid(row=1, column=0, padx=12, pady=(0, 8), sticky="w")

        ctk.CTkLabel(
            controls_help,
            text="Background and points",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=1, padx=12, pady=(8, 2), sticky="w")
        ctk.CTkLabel(
            controls_help,
            text=("Ctrl + mouse wheel: zoom both in 0.01 steps\n"
                  "Ctrl + right mouse button + drag: pan both"),
            justify="left",
            text_color="gray70",
        ).grid(row=1, column=1, padx=12, pady=(0, 8), sticky="w")

        self.rd3d_map_canvas = tk.Canvas(
            window,
            bg="#151719",
            highlightthickness=0,
            borderwidth=0,
            cursor="crosshair",
        )
        self.rd3d_map_canvas.grid(row=4, column=0, padx=18, pady=(0, 8), sticky="nsew")
        self.rd3d_map_canvas.bind("<Configure>", self._schedule_rd3d_map_redraw)
        self.rd3d_map_canvas.bind("<Button-1>", self._on_rd3d_map_click)
        self.rd3d_map_canvas.bind("<Motion>", self._on_rd3d_map_motion)
        self.rd3d_map_canvas.bind("<Leave>", self._on_rd3d_map_leave)
        self.rd3d_map_canvas.bind("<MouseWheel>", self._on_rd3d_map_wheel)
        self.rd3d_map_canvas.bind("<Button-4>", self._on_rd3d_map_wheel)
        self.rd3d_map_canvas.bind("<Button-5>", self._on_rd3d_map_wheel)
        self.rd3d_map_canvas.bind("<ButtonPress-3>", self._start_rd3d_map_pan)
        self.rd3d_map_canvas.bind("<B3-Motion>", self._move_rd3d_map_pan)
        self.rd3d_map_canvas.bind("<ButtonRelease-3>", self._end_rd3d_map_pan)
        MapViewTemplate.bind_middle_pan(
            self.rd3d_map_canvas,
            self._start_rd3d_map_pan,
            self._move_rd3d_map_pan,
            self._end_rd3d_map_pan,
        )

        ctk.CTkLabel(
            window,
            textvariable=self.rd3d_map_selection_var,
            justify="left",
            anchor="w",
            wraplength=1000,
            fg_color=("gray86", "gray20"),
            corner_radius=6,
        ).grid(row=5, column=0, padx=18, pady=(0, 15), ipady=7, sticky="ew")
        PopupTemplate.schedule_activate(window, 50, focus=False)
        PopupTemplate.schedule_activate(window, 60, focus=True)
        window.after(100, self._schedule_rd3d_map_redraw)
        window.after(300, lambda: self._release_rd3d_map_topmost(window))

    def _minimize_rd3d_map_window(self):
        window = self.rd3d_map_window
        if window is None or not window.winfo_exists():
            return
        # A transient window may immediately follow its owner when iconified.
        # Temporarily remove the transient relationship for reliable minimize.
        window.transient("")
        window.iconify()

    def _toggle_rd3d_map_maximize(self):
        window = self.rd3d_map_window
        if window is None or not window.winfo_exists():
            return
        try:
            is_maximized = window.state() == "zoomed"
            window.state("normal" if is_maximized else "zoomed")
        except tk.TclError:
            # Fallback for window managers without the "zoomed" state.
            screen_width = window.winfo_screenwidth()
            screen_height = window.winfo_screenheight()
            if window.winfo_width() >= screen_width - 20:
                window.geometry("1100x780")
            else:
                window.geometry(f"{screen_width}x{screen_height}+0+0")
        self._update_rd3d_map_maximize_button()
        window.after(100, self._schedule_rd3d_map_redraw)

    def _update_rd3d_map_maximize_button(self, _event=None):
        button = self.rd3d_map_maximize_button
        window = self.rd3d_map_window
        if button is None or window is None or not window.winfo_exists():
            return
        try:
            button.configure(
                text="Restore" if window.state() == "zoomed" else "Maximize"
            )
        except tk.TclError:
            pass

    @staticmethod
    def _release_rd3d_map_topmost(window):
        try:
            if window is not None and window.winfo_exists():
                window.attributes("-topmost", False)
                window.lift()
        except tk.TclError:
            pass

    def _close_rd3d_map_window(self):
        if self.rd3d_map_after_id is not None:
            try:
                self.after_cancel(self.rd3d_map_after_id)
            except (ValueError, tk.TclError):
                pass
            self.rd3d_map_after_id = None
        if self.rd3d_map_window is not None:
            self.rd3d_map_window.destroy()
        self.rd3d_map_window = None
        self.rd3d_map_canvas = None
        self.rd3d_map_maximize_button = None
        self.rd3d_map_category_buttons.clear()

    def _rebuild_rd3d_map_category_buttons(self):
        legend = getattr(self, "rd3d_map_legend", None)
        if legend is None or not legend.winfo_exists():
            return
        for widget in legend.winfo_children():
            widget.destroy()
        self.rd3d_map_category_buttons.clear()
        self._rd3d_refresh_found_categories()
        for label in self.rd3d_found_categories:
            color = self._rd3d_category_color(label)
            visible = self.rd3d_map_category_visible.get(label, True)
            button = ctk.CTkButton(
                legend, text=f"     {label}", text_color=color if visible else "#6f757a",
                fg_color="#34383c" if visible else "#17191b", hover_color="#454b50",
                border_width=1, border_color=color, width=96, height=28,
                command=lambda category=label: self._toggle_rd3d_map_category(category),
            )
            button.pack(side="left", padx=(0, 8))
            self.rd3d_map_category_buttons[label] = button

    def _open_rd3d_database_window(self):
        window = self.rd3d_database_window
        if window is not None and window.winfo_exists():
            window.deiconify()
            window.transient(self)
            window.attributes("-topmost", True)
            window.lift()
            PopupTemplate.safe_activate(window)
            window.after(300, lambda: self._release_rd3d_database_topmost(window))
            return
        popup = PopupTemplate.create_window(
            self,
            title="Update available",
            heading="Update available",
            geometry="520x250",
            resizable=False,
            modal=False,
            close_command=window.destroy if False else None,
        )
        window = popup["window"]
        self.rd3d_database_window = window
        window.title("RD3D ObjectDatabase")
        window.geometry("1100x760")
        window.minsize(850, 560)
        window.transient(self)
        window.attributes("-topmost", True)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)
        window.protocol("WM_DELETE_WINDOW", self._close_rd3d_database_window)
        ctk.CTkLabel(window, text="ObjectDatabase", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(16, 4), sticky="w")
        ctk.CTkLabel(
            window, text=f"Database entries: {len(get_combined_object_database(self.CONFIG_FILE))} | Source: database_props.py + custom_objects.json",
            text_color="gray70"
        ).grid(row=1, column=0, padx=18, pady=(0, 8), sticky="w")
        panel = ctk.CTkFrame(window)
        panel.grid(row=2, column=0, padx=18, pady=(4, 16), sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        header = ctk.CTkFrame(panel, corner_radius=4)
        header.grid(row=0, column=0, padx=5, pady=(5, 0), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        self.rd3d_database_type_header = ctk.CTkButton(
            header, text="Type ▲", width=190, height=30, anchor="w",
            fg_color="transparent", hover_color=("gray80", "gray28"),
            text_color=("gray10", "gray90"), font=ctk.CTkFont(weight="bold"),
            command=lambda: self._sort_rd3d_database("type"),
        )
        self.rd3d_database_type_header.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.rd3d_database_path_header = ctk.CTkButton(
            header, text="Path", height=30, anchor="w",
            fg_color="transparent", hover_color=("gray80", "gray28"),
            text_color=("gray10", "gray90"), font=ctk.CTkFont(weight="bold"),
            command=lambda: self._sort_rd3d_database("path"),
        )
        self.rd3d_database_path_header.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        table = ctk.CTkScrollableFrame(panel, fg_color="transparent", height=300)
        table.grid(row=1, column=0, padx=5, pady=(2, 5), sticky="nsew")
        table.grid_columnconfigure(0, weight=1)
        self.rd3d_database_table = table
        self.rd3d_database_sort_column = "type"
        self.rd3d_database_sort_reverse = False
        self._render_rd3d_database()
        PopupTemplate.schedule_activate(window, 50, focus=False)
        PopupTemplate.schedule_activate(window, 60, focus=True)
        window.after(300, lambda: self._release_rd3d_database_topmost(window))

    def _sort_rd3d_database(self, column):
        if self.rd3d_database_sort_column == column:
            self.rd3d_database_sort_reverse = not self.rd3d_database_sort_reverse
        else:
            self.rd3d_database_sort_column = column
            self.rd3d_database_sort_reverse = False
        self._render_rd3d_database()

    def _render_rd3d_database(self):
        table = self.rd3d_database_table
        if table is None or not table.winfo_exists():
            return
        for widget in table.winfo_children():
            widget.destroy()
        rows = [(self._classify_prop(path), path)
                for _source_category, path, _count in get_combined_object_database(self.CONFIG_FILE)]
        if self.rd3d_database_sort_column == "path":
            rows.sort(key=lambda item: item[1].casefold(), reverse=self.rd3d_database_sort_reverse)
        else:
            rows.sort(key=lambda item: (item[0].casefold(), item[1].casefold()),
                      reverse=self.rd3d_database_sort_reverse)
        arrow = "▼" if self.rd3d_database_sort_reverse else "▲"
        self.rd3d_database_type_header.configure(
            text=f"Type {arrow}" if self.rd3d_database_sort_column == "type" else "Type")
        self.rd3d_database_path_header.configure(
            text=f"Path {arrow}" if self.rd3d_database_sort_column == "path" else "Path")
        for row_index, (object_type, path) in enumerate(rows):
            category_color = self._rd3d_category_color(object_type)
            shade = ("gray92", "gray17") if row_index % 2 == 0 else ("gray86", "gray21")
            row = ctk.CTkFrame(table, fg_color=shade, corner_radius=4, height=42)
            row.grid(row=row_index, column=0, padx=1, pady=1, sticky="ew")
            row.grid_propagate(False)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=object_type, text_color=category_color, width=190, anchor="w").grid(
                row=0, column=0, padx=5, pady=5, sticky="w")
            path_var = tk.StringVar(value=path)
            ctk.CTkEntry(row, textvariable=path_var, height=28, state="disabled",
                         border_width=0, fg_color="transparent").grid(
                row=0, column=1, padx=5, pady=5, sticky="ew")

    @staticmethod
    def _release_rd3d_database_topmost(window):
        try:
            if window is not None and window.winfo_exists():
                window.attributes("-topmost", False)
                window.lift()
        except tk.TclError:
            pass

    def _close_rd3d_database_window(self):
        if self.rd3d_database_window is not None and self.rd3d_database_window.winfo_exists():
            self.rd3d_database_window.destroy()
        self.rd3d_database_window = None
        self.rd3d_database_table = None

    def _open_rd3d_objects_window(self):
        window = self.rd3d_objects_window
        if window is not None and window.winfo_exists():
            window.deiconify()
            window.transient(self)
            window.attributes("-topmost", True)
            window.lift()
            PopupTemplate.safe_activate(window)
            window.after(300, lambda: self._release_rd3d_objects_topmost(window))
            return

        popup = PopupTemplate.create_window(
            self,
            title="Update available",
            heading="Update available",
            geometry="520x250",
            resizable=False,
            modal=False,
            close_command=window.destroy if False else None,
        )
        window = popup["window"]
        self.rd3d_objects_window = window
        window.title("RD3D Objects")
        window.geometry("1100x760")
        window.minsize(850, 560)
        window.transient(self)
        window.attributes("-topmost", True)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(4, weight=1)
        window.protocol("WM_DELETE_WINDOW", self._close_rd3d_objects_window)

        ctk.CTkLabel(window, text="Objects", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(16, 4), sticky="w")
        replace_bar = ctk.CTkFrame(window)
        replace_bar.grid(row=1, column=0, padx=18, pady=(4, 10), sticky="ew")
        replace_bar.grid_columnconfigure(1, weight=1)
        replace_bar.grid_columnconfigure(3, weight=1)
        current_types = self._rd3d_replace_from_values()
        database_types = self._rd3d_replace_to_values()
        window.rd3d_replace_from_var = tk.StringVar(value=current_types[0] if current_types else "")
        window.rd3d_replace_to_var = tk.StringVar(value=database_types[0] if database_types else "")
        ctk.CTkLabel(replace_bar, text="Replace From:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=(12, 6), pady=10, sticky="w")
        window.rd3d_replace_from_menu = ctk.CTkOptionMenu(
            replace_bar, variable=window.rd3d_replace_from_var,
            values=current_types or ["No types found"], dynamic_resizing=False
        )
        window.rd3d_replace_from_menu.grid(
            row=0, column=1, padx=(0, 12), pady=10, sticky="ew"
        )
        ctk.CTkLabel(replace_bar, text="To:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=(0, 6), pady=10, sticky="w")
        ctk.CTkOptionMenu(replace_bar, variable=window.rd3d_replace_to_var, values=database_types or ["No types found"], dynamic_resizing=False).grid(row=0, column=3, padx=(0, 12), pady=10, sticky="ew")
        ctk.CTkButton(replace_bar, text="OK", width=90, height=32, command=lambda: self._replace_rd3d_object_type_paths(window)).grid(row=0, column=4, padx=(0, 12), pady=10)

        ctk.CTkLabel(window, text="Values", font=ctk.CTkFont(weight="bold")).grid(
            row=2, column=0, padx=18, pady=(4, 4), sticky="w")
        ctk.CTkLabel(
            window,
            text=("Each Path shows the original value on the first line. "
                  "The second line is the editable value from rd3d_patched.xml; "
                  "if no patched file/value exists it starts with the original path."),
            text_color="#e0a84f", justify="left", wraplength=1000,
        ).grid(row=3, column=0, padx=18, pady=(0, 8), sticky="w")

        panel = ctk.CTkFrame(window)
        panel.grid(row=4, column=0, padx=18, pady=(4, 10), sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(panel, corner_radius=4)
        header.grid(row=0, column=0, padx=5, pady=(5, 0), sticky="ew")
        header.grid_columnconfigure(3, weight=1)
        for col, (title, width) in enumerate((
            ("Index", 52), ("Type", 150), ("Count", 58), ("Path", 0), ("", 90)
        )):
            ctk.CTkLabel(
                header, text=title, width=width, anchor="w",
                font=ctk.CTkFont(weight="bold")
            ).grid(row=0, column=col, padx=5, pady=7, sticky="ew")

        self.rd3d_current_table = ctk.CTkScrollableFrame(
            panel, fg_color="transparent", height=300
        )
        self.rd3d_current_table.grid(row=1, column=0, padx=5, pady=(2, 5), sticky="nsew")
        self.rd3d_current_table.grid_columnconfigure(0, weight=1)
        # Compatibility aliases: the popup now has only one table.
        self.rd3d_new_table = None
        self.rd3d_file_table = self.rd3d_current_table
        self._render_rd3d_file_names()

        actions = ctk.CTkFrame(window, fg_color="transparent")
        actions.grid(row=5, column=0, padx=18, pady=(0, 16), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(
            actions, text="Reset", width=120, height=38,
            fg_color="#555555", hover_color="#666666",
            command=self._reset_rd3d_object_paths,
        ).grid(row=0, column=1, padx=(0, 8), sticky="e")
        ctk.CTkButton(
            actions, text="Save", width=150, height=38,
            font=ctk.CTkFont(weight="bold"),
            command=self._save_rd3d_object_paths,
        ).grid(row=0, column=2, sticky="e")

        PopupTemplate.schedule_activate(window, 50, focus=False)
        PopupTemplate.schedule_activate(window, 60, focus=True)
        window.after(300, lambda: self._release_rd3d_objects_topmost(window))

    def _refresh_rd3d_replace_from_menu(self, window):
        """Rebuild From types from the current editable object paths."""
        if window is None or not window.winfo_exists():
            return
        menu = getattr(window, "rd3d_replace_from_menu", None)
        variable = getattr(window, "rd3d_replace_from_var", None)
        if menu is None or variable is None:
            return
        current_types = self._rd3d_replace_from_values()
        values = current_types or ["No types found"]
        previous_type = self._rd3d_replace_from_type(variable.get().strip())
        menu.configure(values=values)
        matching = next(
            (value for value in current_types
             if self._rd3d_replace_from_type(value) == previous_type),
            None,
        )
        variable.set(matching if matching is not None else values[0])

    @staticmethod
    def _release_rd3d_objects_topmost(window):
        try:
            if window is not None and window.winfo_exists():
                window.attributes("-topmost", False)
                window.lift()
        except tk.TclError:
            pass

    def _close_rd3d_objects_window(self):
        if self.rd3d_objects_window is not None and self.rd3d_objects_window.winfo_exists():
            self.rd3d_objects_window.destroy()
        self.rd3d_objects_window = None
        self.rd3d_current_table = None
        self.rd3d_new_table = None
        self.rd3d_file_table = None

    def _configure_rd3d_table_sync(self):
        # Kept for compatibility with older calls. Only one table remains.
        table = self.rd3d_current_table
        if table is None:
            return
        try:
            canvas = table._parent_canvas
            canvas.bind("<MouseWheel>", self._on_rd3d_table_wheel)
            canvas.bind("<Button-4>", self._on_rd3d_table_wheel)
            canvas.bind("<Button-5>", self._on_rd3d_table_wheel)
        except (AttributeError, tk.TclError):
            pass

    def _sync_rd3d_table_scroll(self, *args):
        table = self.rd3d_current_table
        if table is None or not args:
            return "break"
        canvas = table._parent_canvas
        if args[0] == "moveto":
            canvas.yview_moveto(float(args[1]))
        elif args[0] == "scroll":
            canvas.yview_scroll(int(args[1]), args[2])
        return "break"

    def _on_rd3d_table_wheel(self, event):
        table = self.rd3d_current_table
        if table is None:
            return "break"
        if getattr(event, "num", None) == 4:
            units = -1
        elif getattr(event, "num", None) == 5:
            units = 1
        else:
            units = -1 if event.delta > 0 else 1
        table._parent_canvas.yview_scroll(units, "units")
        return "break"

    def _render_rd3d_file_names(self):
        table = self.rd3d_current_table
        if table is None:
            return
        for widget in table.winfo_children():
            widget.destroy()

        for row_index, (index, original, variable, count) in enumerate(self.rd3d_file_names):
            category = self._classify_prop(variable.get().strip())
            category_color = self._rd3d_category_color(category)
            shade = ("gray92", "gray17") if row_index % 2 == 0 else ("gray86", "gray21")

            row = ctk.CTkFrame(table, fg_color=shade, corner_radius=4, height=76)
            row.grid(row=row_index, column=0, padx=1, pady=1, sticky="ew")
            row.grid_propagate(False)
            row.grid_columnconfigure(3, weight=1)

            ctk.CTkLabel(row, text=str(index), width=52, anchor="w").grid(
                row=0, column=0, rowspan=2, padx=5, pady=5, sticky="nsw")
            ctk.CTkLabel(
                row, text=category, text_color=category_color, width=150, anchor="w"
            ).grid(row=0, column=1, rowspan=2, padx=5, pady=5, sticky="nsw")
            ctk.CTkLabel(row, text=str(count), width=58, anchor="w").grid(
                row=0, column=2, rowspan=2, padx=5, pady=5, sticky="nsw")

            original_var = tk.StringVar(value=original)
            ctk.CTkEntry(
                row, textvariable=original_var, height=28, state="disabled",
                border_width=0, fg_color="transparent"
            ).grid(row=0, column=3, padx=5, pady=(5, 2), sticky="ew")
            ctk.CTkEntry(
                row, textvariable=variable, height=28, border_width=1
            ).grid(row=1, column=3, padx=5, pady=(2, 5), sticky="ew")
            ctk.CTkButton(
                row, text="Change", width=80, height=30,
                command=lambda target_variable=variable: self._open_rd3d_change_window(target_variable),
            ).grid(row=0, column=4, rowspan=2, padx=(5, 8), pady=8, sticky="e")

        self.after_idle(self._configure_rd3d_table_sync)
        self.after_idle(lambda: self._sync_rd3d_table_scroll("moveto", "0.0"))

    def _open_rd3d_change_window(self, target_variable):
        """Open a filtered ObjectDatabase selector for one editable RD3D path."""
        popup = PopupTemplate.create_window(
            self.rd3d_objects_window or self,
            title="Change RD3D Object",
            heading="Change Object",
            geometry="1050x720",
            min_size=(800, 520),
            resizable=True,
            modal=False,
            close_command=lambda: self._close_rd3d_change_window(),
            add_header=True,
            maximize=True,
        )
        window = popup["window"]
        window.title("Change RD3D Object")
        window.geometry("1050x720")
        window.minsize(800, 520)
        window.transient(self.rd3d_objects_window or self)
        window.attributes("-topmost", True)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(window, text="Change Object", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(16, 8), sticky="w")

        filter_bar = ctk.CTkFrame(window)
        filter_bar.grid(row=1, column=0, padx=18, pady=(0, 10), sticky="ew")
        filter_bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(filter_bar, text="Type:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(12, 8), pady=10, sticky="w")

        database_rows = [(self._classify_prop(path), path)
                         for _source_category, path, _count in get_combined_object_database(self.CONFIG_FILE)]
        types = sorted({object_type for object_type, _path in database_rows}, key=str.casefold)
        filter_var = tk.StringVar(value="All")
        ctk.CTkOptionMenu(
            filter_bar, variable=filter_var, values=["All"] + types, dynamic_resizing=False,
            command=lambda _value: self._render_rd3d_change_database(window),
        ).grid(row=0, column=1, padx=(0, 8), pady=10, sticky="ew")

        ctk.CTkLabel(filter_bar, text="Search:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=2, padx=(8, 8), pady=10, sticky="w")
        search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(
            filter_bar, textvariable=search_var,
            placeholder_text="Filter Type or Path...", width=300,
        )
        search_entry.grid(row=0, column=3, padx=(0, 12), pady=10, sticky="ew")
        filter_bar.grid_columnconfigure(3, weight=1)
        window.search_debounce_job = None
        search_var.trace_add(
            "write", lambda *_args: self._schedule_rd3d_change_filter(window)
        )

        ctk.CTkLabel(
            filter_bar,
            text="Search tip: Multiple terms are combined with AND. Each term may match either Type or Path (e.g. 'bush jun').",
            text_color="gray65", anchor="w", justify="left", font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, columnspan=4, padx=(12, 12), pady=(0, 8), sticky="w")

        header = ctk.CTkFrame(window, corner_radius=4)
        header.grid(row=2, column=0, padx=18, pady=(0, 0), sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="Type", width=190, anchor="w",
                     font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=5, pady=7, sticky="w")
        ctk.CTkLabel(header, text="Path", anchor="w",
                     font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, padx=5, pady=7, sticky="ew")

        table = ctk.CTkScrollableFrame(window, fg_color="transparent")
        table.grid(row=3, column=0, padx=18, pady=(2, 16), sticky="nsew")
        table.grid_columnconfigure(0, weight=1)
        window.database_rows = database_rows
        window.filter_var = filter_var
        window.search_var = search_var
        window.database_table = table
        window.target_variable = target_variable
        self._render_rd3d_change_database(window)

        PopupTemplate.schedule_activate(window, 50, focus=False)
        PopupTemplate.schedule_activate(window, 60, focus=True)
        window.after(300, lambda: self._release_rd3d_change_topmost(window))

    def _schedule_rd3d_change_filter(self, window):
        """Debounce the text filter so the database is refreshed 500 ms after typing stops."""
        if window is None or not window.winfo_exists():
            return
        job = getattr(window, "search_debounce_job", None)
        if job is not None:
            try:
                window.after_cancel(job)
            except tk.TclError:
                pass
        window.search_debounce_job = window.after(
            500, lambda: self._run_rd3d_change_filter(window)
        )

    def _run_rd3d_change_filter(self, window):
        if window is None or not window.winfo_exists():
            return
        window.search_debounce_job = None
        self._render_rd3d_change_database(window)

    @staticmethod
    def _matches_filter_terms(object_type, path, search_text):
        """AND-search whitespace-separated terms across Type and Path together.

        Each term may match either column and partial matches are allowed.
        Example: 'bush jun' matches Type 'Bushes Jungle'.
        """
        terms = [term.casefold() for term in (search_text or "").split() if term.strip()]
        if not terms:
            return True
        searchable = f"{object_type} {path}".casefold()
        return all(term in searchable for term in terms)

    @staticmethod
    def _highlight_filter_text(parent, text, search_text, *, width=0, color=None):
        """Render text with every case-insensitive search hit highlighted."""
        box = tk.Text(
            parent, height=1, wrap="none", borderwidth=0, highlightthickness=0,
            relief="flat", cursor="arrow", padx=0, pady=0, takefocus=0,
        )
        try:
            bg = parent._apply_appearance_mode(parent.cget("fg_color"))
        except (AttributeError, tk.TclError):
            bg = "#242424"
        box.configure(
            background=bg, foreground=color or "#dce4ee",
            insertbackground=bg, selectbackground=bg, selectforeground=color or "#dce4ee",
            font=("Segoe UI", 12),
        )
        box.insert("1.0", text)
        terms = [term for term in (search_text or "").split() if term.strip()]
        if terms:
            haystack = text.casefold()
            for term in terms:
                folded = term.casefold()
                start = 0
                while True:
                    pos = haystack.find(folded, start)
                    if pos < 0:
                        break
                    end = pos + len(folded)
                    box.tag_add("search_hit", f"1.{pos}", f"1.{end}")
                    start = end
            box.tag_configure("search_hit", foreground="#FFD54F", background="#5B4A12")
        box.configure(state="disabled")
        if width:
            box.configure(width=width)
        return box

    def _render_rd3d_change_database(self, window):
        table = getattr(window, "database_table", None)
        if table is None or not table.winfo_exists():
            return
        for widget in table.winfo_children():
            widget.destroy()

        selected_type = window.filter_var.get().strip() or "All"
        search_text = window.search_var.get().strip().casefold()
        rows = window.database_rows
        if selected_type != "All":
            rows = [row for row in rows if row[0] == selected_type]
        if search_text:
            rows = [
                row for row in rows
                if self._matches_filter_terms(row[0], row[1], search_text)
            ]
        rows = sorted(rows, key=lambda item: (item[0].casefold(), item[1].casefold()))

        for row_index, (object_type, path) in enumerate(rows):
            category_color = self._rd3d_category_color(object_type)
            shade = ("gray92", "gray17") if row_index % 2 == 0 else ("gray86", "gray21")
            row = ctk.CTkFrame(table, fg_color=shade, corner_radius=4, height=42)
            row.grid(row=row_index, column=0, padx=1, pady=1, sticky="ew")
            row.grid_propagate(False)
            row.grid_columnconfigure(1, weight=1)
            self._highlight_filter_text(
                row, object_type, search_text, width=24, color=category_color
            ).grid(row=0, column=0, padx=5, pady=7, sticky="ew")
            self._highlight_filter_text(
                row, path, search_text
            ).grid(row=0, column=1, padx=5, pady=7, sticky="ew")
            ctk.CTkButton(
                row, text="Select", width=85, height=30,
                command=lambda selected_path=path: self._select_rd3d_change_path(window, selected_path),
            ).grid(row=0, column=2, padx=(5, 8), pady=5, sticky="e")

    def _select_rd3d_change_path(self, window, path):
        """Apply the selected database path only to the row that opened the selector."""
        target_variable = getattr(window, "target_variable", None)
        if target_variable is None:
            return
        target_variable.set(path)
        self._rd3d_refresh_found_categories()
        self._render_rd3d_file_names()
        self._rebuild_rd3d_map_category_buttons()
        self._schedule_rd3d_map_redraw()
        self.status_var.set(f"RD3D object path changed: {path}")
        window.destroy()
        if self.rd3d_objects_window is not None and self.rd3d_objects_window.winfo_exists():
            self.rd3d_objects_window.attributes("-topmost", True)
            self.rd3d_objects_window.lift()
            self.rd3d_objects_PopupTemplate.safe_activate(window)
            self.rd3d_objects_window.after(250, lambda: self._release_rd3d_objects_topmost(self.rd3d_objects_window))

    @staticmethod
    def _release_rd3d_change_topmost(window):
        try:
            if window is not None and window.winfo_exists():
                window.attributes("-topmost", False)
                window.lift()
        except tk.TclError:
            pass

    def _on_rd3d_map_wheel(self, event):
        if getattr(event, "num", None) == 4:
            direction = 1
        elif getattr(event, "num", None) == 5:
            direction = -1
        else:
            direction = 1 if event.delta > 0 else -1

        canvas = self.rd3d_map_canvas
        center_x = canvas.winfo_width() / 2
        center_y = canvas.winfo_height() / 2

        if self._rd3d_ctrl_pressed(event):
            # Ctrl + wheel zooms background and points together in 0.01 steps.
            old_zoom = self.rd3d_map_shared_zoom
            new_zoom = round(old_zoom + direction * 0.01, 2)
            new_zoom = max(0.25, min(12.00, new_zoom))
            if new_zoom == old_zoom:
                return "break"
            ratio = new_zoom / old_zoom
            self.rd3d_map_shared_pan_x = (
                event.x - center_x
                - (event.x - center_x - self.rd3d_map_shared_pan_x) * ratio
            )
            self.rd3d_map_shared_pan_y = (
                event.y - center_y
                - (event.y - center_y - self.rd3d_map_shared_pan_y) * ratio
            )
            self.rd3d_map_shared_zoom = new_zoom
        else:
            # Wheel alone zooms only the point layer in 0.01 steps.
            old_zoom = self.rd3d_map_zoom
            new_zoom = round(old_zoom + direction * 0.01, 2)
            new_zoom = max(0.25, min(12.00, new_zoom))
            if new_zoom == old_zoom:
                return "break"
            ratio = new_zoom / old_zoom
            self.rd3d_map_pan_x = (
                event.x - center_x
                - (event.x - center_x - self.rd3d_map_pan_x) * ratio
            )
            self.rd3d_map_pan_y = (
                event.y - center_y
                - (event.y - center_y - self.rd3d_map_pan_y) * ratio
            )
            self.rd3d_map_zoom = new_zoom

        self._schedule_rd3d_map_redraw()
        return "break"

    def _start_rd3d_map_pan(self, event):
        shared = self._rd3d_ctrl_pressed(event)
        if shared:
            pan_x = self.rd3d_map_shared_pan_x
            pan_y = self.rd3d_map_shared_pan_y
        else:
            pan_x = self.rd3d_map_pan_x
            pan_y = self.rd3d_map_pan_y
        self.rd3d_map_pan_start = (
            event.x,
            event.y,
            pan_x,
            pan_y,
            shared,
        )
        self.rd3d_map_canvas.configure(cursor="fleur")
        return "break"

    def _move_rd3d_map_pan(self, event):
        if self.rd3d_map_pan_start is None:
            return "break"
        start_x, start_y, pan_x, pan_y, shared = self.rd3d_map_pan_start
        new_x = pan_x + event.x - start_x
        new_y = pan_y + event.y - start_y
        if shared:
            # Ctrl + right drag pans background and points together.
            self.rd3d_map_shared_pan_x = new_x
            self.rd3d_map_shared_pan_y = new_y
        else:
            # Right drag alone pans only the points.
            self.rd3d_map_pan_x = new_x
            self.rd3d_map_pan_y = new_y
        self._schedule_rd3d_map_redraw()
        return "break"

    def _end_rd3d_map_pan(self, _event):
        self.rd3d_map_pan_start = None
        self.rd3d_map_canvas.configure(cursor="crosshair")
        return "break"

    def _schedule_rd3d_map_redraw(self, _event=None):
        if self.rd3d_map_canvas is None or not self.rd3d_map_canvas.winfo_exists():
            return
        if self.rd3d_map_after_id is not None:
            try:
                self.after_cancel(self.rd3d_map_after_id)
            except (ValueError, tk.TclError):
                pass
        self.rd3d_map_after_id = self.after(80, self._draw_rd3d_map)

    def _draw_rd3d_map_background(self, canvas, left, top, width, height):
        source = self.rd3d_map_image_source
        if source is None or width <= 1 or height <= 1:
            return
        target_width = max(1, round(width))
        target_height = max(1, round(height))
        resized = source.resize(
            (target_width, target_height),
            Image.Resampling.LANCZOS,
        )
        self.rd3d_map_image_tk = ImageTk.PhotoImage(resized)
        canvas.create_image(
            left + width / 2,
            top + height / 2,
            image=self.rd3d_map_image_tk,
            anchor="center",
            tags=("rd3d_background",),
        )

    def _draw_rd3d_map(self):
        self.rd3d_map_after_id = None
        if self.rd3d_map_canvas is None or not self.rd3d_map_canvas.winfo_exists():
            return
        canvas = self.rd3d_map_canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 200)
        height = max(canvas.winfo_height(), 200)
        margin = 28

        if not self.rd3d_map_points:
            canvas.create_text(
                width / 2,
                height / 2,
                text="No position data loaded",
                fill="#8b9298",
                font=("Segoe UI", 12),
            )
            return

        xs = [point[1] for point in self.rd3d_map_points]
        zs = [point[2] for point in self.rd3d_map_points]
        min_x, max_x = min(xs), max(xs)
        min_z, max_z = min(zs), max(zs)
        range_x = max(max_x - min_x, 1.0)
        range_z = max(max_z - min_z, 1.0)
        drawable_w = max(width - 2 * margin, 1)
        drawable_h = max(height - 2 * margin, 1)
        base_scale = min(drawable_w / range_x, drawable_h / range_z)
        base_used_w = range_x * base_scale
        base_used_h = range_z * base_scale

        # Shared transform controlled by Ctrl+wheel and Ctrl+right-drag.
        shared_zoom = self.rd3d_map_shared_zoom
        shared_used_w = base_used_w * shared_zoom
        shared_used_h = base_used_h * shared_zoom
        shared_offset_x = (
            (width - shared_used_w) / 2 + self.rd3d_map_shared_pan_x
        )
        shared_offset_y = (
            (height - shared_used_h) / 2 + self.rd3d_map_shared_pan_y
        )

        self._draw_rd3d_map_background(
            canvas,
            shared_offset_x,
            shared_offset_y,
            shared_used_w,
            shared_used_h,
        )
        canvas.create_rectangle(
            shared_offset_x,
            shared_offset_y,
            shared_offset_x + shared_used_w,
            shared_offset_y + shared_used_h,
            outline="#394047",
            width=1,
        )

        # Point-only transform is applied on top of the shared transform.
        zoom = self.rd3d_map_zoom
        point_scale = base_scale * shared_zoom * zoom
        point_used_w = shared_used_w * zoom
        point_used_h = shared_used_h * zoom
        shared_center_x = shared_offset_x + shared_used_w / 2
        shared_center_y = shared_offset_y + shared_used_h / 2
        point_offset_x = (
            shared_center_x - point_used_w / 2 + self.rd3d_map_pan_x
        )
        point_offset_y = (
            shared_center_y - point_used_h / 2 + self.rd3d_map_pan_y
        )

        screen_points = []
        radius = max(
            MapViewTemplate.DOT_MIN_RADIUS,
            min(
                MapViewTemplate.DOT_MAX_RADIUS,
                MapViewTemplate.DOT_RADIUS * zoom ** MapViewTemplate.DOT_ZOOM_EXPONENT,
            ),
        )
        visible_count = 0
        for prop_index, x, z, y, position_text in self.rd3d_map_points:
            prop_path = ""
            if 0 <= prop_index < len(self.rd3d_file_names):
                prop_path = self.rd3d_file_names[prop_index][2].get().strip()
            category = self._classify_prop(prop_path)
            visible_category = (
                category
                if category in self.rd3d_map_category_visible
                else DEFAULT_RD3D_CATEGORY
            )
            if not self.rd3d_map_category_visible.get(visible_category, True):
                continue

            px = point_offset_x + (x - min_x) * point_scale
            py = point_offset_y + (max_z - z) * point_scale
            color = self._rd3d_category_color(visible_category)
            point_key = (prop_index, x, z, y)
            draw_radius = (
                radius * MapViewTemplate.DOT_HOVER_SCALE
                if point_key == self.rd3d_map_hover_point
                else radius
            )
            canvas.create_oval(
                px - draw_radius,
                py - draw_radius,
                px + draw_radius,
                py + draw_radius,
                fill=color,
                outline="#111111",
                width=1,
                tags=("rd3d_point", visible_category),
            )
            screen_points.append(
                (px, py, prop_index, x, z, y, position_text, visible_category)
            )
            visible_count += 1

        self.rd3d_map_screen_points = screen_points
        canvas.create_text(
            10,
            10,
            text=(
                f"Point zoom {zoom:.2f}x  |  Shared zoom {shared_zoom:.2f}x  |  "
                f"{visible_count}/{len(self.rd3d_map_points)} points visible"
            ),
            fill="#d0d4d7",
            anchor="nw",
            font=("Segoe UI", 9, "bold"),
        )

    def _on_rd3d_map_motion(self, event):
        if MapViewTemplate.middle_pan_active(self.rd3d_map_canvas, event):
            return "break"
        points = getattr(self, "rd3d_map_screen_points", [])
        hovered = None
        if points:
            nearest = min(
                points,
                key=lambda point: (point[0] - event.x) ** 2 + (point[1] - event.y) ** 2,
            )
            distance_sq = (nearest[0] - event.x) ** 2 + (nearest[1] - event.y) ** 2
            if distance_sq <= MapViewTemplate.HOVER_HIT_RADIUS ** 2:
                hovered = (nearest[2], nearest[3], nearest[4], nearest[5])

        if hovered != self.rd3d_map_hover_point:
            self.rd3d_map_hover_point = hovered
            self._schedule_rd3d_map_redraw()

    def _on_rd3d_map_leave(self, _event):
        if self.rd3d_map_hover_point is not None:
            self.rd3d_map_hover_point = None
            self._schedule_rd3d_map_redraw()

    def _on_rd3d_map_click(self, event):
        points = getattr(self, "rd3d_map_screen_points", [])
        if not points:
            return
        nearest = min(
            points,
            key=lambda point: (point[0] - event.x) ** 2 + (point[1] - event.y) ** 2,
        )
        distance_sq = (nearest[0] - event.x) ** 2 + (nearest[1] - event.y) ** 2
        if distance_sq > MapViewTemplate.HIT_RADIUS ** 2:
            return
        _, _, prop_index, x, z, y, position_text, category = nearest
        prop_path = ""
        if 0 <= prop_index < len(self.rd3d_file_names):
            prop_path = self.rd3d_file_names[prop_index][2].get().strip()
        self.rd3d_map_selection_var.set(
            f"Index {prop_index}  |  {category}  |  X {x:.3f}  Z {z:.3f}  Y {y:.3f}\n"
            f"{prop_path or 'No prop path found'}"
        )







    def _render_tmc_data_rows(self):
        table = self.tmc_data_current_table
        if table is None:
            return
        for widget in table.winfo_children():
            widget.destroy()

        for row_index, (object_id, original_filename, count, variable) in enumerate(self.tmc_data_rows):
            current_filename = variable.get().strip()
            object_type = self._classify_prop(current_filename)
            category_color = self._rd3d_category_color(object_type)
            shade = ("gray92", "gray17") if row_index % 2 == 0 else ("gray86", "gray21")

            row = ctk.CTkFrame(table, height=76, fg_color=shade, corner_radius=4)
            row.grid(row=row_index, column=0, sticky="ew", padx=1, pady=1)
            row.grid_propagate(False)
            row.grid_columnconfigure(3, weight=1)

            ctk.CTkLabel(row, text=object_id, width=70, anchor="w").grid(
                row=0, column=0, rowspan=2, padx=5, pady=5, sticky="nsw"
            )
            ctk.CTkLabel(
                row, text=object_type, text_color=category_color, width=170, anchor="w"
            ).grid(row=0, column=1, rowspan=2, padx=5, pady=5, sticky="nsw")
            ctk.CTkLabel(row, text=str(count), width=65, anchor="w").grid(
                row=0, column=2, rowspan=2, padx=5, pady=5, sticky="nsw"
            )

            original_var = tk.StringVar(value=original_filename)
            ctk.CTkEntry(
                row, textvariable=original_var, height=28, state="disabled",
                border_width=0, fg_color="transparent"
            ).grid(row=0, column=3, padx=5, pady=(5, 2), sticky="ew")
            ctk.CTkEntry(
                row, textvariable=variable, height=28, border_width=1
            ).grid(row=1, column=3, padx=5, pady=(2, 5), sticky="ew")
            ctk.CTkButton(
                row, text="Change", width=80, height=30,
                command=lambda target_variable=variable: self._open_tmc_change_window(target_variable),
            ).grid(row=0, column=4, rowspan=2, padx=(5, 8), pady=8, sticky="e")

        self.after_idle(self._configure_tmc_data_scroll)

    def _open_tmc_change_window(self, target_variable):
        popup = PopupTemplate.create_window(
            self,
            title="Update available",
            heading="Update available",
            geometry="520x250",
            resizable=False,
            modal=False,
            close_command=window.destroy if False else None,
        )
        window = popup["window"]
        window.title("Change TMC Object")
        window.geometry("1050x720")
        window.minsize(800, 520)
        window.transient(self)
        window.attributes("-topmost", True)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(window, text="Change TMC Object", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=18, pady=(16, 8), sticky="w"
        )
        filter_bar = ctk.CTkFrame(window)
        filter_bar.grid(row=1, column=0, padx=18, pady=(0, 10), sticky="ew")
        filter_bar.grid_columnconfigure(1, weight=1)
        filter_bar.grid_columnconfigure(3, weight=1)
        database_rows = [
            (self._classify_prop(path), path)
            for _source_category, path, _count in get_combined_object_database(self.CONFIG_FILE)
        ]
        types = sorted({object_type for object_type, _path in database_rows}, key=str.casefold)
        window.tmc_filter_var = tk.StringVar(value="All")
        window.tmc_search_var = tk.StringVar()
        window.tmc_search_job = None
        window.tmc_database_rows = database_rows
        window.tmc_target_variable = target_variable
        ctk.CTkLabel(filter_bar, text="Type:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=(12, 8), pady=10, sticky="w"
        )
        ctk.CTkOptionMenu(
            filter_bar, variable=window.tmc_filter_var, values=["All"] + types,
            dynamic_resizing=False,
            command=lambda _value: self._render_tmc_change_database(window),
        ).grid(row=0, column=1, padx=(0, 8), pady=10, sticky="ew")
        ctk.CTkLabel(filter_bar, text="Search:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=2, padx=(8, 8), pady=10, sticky="w"
        )
        ctk.CTkEntry(
            filter_bar, textvariable=window.tmc_search_var,
            placeholder_text="Filter Type or Path...", width=300,
        ).grid(row=0, column=3, padx=(0, 12), pady=10, sticky="ew")
        window.tmc_search_var.trace_add(
            "write", lambda *_args: self._schedule_tmc_change_filter(window)
        )
        ctk.CTkLabel(
            filter_bar,
            text="Search tip: Multiple terms are combined with AND. Each term may match either Type or Path (e.g. 'bush jun').",
            text_color="gray65", anchor="w", justify="left", font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, columnspan=4, padx=(12, 12), pady=(0, 8), sticky="w")
        header = ctk.CTkFrame(window, corner_radius=4)
        header.grid(row=2, column=0, padx=18, sticky="ew")
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="Type", width=190, anchor="w", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=5, pady=7, sticky="w"
        )
        ctk.CTkLabel(header, text="Path", anchor="w", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, padx=5, pady=7, sticky="ew"
        )
        table = ctk.CTkScrollableFrame(window, fg_color="transparent")
        table.grid(row=3, column=0, padx=18, pady=(2, 16), sticky="nsew")
        table.grid_columnconfigure(0, weight=1)
        window.tmc_database_table = table
        self._render_tmc_change_database(window)
        PopupTemplate.schedule_activate(window, 50, focus=False)
        PopupTemplate.schedule_activate(window, 60, focus=True)
        window.after(300, lambda: self._release_tmc_change_topmost(window))

    def _schedule_tmc_change_filter(self, window):
        job = getattr(window, "tmc_search_job", None)
        if job is not None:
            try:
                window.after_cancel(job)
            except tk.TclError:
                pass
        window.tmc_search_job = window.after(
            500, lambda: self._run_tmc_change_filter(window)
        )

    def _run_tmc_change_filter(self, window):
        if window is None or not window.winfo_exists():
            return
        window.tmc_search_job = None
        self._render_tmc_change_database(window)

    def _render_tmc_change_database(self, window):
        table = window.tmc_database_table
        for widget in table.winfo_children():
            widget.destroy()
        selected_type = window.tmc_filter_var.get().strip() or "All"
        search_text = window.tmc_search_var.get().strip().casefold()
        rows = window.tmc_database_rows
        if selected_type != "All":
            rows = [row for row in rows if row[0] == selected_type]
        if search_text:
            rows = [
                row for row in rows
                if self._matches_filter_terms(row[0], row[1], search_text)
            ]
        rows = sorted(rows, key=lambda item: (item[0].casefold(), item[1].casefold()))
        for index, (object_type, path) in enumerate(rows):
            shade = ("gray92", "gray17") if index % 2 == 0 else ("gray86", "gray21")
            row = ctk.CTkFrame(table, fg_color=shade, corner_radius=4, height=42)
            row.grid(row=index, column=0, padx=1, pady=1, sticky="ew")
            row.grid_propagate(False)
            row.grid_columnconfigure(1, weight=1)
            self._highlight_filter_text(
                row, object_type, search_text, width=24,
                color=self._rd3d_category_color(object_type)
            ).grid(row=0, column=0, padx=5, pady=7, sticky="ew")
            self._highlight_filter_text(
                row, path, search_text
            ).grid(row=0, column=1, padx=5, pady=7, sticky="ew")
            ctk.CTkButton(
                row, text="Select", width=85, height=30,
                command=lambda selected_path=path: self._select_tmc_change_path(window, selected_path),
            ).grid(row=0, column=2, padx=(5, 8), pady=5)

    def _select_tmc_change_path(self, window, path):
        target_variable = getattr(window, "tmc_target_variable", None)
        if target_variable is None:
            return
        target_variable.set(path)
        self._render_tmc_data_rows()
        self._refresh_tmc_replace_menus()
        self.status_var.set(f"TMC object path changed: {path}")
        window.destroy()

    @staticmethod
    def _release_tmc_change_topmost(window):
        try:
            if window is not None and window.winfo_exists():
                window.attributes("-topmost", False)
                window.lift()
        except tk.TclError:
            pass

    def _configure_tmc_data_scroll(self):
        table = self.tmc_data_current_table
        if table is None:
            return
        try:
            canvas = table._parent_canvas
            canvas.bind("<MouseWheel>", self._on_tmc_data_wheel)
            canvas.bind("<Button-4>", self._on_tmc_data_wheel)
            canvas.bind("<Button-5>", self._on_tmc_data_wheel)
        except (AttributeError, tk.TclError):
            pass

    def _configure_tmc_data_scroll_sync(self):
        self._configure_tmc_data_scroll()

    def _sync_tmc_data_scroll(self, *args):
        table = self.tmc_data_current_table
        if table is None or not args:
            return "break"
        canvas = table._parent_canvas
        if args[0] == "moveto":
            canvas.yview_moveto(float(args[1]))
        elif args[0] == "scroll":
            canvas.yview_scroll(int(args[1]), args[2])
        return "break"

    def _on_tmc_data_wheel(self, event):
        table = self.tmc_data_current_table
        if table is None:
            return "break"
        if getattr(event, "num", None) == 4:
            units = -1
        elif getattr(event, "num", None) == 5:
            units = 1
        else:
            units = -1 if getattr(event, "delta", 0) > 0 else 1
        table._parent_canvas.yview_scroll(units, "units")
        return "break"


    def _path_row(self, parent, row, label, variable, command):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=(15, 8), pady=6, sticky="w")
        ctk.CTkEntry(parent, textvariable=variable).grid(row=row, column=1, padx=8, pady=6, sticky="ew")
        ctk.CTkButton(parent, text="Browse", width=110, command=command).grid(
            row=row, column=2, padx=(8, 15), pady=6
        )

    def _folder_path_row(self, parent, row, label, variable, title):
        ctk.CTkLabel(parent, text=label).grid(row=row, column=0, padx=(15, 8), pady=6, sticky="w")
        entry = ctk.CTkEntry(parent, textvariable=variable)
        entry.grid(row=row, column=1, padx=8, pady=6, sticky="ew")
        entry.bind("<FocusOut>", lambda _event: self._save_config())
        entry.bind("<Return>", lambda _event: self._save_config())
        def browse():
            current = variable.get().strip()
            value = filedialog.askdirectory(title=title, initialdir=current if current and Path(current).is_dir() else None)
            if value:
                variable.set(value)
                self._save_config()
        ctk.CTkButton(parent, text="Browse", width=110, command=browse).grid(row=row, column=2, padx=(8, 15), pady=6)

    def _create_log(self, parent, row):
        frame = ctk.CTkFrame(parent)
        frame.grid(row=row, column=0, padx=5, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(frame, text="Log", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=12, pady=(8, 0), sticky="w"
        )
        log = ctk.CTkTextbox(frame, wrap="word")
        log.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        log.configure(state="disabled")
        return log
