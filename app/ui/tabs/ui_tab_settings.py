from __future__ import annotations

import customtkinter as ctk


class SettingsTabMixin:
    """Settings UI split into tabs with fixed bottom-right actions."""

    def _build_settings_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=0)

        settings_tabs = ctk.CTkTabview(tab)
        settings_tabs.grid(row=0, column=0, padx=5, pady=(5, 0), sticky="nsew")

        general_tab = settings_tabs.add("General")
        map_folders_tab = settings_tabs.add("Map Folders")
        custom_tab = settings_tabs.add("Custom")
        expert_tab = settings_tabs.add("Expert Settings")
        settings_tabs.set("General")

        for settings_tab in (general_tab, map_folders_tab, custom_tab, expert_tab):
            settings_tab.grid_columnconfigure(0, weight=1)
            settings_tab.grid_rowconfigure(0, weight=1)

        general_box = ctk.CTkScrollableFrame(general_tab, orientation="vertical")
        general_box.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        general_box.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            general_box,
            text="Gamefiles",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 5), sticky="w")

        source = ctk.CTkFrame(general_box)
        source.grid(row=1, column=0, columnspan=3, padx=5, pady=(5, 10), sticky="ew")
        source.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(source, text="Folder 'maindata':").grid(
            row=0, column=0, padx=(15, 8), pady=14, sticky="w"
        )
        ctk.CTkEntry(source, textvariable=self.gamefiles_var).grid(
            row=0, column=1, padx=8, pady=14, sticky="ew"
        )
        ctk.CTkButton(
            source,
            text="Browse",
            width=110,
            command=self._select_gamefiles_folder,
        ).grid(row=0, column=2, padx=(8, 15), pady=14)

        ctk.CTkLabel(
            general_box,
            text="Programs",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=2, column=0, columnspan=3, padx=15, pady=(15, 5), sticky="w")
        self._path_row(
            general_box,
            3,
            "RdaConsole.exe:",
            self.rda_var,
            lambda: self._select_exe(self.rda_var, "RdaConsole.exe"),
        )
        self._path_row(general_box, 4, "FileDBReader.exe:", self.fdb_var, self._select_fdb)

        ctk.CTkLabel(
            general_box,
            text="TMC parallel processes",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=5, column=0, columnspan=3, padx=15, pady=(18, 5), sticky="w")
        ctk.CTkLabel(general_box, text="Parallel processes:").grid(
            row=6, column=0, padx=(15, 8), pady=6, sticky="w"
        )
        ctk.CTkEntry(general_box, textvariable=self.tmc_parallel_var, width=90).grid(
            row=6, column=1, padx=8, pady=6, sticky="w"
        )
        ctk.CTkLabel(general_box, text="Default: 4", text_color="gray70").grid(
            row=6, column=2, padx=(8, 15), pady=6, sticky="w"
        )

        map_folders_box = ctk.CTkScrollableFrame(map_folders_tab, orientation="vertical")
        map_folders_box.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        map_folders_box.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            map_folders_box,
            text="Map folders",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 5), sticky="w")
        self._folder_path_row(
            map_folders_box,
            1,
            "Original Maps:",
            self.original_maps_var,
            "Select default source folder for original maps",
        )
        self._folder_path_row(
            map_folders_box,
            2,
            "Custom Map Folder:",
            self.custom_map_folder_var,
            "Select custom map folder",
        )
        self._folder_path_row(
            map_folders_box,
            3,
            "Temporary Map Folder:",
            self.default_custom_maps_var,
            "Select temporary map folder",
        )
        self._folder_path_row(
            map_folders_box,
            4,
            "Map Export Folder:",
            self.map_export_folder_var,
            "Select map export folder",
        )

        custom_box = ctk.CTkScrollableFrame(custom_tab, orientation="vertical")
        custom_box.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        custom_box.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            custom_box,
            text="Custom material sets",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 5), sticky="w")
        self._folder_path_row(
            custom_box,
            1,
            "Custom Material Sets Folder:",
            self.custom_material_sets_folder_var,
            "Select custom material sets folder",
        )

        ctk.CTkLabel(
            custom_box,
            text=(
                "Custom Material Sets can be selected in the Regional Settings tab "
                "under MaterialSetFileName from the dropdown menu under 'Custom'."
            ),
            text_color="gray70",
            anchor="w",
            justify="left",
            wraplength=850,
        ).grid(row=2, column=0, columnspan=3, padx=15, pady=(2, 10), sticky="ew")

        ctk.CTkLabel(
            custom_box,
            text="Custom Objects",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=3, column=0, columnspan=3, padx=15, pady=(15, 5), sticky="w")
        self._folder_path_row(
            custom_box,
            4,
            "Custom Objects Folder:",
            self.custom_objects_folder_var,
            "Select custom objects folder",
        )
        ctk.CTkLabel(
            custom_box,
            text=(
                "Custom objects defined under the 'Custom Content > Objects' tab "
                "can be stored in this folder."
            ),
            text_color="gray70",
            anchor="w",
            justify="left",
            wraplength=850,
        ).grid(row=5, column=0, columnspan=3, padx=15, pady=(2, 10), sticky="ew")

        expert_box = ctk.CTkScrollableFrame(expert_tab, orientation="vertical")
        expert_box.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        expert_box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            expert_box, text="Experimental features",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=15, pady=(15, 5), sticky="w")
        ctk.CTkCheckBox(
            expert_box, text="Experimental", variable=self.experimental_var,
            onvalue=True, offvalue=False,
        ).grid(row=1, column=0, padx=15, pady=(8, 4), sticky="w")
        ctk.CTkLabel(
            expert_box,
            text=(
                "Enables functions and UI elements marked as experimental. "
                "Experimental features may be incomplete or unstable. "
                "Currently this controls River Slot placement in Slot Configuration."
            ),
            text_color="#ff6b6b", anchor="w", justify="left", wraplength=850,
        ).grid(row=2, column=0, padx=15, pady=(4, 15), sticky="ew")

        footer = ctk.CTkFrame(tab, fg_color="transparent")
        footer.grid(row=1, column=0, padx=20, pady=(10, 15), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            footer,
            text=f"Configuration: {self.CONFIG_FILE}",
            text_color="gray70",
        ).grid(row=0, column=0, sticky="w")

        buttons = ctk.CTkFrame(footer, fg_color="transparent")
        buttons.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            buttons,
            text="Validate paths",
            fg_color="#555",
            hover_color="#666",
            command=self._validate_settings_dialog,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            buttons,
            text="Save settings",
            command=self._save_config_with_feedback,
        ).pack(side="left")
