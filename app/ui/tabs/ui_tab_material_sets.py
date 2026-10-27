from __future__ import annotations

import copy
import os
import re
import sys
import tempfile
import tkinter as tk
import app.backend.xml_backend as ET
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from app.templates.template_table import TemplateTable, TableColumn


class MaterialSetsTabMixin:
    """Independent material-set editor; only the shared table template is reused."""

    def _build_material_sets_tab(self, tab):
        self.ms_source_var = tk.StringVar(master=self)
        self.ms_selection_var = tk.StringVar(master=self, value="Select material set...")
        self.ms_info_var = tk.StringVar(master=self, value="Please load a material set.")
        self.ms_document = None
        self.ms_loaded_path = None
        self.ms_rows = []
        self.ms_catalog = {}
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)
        source = ctk.CTkFrame(tab)
        source.grid(row=0, column=0, padx=5, pady=(5, 10), sticky="ew")
        source.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(source, text="Material set:").grid(row=0, column=0, padx=15, pady=12)
        self.ms_menu = ctk.CTkOptionMenu(
            source, variable=self.ms_selection_var, values=["Select material set..."],
            dynamic_resizing=False, command=self._ms_choose_catalog,
        )
        self.ms_menu.grid(row=0, column=1, columnspan=3, padx=(0, 15), pady=12, sticky="ew")
        ctk.CTkLabel(source, text="XML / .materialset:").grid(row=1, column=0, padx=15, pady=(0, 12))
        ctk.CTkEntry(source, textvariable=self.ms_source_var).grid(row=1, column=1, padx=(0, 8), pady=(0, 12), sticky="ew")
        ctk.CTkButton(source, text="Browse", width=100, command=self._ms_browse).grid(row=1, column=2, padx=(0, 8), pady=(0, 12))
        ctk.CTkButton(source, text="Reload", width=100, command=self._ms_reload).grid(row=1, column=3, padx=(0, 15), pady=(0, 12))
        ctk.CTkLabel(
            tab, text="Original values are read-only on the first line. Edit the second line.",
            text_color="gray70", anchor="w",
        ).grid(row=1, column=0, padx=12, pady=(0, 6), sticky="ew")
        self.ms_table = TemplateTable(
            tab,
            (TableColumn("section", "Section", width=110),
             TableColumn("field", "Field / Material ID", width=240),
             TableColumn("value", "Original / Editable value", weight=1)),
            row_height=TemplateTable.COMBINED_ROW_HEIGHT,
            row_builder=self._ms_build_row, fg_color=TemplateTable.TABLE_BACKGROUND,
        )
        self.ms_table.grid(row=2, column=0, padx=5, pady=(0, 10), sticky="nsew")
        actions = ctk.CTkFrame(tab, fg_color="transparent")
        actions.grid(row=3, column=0, padx=10, pady=(0, 8), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(actions, textvariable=self.ms_info_var, anchor="w", wraplength=580).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(actions, text="Reset", width=100, command=self._ms_reset).grid(row=0, column=1, padx=8)
        ctk.CTkButton(actions, text="Save as...", width=150, command=self._ms_save_as).grid(row=0, column=2)
        self._ms_refresh_catalog()

    @staticmethod
    def _ms_build_row(row, data, _index):
        row.grid_columnconfigure(2, weight=1)
        for column, key, width in ((0, "section", 110), (1, "field", 240)):
            ctk.CTkLabel(
                row, text=data[key], width=width, anchor="w",
                font=ctk.CTkFont(size=TemplateTable.BODY_FONT_SIZE),
                text_color=TemplateTable.BODY_TEXT_COLOR,
            ).grid(row=0, column=column, rowspan=2, padx=TemplateTable.CELL_PADX, pady=5, sticky="nsw")
        ctk.CTkEntry(
            row, textvariable=data["original_var"], state="disabled", border_width=0,
            height=TemplateTable.ENTRY_HEIGHT,
            font=ctk.CTkFont(size=TemplateTable.ENTRY_FONT_SIZE),
            fg_color=TemplateTable.DISABLED_FG_COLOR, text_color=TemplateTable.DISABLED_TEXT_COLOR,
        ).grid(row=0, column=2, padx=5, pady=(5, 2), sticky="ew")
        ctk.CTkEntry(
            row, textvariable=data["edit_var"], border_width=1,
            height=TemplateTable.ENTRY_HEIGHT,
            font=ctk.CTkFont(size=TemplateTable.ENTRY_FONT_SIZE),
            fg_color=TemplateTable.EDITABLE_FG_COLOR, text_color=TemplateTable.EDITABLE_TEXT_COLOR,
        ).grid(row=1, column=2, padx=5, pady=(2, 5), sticky="ew")

    def _ms_refresh_catalog(self):
        app_dir = Path(self.CONFIG_FILE).parent
        bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
        catalog = {}
        # Later entries override bundled files; .materialset wins over .xml.
        for folder in (bundle_dir / "material_sets", app_dir / "custom_material_sets"):
            if folder.is_dir():
                for suffix in (".xml", ".materialset"):
                    for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
                        if path.is_file() and path.suffix.casefold() == suffix:
                            catalog[path.stem] = path
        self.ms_catalog = catalog
        self.ms_menu.configure(values=sorted(catalog, key=str.casefold) or ["No material sets found"])

    def _ms_discard_ok(self):
        changed = any(row["edit_var"].get() != row["original"] for row in self.ms_rows)
        return not changed or messagebox.askyesno("material_sets", "Discard the current edits?", parent=self)

    def _ms_choose_catalog(self, name):
        path = self.ms_catalog.get(name)
        if path is not None and self._ms_discard_ok():
            self._ms_load(path)
        elif self.ms_loaded_path is not None:
            self.ms_selection_var.set(self.ms_loaded_path.stem)

    def _ms_browse(self):
        if not self._ms_discard_ok():
            return
        value = filedialog.askopenfilename(
            parent=self, title="Select material set",
            filetypes=[("Material set / XML", "*.materialset *.xml"), ("All files", "*.*")],
        )
        if value:
            self._ms_load(Path(value))

    def _ms_reload(self):
        if self._ms_discard_ok():
            self._ms_load(Path(self.ms_source_var.get().strip()))

    @staticmethod
    def _ms_tag(node):
        return node.tag.rsplit("}", 1)[-1] if isinstance(node.tag, str) else ""

    @staticmethod
    def _ms_expand_compact(text):
        # Tokenize markup, keeping comments, CDATA and quoted attributes intact.
        token = re.compile(r'<!--[\s\S]*?-->|<!\[CDATA\[[\s\S]*?\]\]>|<\?[\s\S]*?\?>|<(?:[^>"\']|"[^"]*"|\'[^\']*\')*>')
        stack = []
        def expand(match):
            value = match.group(0)
            if value == "</>":
                if not stack:
                    raise ET.ParseError("Unmatched compact closing tag")
                return "</" + stack.pop() + ">"
            if value.startswith(("<!", "<?")):
                return value
            if value.startswith("</"):
                name = value[2:-1].strip()
                if not stack or stack.pop() != name:
                    raise ET.ParseError("Mismatched closing tag: " + name)
            elif not value.rstrip().endswith("/>"):
                name = re.match(r'<\s*([^\s/>]+)', value)
                if name:
                    stack.append(name.group(1))
            return value
        result = token.sub(expand, text)
        if stack:
            raise ET.ParseError("Unclosed element: " + stack[-1])
        return result

    @classmethod
    def _ms_read_document(cls, path):
        raw = Path(path).read_bytes()
        if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
            text = raw.decode('utf-16')
        else:
            text = raw.decode('utf-8-sig')
        def legal(code):
            return code in (9, 10, 13) or 32 <= code <= 0xD7FF or 0xE000 <= code <= 0xFFFD or 0x10000 <= code <= 0x10FFFF
        text = re.sub(
            r'&#(x[0-9a-fA-F]+|[0-9]+);',
            lambda m: m.group(0) if legal(int(m[1][1:], 16) if m[1].startswith('x') else int(m[1])) else '',
            text,
        )
        text = ''.join(char for char in text if legal(ord(char)))
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
        root = ET.fromstring(cls._ms_expand_compact(text), parser=parser)
        material = next((n for n in root.iter() if cls._ms_tag(n) == "MaterialSet"), None)
        if material is None:
            raise ValueError("No MaterialSet element found.")
        return ET.ElementTree(root), material

    @classmethod
    def _ms_fields(cls, material):
        fields = []
        # Global settings precede textures and per-material paths. Keep empty
        # elements visible so optional texture paths can be entered or cleared.
        settings = (
            'ShaderType',
            'GritTiling',
            'GritAlphaSharpness',
            'GritSlope',
            'CliffTiling',
            'CliffAlphaSharpness',
            'CliffSlope',
            'SlushDiffuseTexture',
            'SlushNormalTexture',
            'SlushHeightTexture',
            'SlushTiling',
            'SlushAlphaSharpness',
            'SlushSlope',
            'SubSurfaceTexture',
            'SubSurfaceTiling',
            'SubSurfaceDistortion',
            'SubSurfaceDepth',
        )
        for name in settings:
            for node in material:
                if cls._ms_tag(node) == name:
                    fields.append(("Settings", name, node))
        for name in ("GritDiffuseTexture", "CliffDiffuseTexture", "CliffNormalTexture"):
            for node in material.iter():
                if cls._ms_tag(node) == name:
                    fields.append(("Textures", name, node))
        for entry in material.iter():
            if cls._ms_tag(entry) != "Material":
                continue
            material_id = next(((n.text or "").strip() for n in entry if cls._ms_tag(n) == "ID"), "?")
            for node in entry:
                name = cls._ms_tag(node)
                if name in {"FileName", "ObjectFileName", "ObjectFilename"} and (node.text or "").strip():
                    fields.append(("Material files", f"{name} | Material ID {material_id}", node))
        return fields

    def _ms_load(self, path):
        try:
            document, material = self._ms_read_document(path)
            rows = []
            for section, field, node in self._ms_fields(material):
                original = node.text or ""
                rows.append({"section": section, "field": field, "node": node,
                             "original": original,
                             "original_var": tk.StringVar(master=self, value=original),
                             "edit_var": tk.StringVar(master=self, value=original)})
        except (OSError, UnicodeError, ET.ParseError, ValueError) as exc:
            messagebox.showerror("material_sets", f"Could not load material set:\n{exc}", parent=self)
            return False
        self.ms_document, self.ms_loaded_path, self.ms_rows = document, Path(path), rows
        self.ms_source_var.set(str(path))
        self.ms_selection_var.set(Path(path).stem)
        self.ms_table.set_rows(rows)
        self.ms_table.scroll_to_top()
        self.ms_info_var.set(f"{Path(path).name} | {len(rows)} editable fields")
        self.status_var.set(f"material_sets loaded: {Path(path).name}")
        return True

    def _ms_reset(self):
        for row in self.ms_rows:
            row["edit_var"].set(row["original"])
        self.ms_info_var.set(f"{len(self.ms_rows)} fields reset to original values")

    def _ms_edited_document(self):
        if self.ms_document is None:
            raise ValueError("Please load a material set first.")
        document = copy.deepcopy(self.ms_document)
        nodes = dict(zip(self.ms_document.getroot().iter(), document.getroot().iter()))
        for row in self.ms_rows:
            nodes[row["node"]].text = row["edit_var"].get()
        return document

    @staticmethod
    def _ms_write_export(document, target):
        target = Path(target).with_suffix(".materialset")
        link = target.with_name(target.stem + ".xml.lnk")
        # Stage both files before replacing either destination.
        staged = []
        try:
            for destination in (target, link):
                fd, name = tempfile.mkstemp(prefix=".material_sets_", dir=target.parent)
                os.close(fd)
                staged.append((Path(name), destination))
            document.write(staged[0][0], encoding="utf-8", xml_declaration=False)
            staged[1][0].write_text(f"data/config/engine/material_sets/{target.name}", encoding="utf-8")
            for temporary, destination in staged:
                os.replace(temporary, destination)
        finally:
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)
        return target, link

    def _ms_save_as(self):
        try:
            document = self._ms_edited_document()
        except ValueError as exc:
            messagebox.showerror("material_sets", str(exc), parent=self)
            return
        value = filedialog.asksaveasfilename(
            parent=self, title="Save material set as", defaultextension=".materialset",
            initialdir=str(self.ms_loaded_path.parent),
            initialfile=self.ms_loaded_path.stem + "_edited.materialset",
            filetypes=[("Material set", "*.materialset")],
        )
        if not value:
            return
        target = Path(value).with_suffix(".materialset")
        link = target.with_name(target.stem + ".xml.lnk")
        if (target.exists() or link.exists()) and not messagebox.askyesno(
            "material_sets", "Overwrite existing material-set and link files?", parent=self,
        ):
            return
        try:
            target, link = self._ms_write_export(document, target)
        except (OSError, ValueError) as exc:
            messagebox.showerror("material_sets", f"Could not save files:\n{exc}", parent=self)
            return
        self._ms_refresh_catalog()
        self.status_var.set(f"material_sets saved: {target.name} | {link.name}")
        messagebox.showinfo("material_sets", f"Files saved:\n{target}\n{link}", parent=self)
