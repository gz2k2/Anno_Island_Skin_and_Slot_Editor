from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
import threading
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from app.functions.functions_tintmaps import BRIGHTNESS_OPTIONS, REGIONS, patch_island_tintmaps
from app.templates.template_statuswindow import StatusWindowTemplate


class TextureSettingsTabMixin:
    """Texture settings and tintmap patch controls."""

    def _build_texture_settings_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            tab,
            text="Texture Settings",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 12), sticky="w")

        self.tintmap_source_region_var = tk.StringVar(value="The Old World")
        self.tintmap_target_region_var = tk.StringVar(value="Enbesa")
        self.tintmap_brightness_var = tk.StringVar(value="Normal")
        self.tintmap_custom_offset_var = tk.StringVar(value="0")
        tint_frame = ctk.CTkFrame(tab)
        tint_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        tint_frame.grid_columnconfigure((1, 3, 5), weight=1)
        ctk.CTkLabel(
            tint_frame,
            text="Tint Map Settings",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, columnspan=7, padx=14, pady=(12, 0), sticky="w")
        ctk.CTkLabel(tint_frame, text="From:").grid(row=1, column=0, padx=(14, 5), pady=14, sticky="e")
        ctk.CTkOptionMenu(
            tint_frame, variable=self.tintmap_source_region_var,
            values=sorted(("The " + region if region in {"Old World", "New World"} else region for region in REGIONS), key=str.casefold), dynamic_resizing=False,
        ).grid(row=1, column=1, padx=(0, 12), pady=14, sticky="ew")
        ctk.CTkLabel(tint_frame, text="To:").grid(row=1, column=2, padx=(12, 5), pady=14, sticky="e")
        ctk.CTkOptionMenu(
            tint_frame, variable=self.tintmap_target_region_var,
            values=sorted(("The " + region if region in {"Old World", "New World"} else region for region in REGIONS), key=str.casefold), dynamic_resizing=False,
        ).grid(row=1, column=3, padx=(0, 12), pady=14, sticky="ew")
        ctk.CTkLabel(tint_frame, text="Brightness:").grid(
            row=1, column=4, padx=(12, 5), pady=14, sticky="e"
        )
        brightness_frame = ctk.CTkFrame(tint_frame, fg_color="transparent")
        brightness_frame.grid(row=1, column=5, padx=(0, 12), pady=14, sticky="ew")
        brightness_frame.grid_columnconfigure(0, weight=1)
        self.tintmap_brightness_menu = ctk.CTkOptionMenu(
            brightness_frame, variable=self.tintmap_brightness_var,
            values=list(BRIGHTNESS_OPTIONS), dynamic_resizing=False,
            command=self._on_tintmap_brightness_changed,
        )
        self.tintmap_brightness_menu.grid(row=0, column=0, sticky="ew")
        self.tintmap_custom_offset_entry = ctk.CTkEntry(
            brightness_frame,
            textvariable=self.tintmap_custom_offset_var,
            width=80,
            placeholder_text="Offset",
        )
        ctk.CTkButton(
            tint_frame, text="Patch Tintmaps", command=self._start_tintmap_patch,
        ).grid(row=1, column=6, padx=(0, 14), pady=14, sticky="ew")

        self.tintmap_detected_region_var = tk.StringVar()
        ctk.CTkLabel(
            tint_frame,
            textvariable=self.tintmap_detected_region_var,
            anchor="w",
        ).grid(row=2, column=1, padx=(0, 12), pady=(0, 12), sticky="w")
        self._update_texture_detected_region()
        ctk.CTkLabel(
            tint_frame,
            text=(
                "Tint Maps do not necessarily need to be converted to another region.\n"
                "Conversion is only necessary if islands appear too dark or too bright in the game."
            ),
            anchor="w",
            justify="left",
            wraplength=800,
        ).grid(row=3, column=0, columnspan=7, padx=14, pady=(0, 14), sticky="ew")

    def _on_tintmap_brightness_changed(self, value=None):
        custom = (value or self.tintmap_brightness_var.get()) == "Custom"
        entry = getattr(self, "tintmap_custom_offset_entry", None)
        if entry is None:
            return
        if custom:
            entry.grid(row=0, column=1, padx=(8, 0), sticky="e")
        else:
            entry.grid_forget()

    def _update_texture_detected_region(self):
        """Display original-region metadata without changing the From selection."""
        variable = getattr(self, "tintmap_detected_region_var", None)
        if variable is not None:
            region = getattr(self, "original_region_name", "") or "Unknown"
            variable.set(f"Detected region: {region}")

    def _start_tintmap_patch(self):
        """Run the tintmap worker pool without blocking CustomTkinter."""
        if getattr(self, "_tintmap_patch_running", False):
            messagebox.showwarning("Tintmaps", "Tintmap patching is already running.")
            return

        a7m_path = self.unpack_file_var.get().strip() or self.pack_file_var.get().strip()
        source_region = self.tintmap_source_region_var.get().removeprefix("The ")
        target_region = self.tintmap_target_region_var.get().removeprefix("The ")
        brightness = self.tintmap_brightness_var.get()
        custom_offset = 0
        if brightness == "Custom":
            try:
                custom_offset = int(self.tintmap_custom_offset_var.get().strip())
            except ValueError:
                messagebox.showerror("Patch Tintmaps", "Custom offset must be a whole number between -255 and 255.")
                return
            if not -255 <= custom_offset <= 255:
                messagebox.showerror("Patch Tintmaps", "Custom offset must be between -255 and 255.")
                return
        self._tintmap_patch_running = True
        self._tintmap_patch_queue = Queue()
        StatusWindowTemplate.close(getattr(self, "_tintmap_patch_popup", None))
        self._tintmap_patch_popup = StatusWindowTemplate.create(
            self,
            text="Preparing tintmap patch...",
            title="Patch Tintmaps",
            heading="Patching Tintmaps",
            progress=True,
            fraction=0.0,
            modal=False,
            force_paint=False,
        )
        events = self._tintmap_patch_queue

        def worker():
            # Same worker/queue pattern as TMC: no Tk calls in this thread.
            try:
                result = patch_island_tintmaps(
                    a7m_path, source_region, target_region, brightness=brightness,
                    custom_offset=custom_offset,
                    progress_callback=lambda *args: events.put(("progress", *args)),
                )
                events.put(("done", result))
            except Exception as exc:
                events.put(("error", f"{type(exc).__name__}: {exc}"))

        self._tintmap_patch_thread = threading.Thread(
            target=worker,
            name="RegionalTintmapPatch",
            daemon=True,
        )
        self._tintmap_patch_thread.start()
        self.after(50, self._poll_tintmap_patch)

    def _poll_tintmap_patch(self):
        """Apply worker messages on the Tk main thread."""
        queue = getattr(self, "_tintmap_patch_queue", None)
        if queue is None:
            return

        terminal = None
        latest_progress = None
        for _ in range(100):
            try:
                message = queue.get_nowait()
            except Empty:
                break
            if message[0] == "progress":
                stage = message[1]
                payload = message[2:]
                if stage == "folder":
                    label, detail = payload
                    text = f"Folder search: {label}\n{detail}"
                    fraction = 0.02
                elif stage == "folder_found":
                    label, detail = payload
                    text = f"Folder search: {label}\n{detail}"
                    fraction = 0.05
                elif stage == "scan_start":
                    label, detail = payload
                    text = f"DDS scan: {label}\n{detail}"
                    fraction = 0.06
                elif stage == "scan":
                    scanned, dds_found, current = payload
                    text = (
                        f"DDS scan: {scanned} entries scanned, {dds_found} DDS found\n"
                        f"{current}"
                    )
                    fraction = 0.08
                elif stage == "scan_done":
                    scanned, dds_found, folder = payload
                    text = (
                        f"DDS scan finished: {scanned} entries scanned, {dds_found} DDS found\n"
                        f"{folder}"
                    )
                    fraction = 0.10
                elif stage == "patch":
                    completed, total, path, state = payload
                    filename = Path(path).name
                    fraction = 0.10 + (0.90 * completed / total if total else 0.0)
                    text = (
                        f"Patching DDS: {completed} / {total} processed\n"
                        f"{filename}: {state}"
                    )
                else:
                    text = f"Tintmap patch: {stage}"
                    fraction = 0.0
                latest_progress = (text, fraction)
            else:
                terminal = message
                break

        if latest_progress is not None:
            text, fraction = latest_progress
            StatusWindowTemplate.update(
                self._tintmap_patch_popup, text=text, fraction=fraction,
            )

        if terminal is None:
            self.after(50, self._poll_tintmap_patch)
            return

        self._tintmap_patch_running = False
        StatusWindowTemplate.close(getattr(self, "_tintmap_patch_popup", None))
        self._tintmap_patch_popup = None

        if terminal[0] == "error":
            messagebox.showerror("Tintmaps", f"Tintmap patching failed:\n{terminal[1]}")
            return

        result = terminal[1]
        details = "\n".join(result.errors[:10])
        if len(result.errors) > 10:
            details += f"\n... and {len(result.errors) - 10} more error(s)"
        summary = (
            f"Folder: {result.tintmaps_folder}\n"
            f"Variant cache: {result.tintmaps_folder.parent / '_tintmap_variants'}\n"
            f"DDS found: {result.found}\nApplied: {result.changed}\n"
            f"Restored: {result.restored}\nSkipped: {result.skipped}\nFailed: {result.failed}"
        )
        if result.failed:
            messagebox.showwarning("Tintmaps", summary + "\n\n" + details)
        else:
            messagebox.showinfo("Tintmaps", summary)
        self._rebuild_regional_rd3d_cache()
