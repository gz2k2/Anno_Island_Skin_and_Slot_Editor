from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from app.templates.template_popup import PopupTemplate
from app.templates.template_treeview import TreeviewTemplate
from app.config.config_rd3d import RD3D_CATEGORIES, RD3D_CATEGORY_REGIONS, RD3D_REGIONS
from app.functions.function_custom_content import (
    custom_object_options_path,
    custom_objects_path,
    load_custom_object_options,
    load_custom_objects,
    invalidate_custom_content_cache,
)


class CustomContentTabMixin:
    """Manage user-defined object records separately from built-in databases."""

    def _build_custom_content_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(
            tab, text="Custom Content",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 12), sticky="w")
        ctk.CTkButton(
            tab, text="Objects", width=160,
            command=self._open_custom_objects,
        ).grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

    def _custom_objects_path(self):
        return custom_objects_path(self.CONFIG_FILE)

    @staticmethod
    def _validate_custom_objects(rows):
        if not isinstance(rows, list):
            raise ValueError("Objects must be a list.")
        result = []
        seen = set()
        for index, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                raise ValueError(f"Invalid object record at row {index}.")
            if any(not isinstance(row.get(key), str) or not row[key].strip()
                   for key in ("region", "category", "object")):
                raise ValueError(f"Region, Category and Object must not be empty (row {index}).")
            record = {key: row[key].strip() for key in ("region", "category", "object")}
            identity = tuple(value.casefold() for value in record.values())
            if identity in seen:
                raise ValueError(f"Duplicate object record at row {index}.")
            seen.add(identity)
            result.append(record)
        return result

    def _load_custom_objects(self):
        return load_custom_objects(self.CONFIG_FILE, strict=True)

    def _write_custom_objects(self, rows):
        rows = self._validate_custom_objects(rows)
        path = self._custom_objects_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="custom_objects_", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"schema": 1, "objects": rows}, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            invalidate_custom_content_cache(self.CONFIG_FILE)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return path

    def _open_custom_objects(self):
        existing = getattr(self, "_custom_objects_window", None)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            PopupTemplate.request_focus(existing, delay_ms=60)
            return
        try:
            rows = self._load_custom_objects()
        except (OSError, ValueError, UnicodeError) as exc:
            messagebox.showerror("Custom Objects", f"Could not load custom objects:\n{exc}", parent=self)
            return

        state = {"dirty": False}
        window = None

        def close_requested():
            if state["dirty"]:
                return messagebox.askyesno(
                    "Custom Objects", "Discard unsaved changes and close?", parent=window,
                )
            return True

        built = PopupTemplate.create_window(
            self, title="Custom Objects", heading="Custom Objects",
            geometry="940x620", min_size=(720, 440),
            close_command=close_requested,
        )
        window = built["window"]
        self._custom_objects_window = window
        window.transient(self)
        PopupTemplate.apply_native_titlebar_controls(window)
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)

        csv_actions = ctk.CTkFrame(window, fg_color="transparent")
        csv_actions.grid(row=0, column=0, padx=(20, 44), pady=(10, 0), sticky="e")

        inputs = ctk.CTkFrame(window, fg_color="transparent")
        inputs.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="ew")
        variables = {}
        for column, (key, title) in enumerate(
                (("region", "Region"), ("category", "Category"), ("object", "Object"))):
            inputs.grid_columnconfigure(column, weight=1)
            ctk.CTkLabel(inputs, text=title).grid(
                row=0, column=column, padx=(0, 10), sticky="w",
            )
            variable = tk.StringVar(master=window)
            variables[key] = variable
            if key in {"region", "category"}:
                ctk.CTkButton(
                    inputs, text=f"Select {title}",
                    command=lambda field=key, var=variable: self._open_custom_object_selection(
                        window, field, var,
                    ),
                ).grid(row=1, column=column, padx=(0, 10), sticky="ew")
                ctk.CTkLabel(
                    inputs, textvariable=variable, anchor="w", justify="left", wraplength=260,
                ).grid(row=2, column=column, padx=(0, 10), pady=(4, 0), sticky="ew")
            else:
                ctk.CTkEntry(inputs, textvariable=variable).grid(
                    row=1, column=column, padx=(0, 10), sticky="ew",
                )

        table_frame = ctk.CTkFrame(window)
        table_frame.grid(row=2, column=0, padx=20, pady=(0, 12), sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        table = TreeviewTemplate.create(
            table_frame, columns=("region", "category", "object"),
            headings={"region": "Region", "category": "Category", "object": "Object"},
            min_widths={"region": 70, "category": 80, "object": 80},
            max_widths={"region": 1200, "category": 1200, "object": 2400},
            stretch=(), dynamic_width=True, width_padding=24,
            selectmode="extended",
        )
        tree = table["tree"]
        tree.grid(row=0, column=0, sticky="nsew")
        table["y_scrollbar"].grid(row=0, column=1, sticky="ns")
        table["x_scrollbar"].grid(row=1, column=0, sticky="ew")
        def insert_record(record):
            # Use exactly the shared category colors from Objects Table 1.
            category = record["category"]
            # A multi-category row uses its first selected category's shared color.
            first_category = category.split(", ", 1)[0]
            color = self._object_configuration_color_for_category(first_category)
            tree.tag_configure(category, foreground=color)
            tree._template_tag_styles[category] = {"foreground": color}
            return tree.insert(
                "", "end", values=tuple(record[key] for key in variables),
                tags=(category,),
            )

        for row in rows:
            insert_record(row)

        info = tk.StringVar(master=window, value=f"{len(rows)} objects")

        def table_rows():
            return [dict(zip(variables, tree.item(item, "values")))
                    for item in tree.get_children("")]

        def changed():
            state["dirty"] = True
            info.set(f"{len(tree.get_children(''))} objects | Unsaved changes")

        def selection_changed(_event=None):
            selected = tree.selection()
            if len(selected) != 1:
                return
            values = tree.item(selected[0], "values")
            for key, value in zip(variables, values):
                variables[key].set(value)

        tree.bind("<<TreeviewSelect>>", selection_changed, add="+")

        def persist(records):
            try:
                return self._write_custom_objects(records)
            except (OSError, ValueError, UnicodeError) as exc:
                messagebox.showerror("Custom Objects", f"Could not save custom objects:\n{exc}", parent=window)
                return None

        def saved(path):
            state["dirty"] = False
            info.set(f"{len(tree.get_children(''))} objects | Saved: {path}")

        def export_csv():
            destination = filedialog.asksaveasfilename(
                title="Export Custom Objects CSV",
                parent=window,
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile="custom_objects.csv",
            )
            if not destination:
                return
            try:
                with Path(destination).open("w", newline="", encoding="utf-8-sig") as stream:
                    writer = csv.DictWriter(stream, fieldnames=("region", "category", "object"))
                    writer.writeheader()
                    writer.writerows(table_rows())
            except (OSError, UnicodeError, csv.Error) as exc:
                messagebox.showerror("Export CSV", f"Could not export CSV:\n{exc}", parent=window)
                return
            info.set(f"CSV exported: {destination}")

        def duplicate_decision(existing_record, imported_record):
            dialog = PopupTemplate.create_window(
                window,
                title="Duplicate Custom Object",
                geometry="620x330",
                min_size=(620, 330),
                resizable=False,
                modal=True,
                add_header=False,
                maximize=False,
            )["window"]
            dialog.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                dialog,
                text="Duplicate custom object found",
                font=ctk.CTkFont(size=18, weight="bold"),
            ).grid(row=0, column=0, padx=20, pady=(20, 8), sticky="w")
            ctk.CTkLabel(
                dialog,
                text=(
                    f"Object: {imported_record['object']}\n\n"
                    f"Existing: {existing_record['region']} | {existing_record['category']}\n"
                    f"Imported: {imported_record['region']} | {imported_record['category']}"
                ),
                anchor="w", justify="left", wraplength=570,
            ).grid(row=1, column=0, padx=20, pady=(0, 12), sticky="ew")
            remember_var = tk.BooleanVar(master=dialog, value=False)
            ctk.CTkCheckBox(
                dialog, text="Don't ask again", variable=remember_var,
            ).grid(row=2, column=0, padx=20, pady=(0, 16), sticky="w")
            answer = {"action": "cancel", "remember": False}

            def choose(action):
                answer["action"] = action
                answer["remember"] = bool(remember_var.get())
                PopupTemplate.close_window(dialog)

            buttons = ctk.CTkFrame(dialog, fg_color="transparent")
            buttons.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="e")
            ctk.CTkButton(
                buttons, text="Cancel Import", width=120,
                fg_color="#555", hover_color="#666",
                command=lambda: choose("cancel"),
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                buttons, text="Skip", width=100,
                command=lambda: choose("skip"),
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                buttons, text="Overwrite", width=110,
                command=lambda: choose("overwrite"),
            ).pack(side="left")
            dialog.protocol("WM_DELETE_WINDOW", lambda: choose("cancel"))
            PopupTemplate.request_focus(dialog, delay_ms=80)
            window.wait_window(dialog)
            return answer["action"], answer["remember"]

        def import_csv():
            source = filedialog.askopenfilename(
                title="Import Custom Objects CSV",
                parent=window,
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            )
            if not source:
                return
            try:
                sample = Path(source).read_text(encoding="utf-8-sig")
                try:
                    dialect = csv.Sniffer().sniff(sample[:8192], delimiters=",;\t")
                except csv.Error:
                    dialect = csv.excel
                reader = csv.DictReader(sample.splitlines(), dialect=dialect)
                if reader.fieldnames is None:
                    raise ValueError("CSV header is missing.")
                normalized = {str(name).strip().casefold(): name for name in reader.fieldnames}
                missing_columns = [name for name in ("region", "category", "object") if name not in normalized]
                if missing_columns:
                    raise ValueError("Missing CSV column(s): " + ", ".join(missing_columns))
                imported = []
                for line_number, csv_row in enumerate(reader, start=2):
                    record = {
                        key: str(csv_row.get(normalized[key], "") or "").strip()
                        for key in ("region", "category", "object")
                    }
                    if not all(record.values()):
                        raise ValueError(f"Region, Category and Object must not be empty (CSV row {line_number}).")
                    imported.append(record)
            except (OSError, UnicodeError, csv.Error, ValueError) as exc:
                messagebox.showerror("Import CSV", f"Could not import CSV:\n{exc}", parent=window)
                return

            current = table_rows()
            by_object = {record["object"].casefold(): index for index, record in enumerate(current)}
            automatic_action = None
            added = overwritten = skipped = 0
            for record in imported:
                key = record["object"].casefold()
                existing_index = by_object.get(key)
                if existing_index is None:
                    current.append(record)
                    by_object[key] = len(current) - 1
                    added += 1
                    continue
                action = automatic_action
                if action is None:
                    action, remember = duplicate_decision(current[existing_index], record)
                    if action == "cancel":
                        info.set("CSV import cancelled; no changes were applied.")
                        return
                    if remember:
                        automatic_action = action
                if action == "overwrite":
                    current[existing_index] = record
                    overwritten += 1
                else:
                    skipped += 1

            try:
                current = self._validate_custom_objects(current)
            except ValueError as exc:
                messagebox.showerror("Import CSV", str(exc), parent=window)
                return

            # Add unknown CSV regions/categories to the shared custom selection
            # options. Regions may contain a comma-separated multi-selection;
            # categories are stored as one value per object record.
            try:
                option_data = self._load_custom_object_options()
                new_option_counts = {"region": 0, "category": 0}
                for field in ("region", "category"):
                    builtin = {
                        value.casefold()
                        for value in self._custom_object_selection_options(field)
                    }
                    custom = {
                        value.casefold()
                        for value in option_data[field]
                    }
                    values = []
                    for record in current:
                        raw_values = (
                            [part.strip() for part in record[field].split(",") if part.strip()]
                            if field == "region" else [record[field].strip()]
                        )
                        values.extend(raw_values)
                    for value in values:
                        key = value.casefold()
                        if key in builtin or key in custom:
                            continue
                        option_data[field].append(value)
                        custom.add(key)
                        new_option_counts[field] += 1
                for field in ("region", "category"):
                    option_data[field].sort(key=str.casefold)
                if any(new_option_counts.values()):
                    options_path = self._custom_object_options_path()
                    options_path.parent.mkdir(parents=True, exist_ok=True)
                    fd, temporary = tempfile.mkstemp(
                        prefix="custom_options_", suffix=".tmp", dir=options_path.parent
                    )
                    try:
                        with os.fdopen(fd, "w", encoding="utf-8") as stream:
                            json.dump(
                                dict(schema=1, **option_data), stream,
                                ensure_ascii=False, indent=2,
                            )
                            stream.write("\n")
                            stream.flush()
                            os.fsync(stream.fileno())
                        os.replace(temporary, options_path)
                        invalidate_custom_content_cache(self.CONFIG_FILE)
                    finally:
                        if os.path.exists(temporary):
                            os.unlink(temporary)
            except (OSError, UnicodeError, ValueError) as exc:
                messagebox.showerror(
                    "Import CSV",
                    f"Could not create custom Region/Category options:\n{exc}",
                    parent=window,
                )
                return

            tree.delete(*tree.get_children(""))
            for record in current:
                insert_record(record)
            changed()
            info.set(
                f"CSV imported: {added} added, {overwritten} overwritten, {skipped} skipped; "
                f"{new_option_counts['region']} custom region(s), "
                f"{new_option_counts['category']} custom category/categories created. "
                "Click Save to write the object changes."
            )

        ctk.CTkButton(
            csv_actions, text="Import .csv", width=110, command=import_csv,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            csv_actions, text="Export .csv", width=110, command=export_csv,
        ).pack(side="left")

        def add():
            record = {key: variable.get().strip() for key, variable in variables.items()}
            records = table_rows() + [record]
            try:
                self._validate_custom_objects(records)
            except ValueError as exc:
                messagebox.showwarning("Custom Objects", str(exc), parent=window)
                return False

            # Add behaves like Change: update the in-memory table only.
            # The Save button is the only action that writes custom_objects.json.
            item = insert_record(record)
            tree.selection_set(item)
            tree.focus(item)
            tree.see(item)
            changed()
            return True

        def delete():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("Custom Objects", "Select at least one object to delete.", parent=window)
                return
            if not messagebox.askyesno(
                "Delete Custom Objects",
                f"Are you sure you want to delete the selected object(s)?\n\n"
                f"Selected objects: {len(selected)}",
                parent=window,
                icon="warning",
                default="no",
            ):
                return
            tree.delete(*selected)
            changed()

        def change():
            selected = tree.selection()
            if len(selected) != 1:
                messagebox.showwarning("Custom Objects", "Select exactly one object to edit.", parent=window)
                return False
            record = {key: variable.get().strip() for key, variable in variables.items()}
            records = table_rows()
            index = list(tree.get_children("")).index(selected[0])
            records[index] = record
            try:
                self._validate_custom_objects(records)
            except ValueError as exc:
                messagebox.showwarning("Custom Objects", str(exc), parent=window)
                return False
            category = record["category"]
            color = self._object_configuration_color_for_category(category.split(", ", 1)[0])
            tree.tag_configure(category, foreground=color)
            tree._template_tag_styles[category] = {"foreground": color}
            tree.item(selected[0], values=tuple(record.values()), tags=(category,))
            tree.schedule_autosize()
            changed()
            return True

        def save():
            # Persist table rows only; unapplied input edits are not committed.
            path = persist(table_rows())
            if path is None:
                return False
            saved(path)
            return True

        footer = ctk.CTkFrame(window, fg_color="transparent")
        footer.grid(row=3, column=0, padx=20, pady=(0, 18), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(footer, textvariable=info, anchor="w", wraplength=460).grid(
            row=0, column=0, sticky="w",
        )
        input_actions = ctk.CTkFrame(inputs, fg_color="transparent")
        input_actions.grid(row=2, column=2, padx=(0, 10), pady=(8, 0), sticky="e")
        ctk.CTkButton(input_actions, text="Change", width=100, command=change).pack(
            side="left", padx=(0, 8),
        )
        ctk.CTkButton(input_actions, text="Add", width=100, command=add).pack(
            side="left",
        )
        ctk.CTkButton(
            footer, text="Delete", width=100, command=delete,
            fg_color=PopupTemplate.DANGER_BUTTON_FG_COLOR,
            hover_color=PopupTemplate.DANGER_BUTTON_HOVER_COLOR,
        ).grid(row=0, column=2, padx=(0, 8))
        ctk.CTkButton(footer, text="Save", width=100, command=save).grid(row=0, column=3)
        PopupTemplate.request_focus(window, delay_ms=100)

    @staticmethod
    def _custom_object_selection_options(field):
        if field == "region":
            represented = {region for regions in RD3D_CATEGORY_REGIONS.values()
                           for region in regions}
            return sorted((region for region in RD3D_REGIONS if region in represented),
                          key=str.casefold)
        if field == "category":
            return sorted(RD3D_CATEGORIES, key=str.casefold)
        raise ValueError(f"Unknown selection field: {field}")

    def _custom_object_options_path(self):
        return custom_object_options_path(self.CONFIG_FILE)

    def _load_custom_object_options(self):
        return load_custom_object_options(self.CONFIG_FILE, strict=True)

    def _store_custom_object_option(self, field, name):
        name = name.strip()
        if field not in {"region", "category"} or not name or "," in name:
            raise ValueError("Enter a non-empty name without commas.")
        data = self._load_custom_object_options()
        builtin_values = self._custom_object_selection_options(field)
        existing_builtin = next(
            (value for value in builtin_values if value.casefold() == name.casefold()), None
        )
        existing_custom = next(
            (value for value in data[field] if value.casefold() == name.casefold()), None
        )
        if field == "category" and existing_builtin is not None:
            raise ValueError(
                f"Category '{existing_builtin}' already exists and cannot be added as a custom category."
            )
        if existing_custom is not None:
            raise ValueError(f"Custom {field} '{existing_custom}' already exists.")
        if existing_builtin is not None:
            return existing_builtin
        data[field].append(name)
        data[field].sort(key=str.casefold)
        path = self._custom_object_options_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix="custom_options_", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(dict(schema=1, **data), stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            invalidate_custom_content_cache(self.CONFIG_FILE)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return name

    def _open_custom_object_selection(self, owner, field, target_variable):
        """Checkbox selection is applied explicitly; Cancel leaves inputs intact."""
        windows = getattr(self, "_custom_object_selection_windows", None)
        if windows is None:
            windows = self._custom_object_selection_windows = {}
        identity = (str(owner), field)
        existing = windows.get(identity)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            PopupTemplate.request_focus(existing, delay_ms=60)
            return
        title = "Regions" if field == "region" else "Categories"
        try:
            options = self._custom_object_selection_options(field) + self._load_custom_object_options()[field]
        except (OSError, ValueError, UnicodeError) as exc:
            messagebox.showerror("Custom Objects", f"Could not load selection options:\n{exc}", parent=owner)
            return
        selected = {value.strip() for value in target_variable.get().split(",") if value.strip()}
        if field == "category" and len(selected) > 1:
            selected = {sorted(selected, key=str.casefold)[0]}
        # Preserve older/custom values rather than silently deleting them.
        options = sorted(set(options) | selected, key=str.casefold)
        built = PopupTemplate.create_window(
            owner, title=f"Select {title}", heading=f"Select {title}",
            geometry="520x600", min_size=(400, 360),
        )
        popup = built["window"]
        windows[identity] = popup
        popup.transient(owner)
        PopupTemplate.apply_native_titlebar_controls(popup)
        popup.grid_columnconfigure(0, weight=1)
        list_row = 3 if field == "category" else 2
        popup.grid_rowconfigure(list_row, weight=1)
        filter_var = tk.StringVar(master=popup)
        if field == "category":
            filter_bar = ctk.CTkFrame(popup, fg_color="transparent")
            filter_bar.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
            filter_bar.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(filter_bar, text="Filter").grid(
                row=0, column=0, padx=(0, 8), sticky="w",
            )
            ctk.CTkEntry(filter_bar, textvariable=filter_var).grid(
                row=0, column=1, sticky="ew",
            )
        content = ctk.CTkScrollableFrame(popup)
        content.grid(row=list_row, column=0, padx=20, pady=(0, 12), sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        checks = {}
        widgets = {}

        def checkbox_clicked(option):
            if field == "category":
                # Clear all other selections, including currently filtered rows.
                for name, variable in checks.items():
                    if name != option:
                        variable.set(False)

        def create_checkbox(option, checked=False):
            variable = tk.BooleanVar(master=popup, value=checked)
            checks[option] = variable
            checkbox = ctk.CTkCheckBox(
                content, text=option, variable=variable,
                command=lambda name=option: checkbox_clicked(name),
            )
            checkbox.grid(row=len(widgets), column=0, padx=10, pady=6, sticky="w")
            widgets[option] = checkbox

        for option in options:
            create_checkbox(option, option in selected)

        def filter_changed(*_args):
            query = filter_var.get().strip().casefold()
            row = 0
            for option in sorted(widgets, key=str.casefold):
                widget = widgets[option]
                if query in option.casefold():
                    widget.grid(row=row, column=0, padx=10, pady=6, sticky="w")
                    row += 1
                else:
                    widget.grid_remove()

        if field == "category":
            filter_var.trace_add("write", filter_changed)

        custom_bar = ctk.CTkFrame(popup, fg_color="transparent")
        custom_bar.grid(row=list_row - 1, column=0, padx=20, pady=(0, 10), sticky="ew")
        custom_bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(custom_bar, text="New region" if field == "region" else "New category").grid(
            row=0, column=0, padx=(0, 8), sticky="w",
        )
        custom_name = tk.StringVar(master=popup)
        custom_entry = ctk.CTkEntry(custom_bar, textvariable=custom_name)
        custom_entry.grid(row=0, column=1, sticky="ew")

        def add_custom():
            try:
                name = self._store_custom_object_option(field, custom_name.get())
            except (OSError, ValueError, UnicodeError) as exc:
                messagebox.showerror("Custom Objects", str(exc), parent=popup)
                return
            # Reuse existing spelling to avoid case-only duplicate checkboxes.
            name = next((value for value in checks if value.casefold() == name.casefold()), name)
            if name not in checks:
                create_checkbox(name, checked=True)
            checks[name].set(True)
            widgets[name].select()
            checkbox_clicked(name)
            # Show the new category immediately, even when a different filter
            # was active. Filtering always includes dynamically added widgets.
            filter_var.set(name if field == "category" else "")
            filter_changed()

            def reveal_added():
                if not popup.winfo_exists():
                    return
                widget = widgets[name]
                if not widget.winfo_exists():
                    return
                # Wait for the filtered grid to settle before calculating the
                # scroll position; scrolling to zero cannot reveal lower rows.
                content.update_idletasks()
                canvas = content._parent_canvas
                bounds = canvas.bbox("all")
                if bounds:
                    height = max(1, bounds[3] - bounds[1])
                    position = max(0.0, min(1.0, (widget.winfo_y() - 6) / height))
                    canvas.yview_moveto(position)
                widget.focus_set()

            popup.after_idle(reveal_added)

        ctk.CTkButton(custom_bar, text="Add", width=80, command=add_custom).grid(
            row=0, column=2, padx=(8, 0),
        )
        custom_entry.bind("<Return>", lambda _event: add_custom())
        ctk.CTkLabel(
            popup, text="Custom names are saved immediately.", anchor="w",
        ).grid(row=list_row + 1, column=0, padx=20, pady=(0, 8), sticky="w")

        def apply():
            target_variable.set(", ".join(option for option in sorted(checks, key=str.casefold)
                                          if checks[option].get()))
            PopupTemplate.close_window(popup)
            PopupTemplate.request_focus(owner, delay_ms=60)

        buttons = ctk.CTkFrame(popup, fg_color="transparent")
        buttons.grid(row=list_row + 2, column=0, padx=20, pady=(0, 18), sticky="e")
        ctk.CTkButton(
            buttons, text="Cancel", width=100,
            command=lambda: PopupTemplate.close_window(popup),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="Apply", width=100, command=apply).pack(side="left")
        PopupTemplate.request_focus(popup, delay_ms=100)
