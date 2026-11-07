import unittest
from unittest.mock import Mock, patch

from app.templates.template_popup import PopupTemplate
from app.ui.tabs.ui_tab_object_configuration import ObjectConfigurationTabMixin


class ObjectConfigurationPopupTests(unittest.TestCase):
    def test_save_message_is_parented_to_and_reactivates_table_popup(self):
        app = object.__new__(ObjectConfigurationTabMixin)
        rd3d_window = object()
        tmc_window = object()
        app.object_configuration_table1_window = rd3d_window
        app.object_configuration_table2_window = tmc_window

        with (
            patch.object(PopupTemplate, "window_exists", return_value=True),
            patch.object(PopupTemplate, "safe_activate") as activate,
        ):
            for number, window in ((1, rd3d_window), (2, tmc_window)):
                dialog = Mock()
                app._show_object_table_message(number, dialog, "Save", "Complete")
                dialog.assert_called_once_with("Save", "Complete", parent=window)
                activate.assert_called_with(window)


if __name__ == "__main__":
    unittest.main()
