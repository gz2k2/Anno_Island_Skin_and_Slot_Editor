"""Reusable profile toolbar and JSON index store.

The toolbar owns selection, naming and confirmation dialogs. Domain adapters
provide callbacks for Load/Add/Save/Delete and serialize their own data.
ProfileArchiveStore supplies the shared directory, naming and safe JSON writes.
No application-specific table, XML format or worker implementation is assumed.
"""
from __future__ import annotations

import json
import queue
import time
import os
import shutil
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk


class ProfileArchiveStore:
    @staticmethod
    def validate_name(name):
        if (not name or name in ('.', '..') or name[-1:] in (' ', '.')
                or any(ord(c) < 32 or c in '<>:"/\\|?*' for c in name)
                or len(name.encode('utf-8')) > 220):
            raise ValueError('Please use a non-empty, valid Windows filename (maximum 220 UTF-8 bytes).')
        reserved = {'CON', 'PRN', 'AUX', 'NUL',
                    *('COM' + str(i) for i in range(1, 10)),
                    *('LPT' + str(i) for i in range(1, 10))}
        if name.split('.')[0].upper() in reserved:
            raise ValueError('This filename is reserved by Windows.')
        return name

    @staticmethod
    def folder(app_directory, namespace):
        ProfileArchiveStore.validate_name(namespace)
        return Path(app_directory).resolve() / 'custom_profiles' / namespace

    @staticmethod
    def catalog(folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        return {p.stem: p for p in sorted(folder.iterdir(), key=lambda p: p.name.casefold())
                if p.is_file() and not p.is_symlink() and p.suffix.casefold() == '.json'}

    @staticmethod
    def revision(path):
        path = Path(path)
        if path.is_symlink():
            raise ValueError('Linked profile files are not supported.')
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns, stat.st_ino


    @staticmethod
    def write_json(target, document, *, overwrite=False, expected_revision=None, progress=None):
        report = progress or (lambda done, total, stage='': None)
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise ValueError('Linked profile files are not supported.')
        report(0, 3, 'Serializing index values...')
        raw = json.dumps(document, ensure_ascii=False, indent=2).encode('utf-8')
        fd, name = tempfile.mkstemp(prefix='.profile_', suffix='.tmp', dir=target.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(raw)
            report(1, 3, 'Validating JSON profile...')
            json.loads(temporary.read_text(encoding='utf-8'))
            if overwrite:
                if expected_revision is None or ProfileArchiveStore.revision(target) != expected_revision:
                    raise ValueError('The selected profile changed. Please retry Save.')
                os.replace(temporary, target)
            else:
                with target.open('xb') as output:
                    try:
                        with temporary.open('rb') as source:
                            shutil.copyfileobj(source, output)
                    except Exception:
                        output.close()
                        target.unlink(missing_ok=True)
                        raise
            report(3, 3, 'Profile saved successfully.')
        finally:
            temporary.unlink(missing_ok=True)


class ProfilesTemplate(ctk.CTkFrame):
    """[Profile dropdown] [Load] [Add] [Delete] [Save]. No inline name entry.

    Callbacks: on_load(name), on_add(suffix), on_save(name), on_delete(name).
    The adapter owns I/O, background work and error reporting. Call set_profiles
    after a completed mutation. The dropdown never invokes on_load by itself.
    can_act() is checked before and after modal dialogs.
    """
    PLACEHOLDER = 'Select profile...'
    DELETE_COLOR = '#B52B2B'
    DELETE_HOVER_COLOR = '#8F2020'

    def __init__(self, master, *, owner, on_load, on_add, on_save, on_delete,
                 can_act=lambda: True, name_prefix=lambda: '', button_height=28,
                 secondary_text_color='gray70', **kwargs):
        super().__init__(master, fg_color='transparent', **kwargs)
        self._owner = owner
        self._callbacks = dict(load=on_load, add=on_add, save=on_save, delete=on_delete)
        self._can_act = can_act
        self._name_prefix = name_prefix
        self._names = set()
        self._progress_busy = False
        self._progress_events = queue.Queue()
        self._progress_after = None
        self._progress_token = 0
        self.selection = tk.StringVar(master=self, value=self.PLACEHOLDER)
        self.grid_columnconfigure(0, weight=1)
        self.menu = ctk.CTkOptionMenu(
            self, variable=self.selection, values=[self.PLACEHOLDER],
            dynamic_resizing=False, command=lambda _name: self._sync_buttons())
        self.menu.grid(row=0, column=0, padx=(0, 8), sticky='ew')
        self.buttons = {}
        for column, (action, label) in enumerate(
                [('load', 'Load'), ('add', 'Add'), ('delete', 'Delete'), ('save', 'Save')], 1):
            style = dict(fg_color=self.DELETE_COLOR, hover_color=self.DELETE_HOVER_COLOR) if action == 'delete' else {}
            button = ctk.CTkButton(
                self, text=label, width=80, height=button_height,
                command=lambda action=action: self._invoke(action), **style)
            button.grid(row=0, column=column, padx=(0, 8) if column < 4 else 0)
            self.buttons[action] = button
        ctk.CTkLabel(
            self, text='Load: apply selected profile | Add: new profile | Save: overwrite selected profile',
            text_color=secondary_text_color, anchor='w', wraplength=800,
        ).grid(row=1, column=0, columnspan=5, pady=(5, 0), sticky='ew')
        self.progress_frame = ctk.CTkFrame(self, fg_color='transparent')
        self.progress_frame.grid(row=2, column=0, columnspan=5, pady=(8, 2), sticky='ew')
        self.progress_frame.grid_columnconfigure(0, weight=1)
        self.progress_text = tk.StringVar(master=self, value='')
        ctk.CTkLabel(self.progress_frame, textvariable=self.progress_text, anchor='w').grid(
            row=0, column=0, pady=(0, 4), sticky='ew')
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.grid(row=1, column=0, sticky='ew')
        self.progress_bar.set(0)
        self.progress_frame.grid_remove()
        self._sync_buttons()

    def set_profiles(self, names, selected=None):
        self._names = set(names)
        value = self.selection.get() if selected is None else selected
        self.menu.configure(values=[self.PLACEHOLDER] + sorted(self._names, key=str.casefold),
                            state='normal' if self._names and not self._progress_busy else 'disabled')
        self.selection.set(value if value in self._names else self.PLACEHOLDER)
        self._sync_buttons()

    def _sync_buttons(self):
        valid = self.selection.get() in self._names and not self._progress_busy
        self.buttons['add'].configure(state='disabled' if self._progress_busy else 'normal')
        self.menu.configure(state='normal' if self._names and not self._progress_busy else 'disabled')
        for action in ('load', 'delete', 'save'):
            self.buttons[action].configure(state='normal' if valid else 'disabled')

    def _invoke(self, action):
        if self._progress_busy or not self._can_act():
            return
        owner = self._owner()
        if action == 'add':
            try:
                prefix = self._name_prefix()
            except ValueError as exc:
                messagebox.showerror('Object Profiles', str(exc), parent=owner)
                return
            dialog = ctk.CTkInputDialog(
                title='Add Profile', text=f'Enter a profile name suffix.\nThe profile will be named: {prefix}_<name>')
            suffix = dialog.get_input()
            if suffix is None:
                return
            suffix = suffix.strip()
            if not suffix:
                messagebox.showerror('Add Profile', 'Please enter a profile name.', parent=owner)
                return
            if self._can_act():
                self._callbacks['add'](suffix)
            return
        name = self.selection.get()
        if name not in self._names:
            messagebox.showinfo('Object Profiles', 'Please select a profile first.', parent=owner)
            return
        if action in ('save', 'delete'):
            title = 'Overwrite Profile' if action == 'save' else 'Delete Profile'
            text = (f'Overwrite profile "{name}" with the current table values?\n\nThe previous profile content will be replaced.'
                    if action == 'save' else f'Delete profile "{name}" permanently?\n\nThis cannot be undone.')
            if not messagebox.askyesno(title, text, parent=owner, default='no'):
                return
        if self._can_act():
            self._callbacks[action](name)

    def track_worker(self, worker, *, label='Saving profile'):
        """Call on UI thread, then submit the returned callable to a worker.

        worker(report) may call report(done, total, optional_stage) from its
        worker thread. Only this template's after callback touches widgets.
        Returned callable accepts the application's existing progress callback.
        """
        if self._progress_busy:
            raise ValueError('A profile save is already in progress.')
        self._progress_token += 1
        token = self._progress_token
        self._progress_busy = True
        self.progress_frame.grid()
        self.progress_bar.configure(mode='determinate')
        self.progress_bar.set(0)
        self.progress_text.set(label + '... 0%')
        self._sync_buttons()
        self._progress_after = self.after(50, self._poll_profile_progress)
        events = self._progress_events
        def wrapped(application_progress):
            last = [0.0]
            def report(done, total, stage=''):
                fraction = max(0.0, min(1.0, done / total)) if total else None
                now = time.monotonic()
                if done == 0 or done == total or now - last[0] >= 0.05:
                    last[0] = now
                    events.put((token, 'progress', (fraction, stage or label)))
                    application_progress(done, total)
            try:
                result = worker(report)
            except BaseException as exc:
                events.put((token, 'failed', str(exc)))
                raise
            events.put((token, 'finished', label + ' completed.'))
            return result
        return wrapped

    def _poll_profile_progress(self):
        self._progress_after = None
        for _ in range(100):
            try:
                token, kind, payload = self._progress_events.get_nowait()
            except queue.Empty:
                break
            if token != self._progress_token:
                continue
            if kind == 'progress':
                fraction, text = payload
                self.progress_bar.stop()
                if fraction is None:
                    self.progress_bar.configure(mode='indeterminate')
                    self.progress_bar.start()
                    self.progress_text.set(text)
                else:
                    self.progress_bar.configure(mode='determinate')
                    self.progress_bar.set(fraction)
                    self.progress_text.set(f'{text} ({int(fraction * 100)}%)')
            else:
                self._progress_busy = False
                self.progress_bar.stop()
                self.progress_bar.configure(mode='determinate')
                self.progress_bar.set(1 if kind == 'finished' else 0)
                self.progress_text.set(payload if kind == 'finished' else 'Profile save failed: ' + payload)
                self._sync_buttons()
        if self._progress_busy or not self._progress_events.empty():
            self._progress_after = self.after(50, self._poll_profile_progress)

    def destroy(self):
        if self._progress_after is not None:
            try:
                self.after_cancel(self._progress_after)
            except tk.TclError:
                pass
            self._progress_after = None
        super().destroy()

    def notify_loaded(self, name):
        """UI-thread completion hook: call only AFTER applying loaded data.

        Kept separate from on_load because adapters may load asynchronously.
        Errors/cancelled or rejected loads must never call this hook.
        """
        owner = self._owner()
        messagebox.showinfo(
            'Profile Loaded',
            f'Profile "{name}" loaded successfully.',
            parent=owner if owner is not None and owner.winfo_exists() else self,
        )

    def confirm_map_load(self, profile_map, current_map):
        """Reusable UI-thread guard before applying a profile to another map.

        Matching maps proceed without a dialog. A mismatch is a warning, not
        a validation error: OK permits loading, Cancel leaves data unchanged.
        Table/index/data validation remains the responsibility of the adapter.
        """
        if profile_map == current_map:
            return True
        owner = self._owner()
        return messagebox.askokcancel(
            'Profile Map Warning',
            f'This profile was created for map "{profile_map}".\n'
            f'The currently loaded map is "{current_map}".\n\n'
            'The original object data may differ. Values will be applied by index.\n'
            'Click OK to load the profile anyway, or Cancel to leave the table unchanged.',
            icon='warning', default='cancel',
            parent=owner if owner is not None and owner.winfo_exists() else self,
        )
