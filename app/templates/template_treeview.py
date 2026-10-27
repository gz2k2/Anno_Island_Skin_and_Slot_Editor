"""Reusable dark Treeview template with sorting and content-based widths."""
from __future__ import annotations

import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk



class _DynamicTreeview(ttk.Treeview):
    """Treeview that coalesces content-width recalculation after row changes."""

    def configure_dynamic_widths(
        self, headings, min_widths, max_widths, padding=24
    ):
        self._dynamic_headings = dict(headings)
        self._dynamic_min_widths = dict(min_widths)
        self._dynamic_max_widths = dict(max_widths)
        self._dynamic_padding = int(padding)
        self._dynamic_width_after_id = None
        self.schedule_autosize()

    def schedule_autosize(self):
        after_id = getattr(self, "_dynamic_width_after_id", None)
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        self._dynamic_width_after_id = self.after_idle(self.autosize_columns)

    def autosize_columns(self):
        self._dynamic_width_after_id = None
        headings = getattr(self, "_dynamic_headings", {})
        if not headings:
            return
        body_font = tkfont.nametofont("TkDefaultFont")
        heading_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        padding = getattr(self, "_dynamic_padding", 24)
        children = self.get_children("")
        for column in self["columns"]:
            header = headings.get(column, column)
            required = heading_font.measure(str(header)) + padding
            for item in children:
                required = max(required, body_font.measure(str(self.set(item, column))) + padding)
            minimum = self._dynamic_min_widths.get(column, 80)
            maximum = self._dynamic_max_widths.get(column, 420)
            self.column(column, width=max(minimum, min(required, maximum)))

    def insert(self, *args, **kwargs):
        item = super().insert(*args, **kwargs)
        if hasattr(self, "_dynamic_headings"):
            self.schedule_autosize()
        return item

    def delete(self, *items):
        result = super().delete(*items)
        if hasattr(self, "_dynamic_headings"):
            self.schedule_autosize()
        return result


class _TreeviewCellInteraction:
    """Track one clicked cell, draw its border and expose copy commands."""

    BORDER_COLOR = "#4da3ff"

    def __init__(self, tree):
        self.tree = tree
        self.item = ""
        self.column = ""
        self.value = ""
        self.overlay = None
        self.menu = tk.Menu(tree, tearoff=False)
        self.menu.add_command(label="Copy", command=self.copy)
        tree.bind("<Button-1>", self.on_left_click, add="+")
        tree.bind("<Button-3>", self.on_right_click, add="+")
        tree.bind("<Control-c>", self.copy, add="+")
        tree.bind("<Control-C>", self.copy, add="+")
        tree.bind("<Configure>", self.redraw, add="+")

    def _cell_at(self, event):
        item = self.tree.identify_row(event.y)
        display_column = self.tree.identify_column(event.x)
        if not item or not display_column or display_column == "#0":
            return None
        try:
            index = int(display_column[1:]) - 1
            column = self.tree["columns"][index]
        except (ValueError, IndexError):
            return None
        return item, column

    def select(self, item, column):
        self.item = item
        self.column = column
        self.value = str(self.tree.set(item, column))
        self.tree.focus_set()
        self.redraw()

    def on_left_click(self, event):
        cell = self._cell_at(event)
        if cell is not None:
            self.select(*cell)

    def on_right_click(self, event):
        cell = self._cell_at(event)
        if cell is None:
            return
        self.select(*cell)
        # Keep the clicked row part of the normal selection model without
        # destroying an existing multi-selection when it is already selected.
        if cell[0] not in self.tree.selection():
            self.tree.selection_set(cell[0])
            self.tree.focus(cell[0])
        self.menu.tk_popup(event.x_root, event.y_root)
        self.menu.grab_release()
        return "break"

    def copy(self, _event=None):
        if not self.item or not self.column or not self.tree.exists(self.item):
            return "break"
        self.value = str(self.tree.set(self.item, self.column))
        self.tree.clipboard_clear()
        self.tree.clipboard_append(self.value)
        self.tree.update_idletasks()
        return "break"

    def redraw(self, _event=None):
        if self.overlay is not None:
            self.overlay.destroy()
            self.overlay = None
        if not self.item or not self.column or not self.tree.exists(self.item):
            return
        bbox = self.tree.bbox(self.item, self.column)
        if not bbox:
            return
        x, y, width, height = bbox
        overlay = tk.Frame(
            self.tree,
            background=TreeviewTemplate.BACKGROUND,
            highlightbackground=self.BORDER_COLOR,
            highlightcolor=self.BORDER_COLOR,
            highlightthickness=2,
            bd=0,
        )
        foreground = TreeviewTemplate.FOREGROUND
        item_tags = self.tree.item(self.item, "tags")
        tag_styles = getattr(self.tree, "_template_tag_styles", {})
        for tag_name in item_tags:
            configured = tag_styles.get(tag_name, {})
            if configured.get("foreground"):
                foreground = configured["foreground"]
                break
        label = tk.Label(
            overlay,
            text=str(self.tree.set(self.item, self.column)),
            background=TreeviewTemplate.BACKGROUND,
            foreground=foreground,
            anchor="w",
            padx=4,
            font=("Segoe UI", 10),
        )
        label.pack(fill="both", expand=True)
        # Forward clicks from the visual overlay to the same cell behavior.
        overlay.bind("<Button-3>", self._overlay_right_click)
        label.bind("<Button-3>", self._overlay_right_click)
        overlay.bind("<Button-1>", lambda _e: self.tree.focus_set())
        label.bind("<Button-1>", lambda _e: self.tree.focus_set())
        overlay.place(x=x, y=y, width=width, height=height)
        self.overlay = overlay

    def _overlay_right_click(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)
        self.menu.grab_release()
        return "break"


class TreeviewTemplate:
    STYLE_NAME = "AppDark.Treeview"
    BACKGROUND = "#242424"
    HEADING_BACKGROUND = "#333333"
    HEADING_ACTIVE = "#444444"
    HEADING_BORDER = "#707070"
    HEADING_DARK_BORDER = "#252525"
    FOREGROUND = "#f2f2f2"
    BORDER = "#3a3a3a"
    SELECTED = "#1f6aa5"
    ROW_HEIGHT = 28

    @classmethod
    def configure_style(cls, owner):
        style = ttk.Style(owner)
        style.theme_use("clam")
        style.configure(
            cls.STYLE_NAME,
            background=cls.BACKGROUND,
            fieldbackground=cls.BACKGROUND,
            foreground=cls.FOREGROUND,
            bordercolor=cls.BORDER,
            lightcolor=cls.BORDER,
            darkcolor=cls.BORDER,
            rowheight=cls.ROW_HEIGHT,
            font=("Segoe UI", 10),
        )
        style.configure(
            f"{cls.STYLE_NAME}.Heading",
            background=cls.HEADING_BACKGROUND,
            foreground=cls.FOREGROUND,
            bordercolor=cls.HEADING_BORDER,
            lightcolor=cls.HEADING_BORDER,
            darkcolor=cls.HEADING_DARK_BORDER,
            borderwidth=1,
            relief="raised",
            padding=(7, 5),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            cls.STYLE_NAME,
            background=[("selected", cls.SELECTED)],
            foreground=[("selected", "#ffffff")],
        )
        style.map(
            f"{cls.STYLE_NAME}.Heading",
            background=[("active", cls.HEADING_ACTIVE)],
        )
        return style

    @staticmethod
    def _sort_key(value):
        text = str(value or "").strip()
        if re.fullmatch(r"[-+]?\d+", text):
            return (0, int(text))
        if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", text):
            return (1, float(text.replace(",", ".")))
        parts = re.split(r"([-+]?\d+(?:[.,]\d+)?)", text.casefold())
        natural = []
        for part in parts:
            if not part:
                continue
            try:
                natural.append((0, float(part.replace(",", "."))))
            except ValueError:
                natural.append((1, part))
        return (2, tuple(natural))

    @classmethod
    def sort_by_column(cls, tree, column, reverse=False, headings=None):
        selected = set(tree.selection())
        focused = tree.focus()
        rows = [(tree.set(item, column), item) for item in tree.get_children("")]
        rows.sort(key=lambda pair: cls._sort_key(pair[0]), reverse=reverse)
        for index, (_value, item) in enumerate(rows):
            tree.move(item, "", index)
        for current in tree["columns"]:
            base = (headings or {}).get(current, current)
            if current == column:
                caption = f"{base} {'▼' if reverse else '▲'}"
                next_reverse = not reverse
            else:
                caption = base
                next_reverse = False
            tree.heading(
                current,
                text=caption,
                command=lambda col=current, rev=next_reverse: cls.sort_by_column(
                    tree, col, rev, headings=headings
                ),
            )
        existing = [item for item in selected if tree.exists(item)]
        if existing:
            tree.selection_set(existing)
        if focused and tree.exists(focused):
            tree.focus(focused)
            tree.see(focused)
        interaction = getattr(tree, "_cell_interaction", None)
        if interaction is not None:
            interaction.redraw()

    @classmethod
    def create(cls, parent, *, profile=None, columns=None, headings=None,
               widths=None, min_widths=None, max_widths=None, stretch=None,
               tag_styles=None, selectmode=None, on_select=None,
               sortable=True, dynamic_width=True, width_padding=24,
               selectable_cells=True):
        profile = dict(profile or {})
        columns = tuple(columns or profile.get("columns", ()))
        headings = dict(headings or profile.get("headings", {}))
        widths = dict(widths or profile.get("widths", {}))
        min_widths = dict(min_widths or profile.get("min_widths", {}))
        max_widths = dict(max_widths or profile.get("max_widths", {}))
        stretch = set(stretch or profile.get("stretch", ()))
        tag_styles = dict(tag_styles or profile.get("tag_styles", {}))
        selectmode = selectmode or profile.get("selectmode", "browse")
        if not columns:
            raise ValueError("TreeviewTemplate requires at least one column.")
        cls.configure_style(parent)
        tree = _DynamicTreeview(
            parent, columns=columns, show="headings",
            selectmode=selectmode, style=cls.STYLE_NAME,
        )
        for column in columns:
            command = (
                lambda col=column: cls.sort_by_column(tree, col, False, headings)
            ) if sortable else None
            tree.heading(column, text=headings.get(column, column), command=command)
            tree.column(
                column, width=widths.get(column, 120),
                minwidth=min_widths.get(column, 80),
                stretch=column in stretch,
            )
        tree._template_tag_styles = tag_styles
        for tag_name, options in tag_styles.items():
            tree.tag_configure(tag_name, **options)

        def scroll_y(*args):
            result = tree.yview(*args)
            interaction = getattr(tree, "_cell_interaction", None)
            if interaction is not None:
                tree.after_idle(interaction.redraw)
            return result

        def scroll_x(*args):
            result = tree.xview(*args)
            interaction = getattr(tree, "_cell_interaction", None)
            if interaction is not None:
                tree.after_idle(interaction.redraw)
            return result

        y_scroll = ttk.Scrollbar(parent, orient="vertical", command=scroll_y)
        x_scroll = ttk.Scrollbar(parent, orient="horizontal", command=scroll_x)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        if on_select is not None:
            tree.bind("<<TreeviewSelect>>", on_select)
        if dynamic_width:
            tree.configure_dynamic_widths(
                headings, min_widths, max_widths, padding=width_padding
            )
        if selectable_cells:
            tree._cell_interaction = _TreeviewCellInteraction(tree)
            redraw_after_scroll = lambda _event: tree.after_idle(
                tree._cell_interaction.redraw
            )
            tree.bind("<MouseWheel>", redraw_after_scroll, add="+")
            tree.bind("<Shift-MouseWheel>", redraw_after_scroll, add="+")
            tree.bind("<Button-4>", redraw_after_scroll, add="+")
            tree.bind("<Button-5>", redraw_after_scroll, add="+")
        return {"tree": tree, "x_scrollbar": x_scroll, "y_scrollbar": y_scroll}
