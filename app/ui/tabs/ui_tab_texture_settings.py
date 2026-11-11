
from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
import threading
import math
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from app.functions.functions_tintmaps import (
    load_tintmap_presets, patch_island_tintmaps,
    save_tintmap_presets, tintmap_encoder_status, validate_tintmap_presets,
)
from app.templates.template_statuswindow import StatusWindowTemplate
from app.templates.template_treeview import TreeviewTemplate


class TextureSettingsTabMixin:
    """Texture settings and tintmap patch controls."""

    def _build_texture_settings_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(
            tab,
            text="Texture Settings",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 12), sticky="w")

        self.tintmap_comment_var = tk.StringVar(value="")
        tint_frame = ctk.CTkFrame(tab)
        tint_frame.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="ew")
        tint_frame.grid_columnconfigure(0, weight=1)
        # Standard brightness control; independent of island region.
        self.tintmap_brightness_percent_var = tk.DoubleVar(value=0.0)
        self.tintmap_brightness_percent_label_var = tk.StringVar(value="0%")
        test_frame = ctk.CTkFrame(tint_frame)
        test_frame.grid(row=0, column=0, columnspan=1, padx=14, pady=(0, 14), sticky="ew")
        test_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            test_frame, text="Tint Map Brightness",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=12, pady=(10, 4), sticky="w")
#        ctk.CTkLabel(
#            test_frame,
#            text="",
#            wraplength=580, justify="left",
#        ).grid(row=1, column=0, columnspan=3, padx=12, pady=(0, 8), sticky="w")
        ctk.CTkLabel(test_frame, text="Brightness (-90% to +90%):").grid(
            row=2, column=0, padx=12, pady=(0, 12), sticky="w")
        self.tintmap_brightness_slider = ctk.CTkSlider(
            test_frame, from_=-90, to=90, number_of_steps=36,
            variable=self.tintmap_brightness_percent_var,
            command=self._on_tintmap_brightness_percent_changed,
        )
        self.tintmap_brightness_slider.grid(
            row=2, column=1, padx=(0, 12), pady=(0, 12), sticky="ew")
        ctk.CTkLabel(
            test_frame, textvariable=self.tintmap_brightness_percent_label_var, width=55,
        ).grid(row=2, column=2, padx=(0, 12), pady=(0, 12))
        ctk.CTkButton(
            test_frame, text="Apply Brightness",
            command=self._start_tintmap_patch,
        ).grid(row=3, column=2, padx=(0, 12), pady=(0, 12), sticky="ew")
        ctk.CTkLabel(
            test_frame, text="5% steps. 0% restores originals. Changes apply only when you click Apply.",
            wraplength=580, justify="left",
        ).grid(row=3, column=0, columnspan=2, padx=12, pady=(0, 10), sticky="w")
        preset_actions = ctk.CTkFrame(tab, fg_color="transparent")
        preset_actions.grid(row=2, column=0, padx=20, pady=(0, 8), sticky="ew")
        ctk.CTkButton(
            preset_actions, text="Save Settings", width=140,
            command=self._save_tintmap_preset,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            preset_actions, text="Update Selected", width=150,
            command=self._update_tintmap_preset,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            preset_actions, text="Delete Selected", width=150,
            fg_color="#8a3d3d", hover_color="#6f3030",
            command=self._delete_tintmap_presets,
        ).pack(side="left", padx=8)
        ctk.CTkLabel(preset_actions, text="Comment:").pack(
            side="left", padx=(16, 6)
        )
        ctk.CTkEntry(
            preset_actions,
            textvariable=self.tintmap_comment_var,
            placeholder_text="Optional comment",
            width=240,
        ).pack(side="left", padx=(0, 8))

        preset_table_frame = ctk.CTkFrame(tab)
        preset_table_frame.grid(
            row=3, column=0, padx=20, pady=(0, 20), sticky="nsew"
        )
        preset_table_frame.grid_columnconfigure(0, weight=1)
        preset_table_frame.grid_rowconfigure(0, weight=1)
        table = TreeviewTemplate.create(
            preset_table_frame,
            columns=("comment", "settings"),
            headings={"comment": "Comment", "settings": "Brightness"},
            min_widths={"comment": 150, "settings": 100},
            max_widths={"comment": 600, "settings": 180},
            stretch=(),
            selectmode="extended",
            dynamic_width=True,
        )
        self.tintmap_preset_tree = table["tree"]
        self.tintmap_preset_tree.bind(
            "<<TreeviewSelect>>", self._on_tintmap_preset_selected, add="+"
        )
        try:
            presets = load_tintmap_presets(self.CONFIG_FILE)
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showwarning(
                "Tint Map Settings",
                f"Saved settings could not be loaded:\n{exc}",
            )
            presets = []
        self._render_tintmap_presets(presets)

    def _tintmap_preset_settings(self, record):
        percent = record["brightness_percent"]
        return "0%" if percent == 0 else f"{percent:+d}%"

    def _tintmap_tree_records(self):
        records = []
        for item in self.tintmap_preset_tree.get_children(""):
            comment, settings = self.tintmap_preset_tree.item(item, "values")
            records.append({"brightness_percent": int(str(settings).rstrip("%")), "comment": str(comment)})
        return validate_tintmap_presets(records)

    def _render_tintmap_presets(self, records, selected_index=None):
        tree = self.tintmap_preset_tree
        tree.delete(*tree.get_children(""))
        for record in records:
            tree.insert(
                "", "end",
                values=(
                    record.get("comment", ""),
                    self._tintmap_preset_settings(record),
                ),
            )
        children = tree.get_children("")
        if selected_index is not None and 0 <= selected_index < len(children):
            selected = children[selected_index]
            tree.selection_set(selected)
            tree.focus(selected)
            tree.see(selected)

    def _save_tintmap_preset_rows(self, records, selected_index=None):
        try:
            path = save_tintmap_presets(self.CONFIG_FILE, records)
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showerror(
                "Tint Map Settings", f"Settings could not be saved:\n{exc}"
            )
            return False
        self._render_tintmap_presets(records, selected_index)
        self.status_var.set(f"Tint Map settings saved: {path.name}")
        return True

    def _current_tintmap_preset(self):
        return validate_tintmap_presets([{
            "brightness_percent": self.tintmap_brightness_percent_var.get(),
            "comment": self.tintmap_comment_var.get(),
        }])[0]

    def _save_tintmap_preset(self):
        try:
            record = self._current_tintmap_preset()
        except ValueError as exc:
            messagebox.showerror("Tint Map Settings", str(exc))
            return
        records = self._tintmap_tree_records()
        records.append(record)
        self._save_tintmap_preset_rows(records, selected_index=len(records) - 1)

    def _update_tintmap_preset(self):
        selected = self.tintmap_preset_tree.selection()
        if len(selected) != 1:
            messagebox.showwarning(
                "Tint Map Settings", "Select one table entry to update."
            )
            return
        try:
            record = self._current_tintmap_preset()
        except ValueError as exc:
            messagebox.showerror("Tint Map Settings", str(exc))
            return
        records = self._tintmap_tree_records()
        index = self.tintmap_preset_tree.index(selected[0])
        records[index] = record
        self._save_tintmap_preset_rows(records, selected_index=index)

    def _delete_tintmap_presets(self):
        selected = self.tintmap_preset_tree.selection()
        if not selected:
            messagebox.showwarning(
                "Tint Map Settings", "Select at least one table entry to delete."
            )
            return
        if not messagebox.askyesno(
            "Tint Map Settings", f"Delete {len(selected)} selected setting(s)?"
        ):
            return
        selected_set = set(selected)
        records = [
            record for item, record in zip(
                self.tintmap_preset_tree.get_children(""),
                self._tintmap_tree_records(),
            ) if item not in selected_set
        ]
        self._save_tintmap_preset_rows(records)

    def _on_tintmap_preset_selected(self, _event=None):
        selected = self.tintmap_preset_tree.selection()
        if len(selected) != 1:
            return
        comment, settings = self.tintmap_preset_tree.item(selected[0], "values")
        percent = int(str(settings).rstrip("%"))
        self.tintmap_brightness_slider.set(percent)
        self._on_tintmap_brightness_percent_changed(percent)
        self.tintmap_comment_var.set(comment)



    def _update_texture_detected_region(self):
        """Compatibility hook: tintmap brightness is independent of island region."""
        return

    def _on_tintmap_brightness_percent_changed(self, value):
        """Snap the control to 5% steps; moving it never starts DDS writes."""
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError):
            value = 0.0
        if not math.isfinite(value):
            value = 0.0
        percent = int(round(max(-90.0, min(90.0, value)) / 5.0)) * 5
        self.tintmap_brightness_percent_var.set(percent)
        self.tintmap_brightness_percent_label_var.set(
            "0%" if percent == 0 else f"{percent:+d}%")
        return percent

    def _start_tintmap_patch(self):
        """Run the tintmap worker pool without blocking CustomTkinter."""
        if getattr(self, "_tintmap_patch_running", False):
            messagebox.showwarning("Tintmaps", "Tintmap patching is already running.")
            return

        a7m_path = self.unpack_file_var.get().strip() or self.pack_file_var.get().strip()
        percent = self._on_tintmap_brightness_percent_changed(
            self.tintmap_brightness_percent_var.get())
        encoder = tintmap_encoder_status()
        if not encoder["native"]:
            messagebox.showwarning(
                "Patch Tintmaps",
                "The native bc7enc DDS encoder is unavailable.\n\n"
                "The slow Python DXT1 fallback will be used. Conversion can take much longer.\n\n"
                f"Reason: {encoder['detail']}",
            )
        self._tintmap_patch_encoder = encoder
        self._tintmap_patch_running = True
        self._tintmap_patch_queue = Queue()
        StatusWindowTemplate.close(getattr(self, "_tintmap_patch_popup", None))
        self._tintmap_patch_popup = StatusWindowTemplate.create(
            self,
            text=f"Preparing tintmap patch...\nEncoder: {encoder['name']}",
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
                    a7m_path, brightness_percent=percent,
                    progress_callback=lambda *args: events.put(("progress", *args)),
                )
                events.put(("done", result))
            except Exception as exc:
                events.put(("error", f"{type(exc).__name__}: {exc}"))

        self._tintmap_patch_thread = threading.Thread(
            target=worker,
            name="TintmapBrightnessPatch",
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
                if stage == "encoder":
                    name, detail, native = payload
                    self._tintmap_patch_encoder = {"name": name, "detail": detail, "native": native}
                    text = f"Encoder: {name}\n{detail}"
                    fraction = 0.01
                elif stage == "folder":
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
            encoder = getattr(self, "_tintmap_patch_encoder", tintmap_encoder_status())
            text = f"Encoder: {encoder['name']}\n\n{text}"
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
        encoder = getattr(self, "_tintmap_patch_encoder", tintmap_encoder_status())
        summary = (
            f"Encoder: {encoder['name']}\n"
            f"Folder: {result.tintmaps_folder}\n"
            f"DDS found: {result.found}\nApplied: {result.changed}\n"
            f"Restored: {result.restored}\nSkipped: {result.skipped}\nFailed: {result.failed}"
        )
        if result.failed:
            messagebox.showwarning("Tintmaps", summary + "\n\n" + details)
        else:
            messagebox.showinfo("Tintmaps", summary)
        self._rebuild_regional_rd3d_cache()
