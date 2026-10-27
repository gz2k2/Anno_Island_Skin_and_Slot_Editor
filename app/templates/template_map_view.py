from __future__ import annotations

import math
from pathlib import Path
import app.backend.xml_backend as ET
from PIL import Image, ImageTk
import tkinter as tk
import customtkinter as ctk
from app.templates.template_popup import PopupTemplate


class MapViewTemplate:
    """Single visual/interaction source for all overview-map views."""

    WINDOW_GEOMETRY = PopupTemplate.WINDOW_GEOMETRY
    WINDOW_MIN_SIZE = PopupTemplate.WINDOW_MIN_SIZE
    WINDOW_TOPMOST = PopupTemplate.WINDOW_TOPMOST

    CANVAS_BACKGROUND = "#151719"
    PRIMARY_TEXT_COLOR = ("gray10", "gray90")
    SECONDARY_TEXT_COLOR = "gray70"
    SELECTION_BACKGROUND = ("gray86", "gray20")
    EMPTY_TEXT_COLOR = "#8b9298"
    BACKGROUND_BORDER_COLOR = "#394047"
    BACKGROUND_BORDER_WIDTH = 1

    HEADING_FONT_SIZE = 22
    HELP_HEADING_FONT_SIZE = 13
    INFO_FONT_SIZE = 12
    HELP_FONT_SIZE = 12
    SELECTION_FONT_SIZE = 12

    MAP_MARGIN = 28
    BACKGROUND_IMAGE_NAME = "mapimage.png"

    # Shared zoom-level overlay used by Slot Map and Object Map.
    ZOOM_INDICATOR_TAG = "map_zoom_indicator"
    ZOOM_INDICATOR_X = 12
    ZOOM_INDICATOR_Y = 12
    ZOOM_INDICATOR_PAD_X = 9
    ZOOM_INDICATOR_PAD_Y = 5
    ZOOM_INDICATOR_BACKGROUND = "#202428"
    ZOOM_INDICATOR_OUTLINE = "#596168"
    ZOOM_INDICATOR_TEXT = "#F2F4F5"
    ZOOM_INDICATOR_FONT = ("TkDefaultFont", 10, "bold")

    DEFAULT_POINT_ZOOM = 1.0
    DEFAULT_SHARED_ZOOM = 1.0
    POINT_ZOOM_STEP = 0.5
    SHARED_ZOOM_STEP = 0.5
    MIN_ZOOM = 1.0
    REDRAW_DELAY_MS = 25
    ZOOM_DEBOUNCE_MS = 500
    IMAGE_CACHE_LIMIT = 8

    DOT_RADIUS = 4.0
    DOT_HOVER_SCALE = 2.0
    DOT_OUTLINE_COLOR = "#111111"
    DOT_HOVER_OUTLINE_COLOR = "#ffffff"
    DOT_OUTLINE_WIDTH = 1
    DOT_HOVER_OUTLINE_WIDTH = 2
    HIT_RADIUS = 10
    HOVER_HIT_RADIUS = 8

    LEGEND_COLUMNS = 6
    LEGEND_BUTTON_WIDTH = 120
    LEGEND_BUTTON_HEIGHT = 28
    LEGEND_PADX = 6
    LEGEND_PADY = 3
    LEGEND_ACTIVE_FG_COLOR = "#34383c"
    LEGEND_INACTIVE_FG_COLOR = "#17191b"
    LEGEND_HOVER_COLOR = "#454b50"
    LEGEND_INACTIVE_TEXT_COLOR = "#6f757a"
    LEGEND_BORDER_WIDTH = 1

    @classmethod
    def point_visible(cls, canvas, x, y, radius=None):
        """Return True when a point overlaps the visible canvas viewport."""
        if canvas is None:
            return False
        radius = cls.DOT_RADIUS if radius is None else max(0.0, float(radius))
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        return (
            x + radius >= 0
            and y + radius >= 0
            and x - radius <= width
            and y - radius <= height
        )

    @classmethod
    def draw_zoom_indicator(cls, canvas, zoom):
        """Draw or refresh the shared zoom percentage overlay."""
        if canvas is None:
            return
        try:
            if not canvas.winfo_exists():
                return
        except tk.TclError:
            return
        canvas.delete(cls.ZOOM_INDICATOR_TAG)
        try:
            percent = max(0, round(float(zoom) * 100))
        except (TypeError, ValueError, OverflowError):
            percent = 100
        text = f"Zoom {percent}%"
        x = cls.ZOOM_INDICATOR_X
        y = cls.ZOOM_INDICATOR_Y
        text_id = canvas.create_text(
            x + cls.ZOOM_INDICATOR_PAD_X,
            y + cls.ZOOM_INDICATOR_PAD_Y,
            text=text,
            anchor="nw",
            fill=cls.ZOOM_INDICATOR_TEXT,
            font=cls.ZOOM_INDICATOR_FONT,
            tags=("map_overlay", cls.ZOOM_INDICATOR_TAG),
        )
        bbox = canvas.bbox(text_id)
        if bbox is not None:
            left, top, right, bottom = bbox
            background = canvas.create_rectangle(
                left - cls.ZOOM_INDICATOR_PAD_X,
                top - cls.ZOOM_INDICATOR_PAD_Y,
                right + cls.ZOOM_INDICATOR_PAD_X,
                bottom + cls.ZOOM_INDICATOR_PAD_Y,
                fill=cls.ZOOM_INDICATOR_BACKGROUND,
                outline=cls.ZOOM_INDICATOR_OUTLINE,
                width=1,
                tags=("map_overlay", cls.ZOOM_INDICATOR_TAG),
            )
            canvas.tag_lower(background, text_id)
        canvas.tag_raise(cls.ZOOM_INDICATOR_TAG)

    @classmethod
    def draw_dot(cls, canvas, x, y, color, *, hovered=False, warning=False,
                 tags=("map_content", "map_point")):
        """Draw one visible dot; warning dots get white and red outer rings."""
        radius = cls.DOT_RADIUS * cls.DOT_HOVER_SCALE if hovered else cls.DOT_RADIUS
        outer_radius = radius + 4 if warning else radius
        if not cls.point_visible(canvas, x, y, outer_radius):
            return None
        state = "hidden" if cls.zoom_active(canvas) else "normal"
        if warning:
            canvas.create_oval(
                x-outer_radius, y-outer_radius, x+outer_radius, y+outer_radius,
                fill="", outline="#E53935", width=2, state=state, tags=tags,
            )
            canvas.create_oval(
                x-(radius+2), y-(radius+2), x+(radius+2), y+(radius+2),
                fill="", outline="#FFFFFF", width=2, state=state, tags=tags,
            )
        return canvas.create_oval(
            x-radius, y-radius, x+radius, y+radius,
            fill=color,
            outline=cls.DOT_HOVER_OUTLINE_COLOR if hovered else cls.DOT_OUTLINE_COLOR,
            width=cls.DOT_HOVER_OUTLINE_WIDTH if hovered else cls.DOT_OUTLINE_WIDTH,
            state=state, tags=tags,
        )


    @classmethod
    def cached_photo(cls, source, width, height, cache):
        """Return a fast BILINEAR map image and retain only recent zoom sizes."""
        key = (id(source), max(1, int(width)), max(1, int(height)))
        photo = cache.get(key)
        if photo is None:
            resized = source.resize((key[1], key[2]), Image.Resampling.BILINEAR)
            photo = ImageTk.PhotoImage(resized)
            cache[key] = photo
            while len(cache) > cls.IMAGE_CACHE_LIMIT:
                cache.pop(next(iter(cache)))
        return photo

    @classmethod
    def cached_viewport_photo(cls, source, image_x, image_y, image_width,
                              image_height, canvas_width, canvas_height, cache):
        """Render only the visible source-image area, independent of zoom size.

        The returned PhotoImage never exceeds the canvas viewport. This avoids
        allocating a complete multi-megapixel image at high zoom levels.
        """
        if source is None or image_width <= 0 or image_height <= 0:
            return None, 0.0, 0.0

        left = max(0.0, float(image_x))
        top = max(0.0, float(image_y))
        right = min(float(canvas_width), float(image_x + image_width))
        bottom = min(float(canvas_height), float(image_y + image_height))
        if right <= left or bottom <= top:
            return None, left, top

        source_width, source_height = source.size
        sx0 = max(0, int((left - image_x) / image_width * source_width))
        sy0 = max(0, int((top - image_y) / image_height * source_height))
        sx1 = min(source_width, int(((right - image_x) / image_width * source_width) + 0.999999))
        sy1 = min(source_height, int(((bottom - image_y) / image_height * source_height) + 0.999999))
        if sx1 <= sx0 or sy1 <= sy0:
            return None, left, top

        target_width = max(1, int(round(right - left)))
        target_height = max(1, int(round(bottom - top)))
        key = (
            id(source), sx0, sy0, sx1, sy1,
            target_width, target_height,
        )
        photo = cache.get(key)
        if photo is None:
            visible = source.crop((sx0, sy0, sx1, sy1))
            if visible.size != (target_width, target_height):
                visible = visible.resize(
                    (target_width, target_height), Image.Resampling.BILINEAR
                )
            photo = ImageTk.PhotoImage(visible)
            cache[key] = photo
            while len(cache) > cls.IMAGE_CACHE_LIMIT:
                cache.pop(next(iter(cache)))
        return photo, left, top

    @classmethod
    def create_hover_marker(cls, canvas):
        radius = cls.DOT_RADIUS * cls.DOT_HOVER_SCALE
        return canvas.create_oval(
            -radius, -radius, radius, radius,
            fill="", outline=cls.DOT_HOVER_OUTLINE_COLOR,
            width=cls.DOT_HOVER_OUTLINE_WIDTH, state="hidden",
            tags=("map_content", "map_hover"),
        )

    @classmethod
    def position_hover_marker(cls, canvas, item, point, color=None):
        if not item or not point:
            if item:
                canvas.itemconfigure(item, state="hidden")
            return
        radius = cls.DOT_RADIUS * cls.DOT_HOVER_SCALE
        x, y = point[0], point[1]
        canvas.coords(item, x-radius, y-radius, x+radius, y+radius)
        state = "hidden" if cls.zoom_active(canvas) else "normal"
        canvas.itemconfigure(item, state=state, fill=color or "")
        canvas.tag_raise(item)

    @classmethod
    def nearest_point(cls, points, mouse_x, mouse_y, *, hover=False):
        if not points:
            return None
        point = min(points, key=lambda item: (item[0]-mouse_x)**2 + (item[1]-mouse_y)**2)
        radius = cls.HOVER_HIT_RADIUS if hover else cls.HIT_RADIUS
        distance = (point[0]-mouse_x)**2 + (point[1]-mouse_y)**2
        return point if distance <= radius**2 else None

    @classmethod
    def nearest_visible_point(cls, points, mouse_x, mouse_y, *, hover=False, visible=None):
        """Return the nearest selectable point after applying the current map filter."""
        candidates = points or ()
        if visible is not None:
            candidates = [point for point in candidates if visible(point)]
        return cls.nearest_point(candidates, mouse_x, mouse_y, hover=hover)

    @classmethod
    def point_from_event(cls, event, points, *, hover=False, visible=None):
        """Shared event hit-test used by hover, click, context menu and dragging."""
        return cls.nearest_visible_point(
            points, event.x, event.y, hover=hover, visible=visible
        )

    @classmethod
    def world_from_event(cls, event, canvas, bounds, zoom, pan_x, pan_y, margin=None):
        """Invert the exact canvas transform currently used to draw a map view."""
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        margin = cls.MAP_MARGIN if margin is None else margin
        lo, hi, bottom, top = bounds
        span_x, span_z = hi - lo, top - bottom
        if span_x <= 0 or span_z <= 0:
            raise ValueError("The playable map bounds are invalid.")
        scale = min((width - 2 * margin) / span_x, (height - 2 * margin) / span_z) * zoom
        if scale <= 0:
            raise ValueError("The map viewport is too small.")
        left = (width - span_x * scale) / 2 + pan_x
        upper = (height - span_z * scale) / 2 + pan_y
        world_x = lo + (event.x - left) / scale
        world_z = top - (event.y - upper) / scale
        if not lo <= world_x <= hi or not bottom <= world_z <= top:
            raise ValueError("Click inside the playable map area.")
        return world_x, world_z

    MOVE_CURSOR_TAG = "__map_move_cursor__"
    MOVE_CURSOR_COLOR = "#ff3030"
    MOVE_CURSOR_SIZE = 8
    MOVE_CURSOR_WIDTH = 2

    @classmethod
    def build_dot_movement_checkbox(
        cls, parent, variable, *, row=0, column=2, command=None, canvas=None
    ):
        """Build shared Undo + movement controls used by every map view."""
        undo_button = ctk.CTkButton(
            parent, text="Undo", width=70,
            command=lambda: cls.dot_movement_undo(canvas),
        )
        undo_button.grid(row=row, column=column - 1, padx=(8, 0), sticky="e")
        undo_button.grid_remove()
        if canvas is not None:
            canvas._map_dot_undo_button = undo_button
            canvas._map_dot_history = []

        checkbox = ctk.CTkCheckBox(
            parent,
            text="Allow Dot Movement",
            variable=variable,
            onvalue=True,
            offvalue=False,
            command=command,
        )
        checkbox.grid(row=row, column=column, padx=(8, 4), sticky="e")
        return checkbox

    @staticmethod
    def update_dot_movement_undo(canvas, enabled):
        """Show Undo only while movement is enabled; disable it when history is empty."""
        if canvas is None:
            return
        button = getattr(canvas, "_map_dot_undo_button", None)
        if button is None:
            return
        if enabled:
            button.grid()
            button.configure(state="normal" if getattr(canvas, "_map_dot_history", []) else "disabled")
        else:
            button.grid_remove()

    @classmethod
    def dot_movement_push_undo(cls, canvas, undo_action):
        """Store at most the five most recent successful dot movements."""
        if canvas is None or not callable(undo_action):
            return
        history = getattr(canvas, "_map_dot_history", None)
        if history is None:
            history = []
            canvas._map_dot_history = history
        history.append(undo_action)
        del history[:-5]
        cls.update_dot_movement_undo(canvas, True)

    @classmethod
    def dot_movement_undo(cls, canvas):
        """Undo the most recent movement from the shared five-entry history."""
        history = getattr(canvas, "_map_dot_history", []) if canvas is not None else []
        if not history:
            cls.update_dot_movement_undo(canvas, True)
            return
        undo_action = history.pop()
        undo_action()
        cls.update_dot_movement_undo(canvas, True)

    @classmethod
    def set_dot_movement_cursor(cls, canvas, enabled, event=None):
        """Show a red crosshair while dot movement is enabled."""
        if canvas is None:
            return
        canvas.delete(cls.MOVE_CURSOR_TAG)
        canvas.configure(cursor="none" if enabled else "")
        if not enabled or event is None:
            return
        x, y, size = event.x, event.y, cls.MOVE_CURSOR_SIZE
        canvas.create_line(
            x-size, y, x+size, y,
            fill=cls.MOVE_CURSOR_COLOR, width=cls.MOVE_CURSOR_WIDTH,
            tags=cls.MOVE_CURSOR_TAG,
        )
        canvas.create_line(
            x, y-size, x, y+size,
            fill=cls.MOVE_CURSOR_COLOR, width=cls.MOVE_CURSOR_WIDTH,
            tags=cls.MOVE_CURSOR_TAG,
        )
        canvas.tag_raise(cls.MOVE_CURSOR_TAG)

    @classmethod
    def build_legend_button(cls, parent, *, text, color, visible, command, row, column):
        """Identical clickable legend/category label for every map."""
        button = ctk.CTkButton(
            parent,
            text=text,
            width=cls.LEGEND_BUTTON_WIDTH,
            height=cls.LEGEND_BUTTON_HEIGHT,
            text_color=color if visible else cls.LEGEND_INACTIVE_TEXT_COLOR,
            fg_color=cls.LEGEND_ACTIVE_FG_COLOR if visible else cls.LEGEND_INACTIVE_FG_COLOR,
            hover_color=cls.LEGEND_HOVER_COLOR,
            border_width=cls.LEGEND_BORDER_WIDTH,
            border_color=color,
            command=command,
        )
        button.grid(
            row=row, column=column,
            padx=(0, cls.LEGEND_PADX), pady=cls.LEGEND_PADY, sticky="w",
        )
        return button

    @staticmethod
    def build_map_window(
        owner, *, title, heading="Overview map", info_variable, selection_variable,
        close_command, redraw_command, legend_builder,
        maximize_button_attribute=None, object_edit_help=False,
        slot_edit_help=False, **_unused,
    ):
        built = PopupTemplate.create_window(
            owner, title=title, heading=heading,
            close_command=close_command, add_header=True, maximize=True,
        )
        window = built["window"]
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(4, weight=1)
        if maximize_button_attribute:
            setattr(owner, maximize_button_attribute, built["maximize_button"])

        ctk.CTkLabel(
            window, textvariable=info_variable,
            text_color=MapViewTemplate.SECONDARY_TEXT_COLOR,
            font=ctk.CTkFont(size=MapViewTemplate.INFO_FONT_SIZE), justify="left",
        ).grid(row=1, column=0, padx=18, pady=(0, 8), sticky="w")

        legend = ctk.CTkFrame(window, fg_color="transparent")
        legend.grid(row=2, column=0, padx=18, pady=(0, 8), sticky="w")

        help_container = ctk.CTkFrame(window, corner_radius=8)
        help_container.grid(row=3, column=0, padx=18, pady=(0, 8), sticky="ew")
        help_container.grid_columnconfigure(0, weight=1)
        help_header = ctk.CTkFrame(help_container, fg_color="transparent")
        help_header.grid(row=0, column=0, sticky="ew")
        help_header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            help_header, text="Map instructions", anchor="w",
            font=ctk.CTkFont(size=MapViewTemplate.HELP_HEADING_FONT_SIZE, weight="bold"),
        ).grid(row=0, column=0, padx=(12, 8), pady=6, sticky="w")

        help_frame = ctk.CTkFrame(help_container, fg_color="transparent")
        help_frame.grid(row=1, column=0, sticky="ew")
        help_frame.grid_columnconfigure(0, weight=1)
        map_help = "Mouse wheel: zoom in / out\nMiddle mouse button + drag: pan"
        if slot_edit_help:
            map_help += "\nRight click: open context menu"
        help_items = ((0, "Map", map_help),)
        if object_edit_help:
            help_frame.grid_columnconfigure(1, weight=1)
            help_frame.grid_columnconfigure(2, weight=1)
            help_items += (
                (1, "Object editing",
                    "Right click: open menu\n"
                    "Add Object: place an object at the clicked position\n"
                    "Remove Object: delete the object under the pointer\n"
                    "Changes remain in memory until Save."),
                (2, "Area Selection",
                    "Shift + left mouse button + drag: select a rectangular area\n"
                    "Ctrl + left mouse button: add points to a lasso selection\n"
                    "Right click on the selected area: open Add / Change / Remove\n"
                    "ESC - Key clears the selection"),
            )
        elif slot_edit_help:
            help_frame.grid_columnconfigure(1, weight=1)
            help_frame.grid_columnconfigure(2, weight=1)
            help_frame.grid_columnconfigure(3, weight=1)
            help_items += (
                (1, "Slot editing",
                    "Right click: open the context menu\n"
                    "Add Slot: choose and add a slot type\n"
                    "Remove Slot: remove that slot\n"
                    "Changes remain in memory until Save."
                ),

                (2, "River & Mine Slots",
                    "The arrow must point from the slot\n"
                    "toward the river / mountain.\n"
                    "On some maps, the direction display is wrong.\n"
                    "check the game to verify the correct direction."
                ),

                (3, "Area Selection",
                    "Shift + left mouse button + drag: select a rectangular area\n"
                    "Ctrl + left mouse button: add points to a lasso selection\n"
                    "Right click on the selected area: open Add / Remove\n"
                    "ESC - Key clears the selection"

                ),


            )
        for col, title_text, body in help_items:
            ctk.CTkLabel(help_frame, text=title_text, font=ctk.CTkFont(size=MapViewTemplate.HELP_HEADING_FONT_SIZE, weight="bold")).grid(row=0,column=col,padx=12,pady=(2,2),sticky="w")
            ctk.CTkLabel(help_frame, text=body, justify="left", text_color=MapViewTemplate.SECONDARY_TEXT_COLOR, font=ctk.CTkFont(size=MapViewTemplate.HELP_FONT_SIZE)).grid(row=1,column=col,padx=12,pady=(0,8),sticky="w")

        help_expanded = tk.BooleanVar(master=window, value=True)
        help_button = ctk.CTkButton(
            help_header, text="Minimize ▲", width=105,
            height=MapViewTemplate.LEGEND_BUTTON_HEIGHT,
            fg_color=MapViewTemplate.LEGEND_INACTIVE_FG_COLOR,
            hover_color=MapViewTemplate.LEGEND_HOVER_COLOR,
        )

        def toggle_help():
            if help_expanded.get():
                help_frame.grid_remove()
                help_expanded.set(False)
                help_button.configure(text="Show ▼")
            else:
                help_frame.grid()
                help_expanded.set(True)
                help_button.configure(text="Minimize ▲")
            window.update_idletasks()
            redraw_command()

        help_button.configure(command=toggle_help)
        help_button.grid(row=0, column=1, padx=8, pady=5, sticky="e")

        canvas = tk.Canvas(window, bg=MapViewTemplate.CANVAS_BACKGROUND, highlightthickness=0, borderwidth=0, cursor="crosshair")
        canvas.grid(row=4, column=0, padx=18, pady=(0, 8), sticky="nsew")
        ctk.CTkLabel(
            window, textvariable=selection_variable, justify="left", anchor="w", wraplength=1000,
            fg_color=MapViewTemplate.SELECTION_BACKGROUND,
            text_color=MapViewTemplate.PRIMARY_TEXT_COLOR,
            font=ctk.CTkFont(size=MapViewTemplate.SELECTION_FONT_SIZE), corner_radius=6,
        ).grid(row=5,column=0,padx=18,pady=(0,15),ipady=7,sticky="ew")
        legend_builder()
        window.after(100, redraw_command)
        return {"window": window, "canvas": canvas, "legend": legend,
                "header": built["header"], "maximize_button": built["maximize_button"],
                "help_container": help_container, "help_frame": help_frame,
                "help_button": help_button, "help_expanded": help_expanded}

    @staticmethod
    def read_playable_area(path, parser=None):
        """Return (min_x, max_x, min_z, max_z) from SessionSettings.

        PlayableArea is min_x min_z max_x max_z, not width/height.
        The entire background image maps to these bounds, including margins.
        No point-extents fallback: it would misregister the image again.
        """
        if not path or not str(path).strip():
            raise ValueError('Select gamedata_original.xml in Files and Folders first.')
        path = Path(path)
        tree = parser(path)[0] if parser else ET.parse(path)
        tag = lambda node: node.tag.rsplit('}', 1)[-1] if isinstance(node.tag, str) else ''
        areas = [child for node in tree.getroot().iter() if tag(node) == 'SessionSettings'
                 for child in node if tag(child) == 'PlayableArea']
        if len(areas) != 1:
            raise ValueError('Expected exactly one SessionSettings/PlayableArea in gamedata_original.xml.')
        parts = (areas[0].text or '').replace(';', ' ').split()
        if len(parts) != 4:
            raise ValueError('PlayableArea must contain four numbers: min X, min Z, max X, max Z.')
        try:
            min_x, min_z, max_x, max_z = (float(v.replace(',', '.')) for v in parts)
        except ValueError as exc:
            raise ValueError('PlayableArea contains invalid coordinates.') from exc
        if not all(math.isfinite(v) for v in (min_x, min_z, max_x, max_z)) or max_x <= min_x or max_z <= min_z:
            raise ValueError('PlayableArea must have finite coordinates and positive width and height.')
        return min_x, max_x, min_z, max_z

    @classmethod
    def load_background(cls, roots, *, direct_first=True):
        """Find and decode the first readable background image.

        roots is an ordered iterable of search directories supplied by the view.
        direct_first=True checks all direct candidates before recursive search;
        False searches each root directly and recursively before the next root.
        Return (detached RGBA Pillow image, source Path), or (None, None).
        No Tk calls: this helper can also be invoked from an existing worker.
        Filename, duplicate handling, decoding and error fallback live here only.
        """
        folders = []
        seen_roots = set()
        for value in roots:
            if value is None or not str(value).strip():
                continue
            folder = Path(value)
            key = str(folder.absolute()).casefold()
            if key not in seen_roots and folder.is_dir():
                seen_roots.add(key)
                folders.append(folder)
        def recursive(folder):
            try:
                yield from folder.rglob(cls.BACKGROUND_IMAGE_NAME)
            except OSError:
                # A missing/inaccessible subtree must not prevent later roots.
                return
        def candidates():
            if direct_first:
                for folder in folders:
                    yield folder / cls.BACKGROUND_IMAGE_NAME
                for folder in folders:
                    yield from recursive(folder)
            else:
                for folder in folders:
                    yield folder / cls.BACKGROUND_IMAGE_NAME
                    yield from recursive(folder)
        seen = set()
        for candidate in candidates():
            key = str(candidate.absolute()).casefold()
            if key in seen:
                continue
            seen.add(key)
            try:
                if not candidate.is_file():
                    continue
                with Image.open(candidate) as image:
                    return image.convert('RGBA').copy(), candidate
            except (OSError, ValueError, Image.DecompressionBombError):
                continue
        return None, None

    @staticmethod
    def ctrl_pressed(event):
        return bool(getattr(event, 'state', 0) & 0x0004)

    @classmethod
    def zoom_from_event(cls, current_zoom, event):
        """Shared background/point zoom. No modifier key is required."""
        number = getattr(event, 'num', None)
        delta = getattr(event, 'delta', 0)
        direction = 1 if number == 4 else -1 if number == 5 else 1 if delta > 0 else -1 if delta < 0 else 0
        return max(cls.MIN_ZOOM, current_zoom + direction * cls.SHARED_ZOOM_STEP)

    @classmethod
    def zoom_about_pointer(cls, canvas, bounds, current_zoom, pan_x, pan_y, event):
        """Return zoom/pan values that keep the world point under the mouse fixed."""
        new_zoom = cls.zoom_from_event(current_zoom, event)
        if canvas is None or new_zoom == current_zoom:
            return new_zoom, pan_x, pan_y

        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        min_x, max_x, min_z, max_z = bounds
        span_x = max_x - min_x
        span_z = max_z - min_z
        if span_x <= 0 or span_z <= 0:
            return new_zoom, pan_x, pan_y

        base_scale = min(
            (width - 2 * cls.MAP_MARGIN) / span_x,
            (height - 2 * cls.MAP_MARGIN) / span_z,
        )
        old_scale = base_scale * current_zoom
        new_scale = base_scale * new_zoom
        if old_scale <= 0 or new_scale <= 0:
            return new_zoom, pan_x, pan_y

        old_width = span_x * old_scale
        old_height = span_z * old_scale
        old_left = (width - old_width) / 2 + pan_x
        old_top = (height - old_height) / 2 + pan_y

        # Fractions may be outside 0..1 when the pointer is outside the map.
        # Keeping them unbounded still provides continuous, predictable zooming.
        focus_x = (event.x - old_left) / old_width
        focus_y = (event.y - old_top) / old_height

        new_width = span_x * new_scale
        new_height = span_z * new_scale
        new_left = event.x - focus_x * new_width
        new_top = event.y - focus_y * new_height
        new_pan_x = new_left - (width - new_width) / 2
        new_pan_y = new_top - (height - new_height) / 2
        return new_zoom, new_pan_x, new_pan_y

    @classmethod
    def handle_focus_zoom_event(cls, canvas, bounds, current_zoom, pan_x, pan_y,
                                event, redraw_callback):
        """Apply pointer-focused zoom and retain the shared debounce behavior."""
        new_zoom, new_pan_x, new_pan_y = cls.zoom_about_pointer(
            canvas, bounds, current_zoom, pan_x, pan_y, event,
        )
        # handle_zoom_event owns the common hide/preview/debounce lifecycle. Give
        # it an event with no wheel direction so it keeps the already calculated
        # zoom value and only performs the visual lifecycle.
        class _VisualEvent:
            num = None
            delta = 0
        cls.handle_zoom_event(canvas, new_zoom, _VisualEvent(), redraw_callback)
        return new_zoom, new_pan_x, new_pan_y

    @classmethod
    def handle_zoom_event(cls, canvas, current_zoom, event, redraw_callback):
        """Apply zoom and keep dots hidden until 500 ms after the last event."""
        new_zoom = cls.zoom_from_event(current_zoom, event)
        if canvas is None:
            redraw_callback()
            return new_zoom

        canvas._map_zoom_active = True
        cls.begin_pan_visuals(canvas)

        pending = getattr(canvas, "_map_zoom_debounce_id", None)
        if pending is not None:
            try:
                canvas.after_cancel(pending)
            except (tk.TclError, ValueError):
                pass

        # Render a live background preview for orientation. Because map views
        # use cached_viewport_photo(), this redraw processes only the visible
        # canvas-sized crop instead of a full high-resolution zoom image. Dots
        # remain hidden while _map_zoom_active is true.
        redraw_callback()

        def finish_zoom():
            canvas._map_zoom_debounce_id = None
            canvas._map_zoom_active = False
            redraw_callback()

        canvas._map_zoom_debounce_id = canvas.after(
            cls.ZOOM_DEBOUNCE_MS, finish_zoom
        )
        return new_zoom

    @staticmethod
    def zoom_active(canvas):
        return bool(canvas is not None and getattr(canvas, "_map_zoom_active", False))

    @staticmethod
    def dot_drag_cancel(canvas):
        """Cancel an active dot drag and remove its preview marker."""
        state = getattr(canvas, "_map_dot_drag", None)
        canvas._map_dot_drag = None
        if state and state.get("preview") is not None:
            canvas.delete(state["preview"])

    @classmethod
    def dot_drag_start(cls, event, canvas, enabled, hit_test, color_getter=None):
        """Start dragging the dot directly below MouseDown, without selecting it."""
        cls.dot_drag_cancel(canvas)
        if not enabled:
            return None
        hit = hit_test(event)
        if hit is None:
            return None
        preview = cls.create_hover_marker(canvas)
        color = color_getter(hit) if color_getter is not None else None
        cls.position_hover_marker(canvas, preview, (event.x, event.y), color)
        canvas._map_dot_drag = {
            "hit": hit,
            "preview": preview,
            "moved": False,
            "start_x": event.x,
            "start_y": event.y,
        }
        return "break"

    @classmethod
    def dot_drag_motion(cls, event, canvas, enabled):
        """Move the shared drag preview while Button-1 remains pressed."""
        if not enabled:
            cls.dot_drag_cancel(canvas)
            return None
        state = getattr(canvas, "_map_dot_drag", None)
        if state is None:
            return None
        if event.x != state["start_x"] or event.y != state["start_y"]:
            state["moved"] = True
        cls.position_hover_marker(canvas, state.get("preview"), (event.x, event.y))
        return "break"

    @classmethod
    def dot_drag_end(cls, event, canvas, enabled, commit):
        """Finish a shared dot drag and hand the hit to the view-specific RAM commit."""
        state = getattr(canvas, "_map_dot_drag", None)
        canvas._map_dot_drag = None
        if state and state.get("preview") is not None:
            canvas.delete(state["preview"])
        if not enabled or not state or not state.get("moved"):
            return None
        undo_action = commit(event, state["hit"])
        cls.dot_movement_push_undo(canvas, undo_action)
        return "break"

    @staticmethod
    def point_in_polygon(x, y, polygon):
        """Even-odd point test; polygon accepts screen or world coordinate pairs."""
        if len(polygon or ()) < 3:
            return False
        inside = False
        previous_x, previous_y = polygon[-1]
        for current_x, current_y in polygon:
            if ((current_y > y) != (previous_y > y)):
                crossing_x = ((previous_x - current_x) * (y - current_y)
                              / (previous_y - current_y) + current_x)
                if x < crossing_x:
                    inside = not inside
            previous_x, previous_y = current_x, current_y
        return inside

    @classmethod
    def bind_map_mouse(
        cls, canvas, *, configure=None, motion=None, leave=None,
        left_start=None, left_move=None, left_end=None,
        selection_start=None, selection_move=None, selection_end=None,
        lasso_point=None, wheel=None, context=None, pan_start=None, pan_move=None, pan_end=None,
        redraw=None, owner=None, escape=None,
    ):
        """Install the complete, consistent mouse contract for a map canvas."""
        def button1_start(event):
            # Route the complete Ctrl click lifecycle away from normal dot drag.
            is_lasso = lasso_point is not None and cls.ctrl_pressed(event)
            canvas._map_lasso_click_active = bool(is_lasso)
            if is_lasso:
                return lasso_point(event)
            if left_start is not None:
                return left_start(event)
            return None

        def button1_move(event):
            if getattr(canvas, "_map_lasso_click_active", False):
                return "break"
            if left_move is not None:
                return left_move(event)
            return None

        def button1_end(event):
            if getattr(canvas, "_map_lasso_click_active", False):
                canvas._map_lasso_click_active = False
                return "break"
            if left_end is not None:
                return left_end(event)
            return None

        canvas._map_lasso_click_active = False
        bindings = (
            ("<Configure>", configure), ("<Motion>", motion), ("<Leave>", leave),
            ("<ButtonPress-1>", button1_start), ("<B1-Motion>", button1_move),
            ("<ButtonRelease-1>", button1_end),
            ("<Shift-ButtonPress-1>", selection_start),
            ("<Shift-B1-Motion>", selection_move),
            ("<Shift-ButtonRelease-1>", selection_end),
            ("<MouseWheel>", wheel), ("<Button-4>", wheel), ("<Button-5>", wheel),
            ("<ButtonPress-3>", context),
        )
        for sequence, callback in bindings:
            if callback is not None:
                canvas.bind(sequence, callback)
        if pan_start is not None and pan_move is not None and pan_end is not None:
            cls.bind_middle_pan(canvas, pan_start, pan_move, pan_end, redraw)
        if escape is not None:
            canvas.bind("<Escape>", escape, add="+")
            if owner is not None and owner is not canvas:
                owner.bind("<Escape>", escape, add="+")

    @staticmethod
    def show_context_menu(owner, event, entries):
        """Render a context menu from map-owned entry definitions."""
        def populate(menu, definitions):
            for entry in definitions:
                kind = entry.get("kind", "command")
                if kind == "separator":
                    menu.add_separator()
                elif kind == "cascade":
                    submenu = tk.Menu(menu, tearoff=0)
                    populate(submenu, entry.get("entries", ()))
                    menu.add_cascade(label=entry["label"], menu=submenu)
                else:
                    menu.add_command(
                        label=entry["label"], command=entry.get("command"),
                        state=entry.get("state", "normal"),
                    )
        menu = tk.Menu(owner, tearoff=0)
        populate(menu, entries)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    @classmethod
    def bind_middle_pan(cls, canvas, start_callback, move_callback, end_callback,
                        redraw_callback=None):
        """Bind the shared middle-button pan behavior for every map canvas.

        During pan only ``map_background`` is moved. Point and hover layers are
        hidden until the button is released, then the owning view is redrawn once
        so dots, hit targets and cached screen coordinates match the final pan.
        """
        canvas._map_middle_pan_active = False

        def start(event):
            canvas._map_middle_pan_active = True
            cls.begin_pan_visuals(canvas)
            start_callback(event)
            return "break"

        def move(event):
            if not canvas._map_middle_pan_active:
                return "break"
            move_callback(event)
            return "break"

        def end(event):
            try:
                end_callback(event)
            finally:
                canvas._map_middle_pan_active = False
                cls.end_pan_visuals(canvas, redraw_callback)
            return "break"

        canvas.bind("<ButtonPress-2>", start)
        canvas.bind("<B2-Motion>", move)
        canvas.bind("<ButtonRelease-2>", end)

    @staticmethod
    def begin_pan_visuals(canvas):
        """Hide every dot-related layer while keeping the background visible."""
        if canvas is None:
            return
        for tag in ("map_point", "map_hover"):
            canvas.itemconfigure(tag, state="hidden")

    @staticmethod
    def move_pan_background(canvas, dx, dy):
        """Move only the background image and its border during an active pan."""
        if canvas is not None and (dx or dy):
            canvas.move("map_background", dx, dy)

    @staticmethod
    def end_pan_visuals(canvas, redraw_callback=None):
        """Restore the dot layers by rebuilding the map at the final pan offset."""
        if redraw_callback is not None:
            redraw_callback()
            return
        if canvas is not None:
            for tag in ("map_point", "map_hover"):
                canvas.itemconfigure(tag, state="normal")

    @staticmethod
    def middle_pan_active(canvas, event=None):
        """True while button 2 is panning; usable by all hover handlers."""
        if canvas is None:
            return False
        if getattr(canvas, "_map_middle_pan_active", False):
            return True
        return bool(event is not None and getattr(event, "state", 0) & 0x0200)

    @staticmethod
    def begin_pan(event, pan_x, pan_y):
        """Capture shared pan on right-button press, regardless of modifiers."""
        return event.x, event.y, pan_x, pan_y

    @staticmethod
    def move_pan(start, event):
        if start is None:
            return None
        x, y, pan_x, pan_y = start
        return pan_x + event.x - x, pan_y + event.y - y
