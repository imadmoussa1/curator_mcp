"""
Unit tests for token optimization and serialization utilities (services/token_utils.py).
"""

import unittest
from services.token_utils import compact_text, compact_dict, strip_none_and_empty


class TestTokenUtils(unittest.TestCase):
    """Test suite verifying payload compaction and schema minimization utilities."""

    def test_compact_text_none_and_empty(self):
        self.assertEqual(compact_text(None), "")
        self.assertEqual(compact_text(""), "")
        self.assertEqual(compact_text("   \n\t  "), "")

    def test_compact_text_whitespace_normalization(self):
        raw = "  Christopher   Nolan's    masterpiece \n in  70mm.  "
        expected = "Christopher Nolan's masterpiece in 70mm."
        self.assertEqual(compact_text(raw, max_chars=100), expected)

    def test_compact_text_within_boundary(self):
        text = "Short review."
        self.assertEqual(compact_text(text, max_chars=50), text)

    def test_compact_text_truncation_with_ellipsis(self):
        text = "This is a comprehensive and detailed analysis of modern cinema."
        result = compact_text(text, max_chars=26)
        self.assertLessEqual(len(result), 26)
        self.assertTrue(result.endswith("..."))
        self.assertEqual(result, "This is a comprehensive...")

    def test_compact_text_small_boundary(self):
        text = "Hello World"
        self.assertEqual(compact_text(text, max_chars=3), "Hel")
        self.assertEqual(compact_text(text, max_chars=2), "He")
        self.assertEqual(compact_text(text, max_chars=1), "H")

    def test_compact_dict_projection_and_filtering(self):
        source = {
            "title": "Inception",
            "director": "Christopher Nolan",
            "year": 2010,
            "empty_notes": "",
            "none_field": None,
            "empty_list": [],
            "extra_field": "ignore me",
        }
        allowed = ["title", "director", "year", "empty_notes", "none_field", "empty_list"]
        result = compact_dict(source, allowed)

        self.assertEqual(result, {
            "title": "Inception",
            "director": "Christopher Nolan",
            "year": 2010,
        })
        self.assertNotIn("extra_field", result)
        self.assertNotIn("empty_notes", result)

    def test_compact_dict_string_truncation(self):
        source = {
            "title": "Dune",
            "review": "A" * 300,
        }
        result = compact_dict(source, ["title", "review"], max_str_len=50)
        self.assertEqual(result["title"], "Dune")
        self.assertEqual(len(result["review"]), 50)
        self.assertTrue(result["review"].endswith("..."))

    def test_compact_dict_invalid_inputs(self):
        self.assertEqual(compact_dict(None, ["title"]), {})
        self.assertEqual(compact_dict({}, ["title"]), {})

    def test_strip_none_and_empty_nested(self):
        payload = {
            "id": 123,
            "title": "Solaris",
            "empty_str": "",
            "none_val": None,
            "empty_list": [],
            "empty_dict": {},
            "active": True,
            "score": 0,
            "nested": {
                "keep": "value",
                "drop": None,
                "sub_empty": {},
            },
            "list_items": ["item1", None, "", "item2"],
        }
        cleaned = strip_none_and_empty(payload)
        expected = {
            "id": 123,
            "title": "Solaris",
            "active": True,
            "score": 0,
            "nested": {
                "keep": "value",
            },
            "list_items": ["item1", "item2"],
        }
        self.assertEqual(cleaned, expected)


if __name__ == "__main__":
    unittest.main()
