from __future__ import annotations
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

class FilesAndFoldersTabMixin:
    def _build_files_and_folders_tab(self, tab):
        tab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(tab, text="Files and Folders", font=ctk.CTkFont(size=22, weight="bold")).grid(row=0,column=0,padx=20,pady=(20,8),sticky="w")
        content=ctk.CTkFrame(tab); content.grid(row=1,column=0,padx=20,pady=(0,20),sticky="new"); content.grid_columnconfigure(1,weight=1)
        ctk.CTkLabel(content,text="Select the A7M file to auto-detect all related files and folders. You can also select individual paths manually.",text_color="gray70",justify="left").grid(row=0,column=0,columnspan=3,padx=16,pady=(14,10),sticky="w")
        ctk.CTkLabel(content,text="A7M file:",font=ctk.CTkFont(weight="bold")).grid(row=1,column=0,padx=(16,8),pady=7,sticky="w")
        ctk.CTkEntry(content,textvariable=self.unpack_file_var).grid(row=1,column=1,padx=8,pady=7,sticky="ew")
        ctk.CTkButton(content,text="Browse",width=110,command=self._select_files_folders_a7m).grid(row=1,column=2,padx=(8,16),pady=7)
        self._files_folders_file_row(content,2,"gamedata_original.xml:",self.gamedata_file_var,"Select gamedata_original.xml","gamedata_original.xml")
        self._files_folders_file_row(content,3,"mapname_original.xml:",self.mapname_file_var,"Select mapname_original.xml","*_original.xml")
        self._files_folders_file_row(content,4,"rd3d_original.xml:",self.rd3d_file_var,"Select rd3d_original.xml","rd3d_original.xml")
        self._files_folders_folder_row(content,5,"Meshes folder:",self.tmc_data_meshes_var,"Select Meshes folder")
        self._build_xml_loading_indicator(tab, 2)

    def _files_folders_file_row(self,parent,row,label,variable,title,pattern):
        ctk.CTkLabel(parent,text=label).grid(row=row,column=0,padx=(16,8),pady=7,sticky="w")
        ctk.CTkEntry(parent,textvariable=variable).grid(row=row,column=1,padx=8,pady=7,sticky="ew")
        def browse():
            current=Path(variable.get().strip()) if variable.get().strip() else None
            value=filedialog.askopenfilename(title=title,initialdir=str(current.parent) if current and current.parent.is_dir() else None,filetypes=[("XML",pattern),("XML files","*.xml"),("All files","*.*")])
            if value:
                variable.set(value)
                if variable is self.gamedata_file_var:
                    self._load_gamedata_xml(show_errors=False)
                    self._refresh_slot_configuration_from_files()
                elif variable is self.rd3d_file_var:
                    self._load_rd3d_xml(show_errors=False)
                    self._rd3d_ram_preload()
        ctk.CTkButton(parent,text="Browse",width=110,command=browse).grid(row=row,column=2,padx=(8,16),pady=7)
    def _files_folders_folder_row(self,parent,row,label,variable,title):
        ctk.CTkLabel(parent,text=label).grid(row=row,column=0,padx=(16,8),pady=7,sticky="w")
        ctk.CTkEntry(parent,textvariable=variable).grid(row=row,column=1,padx=8,pady=7,sticky="ew")
        def browse():
            current=variable.get().strip(); value=filedialog.askdirectory(title=title,initialdir=current if current and Path(current).is_dir() else None)
            if value: variable.set(value); self._tmc_ram_preload()
        ctk.CTkButton(parent,text="Browse",width=110,command=browse).grid(row=row,column=2,padx=(8,16),pady=7)
