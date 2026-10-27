from pathlib import Path
import tempfile
import unittest
import app.backend.xml_backend as ET
from app.functions.function_xml_repair import parse_xml_tolerant, sanitize_xml_text


class XmlPreservationTests(unittest.TestCase):
    def test_valid_text_unchanged(self):
        source = "<Root><Value>abc</Value></Root>"
        masked, count = sanitize_xml_text(source)
        self.assertEqual(source, masked)
        self.assertEqual(0, count)

    def _roundtrip(self, raw):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.xml"
            target = Path(folder) / "patched.xml"
            source.write_bytes(raw)
            tree, preserved, count = parse_xml_tolerant(source)
            self.assertTrue(preserved)
            self.assertGreater(count, 0)
            tree.getroot().set("edited", "yes")
            tree.write(target, encoding="utf-8", xml_declaration=False)
            value = raw.split(b"<Value>", 1)[1].split(b"</Value>", 1)[0]
            self.assertIn(value, target.read_bytes())

    def test_forbidden_control_is_preserved(self):
        self._roundtrip(b"<Root><Value>abc\x01def</Value></Root>")

    def test_invalid_numeric_reference_is_preserved(self):
        self._roundtrip(b"<Root><Value>abc&#x0;def</Value></Root>")

    def test_non_utf8_byte_is_preserved(self):
        self._roundtrip(b"<Root><Value>abc\x80def</Value></Root>")

    def test_structural_error_still_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.xml"
            path.write_bytes(b"<Root><Value></Root>")
            with self.assertRaises(ET.ParseError):
                parse_xml_tolerant(path)


if __name__ == "__main__":
    unittest.main()
