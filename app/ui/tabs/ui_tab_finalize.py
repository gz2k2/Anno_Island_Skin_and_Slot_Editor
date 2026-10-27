from __future__ import annotations

import shutil
import subprocess
import threading
import time
from pathlib import Path
from tkinter import filedialog, messagebox

from app.functions.function_map_export import export_map, validate_export_paths, MapExportCancelled
from app.functions.function_custom_content import load_custom_objects

import customtkinter as ctk
from app.templates.template_statuswindow import StatusWindowTemplate


class FinalizeTabMixin:
    """Standalone Finalize workflow.

    The tab intentionally owns its widgets, state, validation, cleanup, worker,
    logging, binary installation, TMC discovery and backup behavior. It does
    not call the Pack tab builder, Pack buttons, Pack progress bar, Pack log,
    _start_pack, _pack_worker, _pack_tmc_files or _delete_pack_xml_files.
    """

    def _build_finalize_tab(self, tab):
        import tkinter as tk

        self.finalize_backup_var = tk.BooleanVar(value=self.backup_var.get())
        self._finalize_status_popup = None
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(4, weight=1)

        source = ctk.CTkFrame(tab)
        source.grid(row=0, column=0, padx=5, pady=(5, 10), sticky="ew")
        source.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(source, text="A7M file:").grid(
            row=0, column=0, padx=(15, 8), pady=14, sticky="w"
        )
        ctk.CTkEntry(
            source, textvariable=self.unpack_file_var, state="disabled"
        ).grid(row=0, column=1, padx=(8, 15), pady=14, sticky="ew")


        info = ctk.CTkFrame(tab)
        info.grid(row=1, column=0, padx=5, pady=(0, 10), sticky="ew")
        ctk.CTkLabel(
            info,
            text=(
                "A7M file and Meshes folder are taken directly from the Files and Folders tab. "
                "Finalize uses complete *_patched.xml files to rebuild gamedata.data, rd3d.data, "
                "changed TMC files, the A7M file and, when available, A7MINFO."
            ),
            justify="left", wraplength=960, text_color="gray75",
        ).pack(anchor="w", padx=15, pady=12)

        options = ctk.CTkFrame(tab)
        options.grid(row=2, column=0, padx=5, pady=(0, 10), sticky="ew")
        ctk.CTkCheckBox(
            options, text="Back up existing binary files",
            variable=self.finalize_backup_var,
        ).pack(side="left", padx=15, pady=12)

        self.finalize_export_material_btn = ctk.CTkButton(
            options, text="Export custom content files", width=230,
            command=self._export_finalize_custom_content,
        )
        self.finalize_export_material_btn.pack(side="right", padx=15, pady=12)

        controls = ctk.CTkFrame(tab, fg_color="transparent")
        controls.grid(row=3, column=0, padx=5, pady=(0, 10), sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        self.finalize_progress = ctk.CTkProgressBar(controls)
        self.finalize_progress.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.finalize_progress.set(0)
        self.finalize_cleanup_btn = ctk.CTkButton(
            controls, text="CleanUp", width=145,
            fg_color="#8a5a24", hover_color="#6f471c",
            command=self._cleanup_finalize_files,
        )
        self.finalize_cleanup_btn.grid(row=0, column=1, padx=5)
        self.finalize_btn = ctk.CTkButton(
            controls, text="Pack Island Data", width=155,
            command=self._start_finalize,
        )
        self.finalize_btn.grid(row=0, column=2, padx=5)
        self.finalize_export_map_btn = ctk.CTkButton(
            controls, text="Export Map", width=120,
            command=self._start_export_map,
        )
        self.finalize_export_map_btn.grid(row=0, column=3, padx=5)
        self.finalize_stop_btn = ctk.CTkButton(
            controls, text="Stop immediately", width=130, state="disabled",
            fg_color="#a83232", hover_color="#852626", command=self._stop,
        )
        self.finalize_stop_btn.grid(row=0, column=4, padx=(5, 0))
        self.finalize_log = self._create_log(tab, 4)




    def _show_finalize_status(self, text):
        StatusWindowTemplate.close(getattr(self, "_finalize_status_popup", None))
        self._finalize_status_popup = StatusWindowTemplate.create(
            self, text=text, title="Status", heading="Status",
            modal=False, topmost=True,
        )

    def _watch_finalize_status(self):
        popup = getattr(self, "_finalize_status_popup", None)
        if popup is None:
            return
        worker = getattr(self, "worker", None)
        if worker is not None and worker.is_alive():
            self.after(100, self._watch_finalize_status)
            return
        self._finalize_status_popup = None
        StatusWindowTemplate.close(popup)

    def _resolve_finalize_island(self):
        selected = Path(self.unpack_file_var.get().strip())
        if not selected.is_file() or selected.suffix.casefold() != ".a7m":
            raise ValueError(
                "Please select an existing A7M file in the Files and Folders tab first."
            )
        root = selected.parent
        data_dir = root / selected.stem
        if not data_dir.is_dir():
            raise ValueError(f"The unpacked data folder was not found:\n{data_dir}")
        return root, selected, data_dir


    def _start_finalize(self):
        if self._busy():
            return
        try:
            root, a7m_file, data_dir = self._resolve_finalize_island()
        except ValueError as exc:
            messagebox.showerror("Finalize", str(exc))
            return
        meshes = Path(self.tmc_data_meshes_var.get().strip())
        if not meshes.is_dir():
            messagebox.showerror(
                "Finalize",
                "Please select an existing Meshes folder in the Files and Folders tab first."
            )
            return
        errors = self._validate_settings()
        if errors:
            self._show_settings_errors(errors)
            return
        self._show_finalize_status("Packing Island Data....")
        self.stop_event.clear()
        self.finalize_progress.set(0)
        self._clear_log(self.finalize_log)
        self._set_running(True, "finalize")
        self.status_var.set("Preparing finalization...")
        self.worker = threading.Thread(
            target=self._finalize_worker,
            args=(root, a7m_file, data_dir),
            daemon=True,
        )
        self.worker.start()
        self.after(100, self._watch_finalize_status)

    def _finalize_backup(self, path: Path):
        backup = path.with_name(f"{path.stem}_original{path.suffix}")
        if backup.exists():
            stamp = time.strftime("%Y%m%d_%H%M%S")
            backup = path.with_name(f"{path.stem}_backup_{stamp}{path.suffix}")
        shutil.copy2(path, backup)
        self._event("log_finalize", f"Backup: {backup.name}\n")

    def _finalize_install_binary(self, source: Path, destination: Path):
        if source.resolve() == destination.resolve():
            return
        if self.finalize_backup_var.get() and destination.exists():
            self._finalize_backup(destination)
        self._rename_replace(source, destination)

    def _run_finalize_tmc_quiet(self, command, cwd):
        """Run FileDBReader quietly; only a short diagnostic tail is kept on errors."""
        startupinfo = None
        creationflags = 0
        if __import__("os").name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NO_WINDOW
        process = subprocess.Popen(
            [str(value) for value in command], cwd=str(cwd),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            startupinfo=startupinfo, creationflags=creationflags,
        )
        self.process = process
        tail = []
        assert process.stdout is not None
        for line in process.stdout:
            tail.append(line.rstrip())
            if len(tail) > 12:
                tail.pop(0)
            if self.stop_event.is_set():
                self._kill_process()
                raise RuntimeError("Stop requested")
        code = process.wait()
        self.process = None
        if code != 0:
            details = "\n".join(tail)
            raise RuntimeError(
                f"TMC packing failed with exit code {code}."
                + (f"\n{details}" if details else "")
            )

    def _finalize_tmc_files(self):
        meshes = Path(self.tmc_data_meshes_var.get().strip())
        if not meshes.is_dir():
            raise RuntimeError(
                "The Meshes folder from Files and Folders does not exist:\n"
                f"{meshes if str(meshes) != '.' else '(no folder selected)'}"
            )
        patched_files = sorted(meshes.rglob("*_patched.xml"), key=lambda path: str(path).casefold())
        self._event("log_finalize", f"TMC files to pack: {len(patched_files)}\n")
        for patched in patched_files:
            if self.stop_event.is_set():
                raise RuntimeError("Stop requested")
            base_name = patched.name[:-len("_patched.xml")]
            generated = patched.with_name(f"{patched.stem}.tmc")
            target = patched.with_name(f"{base_name}.tmc")
            if generated.exists():
                generated.unlink()
            self._run_finalize_tmc_quiet([
                self.fdb_var.get(), "compress", "-f", str(patched), "-c", "3",
                "-i", self.tmc_format_var.get(), "-o", ".tmc", "-y",
            ], patched.parent)
            if not generated.is_file() or generated.stat().st_size == 0:
                raise RuntimeError(f"No valid TMC file was created from {patched.name}.")
            self._finalize_install_binary(generated, target)
        self._event("log_finalize", f"TMC packing completed: {len(patched_files)} file(s).\n")



    def _finalize_worker(self, root: Path, a7m_file: Path, data_dir: Path):
        ok = False
        try:
            self._event("status", f"Finalizing {a7m_file.name}...")
            self._event("log_finalize", f"Island root: {root}\nData folder: {data_dir}\nTarget file: {a7m_file}\n\n")
            game_patched = data_dir / "gamedata_patched.xml"
            game_original = data_dir / "gamedata_original.xml"
            rd3d_patched = data_dir / "rd3d_patched.xml"
            rd3d_original = data_dir / "rd3d_original.xml"

            if game_patched.is_file():
                game_source = game_patched
            elif game_original.is_file():
                game_source = game_original
                self._event("log_finalize_colored", ("WARNING: gamedata_patched.xml not found. Using gamedata_original.xml.\n", "#FFD166"))
            else:
                raise RuntimeError("Neither gamedata_patched.xml nor gamedata_original.xml was found.")

            if rd3d_patched.is_file():
                rd3d_source = rd3d_patched
            elif rd3d_original.is_file():
                rd3d_source = rd3d_original
                self._event("log_finalize_colored", ("WARNING: rd3d_patched.xml not found. Using rd3d_original.xml.\n", "#FFD166"))
            else:
                raise RuntimeError("Neither rd3d_patched.xml nor rd3d_original.xml was found.")

            game_xml = data_dir / "gamedata.xml"
            rd3d_xml = data_dir / "rd3d.xml"
            shutil.copy2(game_source, game_xml)
            shutil.copy2(rd3d_source, rd3d_xml)
            self._event("log_finalize", f"Gamedata source: {game_source.name}\n")
            self._event("log_finalize", f"RD3D source: {rd3d_source.name}\n")
            self._event("progress_finalize", 0.30)

            game_data = self._compress_data(game_xml, self.gamedata_format_var.get(), data_dir, "finalize")
            rd3d_data = self._compress_data(rd3d_xml, self.rd3d_format_var.get(), data_dir, "finalize")
            self._event("progress_finalize", 0.55)

            self._finalize_tmc_files()
            self._event("progress_finalize", 0.68)

            final_game = data_dir / "gamedata.data"
            final_rd3d = data_dir / "rd3d.data"
            self._finalize_install_binary(game_data, final_game)
            self._finalize_install_binary(rd3d_data, final_rd3d)
            if self.finalize_backup_var.get() and a7m_file.exists():
                self._finalize_backup(a7m_file)
            self._run([
                self.rda_var.get(), "pack", "-f", str(final_game), str(final_rd3d),
                "-o", str(a7m_file), "-y", "-v", "2",
            ], root, "finalize")
            self._event("progress_finalize", 0.84)

            info_patched = root / f"{a7m_file.stem}_patched.xml"
            if info_patched.is_file():
                info_xml = root / f"{a7m_file.stem}.xml"
                shutil.copy2(info_patched, info_xml)
                info_output = self._compress_a7minfo(info_xml, root, "finalize")
                final_info = a7m_file.with_suffix(".a7minfo")
                self._finalize_install_binary(info_output, final_info)
                self._event("log_finalize", f"A7MINFO rebuilt: {final_info.name}\n")
            else:
                self._event("log_finalize", f"A7MINFO skipped: {info_patched.name} is missing.\n")

            self._event("progress_finalize", 1.0)
            self._event("log_finalize", "\nFinalization completed successfully.\n")
            ok = True
        except Exception as exc:
            self._event("log_finalize", f"\nERROR: {exc}\n")
        finally:
            self._event("done", ("finalize", ok, self.stop_event.is_set()))

    def _cleanup_finalize_files(self):
        if self._busy():
            return
        try:
            root, _a7m_file, _data_dir = self._resolve_finalize_island()
        except ValueError as exc:
            messagebox.showerror("Finalize CleanUp", str(exc))
            return
        files = sorted(
            (
                path for path in root.rglob("*") if path.is_file()
                and (
                    path.suffix.casefold() in {".xml", ".data"}
                    or "_backup" in path.name.casefold()
                    or "_original" in path.name.casefold()
                )
            ),
            key=lambda path: str(path).casefold(),
        )
        if not files:
            messagebox.showinfo("Finalize CleanUp", f"No cleanup files were found in:\n{root}")
            return
        if not messagebox.askyesno(
            "Finalize CleanUp",
            f"Delete {len(files)} cleanup file(s) in:\n{root}\n\nThis cannot be undone.",
        ):
            return
        deleted, errors = 0, []
        for path in files:
            try:
                path.unlink()
                deleted += 1
            except OSError as exc:
                errors.append(f"{path}: {exc}")
        self.status_var.set(f"Finalize CleanUp: deleted {deleted} file(s)")
        if errors:
            messagebox.showwarning("Finalize CleanUp", f"Deleted: {deleted}\nFailed: {len(errors)}\n\n" + "\n".join(errors[:10]))
        else:
            messagebox.showinfo("Finalize CleanUp", f"Deleted files: {deleted}\n\nMap folder:\n{root}")

    def _finalize_used_object_paths(self):
        """Return current Object Tables 1 and 2 paths, including unsaved RAM edits."""
        values = []

        # Objects Table 1 / Object Map: prefer the active edit session, then the
        # editable table variables, and finally the RD3D cache.
        session = getattr(self, '_map_edit_session', None)
        if session is not None:
            values.extend(path for path in session.paths() if path)
        else:
            rows = getattr(self, 'object_configuration_table1_rows', ())
            for row in rows:
                try:
                    value = row[2].get().strip()
                except (AttributeError, IndexError, TypeError):
                    continue
                if value:
                    values.append(value)
            if not rows:
                cache = getattr(self, 'rd3d_ram_cache', None)
                if cache is not None:
                    values.extend(path for path in cache.values if path)

        # Objects Table 2: row layout is
        # (index, object_id, original_path, reference_count, editable_path_var).
        # Reading the StringVar includes unsaved TMC path changes.
        for row in getattr(self, 'object_configuration_table2_rows', ()):
            try:
                value = row[4].get().strip()
            except (AttributeError, IndexError, TypeError):
                continue
            if value:
                values.append(value)

        # Keep source order while avoiding repeated file lookups and exports.
        return tuple(dict.fromkeys(values))

    @staticmethod
    def _finalize_find_custom_object_file(root, object_path):
        """Resolve one game object path inside the configured custom-object folder."""
        root = Path(root)
        normalized = str(object_path or '').strip().replace('\\', '/').lstrip('/')
        if not normalized or not root.is_dir():
            return None
        direct = root.joinpath(*normalized.split('/'))
        if direct.is_file():
            return direct
        # A configured folder may already represent the game's data directory.
        parts = normalized.split('/')
        if parts and parts[0].casefold() == 'data':
            without_data = root.joinpath(*parts[1:])
            if without_data.is_file():
                return without_data
        basename = Path(normalized).name.casefold()
        matches = [
            candidate for candidate in root.rglob('*')
            if candidate.is_file() and candidate.name.casefold() == basename
        ]
        return matches[0] if len(matches) == 1 else None

    def _export_finalize_custom_content(self):
        """Export the selected material set and currently used custom object files."""
        if self._busy():
            return

        export_items = []
        missing = []

        selected = self.regional_material_set_dropdown_var.get().strip()
        if selected and selected not in {
            'Select XML...', 'No XML files found', 'No material set files found'
        }:
            source = self._find_material_set_dropdown_file(selected)
            if source is None or not Path(source).is_file():
                missing.append(f'Material Set: {selected}')
            else:
                source = Path(source)
                export_items.append((
                    source,
                    Path('data/config/engine/material_sets') / f'{source.stem}.materialset',
                    'Material Set',
                ))
                export_items.append((
                    None,
                    Path('data/config/engine/material_sets') / f'{source.stem}.xml.lnk',
                    f'data/config/engine/material_sets/{source.stem}.materialset',
                ))

        custom_rows = load_custom_objects(self.CONFIG_FILE)
        custom_by_path = {
            row['object'].strip().casefold(): row['object'].strip()
            for row in custom_rows if row.get('object', '').strip()
        }
        used_custom_paths = sorted({
            custom_by_path[path.strip().casefold()]
            for path in self._finalize_used_object_paths()
            if path.strip().casefold() in custom_by_path
        }, key=str.casefold)

        custom_root_text = self.custom_objects_folder_var.get().strip()
        custom_root = Path(custom_root_text).expanduser() if custom_root_text else None
        if used_custom_paths and (custom_root is None or not custom_root.is_dir()):
            missing.append('Custom Objects Folder is not configured or does not exist.')
        elif custom_root is not None:
            for object_path in used_custom_paths:
                source = self._finalize_find_custom_object_file(custom_root, object_path)
                if source is None:
                    missing.append(f'Custom Object: {object_path}')
                    continue
                try:
                    relative = source.relative_to(custom_root)
                except ValueError:
                    relative = Path(source.name)
                export_items.append((source, Path('custom_objects') / relative, 'Custom Object'))

        if missing:
            messagebox.showerror(
                'Export Custom Content Files',
                'The following selected or used custom content files were not found:\n\n'
                + '\n'.join(f'- {item}' for item in missing),
            )
            return
        if not export_items:
            messagebox.showinfo(
                'Export Custom Content Files',
                'No selected Material Set or used Custom Content > Objects files were found.',
            )
            return

        destination = filedialog.askdirectory(title='Export custom content files')
        if not destination:
            return
        folder = Path(destination)
        targets = [folder / relative for _source, relative, _kind in export_items]
        existing = [target for target in targets if target.exists()]
        if existing and not messagebox.askyesno(
            'Export Custom Content Files',
            'Overwrite existing export files?\n\n' + '\n'.join(str(path) for path in existing),
        ):
            return

        exported = []
        try:
            for source, relative, kind in export_items:
                target = folder / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if source is None:
                    target.write_text(kind, encoding='utf-8')
                elif source.resolve() != target.resolve():
                    shutil.copy2(source, target)
                exported.append(target)
        except (OSError, shutil.Error) as exc:
            messagebox.showerror('Export Custom Content Files', f'Export failed:\n{exc}')
            return

        details = '\n'.join(str(path) for path in exported)
        self._event('log_finalize', f'Custom content files exported:\n{details}\n')
        self.status_var.set(f'Custom content exported: {len(exported)} file(s)')
        messagebox.showinfo(
            'Export Custom Content Files',
            f'Files exported: {len(exported)}\n\n{details}',
        )

    def _start_export_map(self):
        if self._busy():
            return
        selected = self.unpack_file_var.get().strip()
        a7m = Path(selected) if selected else None
        if a7m is None or not a7m.is_file() or a7m.suffix.casefold() != '.a7m':
            messagebox.showerror('Export Map', 'Select an existing A7M file in Files and Folders first.')
            return
        folder = self.map_export_folder_var.get().strip()
        if not folder:
            self.tabs.set('Settings')
            messagebox.showerror('Export Map', 'Please configure Map export folder in Settings first.')
            return
        try:
            source, destination = validate_export_paths(a7m.parent, Path(folder).expanduser() / a7m.stem)
            if destination.exists() and not destination.is_dir():
                raise ValueError(f'The export destination is not a folder: {destination}')
        except (OSError, ValueError) as exc:
            messagebox.showerror('Export Map', str(exc))
            return
        overwrite = destination.exists()
        if overwrite and not messagebox.askyesno(
            'Export Map',
            'Replace this existing exported map folder completely?\n\n'
            f'{destination}\n\nOnly this map subfolder will be replaced. Other exports remain untouched.',
        ):
            return
        if not self._save_config():
            return
        self._show_finalize_status("Exporting Map....")
        self.stop_event.clear()
        self.finalize_progress.set(0)
        self._clear_log(self.finalize_log)
        self._set_running(True, 'finalize')
        self.status_var.set('Preparing map export...')
        self.worker = threading.Thread(
            target=self._export_map_worker,
            args=(source, destination, overwrite), daemon=True, name='MapExport',
        )
        self.worker.start()
        self.after(100, self._watch_finalize_status)

    def _export_map_worker(self, source, destination, overwrite):
        ok = False
        try:
            self._event('log_finalize',
                f'Export Map\nSource: {source}\nTarget: {destination}\n'
                'Excluded: *.xml, *_original*, backup files/folders.\n'
                'This copies existing files only. Run Pack Island Data first to include XML edits.\n\n')
            def progress(done, total, relative, count, files):
                fraction = min(1.0, done / total) if total else (count / files if files else 0.0)
                self._event('progress_finalize', fraction)
                self._event('status', f'Export Map: {count}/{files} files | {relative}')
            count, size, warnings = export_map(
                source, destination, self.stop_event, progress, overwrite=overwrite)
            for warning in warnings:
                self._event('log_finalize', 'WARNING: ' + warning + '\n')
            self._event('progress_finalize', 1.0)
            self._event('log_finalize_colored', (
                f'\nMap exported successfully: {count} files, {size:,} bytes.\nTarget: {destination}\n', '#26DE81'))
            ok = True
        except MapExportCancelled as exc:
            self._event('log_finalize', f'\nCancelled: {exc}\n')
        except Exception as exc:
            self._event('log_finalize', f'\nERROR: Map export failed: {exc}\n')
        finally:
            self._event('done', ('finalize', ok, self.stop_event.is_set()))
