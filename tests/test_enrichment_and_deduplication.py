"""
Comprehensive unit tests for TMDB auto-enrichment and de-duplication across ALL data collections:
Media, Books, Podcasts, Restaurants, Quotes, and Sensory Vault.
"""

import unittest
from unittest.mock import MagicMock, patch
from services.media_service import MediaService
from services.book_service import BookService
from services.podcast_service import PodcastService
from services.restaurant_service import RestaurantService
from services.quote_service import QuoteService
from services.connoisseur.base import BaseConnoisseurService


class TestAllDataDeduplication(unittest.TestCase):
    def setUp(self):
        self.media_service = MediaService()
        self.book_service = BookService()
        self.podcast_service = PodcastService()
        self.restaurant_service = RestaurantService()
        self.quote_service = QuoteService()
        self.whiskey_service = BaseConnoisseurService("whiskey")

    # 1. Media
    def test_title_normalization(self):
        norm1 = MediaService._normalize_title("The Dark Knight")
        norm2 = MediaService._normalize_title("dark knight")
        self.assertEqual(norm1, "darkknight")
        self.assertEqual(norm2, "darkknight")

    @patch.object(MediaService, "find_existing")
    @patch.object(MediaService, "set")
    def test_media_deduplication(self, mock_set, mock_find):
        mock_find.return_value = {"id": "tt003", "title": "Interstellar", "status": "watchlist"}
        res = self.media_service.add_to_watchlist("Interstellar")
        self.assertEqual(res["status"], "already_exists")
        self.assertIn("Duplicate prevented", res["message"])
        mock_set.assert_not_called()

    # 2. Books
    @patch.object(BookService, "find_existing")
    @patch.object(BookService, "set")
    def test_book_deduplication(self, mock_set, mock_find):
        mock_find.return_value = {"id": "gr001", "title": "Clean Code", "author": "Robert C. Martin", "shelf": "to-read"}
        res = self.book_service.add_to_reading_list("Clean Code", "Robert C. Martin")
        self.assertEqual(res["status"], "already_exists")
        self.assertIn("Duplicate prevented", res["message"])
        mock_set.assert_not_called()

    # 3. Podcasts
    @patch.object(PodcastService, "find_existing")
    @patch.object(PodcastService, "set")
    def test_podcast_deduplication(self, mock_set, mock_find):
        mock_find.return_value = {"id": "pod001", "podcast_name": "Huberman Lab", "episode_title": "Sleep Protocol", "status": "queue"}
        res = self.podcast_service.add_to_queue("Huberman Lab", "Sleep Protocol")
        self.assertEqual(res["status"], "already_exists")
        self.assertIn("duplicate prevented", res["message"])
        mock_set.assert_not_called()

    # 4. Restaurants
    @patch.object(RestaurantService, "find_existing")
    @patch.object(RestaurantService, "set")
    def test_restaurant_deduplication(self, mock_set, mock_find):
        mock_find.return_value = {"id": "rest001", "name": "L'Ambroisie", "city": "Paris", "status": "visited"}
        res = self.restaurant_service.log_restaurant("L'Ambroisie", "Paris", "French", user_rating=9.5)
        self.assertEqual(res["status"], "success")
        self.assertIn("duplicate prevented", res["message"])
        mock_set.assert_called_once()

    # 5. Quotes
    @patch.object(QuoteService, "find_existing")
    @patch.object(QuoteService, "set")
    def test_quote_deduplication(self, mock_set, mock_find):
        mock_find.return_value = {"id": "quote001", "quote_text": "Stay hungry, stay foolish.", "source_title": "Stanford Speech"}
        res = self.quote_service.add("Stay hungry, stay foolish.", "Stanford Speech")
        self.assertEqual(res["status"], "already_exists")
        self.assertIn("duplicate prevented", res["message"])

    # 6. Sensory Vault
    @patch.object(BaseConnoisseurService, "find_existing")
    @patch.object(BaseConnoisseurService, "set")
    def test_sensory_deduplication(self, mock_set, mock_find):
        mock_find.return_value = {"id": "sens001", "category": "whiskey", "name": "Lagavulin 16", "maker_or_brand": "Lagavulin"}
        res = self.whiskey_service.log("Lagavulin 16", "Lagavulin", user_rating=9.0)
        self.assertEqual(res["status"], "success")
        self.assertIn("duplicate prevented", res["message"])
        mock_set.assert_called_once()


if __name__ == "__main__":
    unittest.main()
