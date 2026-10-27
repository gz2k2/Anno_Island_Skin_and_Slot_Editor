import importlib.util
from pathlib import Path
import unittest
import sys
import app.backend.xml_backend as ET
ROOT = Path(__file__).resolve().parents[1] / "app"
CSHARP = ROOT.parent / "csharp" / "Island-Editor-main" / "src" / "Anno1800IslandTool.Pipeline" / "Resources" / "Mines"

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

config = load("config_slot_test", ROOT / "config" / "config_slot.py")
sys.path.insert(0, str(ROOT))
import app.functions.function_slot_validation as validation
class NativeDepositTests(unittest.TestCase):
    def test_templates_match_working_csharp_objects(self):
        for name, filename in (("clay slot", "Clay.xml"), ("oil slot", "Oil.xml")):
            expected = ET.tostring(ET.parse(CSHARP / filename).getroot(), encoding="unicode")
            actual = ET.tostring(config.template_element(name), encoding="unicode")
            self.assertEqual(expected, actual)

    def test_runtime_normalized_deposit_passes_gate(self):
        obj = config.template_element("clay slot")
        obj.find("ID").text = "-1"
        obj.find("ObjectFolderID").text = "0"
        obj.find("Position").text = "10,5 5 10,5"
        obj.find("./Mesh/SequenceData/CurrentSequenceStartTime").text = "0"
        game = ET.fromstring("<Content><GameObject><objects/></GameObject></Content>")
        game.find("./GameObject/objects").append(obj)
        map_root = ET.fromstring("<Content><ObjectMetaInfo><SlotObjects><None><value><id>1</id></value></None><None><None><ObjectId>-1</ObjectId><ObjectGuid>100417</ObjectGuid><Position>10,5 5 10,5</Position></None></None></SlotObjects></ObjectMetaInfo></Content>")
        report = validation.validate_slot_trees(map_root, game)
        self.assertTrue(report.ok, report.errors)

    def test_old_incomplete_sound_emitter_is_rejected(self):
        obj = config.template_element("oil slot")
        obj.find("ID").text = "-2"
        obj.find("ObjectFolderID").text = "0"
        obj.find("Position").text = "20,5 5 20,5"
        obj.find("./Mesh/SequenceData/CurrentSequenceStartTime").text = "0"
        obj.find("SoundEmitter").remove(obj.find("./SoundEmitter/TimeBudget"))
        game = ET.fromstring("<Content><GameObject><objects/></GameObject></Content>")
        game.find("./GameObject/objects").append(obj)
        map_root = ET.fromstring("<Content><ObjectMetaInfo><SlotObjects><None><value><id>1</id></value></None><None><None><ObjectId>-2</ObjectId><ObjectGuid>100849</ObjectGuid><Position>20,5 5 20,5</Position></None></None></SlotObjects></ObjectMetaInfo></Content>")
        report = validation.validate_slot_trees(map_root, game, strict_deposit_ids={"-2"})
        self.assertFalse(report.ok)
        self.assertTrue(any("TimeBudget 500" in error for error in report.errors))

if __name__ == "__main__":
    unittest.main()
