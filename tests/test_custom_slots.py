import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from app.config.config_slot import (
    SINGLE_SLOT_GUIDS,
    SLOT_DEFINITIONS,
    configure_custom_slots,
)
from app.functions.function_custom_slots import (
    load_custom_slots,
    save_custom_slots,
    validate_custom_slots,
)
from app.functions.function_custom_river_slots import validate_custom_river_slots
from app.functions.function_island_slots import IslandSlotEditingMixin


class CustomSlotTests(unittest.TestCase):
    def test_round_trip_named_single_slots(self):
        rows = [
            {"name": "Cliff Slot", "guid": "19991001"},
            {"name": "Harbor Slot", "guid": "19991002"},
        ]
        with TemporaryDirectory() as directory:
            config_file = Path(directory) / "config.ini"
            path = save_custom_slots(config_file, rows)

            self.assertEqual("config_custom_slots.json", path.name)
            self.assertEqual(rows, load_custom_slots(config_file))

    def test_duplicate_and_reserved_guids_are_rejected(self):
        duplicate_rows = [
            {"name": "Slot One", "guid": "19991001"},
            {"name": "Slot Two", "guid": "19991001"},
        ]
        with self.assertRaisesRegex(ValueError, "already used"):
            validate_custom_slots(duplicate_rows)
        with self.assertRaisesRegex(ValueError, "already used"):
            validate_custom_slots([{"name": "Reserved", "guid": "117741"}])

    def test_river_slot_guid_can_be_reserved_against_single_slot(self):
        with self.assertRaisesRegex(ValueError, "already used"):
            validate_custom_slots(
                [{"name": "Overlap", "guid": "19991001"}],
                reserved_guids=("19991001",),
            )
        with self.assertRaisesRegex(ValueError, "already used"):
            validate_custom_river_slots(
                [{
                    "name": "Overlap",
                    "river_slot_guid": "19991001",
                    "work_area_guid": "19991002",
                }],
                additional_reserved_guids=("19991001",),
            )

    def test_custom_slot_registration_adds_and_removes_definition(self):
        record = {"name": "Registered Custom Slot", "guid": "19991003"}
        try:
            configure_custom_slots([record])
            self.assertEqual("19991003", SLOT_DEFINITIONS[record["name"]]["guid"])
            self.assertIn("19991003", SINGLE_SLOT_GUIDS)
        finally:
            configure_custom_slots([])

        self.assertNotIn(record["name"], SLOT_DEFINITIONS)
        self.assertNotIn("19991003", SINGLE_SLOT_GUIDS)

    def test_slot_map_uses_selected_configured_slot(self):
        record = {"name": "Selected Slot", "guid": "19991004"}

        class _Value:
            def get(self):
                return record["name"]

        try:
            configure_custom_slots([record])
            app = object.__new__(IslandSlotEditingMixin)
            app.slot_map_custom_slot_var = _Value()
            app.slot_map_custom_slot_guids = {record["name"]: record["guid"]}
            app.slot_map_window = object()
            app._island_slot_add_at_event = Mock()
            event = object()

            app._island_slot_add_selected_custom_slot_at_event(event)

            app._island_slot_add_at_event.assert_called_once_with(event, record["name"])
        finally:
            configure_custom_slots([])


if __name__ == "__main__":
    unittest.main()
