import unittest
import app.backend.xml_backend as ET
from app.functions.function_slot_validation import validate_slot_trees


def game_xml(primary_guid, work_guid, primary_id="-1", work_id="-2", folder="", bad_bounds=False):
    folder_xml = f"<ObjectFolderID>{folder}</ObjectFolderID>" if folder else ""
    maximum = "5 5 5" if bad_bounds else "20 5 20"
    return ET.fromstring(f"""
<Content><GameObject><objects>
<None><guid>{primary_guid}</guid><ID>{primary_id}</ID>{folder_xml}<Position>10 5 10</Position><RandomMapObject/></None>
<None><guid>{work_guid}</guid><ID>{work_id}</ID>{folder_xml}<Position>20 5 20</Position>
<BezierPath><Path><Minimum>10 5 10</Minimum><Maximum>{maximum}</Maximum><BezierCurve>
<None><p>20 5 20</p><i>0 0 0</i><o>0 0 0</o></None>
<None><p>10 5 10</p><i>0 0 0</i><o>0 0 0</o></None>
</BezierCurve></Path></BezierPath></None>
</objects></GameObject></Content>""")


def map_xml(primary_guid, work_guid, primary_group, work_group, primary_id="-1", work_id="-2"):
    return ET.fromstring(f"""
<Content><ObjectMetaInfo><SlotObjects>
<None><value><id>{primary_group}</id></value></None><None><None><ObjectId>{primary_id}</ObjectId><ObjectGuid>{primary_guid}</ObjectGuid><Position>10 5 10</Position></None></None>
<None><value><id>{work_group}</id></value></None><None><None><ObjectId>{work_id}</ObjectId><ObjectGuid>{work_guid}</ObjectGuid><Position>20 5 20</Position></None></None>
</SlotObjects></ObjectMetaInfo></Content>""")


class SlotValidationTests(unittest.TestCase):
    def test_native_river_folder_pair(self):
        report = validate_slot_trees(map_xml("117741", "117742", 4, 3), game_xml("117741", "117742", folder="7"))
        self.assertTrue(report.ok, report.errors)
        self.assertEqual([("-1", "-2", "native")], report.river_pairs)

    def test_custom_a_resolves_from_bezier_endpoints_without_folder(self):
        report = validate_slot_trees(map_xml("1999002330", "1999002331", 15, 3), game_xml("1999002330", "1999002331"))
        self.assertTrue(report.ok, report.errors)
        self.assertEqual([("-1", "-2", "custom_a")], report.river_pairs)

    def test_custom_b_resolves_from_bezier_endpoints_without_folder(self):
        report = validate_slot_trees(map_xml("1999002336", "1999002337", 15, 3), game_xml("1999002336", "1999002337"))
        self.assertTrue(report.ok, report.errors)
        self.assertEqual([("-1", "-2", "custom_b")], report.river_pairs)

    def test_wrong_custom_category_is_rejected(self):
        report = validate_slot_trees(map_xml("1999002330", "1999002331", 1, 3), game_xml("1999002330", "1999002331"))
        self.assertFalse(report.ok)
        self.assertTrue(any("category 15" in error for error in report.errors))

    def test_ambiguous_custom_pair_is_rejected(self):
        game = game_xml("1999002330", "1999002331")
        objects = next(game.iter("objects"))
        duplicate = ET.fromstring(ET.tostring(list(objects)[1], encoding="unicode"))
        duplicate.find("ID").text = "-3"
        objects.append(duplicate)
        report = validate_slot_trees(map_xml("1999002330", "1999002331", 15, 3), game)
        self.assertFalse(report.ok)
        self.assertTrue(any("unambiguous" in error for error in report.errors))

    def test_invalid_bezier_bounds_are_rejected(self):
        report = validate_slot_trees(map_xml("117741", "117742", 4, 3), game_xml("117741", "117742", folder="7", bad_bounds=True))
        self.assertFalse(report.ok)
        self.assertTrue(any("Bezier bounds" in error for error in report.errors))

    def test_clay_requires_category_one(self):
        game = ET.fromstring("<Content><GameObject><objects><None><guid>100417</guid><ID>-5</ID><Position>1 2 3</Position></None></objects></GameObject></Content>")
        map_root = ET.fromstring("<Content><ObjectMetaInfo><SlotObjects><None><value><id>3</id></value></None><None><None><ObjectId>-5</ObjectId><ObjectGuid>100417</ObjectGuid><Position>1 2 3</Position></None></None></SlotObjects></ObjectMetaInfo></Content>")
        report = validate_slot_trees(map_root, game)
        self.assertFalse(report.ok)
        self.assertTrue(any("category 1" in error for error in report.errors))


class SlotLifecycleGateTests(unittest.TestCase):
    """File-system boundary tests for Save, Finalize and Pack."""

    @staticmethod
    def _write_pair(folder, *, valid=True, prefix="candidate"):
        from pathlib import Path
        folder = Path(folder)
        map_root = map_xml("117741", "117742", 4, 3)
        game_root = game_xml("117741", "117742", folder="7")
        if not valid:
            # Keep XML well formed but break the cross-file position invariant.
            next(map_root.iter("Position")).text = "99 5 99"
        map_path = folder / f"{prefix}_mapname.xml"
        game_path = folder / f"{prefix}_gamedata.xml"
        ET.ElementTree(map_root).write(map_path, encoding="utf-8", xml_declaration=True)
        ET.ElementTree(game_root).write(game_path, encoding="utf-8", xml_declaration=True)
        return map_path, game_path

    def test_save_gate_valid_candidates_can_replace_targets(self):
        import os
        import tempfile
        from pathlib import Path
        from app.functions.function_slot_validation import validate_slot_gate

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            candidate_map, candidate_game = self._write_pair(directory, prefix="temp")
            target_map = directory / "mapname_patched.xml"
            target_game = directory / "gamedata_patched.xml"
            target_map.write_text("old-map", encoding="utf-8")
            target_game.write_text("old-game", encoding="utf-8")

            report = validate_slot_gate("save", candidate_map, candidate_game)
            report.require_ok()
            os.replace(candidate_map, target_map)
            os.replace(candidate_game, target_game)

            self.assertTrue(target_map.read_text(encoding="utf-8").startswith("<?xml"))
            self.assertTrue(target_game.read_text(encoding="utf-8").startswith("<?xml"))

    def test_save_gate_failure_leaves_existing_targets_unchanged(self):
        import tempfile
        from pathlib import Path
        from app.functions.function_slot_validation import validate_slot_gate

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            candidate_map, candidate_game = self._write_pair(directory, valid=False, prefix="temp")
            target_map = directory / "mapname_patched.xml"
            target_game = directory / "gamedata_patched.xml"
            target_map.write_bytes(b"OLD_MAP_TARGET")
            target_game.write_bytes(b"OLD_GAME_TARGET")
            before = (target_map.read_bytes(), target_game.read_bytes())

            report = validate_slot_gate("save", candidate_map, candidate_game)
            self.assertFalse(report.ok)
            self.assertTrue(all(error.startswith("[save]") for error in report.errors))
            self.assertEqual(before, (target_map.read_bytes(), target_game.read_bytes()))

    def test_finalize_gate_validates_exact_files_copied_to_finalize(self):
        import shutil
        import tempfile
        from pathlib import Path
        from app.functions.function_slot_validation import validate_slot_gate

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            patched_map, patched_game = self._write_pair(directory, prefix="patched")
            finalize = directory / "finalize"
            finalize.mkdir()
            final_map = finalize / "island.xml"
            final_game = finalize / "island_gamedata.xml"
            shutil.copy2(patched_map, final_map)
            shutil.copy2(patched_game, final_game)

            report = validate_slot_gate("finalize", final_map, final_game)
            self.assertTrue(report.ok, report.errors)
            self.assertEqual(1, len(report.river_pairs))

    def test_finalize_gate_rejects_modified_copy_even_if_source_was_valid(self):
        import shutil
        import tempfile
        from pathlib import Path
        from app.functions.function_slot_validation import validate_slot_gate

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            patched_map, patched_game = self._write_pair(directory, prefix="patched")
            self.assertTrue(validate_slot_gate("save", patched_map, patched_game).ok)
            final_map = directory / "final_map.xml"
            final_game = directory / "final_game.xml"
            shutil.copy2(patched_map, final_map)
            shutil.copy2(patched_game, final_game)
            tree = ET.parse(final_game)
            next(tree.getroot().iter("Position")).text = "77 5 77"
            tree.write(final_game, encoding="utf-8", xml_declaration=True)

            report = validate_slot_gate("finalize", final_map, final_game)
            self.assertFalse(report.ok)
            self.assertTrue(all(error.startswith("[finalize]") for error in report.errors))

    def test_pack_gate_failure_does_not_create_or_replace_archive(self):
        import tempfile
        import zipfile
        from pathlib import Path
        from app.functions.function_slot_validation import validate_slot_gate

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            map_path, game_path = self._write_pair(directory, valid=False, prefix="pack")
            archive = directory / "island.zip"
            archive.write_bytes(b"EXISTING_ARCHIVE")
            before = archive.read_bytes()

            report = validate_slot_gate("pack", map_path, game_path)
            if report.ok:
                with zipfile.ZipFile(archive, "w") as output:
                    output.write(map_path, map_path.name)
                    output.write(game_path, game_path.name)

            self.assertFalse(report.ok)
            self.assertEqual(before, archive.read_bytes())
            self.assertTrue(all(error.startswith("[pack]") for error in report.errors))

    def test_pack_gate_valid_pair_is_the_pair_written_to_archive(self):
        import tempfile
        import zipfile
        from pathlib import Path
        from app.functions.function_slot_validation import validate_slot_gate

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            map_path, game_path = self._write_pair(directory, prefix="pack")
            archive = directory / "island.zip"
            report = validate_slot_gate("pack", map_path, game_path)
            report.require_ok()
            with zipfile.ZipFile(archive, "w") as output:
                output.write(map_path, "island.xml")
                output.write(game_path, "island_gamedata.xml")
            with zipfile.ZipFile(archive) as packed:
                self.assertEqual(map_path.read_bytes(), packed.read("island.xml"))
                self.assertEqual(game_path.read_bytes(), packed.read("island_gamedata.xml"))

    def test_unknown_gate_stage_is_rejected(self):
        import tempfile
        from pathlib import Path
        from app.functions.function_slot_validation import validate_slot_gate

        with tempfile.TemporaryDirectory() as directory:
            map_path, game_path = self._write_pair(Path(directory))
            with self.assertRaisesRegex(ValueError, "expected save, finalize or pack"):
                validate_slot_gate("preview", map_path, game_path)


if __name__ == "__main__":
    unittest.main()
