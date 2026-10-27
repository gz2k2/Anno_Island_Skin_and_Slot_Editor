from __future__ import annotations

import ctypes
import csv
import tkinter as tk
from app.templates.template_popup import PopupTemplate
from app.templates.template_treeview import TreeviewTemplate
from app.templates.template_statuswindow import StatusWindowTemplate
import os
import subprocess
import sys
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageOps, ImageTk
from app.config.config_rd3d import RD3D_REGION_BY_SOURCE_CATEGORY


class StartTabMixin:
    """Independent Start workflow for selecting, creating and extracting islands."""

    def _build_start_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        source = ctk.CTkFrame(tab)
        source.grid(row=0, column=0, padx=5, pady=(5, 10), sticky="ew")
        source.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            source, text="Create Custom Island",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=15, pady=(14, 6), sticky="w")
        create_buttons = ctk.CTkFrame(source, fg_color="transparent")
        create_buttons.grid(row=1, column=0, columnspan=3, padx=15, pady=(0, 6), sticky="w")
        ctk.CTkButton(
            create_buttons, text="Create from Original Maps", width=205,
            command=self._open_original_maps_popup,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            create_buttons, text="Create from CustomFolder", width=185,
            command=self._open_custom_map_folder,
        ).pack(side="left")

        ctk.CTkLabel(
            source,
            text="Or choose a .a7m - File",
            font=ctk.CTkFont(weight="bold"),
            text_color="gray70",
        ).grid(row=2, column=0, columnspan=3, padx=15, pady=(8, 4), sticky="w")

        ctk.CTkLabel(source, text="A7M file:").grid(
            row=3, column=0, padx=(15, 8), pady=(6, 14), sticky="w"
        )
        ctk.CTkEntry(source, textvariable=self.unpack_file_var).grid(
            row=3, column=1, padx=8, pady=(6, 14), sticky="ew"
        )
        ctk.CTkButton(
            source, text="Browse", width=110,
            command=self._select_start_a7m_file,
        ).grid(row=3, column=2, padx=(8, 15), pady=(6, 14))

        options = ctk.CTkFrame(tab)
        options.grid(row=1, column=0, padx=5, pady=(0, 10), sticky="ew")
        ctk.CTkCheckBox(
            options, text="Unpack gamedata", variable=self.unpack_gamedata_var,
            command=self._save_config,
        ).pack(side="left", padx=(15, 8), pady=12)
        ctk.CTkCheckBox(
            options, text="Unpack rd3d.data", variable=self.unpack_rd3d_var,
            command=self._save_config,
        ).pack(side="left", padx=8, pady=12)
        ctk.CTkCheckBox(
            options, text="Unpack tmc.data", variable=self.unpack_tmc_var,
            command=self._save_config,
        ).pack(side="left", padx=8, pady=12)
        ctk.CTkCheckBox(
            options, text="Unpack matching .a7minfo", variable=self.unpack_a7minfo_var,
            command=self._save_config,
        ).pack(side="left", padx=15, pady=12)

        controls = ctk.CTkFrame(tab, fg_color="transparent")
        controls.grid(row=2, column=0, padx=5, pady=(0, 10), sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        self.start_progress = ctk.CTkProgressBar(controls)
        self.start_progress.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.start_progress.set(0)
        self.start_btn = ctk.CTkButton(
            controls, text="Unpack island", width=145,
            command=self._start_island_extraction,
        )
        self.start_btn.grid(row=0, column=1, padx=5)
        self.start_stop_btn = ctk.CTkButton(
            controls, text="Stop immediately", width=130, state="disabled",
            fg_color="#a83232", hover_color="#852626", command=self._stop,
        )
        self.start_stop_btn.grid(row=0, column=2, padx=(5, 0))
        self._build_xml_loading_indicator(controls, 1)
        self.start_log = self._create_log(tab, 3)

    @staticmethod
    def _original_maps_app_folder():
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(sys.argv[0]).resolve().parent

    def _original_maps_index_path(self):
        return self._original_maps_app_folder() / "original_maps_index.csv"

    @staticmethod
    def _original_map_region(a7m_path):
        # Match the configured source-category names against the complete A7M
        # path. Some game paths contain names such as scenario03_s_01 rather
        # than a directory component that is exactly "scenario03".
        path_text = str(Path(a7m_path)).replace("\\", "/").casefold()
        matches = [
            (source_name, region_name)
            for source_name, region_name in RD3D_REGION_BY_SOURCE_CATEGORY.items()
            if source_name.casefold() in path_text
        ]
        if not matches:
            return "Unknown"
        # Prefer the most specific configured name if names ever overlap.
        return max(matches, key=lambda item: len(item[0]))[1]

    @staticmethod
    def _original_map_image_for(a7m_path, original_root, image_index=None):
        a7m_path = Path(a7m_path)
        original_root = Path(original_root)
        map_name = a7m_path.stem.casefold()
        direct = a7m_path.parent / "_gamedata" / a7m_path.stem / "mapimage.png"
        if direct.is_file():
            return direct
        for parent in a7m_path.parents:
            if parent == original_root.parent:
                break
            candidate = parent / "_gamedata" / a7m_path.stem / "mapimage.png"
            if candidate.is_file():
                return candidate
            if parent == original_root:
                break
        matches = (image_index or {}).get(map_name, ())
        return matches[0] if matches else None

    def _scan_original_maps(self, original_root, progress=None):
        original_root = Path(original_root)
        image_paths = sorted(original_root.rglob("mapimage.png"), key=lambda p: str(p).casefold())
        image_index = {}
        image_total = max(1, len(image_paths))
        for index, image_path in enumerate(image_paths, 1):
            if image_path.is_file() and image_path.parent.parent.name.casefold() == "_gamedata":
                image_index.setdefault(image_path.parent.name.casefold(), []).append(image_path)
            if progress:
                progress(0.35 * index / image_total, f"Indexing map images... {index}/{len(image_paths)}")

        a7m_paths = sorted(original_root.rglob("*.a7m"), key=lambda path: str(path).casefold())
        rows = []
        a7m_total = max(1, len(a7m_paths))
        for index, a7m_path in enumerate(a7m_paths, 1):
            if a7m_path.is_file():
                image_path = self._original_map_image_for(a7m_path, original_root, image_index)
                rows.append((
                    self._original_map_region(a7m_path),
                    str(a7m_path.resolve()),
                    str(image_path.resolve()) if image_path else "",
                ))
            if progress:
                progress(
                    0.35 + 0.65 * index / a7m_total,
                    f"Scanning A7M files... {index}/{len(a7m_paths)}\n"
                    f"{len(rows)} Islands found",
                )

        index_path = self._original_maps_index_path()
        with index_path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(("Region", "A7M Path", "Map Image Path"))
            writer.writerows(rows)
        return rows, index_path

    def _load_original_maps_index(self, _original_root=None):
        path = self._original_maps_index_path()
        if not path.is_file():
            return []
        rows = []
        try:
            with path.open("r", newline="", encoding="utf-8-sig") as stream:
                for row in csv.DictReader(stream, delimiter=";"):
                    a7m = (row.get("A7M Path") or "").strip()
                    image = (row.get("Map Image Path") or "").strip()
                    region = (row.get("Region") or "").strip()
                    if a7m:
                        rows.append((region or self._original_map_region(a7m), a7m, image))
        except (OSError, UnicodeError, csv.Error):
            return []
        return rows

    def _apply_original_map_selection(self, a7m_path, window):
        source = Path(a7m_path)
        if not source.is_file():
            messagebox.showerror(
                "Original Maps", f"The selected A7M file no longer exists:\n{source}", parent=window,
            )
            return
        PopupTemplate.close_window(window)
        self._create_custom_island(source=source.parent, selected_a7m=source)

    def _open_original_maps_popup(self):
        existing = getattr(self, "_original_maps_window", None)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            try:
                owner_window = self.winfo_toplevel()
                existing.transient(owner_window)
                existing.lift(owner_window)
            except (tk.TclError, AttributeError):
                existing.lift()
            PopupTemplate.request_focus(existing, delay_ms=60)
            return
        root_text = self.original_maps_var.get().strip()
        if not root_text:
            messagebox.showwarning("Original Maps", "Please configure Original Maps in Settings first.", parent=self)
            return
        original_root = Path(root_text).expanduser()
        if not original_root.is_dir():
            messagebox.showerror("Original Maps", f"The configured Original Maps folder does not exist:\n{original_root}", parent=self)
            return

        built = PopupTemplate.create_window(
            self, title="Create from Original Maps", heading="Original Maps",
            geometry="1160x740", min_size=(860, 560), resizable=True,
        )
        window = built["window"]
        self._original_maps_window = window
        try:
            owner_window = self.winfo_toplevel()
            if owner_window is not None and owner_window.winfo_exists():
                window.transient(owner_window)
                PopupTemplate.apply_native_titlebar_controls(window)
                window.lift(owner_window)
                PopupTemplate.request_focus(window, delay_ms=100)
        except (tk.TclError, AttributeError):
            pass
        window.grid_columnconfigure(0, weight=1, uniform="original_maps_split")
        window.grid_columnconfigure(1, weight=1, uniform="original_maps_split")
        window.grid_rowconfigure(3, weight=1)

        status_var = tk.StringVar(master=window, value="No index loaded.")
        active_region = tk.StringVar(master=window, value="All")
        all_rows = []
        row_data = {}

        toolbar = ctk.CTkFrame(window, fg_color="transparent")
        toolbar.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 8), sticky="ew")
        toolbar.grid_columnconfigure(1, weight=1)
        scan_button = ctk.CTkButton(toolbar, text="Scan Original Maps Folder", width=210)
        scan_button.grid(row=0, column=0, padx=(0, 12), sticky="w")
        ctk.CTkLabel(toolbar, textvariable=status_var, anchor="w").grid(row=0, column=1, sticky="ew")

        filters = ctk.CTkFrame(window, fg_color="transparent")
        filters.grid(row=2, column=0, columnspan=2, padx=20, pady=(0, 10), sticky="w")
        region_names = list(dict.fromkeys(RD3D_REGION_BY_SOURCE_CATEGORY.values()))
        filter_buttons = {}

        table_frame = ctk.CTkFrame(window)
        table_frame.grid(row=3, column=0, padx=(20, 10), pady=(0, 12), sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1); table_frame.grid_rowconfigure(0, weight=1)
        table = TreeviewTemplate.create(
            table_frame, columns=("region", "island", "a7m"),
            headings={"region": "Region", "island": "Island", "a7m": "A7M Path"},
            min_widths={"region": 70, "island": 90, "a7m": 120},
            max_widths={"region": 320, "island": 520, "a7m": 2400},
            stretch=(), selectmode="browse", dynamic_width=True, width_padding=24,
        )
        tree = table["tree"]

        preview = ctk.CTkFrame(window)
        preview.grid(row=3, column=1, padx=(10, 20), pady=(0, 12), sticky="nsew")
        preview.grid_columnconfigure(0, weight=1); preview.grid_rowconfigure(1, weight=1)
        preview_title = ctk.CTkLabel(preview, text="Select an island", anchor="w")
        preview_title.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        image_frame = ctk.CTkFrame(preview, fg_color="transparent")
        image_frame.grid(row=1, column=0, padx=12, pady=12, sticky="nsew")
        image_frame.grid_columnconfigure(0, weight=1)
        image_frame.grid_rowconfigure(0, weight=1)
        image_canvas = tk.Canvas(
            image_frame, background="#242424", borderwidth=0, highlightthickness=0,
        )
        image_canvas.grid(row=0, column=0, sticky="nsew")
        image_canvas.create_text(
            10, 10, text="No preview available", anchor="nw", fill="#DCE4EE",
            tags="preview_message",
        )
        image_path_var = tk.StringVar(master=window)
        ctk.CTkLabel(preview, textvariable=image_path_var, anchor="w", justify="left",
                     wraplength=380, text_color="gray70").grid(
            row=2, column=0, padx=12, pady=(0, 12), sticky="ew")

        def selected_record():
            selected = tree.selection()
            return row_data.get(selected[0]) if len(selected) == 1 else None

        preview_state = {"path": "", "source": None, "tk_image": None, "after": None}

        def render_preview():
            if not window.winfo_exists() or not image_canvas.winfo_exists():
                return
            image_canvas.delete("all")
            source_image = preview_state["source"]
            if source_image is None:
                image_canvas.create_text(
                    10, 10, text="No preview available", anchor="nw", fill="#DCE4EE",
                )
                image_canvas.configure(scrollregion=(0, 0, 1, 1))
                preview_state["tk_image"] = None
                self._original_maps_preview_image = None
                return
            canvas_width = max(1, image_canvas.winfo_width())
            canvas_height = max(1, image_canvas.winfo_height())
            original_width, original_height = source_image.size
            # Fit the complete image into the available preview area. The
            # image may be scaled down or enlarged, while preserving its aspect ratio.
            scale = min(canvas_width / original_width, canvas_height / original_height)
            shown_width = max(1, int(round(original_width * scale)))
            shown_height = max(1, int(round(original_height * scale)))
            if (shown_width, shown_height) == source_image.size:
                shown_image = source_image.copy()
            else:
                shown_image = source_image.resize(
                    (shown_width, shown_height), Image.Resampling.LANCZOS,
                )
            tk_image = ImageTk.PhotoImage(shown_image)
            x = max(0, (canvas_width - shown_width) // 2)
            y = max(0, (canvas_height - shown_height) // 2)
            image_canvas.create_image(x, y, image=tk_image, anchor="nw")
            image_canvas.configure(
                scrollregion=(0, 0, max(canvas_width, shown_width), max(canvas_height, shown_height)),
            )
            preview_state["tk_image"] = tk_image
            self._original_maps_preview_image = tk_image

        def schedule_preview_render(_event=None):
            pending = preview_state.get("after")
            if pending:
                try:
                    window.after_cancel(pending)
                except (tk.TclError, ValueError):
                    pass
            preview_state["after"] = window.after(80, render_preview)

        image_canvas.bind("<Configure>", schedule_preview_render, add="+")

        def show_preview(_event=None):
            record = selected_record()
            if record is None:
                return
            region, a7m_path, map_image = record
            preview_title.configure(text=f"{Path(a7m_path).stem} | {region}")
            image_path_var.set(map_image or "No mapimage.png found")
            preview_state["path"] = map_image
            preview_state["source"] = None
            if map_image and Path(map_image).is_file():
                try:
                    with Image.open(map_image) as source_image:
                        preview_state["source"] = source_image.convert("RGBA")
                except (OSError, ValueError, Image.DecompressionBombError):
                    preview_state["source"] = None
            schedule_preview_render()

        def fill():
            selected_region = active_region.get()
            visible = [row for row in all_rows if selected_region == "All" or row[0] == selected_region]
            tree.delete(*tree.get_children("")); row_data.clear()
            for region, a7m_path, map_image in visible:
                item = tree.insert("", "end", values=(region, Path(a7m_path).stem, a7m_path))
                row_data[item] = (region, a7m_path, map_image)
            tree.schedule_autosize()
            status_var.set(f"{len(visible)} shown / {len(all_rows)} total | Index: {self._original_maps_index_path()}")
            if visible:
                first = tree.get_children("")[0]
                tree.selection_set(first); tree.focus(first); tree.see(first); show_preview()
            else:
                preview_title.configure(text="No island selected")
                image_path_var.set("")
                preview_state["source"] = None
                schedule_preview_render()

        def set_region(region):
            active_region.set(region)
            for name, button in filter_buttons.items():
                button.configure(fg_color=("#1f6aa5" if name == region else "#555555"))
            fill()

        for column, region in enumerate(["All"] + region_names):
            button = ctk.CTkButton(filters, text=region, width=110,
                                   command=lambda value=region: set_region(value))
            button.grid(row=0, column=column, padx=(0, 8), sticky="w")
            filter_buttons[region] = button

        tree.bind("<<TreeviewSelect>>", show_preview, add="+")
        tree.bind("<Double-1>", lambda _event: (
            self._apply_original_map_selection(selected_record()[1], window) if selected_record() else None
        ), add="+")

        scan_queue = queue.Queue()
        def scan_worker():
            try:
                rows, index_path = self._scan_original_maps(
                    original_root,
                    lambda fraction, text: scan_queue.put(("progress", fraction, text)),
                )
                scan_queue.put(("done", rows, index_path))
            except Exception as exc:
                scan_queue.put(("error", exc))

        def scan():
            if getattr(self, "_original_maps_scan_running", False): return
            self._original_maps_scan_running = True
            scan_button.configure(state="disabled")
            status = StatusWindowTemplate.create(
                window, text="Scanning Original Maps Folder...\n0 Islands found", title="Original Maps Scan",
                heading="Original Maps Scan", progress=True, fraction=None,
                modal=False, topmost=True,
            )
            def poll():
                if not window.winfo_exists(): return
                finished = False
                try:
                    while True:
                        message = scan_queue.get_nowait()
                        if message[0] == "progress":
                            StatusWindowTemplate.update(status, text=message[2], fraction=message[1])
                        elif message[0] == "done":
                            all_rows[:] = message[1]
                            active_region.set("All"); set_region("All")
                            status_var.set(f"{len(all_rows)} island(s) found | Saved: {message[2]}")
                            finished = True
                        elif message[0] == "error":
                            messagebox.showerror("Original Maps", f"Scan failed:\n{message[1]}", parent=window)
                            finished = True
                except queue.Empty:
                    pass
                if finished:
                    self._original_maps_scan_running = False
                    scan_button.configure(state="normal")
                    StatusWindowTemplate.close(status)
                else:
                    window.after(75, poll)
            threading.Thread(target=scan_worker, daemon=True).start()
            window.after(75, poll)
        scan_button.configure(command=scan)

        footer = ctk.CTkFrame(window, fg_color="transparent")
        footer.grid(row=4, column=0, columnspan=2, padx=20, pady=(0, 18), sticky="e")
        ctk.CTkButton(footer, text="Use Selected Island", width=170, command=lambda: (
            self._apply_original_map_selection(selected_record()[1], window)
            if selected_record() else messagebox.showinfo("Original Maps", "Select an island first.", parent=window)
        )).pack(side="left")

        all_rows[:] = self._load_original_maps_index(original_root)
        set_region("All")
        PopupTemplate.request_focus(window, delay_ms=100)

    def _open_custom_map_folder(self):
        """Choose one A7M from the configured Custom Map Folder and create a copy."""
        value = self.custom_map_folder_var.get().strip()
        if not value:
            messagebox.showwarning(
                "Create from Custom Folder",
                "Please configure Custom Map Folder in Settings first.",
                parent=self,
            )
            return
        folder = Path(value).expanduser()
        if not folder.is_dir():
            messagebox.showerror(
                "Create from Custom Folder",
                f"The configured Custom Map Folder does not exist:\n{folder}",
                parent=self,
            )
            return

        selected = filedialog.askopenfilename(
            title="Select A7M from Custom Map Folder",
            initialdir=str(folder),
            filetypes=[("Anno island", "*.a7m"), ("All files", "*.*")],
            parent=self,
        )
        if not selected:
            return
        selected_a7m = Path(selected)
        try:
            selected_a7m.resolve().relative_to(folder.resolve())
        except (OSError, ValueError):
            messagebox.showerror(
                "Create from Custom Folder",
                "Please select an A7M file inside the configured Custom Map Folder.",
                parent=self,
            )
            return
        if not selected_a7m.is_file() or selected_a7m.suffix.casefold() != ".a7m":
            messagebox.showerror(
                "Create from Custom Folder",
                "Please select a valid .a7m file.",
                parent=self,
            )
            return

        # The shared flow shows the naming dialog (<MapName>_skinned), copies
        # the selected variant and its related data, and targets Temporary Map Folder.
        self._create_custom_island(
            source=selected_a7m.parent,
            selected_a7m=selected_a7m,
        )

    def _invalidate_island_runtime_cache(self, a7m_path=None):
        """Drop every island-specific RAM/cache/session when the selected A7M changes."""
        # RD3D / TMC source caches and all edit sessions that reference them.
        self.rd3d_ram_cache = None
        self.tmc_ram_cache = None
        self.tmc_ram_folder = None
        self._map_edit_session = None
        self._density_session = None
        self._density_cache = None

        # Object Map derived data/indexes/images.
        self.object_configuration_map_points = []
        self.object_configuration_map_screen_points = []
        self.object_configuration_map_file_names = []
        self.object_configuration_map_world_grid = {}
        self.object_configuration_map_world_grid_signature = None
        self.object_configuration_map_screen_grid = {}
        self.object_configuration_map_image_source = None
        self.object_configuration_map_image_tk = None
        self.object_configuration_map_image_cache = {}
        self.object_configuration_map_hover_point = None
        self.object_configuration_map_dot_image = None
        self.object_configuration_map_dot_photo = None
        self.object_configuration_map_rendered_count = 0

        # Slot Map RAM trees, pending edits and all data derived from the old island.
        self._island_slot_ram_game_tree = None
        self._island_slot_ram_map_tree = None
        self._island_slot_snapshot = None
        self._slot_map_pending_moves = {}
        self.slot_map_points = []
        self.slot_map_screen_points = []
        self.slot_map_river_pairs = []
        self.slot_map_orientation_directions = {}
        self.slot_map_image_source = None
        self.slot_map_image_tk = None
        self.slot_map_image_cache = {}
        self.slot_map_hover_point = None
        generated = getattr(self, "_island_slot_generated_deposit_ids", None)
        if generated is not None:
            generated.clear()
        selected = getattr(self, "island_slot_selected_ids", None)
        if selected is not None:
            selected.clear()

        # Table/editor models must not keep rows/nodes from another island.
        self.object_configuration_table1_rows = []
        self.object_configuration_table2_rows = []
        self.combined_slot_records = []
        self.combined_slot_records_by_id = {}
        self.combined_slot_game_nodes_by_id = {}
        self.combined_slot_map_nodes_by_id = {}
        self.combined_slot_edit_rows_by_id = {}
        self.combined_slot_dirty_ids = set()
        self.combined_slot_deleted_ids = set()
        self._island_cache_a7m_path = (
            str(Path(a7m_path).resolve()) if a7m_path else None
        )
        return True

    def _select_start_a7m_file(self):
        if self._busy():
            return
        current = self.unpack_file_var.get().strip()
        value = filedialog.askopenfilename(
            title="Select A7M file",
            initialdir=str(Path(current).parent) if current and Path(current).parent.is_dir() else None,
            filetypes=[("Anno island", "*.a7m"), ("All files", "*.*")],
        )
        if not value:
            return
        source = Path(value)
        previous = self.unpack_file_var.get().strip()
        if not previous or Path(previous) != source:
            self._invalidate_island_runtime_cache(source)
        self.unpack_file_var.set(str(source))
        self.pack_file_var.set(str(source))
        self._start_detect_meshes_folder(source)
        self._refresh_files_and_folders_from_map(source)

    def _start_detect_meshes_folder(self, a7m_file: Path):
        a7m_file = Path(a7m_file)
        if not a7m_file.is_file() or a7m_file.suffix.casefold() != ".a7m":
            return False
        root = a7m_file.parent
        map_name = a7m_file.stem
        gamedata_root = root / "_gamedata"
        expected = gamedata_root / map_name / "meshes"
        meshes = expected if expected.is_dir() else None
        if meshes is None and gamedata_root.is_dir():
            for map_folder in gamedata_root.iterdir():
                if not map_folder.is_dir() or map_folder.name.casefold() != map_name.casefold():
                    continue
                meshes = next(
                    (child for child in map_folder.iterdir()
                     if child.is_dir() and child.name.casefold() == "meshes"),
                    None,
                )
                if meshes is not None:
                    break
        if meshes is None and gamedata_root.is_dir():
            candidates = sorted(
                (folder for folder in gamedata_root.rglob("*")
                 if folder.is_dir() and folder.name.casefold() == "meshes"),
                key=lambda folder: str(folder).casefold(),
            )
            if len(candidates) == 1:
                meshes = candidates[0]
        if meshes is None:
            return False
        self.tmc_data_meshes_var.set(str(meshes))
        self.status_var.set(f"Meshes folder detected: {meshes}")
        return True

    def _show_unpack_status(self):
        """Show the shared themed status window for the complete unpack workflow."""
        current = getattr(self, "_unpack_status_popup", None)
        if StatusWindowTemplate.exists(current):
            StatusWindowTemplate.update(current, text="Unpacking....")
            return
        self._unpack_status_popup = StatusWindowTemplate.create(
            self, text="Unpacking....", title="Status", heading="Status",
            modal=False, topmost=True,
        )

    def _close_unpack_status(self):
        popup = getattr(self, "_unpack_status_popup", None)
        self._unpack_status_popup = None
        StatusWindowTemplate.close(popup)


    def _watch_unpack_completion(self):
        """Close the status only after the complete extraction worker has ended."""
        popup = getattr(self, "_unpack_status_popup", None)
        if popup is None:
            return
        worker = getattr(self, "worker", None)
        if worker is not None and worker.is_alive():
            self.after(100, self._watch_unpack_completion)
            return
        self._close_unpack_status()

    def _start_island_extraction(self):
        if self._busy():
            return
        source = Path(self.unpack_file_var.get().strip())
        if not source.is_file() or source.suffix.casefold() != ".a7m":
            messagebox.showerror("Start", "Please select an existing .a7m file.")
            return
        errors = self._validate_settings()
        if errors:
            self._show_settings_errors(errors)
            return
        self._show_unpack_status()
        self._start_detect_meshes_folder(source)
        # Extraction may replace XMLs in the same folder: rebuild every island cache.
        self._invalidate_island_runtime_cache(source)
        self.stop_event.clear()
        self.status_var.set("Preparing...")
        self._set_running(True, "start")
        self.start_progress.set(0)
        self._clear_log(self.start_log)
        self.worker = threading.Thread(
            target=self._start_extraction_worker,
            args=(source,), daemon=True,
        )
        self.worker.start()
        self.after(100, self._watch_unpack_completion)

    def _start_extraction_worker(self, source: Path):
        ok = False
        try:
            root = source.parent
            data_dir = root / source.stem
            self._event("status", f"Unpacking {source.name}...")
            self._event("log_start", f"Source: {source}\nTarget folder: {data_dir}\n\n")
            if data_dir.exists() and any(data_dir.iterdir()):
                if not self._ask_worker_yes_no(
                    "Folder already exists",
                    f"The folder is not empty:\n{data_dir}\n\nContinue using or overwrite existing files?",
                ):
                    raise RuntimeError("Cancelled by user")
            data_dir.mkdir(parents=True, exist_ok=True)
            self._run(
                [self.rda_var.get(), "extract", "-f", str(source), "-o", str(data_dir), "-y"],
                root, "start",
            )
            if self._start_detect_meshes_folder(source):
                self._event("log_start", f"Meshes folder detected: {self.tmc_data_meshes_var.get()}\n")
            self._event("progress_start", 0.30)

            gamedata = self._find_data_file(data_dir, "gamedata.data")
            rd3d = self._find_data_file(data_dir, "rd3d.data")
            if self.unpack_gamedata_var.get():
                if not gamedata:
                    raise RuntimeError("gamedata.data was not found in the unpacked folder.")
                self._event("log_start", "\nUnpacking gamedata.data...\n")
                self._run([
                    self.fdb_var.get(), "decompress", "-f", str(gamedata), "-y",
                    "-i", self.gamedata_format_var.get(),
                ], data_dir, "start")
                game_xml = self._locate_generated_xml(data_dir, gamedata, "gamedata")
                gamedata_original = data_dir / "gamedata_original.xml"
                self._rename_replace(game_xml, gamedata_original)
                self._event("gamedata_ready", str(gamedata_original))
            else:
                self._event("log_start", "\nSkipping gamedata.data (disabled).\n")
            self._event("progress_start", 0.50)

            if self.unpack_rd3d_var.get():
                if not rd3d:
                    raise RuntimeError("rd3d.data was not found in the unpacked folder.")
                self._event("log_start", "\nUnpacking rd3d.data...\n")
                self._run([
                    self.fdb_var.get(), "decompress", "-f", str(rd3d), "-y",
                    "-i", self.rd3d_format_var.get(),
                ], data_dir, "start")
                rd3d_xml = self._locate_generated_xml(data_dir, rd3d, "rd3d")
                rd3d_original = data_dir / "rd3d_original.xml"
                self._rename_replace(rd3d_xml, rd3d_original)
                self._event("rd3d_ready", str(rd3d_original))
            else:
                self._event("log_start", "\nSkipping rd3d.data (disabled).\n")
            self._event("progress_start", 0.65)

            if self.unpack_tmc_var.get():
                self._start_extract_tmc_files(data_dir)
            else:
                self._event("log_start", "\nSkipping TMC files (disabled).\n")
            self._event("progress_start", 0.82)

            info = source.with_suffix(".a7minfo")
            if self.unpack_a7minfo_var.get() and info.is_file():
                self._run([
                    self.fdb_var.get(), "decompress", "-f", str(info), "-y",
                    "-i", self.a7minfo_format_var.get(),
                ], root, "start")
                info_xml = self._locate_generated_xml(root, info, source.stem)
                mapname_original = root / f"{source.stem}_original.xml"
                self._rename_replace(info_xml, mapname_original)
                self._event("mapname_ready", str(mapname_original))
                self._event("log_start", f"MapName XML ready: {mapname_original.name}\n")

            self._event("progress_start", 1.0)
            self._event("files_folders_ready", str(source))
            self._event("log_start_colored", ("\nUnpacking completed successfully.\n", "#26DE81"))
            ok = True
        except Exception as exc:
            label = "Cancelled" if self.stop_event.is_set() else "ERROR"
            self._event("log_start", f"\n{label}: {exc}\n")
        finally:
            self._event("done", ("start", ok, self.stop_event.is_set()))

    def _start_extract_tmc_files(self, data_dir: Path):
        meshes = Path(self.tmc_data_meshes_var.get().strip())
        if not meshes.is_dir():
            expected = data_dir.parent / "_gamedata" / data_dir.name / "meshes"
            if expected.is_dir():
                meshes = expected
                self.tmc_data_meshes_var.set(str(meshes))
        if not meshes.is_dir():
            raise RuntimeError(f"TMC extraction could not find the meshes folder:\n{meshes}")

        tmc_files = sorted(
            (path for path in meshes.rglob("*") if path.is_file() and path.suffix.casefold() == ".tmc"),
            key=lambda path: str(path).casefold(),
        )
        total = len(tmc_files)
        if not tmc_files:
            self._event("log_start", "\nNo TMC files found.\n")
            return

        try:
            workers = int(self.tmc_parallel_var.get().strip())
        except ValueError:
            workers = 4
        workers = max(1, min(workers, 32, total))

        # Keep the log visibly alive without flooding Tk's event queue. For small
        # collections every file is reported; larger collections are updated in
        # roughly 20 steps (5 percent intervals).
        report_every = 1 if total <= 20 else max(1, total // 20)
        self._event(
            "log_start",
            f"\nStarting TMC conversion: {total} file(s), {workers} parallel worker(s).\n"
            f"Progress is reported every {report_every} completed file(s).\n",
        )
        self._event("status", f"TMC conversion: 0/{total} (0%)")

        successful = 0
        failures = []
        completed = 0
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="StartTMC") as executor:
            jobs = {executor.submit(self._start_extract_single_tmc, path): path for path in tmc_files}
            for job in as_completed(jobs):
                path = jobs[job]
                if self.stop_event.is_set():
                    for pending in jobs:
                        pending.cancel()
                    raise RuntimeError("Stop requested")

                completed += 1
                try:
                    job.result()
                    successful += 1
                except Exception as exc:
                    failures.append((path, str(exc)))
                    self._event(
                        "log_start",
                        f"[{completed}/{total}] FAILED: {path.name}\n  {exc}\n",
                    )

                percent = round(completed * 100 / total)
                self._event("status", f"TMC conversion: {completed}/{total} ({percent}%)")

                # TMC occupies the Start workflow range from 65 to 82 percent.
                self._event(
                    "progress_start",
                    0.65 + (0.17 * completed / total),
                )

                if completed == 1 or completed == total or completed % report_every == 0:
                    self._event(
                        "log_start",
                        f"[{completed}/{total}] TMC files processed ({percent}%) | "
                        f"successful: {successful} | failed: {len(failures)}\n",
                    )

        self._event(
            "log_start",
            f"TMC conversion completed: {successful} successful, "
            f"{len(failures)} failed, {total} total.\n",
        )


    def _start_extract_single_tmc(self, tmc_file: Path):
        self._start_run_tmc_process([
            self.fdb_var.get(), "decompress", "-f", str(tmc_file),
            "-i", self.tmc_format_var.get(), "-y",
        ], tmc_file.parent)
        generated = tmc_file.with_suffix(".xml")
        if not generated.is_file():
            raise RuntimeError(f"FileDBReader did not create XML for {tmc_file.name}.")
        self._rename_replace(generated, tmc_file.with_name(f"{tmc_file.stem}_original.xml"))

    def _start_run_tmc_process(self, command, cwd):
        if self.stop_event.is_set():
            raise RuntimeError("Stop requested")
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 2
            process = subprocess.Popen(
                [str(value) for value in command], cwd=str(cwd),
                startupinfo=startupinfo, creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            process = subprocess.Popen([str(value) for value in command], cwd=str(cwd))
        with self.parallel_processes_lock:
            self.parallel_processes.add(process)
        try:
            while process.poll() is None:
                if self.stop_event.is_set():
                    self._kill_specific_process(process)
                    raise RuntimeError("Stop requested")
                time.sleep(0.1)
            if process.returncode:
                raise RuntimeError(f"FileDBReader exited with code {process.returncode}.")
        finally:
            with self.parallel_processes_lock:
                self.parallel_processes.discard(process)

    def _start_choose_source_variant(self, source):
        """Select one root-level A7M before naming or copying the new island."""
        variants = sorted(
            (p for p in Path(source).iterdir()
             if p.is_file() and p.suffix.casefold() == ".a7m"),
            key=lambda p: p.name.casefold(),
        )
        if not variants:
            messagebox.showerror("Create Custom Island", "No .a7m file was found in the selected source folder.")
            return None
        if len(variants) == 1:
            return variants[0]
        dialog = PopupTemplate.create_window(
            self, title="Select island variant", heading="Select island variant",
            geometry="760x480", min_size=(600, 360), modal=True, maximize=False,
        )["window"]
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(
            dialog, text="Choose the A7M variant to copy. Other map variants will be excluded.",
            wraplength=650, justify="left",
        ).grid(row=1, column=0, padx=18, pady=(0, 10), sticky="w")
        choices = ctk.CTkScrollableFrame(dialog)
        choices.grid(row=2, column=0, padx=18, pady=(0, 12), sticky="nsew")
        choices.grid_columnconfigure(0, weight=1)
        selected = tk.StringVar(master=dialog, value=str(variants[0]))
        for index, path in enumerate(variants):
            ctk.CTkRadioButton(
                choices, text=path.name, variable=selected, value=str(path),
            ).grid(row=index, column=0, padx=12, pady=10, sticky="w")
        result = {"path": None}
        def accept():
            result["path"] = Path(selected.get())
            dialog.destroy()
        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.grid(row=3, column=0, padx=18, pady=(0, 18), sticky="e")
        ctk.CTkButton(actions, text="Cancel", width=110, command=dialog.destroy).pack(side="left", padx=8)
        ctk.CTkButton(actions, text="Use variant", width=140, command=accept).pack(side="left")
        dialog.bind("<Return>", lambda _event: accept())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        self.wait_window(dialog)
        return result["path"]

    @staticmethod
    def _start_variant_copy_plan(source, selected, new_name):
        """Prune other variants before traversal; keep shared container names."""
        source, selected = Path(source), Path(selected)
        if selected.parent.resolve() != source.resolve() or not selected.is_file():
            raise ValueError("The selected A7M must belong to the source folder.")
        variants = {p.stem.casefold() for p in source.iterdir()
                    if p.is_file() and p.suffix.casefold() == ".a7m"}
        chosen = selected.stem.casefold()
        if chosen not in variants:
            raise ValueError("The selected variant is no longer available.")
        # Longest names first: map and map_extra are separate variants.
        ordered = sorted(variants, key=len, reverse=True)
        def file_owner(name):
            folded = name.casefold()
            for stem in ordered:
                if folded.startswith(stem + ".") or any(
                    folded.startswith(stem + marker)
                    for marker in ("_original.", "_patched.", "_backup_")
                ):
                    return stem
            return None
        directories, files, targets = [], [], set()
        def target_path(relative, is_file):
            parts = list(relative.parts)
            for index in range(len(parts) - (1 if is_file else 0)):
                if parts[index].casefold() == chosen:
                    parts[index] = new_name
            if is_file and len(parts) == 1 and file_owner(parts[-1]) == chosen:
                parts[-1] = new_name + parts[-1][len(selected.stem):]
            result = Path(*parts)
            key = result.as_posix().casefold()
            if key in targets:
                raise ValueError(f"Conflicting destination path: {result}")
            targets.add(key)
            return result
        def walk_error(error):
            raise error
        for folder, dirs, names in os.walk(source, followlinks=False, onerror=walk_error):
            folder = Path(folder)
            # Symlinks are rejected rather than copying data outside the package.
            for name in dirs + names:
                if (folder / name).is_symlink():
                    raise ValueError(f"Symbolic links are not supported: {folder / name}")
            dirs[:] = sorted(
                (name for name in dirs
                 if name.casefold() not in variants or name.casefold() == chosen),
                key=str.casefold,
            )
            for name in dirs:
                relative = (folder / name).relative_to(source)
                directories.append(target_path(relative, False))
            for name in sorted(names, key=str.casefold):
                path = folder / name
                if folder == source:
                    owner = file_owner(name)
                    if owner is not None and owner != chosen:
                        continue
                files.append((path, target_path(path.relative_to(source), True)))
        return directories, files
