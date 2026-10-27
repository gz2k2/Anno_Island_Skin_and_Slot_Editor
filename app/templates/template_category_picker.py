
from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from app.templates.template_popup import PopupTemplate


class CategoryPickerTemplate:
    """Reusable searchable category picker for large category collections."""

    GEOMETRY = "760x680"
    MIN_SIZE = (640, 520)
    PADX = PopupTemplate.HEADER_PADX
    SEARCH_HEIGHT = 34
    GROUP_BUTTON_WIDTH = 92
    ROW_HEIGHT = 42
    TYPE_WIDTH = 300
    VARIATIONS_WIDTH = 90
    FILTER_ALL = "All"

    @staticmethod
    def group_for(category: str) -> str:
        value = (category or "").strip()
        first = value.split(None, 1)[0] if value else "Other"
        return first if first in {"Pebbles", "Rocks", "Bushes", "Flowers", "Grass", "Tree", "Deco"} else "Other"

    @classmethod
    def create(cls, owner, *, categories, selected="", color_provider=None, on_select=None, title="Select Replace-To Category"):
        rows = []
        for item in categories:
            if isinstance(item, dict):
                category = str(item.get("category", "")).strip()
                variations = int(item.get("variations", 0) or 0)
                regions = tuple(str(value).strip() for value in item.get("regions", ()) if str(value).strip())
                display_category = str(item.get("display_category", category)).strip() or category
                display_regions = tuple(str(value).strip() for value in item.get("display_regions", regions) if str(value).strip())
            else:
                category = str(item[0]).strip()
                variations = int(item[1]) if len(item) > 1 else 0
                regions = tuple(item[2]) if len(item) > 2 else ()
                display_category = category
                display_regions = regions
            if category:
                rows.append((category, variations, regions, display_category, display_regions))
        rows.sort(key=lambda x: x[0].casefold())

        state = {"window": None, "region": cls.FILTER_ALL, "group": cls.FILTER_ALL, "rows": rows}
        built = PopupTemplate.create_window(
            owner, title=title, heading=title, geometry=cls.GEOMETRY,
            min_size=cls.MIN_SIZE, close_command=lambda: cls._close(state),
        )
        window = built["window"]
        state["window"] = window
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(5, weight=1)

        search_var = tk.StringVar()
        state["search_var"] = search_var
        search_row = ctk.CTkFrame(window, fg_color="transparent")
        search_row.grid(row=1, column=0, padx=cls.PADX, pady=(0, 8), sticky="ew")
        search_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(search_row, text="Filter:").grid(row=0, column=0, padx=(0, 8), sticky="w")
        search = ctk.CTkEntry(search_row, textvariable=search_var, height=cls.SEARCH_HEIGHT,
                              placeholder_text="Search categories, e.g. 'tree jun' or 'rock snow'...")
        search.grid(row=0, column=1, sticky="ew")

        regions = [cls.FILTER_ALL] + sorted(
            {region for _category, _variations, row_regions, _display_category, _display_regions in rows for region in row_regions},
            key=str.casefold,
        )
        region_bar = ctk.CTkScrollableFrame(window, height=48, orientation="horizontal", fg_color="transparent")
        region_bar.grid(row=2, column=0, padx=cls.PADX, pady=(0, 8), sticky="ew")
        state["region_buttons"] = {}
        region_labels = {cls.FILTER_ALL: cls.FILTER_ALL}
        for _category, _variations, raw_regions, _display_category, shown_regions in rows:
            region_labels.update(zip(raw_regions, shown_regions))
        for region in regions:
            button = ctk.CTkButton(region_bar, text=region_labels.get(region, region), width=cls.GROUP_BUTTON_WIDTH,
                                   height=PopupTemplate.BUTTON_HEIGHT,
                                   command=lambda value=region: cls._set_region(state, value))
            button.pack(side="left", padx=(0, 6), pady=2)
            state["region_buttons"][region] = button

        groups = [cls.FILTER_ALL] + sorted(
            {cls.group_for(category) for category, _variations, _regions, _display_category, _display_regions in rows},
            key=str.casefold,
        )
        group_bar = ctk.CTkScrollableFrame(window, height=48, orientation="horizontal", fg_color="transparent")
        group_bar.grid(row=3, column=0, padx=cls.PADX, pady=(0, 8), sticky="ew")
        state["group_buttons"] = {}
        for group in groups:
            button = ctk.CTkButton(group_bar, text=group, width=cls.GROUP_BUTTON_WIDTH,
                                   height=PopupTemplate.BUTTON_HEIGHT,
                                   command=lambda value=group: cls._set_group(state, value))
            button.pack(side="left", padx=(0, 6), pady=2)
            state["group_buttons"][group] = button

        header = ctk.CTkFrame(window, corner_radius=4)
        header.grid(row=4, column=0, padx=cls.PADX, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Category", anchor="w", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=7, sticky="ew")
        ctk.CTkLabel(header, text="Variations", width=cls.VARIATIONS_WIDTH, anchor="e", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=10, pady=7, sticky="e")

        table = ctk.CTkScrollableFrame(window, fg_color="transparent")
        table.grid(row=5, column=0, padx=cls.PADX, pady=(2, 8), sticky="nsew")
        table.grid_columnconfigure(0, weight=1)
        state["table"] = table

        footer = ctk.CTkFrame(window, fg_color="transparent")
        footer.grid(row=6, column=0, padx=cls.PADX, pady=(0, 14), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        result_var = tk.StringVar(value="")
        state["result_var"] = result_var
        ctk.CTkLabel(footer, textvariable=result_var, text_color=PopupTemplate.SECONDARY_TEXT_COLOR).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(footer, text="Cancel", width=PopupTemplate.BUTTON_WIDTH, height=PopupTemplate.BUTTON_HEIGHT,
                      fg_color=PopupTemplate.BUTTON_FG_COLOR, hover_color=PopupTemplate.BUTTON_HOVER_COLOR,
                      command=lambda: cls._close(state)).grid(row=0, column=1, sticky="e")

        state["color_provider"] = color_provider
        state["on_select"] = on_select
        state["selected"] = selected
        search_var.trace_add("write", lambda *_: cls._render(state))
        cls._set_group(state, cls.FILTER_ALL)
        PopupTemplate.request_focus(window, widget=search, delay_ms=50)
        return window

    @classmethod
    def _set_region(cls, state, region):
        state["region"] = region
        for name, button in state["region_buttons"].items():
            active = name == region
            button.configure(
                fg_color=("#1f6aa5" if active else PopupTemplate.BUTTON_FG_COLOR),
                hover_color=("#144870" if active else PopupTemplate.BUTTON_HOVER_COLOR),
            )
        cls._render(state)

    @classmethod
    def _set_group(cls, state, group):
        state["group"] = group
        for name, button in state["group_buttons"].items():
            active = name == group
            button.configure(
                fg_color=("#1f6aa5" if active else PopupTemplate.BUTTON_FG_COLOR),
                hover_color=("#144870" if active else PopupTemplate.BUTTON_HOVER_COLOR),
            )
        cls._render(state)

    @staticmethod
    def _matches(category, search_text):
        terms = [term.casefold() for term in (search_text or "").split() if term.strip()]
        text = category.casefold()
        return all(term in text for term in terms)

    @classmethod
    def _render(cls, state):
        table = state["table"]
        for widget in table.winfo_children():
            widget.destroy()
        query = state["search_var"].get().strip()
        region = state["region"]
        group = state["group"]
        rows = [
            row for row in state["rows"]
            if (region == cls.FILTER_ALL or region in row[2])
            and (group == cls.FILTER_ALL or cls.group_for(row[0]) == group)
            and cls._matches(row[3], query)
        ]
        state["result_var"].set(f"{len(rows)} matching categories")
        if not rows:
            ctk.CTkLabel(table, text="No matching categories.", text_color=PopupTemplate.SECONDARY_TEXT_COLOR).grid(row=0, column=0, padx=10, pady=18, sticky="w")
            return
        for index, (category, variations, _regions, display_category, display_regions) in enumerate(rows):
            shade = ("gray92", "gray17") if index % 2 == 0 else ("gray86", "gray21")
            row = ctk.CTkFrame(table, fg_color=shade, corner_radius=4, height=cls.ROW_HEIGHT)
            row.grid(row=index, column=0, padx=1, pady=1, sticky="ew")
            row.grid_propagate(False)
            row.grid_columnconfigure(0, weight=1)
            color = state["color_provider"](category) if callable(state["color_provider"]) else None
            label = ctk.CTkLabel(row, text=display_category, text_color=color, anchor="w", cursor="hand2")
            label.grid(row=0, column=0, padx=10, pady=7, sticky="ew")
            count = ctk.CTkLabel(row, text=str(variations), width=cls.VARIATIONS_WIDTH, anchor="e", cursor="hand2")
            count.grid(row=0, column=1, padx=10, pady=7, sticky="e")
            for widget in (row, label, count):
                widget.bind("<Button-1>", lambda _event, item=category: cls._choose(state, item), add="+")
                widget.bind("<Double-Button-1>", lambda _event, item=category: cls._choose(state, item), add="+")

    @staticmethod
    def _choose(state, category):
        callback = state.get("on_select")
        if callable(callback):
            callback(category)
        CategoryPickerTemplate._close(state)

    @staticmethod
    def _close(state):
        window = state.get("window")
        if window is not None and window.winfo_exists():
            PopupTemplate.close_window(window)
