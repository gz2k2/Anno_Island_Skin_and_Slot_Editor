from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

from app.templates.template_popup import PopupTemplate


class StatusWindowTemplate:
    """Central themed status popup used by load, save and unpack workflows."""

    GEOMETRY = "520x170"
    PROGRESS_GEOMETRY = "640x220"

    @classmethod
    def create(
        cls,
        owner,
        text="Working...",
        *,
        title="Status",
        heading="Status",
        progress=False,
        fraction=None,
        modal=False,
        topmost=True,
        force_paint=True,
    ):
        parent = owner.winfo_toplevel() if hasattr(owner, "winfo_toplevel") else owner
        built = PopupTemplate.create_window(
            parent,
            title=title,
            heading=heading,
            geometry=cls.PROGRESS_GEOMETRY if progress else cls.GEOMETRY,
            min_size=(440, 150),
            resizable=False,
            maximize=False,
            modal=modal,
            close_command=lambda: None,
            topmost=False,
        )
        window = built["window"]
        window.protocol("WM_DELETE_WINDOW", lambda: None)
        window._status_owner = parent
        window._status_keep_topmost = bool(topmost)
        try:
            if parent is not None and parent.winfo_exists():
                window.transient(parent)
            window.attributes("-topmost", bool(topmost))
            window.lift(parent if parent is not None else None)
        except (tk.TclError, AttributeError):
            try:
                window.lift()
            except tk.TclError:
                pass

        def keep_in_front(_event=None):
            if not PopupTemplate.window_exists(window):
                return
            try:
                if window._status_keep_topmost:
                    window.attributes("-topmost", True)
                owner_window = getattr(window, "_status_owner", None)
                if PopupTemplate.window_exists(owner_window):
                    window.lift(owner_window)
                else:
                    window.lift()
            except (tk.TclError, AttributeError):
                pass

        window.bind("<Map>", keep_in_front, add="+")
        window.bind("<Visibility>", keep_in_front, add="+")
        window.grid_columnconfigure(0, weight=1)

        text_var = tk.StringVar(master=window, value=str(text))
        label = ctk.CTkLabel(
            window,
            textvariable=text_var,
            anchor="w",
            justify="left",
            wraplength=590 if progress else 470,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        label.grid(row=1, column=0, padx=24, pady=(12, 18 if not progress else 12), sticky="ew")

        bar = None
        if progress:
            bar = ctk.CTkProgressBar(window)
            bar.grid(row=2, column=0, padx=24, pady=(0, 24), sticky="ew")

        handle = {
            "window": window,
            "text_var": text_var,
            "label": label,
            "progress": bar,
            "topmost": bool(topmost),
            "owner": parent,
            "keep_in_front": keep_in_front,
        }
        cls.update(handle, text=text, fraction=fraction)
        keep_in_front()
        PopupTemplate.safe_activate(window)
        if force_paint:
            window.update_idletasks()
            window.update()
        return handle

    @staticmethod
    def exists(handle):
        if not handle:
            return False
        window = handle.get("window") if isinstance(handle, dict) else handle
        return PopupTemplate.window_exists(window)

    @classmethod
    def update(cls, handle, *, text=None, fraction=None):
        if not cls.exists(handle):
            return False
        if text is not None:
            handle["text_var"].set(str(text))
        bar = handle.get("progress")
        if bar is not None:
            bar.stop()
            if fraction is None:
                bar.configure(mode="indeterminate")
                bar.start()
            else:
                bar.configure(mode="determinate")
                bar.set(max(0.0, min(1.0, float(fraction))))
        keep_in_front = handle.get("keep_in_front")
        if callable(keep_in_front):
            keep_in_front()
        handle["window"].update_idletasks()
        return True

    @classmethod
    def close(cls, handle):
        if not handle:
            return
        window = handle.get("window") if isinstance(handle, dict) else handle
        if isinstance(handle, dict):
            bar = handle.get("progress")
            if bar is not None:
                try:
                    bar.stop()
                except tk.TclError:
                    pass
        if PopupTemplate.window_exists(window):
            try:
                window.attributes("-topmost", False)
            except tk.TclError:
                pass
            PopupTemplate.close_window(window)
