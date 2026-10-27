from pathlib import Path
import re
import customtkinter as ctk
from tkinter import filedialog, messagebox

# CustomTkinter Design-Einstellungen
ctk.set_appearance_mode("System")  # "System", "Dark", "Light"
ctk.set_default_color_theme("blue")

class ProjectUnpackerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Project Bundle Unpacker")
        self.geometry("680, 480")
        self.resizable(False, False)

        # Titel
        self.title_label = ctk.CTkLabel(
            self, 
            text="Project Bundle Unpacker", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(pady=(20, 15))

        # --- Source File Auswahl ---
        self.source_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.source_frame.pack(fill="x", padx=30, pady=10)

        self.source_label = ctk.CTkLabel(self.source_frame, text="Bundle-Datei (.txt):", anchor="w", width=140)
        self.source_label.pack(side="left")

        self.source_entry = ctk.CTkEntry(self.source_frame, width=360)
        self.source_entry.pack(side="left", padx=(0, 10))

        self.source_btn = ctk.CTkButton(self.source_frame, text="Durchsuchen", width=90, command=self.browse_source)
        self.source_btn.pack(side="left")

        # --- Target Folder Auswahl ---
        self.target_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.target_frame.pack(fill="x", padx=30, pady=10)

        self.target_label = ctk.CTkLabel(self.target_frame, text="Zielordner:", anchor="w", width=140)
        self.target_label.pack(side="left")

        self.target_entry = ctk.CTkEntry(self.target_frame, width=360)
        self.target_entry.pack(side="left", padx=(0, 10))

        self.target_btn = ctk.CTkButton(self.target_frame, text="Durchsuchen", width=90, command=self.browse_target)
        self.target_btn.pack(side="left")

        # --- Start Button ---
        self.unpack_btn = ctk.CTkButton(
            self, 
            text="Projekt entpacken", 
            font=ctk.CTkFont(size=15, weight="bold"), 
            height=40, 
            command=self.unpack_bundle_action
        )
        self.unpack_btn.pack(pady=20)

        # --- Log / Status Box ---
        self.status_textbox = ctk.CTkTextbox(self, height=140, width=600)
        self.status_textbox.pack(padx=30, pady=(0, 20))
        self.status_textbox.insert("0.0", "Bereit. Bitte Bundle-Datei und Zielordner auswählen.\n")
        self.status_textbox.configure(state="disabled")

    def browse_source(self):
        filename = filedialog.askopenfilename(
            title="Projekt-Bundle auswählen",
            filetypes=[("Text Dateien", "*.txt"), ("Alle Dateien", "*.*")]
        )
        if filename:
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, filename)

    def browse_target(self):
        foldername = filedialog.askdirectory(title="Zielordner auswählen")
        if foldername:
            self.target_entry.delete(0, "end")
            self.target_entry.insert(0, foldername)

    def log(self, message):
        self.status_textbox.configure(state="normal")
        self.status_textbox.insert("end", message + "\n")
        self.status_textbox.see("end")
        self.status_textbox.configure(state="disabled")

    def unpack_bundle_action(self):
        source_path_str = self.source_entry.get().strip()
        target_path_str = self.target_entry.get().strip()

        if not source_path_str or not target_path_str:
            messagebox.showerror("Fehler", "Bitte sowohl eine Quelldatei als auch einen Zielordner angeben!")
            return

        bundle_path = Path(source_path_str)
        target_dir = Path(target_path_str)

        if not bundle_path.exists() or not bundle_path.is_file():
            messagebox.showerror("Fehler", f"Die Quelldatei existiert nicht:\n{bundle_path}")
            return

        try:
            self.log(f"\nStarte Entpacken von: {bundle_path.name}")
            text = bundle_path.read_text(encoding="utf-8")
            
            lines = text.splitlines(keepends=True)
            i = 0
            count = 0
            
            while i < len(lines):
                line = lines[i]
                if line.startswith("===== FILE: "):
                    match = re.match(r"^===== FILE: (.+?) =====\r?\n?$", line)
                    if match:
                        rel_path = match.group(1)
                        i += 1
                        file_content_lines = []
                        end_marker = f"===== END FILE: {rel_path} ====="
                        
                        while i < len(lines):
                            curr_line = lines[i]
                            if curr_line.strip() == end_marker:
                                break
                            file_content_lines.append(curr_line)
                            i += 1
                        
                        # Ziel-Dateipfad im Ordner erstellen
                        target_file = target_dir / rel_path
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        file_content = "".join(file_content_lines)
                        target_file.write_text(file_content, encoding="utf-8")
                        self.log(f"Wiederhergestellt: {rel_path}")
                        count += 1
                i += 1

            self.log(f"Erfolgreich! {count} Dateien wurden nach '{target_dir}' extrahiert.")
            messagebox.showinfo("Erfolg", f"Projekt erfolgreich entpackt!\nEs wurden {count} Dateien wiederhergestellt.")

        except Exception as e:
            self.log(f"Fehler beim Entpacken: {str(e)}")
            messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten:\n{str(e)}")

if __name__ == "__main__":
    app = ProjectUnpackerApp()
    app.mainloop()