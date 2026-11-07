import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.functions.functions_tintmaps import (
    DEFAULT_TINTMAP_PRESETS,
    load_tintmap_presets,
    save_tintmap_presets,
    validate_tintmap_presets,
)


class TintmapPresetTests(unittest.TestCase):
    def test_missing_file_returns_starting_example(self):
        with TemporaryDirectory() as directory:
            presets = load_tintmap_presets(Path(directory) / "config.ini")

        self.assertEqual(list(DEFAULT_TINTMAP_PRESETS), presets)

    def test_presets_round_trip(self):
        with TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.ini"
            presets = [
                {
                    "from_region": "The Old World",
                    "to_region": "Enbesa",
                    "brightness": "Custom",
                    "custom_offset": "-20",
                    "comment": "Recommended starting value",
                },
                {
                    "from_region": "Arctic",
                    "to_region": "The New World",
                    "brightness": "Brighter (+12)",
                    "custom_offset": "0",
                    "comment": "",
                },
            ]
            save_tintmap_presets(config_file, presets)

            self.assertEqual(presets, load_tintmap_presets(config_file))

    def test_legacy_filename_is_migrated(self):
        with TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.ini"
            legacy_path = Path(directory) / "tintmap_presets.json"
            legacy_path.write_text(
                '{"schema": 1, "presets": []}', encoding="utf-8"
            )

            self.assertEqual([], load_tintmap_presets(config_file))
            self.assertTrue((Path(directory) / "config_tintmap_presets.json").is_file())
            self.assertFalse(legacy_path.exists())

    def test_custom_offset_outside_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "between -255 and 255"):
            validate_tintmap_presets([{
                "from_region": "The Old World",
                "to_region": "Enbesa",
                "brightness": "Custom",
                "custom_offset": "256",
            }])


if __name__ == "__main__":
    unittest.main()