from __future__ import annotations

from pathlib import Path
import math
import random
import re
import tkinter as tk
import threading
from tkinter import messagebox
import app.backend.xml_backend as ET
import customtkinter as ctk
from PIL import Image, ImageTk

from app.templates.template_table import TemplateTable, TableColumn
from app.templates.template_map_view import MapViewTemplate
from app.templates.template_popup import PopupTemplate
from app.templates.template_statuswindow import StatusWindowTemplate
from app.templates.template_treeview import TreeviewTemplate
from app.config.config_colors import TYPE_CATEGORY_COLOR_FAMILIES, TYPE_CATEGORY_COLORS, DEFAULT_TYPE_COLOR
from app.config.config_slot import RIVER_GUID_FAMILIES, RIVER_GUID_ROLE
from app.functions.function_island_slots import (
    IslandSlotEditingMixin,
    estimate_nearby_height,
    object_records,
    remove_map_ids,
)
from app.functions.function_place_object import world_from_click


class SlotConfigurationTabMixin(IslandSlotEditingMixin):
    """Slot map and combined original/patched GUID configuration table."""

    def _init_slot_configuration_state(self):
        if getattr(self, "_slot_config_initialized", False):
            return
        self._slot_config_initialized = True
        self.slot_configuration_window = None
        self.slot_config2_window = None
        self.slot_configuration_table = None
        self.slot_config2_table = None
        self.slot_configuration_info_var = tk.StringVar(value="Load gamedata_original.xml to display slot objects.")
        self.slot_config2_info_var = tk.StringVar(value="Load mapname_original.xml to display slot objects.")
        self.slot_mass_original_guid_var = tk.StringVar()
        self.slot_mass_new_guid_var = tk.StringVar()
        self.slot2_mass_original_guid_var = tk.StringVar()
        self.slot2_mass_new_guid_var = tk.StringVar()
        self.slot_configuration_original_rows = []
        self.slot_configuration_edit_rows = []
        self.slot_config2_original_rows = []
        self.slot_config2_edit_rows = []
        self.slot_map_window = None
        self.slot_map_canvas = None
        self.slot_map_allow_dot_movement_var = tk.BooleanVar(value=False)
        self.slot_map_legend = None
        self.slot_map_bounds = None
        self.slot_map_points = []
        self.slot_map_screen_points = []
        self.slot_map_river_pairs = []
        self.slot_map_orientation_directions = {}
        self.slot_map_guid_colors = {}
        self.slot_map_guid_visible = {}
        self.slot_map_hover_point = None
        self.slot_map_after_id = None
        self.slot_map_pan_start = None
        self.slot_map_point_zoom = MapViewTemplate.DEFAULT_POINT_ZOOM
        self.slot_map_point_pan_x = 0.0
        self.slot_map_point_pan_y = 0.0
        self.slot_map_shared_zoom = MapViewTemplate.DEFAULT_SHARED_ZOOM
        self.slot_map_shared_pan_x = 0.0
        self.slot_map_shared_pan_y = 0.0
        self.slot_map_image_path = None
        self.slot_map_image_source = None
        self.slot_map_image_tk = None
        self.slot_map_image_cache = {}
        self.slot_map_hover_item = None
        self.slot_map_info_var = tk.StringVar(value="Positions from mapname_original.xml are displayed using X and Z.")
        self.slot_map_selection_var = tk.StringVar(value="Hover or click a point to display ObjectId, GUID and Position.")
        self.combined_slot_window = None
        self.combined_slot_records = []
        self.combined_slot_edit_rows = []
        self.combined_slot_filter = tk.StringVar()
        self.combined_slot_mass_guid_from = tk.StringVar()
        self.combined_slot_mass_guid_to = tk.StringVar()
        self.combined_slot_summary = None
        self.combined_slot_scroll = None
        self.combined_slot_records_by_id = {}
        self.combined_slot_dirty_ids = set()
        self.combined_slot_deleted_ids = set()
        self.combined_slot_game_tree = None
        self.combined_slot_map_tree = None
        self.combined_slot_game_nodes_by_id = {}
        self.combined_slot_map_nodes_by_id = {}
        self.combined_slot_game_target = None
        self.combined_slot_map_target = None
        self.combined_slot_page = 0
        self.combined_slot_page_size = 25
        self.combined_slot_page_var = tk.StringVar(value="Page 1 / 1")
        self.combined_slot_filtered_count = 0
        self.combined_slot_tree = None
        self.combined_slot_editor_id = tk.StringVar()
        self.combined_slot_editor_guid = tk.StringVar()
        self.combined_slot_editor_x = tk.StringVar()
        self.combined_slot_editor_y = tk.StringVar()
        self.combined_slot_editor_z = tk.StringVar()
        self.combined_slot_editor_source = tk.StringVar(value="Use Mapdata")

    def _build_slot_configuration_tab(self, tab):
        self._init_slot_configuration_state()
        tab.grid_columnconfigure(0, weight=1)
        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Slot Configuration", font=ctk.CTkFont(size=22, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="Show Slot Map", width=160, height=34, fg_color="#555555", hover_color="#666666", command=self._open_slot_map).grid(row=0, column=1, padx=(8, 0), sticky="e")
        box = ctk.CTkFrame(tab)
        box.grid(row=1, column=0, padx=20, pady=(5, 20), sticky="ew")
        box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box, text="Slot Editor", font=ctk.CTkFont(size=18, weight="bold"), anchor="w").grid(row=0, column=0, padx=18, pady=(16, 4), sticky="ew")
        ctk.CTkLabel(box, text="Links gamedata ID/guid with mapname ObjectId/ObjectGuid/Position. GUID changes are written to both files.", anchor="w", justify="left", wraplength=900).grid(row=1, column=0, padx=18, pady=(0, 14), sticky="ew")
        ctk.CTkButton(box, text="Open Slot Editor", width=230, height=40, font=ctk.CTkFont(weight="bold"), command=self._open_combined_slot_editor).grid(row=2, column=0, padx=18, pady=(0, 18), sticky="w")

    def _refresh_slot_configuration_from_files(self):
        self._init_slot_configuration_state()
        slot_window = getattr(self, "slot_configuration_window", None)
        if slot_window is not None and slot_window.winfo_exists():
            self._load_slot_configuration_objects()
        slot2_window = getattr(self, "slot_config2_window", None)
        if slot2_window is not None and slot2_window.winfo_exists():
            self._load_slot_config2_objects()
        map_window = getattr(self, "slot_map_window", None)
        if map_window is not None and map_window.winfo_exists():
            if self._slot_map_load_points(preserve_view=True):
                self._slot_map_rebuild_legend()
                self._slot_map_schedule_redraw()

    def _refresh_open_slot_map(self):
        self._init_slot_configuration_state()
        window = getattr(self, "slot_map_window", None)
        if window is not None and window.winfo_exists():
            if self._slot_map_load_points(preserve_view=True):
                self._slot_map_rebuild_legend()
                self._slot_map_schedule_redraw()

    def _preview_slot_map_from_config2_edits(self):
        self._init_slot_configuration_state()
        window = getattr(self, "slot_map_window", None)
        if window is None or not window.winfo_exists():
            return
        edits = {idv.get().strip(): (guidv.get().strip(), posv.get().strip()) for idv, guidv, posv in self.slot_config2_edit_rows}
        updated = []
        for point in self.slot_map_points:
            if len(point) == 7:
                oid, guid, x, y, z, pos, issue = point
            elif len(point) == 6:
                oid, guid, x, y, z, pos = point
                issue = None
            else:
                print(
                    f"[Slot Map] Invalid slot record skipped: "
                    f"{point!r} ({len(point)} values)"
                )
                continue
            new_guid, new_pos = edits.get(oid, (guid, pos))
            parsed = self._slot_map_parse_position(new_pos)
            if parsed is None:
                parsed = (x, y, z)
            nx, ny, nz = parsed
            updated.append((oid, new_guid, nx, ny, nz, new_pos, issue))
        self.slot_map_points = updated
        guids = {p[1] for p in updated}
        self.slot_map_guid_visible = {g: self.slot_map_guid_visible.get(g, True) for g in guids}
        current_colors = getattr(self, "slot_map_guid_colors", {})
        self.slot_map_guid_colors = {g: c for g, c in current_colors.items() if g in guids}
        for guid in guids:
            if guid not in self.slot_map_guid_colors:
                self.slot_map_guid_colors[guid] = self._slot_map_random_family_color(self.slot_map_guid_colors.values())
        self._slot_map_rebuild_legend()
        self._slot_map_schedule_redraw()

    def _open_slot_config_1(self):
        self._open_combined_slot_editor()

    def _open_slot_config_2(self):
        self._open_combined_slot_editor()

    def _open_slot_editor_popup(self, mode):
        is_map = mode == 2
        attr = "slot_config2_window" if is_map else "slot_configuration_window"
        window = getattr(self, attr, None)
        if window is not None and window.winfo_exists():
            window.deiconify(); PopupTemplate.safe_activate(window)
            (self._load_slot_config2_objects if is_map else self._load_slot_configuration_objects)()
            return
        title = "Slot Config 2" if is_map else "Slot Config 1"
        built = PopupTemplate.create_window(
            self, title=title, heading=title,
            close_command=lambda: self._close_slot_editor_popup(mode),
        )
        window=built["window"]; head=built["header"]; setattr(self, attr, window)
        window.grid_columnconfigure(0, weight=1); window.grid_rowconfigure(3, weight=1)
        info_var=self.slot_config2_info_var if is_map else self.slot_configuration_info_var
        ctk.CTkLabel(head,textvariable=info_var,text_color=PopupTemplate.SECONDARY_TEXT_COLOR).grid(row=1,column=0,pady=(3,0),sticky="w")
        if built["maximize_button"] is not None:
            built["maximize_button"].grid_configure(row=0,column=2,rowspan=2,padx=(8,0))
        ctk.CTkButton(head,text="Reload",width=110,command=self._load_slot_config2_objects if is_map else self._load_slot_configuration_objects).grid(row=0,column=1,rowspan=2,sticky="e")
        mass=ctk.CTkFrame(window); mass.grid(row=1,column=0,padx=18,pady=(0,10),sticky="ew"); mass.grid_columnconfigure(1,weight=1); mass.grid_columnconfigure(3,weight=1)
        ctk.CTkLabel(mass,text="Mass Replace",font=ctk.CTkFont(weight="bold")).grid(row=0,column=0,columnspan=5,padx=12,pady=(10,6),sticky="w")
        old_var=self.slot2_mass_original_guid_var if is_map else self.slot_mass_original_guid_var; new_var=self.slot2_mass_new_guid_var if is_map else self.slot_mass_new_guid_var
        ctk.CTkLabel(mass,text="Original GUID:").grid(row=1,column=0,padx=(12,6),pady=(0,10),sticky="w"); ctk.CTkEntry(mass,textvariable=old_var).grid(row=1,column=1,padx=(0,12),pady=(0,10),sticky="ew")
        ctk.CTkLabel(mass,text="New GUID:").grid(row=1,column=2,padx=(0,6),pady=(0,10),sticky="w"); ctk.CTkEntry(mass,textvariable=new_var).grid(row=1,column=3,padx=(0,12),pady=(0,10),sticky="ew")
        ctk.CTkButton(mass,text="Replace All",width=120,command=self._mass_replace_slot_config2_guids if is_map else self._mass_replace_slot_configuration_guids).grid(row=1,column=4,padx=(0,12),pady=(0,10))
        if is_map:
            columns=(TableColumn("id","ObjectId",width=240),TableColumn("guid","ObjectGuid",width=180),TableColumn("position","Position",weight=1))
            table=TemplateTable(window,columns,row_builder=self._slot_config2_combined_row,fg_color=TemplateTable.TABLE_BACKGROUND); self.slot_config2_table=table
            help_text="Original ObjectGuid / Position are shown above; patched values are editable below."
        else:
            columns=(TableColumn("id","ID",width=220),TableColumn("guid","GUID",weight=1))
            table=TemplateTable(window,columns,row_builder=self._slot_configuration_combined_row,fg_color=TemplateTable.TABLE_BACKGROUND); self.slot_configuration_table=table
            help_text="Original GUID is shown above; patched GUID is editable below."
        ctk.CTkLabel(window,text=help_text,text_color="#e0a84f").grid(row=2,column=0,padx=18,pady=(0,8),sticky="w")
        table.grid(row=3,column=0,padx=18,pady=(0,10),sticky="nsew")
        actions=ctk.CTkFrame(window,fg_color="transparent"); actions.grid(row=4,column=0,padx=18,pady=(0,16),sticky="ew"); actions.grid_columnconfigure(0,weight=1)
        ctk.CTkButton(actions,text="Reset",width=120,height=38,fg_color="#555555",hover_color="#666666",command=self._reset_slot_config2 if is_map else self._reset_slot_configuration).grid(row=0,column=1,padx=(0,8),sticky="e")
        ctk.CTkButton(actions,text="Save",width=150,height=38,font=ctk.CTkFont(weight="bold"),command=self._save_slot_config2 if is_map else self._save_slot_configuration).grid(row=0,column=2,sticky="e")
        (self._load_slot_config2_objects if is_map else self._load_slot_configuration_objects)()

    def _close_slot_editor_popup(self, mode):
        attr="slot_config2_window" if mode==2 else "slot_configuration_window"; table_attr="slot_config2_table" if mode==2 else "slot_configuration_table"
        window=getattr(self,attr,None)
        if window is not None and window.winfo_exists(): window.destroy()
        setattr(self,attr,None); setattr(self,table_attr,None)

    @staticmethod
    def _slot_config2_combined_row(row, data, _row_index):
        row.configure(height=TemplateTable.COMBINED_ROW_HEIGHT); row.grid_columnconfigure(2,weight=1)
        ctk.CTkLabel(row,textvariable=data["id"],width=240,anchor="w").grid(row=0,column=0,rowspan=2,padx=5,pady=5,sticky="nsw")
        ctk.CTkEntry(row,textvariable=data["original_guid"],height=TemplateTable.ENTRY_HEIGHT,font=ctk.CTkFont(size=TemplateTable.ENTRY_FONT_SIZE),text_color=TemplateTable.DISABLED_TEXT_COLOR,state="disabled",border_width=0,fg_color=TemplateTable.DISABLED_FG_COLOR).grid(row=0,column=1,padx=5,pady=(5,2),sticky="ew")
        ctk.CTkEntry(row,textvariable=data["patched_guid"],height=TemplateTable.ENTRY_HEIGHT,font=ctk.CTkFont(size=TemplateTable.ENTRY_FONT_SIZE),text_color=TemplateTable.EDITABLE_TEXT_COLOR,fg_color=TemplateTable.EDITABLE_FG_COLOR,border_width=1).grid(row=1,column=1,padx=5,pady=(2,5),sticky="ew")
        ctk.CTkEntry(row,textvariable=data["original_position"],height=TemplateTable.ENTRY_HEIGHT,font=ctk.CTkFont(size=TemplateTable.ENTRY_FONT_SIZE),text_color=TemplateTable.DISABLED_TEXT_COLOR,state="disabled",border_width=0,fg_color=TemplateTable.DISABLED_FG_COLOR).grid(row=0,column=2,padx=5,pady=(5,2),sticky="ew")
        ctk.CTkEntry(row,textvariable=data["patched_position"],height=TemplateTable.ENTRY_HEIGHT,font=ctk.CTkFont(size=TemplateTable.ENTRY_FONT_SIZE),text_color=TemplateTable.EDITABLE_TEXT_COLOR,fg_color=TemplateTable.EDITABLE_FG_COLOR,border_width=1).grid(row=1,column=2,padx=5,pady=(2,5),sticky="ew")

    @staticmethod
    def _collect_mapname_slot_objects(root):
        rows=[]
        for parent in root.iter():
            values={}
            for child in list(parent):
                if not isinstance(child.tag,str): continue
                tag=child.tag.rsplit("}",1)[-1]
                if tag in {"ObjectId","ObjectGuid","Position"}: values[tag]=(child.text or "").strip()
            if all(values.get(k) for k in ("ObjectId","ObjectGuid","Position")):
                rows.append((values["ObjectId"],values["ObjectGuid"],values["Position"]))
        return rows

    def _load_slot_config2_objects(self, original_only=False):
        original=Path(self.mapname_file_var.get().strip())
        if not original.is_file(): self.slot_config2_info_var.set("No mapname_original.xml loaded."); self._clear_slot_config2(); return False
        try: original_rows=self._collect_mapname_slot_objects(self._slot_parse_xml(original)[0].getroot())
        except (ET.ParseError,OSError,UnicodeError) as exc: self.slot_config2_info_var.set(f"Could not read mapname_original.xml: {exc}"); return False
        source_rows=original_rows
        patched=original.with_name(original.name.replace("_original.xml","_patched.xml") if original.name.endswith("_original.xml") else f"{original.stem}_patched.xml")
        if not original_only and patched.is_file():
            try:
                candidate=self._collect_mapname_slot_objects(self._slot_parse_xml(patched)[0].getroot())
                if len(candidate)==len(original_rows): source_rows=candidate
            except (ET.ParseError,OSError,UnicodeError): pass
        self.slot_config2_original_rows=list(original_rows); self.slot_config2_edit_rows=[]; table_rows=[]
        for (oid,oguid,opos),(_pid,pguid,ppos) in zip(original_rows,source_rows):
            idv=tk.StringVar(value=oid); og=tk.StringVar(value=oguid); pg=tk.StringVar(value=pguid); op=tk.StringVar(value=opos); pp=tk.StringVar(value=ppos)
            self.slot_config2_edit_rows.append((idv,pg,pp)); table_rows.append({"id":idv,"original_guid":og,"patched_guid":pg,"original_position":op,"patched_position":pp})
        table=getattr(self,"slot_config2_table",None)
        if table is not None and table.winfo_exists(): table.set_rows(table_rows); table.scroll_to_top()
        self.slot_config2_info_var.set(f"Objects: {len(original_rows)} ObjectId/ObjectGuid/Position entries")
        return True

    def _clear_slot_config2(self):
        table=getattr(self,"slot_config2_table",None)
        if table is not None and table.winfo_exists(): table.clear()
        self.slot_config2_original_rows=[]; self.slot_config2_edit_rows=[]

    def _mass_replace_slot_config2_guids(self):
        old=self.slot2_mass_original_guid_var.get().strip(); new=self.slot2_mass_new_guid_var.get().strip()
        if not old or not new: messagebox.showerror("Mass Replace","Please enter both Original GUID and New GUID."); return
        count=0
        for _id,guid,_pos in self.slot_config2_edit_rows:
            if guid.get().strip()==old: guid.set(new); count+=1
        self._preview_slot_map_from_config2_edits()
        messagebox.showinfo("Mass Replace",f"Replaced entries: {count}")

    def _reset_slot_config2(self):
        self.slot2_mass_original_guid_var.set(""); self.slot2_mass_new_guid_var.set(""); self._load_slot_config2_objects(original_only=True)
        self._preview_slot_map_from_config2_edits()
        self.status_var.set("Slot Config 2 reloaded from mapname_original.xml")

    def _save_slot_config2(self):
        original=Path(self.mapname_file_var.get().strip())
        if not original.is_file(): messagebox.showerror("Slot Config 2","Please load mapname_original.xml first."); return
        edits={idv.get().strip():(gv.get().strip(),pv.get().strip()) for idv,gv,pv in self.slot_config2_edit_rows}
        if any(not oid or not guid or not pos for oid,(guid,pos) in edits.items()): messagebox.showerror("Slot Config 2","ObjectId, ObjectGuid and Position must not be empty."); return
        try:
            tree=self._slot_parse_xml(original)[0]; changed_guid=0; changed_pos=0
            for parent in tree.getroot().iter():
                children=list(parent); idn=next((c for c in children if isinstance(c.tag,str) and c.tag.rsplit("}",1)[-1]=="ObjectId"),None); gn=next((c for c in children if isinstance(c.tag,str) and c.tag.rsplit("}",1)[-1]=="ObjectGuid"),None); pn=next((c for c in children if isinstance(c.tag,str) and c.tag.rsplit("}",1)[-1]=="Position"),None)
                oid=(idn.text or "").strip() if idn is not None else ""
                if oid in edits and gn is not None and pn is not None:
                    guid,pos=edits[oid]
                    if (gn.text or "").strip()!=guid: gn.text=guid; changed_guid+=1
                    if (pn.text or "").strip()!=pos: pn.text=pos; changed_pos+=1
            target=original.with_name(original.name.replace("_original.xml","_patched.xml") if original.name.endswith("_original.xml") else f"{original.stem}_patched.xml")
            tree.write(target,encoding="utf-8",xml_declaration=False,short_empty_elements=True)
        except (OSError,ET.ParseError,UnicodeError) as exc: messagebox.showerror("Slot Config 2",f"Could not save mapname patched XML:\n{exc}"); return
        self._refresh_open_slot_map()
        self.status_var.set(f"Slot Config 2 saved: {changed_guid} GUID, {changed_pos} Position change(s)")
        messagebox.showinfo("Slot Config 2",f"Saved: {target.name}\n\nObjectGuid changes: {changed_guid}\nPosition changes: {changed_pos}")

    def _slot_parse_xml(self, path):
        parser = getattr(self, "_parse_xml_tolerant", None)
        if callable(parser):
            return parser(Path(path))
        return ET.parse(Path(path)), False, 0

    @staticmethod
    def _slot_collect_gamedata_objects(root):
        rows=[]
        for parent in root.iter():
            oid=guid=None
            for child in list(parent):
                if not isinstance(child.tag,str): continue
                tag=child.tag.rsplit("}",1)[-1].lower()
                if tag=="id": oid=(child.text or "").strip()
                elif tag=="guid": guid=(child.text or "").strip()
            if oid and guid: rows.append((oid,guid))
        return rows

    @staticmethod
    def _slot_map_parse_position(text):
        parts = (text or "").strip().replace(";", " ").split()
        if len(parts) < 3:
            return None
        try:
            return tuple(float(value.replace(",", ".")) for value in parts[:3])
        except ValueError:
            return None

    @staticmethod
    def _slot_map_random_family_color(used_colors):
        used = set(used_colors)
        families = {name: [c for c in colors if c] for name, colors in TYPE_CATEGORY_COLOR_FAMILIES.items()}
        max_rounds = max((len(colors) for colors in families.values()), default=0)
        for shade in range(max_rounds):
            available = [colors[shade] for colors in families.values() if shade < len(colors) and colors[shade] not in used]
            if available:
                return random.choice(available)
        palette = [c for c in TYPE_CATEGORY_COLORS if c]
        available = [c for c in palette if c not in used]
        return random.choice(available or palette) if palette else DEFAULT_TYPE_COLOR


    def _slot_map_load_points(self, preserve_view=False):
        try:
            bounds = MapViewTemplate.read_playable_area(
                self.gamedata_file_var.get().strip(), parser=self._parse_xml_tolerant)
        except (OSError, ET.ParseError, UnicodeError, ValueError) as exc:
            messagebox.showerror('Slot Map', f'PlayableArea could not be loaded:\n{exc}')
            return False
        self.slot_map_bounds = bounds
        path = Path(self.mapname_file_var.get().strip())
        if not path.is_file():
            messagebox.showerror("Slot Map", "Please load an existing mapname_original.xml file first.")
            return False
        source = path.with_name(path.name.replace("_original.xml", "_patched.xml") if path.name.endswith("_original.xml") else f"{path.stem}_patched.xml")
        if not source.is_file():
            source = path
        try:
            ram_map_tree = getattr(self, "_island_slot_ram_map_tree", None)
            root = (
                ram_map_tree.getroot()
                if ram_map_tree is not None
                else self._slot_parse_xml(source)[0].getroot()
            )
        except (ET.ParseError, OSError, UnicodeError) as exc:
            messagebox.showerror("Slot Map", f"Map XML could not be read:\n{exc}")
            return False
        map_entries = {}
        for parent in root.iter():
            values = {}
            for child in list(parent):
                if isinstance(child.tag, str):
                    tag = child.tag.rsplit("}", 1)[-1]
                    if tag in {"ObjectId", "ObjectGuid", "Position"}:
                        values[tag] = (child.text or "").strip()
            if not values.get("ObjectGuid") or not values.get("Position"):
                continue
            position = self._slot_map_parse_position(values["Position"])
            if position is None:
                continue
            oid = values.get("ObjectId", "-")
            map_entries[oid] = (values["ObjectGuid"], position, values["Position"])

        game_path = Path(self.gamedata_file_var.get().strip())
        game_source = game_path.with_name(
            game_path.name.replace("_original.xml", "_patched.xml")
            if game_path.name.endswith("_original.xml") else f"{game_path.stem}_patched.xml"
        )
        if not game_source.is_file():
            game_source = game_path
        try:
            ram_game_tree = getattr(self, "_island_slot_ram_game_tree", None)
            game_root = (
                ram_game_tree.getroot()
                if ram_game_tree is not None
                else self._slot_parse_xml(game_source)[0].getroot()
            )
            game_entries = {record["id"]: record for record in object_records(game_root)}
        except (ET.ParseError, OSError, UnicodeError) as exc:
            # Unsupported original content is preserved by _slot_parse_xml().
            # Only genuine XML structure errors reach this branch.
            messagebox.showerror(
                "Slot Map",
                f"Gamedata XML structure could not be read:\n{exc}",
                parent=getattr(self, "slot_map_window", None),
            )
            return False

        # Resolve logical river pairs once while loading. Rendering then uses
        # only the two ObjectIds, so preview moves update connecting lines without
        # reparsing either XML file.
        river_pairs = []
        paired_ids = set()
        game_records = list(game_entries.values())
        for family_name, family in RIVER_GUID_FAMILIES.items():
            primaries = [r for r in game_records if r["guid"] == family["primary"]]
            workareas = [r for r in game_records if r["guid"] == family["workarea"]]
            if family.get("folder_pairing"):
                for primary in primaries:
                    matches = [
                        work for work in workareas
                        if primary["folder"] and work["folder"] == primary["folder"]
                    ]
                    if len(matches) == 1:
                        pair = (primary["id"], matches[0]["id"], family_name)
                        if pair[0] in map_entries and pair[1] in map_entries:
                            river_pairs.append(pair)
                            paired_ids.update(pair[:2])
            else:
                # Custom templates do not always provide a usable folder key.
                # Use matching non-empty folders first; a global fallback is safe
                # only when exactly one unmatched primary/work-area remains.
                for primary in primaries:
                    matches = [
                        work for work in workareas
                        if primary["folder"] and work["folder"] == primary["folder"]
                        and work["id"] not in paired_ids
                    ]
                    if len(matches) == 1 and primary["id"] not in paired_ids:
                        pair = (primary["id"], matches[0]["id"], family_name)
                        if pair[0] in map_entries and pair[1] in map_entries:
                            river_pairs.append(pair)
                            paired_ids.update(pair[:2])
                remaining_primary = [r for r in primaries if r["id"] not in paired_ids]
                remaining_work = [r for r in workareas if r["id"] not in paired_ids]
                if len(remaining_primary) == len(remaining_work) == 1:
                    pair = (remaining_primary[0]["id"], remaining_work[0]["id"], family_name)
                    if pair[0] in map_entries and pair[1] in map_entries:
                        river_pairs.append(pair)
                        paired_ids.update(pair[:2])
        self.slot_map_river_pairs = river_pairs

        # Single-point River and Mine slots use the scalar Direction field.
        # Keep it by ObjectId so the Slot Map can render a facing arrow without
        # changing the existing point tuple.
        orientation_directions = {}
        directional_guids = {"117741", "1000029", "614", "116037"}
        for record in game_records:
            if record["guid"] not in directional_guids:
                continue
            direction_text = next((
                (child.text or "").strip()
                for child in record["node"].iter()
                if child.tag.rsplit("}", 1)[-1] == "Direction" and (child.text or "").strip()
            ), "")
            try:
                orientation_directions[record["id"]] = float(direction_text.replace(",", "."))
            except ValueError:
                continue
        self.slot_map_orientation_directions = orientation_directions

        # Preserve the original Slot Map object set: only MapName entries are
        # displayed. Gamedata is used exclusively to validate the existing dots;
        # unrelated Gamedata objects must never create additional map points.
        points = []
        for oid, map_entry in map_entries.items():
            guid, position, position_text = map_entry
            x, y, z = position
            issue = None if oid in game_entries else "Missing Gamedata entry"
            points.append((oid, guid, x, y, z, position_text, issue))
        self.slot_map_points = points
        guids = {p[1] for p in points}
        current_colors = getattr(self, "slot_map_guid_colors", {})
        self.slot_map_guid_colors = {g: c for g, c in current_colors.items() if g in guids}
        current_visible = getattr(self, "slot_map_guid_visible", {})
        self.slot_map_guid_visible = {g: v for g, v in current_visible.items() if g in guids}
        for guid in sorted(guids, key=lambda v: (len(v), v)):
            if guid not in self.slot_map_guid_colors:
                self.slot_map_guid_colors[guid] = self._slot_map_random_family_color(self.slot_map_guid_colors.values())
            self.slot_map_guid_visible.setdefault(guid, True)
        if not preserve_view:
            self.slot_map_point_zoom = MapViewTemplate.DEFAULT_POINT_ZOOM
            self.slot_map_point_pan_x = self.slot_map_point_pan_y = 0.0
            self.slot_map_shared_zoom = MapViewTemplate.DEFAULT_SHARED_ZOOM
            self.slot_map_shared_pan_x = self.slot_map_shared_pan_y = 0.0
        self.slot_map_hover_point = None
        self.slot_map_selection_var.set("Hover or click a point to display ObjectId, GUID and Position.")
        self._slot_map_load_background(path)
        return True

    def _slot_map_load_background(self, mapname_path):
        self.slot_map_image_tk = None
        roots = [Path(mapname_path).parent]
        value = self.gamedata_file_var.get().strip()
        if value:
            gamedata = Path(value)
            if gamedata.is_file():
                roots.extend((gamedata.parent, gamedata.parent.parent))
        self.slot_map_image_source, self.slot_map_image_path = MapViewTemplate.load_background(
            roots, direct_first=False)
        guid_count = len({p[1] for p in self.slot_map_points})
        image_name = self.slot_map_image_path.name if self.slot_map_image_path else "not found"
        self.slot_map_info_var.set(f"{len(self.slot_map_points)} positions | {guid_count} GUIDs | Background: {image_name} | X/Z | PlayableArea: {self.slot_map_bounds}")

    def _open_slot_map(self):
        status = self._show_object_operation_status("Loading Slot Map...")
        try:
            self._open_slot_map_impl()
            self.update_idletasks()
            window = getattr(self, "slot_map_window", None)
            if window is not None and window.winfo_exists():
                window.update_idletasks()
                window.lift()
        finally:
            self._hide_object_operation_status(status)

    def _open_slot_map_impl(self):
        self._init_slot_configuration_state()
        if not self._slot_map_load_points():
            return
        if self.slot_map_window is not None and self.slot_map_window.winfo_exists():
            self.slot_map_window.deiconify(); PopupTemplate.safe_activate(self.slot_map_window)
            self._slot_map_rebuild_legend(); self._slot_map_schedule_redraw(); return
        built = MapViewTemplate.build_map_window(
            self, title="Slot Map", heading="Slot Map",
            slot_edit_help=True,
            info_variable=self.slot_map_info_var,
            selection_variable=self.slot_map_selection_var,
            close_command=self._close_slot_map,
            redraw_command=self._slot_map_schedule_redraw,
            legend_builder=lambda: None,
            maximize_button_attribute="slot_map_maximize_button",
        )
        self.slot_map_window = built["window"]
        self.slot_map_canvas = built["canvas"]
        self.slot_map_legend = built["legend"]
        header = built["header"]
        maximize = built["maximize_button"]
        if maximize is not None:
            maximize.grid_configure(column=6, padx=(8, 0))
        self.slot_map_allow_dot_movement_var.set(False)
        MapViewTemplate.build_dot_movement_checkbox(
            header, self.slot_map_allow_dot_movement_var,
            column=2, command=self._slot_map_dot_movement_changed,
            canvas=self.slot_map_canvas,
        )
        ctk.CTkButton(header, text="Save", width=90, command=self._island_slot_save).grid(row=0, column=3, padx=(8, 0), sticky="e")
        ctk.CTkButton(header, text="Reload", width=90, command=self._slot_map_reload_rd3d).grid(row=0, column=4, padx=(8, 0), sticky="e")
        ctk.CTkButton(header, text="Reset", width=90, fg_color="#B33939", hover_color="#8F2D2D", command=self._island_slot_reset).grid(row=0, column=5, padx=(8, 0), sticky="e")
        self._island_slot_capture_snapshot()
        self._slot_map_bind_canvas(); self._slot_map_rebuild_legend(); self._slot_map_schedule_redraw()
        self.slot_map_selection_var.set(
            "Right click: open menu to add or remove slots | Middle drag: pan"
        )

    def _slot_map_reload_rd3d(self):
        """Reload RD3D asynchronously and close status only in completion callback."""
        if getattr(self, "_slot_map_reload_running", False):
            return
        configured = Path(self.rd3d_file_var.get().strip())
        if not configured.is_file():
            messagebox.showerror(
                "Slot Map Reload", "Load rd3d_original.xml first.",
                parent=self.slot_map_window,
            )
            return
        original = configured
        if configured.name.endswith("_patched.xml"):
            candidate = configured.with_name(
                configured.name[:-len("_patched.xml")] + "_original.xml"
            )
            if candidate.is_file():
                original = candidate
        patched = original.with_name(
            original.name[:-len("_original.xml")] + "_patched.xml"
            if original.name.endswith("_original.xml")
            else original.stem + "_patched.xml"
        )
        source = patched if patched.is_file() else original
        self._slot_map_reload_running = True
        reload_status = StatusWindowTemplate.create(
            self.slot_map_window, text="Reloading...", title="Status", heading="Status",
            modal=False, topmost=True,
        )

        def worker():
            try:
                # Parse/validate the selected on-disk source in the worker. The
                # normal shared RD3D cache is rebuilt from the same source.
                self._parse_xml_tolerant(source)
                from app.ui.tabs.ui_tab_object_configuration import Rd3dXmlRamCache
                cache = Rd3dXmlRamCache(original).load(lambda _done, _total: None)
                result = (cache, None)
            except (OSError, ET.ParseError, UnicodeError, ValueError, RuntimeError) as exc:
                result = (None, str(exc))
            self.after(0, lambda: self._slot_map_reload_complete(
                reload_status, source, result[0], result[1]
            ))

        threading.Thread(
            target=worker, daemon=True, name="SlotMapRD3DReload"
        ).start()

    def _slot_map_reload_complete(self, reload_status, source, cache, error):
        """Apply asynchronous RD3D result and close popup on the Tk thread."""
        try:
            if error is not None:
                messagebox.showerror(
                    "Slot Map Reload", error, parent=self.slot_map_window
                )
                return
            self.rd3d_ram_cache = cache
            self.object_configuration_table1_rows = [
                (index, old, tk.StringVar(value=current), count)
                for index, (old, current, count) in enumerate(
                    zip(cache.original_values, cache.values, cache.usage)
                )
            ]
            self._slot_map_rd3d_reload_source = source
            self._refresh_open_slot_map()
            self.status_var.set(f"Slot Map RD3D reloaded from {source.name}.")
        finally:
            self._slot_map_reload_running = False
            StatusWindowTemplate.close(reload_status)


    def _close_slot_map(self):
        window = self.slot_map_window
        if getattr(self, "_island_slot_save_running", False):
            messagebox.showwarning(
                "Slot Map",
                "Slot Map is currently saving. Wait for the save to finish before closing.",
                parent=window,
            )
            return False
        if self._island_slot_has_unsaved_changes():
            if not messagebox.askyesno(
                "Discard unsaved Slot Map changes?",
                "The Slot Map contains changes that have not been saved.\n\n"
                "Closing the Slot Map will discard all unsaved Add, Remove, Change, "
                "Rotate and Dot Movement changes from RAM.\n\n"
                "Close and discard the unsaved changes?",
                parent=window,
                default="no",
            ):
                return False
        # Closing the popup is a hard working-copy boundary. Nothing from the
        # current RAM edit session survives into the next Slot Map popup.
        self._island_slot_discard_working_copy()
        self.island_slot_lasso_points = []
        self.island_slot_lasso_world_points = []
        self.island_slot_selection_start = None
        self.island_slot_selection_world_bounds = None
        self.island_slot_selected_ids = set()
        self.island_slot_selection_rect = None
        canvas = self.slot_map_canvas
        if canvas is not None:
            canvas.delete("slot_lasso")
            canvas.delete("slot_selection")
            canvas.delete("slot_selection_area")
            MapViewTemplate.dot_drag_cancel(canvas)
            canvas._map_dot_history = []
        if self.slot_map_after_id is not None:
            try: self.after_cancel(self.slot_map_after_id)
            except (ValueError, tk.TclError): pass
        if window is not None and window.winfo_exists():
            PopupTemplate.close_window(window)
        self.slot_map_window = self.slot_map_canvas = self.slot_map_legend = None
        self.slot_map_after_id = None
        self.slot_map_image_tk = None
        self.slot_map_image_source = None
        self.slot_map_image_cache = {}
        self.slot_map_points = []
        self.slot_map_screen_points = []
        self.slot_map_river_pairs = []
        self.slot_map_orientation_directions = {}
        self.slot_map_hover_point = None
        self.status_var.set("Slot Map closed; RAM working copy cleared.")
        return True

    def _slot_map_bind_canvas(self):
        # Initialize selection state before MapViewTemplate can dispatch any
        # right-click or Shift-selection event.
        self._island_slot_init()
        MapViewTemplate.bind_map_mouse(
            self.slot_map_canvas,
            configure=self._slot_map_schedule_redraw,
            motion=self._slot_map_motion,
            leave=self._slot_map_leave,
            left_start=self._slot_map_drag_start,
            left_move=self._slot_map_drag_motion,
            left_end=self._slot_map_drag_end,
            selection_start=self._island_slot_select_start,
            selection_move=self._island_slot_select_move,
            selection_end=self._island_slot_select_end,
            lasso_point=self._island_slot_lasso_point,
            wheel=self._slot_map_wheel,
            context=self._island_slot_right_click,
            pan_start=self._slot_map_pan_start_event,
            pan_move=self._slot_map_pan_move,
            pan_end=self._slot_map_pan_end,
            redraw=self._slot_map_schedule_redraw,
            owner=self.slot_map_window,
            escape=self._island_slot_selection_clear,
        )

    def _slot_map_rebuild_legend(self):
        legend = self.slot_map_legend
        if legend is None or not legend.winfo_exists(): return
        for widget in legend.winfo_children(): widget.destroy()
        counts = {}
        for point in self.slot_map_points: counts[point[1]] = counts.get(point[1], 0) + 1
        for index, guid in enumerate(sorted(counts, key=lambda v: (len(v), v))):
            visible = self.slot_map_guid_visible.get(guid, True); color = self.slot_map_guid_colors[guid]
            MapViewTemplate.build_legend_button(
                legend, text=f"{guid} ({counts[guid]})", color=color, visible=visible,
                command=lambda value=guid: self._slot_map_toggle_guid(value),
                row=index // MapViewTemplate.LEGEND_COLUMNS,
                column=index % MapViewTemplate.LEGEND_COLUMNS,
            )

    def _slot_map_toggle_guid(self, guid):
        self.slot_map_guid_visible[guid] = not self.slot_map_guid_visible.get(guid, True)
        if not self.slot_map_guid_visible[guid]:
            hidden_ids = {point[0] for point in self.slot_map_points if point[1] == guid}
            self.island_slot_selected_ids.difference_update(hidden_ids)
        self._slot_map_rebuild_legend(); self._slot_map_schedule_redraw()

    @staticmethod
    def _slot_map_ctrl_pressed(event): return bool(getattr(event, "state", 0) & 0x0004)

    def _slot_map_wheel(self, event):
        (
            self.slot_map_shared_zoom,
            self.slot_map_shared_pan_x,
            self.slot_map_shared_pan_y,
        ) = MapViewTemplate.handle_focus_zoom_event(
            self.slot_map_canvas,
            self.slot_map_bounds,
            self.slot_map_shared_zoom,
            self.slot_map_shared_pan_x,
            self.slot_map_shared_pan_y,
            event,
            self._slot_map_schedule_redraw,
        )
        return "break"

    def _slot_map_pan_start_event(self, event):
        self.slot_map_pan_start = MapViewTemplate.begin_pan(
            event, self.slot_map_shared_pan_x, self.slot_map_shared_pan_y)
        self.slot_map_canvas.configure(cursor="fleur")
        return "break"

    def _slot_map_pan_move(self, event):
        position = MapViewTemplate.move_pan(self.slot_map_pan_start, event)
        if position is not None:
            old_x, old_y = self.slot_map_shared_pan_x, self.slot_map_shared_pan_y
            self.slot_map_shared_pan_x, self.slot_map_shared_pan_y = position
            dx, dy = position[0] - old_x, position[1] - old_y
            MapViewTemplate.move_pan_background(self.slot_map_canvas, dx, dy)
        return "break"

    def _slot_map_pan_end(self, _event):
        self.slot_map_pan_start = None
        if self.slot_map_canvas is not None:
            self.slot_map_canvas.configure(cursor="crosshair")
        return "break"

    def _slot_map_schedule_redraw(self, _event=None):
        if self.slot_map_canvas is None or not self.slot_map_canvas.winfo_exists(): return
        if self.slot_map_after_id is not None:
            return
        self.slot_map_after_id = self.after(MapViewTemplate.REDRAW_DELAY_MS, self._slot_map_draw)

    def _slot_map_draw(self):
        self.slot_map_screen_points = []
        self.slot_map_after_id = None; canvas = self.slot_map_canvas
        if canvas is None or not canvas.winfo_exists(): return
        canvas.delete("all"); width, height = max(canvas.winfo_width(), 200), max(canvas.winfo_height(), 200)
        no_positions = not self.slot_map_points
        min_x, max_x, min_z, max_z = self.slot_map_bounds
        span_x, span_z = max_x-min_x, max_z-min_z; margin = MapViewTemplate.MAP_MARGIN
        scale = min((width-2*margin)/span_x, (height-2*margin)/span_z)
        image_w, image_h = span_x*scale*self.slot_map_shared_zoom, span_z*scale*self.slot_map_shared_zoom
        image_x, image_y = (width-image_w)/2+self.slot_map_shared_pan_x, (height-image_h)/2+self.slot_map_shared_pan_y
        source = self.slot_map_image_source
        if source is not None:
            self.slot_map_image_tk, visible_x, visible_y = MapViewTemplate.cached_viewport_photo(
                source, image_x, image_y, image_w, image_h,
                width, height, self.slot_map_image_cache,
            )
            if self.slot_map_image_tk is not None:
                canvas.create_image(
                    visible_x, visible_y, image=self.slot_map_image_tk,
                    anchor="nw", tags=("map_content", "map_background"),
                )
            canvas.create_rectangle(
                image_x, image_y, image_x + image_w, image_y + image_h,
                outline=MapViewTemplate.BACKGROUND_BORDER_COLOR,
                width=MapViewTemplate.BACKGROUND_BORDER_WIDTH,
                tags=("map_content", "map_background"),
            )
        else:
            canvas.create_rectangle(image_x,image_y,image_x+image_w,image_y+image_h,outline=MapViewTemplate.BACKGROUND_BORDER_COLOR,width=MapViewTemplate.BACKGROUND_BORDER_WIDTH,tags=("map_content", "map_background"))
        if no_positions:
            canvas.create_text(
                width / 2, height / 2, text="No Position found.",
                fill=MapViewTemplate.EMPTY_TEXT_COLOR, tags=("map_content", "empty_text"),
            )
        zoom=1.0; cx,cy=image_x+image_w/2,image_y+image_h/2
        screen=[]
        visible_points=[]
        for point in self.slot_map_points:
            if len(point) == 7:
                oid, guid, x, y, z, pos, issue = point
            elif len(point) == 6:
                oid, guid, x, y, z, pos = point
                issue = None
            else:
                print(
                    f"[Slot Map] Invalid slot record skipped: "
                    f"{point!r} ({len(point)} values)"
                )
                continue
            if not self.slot_map_guid_visible.get(guid,True):
                continue
            bx=image_x+((x-min_x)/span_x)*image_w; by=image_y+((max_z-z)/span_z)*image_h
            px=cx+(bx-cx)*zoom+0.0; py=cy+(by-cy)*zoom+0.0
            visible_points.append((px,py,oid,guid,x,y,z,pos,issue))

        screen_by_id = {point[2]: point for point in visible_points}
        river_orientation_vectors = []
        for primary_id, workarea_id, _family_name in getattr(self, "slot_map_river_pairs", []):
            primary = screen_by_id.get(primary_id)
            workarea = screen_by_id.get(workarea_id)
            if primary is None or workarea is None:
                continue
            line_color = self.slot_map_guid_colors.get(primary[3], "#4da3ff")
            canvas.create_line(
                primary[0], primary[1], workarea[0], workarea[1],
                fill=line_color, width=3, dash=(7, 4),
                tags=("map_content", "river_pair_line"),
            )
            dx, dy = workarea[0] - primary[0], workarea[1] - primary[1]
            length = math.hypot(dx, dy)
            if length > 0.001:
                river_orientation_vectors.append((primary, dx / length, dy / length, line_color))

        # Show the facing direction at single-point River and Mine slots.
        # Direction is in radians; +X is right and +Z is up on the Slot Map.
        orientation_line_length = 30
        virtual_orientation_guids = {"117741", "1000029", "614", "116037"}
        paired_primary_ids = {
            primary_id
            for primary_id, _workarea_id, _family_name
            in getattr(self, "slot_map_river_pairs", [])
        }
        for point in visible_points:
            px, py, oid, guid = point[:4]
            if guid not in virtual_orientation_guids:
                continue
            if guid == "117741" and oid in paired_primary_ids:
                continue
            direction = getattr(self, "slot_map_orientation_directions", {}).get(oid)
            if direction is None:
                continue
            # Direction is stored as menu angle + 90 degrees when a directional
            # River/Mine slot is added. Convert it back to the menu-facing angle
            # so the Slot Map arrow matches Add > Riverslot exactly:
            # right=0, up=90, left=180, down=-90.
            menu_angle = direction - (math.pi / 2.0)
            dir_x = math.cos(menu_angle)
            # World +Z maps upward, therefore its canvas delta is negative Y.
            dir_y = -math.sin(menu_angle)
            if guid in {"1000029", "614", "116037"}:
                # MineSlot visual only: rotate the displayed canvas arrow 90 deg CCW.
                # RiverSlot 117741 is deliberately untouched.
                dir_x, dir_y = dir_y, -dir_x
            virtual_workarea_x = px + dir_x * orientation_line_length
            virtual_workarea_y = py + dir_y * orientation_line_length
            line_color = self.slot_map_guid_colors.get(guid, "#c68a52")
            canvas.create_line(
                px, py, virtual_workarea_x, virtual_workarea_y,
                fill=line_color, width=3, arrow=tk.LAST, arrowshape=(8, 10, 4),
                tags=("map_content", "virtual_slot_orientation_line"),
            )

        # River Slot arrows use the actual primary -> work-area pair direction.
        # This is the same fixed-length visual orientation marker used by river test.
        for primary, dir_x, dir_y, line_color in river_orientation_vectors:
            px, py = primary[0], primary[1]
            canvas.create_line(
                px, py,
                px + dir_x * orientation_line_length,
                py + dir_y * orientation_line_length,
                fill=line_color, width=3, arrow=tk.LAST, arrowshape=(8, 10, 4),
                tags=("map_content", "river_orientation_line"),
            )

        # Dots are drawn after helper lines so every endpoint remains selectable.
        for point in visible_points:
            px,py,oid,guid,x,y,z,pos,issue = point
            dot_id = MapViewTemplate.draw_dot(
                canvas, px, py, self.slot_map_guid_colors[guid],
                warning=issue is not None,
            )
            if dot_id is not None:
                screen.append(point)
        self.slot_map_screen_points=screen
        self.slot_map_hover_item = MapViewTemplate.create_hover_marker(canvas)
        if self.slot_map_hover_point is not None:
            hovered = next((point for point in screen if point[2:7] == self.slot_map_hover_point), None)
            color = self.slot_map_guid_colors.get(hovered[3]) if hovered else None
            MapViewTemplate.position_hover_marker(canvas, self.slot_map_hover_item, hovered, color)

        MapViewTemplate.draw_zoom_indicator(
            canvas, self.slot_map_shared_zoom
        )

        self._island_slot_lasso_draw()

        # Recreate the persistent Shift+left selection after canvas.delete("all").
        selection = getattr(self, "island_slot_selection_world_bounds", None)
        lasso = getattr(self, "island_slot_lasso_world_points", ())
        if selection is not None and len(lasso) < 3:
            select_min_x, select_max_x, select_min_z, select_max_z = selection
            left = image_x + ((select_min_x - min_x) / span_x) * image_w
            right = image_x + ((select_max_x - min_x) / span_x) * image_w
            top = image_y + ((max_z - select_max_z) / span_z) * image_h
            bottom = image_y + ((max_z - select_min_z) / span_z) * image_h
            self.island_slot_selection_rect = canvas.create_rectangle(
                left, top, right, bottom,
                outline="#4da3ff", dash=(4, 2), width=2,
                tags=("slot_selection_area",),
            )

    def _slot_map_nearest(self, event, hover=False):
        return MapViewTemplate.point_from_event(
            event,
            self.slot_map_screen_points,
            hover=hover,
            visible=lambda point: self.slot_map_guid_visible.get(point[3], True),
        )

    def _slot_map_dot_movement_changed(self):
        enabled = bool(self.slot_map_allow_dot_movement_var.get())
        if not enabled:
            MapViewTemplate.dot_drag_cancel(self.slot_map_canvas)
        MapViewTemplate.set_dot_movement_cursor(self.slot_map_canvas, enabled)
        MapViewTemplate.update_dot_movement_undo(self.slot_map_canvas, enabled)

    def _slot_map_motion(self, event):
        MapViewTemplate.set_dot_movement_cursor(
            self.slot_map_canvas, bool(self.slot_map_allow_dot_movement_var.get()), event,
        )
        if MapViewTemplate.middle_pan_active(self.slot_map_canvas, event):
            return "break"
        p=self._slot_map_nearest(event, hover=True); hover=(p[2],p[3],p[4],p[5],p[6]) if p else None
        if hover != self.slot_map_hover_point:
            self.slot_map_hover_point = hover
            color = self.slot_map_guid_colors.get(p[3]) if p else None
            MapViewTemplate.position_hover_marker(self.slot_map_canvas, self.slot_map_hover_item, p, color)

    def _slot_map_leave(self, _event):
        MapViewTemplate.set_dot_movement_cursor(
            self.slot_map_canvas, bool(self.slot_map_allow_dot_movement_var.get())
        )
        self.slot_map_hover_point = None
        if self.slot_map_canvas is not None:
            MapViewTemplate.position_hover_marker(self.slot_map_canvas, self.slot_map_hover_item, None)

    def _slot_map_drag_start(self, event):
        return MapViewTemplate.dot_drag_start(
            event,
            self.slot_map_canvas,
            bool(self.slot_map_allow_dot_movement_var.get()),
            lambda drag_event: self._slot_map_nearest(drag_event, hover=True),
            lambda hit: hit[4] if len(hit) > 4 and isinstance(hit[4], str) and hit[4].startswith("#") else None,
        )

    def _slot_map_drag_motion(self, event):
        return MapViewTemplate.dot_drag_motion(
            event, self.slot_map_canvas,
            bool(self.slot_map_allow_dot_movement_var.get()),
        )

    def _slot_map_drag_end(self, event):
        return MapViewTemplate.dot_drag_end(
            event,
            self.slot_map_canvas,
            bool(self.slot_map_allow_dot_movement_var.get()),
            self._slot_map_commit_drag,
        )

    def _slot_map_commit_drag(self, event, hit):
        try:
            x,z=MapViewTemplate.world_from_event(
                event, self.slot_map_canvas, self.slot_map_bounds,
                self.slot_map_shared_zoom, self.slot_map_shared_pan_x, self.slot_map_shared_pan_y,
            )
            original=Path(self.mapname_file_var.get().strip())
            patched=original.with_name(original.name.replace("_original.xml","_patched.xml"))
            source=patched if patched.is_file() else original
            ram_map_tree = getattr(self, "_island_slot_ram_map_tree", None)
            tree = ram_map_tree if ram_map_tree is not None else self._slot_parse_xml(source)[0]
            root=tree.getroot(); oid=hit[2]
            records=[]
            for parent in root.iter():
                for node in list(parent):
                    vals={c.tag.rsplit("}",1)[-1]:(c.text or "").strip() for c in list(node) if isinstance(c.tag,str)}
                    if vals.get("ObjectId") and vals.get("Position"): records.append((node,vals))
            selected=next((r for r in records if r[1].get("ObjectId")==oid),None)
            if selected is None:raise ValueError('The selected slot no longer exists.')
            old=self._slot_map_parse_position(selected[1]["Position"]); dx,dz=x-old[0],z-old[2]
            samples,_source=self._island_slot_height_samples(); y=estimate_nearby_height(x,z,samples) if samples else old[1]
            targets=[selected]

            # Move the selected object independently; no River partner lookup.
            pending=getattr(self,'_slot_map_pending_moves',{})
            moved_ids=set()
            for node,vals in targets:
                pos=self._slot_map_parse_position(vals["Position"]); nx,nz=pos[0]+dx,pos[2]+dz
                ny=estimate_nearby_height(nx,nz,samples) if samples else pos[1]
                new_pos=f'{nx:.8g} {ny if ny is not None else pos[1]:.8g} {nz:.8g}'
                oid_value=vals.get("ObjectId","")
                pending[oid_value]=new_pos; moved_ids.add(oid_value)
            self._slot_map_pending_moves=pending
            updated=[]
            for point in self.slot_map_points:
                if point[0] in moved_ids:
                    px,py,pz=self._slot_map_parse_position(pending[point[0]])
                    issue = point[6] if len(point) >= 7 else None
                    updated.append((point[0],point[1],px,py,pz,pending[point[0]],issue))
                else: updated.append(point)
            self.slot_map_points=updated
            self._slot_map_schedule_redraw()
            self.status_var.set(f'Moved {len(targets)} slot object(s) in preview. Use Save to write changes.')
            old_position = hit[7]
            def undo_move():
                pending_moves = getattr(self, '_slot_map_pending_moves', {})
                pending_moves[oid] = old_position
                self._slot_map_pending_moves = pending_moves
                restored = []
                for point in self.slot_map_points:
                    if point[0] == oid:
                        px, py, pz = self._slot_map_parse_position(old_position)
                        issue = point[6] if len(point) >= 7 else None
                        restored.append((point[0], point[1], px, py, pz, old_position, issue))
                    else:
                        restored.append(point)
                self.slot_map_points = restored
                self._slot_map_schedule_redraw()
                self.status_var.set('Last slot movement undone in RAM.')
            return undo_move
        except (ValueError,OSError,ET.ParseError) as exc:
            messagebox.showerror('Move Slot',str(exc),parent=self.slot_map_window)
        return "break"

    def _slot_map_click(self, event):
        p=self._slot_map_nearest(event, hover=False)
        if not p:
            return
        if len(p) >= 9:
            _, _, oid, guid, x, y, z, pos, issue = p[:9]
        elif len(p) == 8:
            _, _, oid, guid, x, y, z, pos = p
            issue = None
        else:
            print(
                f"[Slot Map] Invalid hit record: "
                f"{p!r} ({len(p)} values)"
            )
            return

        selection_text = (
            f"ObjectId {oid} | GUID {guid} | "
            f"X {x:.3f} Y {y:.3f} Z {z:.3f}\n"
            f"Position: {pos}"
        )
        if issue:
            selection_text += f"\nIssue: {issue}"
        self.slot_map_selection_var.set(selection_text)

    @staticmethod
    def _slot_configuration_combined_row(row, data, _row_index):
        """RD3D Objects layout: stable ID + original GUID + editable patched GUID."""
        row.configure(height=TemplateTable.COMBINED_ROW_HEIGHT)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row,
            textvariable=data["id"],
            width=220,
            anchor="w",
        ).grid(row=0, column=0, rowspan=2, padx=5, pady=5, sticky="nsw")

        # Original GUID, first line: read-only, transparent, no border.
        ctk.CTkEntry(
            row,
            textvariable=data["original_guid"],
            height=TemplateTable.ENTRY_HEIGHT,
            font=ctk.CTkFont(size=TemplateTable.ENTRY_FONT_SIZE),
            text_color=TemplateTable.DISABLED_TEXT_COLOR,
            state="disabled",
            border_width=0,
            fg_color=TemplateTable.DISABLED_FG_COLOR,
        ).grid(row=0, column=1, padx=5, pady=(5, 2), sticky="ew")

        # Patched/new GUID, second line: editable.
        ctk.CTkEntry(
            row,
            textvariable=data["patched_guid"],
            height=TemplateTable.ENTRY_HEIGHT,
            font=ctk.CTkFont(size=TemplateTable.ENTRY_FONT_SIZE),
            text_color=TemplateTable.EDITABLE_TEXT_COLOR,
            fg_color=TemplateTable.EDITABLE_FG_COLOR,
            border_width=1,
        ).grid(row=1, column=1, padx=5, pady=(2, 5), sticky="ew")

    def _mass_replace_slot_configuration_guids(self):
        old_guid = self.slot_mass_original_guid_var.get().strip()
        new_guid = self.slot_mass_new_guid_var.get().strip()
        if not old_guid or not new_guid:
            messagebox.showerror(
                "Mass Replace", "Please enter both Original GUID and New GUID."
            )
            return
        if old_guid == new_guid:
            messagebox.showinfo(
                "Mass Replace", "Original GUID and New GUID are identical."
            )
            return
        replaced = 0
        for _id_var, guid_var in getattr(self, "slot_configuration_edit_rows", []):
            if guid_var.get().strip() == old_guid:
                guid_var.set(new_guid)
                replaced += 1
        if replaced:
            self.status_var.set(
                f"Mass Replace: {old_guid} -> {new_guid} ({replaced} entries)"
            )
            messagebox.showinfo(
                "Mass Replace",
                f"Replaced {replaced} entr{'y' if replaced == 1 else 'ies'}.\n\n"
                f"{old_guid} -> {new_guid}\n\n"
                "Click Save to write the changes to the patched XML files.",
            )
        else:
            messagebox.showinfo(
                "Mass Replace", f"GUID {old_guid} was not found in patched values."
            )

    def _load_slot_configuration_objects(self):
        original = Path(self.gamedata_file_var.get().strip())
        if not original.is_file():
            self.slot_configuration_info_var.set("No gamedata_original.xml loaded.")
            self._clear_slot_configuration_table()
            return False

        try:
            original_tree, _repaired, _repairs = self._slot_parse_xml(original)
            original_rows = self._slot_collect_gamedata_objects(original_tree.getroot())
        except (ET.ParseError, OSError, UnicodeError) as exc:
            self.slot_configuration_info_var.set(
                f"Could not read gamedata_original.xml: {exc}"
            )
            self._clear_slot_configuration_table()
            return False

        patched = original.with_name("gamedata_patched.xml")
        patched_rows = original_rows
        if patched.is_file():
            try:
                patched_tree, _repaired, _repairs = self._slot_parse_xml(patched)
                candidate_rows = self._slot_collect_gamedata_objects(patched_tree.getroot())
                if len(candidate_rows) == len(original_rows):
                    patched_rows = candidate_rows
            except (ET.ParseError, OSError, UnicodeError):
                pass

        self.slot_configuration_original_rows = list(original_rows)
        self.slot_configuration_edit_rows = []
        table_rows = []

        for (original_id, original_guid), (patched_id, patched_guid) in zip(
            original_rows, patched_rows
        ):
            # ID remains read-only. Patched GUID is matched by source order, as in
            # the previous Objects implementation.
            id_var = tk.StringVar(value=original_id)
            original_guid_var = tk.StringVar(value=original_guid)
            patched_guid_var = tk.StringVar(value=patched_guid)
            self.slot_configuration_edit_rows.append((id_var, patched_guid_var))
            table_rows.append(
                {
                    "id": id_var,
                    "original_guid": original_guid_var,
                    "patched_guid": patched_guid_var,
                }
            )

        self.slot_configuration_table.set_rows(table_rows)
        self.slot_configuration_table.scroll_to_top()
        self.slot_configuration_info_var.set(
            f"Objects: {len(original_rows)} ID/GUID entries | "
            "Original GUID above, patched GUID below"
        )
        return True

    def _clear_slot_configuration_table(self):
        table = getattr(self, "slot_configuration_table", None)
        if table is not None and table.winfo_exists():
            table.clear()
        self.slot_configuration_original_rows = []
        self.slot_configuration_edit_rows = []

    # Compatibility for calls from an earlier two-table version.
    def _clear_slot_configuration_tables(self):
        self._clear_slot_configuration_table()

    def _reset_slot_configuration(self):
        """Reload all slot rows from gamedata_original.xml and discard UI edits."""
        original = Path(self.gamedata_file_var.get().strip())
        if not original.is_file():
            messagebox.showerror(
                "Slot Configuration", "Please load gamedata_original.xml first."
            )
            return
        # Temporarily ignore gamedata_patched.xml so the editable values are
        # rebuilt from the original file exactly as requested.
        try:
            tree, _repaired, _repairs = self._slot_parse_xml(original)
            original_rows = self._slot_collect_gamedata_objects(tree.getroot())
        except (ET.ParseError, OSError, UnicodeError) as exc:
            messagebox.showerror(
                "Slot Configuration", f"gamedata_original.xml could not be read:\n{exc}"
            )
            return
        self.slot_configuration_original_rows = list(original_rows)
        self.slot_configuration_edit_rows = []
        table_rows = []
        for object_id, original_guid in original_rows:
            id_var = tk.StringVar(value=object_id)
            original_guid_var = tk.StringVar(value=original_guid)
            patched_guid_var = tk.StringVar(value=original_guid)
            self.slot_configuration_edit_rows.append((id_var, patched_guid_var))
            table_rows.append({
                "id": id_var,
                "original_guid": original_guid_var,
                "patched_guid": patched_guid_var,
            })
        self.slot_configuration_table.set_rows(table_rows)
        self.slot_configuration_table.scroll_to_top()
        self.slot_configuration_info_var.set(
            f"Objects: {len(original_rows)} ID/GUID entries | Original values reloaded"
        )
        self.slot_mass_original_guid_var.set("")
        self.slot_mass_new_guid_var.set("")
        self.status_var.set("Slot configuration reloaded from gamedata_original.xml")

    def _save_slot_configuration(self):
        original = Path(self.gamedata_file_var.get().strip())
        if not original.is_file():
            messagebox.showerror("Slot Configuration", "Please load gamedata_original.xml first.")
            return
        edit_rows = getattr(self, "slot_configuration_edit_rows", [])
        if not edit_rows:
            messagebox.showerror("Slot Configuration", "No slot objects are loaded.")
            return
        guid_changes = {}
        for id_var, guid_var in edit_rows:
            object_id = id_var.get().strip(); guid = guid_var.get().strip()
            if not object_id or not guid:
                messagebox.showerror("Slot Configuration", "ID and GUID values must not be empty.")
                return
            guid_changes[object_id] = guid
        try:
            tree, _repaired, _repairs = self._slot_parse_xml(original)
            root = tree.getroot()
            changed = 0
            for parent in root.iter():
                children = list(parent)
                id_node = next((c for c in children if isinstance(c.tag,str) and c.tag.rsplit("}",1)[-1].lower()=="id"), None)
                guid_node = next((c for c in children if isinstance(c.tag,str) and c.tag.rsplit("}",1)[-1].lower()=="guid"), None)
                object_id = (id_node.text or "").strip() if id_node is not None else ""
                if object_id in guid_changes and guid_node is not None and (guid_node.text or "").strip() != guid_changes[object_id]:
                    guid_node.text = guid_changes[object_id]; changed += 1
            patched = original.with_name("gamedata_patched.xml")
            tree.write(patched, encoding="utf-8", xml_declaration=False, short_empty_elements=True)

            map_changed = 0
            mapname = Path(self.mapname_file_var.get().strip())
            if mapname.is_file():
                map_tree, _repaired, _repairs = self._slot_parse_xml(mapname)
                for parent in map_tree.getroot().iter():
                    children = list(parent)
                    id_node = next((c for c in children if isinstance(c.tag,str) and c.tag.rsplit("}",1)[-1].lower()=="objectid"), None)
                    guid_node = next((c for c in children if isinstance(c.tag,str) and c.tag.rsplit("}",1)[-1].lower()=="objectguid"), None)
                    object_id = (id_node.text or "").strip() if id_node is not None else ""
                    if object_id in guid_changes and guid_node is not None and (guid_node.text or "").strip() != guid_changes[object_id]:
                        guid_node.text = guid_changes[object_id]; map_changed += 1
                map_patched = mapname.with_name(mapname.name.replace("_original.xml", "_patched.xml") if mapname.name.endswith("_original.xml") else f"{mapname.stem}_patched.xml")
                map_tree.write(map_patched, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
        except (OSError, ET.ParseError, UnicodeError) as exc:
            messagebox.showerror("Slot Configuration", f"Slot changes could not be saved:\n{exc}")
            return
        self._refresh_open_slot_map()
        self.status_var.set(f"Slot configuration saved: {changed} gamedata GUID change(s), {map_changed} map GUID change(s)")
        messagebox.showinfo("Slot Configuration", f"Slot configuration saved.\n\nGamedata GUID changes: {changed}\nMap GUID changes: {map_changed}")

    # ------------------------------------------------------------------
    # Combined Slot Editor (ID-based join of gamedata and mapname)
    # ------------------------------------------------------------------
    @staticmethod
    def _combined_slot_map_rows(root):
        slot_objects = next((n for n in root.iter() if isinstance(n.tag, str) and n.tag.rsplit("}", 1)[-1] == "SlotObjects"), None)
        rows, current_group = [], ""
        if slot_objects is None:
            return rows
        for block in list(slot_objects):
            value = next((c for c in list(block) if isinstance(c.tag, str) and c.tag.rsplit("}", 1)[-1].lower() == "value"), None)
            if value is not None:
                group_node = next((c for c in list(value) if isinstance(c.tag, str) and c.tag.rsplit("}", 1)[-1].lower() == "id"), None)
                if group_node is not None:
                    current_group = (group_node.text or "").strip()
                continue
            for node in list(block):
                children = {c.tag.rsplit("}", 1)[-1].lower(): c for c in list(node) if isinstance(c.tag, str)}
                if {"objectid", "objectguid", "position"} <= children.keys():
                    rows.append({"group": current_group, "id": (children["objectid"].text or "").strip(), "guid": (children["objectguid"].text or "").strip(), "position": (children["position"].text or "").strip()})
        return rows

    @staticmethod
    def _combined_slot_position_parts(text):
        parts = (text or "").split()
        if len(parts) != 3:
            return None
        try:
            [float(value.replace(",", ".")) for value in parts]
        except ValueError:
            return None
        return parts

    @staticmethod
    def _combined_slot_gamedata_rows(root):
        rows = {}
        for parent in root.iter():
            values = {}
            for child in list(parent):
                if not isinstance(child.tag, str):
                    continue
                tag = child.tag.rsplit("}", 1)[-1].lower()
                if tag in {"id", "guid", "position"}:
                    values[tag] = (child.text or "").strip()
            if values.get("id") and values.get("guid"):
                rows[values["id"]] = {
                    "guid": values["guid"],
                    "position": values.get("position", ""),
                }
        return rows

    def _combined_slot_collect(self, original_only=False):
        game_path = Path(self.gamedata_file_var.get().strip())
        map_path = Path(self.mapname_file_var.get().strip())
        if not game_path.is_file() or not map_path.is_file():
            raise FileNotFoundError("Please load gamedata_original.xml and mapname_original.xml first.")

        orig_game_tree = self._slot_parse_xml(game_path)[0]
        orig_map_tree = self._slot_parse_xml(map_path)[0]
        orig_game_rows = self._combined_slot_gamedata_rows(orig_game_tree.getroot())
        orig_game = {oid: item["guid"] for oid, item in orig_game_rows.items()}
        orig_map_rows = self._combined_slot_map_rows(orig_map_tree.getroot())

        game_target = game_path.with_name("gamedata_patched.xml")
        map_target = map_path.with_name(map_path.name.replace("_original.xml", "_patched.xml") if map_path.name.endswith("_original.xml") else f"{map_path.stem}_patched.xml")

        cur_game = dict(orig_game)
        cur_game_rows = dict(orig_game_rows)
        cur_game_tree = orig_game_tree
        if game_target.is_file() and not original_only:
            try:
                cur_game_tree = self._slot_parse_xml(game_target)[0]
                cur_game_rows = self._combined_slot_gamedata_rows(cur_game_tree.getroot())
                cur_game_objs = {oid: item["guid"] for oid, item in cur_game_rows.items()}
                if cur_game_objs:
                    cur_game = cur_game_objs
            except (ET.ParseError, OSError, UnicodeError):
                pass

        cur_map_tree = orig_map_tree
        cur_map_by_id = {}
        if map_target.is_file() and not original_only:
            try:
                cur_map_tree = self._slot_parse_xml(map_target)[0]
                cur_map_rows = self._combined_slot_map_rows(cur_map_tree.getroot())
                if cur_map_rows:
                    cur_map_by_id = {item["id"]: item for item in cur_map_rows}
            except (ET.ParseError, OSError, UnicodeError):
                pass

        # The editor must show the current MapName state. Once a patched file
        # exists, entries deleted from it must not reappear from mapname_original.
        original_map_by_id = {item["id"]: item for item in orig_map_rows}
        current_map_rows = (
            list(cur_map_by_id.values()) if map_target.is_file() and not original_only
            else list(orig_map_rows)
        )

        result = []
        for cur_item in current_map_rows:
            oid = cur_item["id"]
            group = cur_item["group"]
            orig_item = original_map_by_id.get(oid, cur_item)
            orig_guid = orig_game.get(oid) or orig_item.get("guid") or ""
            orig_pos = orig_item.get("position") or ""

            effective_guid = cur_item.get("guid") or orig_guid
            effective_pos = cur_item.get("position") or orig_pos
            game_guid = cur_game.get(oid)

            if game_guid is None and oid not in orig_game:
                status = "Mapname only"
            elif game_guid is not None and game_guid != effective_guid:
                status = "GUID mismatch"
            elif self._combined_slot_position_parts(effective_pos) is None:
                status = "Invalid position"
            else:
                status = "Linked"

            parts = self._combined_slot_position_parts(effective_pos) or ["", "", ""]

            result.append({
                "group": group,
                "id": oid,
                "map_object_id": oid,
                "original_guid": orig_guid,
                "original_position": orig_pos,
                "guid": effective_guid,
                "position": effective_pos,
                "game_guid": game_guid or "",
                "game_position": cur_game_rows.get(oid, {}).get("position", ""),
                "status": status,
                "guid_var": tk.StringVar(value=effective_guid),
                "x_var": tk.StringVar(value=parts[0]),
                "y_var": tk.StringVar(value=parts[1]),
                "z_var": tk.StringVar(value=parts[2]),
                "position_source_var": tk.StringVar(value="Use Mapdata"),
            })
        self.combined_slot_game_tree = cur_game_tree
        self.combined_slot_map_tree = cur_map_tree
        self.combined_slot_game_target = game_target
        self.combined_slot_map_target = map_target
        self.combined_slot_game_nodes_by_id = self._combined_slot_build_xml_index(
            cur_game_tree.getroot(), "id"
        )
        self.combined_slot_map_nodes_by_id = self._combined_slot_build_xml_index(
            cur_map_tree.getroot(), "objectid"
        )
        return result

    @staticmethod
    def _combined_slot_build_xml_index(root, id_tag):
        index = {}
        for parent in root.iter():
            children = {
                child.tag.rsplit("}", 1)[-1].lower(): child
                for child in list(parent)
                if isinstance(child.tag, str)
            }
            node = children.get(id_tag)
            object_id = (node.text or "").strip() if node is not None else ""
            if object_id:
                index[object_id] = (parent, children)
        return index

    def _combined_slot_mark_dirty(self, object_id, *_args):
        object_id = str(object_id)
        if object_id not in self.combined_slot_deleted_ids:
            self.combined_slot_dirty_ids.add(object_id)
            self._combined_slot_update_summary()

    def _combined_slot_bind_ram_record(self, record):
        object_id = record["id"]
        for key in ("guid_var", "x_var", "y_var", "z_var"):
            record[key].trace_add(
                "write",
                lambda *_args, oid=object_id: self._combined_slot_mark_dirty(oid),
            )

    def _combined_slot_update_summary(self):
        counts = {}
        for record in self.combined_slot_records:
            counts[record["status"]] = counts.get(record["status"], 0) + 1
        base = " | ".join(
            f"{key}: {value}" for key, value in sorted(counts.items())
        ) or "No SlotObjects found"
        changes = len(self.combined_slot_dirty_ids) + len(self.combined_slot_deleted_ids)
        if changes:
            base += f" | Unsaved: {changes}"
        if self.combined_slot_summary is not None and self.combined_slot_summary.winfo_exists():
            self.combined_slot_summary.configure(text=base)

    def _open_combined_slot_editor(self):
        status = self._show_object_operation_status("Loading Slot Editor...")
        try:
            self._open_combined_slot_editor_impl()
            self.update_idletasks()
            window = getattr(self, "combined_slot_window", None)
            if window is not None and window.winfo_exists():
                window.update_idletasks()
                window.lift()
        finally:
            self._hide_object_operation_status(status)

    def _open_combined_slot_editor_impl(self):
        old = getattr(self, "combined_slot_window", None)
        if old is not None and old.winfo_exists():
            PopupTemplate.safe_activate(old)
            return
        try:
            records = self._combined_slot_collect()
        except (OSError, ET.ParseError, UnicodeError) as exc:
            messagebox.showerror("Slot Editor", str(exc))
            return
        popup = PopupTemplate.create_window(
            self,
            title="Slot Editor",
            heading="Slot Editor",
            geometry="1450x760",
            min_size=(1050, 560),
            resizable=True,
            modal=False,
            close_command=lambda: self._close_combined_slot_editor(),
            add_header=False,
            maximize=False,
        )
        window = popup["window"]
        self.combined_slot_window = window
        window.title("Slot Editor")
        window.geometry("1450x760")
        window.minsize(1050, 560)
        window.transient(self.winfo_toplevel())
        window.protocol("WM_DELETE_WINDOW", lambda: self._close_combined_slot_editor())
        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(2, weight=1)
        top = ctk.CTkFrame(window, fg_color="transparent")
        top.grid(row=0, column=0, padx=16, pady=(14, 8), sticky="ew")
        top.grid_columnconfigure(0, weight=1, uniform="combined_top")
        top.grid_columnconfigure(1, weight=2, uniform="combined_top")
        top.grid_columnconfigure(2, weight=1, uniform="combined_top")
        ctk.CTkLabel(
            top,
            text="Slot Editor",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        window._popup_maximize_button = None

        filter_bar = ctk.CTkFrame(top, fg_color="transparent")
        filter_bar.grid(row=0, column=1)
        self.combined_slot_filter = tk.StringVar()
        entry = ctk.CTkEntry(
            filter_bar,
            textvariable=self.combined_slot_filter,
            placeholder_text="Filter by ID, GUID, group or status",
            width=360,
        )
        entry.grid(row=0, column=0, padx=(0, 8))
        entry.bind("<Return>", lambda _event: self._combined_slot_apply_filter())
        ctk.CTkButton(
            filter_bar,
            text="Apply Filter",
            width=110,
            command=self._combined_slot_apply_filter,
        ).grid(row=0, column=1)

        mass_guid_bar = ctk.CTkFrame(top, fg_color="transparent")
        mass_guid_bar.grid(row=1, column=0, columnspan=3, pady=(10, 0), sticky="w")
        ctk.CTkLabel(
            mass_guid_bar,
            text="Mass GUID Change:",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, padx=(0, 8), sticky="w")
        self.combined_slot_mass_guid_from = tk.StringVar()
        self.combined_slot_mass_guid_to = tk.StringVar()
        ctk.CTkLabel(mass_guid_bar, text="From:").grid(
            row=0, column=1, padx=(0, 6), sticky="w"
        )
        from_entry = ctk.CTkEntry(
            mass_guid_bar,
            textvariable=self.combined_slot_mass_guid_from,
            width=180,
        )
        from_entry.grid(row=0, column=2, padx=(0, 12), sticky="w")
        ctk.CTkLabel(mass_guid_bar, text="To:").grid(
            row=0, column=3, padx=(0, 6), sticky="w"
        )
        to_entry = ctk.CTkEntry(
            mass_guid_bar,
            textvariable=self.combined_slot_mass_guid_to,
            width=180,
        )
        to_entry.grid(row=0, column=4, padx=(0, 8), sticky="w")
        ctk.CTkButton(
            mass_guid_bar,
            text="Apply",
            width=90,
            command=self._combined_slot_mass_guid_change,
        ).grid(row=0, column=5, sticky="w")
        from_entry.bind("<Return>", lambda _event: to_entry.focus_set())
        to_entry.bind("<Return>", lambda _event: self._combined_slot_mass_guid_change())

        counts = {}
        for record in records:
            counts[record["status"]] = counts.get(record["status"], 0) + 1
        summary = " | ".join([f"{key}: {value}" for key, value in sorted(counts.items())]) or "No SlotObjects found"
        self.combined_slot_summary = ctk.CTkLabel(window, text=summary, anchor="w", text_color="#e0a84f")
        self.combined_slot_summary.grid(row=1, column=0, padx=18, pady=(0, 8), sticky="ew")
        table_frame = ctk.CTkFrame(window)
        table_frame.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        columns = (
            "id", "game_guid", "game_pos", "map_guid", "map_pos",
            "status", "new_guid", "new_pos",
        )
        headings = {
            "id": "Object ID",
            "game_guid": "Gamedata GUID",
            "game_pos": "Gamedata Position",
            "map_guid": "Mapdata GUID",
            "map_pos": "Mapdata Position",
            "status": "Status",
            "new_guid": "New GUID",
            "new_pos": "New Position",
        }
        tag_styles = {
            "Linked": {"foreground": "#55bb66"},
            "Mapname only": {"foreground": "#ff6666"},
            "GUID mismatch": {"foreground": "#ffb000"},
        }
        tree_widgets = TreeviewTemplate.create(
            table_frame,
            columns=columns,
            headings=headings,
            widths={
                "id": 185, "game_guid": 105, "game_pos": 190,
                "map_guid": 105, "map_pos": 190, "status": 115,
                "new_guid": 105, "new_pos": 190,
            },
            min_widths={
                "id": 135, "game_guid": 100, "game_pos": 145,
                "map_guid": 100, "map_pos": 145, "status": 100,
                "new_guid": 95, "new_pos": 145,
            },
            max_widths={
                "id": 260, "game_guid": 180, "game_pos": 330,
                "map_guid": 180, "map_pos": 330, "status": 190,
                "new_guid": 180, "new_pos": 330,
            },
            stretch={"game_pos", "map_pos", "new_pos"},
            tag_styles=tag_styles,
            selectmode="extended",
            on_select=self._combined_slot_tree_select,
            sortable=True,
            dynamic_width=True,
        )
        tree = tree_widgets["tree"]
        self.combined_slot_tree = tree
        self.combined_slot_scroll = tree

        editor = ctk.CTkFrame(window)
        editor.grid(row=3, column=0, padx=16, pady=(0, 8), sticky="ew")
        editor.grid_columnconfigure(0, weight=1)

        selection = ctk.CTkFrame(editor, fg_color="transparent")
        selection.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="ew")
        selection.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(selection, text="Selected Object ID", width=125, anchor="w").grid(
            row=0, column=0, padx=(0, 8), sticky="w"
        )
        ctk.CTkLabel(
            selection, textvariable=self.combined_slot_editor_id,
            width=210, anchor="w"
        ).grid(row=0, column=1, padx=(0, 12), sticky="w")
        ctk.CTkOptionMenu(
            selection,
            variable=self.combined_slot_editor_source,
            values=["Use Mapdata", "Use Gamedata"],
            width=145,
            command=self._combined_slot_editor_source_changed,
        ).grid(row=0, column=2, padx=(0, 6))

        values = ctk.CTkFrame(editor, fg_color="transparent")
        values.grid(row=1, column=0, padx=10, pady=(4, 8), sticky="w")
        fields = (
            ("GUID", self.combined_slot_editor_guid, 150),
            ("X", self.combined_slot_editor_x, 105),
            ("Y", self.combined_slot_editor_y, 105),
            ("Z", self.combined_slot_editor_z, 105),
        )
        column = 0
        for label, variable, width in fields:
            ctk.CTkLabel(values, text=label, width=42, anchor="e").grid(
                row=0, column=column, padx=(0, 4), sticky="e"
            )
            ctk.CTkEntry(values, textvariable=variable, width=width).grid(
                row=0, column=column + 1, padx=(0, 12)
            )
            column += 2
        ctk.CTkButton(
            values, text="Apply", width=90,
            command=self._combined_slot_editor_apply
        ).grid(row=0, column=column, padx=(4, 6))
        ctk.CTkButton(
            values, text="Delete", width=90,
            fg_color="#bb3333", hover_color="#992222",
            command=self._combined_slot_editor_delete
        ).grid(row=0, column=column + 1, padx=(0, 0))


        actions = ctk.CTkFrame(window, fg_color="transparent")
        actions.grid(row=4, column=0, padx=16, pady=(0, 14), sticky="ew")
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(actions, text="Reload", width=110, fg_color="#555555", hover_color="#666666", command=self._combined_slot_reload).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(
            actions,
            text="Reset",
            width=110,
            fg_color="#B33939",
            hover_color="#8F2D2D",
            command=self._combined_slot_reset_to_original,
        ).grid(row=0, column=2, padx=(0, 8))
        ctk.CTkButton(actions, text="Save", width=120, font=ctk.CTkFont(weight="bold"), command=self._save_combined_slot_editor).grid(row=0, column=3)
        self.combined_slot_records = records
        self.combined_slot_page = 0
        self.combined_slot_records_by_id = {record["id"]: record for record in records}
        self.combined_slot_dirty_ids.clear()
        self.combined_slot_deleted_ids.clear()
        for record in records:
            record["_search_text"] = self._combined_slot_search_text(record)
            self._combined_slot_bind_ram_record(record)
        self._combined_slot_render()
        PopupTemplate.schedule(window, 50, lambda: PopupTemplate.safe_activate(window))

    def _close_combined_slot_editor(self):
        window = getattr(self, "combined_slot_window", None)
        PopupTemplate.close_window(window)
        self.combined_slot_window = None

    def _combined_slot_reload(self):
        try:
            records = self._combined_slot_collect()
        except (OSError, ET.ParseError, UnicodeError) as exc:
            messagebox.showerror("Slot Editor", str(exc), parent=self.combined_slot_window)
            return
        self.combined_slot_records = records
        self.combined_slot_page = 0
        self.combined_slot_records_by_id = {record["id"]: record for record in records}
        self.combined_slot_dirty_ids.clear()
        self.combined_slot_deleted_ids.clear()
        for record in records:
            record["_search_text"] = self._combined_slot_search_text(record)
            self._combined_slot_bind_ram_record(record)
        self._combined_slot_render()

    def _combined_slot_reset_to_original(self):
        if not messagebox.askyesno(
            "Slot Editor",
            "Reload Gamedata and Mapdata from the _original XML files?\n\n"
            "All unsaved Combined Slot Editor changes will be discarded.",
            parent=self.combined_slot_window,
            default="no",
        ):
            return
        try:
            records = self._combined_slot_collect(original_only=True)
        except (OSError, ET.ParseError, UnicodeError) as exc:
            messagebox.showerror(
                "Slot Editor", str(exc), parent=self.combined_slot_window
            )
            return
        self.combined_slot_records = records
        self.combined_slot_records_by_id = {record["id"]: record for record in records}
        self.combined_slot_dirty_ids.clear()
        self.combined_slot_deleted_ids.clear()
        for record in records:
            record["_search_text"] = self._combined_slot_search_text(record)
            self._combined_slot_bind_ram_record(record)
        self.combined_slot_filter.set("")
        self.combined_slot_editor_id.set("")
        self.combined_slot_editor_guid.set("")
        self.combined_slot_editor_x.set("")
        self.combined_slot_editor_y.set("")
        self.combined_slot_editor_z.set("")
        self._combined_slot_render()
        self.status_var.set(
            "Combined Slot Editor reloaded from gamedata_original.xml and mapname_original.xml."
        )

    def _combined_slot_apply_position_source(self, record, choice):
        """Copy the selected source position to the other source in memory."""
        if choice == "Use Gamedata":
            parts = self._combined_slot_position_parts(record.get("game_position", ""))
            if parts is None:
                messagebox.showwarning(
                    "Slot Editor",
                    f"Gamedata has no valid position for Object ID {record['id']}.",
                    parent=self.combined_slot_window,
                )
                record["position_source_var"].set("Use Mapdata")
                return
            record["x_var"].set(parts[0])
            record["y_var"].set(parts[1])
            record["z_var"].set(parts[2])
            record["position"] = " ".join(parts)
        else:
            parts = [
                record["x_var"].get().strip(),
                record["y_var"].get().strip(),
                record["z_var"].get().strip(),
            ]
            if self._combined_slot_position_parts(" ".join(parts)) is None:
                messagebox.showwarning(
                    "Slot Editor",
                    f"Mapdata has no valid position for Object ID {record['id']}.",
                    parent=self.combined_slot_window,
                )
                return
            record["game_position"] = " ".join(parts)
        self._combined_slot_render()

    def _combined_slot_mass_guid_change(self):
        from_guid = self.combined_slot_mass_guid_from.get().strip()
        to_guid = self.combined_slot_mass_guid_to.get().strip()
        if not from_guid or not to_guid:
            messagebox.showwarning(
                "Mass GUID Change",
                "Enter both a From GUID and a To GUID.",
                parent=self.combined_slot_window,
            )
            return
        if from_guid == to_guid:
            messagebox.showinfo(
                "Mass GUID Change",
                "From and To contain the same GUID. No values were changed.",
                parent=self.combined_slot_window,
            )
            return

        changed_ids = []
        for record in self.combined_slot_records:
            if record["id"] in self.combined_slot_deleted_ids:
                continue
            if record["guid_var"].get().strip() != from_guid:
                continue
            record["guid_var"].set(to_guid)
            record["_search_text"] = self._combined_slot_search_text(record)
            self._combined_slot_mark_dirty(record["id"])
            changed_ids.append(record["id"])

        if not changed_ids:
            messagebox.showinfo(
                "Mass GUID Change",
                f"No entries with GUID {from_guid} were found.",
                parent=self.combined_slot_window,
            )
            return

        selected_id = self.combined_slot_editor_id.get().strip()
        if selected_id in changed_ids:
            self.combined_slot_editor_guid.set(to_guid)
        self._combined_slot_render()
        self.status_var.set(
            f"Slot Editor: changed GUID {from_guid} to {to_guid} for "
            f"{len(changed_ids)} object(s) in RAM. Click Save to write both XML files."
        )
        messagebox.showinfo(
            "Mass GUID Change",
            f"Changed {len(changed_ids)} GUID value(s) in RAM.\n\n"
            "Click Save to write the changes to Gamedata and MapName.",
            parent=self.combined_slot_window,
        )

    def _combined_slot_apply_filter(self):
        self.combined_slot_page = 0
        self._combined_slot_render()

    def _combined_slot_change_page(self, delta):
        page_size = max(1, int(self.combined_slot_page_size))
        pages = max(1, (self.combined_slot_filtered_count + page_size - 1) // page_size)
        new_page = max(0, min(self.combined_slot_page + int(delta), pages - 1))
        if new_page != self.combined_slot_page:
            self.combined_slot_page = new_page
            self._combined_slot_render()

    @staticmethod
    def _combined_slot_search_text(record):
        return " ".join(str(record.get(key, "")) for key in (
            "group", "id", "original_guid", "game_guid",
            "game_position", "position", "status",
        )).casefold()

    def _combined_slot_tree_values(self, record):
        new_pos = " ".join((record["x_var"].get().strip(), record["y_var"].get().strip(), record["z_var"].get().strip()))
        return (
            record["id"], record.get("game_guid") or "-", record.get("game_position") or "-",
            record.get("guid") or "-", record.get("position") or "-", record.get("status") or "-",
            record["guid_var"].get().strip(), new_pos,
        )

    def _combined_slot_render(self):
        tree = getattr(self, "combined_slot_tree", None)
        if tree is None or not tree.winfo_exists():
            return
        selection = tree.selection()
        selected_id = selection[0] if selection else None
        tree.delete(*tree.get_children())
        query = self.combined_slot_filter.get().strip().casefold()
        visible = 0
        for record in self.combined_slot_records:
            haystack = record.get("_search_text") or self._combined_slot_search_text(record)
            if query and query not in haystack and query not in record["guid_var"].get().strip().casefold():
                continue
            object_id = record["id"]
            tree.insert("", "end", iid=object_id, values=self._combined_slot_tree_values(record), tags=(record.get("status", ""),))
            visible += 1
        self.combined_slot_filtered_count = visible
        self.combined_slot_page_var.set(f"{visible} row(s)")
        if selected_id and tree.exists(selected_id):
            tree.selection_set(selected_id)
            tree.focus(selected_id)
        self._combined_slot_update_summary()

    def _combined_slot_tree_select(self, _event=None):
        tree = self.combined_slot_tree
        selection = tree.selection() if tree is not None else ()
        if not selection:
            return
        # The shared editor displays the first selected row. Delete operates on
        # every selected row in the Treeview.
        object_id = selection[0]
        record = self.combined_slot_records_by_id.get(object_id)
        if record is None:
            return
        self.combined_slot_editor_id.set(object_id)
        self.combined_slot_editor_guid.set(record["guid_var"].get())
        self.combined_slot_editor_x.set(record["x_var"].get())
        self.combined_slot_editor_y.set(record["y_var"].get())
        self.combined_slot_editor_z.set(record["z_var"].get())
        self.combined_slot_editor_source.set("Use Mapdata")

    def _combined_slot_editor_apply(self):
        object_id = self.combined_slot_editor_id.get().strip()
        record = self.combined_slot_records_by_id.get(object_id)
        if record is None:
            return
        guid = self.combined_slot_editor_guid.get().strip()
        position = " ".join((self.combined_slot_editor_x.get().strip(), self.combined_slot_editor_y.get().strip(), self.combined_slot_editor_z.get().strip()))
        if not guid or self._combined_slot_position_parts(position) is None:
            messagebox.showerror("Slot Editor", "GUID and X/Y/Z must be valid.", parent=self.combined_slot_window)
            return
        record["guid_var"].set(guid)
        record["x_var"].set(self.combined_slot_editor_x.get().strip())
        record["y_var"].set(self.combined_slot_editor_y.get().strip())
        record["z_var"].set(self.combined_slot_editor_z.get().strip())
        record["_search_text"] = self._combined_slot_search_text(record)
        self._combined_slot_mark_dirty(object_id)
        if self.combined_slot_tree.exists(object_id):
            self.combined_slot_tree.item(object_id, values=self._combined_slot_tree_values(record))

    def _combined_slot_editor_source_changed(self, choice):
        object_id = self.combined_slot_editor_id.get().strip()
        record = self.combined_slot_records_by_id.get(object_id)
        if record is None:
            return
        if choice == "Use Gamedata":
            guid = record.get("game_guid", "")
            position = record.get("game_position", "")
            source_name = "Gamedata"
        else:
            guid = record.get("guid", "")
            position = record.get("position", "")
            source_name = "Mapdata"
        parts = self._combined_slot_position_parts(position)
        if not guid or parts is None:
            messagebox.showwarning(
                "Slot Editor",
                f"{source_name} has no complete GUID and position for Object ID {object_id}.",
                parent=self.combined_slot_window,
            )
            return
        self.combined_slot_editor_guid.set(guid)
        self.combined_slot_editor_x.set(parts[0])
        self.combined_slot_editor_y.set(parts[1])
        self.combined_slot_editor_z.set(parts[2])

    def _combined_slot_editor_delete(self):
        tree = self.combined_slot_tree
        selected_ids = set(tree.selection()) if tree is not None else set()
        if not selected_ids:
            object_id = self.combined_slot_editor_id.get().strip()
            if object_id:
                selected_ids.add(object_id)
        if selected_ids:
            self._combined_slot_delete(selected_ids)

    @staticmethod
    def _combined_slot_remove_indexed_node(tree, index, object_id):
        """Remove one indexed XML node from its actual parent."""
        node_info = index.get(object_id)
        if node_info is None:
            return False
        node, _children = node_info
        for parent in tree.getroot().iter():
            if node in list(parent):
                parent.remove(node)
                index.pop(object_id, None)
                return True
        return False

    def _combined_slot_delete(self, object_ids):
        """Delete selected IDs from MapName and Gamedata RAM trees; Save persists."""
        if isinstance(object_ids, str):
            object_ids = {object_ids}
        else:
            object_ids = {str(value) for value in object_ids if str(value)}
        existing_ids = {
            object_id for object_id in object_ids
            if object_id in self.combined_slot_map_nodes_by_id
            or object_id in self.combined_slot_game_nodes_by_id
        }
        if not existing_ids:
            messagebox.showwarning(
                "Delete Slots",
                "The selected objects are no longer present in MapName or Gamedata RAM.",
                parent=self.combined_slot_window,
            )
            return
        if not messagebox.askyesno(
            "Delete Slots",
            f"Delete {len(existing_ids)} selected object(s) from MapName and Gamedata?\n\n"
            "The XML files will not be changed until Save is clicked.",
            parent=self.combined_slot_window,
            default="no",
        ):
            return

        removed_map = 0
        removed_game = 0
        for object_id in existing_ids:
            if self._combined_slot_remove_indexed_node(
                self.combined_slot_map_tree,
                self.combined_slot_map_nodes_by_id,
                object_id,
            ):
                removed_map += 1
            if self._combined_slot_remove_indexed_node(
                self.combined_slot_game_tree,
                self.combined_slot_game_nodes_by_id,
                object_id,
            ):
                removed_game += 1
            self.combined_slot_records_by_id.pop(object_id, None)
            self.combined_slot_dirty_ids.discard(object_id)
            self.combined_slot_deleted_ids.add(object_id)

        self.combined_slot_records = [
            record for record in self.combined_slot_records
            if record["id"] not in existing_ids
        ]
        self.combined_slot_editor_id.set("")
        self.combined_slot_editor_guid.set("")
        self.combined_slot_editor_x.set("")
        self.combined_slot_editor_y.set("")
        self.combined_slot_editor_z.set("")
        self._combined_slot_render()
        self._combined_slot_update_summary()
        self.status_var.set(
            f"Marked {len(existing_ids)} object(s) for deletion: "
            f"{removed_map} MapName, {removed_game} Gamedata. Click Save to write XML files."
        )

    def _save_combined_slot_editor(self):
        dirty_ids = set(self.combined_slot_dirty_ids)
        deleted_ids = set(self.combined_slot_deleted_ids)
        if not dirty_ids and not deleted_ids:
            messagebox.showinfo(
                "Slot Editor",
                "There are no unsaved changes.",
                parent=self.combined_slot_window,
            )
            return

        edits = {}
        for object_id in dirty_ids:
            record = self.combined_slot_records_by_id.get(object_id)
            if record is None:
                continue
            guid = record["guid_var"].get().strip()
            pos = " ".join(
                (record["x_var"].get().strip(), record["y_var"].get().strip(), record["z_var"].get().strip())
            )
            if not guid or self._combined_slot_position_parts(pos) is None:
                messagebox.showerror(
                    "Slot Editor",
                    f"Invalid GUID or position for Object ID {object_id}.",
                    parent=self.combined_slot_window,
                )
                return
            edits[object_id] = (guid, pos)

        game_tree = self.combined_slot_game_tree
        map_tree = self.combined_slot_map_tree
        game_target = self.combined_slot_game_target
        map_target = self.combined_slot_map_target
        if game_tree is None or map_tree is None or game_target is None or map_target is None:
            messagebox.showerror(
                "Slot Editor", "The RAM model is not initialized.", parent=self.combined_slot_window
            )
            return

        game_changed = map_guid_changed = position_changed = 0
        for object_id, (guid, pos) in edits.items():
            game_info = self.combined_slot_game_nodes_by_id.get(object_id)
            if game_info is not None:
                _node, children = game_info
                guid_node = children.get("guid")
                position_node = children.get("position")
                if guid_node is not None and (guid_node.text or "").strip() != guid:
                    guid_node.text = guid
                    game_changed += 1
                if position_node is not None and (position_node.text or "").strip() != pos:
                    position_node.text = pos
            map_info = self.combined_slot_map_nodes_by_id.get(object_id)
            if map_info is not None:
                _node, children = map_info
                guid_node = children.get("objectguid")
                position_node = children.get("position")
                if guid_node is not None and (guid_node.text or "").strip() != guid:
                    guid_node.text = guid
                    map_guid_changed += 1
                if position_node is not None and (position_node.text or "").strip() != pos:
                    position_node.text = pos
                    position_changed += 1

        game_tmp = game_target.with_suffix(game_target.suffix + ".tmp")
        map_tmp = map_target.with_suffix(map_target.suffix + ".tmp")
        try:
            game_tree.write(game_tmp, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
            map_tree.write(map_tmp, encoding="utf-8", xml_declaration=False, short_empty_elements=True)
            self._slot_parse_xml(game_tmp)
            self._slot_parse_xml(map_tmp)
            game_tmp.replace(game_target)
            map_tmp.replace(map_target)
        except (OSError, ET.ParseError, UnicodeError) as exc:
            for tmp in (game_tmp, map_tmp):
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
            messagebox.showerror(
                "Slot Editor", f"Could not save both XML files:\n{exc}",
                parent=self.combined_slot_window,
            )
            return

        # Commit the RAM model as the new baseline without reparsing or rebuilding
        # all row widgets. Only clear dirty/deleted state and update visible values.
        for object_id, (guid, pos) in edits.items():
            record = self.combined_slot_records_by_id.get(object_id)
            if record is None:
                continue
            record["guid"] = guid
            record["position"] = pos
            record["game_guid"] = guid if object_id in self.combined_slot_game_nodes_by_id else record["game_guid"]
            record["game_position"] = pos if object_id in self.combined_slot_game_nodes_by_id else record["game_position"]
            record["status"] = "Linked" if object_id in self.combined_slot_game_nodes_by_id else "Mapname only"
        self.combined_slot_dirty_ids.clear()
        self.combined_slot_deleted_ids.clear()

        # Re-read the exact patched files that were just installed. This rebuilds
        # records, XML indexes and Treeview values from disk, so the table cannot
        # retain stale pre-save values and no manual Reload is required.
        self._combined_slot_reload()
        self._refresh_open_slot_map()
        self.status_var.set(
            f"Combined slots saved: {game_changed} gamedata GUID, "
            f"{map_guid_changed} map GUID, {position_changed} position change(s), "
            f"{len(deleted_ids)} deletion(s)"
        )
        messagebox.showinfo(
            "Slot Editor",
            "Both patched files were saved.\n\n"
            f"Dirty records processed: {len(dirty_ids)}\n"
            f"Mapdata deletions: {len(deleted_ids)}\n"
            f"Gamedata GUID changes: {game_changed}\n"
            f"Map GUID changes: {map_guid_changed}\n"
            f"Position changes: {position_changed}",
            parent=self.combined_slot_window,
        )
