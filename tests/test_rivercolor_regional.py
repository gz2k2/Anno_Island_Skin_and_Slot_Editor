import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import app.backend.backend_xml as ET
from app.backend.backend_patch_store import (
  PatchStore,
  apply_gamedata_regional,
)
from app.config.config_rivercolor import RIVER_COLOR_OPTIONS


class RivercolorRegionalTests(unittest.TestCase):
    def test_custom_color_updates_guid_1001608(self):
        root = ET.fromstring("""
<Root><GameObject><objects>
  <None><guid>1001608</guid><WaterColor>-1</WaterColor></None>
  <None><guid>1001609</guid><WaterColor>-3</WaterColor></None>
</objects></GameObject></Root>
""")

        apply_gamedata_regional(ET.ElementTree(root), {
            "values": {},
            "rivercolor": "-7654321",
        })

        records = list(root.iter("None"))
        self.assertEqual("-7654321", records[0].findtext("WaterColor"))
        self.assertEqual("-3", records[1].findtext("WaterColor"))

    def test_selected_color_updates_only_guid_1001608(self):
        root = ET.fromstring("""
<Root>
  <GameObject><objects>
    <None><guid>1001608</guid><Water><WaterColor>-1</WaterColor></Water></None>
    <None><guid>1001608</guid><WaterColor>-2</WaterColor></None>
    <None><guid>1001609</guid><WaterColor>-3</WaterColor></None>
  </objects></GameObject>
</Root>
""")

        apply_gamedata_regional(ET.ElementTree(root), {
            "values": {},
            "rivercolor": RIVER_COLOR_OPTIONS["Clear (blue)"],
        })

        records = list(root.iter("None"))
        self.assertEqual("-15557966", records[0].findtext(".//WaterColor"))
        self.assertEqual("-15557966", records[1].findtext(".//WaterColor"))
        self.assertEqual("-3", records[2].findtext(".//WaterColor"))

    def test_original_without_override_preserves_existing_colors(self):
        root = ET.fromstring("""
<Root><GameObject><objects>
  <None><guid>1001608</guid><WaterColor>-7</WaterColor></None>
</objects></GameObject></Root>
""")

        apply_gamedata_regional(ET.ElementTree(root), {"values": {}})

        self.assertEqual("-7", root.findtext(".//WaterColor"))

    def test_selecting_original_removes_a_saved_override(self):
        root = ET.fromstring("""
<Root>
  <SessionSettings>
    <GlobalAmbientName>Old</GlobalAmbientName>
    <VegetationPropSetName>Old</VegetationPropSetName>
  </SessionSettings>
  <GameObject><objects>
    <None><guid>1001608</guid><WaterColor>-7</WaterColor></None>
  </objects></GameObject>
</Root>
""")
        with TemporaryDirectory() as directory:
            original = Path(directory) / "gamedata_original.xml"
            ET.ElementTree(root).write(original, encoding="utf-8")
            store = PatchStore()
            store.register("gamedata", "gamedata_regional", apply_gamedata_regional)
            values = {
                "GlobalAmbientName": "New",
                "VegetationPropSetName": "New",
            }
            store.save_scope("gamedata", original, "gamedata_regional", {
                "values": values,
                "rivercolor": RIVER_COLOR_OPTIONS["Clear (blue)"],
            })
            cleared = store.save_scope("gamedata", original, "gamedata_regional", {
                "values": values,
            })

        self.assertEqual("-7", cleared.getroot().findtext(".//WaterColor"))

    def test_selected_color_is_ignored_when_guid_is_absent(self):
      root = ET.fromstring("""
  <Root><GameObject><objects>
    <None><guid>1001609</guid><WaterColor>-3</WaterColor></None>
  </objects></GameObject></Root>
  """)

      apply_gamedata_regional(ET.ElementTree(root), {
        "values": {},
                "rivercolor": RIVER_COLOR_OPTIONS["Mud (brown)"],
      })

      self.assertEqual("-3", root.findtext(".//WaterColor"))


if __name__ == "__main__":
    unittest.main()