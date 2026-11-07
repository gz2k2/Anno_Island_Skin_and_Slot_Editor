import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.ui.tabs import ui_tab_finalize
from app.ui.tabs.ui_tab_finalize import FinalizeTabMixin


class _Value:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _FinalizeHarness(FinalizeTabMixin):
    def _busy(self):
        return False

    def _finalize_used_object_paths(self):
        return self.used_object_paths

    def _event(self, *_args):
        pass


class FinalizeExportTests(unittest.TestCase):
    def test_custom_content_export_includes_only_used_custom_objects(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            custom_root = root / "custom"
            source = custom_root / "data" / "custom_objects" / "island.xml"
            source.parent.mkdir(parents=True)
            source.write_text("<Root />", encoding="utf-8")
            destination = root / "export"
            destination.mkdir()

            app = _FinalizeHarness()
            app.CONFIG_FILE = root / "config.ini"
            app.custom_objects_folder_var = _Value(str(custom_root))
            app.custom_material_sets_folder_var = _Value()
            app.used_object_paths = ("data/custom_objects/island.xml",)
            app.status_var = _Value()

            with (
                patch.object(
                    ui_tab_finalize,
                    "load_custom_objects",
                    return_value=[{"object": "data/custom_objects/island.xml"}],
                ),
                patch.object(
                    ui_tab_finalize.filedialog,
                    "askdirectory",
                    return_value=str(destination),
                ),
                patch.object(ui_tab_finalize.messagebox, "showinfo"),
            ):
                app._export_finalize_custom_content()

            exported = [path for path in destination.rglob("*") if path.is_file()]
            self.assertEqual(1, len(exported))
            self.assertEqual("island.xml", exported[0].name)
            self.assertIn("custom_objects", exported[0].parts)

    def test_custom_content_export_includes_material_set_files_and_links(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            custom_material_sets = root / "custom-material-sets"
            custom_material_sets.mkdir()
            (custom_material_sets / "alpine.materialset").write_text(
                "materialset source", encoding="utf-8"
            )
            (custom_material_sets / "alpine.xml").write_text(
                "xml fallback", encoding="utf-8"
            )
            (custom_material_sets / "coastal.xml").write_text(
                "xml materialset", encoding="utf-8"
            )
            destination = root / "export"
            destination.mkdir()

            app = _FinalizeHarness()
            app.CONFIG_FILE = root / "config.ini"
            app.custom_objects_folder_var = _Value()
            app.custom_material_sets_folder_var = _Value(str(custom_material_sets))
            app.used_object_paths = ()
            app.status_var = _Value()

            with (
                patch.object(ui_tab_finalize, "load_custom_objects", return_value=[]),
                patch.object(
                    ui_tab_finalize.filedialog,
                    "askdirectory",
                    return_value=str(destination),
                ),
                patch.object(ui_tab_finalize.messagebox, "showinfo"),
            ):
                app._export_finalize_custom_content()

            material_sets_dir = destination / "data" / "config" / "engine" / "material_sets"
            self.assertEqual(
                "materialset source",
                (material_sets_dir / "alpine.materialset").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "data/config/engine/material_sets/alpine.materialset",
                (material_sets_dir / "alpine.xml.lnk").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "xml materialset",
                (material_sets_dir / "coastal.materialset").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "data/config/engine/material_sets/coastal.materialset",
                (material_sets_dir / "coastal.xml.lnk").read_text(encoding="utf-8"),
            )

    def test_editor_mod_export_copies_complete_bundled_package(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            bundle = root / "bundle"
            mod_folder = root / "Anno 1800" / "Mod"
            source = (
                bundle / "data" / "gamedata"
                / "[IslandEditor] ModFiles [gz2k2]"
            )
            (source / "data" / "gamedata").mkdir(parents=True)
            (source / "modinfo.json").write_text("{}", encoding="utf-8")
            mod_file = source / "data" / "gamedata" / "island.xml"
            mod_file.write_text("<Root />", encoding="utf-8")
            mod_folder.mkdir(parents=True)

            app = _FinalizeHarness()
            app.mod_folder_var = _Value(str(mod_folder))
            app.BUNDLE_DIR = bundle
            app.status_var = _Value()

            with patch.object(ui_tab_finalize.messagebox, "showinfo"):
                app._export_editor_mod_files()

            target = mod_folder / source.name
            self.assertEqual("{}", (target / "modinfo.json").read_text(encoding="utf-8"))
            self.assertEqual(
                "<Root />",
                (target / "data" / "gamedata" / "island.xml").read_text(encoding="utf-8"),
            )
            self.assertIn("2 file(s)", app.status_var.get())


if __name__ == "__main__":
    unittest.main()
