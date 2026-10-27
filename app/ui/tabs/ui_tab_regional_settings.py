from __future__ import annotations

from pathlib import Path
import tkinter as tk

import customtkinter as ctk

from app.config.config_gamedata import GLOBAL_AMBIENT_OPTIONS, VEGETATION_PROP_SET_OPTIONS


class RegionalSettingsTabMixin:
    """Regional values read from and written to gamedata/RD3D XML files."""

    def _build_regional_settings_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        title_row = ctk.CTkFrame(tab, fg_color="transparent")
        title_row.grid(row=0, column=0, padx=20, pady=(20, 12), sticky="ew")
        title_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            title_row,
            text="Regional Settings",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            title_row,
            text="Reload",
            width=140,
            command=self._reload_regional_settings,
        ).grid(row=0, column=1, sticky="e")

        # One shared grid is used for BOTH columns. This guarantees every Current/New
        # label and control uses exactly the same row geometry.
        content = ctk.CTkFrame(tab, fg_color="transparent")
        content.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")
        content.grid_columnconfigure((0, 1), weight=1, uniform="regional_columns")

        ctk.CTkLabel(
            content,
            text="Original Content",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, padx=(18, 26), pady=(18, 18), sticky="w")
        ctk.CTkLabel(
            content,
            text="New Content",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=1, padx=(26, 18), pady=(18, 18), sticky="w")

        # GlobalAmbientName: title row 1, value row 2.
        self._regional_pair_title(content, 1, "GlobalAmbientName")
        self._regional_current_box(content, 2, self.global_ambient_var)
        self._regional_option_box(
            content,
            2,
            self.new_global_ambient_var,
            list(GLOBAL_AMBIENT_OPTIONS.keys()),
        )

        # VegetationPropSetName: title row 3, value row 4.
        self._regional_pair_title(content, 3, "VegetationPropSetName")
        self._regional_current_box(content, 4, self.vegetation_prop_set_var)
        self._regional_option_box(
            content,
            4,
            self.new_vegetation_var,
            list(VEGETATION_PROP_SET_OPTIONS.keys()),
        )

        # MaterialSetFileName: title row 5. Current box spans rows 6+7 so its
        # vertical group has exactly the same height as dropdown + entry on the right.
        self._regional_pair_title(content, 5, "MaterialSetFileName")
        ctk.CTkLabel(
            content,
            textvariable=self.material_set_var,
            anchor="w",
            justify="left",
            wraplength=440,
            fg_color=("gray86", "gray20"),
            corner_radius=6,
        ).grid(
            row=6,
            column=0,
            rowspan=2,
            padx=(18, 26),
            pady=(0, 18),
            ipady=10,
            sticky="nsew",
        )

        # Keep the legacy selection variable for Finalize / Material Set Export.
        self.regional_material_set_dropdown_var = tk.StringVar(value="Select XML...")
        self.regional_material_from_var = tk.StringVar(value="The Old World")
        self.regional_material_to_var = tk.StringVar(value="The Old World")
        material_dropdown_row = ctk.CTkFrame(content, fg_color="transparent")
        material_dropdown_row.grid(
            row=6, column=1, padx=(26, 18), pady=(0, 6), sticky="ew"
        )
        material_dropdown_row.grid_columnconfigure((1, 3), weight=1)
        ctk.CTkLabel(material_dropdown_row, text="From:").grid(
            row=0, column=0, padx=(0, 5), sticky="w"
        )
        self.regional_material_from_dropdown = ctk.CTkOptionMenu(
            material_dropdown_row, variable=self.regional_material_from_var,
            values=list(self._REGIONAL_MATERIAL_REGIONS) + ["Custom"],
            dynamic_resizing=False, command=self._regional_material_from_selected,
        )
        self.regional_material_from_dropdown.grid(row=0, column=1, sticky="ew")
        ctk.CTkLabel(material_dropdown_row, text="To:").grid(
            row=0, column=2, padx=(12, 5), sticky="w"
        )
        self.regional_material_to_dropdown = ctk.CTkOptionMenu(
            material_dropdown_row, variable=self.regional_material_to_var,
            values=list(self._REGIONAL_MATERIAL_REGIONS),
            dynamic_resizing=False, command=self._regional_material_to_selected,
        )
        self.regional_material_to_dropdown.grid(row=0, column=3, sticky="ew")
        self.regional_material_set_dropdown = self.regional_material_to_dropdown
        # Synchronize loaded / manually edited paths without writing any XML.
        self.new_material_set_var.trace_add(
            "write", self._regional_material_path_changed
        )
        self._regional_material_path_changed()

        ctk.CTkEntry(
            content,
            textvariable=self.new_material_set_var,
            height=34,
        ).grid(
            row=7,
            column=1,
            padx=(26, 18),
            pady=(0, 18),
            sticky="ew",
        )


        self.regional_detected_region_var = tk.StringVar()
        ctk.CTkLabel(
            content,
            textvariable=self.regional_detected_region_var,
            anchor="w",
        ).grid(row=8, column=1, padx=(26, 18), pady=(0, 12), sticky="w")
        self._update_regional_detected_region()

        ctk.CTkButton(
            content,
            text="Save",
            height=38,
            font=ctk.CTkFont(weight="bold"),
            command=self._save_regional_settings,
        ).grid(row=9, column=1, padx=(26, 18), pady=(5, 18), sticky="ew")

        # Explicit equal row minima keep option menus and current-value boxes aligned.
        content.grid_rowconfigure(2, minsize=48)
        content.grid_rowconfigure(4, minsize=48)
        content.grid_rowconfigure(6, minsize=34)
        content.grid_rowconfigure(7, minsize=40)
        tab.after_idle(self._reload_regional_settings)

    @staticmethod
    def _regional_pair_title(parent, row, title):
        ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=row, column=0, padx=(18, 26), pady=(5, 6), sticky="w")
        ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=row, column=1, padx=(26, 18), pady=(5, 6), sticky="w")

    @staticmethod
    def _regional_current_box(parent, row, variable):
        ctk.CTkLabel(
            parent,
            textvariable=variable,
            anchor="w",
            justify="left",
            wraplength=440,
            fg_color=("gray86", "gray20"),
            corner_radius=6,
        ).grid(
            row=row,
            column=0,
            padx=(18, 26),
            pady=(0, 18),
            ipady=10,
            sticky="ew",
        )

    @staticmethod
    def _regional_option_box(parent, row, variable, values):
        ctk.CTkOptionMenu(
            parent,
            variable=variable,
            values=values,
            dynamic_resizing=False,
        ).grid(
            row=row,
            column=1,
            padx=(26, 18),
            pady=(0, 18),
            sticky="ew",
        )

    def _save_regional_settings(self):
        if not self._save_gamedata_patch():
            return
        # Regional Save has just merged into the latest patched Gamedata. Drop any
        # stale in-memory Slot trees so all following Slot operations use that file.
        self._island_slot_ram_game_tree = None
        self._island_slot_ram_map_tree = None
        # Reload the Gamedata view immediately after Save. The loader reads the
        # original document and then applies displayed New values from the patched
        # document, so Current/New controls reflect the file just written.
        self._load_gamedata_xml(show_errors=False)
        self._save_rd3d_patch()
        self._rebuild_regional_rd3d_cache()

    def _rebuild_regional_rd3d_cache(self):
        """Rebuild the RD3D RAM cache without invalidating or loading TMC."""
        if self._tmc_ram_is_busy():
            self.status_var.set(
                "Regional settings saved; RD3D cache rebuild waits for the current XML operation."
            )
            self.after(150, self._rebuild_regional_rd3d_cache)
            return

        # _rd3d_ram_complete() normally continues with _tmc_ram_preload(). Replace
        # that instance method for this one RD3D load so the TMC cache, folder identity
        # and Object Table 2 rows remain untouched.
        original_tmc_preload = self._tmc_ram_preload
        suppression_active = True

        def suppress_one_tmc_preload():
            nonlocal suppression_active
            if suppression_active:
                suppression_active = False
                self._tmc_ram_preload = original_tmc_preload
                self.status_var.set("Regional settings saved; RD3D cache rebuilt.")
                return True
            return original_tmc_preload()

        self.rd3d_ram_cache = None
        self.object_configuration_table1_rows = []
        self._tmc_ram_preload = suppress_one_tmc_preload
        self.tmc_ram_info.set("XML cache: rebuilding RD3D after Regional Save...")
        self.status_var.set("Regional settings saved; rebuilding RD3D cache...")

        started = self._rd3d_ram_preload()
        if not started:
            suppression_active = False
            self._tmc_ram_preload = original_tmc_preload

    def _reload_regional_settings(self):
        gamedata_path = Path(self.gamedata_file_var.get().strip())
        if gamedata_path.is_file():
            self._load_gamedata_xml(show_errors=False)
        else:
            self.global_ambient_var.set("-")
            self.vegetation_prop_set_var.set("-")

        rd3d_path = Path(self.rd3d_file_var.get().strip())
        if rd3d_path.is_file():
            self._load_rd3d_xml(show_errors=False)
        else:
            self.material_set_var.set("-")

    _REGIONAL_MATERIAL_REGIONS = {
        "Arctic": "arctic",
        "Enbesa": "enbesa",
        "Enbesa Scenario": "enbesa-scenario02",
        "The New World": "nw",
        "The Old World": "ow",
    }

    def _regional_custom_material_names(self):
        """List only external custom files, never bundled conversion files."""
        names = set()
        for folder in self._material_set_search_dirs():
            folder = Path(folder)
            if folder.name not in {"custom_material_sets", "custom_materialsets"}:
                continue
            if folder.is_dir():
                for pattern in ("*.xml", "*.materialset"):
                    names.update(p.stem for p in folder.glob(pattern) if p.is_file())
        return sorted(names, key=str.casefold)

    def _regional_material_configure_to(self, custom, selected=None):
        if custom:
            values = self._regional_custom_material_names()
            self.regional_material_to_dropdown.configure(
                values=values or ["No custom material set files found"],
                state="normal" if values else "disabled",
            )
            self.regional_material_to_var.set(
                selected if selected in values else
                (values[0] if values else "No custom material set files found")
            )
        else:
            values = list(self._REGIONAL_MATERIAL_REGIONS)
            self.regional_material_to_dropdown.configure(values=values, state="normal")
            self.regional_material_to_var.set(
                selected if selected in values else self.regional_material_from_var.get()
            )

    def _regional_material_from_selected(self, value):
        previous_target = self.regional_material_to_var.get()
        self._regional_material_configure_to(value == "Custom", previous_target)
        self._regional_material_apply_selection()

    def _regional_material_to_selected(self, _value):
        self._regional_material_apply_selection()

    def _regional_material_apply_selection(self):
        source = self.regional_material_from_var.get()
        target = self.regional_material_to_var.get()
        if source == "Custom":
            if target not in self._regional_custom_material_names():
                self.regional_material_set_dropdown_var.set("Select XML...")
                return
            filename = target
        else:
            regions = self._REGIONAL_MATERIAL_REGIONS
            if source not in regions or target not in regions:
                return
            src, dst = regions[source], regions[target]
            filename = ("enbesa_" if src == "enbesa" else src) if src == dst else f"{src}_to_{dst}"
        self.regional_material_set_dropdown_var.set(filename)
        self._regional_material_selection_active = True
        try:
            self.new_material_set_var.set(f"data/config/engine/material_sets/{filename}.xml")
        finally:
            self._regional_material_selection_active = False

    def _regional_material_path_changed(self, *_args):
        """Reflect loaded paths in both menus; never replace a loaded value."""
        if getattr(self, "_regional_material_selection_active", False):
            return
        value = self.new_material_set_var.get().strip().replace("\\", "/")
        filename = Path(value).stem if value else ""
        self.regional_material_set_dropdown_var.set(filename or "Select XML...")
        reverse = {code: label for label, code in self._REGIONAL_MATERIAL_REGIONS.items()}
        if "_to_" in filename:
            source, target = filename.split("_to_", 1)
        else:
            source = target = "enbesa" if filename == "enbesa_" else filename
        if source in reverse and target in reverse:
            self.regional_material_from_var.set(reverse[source])
            self._regional_material_configure_to(False, reverse[target])
        elif filename:
            self.regional_material_from_var.set("Custom")
            self._regional_material_configure_to(True, filename)
        else:
            self._regional_material_configure_to(
                self.regional_material_from_var.get() == "Custom",
                self.regional_material_to_var.get(),
            )

    def _update_regional_detected_region(self):
        """Show original-region metadata below the editable materialset path."""
        variable = getattr(self, "regional_detected_region_var", None)
        if variable is not None:
            region = getattr(self, "original_region_name", "") or "Unknown"
            variable.set(f"Detected region: {region}")
