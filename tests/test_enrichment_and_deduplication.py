"""
Unit tests for TMDB auto-enrichment and de-duplication across Media and Books.
"""

import unittest
from unittest.mock import MagicMock, patch
from services.media_service import MediaService
from services.book_service import BookService


class TestEnrichmentAndDeduplication(unittest.TestCase):
    def setUp(self):
        self.media_service = MediaService()
        self.book_service = BookService()

    def test_title_normalization(self):
        norm1 = MediaService._normalize_title("The Dark Knight")
        norm2 = MediaService._normalize_title("dark knight")
        norm3 = MediaService._normalize_title("Dark Knight, The")
        self.assertEqual(norm1, "darkknight")
        self.assertEqual(norm2, "darkknight")

    @patch.object(MediaService, "stream_all")
    def test_media_find_existing_by_title(self, mock_stream):
        mock_stream.return_value = [
            {"id": "tt001", "title": "Inception", "year": 2010, "status": "watched"}
        ]
        found = self.media_service.find_existing("inception")
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "tt001")

    @patch.object(MediaService, "stream_all")
    def test_media_find_existing_by_tmdb_id(self, mock_stream):
        mock_stream.return_value = [
            {"id": "tt002", "title": "Dune", "tmdb_id": 438631, "status": "watched"}
        ]
        found = self.media_service.find_existing("Different Title", tmdb_id=438631)
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], "tt002")

    @patch.object(MediaService, "find_existing")
    @patch.object(MediaService, "set")
    def test_add_to_watchlist_prevents_duplicate(self, mock_set, mock_find):
        mock_find.return_value = {
            "id": "tt003",
            "title": "Interstellar",
            "status": "watchlist"
        }
        res = self.media_service.add_to_watchlist("Interstellar")
        self.assertEqual(res["status"], "already_exists")
        self.assertIn("Duplicate prevented", res["message"])
        mock_set.assert_not_called()

    @patch.object(MediaService, "find_existing")
    @patch.object(MediaService, "_enrich_from_tmdb")
    @patch.object(MediaService, "set")
    def test_add_to_watchlist_enriches_from_tmdb(self, mock_set, mock_enrich, mock_find):
        mock_find.return_value = None
        mock_enrich.return_value = {
            "title": "Oppenheimer",
            "release_date": "2023-07-19",
            "vote_average": 8.1,
            "genres": ["Drama", "History"],
            "poster_url": "https://image.tmdb.org/t/p/w500/oppenheimer.jpg",
            "overview": "The story of J. Robert Oppenheimer...",
            "tmdb_id": 872585
        }
        res = self.media_service.add_to_watchlist("oppenheimer")
        self.assertEqual(res["status"], "success")
        self.assertIn("auto-enriched with TMDB metadata", res["message"])
        saved_media = res["media"]
        self.assertEqual(saved_media["title"], "Oppenheimer")
        self.assertEqual(saved_media["year"], 2023)
        self.assertEqual(saved_media["tmdb_id"], 872585)
        self.assertEqual(saved_media["poster_url"], "https://image.tmdb.org/t/p/w500/oppenheimer.jpg")
        self.assertIn("Drama", saved_media["genres"])
        mock_set.assert_called_once()

    @patch.object(MediaService, "find_existing")
    @patch.object(MediaService, "set")
    def test_log_watched_updates_existing_without_duplicate(self, mock_set, mock_find):
        mock_find.return_value = {
            "id": "tt005",
            "title": "Arrival",
            "status": "watchlist",
            "year": 2016
        }
        res = self.media_service.log_watched("Arrival", user_rating=9, review="Masterpiece")
        self.assertEqual(res["status"], "success")
        self.assertIn("duplicate prevented", res["message"])
        saved = res["media"]
        self.assertEqual(saved["status"], "watched")
        self.assertEqual(saved["user_rating"], 9)
        self.assertEqual(saved["review"], "Masterpiece")

    @patch.object(BookService, "find_existing")
    @patch.object(BookService, "set")
    def test_book_deduplication(self, mock_set, mock_find):
        mock_find.return_value = {
            "id": "gr001",
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "shelf": "to-read"
        }
        res = self.book_service.add_to_reading_list("Clean Code", "Robert C. Martin")
        self.assertEqual(res["status"], "already_exists")
        self.assertIn("Duplicate prevented", res["message"])
        mock_set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
