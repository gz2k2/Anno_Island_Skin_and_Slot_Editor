from __future__ import annotations

import customtkinter as ctk


class HelpersTabMixin:
    """Helper exports; application callbacks and shared log builder stay shared."""

    def _build_helpers_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)

        material = ctk.CTkFrame(tab)
        material.grid(row=0, column=0, padx=5, pady=(0, 10), sticky="ew")
        material.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(material, text="Material Sets", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=15, pady=(14, 4), sticky="w"
        )
        ctk.CTkLabel(
            material,
            text=("Exports the material_sets/ content from data0.rda through data33.rda. "
                  "Archives are processed in ascending order so later archives can overwrite older files."),
            justify="left", wraplength=760, text_color="gray70",
        ).grid(row=1, column=0, padx=15, pady=(0, 12), sticky="w")
        self.exports_material_btn = ctk.CTkButton(
            material, text="Export material_sets", width=180, height=36,
            font=ctk.CTkFont(weight="bold"), command=self._start_export_material_sets,
        )
        self.exports_material_btn.grid(row=0, column=1, rowspan=2, padx=(10, 15), pady=14)

        island = ctk.CTkFrame(tab)
        island.grid(row=1, column=0, padx=5, pady=(0, 10), sticky="ew")
        island.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(island, text="Export Island Data", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=3, padx=15, pady=(14, 4), sticky="w"
        )
        ctk.CTkLabel(
            island,
            text="Exports island data from data0.rda through data33.rda using the selected session filter.",
            justify="left", text_color="gray70",
        ).grid(row=1, column=0, columnspan=3, padx=15, pady=(0, 10), sticky="w")
        self.exports_island_buttons = []
        self.exports_island_entries = []

        # All Maps: fixed filter, intentionally not editable.
        ctk.CTkLabel(
            island, text="All Maps:", width=100, anchor="w",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=2, column=0, padx=(15, 8), pady=5, sticky="w")
        all_maps_entry = ctk.CTkEntry(island)
        all_maps_entry.insert(0, r"sessions\islands")
        all_maps_entry.configure(state="disabled")
        all_maps_entry.grid(row=2, column=1, padx=8, pady=5, sticky="ew")
        all_maps_actions = ctk.CTkFrame(island, fg_color="transparent")
        all_maps_actions.grid(row=2, column=2, padx=(8, 15), pady=5, sticky="e")
        ctk.CTkCheckBox(
            all_maps_actions,
            text="Create .lnk files for normal maps",
            variable=self.island_export_create_links_var,
        ).pack(side="left", padx=(0, 10))
        all_maps_button = ctk.CTkButton(
            all_maps_actions, text="Export All Maps", width=150,
            command=lambda: self._start_export_island_data(
                "All Maps",
                r"sessions\islands",
                replace_map_textures_with_links=self.island_export_create_links_var.get(),
                minimize_console=True,
                create_a7m_source_csv=True,
            ),
        )
        all_maps_button.pack(side="left")
        self.exports_island_buttons.append(all_maps_button)

        # Custom: user-defined RdaConsole filter, stored in config.ini.
        ctk.CTkLabel(
            island, text="Custom:", width=100, anchor="w",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=3, column=0, padx=(15, 8), pady=5, sticky="w")
        custom_entry = ctk.CTkEntry(island, textvariable=self.island_export_custom_var)
        custom_entry.grid(row=3, column=1, padx=8, pady=5, sticky="ew")
        custom_entry.bind("<FocusOut>", lambda _event: self._save_config())
        custom_entry.bind("<Return>", lambda _event: self._save_config())
        self.exports_island_entries.append(custom_entry)
        custom_button = ctk.CTkButton(
            island, text="Export Custom", width=150,
            command=lambda: self._start_export_island_data(
                "Custom", self.island_export_custom_var.get()
            ),
        )
        custom_button.grid(row=3, column=2, padx=(8, 15), pady=5)
        self.exports_island_buttons.append(custom_button)
        controls = ctk.CTkFrame(tab, fg_color="transparent")
        controls.grid(row=2, column=0, padx=5, pady=(0, 10), sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        self.exports_progress = ctk.CTkProgressBar(controls)
        self.exports_progress.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.exports_progress.set(0)
        self.exports_stop_btn = ctk.CTkButton(
            controls, text="Stop immediately", width=130, state="disabled",
            fg_color="#a83232", hover_color="#852626", command=self._stop,
        )
        self.exports_stop_btn.grid(row=0, column=1)
        self.exports_log = self._create_log(tab, 3)

