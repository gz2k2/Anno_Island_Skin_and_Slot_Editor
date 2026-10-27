import unittest
import app.backend.xml_backend as ET
from app.functions.function_slot_validation import validate_slot_trees


def trees(folder="19", sequence="100", budget=""):
    sound = f"<SoundEmitter>{budget}</SoundEmitter>"
    game = ET.fromstring(f"""<Content><GameObject><objects><None>
      <guid>100417</guid><ID>-10</ID><ObjectFolderID>{folder}</ObjectFolderID><Position>1 2 3</Position>
      <ParticipantID><id>8</id></ParticipantID><Blocking/><Building/><QuestObject/><Infolayer/>
      <Mesh><Flags><flags>1</flags></Flags><SequenceData><CurrentSequenceStartTime>{sequence}</CurrentSequenceStartTime></SequenceData></Mesh>
      <RandomMapObject/><Selection/>{sound}</None></objects></GameObject></Content>""")
    map_root = ET.fromstring("""<Content><ObjectMetaInfo><SlotObjects>
      <None><value><id>1</id></value></None><None><None><ObjectId>-10</ObjectId><ObjectGuid>100417</ObjectGuid><Position>1 2 3</Position></None></None>
      </SlotObjects></ObjectMetaInfo></Content>""")
    return map_root, game

class OriginalDepositVariantTests(unittest.TestCase):
    def test_original_game_variant_is_not_a_blocker(self):
        map_root, game = trees(folder="19", sequence="100", budget="")
        report = validate_slot_trees(map_root, game)
        self.assertTrue(report.ok, report.errors)

    def test_current_session_generated_deposit_remains_strict(self):
        map_root, game = trees(folder="19", sequence="100", budget="")
        report = validate_slot_trees(map_root, game, strict_deposit_ids={"-10"})
        self.assertFalse(report.ok)
        self.assertTrue(any("ObjectFolderID 0" in error for error in report.errors))
        self.assertTrue(any("CurrentSequenceStartTime 0" in error for error in report.errors))
        self.assertTrue(any("TimeBudget 500" in error for error in report.errors))

if __name__ == "__main__":
    unittest.main()
