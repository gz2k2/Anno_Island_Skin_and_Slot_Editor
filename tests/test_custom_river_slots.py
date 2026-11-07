"""Tests for custom River Slot persistence and validation."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.functions.function_custom_river_slots import (
    load_custom_river_slots,
    save_custom_river_slots,
    validate_custom_river_slots,
)
from app.config.config_slot import RIVER_GUID_FAMILIES, RIVER_GUID_ROLE, configure_custom_river_guids
import app.functions.function_island_slots
from app.functions.function_river_slots import RiverSlotEditingMixin


class CustomRiverSlotTests(unittest.TestCase):
    """Verify user-defined River Slot lists remain valid and portable."""

    def test_round_trip_multiple_named_pairs(self):
        """Persist and reload more than one named River Slot pair."""
        rows = [
            {"name": "North River", "river_slot_guid": "19990001", "work_area_guid": "19990002"},
            {"name": "South River", "river_slot_guid": "19990003", "work_area_guid": "19990004"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.ini"
            path = save_custom_river_slots(config_file, rows)
            self.assertEqual(rows, load_custom_river_slots(config_file))
            self.assertEqual("config_custom_riverslots.json", path.name)

    def test_missing_file_loads_empty_list(self):
        """Treat a not-yet-created user data file as an empty list."""
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual([], load_custom_river_slots(Path(directory) / "config.ini"))

    def test_duplicate_guid_is_rejected(self):
        """Reject GUID reuse between distinct named pairs."""
        rows = [
            {"name": "River A", "river_slot_guid": "19990001", "work_area_guid": "19990002"},
            {"name": "River B", "river_slot_guid": "19990001", "work_area_guid": "19990004"},
        ]
        with self.assertRaisesRegex(ValueError, "already used"):
            validate_custom_river_slots(rows)

    def test_built_in_guid_is_rejected(self):
        """Reject reuse of a built-in River Slot GUID."""
        rows = [{"name": "River A", "river_slot_guid": "117741", "work_area_guid": "19990002"}]
        with self.assertRaisesRegex(ValueError, "already used"):
            validate_custom_river_slots(rows)

    def test_existing_mine_guid_is_rejected(self):
        """Reject reuse of a built-in mine GUID."""
        rows = [{"name": "River A", "river_slot_guid": "1000029", "work_area_guid": "19990002"}]
        with self.assertRaisesRegex(ValueError, "already used"):
            validate_custom_river_slots(rows)

    def test_invalid_file_schema_is_rejected(self):
        """Reject user data written with an unsupported schema version."""
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.ini"
            path = Path(directory) / "config_riverslots.json"
            path.write_text(json.dumps({"schema": 2, "river_slots": []}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                load_custom_river_slots(config_file)

    def test_legacy_filename_is_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.ini"
            legacy_path = Path(directory) / "config_riverslots.json"
            legacy_path.write_text(
                json.dumps({"schema": 1, "river_slots": []}), encoding="utf-8"
            )

            self.assertEqual([], load_custom_river_slots(config_file))
            self.assertTrue((Path(directory) / "config_custom_riverslots.json").is_file())
            self.assertFalse(legacy_path.exists())

    def test_old_legacy_filename_is_also_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.ini"
            legacy_path = Path(directory) / "custom_river_slots.json"
            legacy_path.write_text(
                json.dumps({"schema": 1, "river_slots": []}), encoding="utf-8"
            )

            self.assertEqual([], load_custom_river_slots(config_file))
            self.assertTrue((Path(directory) / "config_custom_riverslots.json").is_file())
            self.assertFalse(legacy_path.exists())

    def test_custom_pairs_are_registered_for_slot_processing(self):
        """Expose registered pairs through the shared slot-family registry."""
        rows = [{"name": "North River", "river_slot_guid": "19990001", "work_area_guid": "19990002"}]
        try:
            configure_custom_river_guids(rows)
            family = RIVER_GUID_FAMILIES["custom:North River"]
            self.assertEqual("19990001", family["primary"])
            self.assertEqual(("custom:North River", "workarea"), RIVER_GUID_ROLE["19990002"])
        finally:
            configure_custom_river_guids([])

    def test_selected_slot_map_type_resolves_its_guid_pair(self):
        """Use the GUID pair associated with the selected Slot Map option."""
        state = SimpleNamespace(
            slot_map_river_type_var=Mock(get=Mock(return_value="Custom River")),
            slot_map_river_type_guids={"Custom River": ("19990001", "19990002")},
        )
        self.assertEqual(
            ("19990001", "19990002"),
            RiverSlotEditingMixin._slot_map_selected_river_guids(state),
        )


if __name__ == "__main__":
    unittest.main()