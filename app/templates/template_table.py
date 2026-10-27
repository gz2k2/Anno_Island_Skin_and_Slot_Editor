from __future__ import annotations

"""Reusable CustomTkinter table based on the RD3D Objects table style.

The template preserves the visual/layout principles used by the RD3D Objects
popup while keeping application-specific data, classification, Change dialogs,
and save/reset logic outside of the table component.
"""

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence
import tkinter as tk
import customtkinter as ctk


@dataclass(frozen=True)
class TableColumn:
    key: str
    title: str
    width: int = 0
    weight: int = 0
    anchor: str = "w"
    text_color: Callable[[dict], str | tuple[str, str] | None] | None = None


class TemplateTable(ctk.CTkFrame):
    """Configurable, scrollable table with RD3D Objects styling.

    Row dictionaries may contain plain values or Tk variables. Use a custom
    ``row_builder`` when a column needs two-line original/editable entries,
    buttons, option menus, or other specialized controls.
    """

    # Central style/settings for every TemplateTable instance.
    EVEN_ROW_COLOR = ("gray92", "gray17")
    ODD_ROW_COLOR = ("gray86", "gray21")
    TABLE_BACKGROUND = "transparent"
    HEADER_BACKGROUND = ("gray86", "gray20")
    HEADER_TEXT_COLOR = ("gray10", "gray90")
    BODY_TEXT_COLOR = ("gray10", "gray90")
    EDITABLE_FG_COLOR = ("white", "gray14")
    EDITABLE_TEXT_COLOR = ("gray10", "gray90")
    DISABLED_FG_COLOR = "transparent"
    DISABLED_TEXT_COLOR = ("gray25", "gray75")
    BUTTON_FG_COLOR = "#555555"
    BUTTON_HOVER_COLOR = "#666666"

    HEADER_FONT_SIZE = 13
    HEADER_FONT_WEIGHT = "bold"
    BODY_FONT_SIZE = 12
    ENTRY_FONT_SIZE = 12
    BUTTON_FONT_SIZE = 12

    DEFAULT_HEIGHT = 300
    DEFAULT_ROW_HEIGHT = 42
    COMBINED_ROW_HEIGHT = 76
    ENTRY_HEIGHT = 28
    BUTTON_WIDTH = 80
    BUTTON_HEIGHT = 30
    HEADER_CORNER_RADIUS = 4
    ROW_CORNER_RADIUS = 4
    HEADER_PADX = 5
    HEADER_PADY = 7
    CELL_PADX = 5
    CELL_PADY = 5
    ROW_PADX = 1
    ROW_PADY = 1

    # Mouse wheel settings. Windows/macOS use delta; Linux uses Button-4/5.
    SCROLL_UNITS = 20
    SCROLL_MODE = "units"

    def __init__(
        self,
        master,
        columns: Sequence[TableColumn],
        *,
        height: int | None = None,
        row_height: int | None = None,
        row_builder: Callable[[ctk.CTkFrame, dict, int], None] | None = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.columns = tuple(columns)
        height = self.DEFAULT_HEIGHT if height is None else height
        self.row_height = self.DEFAULT_ROW_HEIGHT if row_height is None else row_height
        self.row_builder = row_builder
        self.rows: list[dict] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.header = ctk.CTkFrame(self, corner_radius=self.HEADER_CORNER_RADIUS, fg_color=self.HEADER_BACKGROUND)
        self.header.grid(row=0, column=0, padx=5, pady=(5, 0), sticky="ew")
        self._configure_columns(self.header)
        self._build_header()

        self.table = ctk.CTkScrollableFrame(
            self, fg_color=self.TABLE_BACKGROUND, height=height
        )
        self.table.grid(row=1, column=0, padx=5, pady=(2, 5), sticky="nsew")
        self.table.grid_columnconfigure(0, weight=1)
        self.after_idle(self._configure_mousewheel)

    def _configure_columns(self, parent):
        for index, column in enumerate(self.columns):
            parent.grid_columnconfigure(index, weight=column.weight)

    def _build_header(self):
        for index, column in enumerate(self.columns):
            ctk.CTkLabel(
                self.header,
                text=column.title,
                width=column.width,
                anchor=column.anchor,
                font=ctk.CTkFont(size=self.HEADER_FONT_SIZE, weight=self.HEADER_FONT_WEIGHT),
                text_color=self.HEADER_TEXT_COLOR,
            ).grid(row=0, column=index, padx=self.HEADER_PADX, pady=self.HEADER_PADY, sticky="ew")

    def set_rows(self, rows: Iterable[dict]):
        self.rows = list(rows)
        self.render()

    def clear(self):
        for widget in self.table.winfo_children():
            widget.destroy()

    def render(self):
        self.clear()
        for row_index, data in enumerate(self.rows):
            shade = self.EVEN_ROW_COLOR if row_index % 2 == 0 else self.ODD_ROW_COLOR
            row = ctk.CTkFrame(
                self.table,
                fg_color=shade,
                corner_radius=self.ROW_CORNER_RADIUS,
                height=self.row_height,
            )
            row.grid(row=row_index, column=0, padx=self.ROW_PADX, pady=self.ROW_PADY, sticky="ew")
            row.grid_propagate(False)
            self._configure_columns(row)

            if self.row_builder is not None:
                self.row_builder(row, data, row_index)
            else:
                self._build_default_row(row, data)
        self.after_idle(self._configure_mousewheel)

    def _build_default_row(self, row, data: dict):
        for index, column in enumerate(self.columns):
            value = data.get(column.key, "")
            color = column.text_color(data) if column.text_color else None
            label_kwargs = {
                "textvariable": value,
            } if isinstance(value, tk.Variable) else {
                "text": str(value),
            }
            ctk.CTkLabel(
                row,
                width=column.width,
                anchor=column.anchor,
                font=ctk.CTkFont(size=self.BODY_FONT_SIZE),
                text_color=color if color is not None else self.BODY_TEXT_COLOR,
                **{key: value for key, value in label_kwargs.items() if key != "text_color"},
            ).grid(
                row=0, column=index, padx=self.CELL_PADX, pady=self.CELL_PADY, sticky="ew"
            )

    def _configure_mousewheel(self):
        try:
            self._bind_wheel_recursive(self.table)
        except tk.TclError:
            pass

    def _bind_wheel_recursive(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        widget.bind("<Button-4>", self._on_mousewheel, add="+")
        widget.bind("<Button-5>", self._on_mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_wheel_recursive(child)

    def _on_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            units = -1
        elif getattr(event, "num", None) == 5:
            units = 1
        else:
            units = -1 if getattr(event, "delta", 0) > 0 else 1
        self.table._parent_canvas.yview_scroll(units * self.SCROLL_UNITS, self.SCROLL_MODE)
        return "break"

    def scroll_to_top(self):
        try:
            self.table._parent_canvas.yview_moveto(0.0)
        except (AttributeError, tk.TclError):
            pass


def build_rd3d_style_row(
    row: ctk.CTkFrame,
    data: dict,
    _row_index: int,
):
    """Reference row builder matching RD3D Objects.

    Expected keys:
      index, type, type_color, count, original, variable, on_change
    """
    row.configure(height=TemplateTable.COMBINED_ROW_HEIGHT)
    row.grid_columnconfigure(3, weight=1)

    ctk.CTkLabel(row, text=str(data.get("index", "")), width=52, anchor="w", font=ctk.CTkFont(size=TemplateTable.BODY_FONT_SIZE), text_color=TemplateTable.BODY_TEXT_COLOR).grid(
        row=0, column=0, rowspan=2, padx=5, pady=5, sticky="nsw"
    )
    ctk.CTkLabel(
        row,
        text=str(data.get("type", "")),
        text_color=data.get("type_color"),
        width=150,
        anchor="w",
        font=ctk.CTkFont(size=TemplateTable.BODY_FONT_SIZE),
    ).grid(row=0, column=1, rowspan=2, padx=5, pady=5, sticky="nsw")
    ctk.CTkLabel(row, text=str(data.get("count", "")), width=58, anchor="w", font=ctk.CTkFont(size=TemplateTable.BODY_FONT_SIZE), text_color=TemplateTable.BODY_TEXT_COLOR).grid(
        row=0, column=2, rowspan=2, padx=5, pady=5, sticky="nsw"
    )

    original_var = tk.StringVar(value=str(data.get("original", "")))
    ctk.CTkEntry(
        row,
        textvariable=original_var,
        height=TemplateTable.ENTRY_HEIGHT,
        font=ctk.CTkFont(size=TemplateTable.ENTRY_FONT_SIZE),
        text_color=TemplateTable.DISABLED_TEXT_COLOR,
        state="disabled",
        border_width=0,
        fg_color="transparent",
    ).grid(row=0, column=3, padx=5, pady=(5, 2), sticky="ew")

    variable = data.get("variable")
    if not isinstance(variable, tk.Variable):
        variable = tk.StringVar(value=str(variable or data.get("original", "")))
    ctk.CTkEntry(row, textvariable=variable, height=TemplateTable.ENTRY_HEIGHT, border_width=1, font=ctk.CTkFont(size=TemplateTable.ENTRY_FONT_SIZE), text_color=TemplateTable.EDITABLE_TEXT_COLOR, fg_color=TemplateTable.EDITABLE_FG_COLOR).grid(
        row=1, column=3, padx=5, pady=(2, 5), sticky="ew"
    )

    on_change = data.get("on_change")
    button = ctk.CTkButton(
        row,
        text="Change",
        width=TemplateTable.BUTTON_WIDTH,
        height=TemplateTable.BUTTON_HEIGHT,
        fg_color=TemplateTable.BUTTON_FG_COLOR,
        hover_color=TemplateTable.BUTTON_HOVER_COLOR,
        font=ctk.CTkFont(size=TemplateTable.BUTTON_FONT_SIZE),
        command=(lambda var=variable: on_change(var)) if callable(on_change) else None,
    )
    if not callable(on_change):
        button.configure(state="disabled")
    button.grid(row=0, column=4, rowspan=2, padx=(5, 8), pady=8, sticky="e")


RD3D_OBJECT_COLUMNS = (
    TableColumn("index", "Index", width=52),
    TableColumn("type", "Type", width=150),
    TableColumn("count", "Count", width=58),
    TableColumn("path", "Path", weight=1),
    TableColumn("action", "", width=90),
)
