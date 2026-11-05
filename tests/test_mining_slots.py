"""Tests for generated MineSlot and Work Area path geometry."""
import unittest

import app.functions.function_island_slots
from app.functions.function_mining_slots import MiningSlotEditingMixin


class MineWorkareaBezierEndpointTests(unittest.TestCase):
    """Verify Work Area path endpoints follow their respective object heights."""

    def test_endpoints_follow_objects_with_independent_offsets(self):
        """Keep MineSlot and Work Area endpoint offsets independent."""
        mixin = MiningSlotEditingMixin()
        mixin.MINE_PATH_MINESLOT_HEIGHT_OFFSET = 0.25
        mixin.MINE_PATH_WORKAREA_HEIGHT_OFFSET = -0.5

        mine_position = (10.0, 5.0, 20.0)
        workarea_position = (30.0, 7.0, 40.0)
        mine_path_anchor = (10.5, 20.0)
        workarea_path_anchor = (29.5, 40.0)

        start, end = mixin.mine_workarea_path_endpoints(
            mine_position,
            workarea_position,
            mine_path_anchor,
            workarea_path_anchor,
        )

        self.assertEqual((10.5, 5.25, 20.0), start)
        self.assertEqual((29.5, 6.5, 40.0), end)


if __name__ == "__main__":
    unittest.main()