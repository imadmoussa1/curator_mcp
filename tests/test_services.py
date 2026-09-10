"""
Unit tests for external API services (Google Books and TMDB).
"""

import unittest
from services.external_api import search_google_books, find_similar_books, search_tmdb


class TestExternalApiServices(unittest.TestCase):
    def test_google_books_search(self):
        # Live test of public Google Books API (no key required)
        results = search_google_books("Thinking, Fast and Slow", author="Daniel Kahneman", limit=2)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        self.assertIn("title", results[0])
        self.assertIn("authors", results[0])

    def test_google_books_similar(self):
        res = find_similar_books("The Power of Habit", limit=2)
        self.assertEqual(res.get("status"), "success")
        self.assertIn("seed_book", res)
        self.assertIn("recommendations", res)

    def test_tmdb_fallback_when_no_key(self):
        # When TMDB_API_KEY is not set or empty, verify it returns config_required without crashing
        res = search_tmdb("Inception")
        self.assertIsInstance(res, list)
        self.assertTrue("config_required" in res[0].get("status", "") or "title" in res[0])


if __name__ == "__main__":
    unittest.main()
