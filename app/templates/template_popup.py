from __future__ import annotations

import tkinter as tk
import customtkinter as ctk

def _patch_ctk_toplevel():
    """Guard CustomTkinter's delayed Windows focus restoration.

    CTkToplevel._windows_set_titlebar_color() temporarily withdraws a window
    and schedules the previously focused widget directly via after(..., focus).
    If that widget is a popup which is destroyed before the callback runs,
    Tk raises ``TclError: bad window path name``. Intercept only those focus
    callbacks while the CTk titlebar method is running and replace them with a
    lifecycle-checked callback.
    """
    try:
        import customtkinter.windows.ctk_toplevel as ctk_top
    except (ImportError, AttributeError):
        return

    cls = ctk_top.CTkToplevel
    if getattr(cls, "_popup_lifecycle_patch_installed", False):
        return

    original_titlebar = getattr(cls, "_windows_set_titlebar_color", None)
    original_revert = getattr(cls, "_revert_withdraw_after_windows_set_titlebar_color", None)
    original_destroy = cls.destroy

    def _widget_exists(widget):
        try:
            return widget is not None and bool(widget.winfo_exists())
        except (tk.TclError, AttributeError):
            return False

    def _is_focus_callback(callback):
        return (
            callable(callback)
            and getattr(callback, "__self__", None) is not None
            and getattr(callback, "__name__", "")
                in {"focus", "focus_set", "focus_force"}
        )

    if callable(original_revert):
        def _safe_revert_withdraw_after_windows_set_titlebar_color(self, *args, **kwargs):
            # CustomTkinter schedules this method with after(). A short-lived
            # status window may already be destroyed when the callback runs.
            if not _widget_exists(self):
                return None
            try:
                return original_revert(self, *args, **kwargs)
            except (tk.TclError, AttributeError):
                return None

        cls._revert_withdraw_after_windows_set_titlebar_color = (
            _safe_revert_withdraw_after_windows_set_titlebar_color
        )

    if callable(original_titlebar):
        def _safe_windows_set_titlebar_color(self, *args, **kwargs):
            original_after = self.after

            def guarded_after(delay_ms, callback=None, *callback_args):
                if _is_focus_callback(callback):
                    target = getattr(callback, "__self__", None)

                    def safe_focus():
                        if not _widget_exists(self) or not _widget_exists(target):
                            return
                        try:
                            callback(*callback_args)
                        except (tk.TclError, AttributeError):
                            pass

                    return original_after(delay_ms, safe_focus)
                return original_after(delay_ms, callback, *callback_args)

            # CTk resolves self.after dynamically, so this narrowly intercepts
            # callbacks created by the titlebar-color operation only.
            self.after = guarded_after
            try:
                return original_titlebar(self, *args, **kwargs)
            except (tk.TclError, AttributeError):
                return None
            finally:
                try:
                    self.after = original_after
                except (tk.TclError, AttributeError):
                    pass

        cls._windows_set_titlebar_color = _safe_windows_set_titlebar_color

    def _safe_destroy(self):
        try:
            original_destroy(self)
        except (tk.TclError, AttributeError):
            pass

    cls.destroy = _safe_destroy
    cls._popup_lifecycle_patch_installed = True


_patch_ctk_toplevel()


class PopupTemplate:
    """Central configuration and helpers for all CTkToplevel windows."""

    WINDOW_GEOMETRY = "1100x760"
    WINDOW_MIN_SIZE = (850, 560)
    WINDOW_TOPMOST = True
    RELEASE_TOPMOST_AFTER_MS = 300

    HEADER_PADX = 18
    HEADER_PADY = (16, 8)
    HEADING_FONT_SIZE = 22
    HEADING_FONT_WEIGHT = "bold"
    SECONDARY_TEXT_COLOR = "gray70"

    BORDER_COLOR = "#A6A6A6"
    BORDER_WIDTH = 2

    BUTTON_WIDTH = 90
    BUTTON_HEIGHT = 30
    BUTTON_FG_COLOR = "#555555"
    BUTTON_HOVER_COLOR = "#666666"
    DANGER_BUTTON_FG_COLOR = "#B52B2B"
    DANGER_BUTTON_HOVER_COLOR = "#8F2020"
    BUTTON_FONT_SIZE = 12

    @classmethod
    def create_window(
        cls,
        owner,
        *,
        title: str,
        heading: str | None = None,
        geometry: str | None = None,
        min_size: tuple[int, int] | None = None,
        resizable: bool | tuple[bool, bool] = True,
        modal: bool = False,
        close_command=None,
        add_header: bool = True,
        maximize: bool = True,
        topmost: bool | None = None,
    ):
        window = ctk.CTkToplevel(owner)
        window.title(title)
        # Independent decorated toplevels retain native minimize/maximize controls.
        # A transient Tk window cannot be iconified on Windows. Keep the Python
        # owner reference and the existing grab-based modality instead.
        window._popup_owner = owner
        cls.apply_window_settings(
            window,
            geometry=geometry,
            min_size=min_size,
            resizable=resizable,
            topmost=topmost,
        )
        def _close_popup():
            # A close callback may veto automatic destruction by returning False.
            # This is required for confirmation dialogs such as "Close and discard?".
            allow_close = True
            if close_command is not None:
                try:
                    result = close_command()
                    if result is False:
                        allow_close = False
                except (tk.TclError, AttributeError):
                    pass
            if allow_close and cls.window_exists(window):
                cls.close_window(window)

        window.protocol("WM_DELETE_WINDOW", _close_popup)
        if modal:
            try:
                window.grab_set()
            except tk.TclError:
                pass

        header = None
        maximize_button = None
        if add_header:
            header = ctk.CTkFrame(window, fg_color="transparent")
            header.grid(
                row=0, column=0, padx=cls.HEADER_PADX,
                pady=cls.HEADER_PADY, sticky="ew"
            )
            header.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                header,
                text=heading or title,
                font=ctk.CTkFont(
                    size=cls.HEADING_FONT_SIZE,
                    weight=cls.HEADING_FONT_WEIGHT,
                ),
            ).grid(row=0, column=0, sticky="w")

        cls.request_focus(window, delay_ms=60)
        if cls.WINDOW_TOPMOST if topmost is None else topmost:
            cls.schedule(window, cls.RELEASE_TOPMOST_AFTER_MS, lambda: cls.release_topmost(window))
        return {"window": window, "header": header, "maximize_button": maximize_button}

    @classmethod
    def apply_window_settings(cls, window, *, geometry=None, min_size=None, resizable=True, topmost=None):
        geometry = geometry or cls.WINDOW_GEOMETRY
        min_size = min_size or cls.WINDOW_MIN_SIZE
        window.geometry(geometry)
        window.minsize(*min_size)
        if isinstance(resizable, tuple):
            window.resizable(*resizable)
        else:
            window.resizable(bool(resizable), bool(resizable))
        use_topmost = cls.WINDOW_TOPMOST if topmost is None else bool(topmost)
        window.attributes("-topmost", use_topmost)
        window._popup_restore_geometry = geometry
        cls.apply_popup_border(window)
        cls.apply_native_titlebar_controls(window)

    @classmethod
    def apply_native_titlebar_controls(cls, window):
        """Enable Windows caption controls without replacing close handling.

        Explicit native style bits also enable maximize on fixed-size status
        windows. The caller's interactive resize policy remains unchanged.
        """
        import sys
        if sys.platform != "win32":
            return

        def apply_controls(event=None):
            if event is not None and event.widget is not window:
                return
            try:
                if not window.winfo_exists():
                    return
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
                user32.GetAncestor.restype = wintypes.HWND
                user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
                user32.GetWindowLongW.restype = wintypes.LONG
                user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
                user32.SetWindowLongW.restype = wintypes.LONG
                user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
                user32.SetWindowPos.restype = wintypes.BOOL
                hwnd = user32.GetAncestor(window.winfo_id(), 2)  # GA_ROOT
                if not hwnd:
                    return
                index = -16  # GWL_STYLE
                style = user32.GetWindowLongW(hwnd, index)
                desired = style | 0x00020000 | 0x00010000 | 0x00080000
                # WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU
                if desired != style:
                    user32.SetWindowLongW(hwnd, index, desired)
                    user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                                        0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
            except (tk.TclError, AttributeError, OSError):
                return

        if not getattr(window, "_popup_native_controls_bound", False):
            window.bind("<Map>", apply_controls, add="+")
            window._popup_native_controls_bound = True
        cls.schedule(window, 0, apply_controls)

    @classmethod
    def apply_popup_border(cls, window):
        """Draw a visible inner outline without reparenting popup content.

        Placed edge strips do not participate in grid/pack sizing. Raising them
        after a window resize keeps the outline above subsequently added content.
        The strips and binding are destroyed together with their owning window.
        """
        if getattr(window, "_popup_border_edges", None):
            return
        width = cls.BORDER_WIDTH
        edges = []
        placements = (
            {"relx": 0, "rely": 0, "relwidth": 1, "height": width},
            {"relx": 0, "rely": 1, "y": -width, "relwidth": 1, "height": width},
            {"relx": 0, "rely": 0, "width": width, "relheight": 1},
            {"relx": 1, "x": -width, "rely": 0, "width": width, "relheight": 1},
        )
        for placement in placements:
            edge = tk.Frame(window, background=cls.BORDER_COLOR,
                            borderwidth=0, highlightthickness=0, takefocus=0)
            edge.place(**placement)
            edges.append(edge)
        window._popup_border_edges = tuple(edges)

        def raise_border(event=None):
            if event is not None and event.widget is not window:
                return
            try:
                for edge in edges:
                    edge.lift()
            except (tk.TclError, AttributeError):
                pass

        window.bind("<Configure>", raise_border, add="+")
        cls.schedule(window, 0, raise_border)

    @classmethod
    def toggle_maximize(cls, window):
        if window is None or not window.winfo_exists():
            return
        try:
            maximized = window.state() == "zoomed"
            window.state("normal" if maximized else "zoomed")
        except tk.TclError:
            screen_width = window.winfo_screenwidth()
            screen_height = window.winfo_screenheight()
            if window.winfo_width() >= screen_width - 20:
                cls.restore_window_geometry(window)
            else:
                window.geometry(f"{screen_width}x{screen_height}+0+0")
        cls.update_maximize_button(window)

    @classmethod
    def update_maximize_button(cls, window):
        button = getattr(window, "_popup_maximize_button", None)
        if button is None or not button.winfo_exists():
            return
        try:
            is_maximized = window.state() == "zoomed"
        except tk.TclError:
            is_maximized = False
        button.configure(text="Restore" if is_maximized else "Maximize")

    @classmethod
    def restore_window_geometry(cls, window):
        window.geometry(getattr(window, "_popup_restore_geometry", cls.WINDOW_GEOMETRY))

    @staticmethod
    def window_exists(window) -> bool:
        if window is None:
            return False
        try:
            return bool(window.winfo_exists())
        except (tk.TclError, AttributeError):
            return False

    @classmethod
    def schedule(cls, window, delay_ms, callback):
        """Schedule a guarded popup callback and retain its cancellable job id."""
        if not cls.window_exists(window):
            return None
        holder = {"id": None}
        def guarded():
            job_id = holder["id"]
            jobs = getattr(window, "_popup_after_jobs", None)
            if jobs is not None and job_id is not None:
                jobs.discard(job_id)
            if not cls.window_exists(window):
                return
            try:
                callback()
            except (tk.TclError, AttributeError):
                pass
        try:
            job_id = window.after(delay_ms, guarded)
            holder["id"] = job_id
            jobs = getattr(window, "_popup_after_jobs", None)
            if jobs is None:
                jobs = set(); window._popup_after_jobs = jobs
            jobs.add(job_id)
            return job_id
        except (tk.TclError, AttributeError):
            return None

    @classmethod
    def request_focus(cls, window, widget=None, delay_ms=50):
        """Focus only through a guarded callback, never as a raw Tk after target."""
        target = widget or window
        def apply_focus():
            if not cls.window_exists(window) or not cls.window_exists(target):
                return
            try:
                target.focus_set()
            except (tk.TclError, AttributeError):
                pass
        return cls.schedule(window, delay_ms, apply_focus)

    @classmethod
    def safe_activate(cls, window, *, focus=True):
        if not cls.window_exists(window):
            return
        try:
            window.lift()
        except (tk.TclError, AttributeError):
            return
        if focus:
            cls.request_focus(window, delay_ms=0)

    @classmethod
    def schedule_activate(cls, window, delay_ms=50, *, focus=True):
        """Schedule a guarded foreground activation for an existing popup."""
        return cls.schedule(
            window,
            delay_ms,
            lambda: cls.safe_activate(window, focus=focus),
        )

    @classmethod
    def cancel_scheduled_callbacks(cls, window):
        for job_id in list(getattr(window, "_popup_after_jobs", ()) or ()):
            try:
                window.after_cancel(job_id)
            except (tk.TclError, ValueError, AttributeError):
                pass
        try:
            window._popup_after_jobs = set()
        except (tk.TclError, AttributeError):
            pass

    @classmethod
    def close_window(cls, window):
        if window is None:
            return
        cls.cancel_scheduled_callbacks(window)
        try:
            if cls.window_exists(window):
                window.grab_release()
        except (tk.TclError, AttributeError):
            pass
        try:
            if cls.window_exists(window):
                window.destroy()
        except (tk.TclError, AttributeError):
            pass

    @staticmethod
    def release_topmost(window):
        try:
            if window is not None and window.winfo_exists():
                window.attributes("-topmost", False)
                window.lift()
        except tk.TclError:
            pass
