"""
Unit tests for domain services, OOP repositories, and external API clients.
"""

import unittest
from unittest.mock import MagicMock, patch

from models import BookModel, MediaModel, QuoteModel, PodcastModel
from services.book_service import BookService
from services.media_service import MediaService
from services.quote_service import QuoteService
from services.podcast_service import PodcastService
from services.recommendation_service import RecommendationService
from services.external.books_client import BookMetadataClient
from services.external.tmdb_client import TMDBClient
from services.external.podcasts_client import ApplePodcastsClient
from importers import GoodreadsImporter, IMDbImporter


class TestDomainServices(unittest.TestCase):
    def test_book_service_helpers(self):
        service = BookService()
        doc_id = service._generate_book_id("Thinking, Fast and Slow", "Daniel Kahneman")
        self.assertTrue(doc_id.startswith("gr_thinking_fast_and_slow"))

    def test_media_service_helpers(self):
        service = MediaService()
        doc_id = service._generate_media_id("Interstellar")
        self.assertTrue(doc_id.startswith("tt_interstellar"))

    def test_quote_service_helpers(self):
        service = QuoteService()
        doc_id = service._generate_quote_id("Fight Club", "Tyler Durden")
        self.assertTrue(doc_id.startswith("quote_fight_club"))

    def test_podcast_service_helpers(self):
        service = PodcastService()
        doc_id = service._generate_podcast_id("Huberman Lab", "Dopamine")
        self.assertTrue(doc_id.startswith("pod_huberman_lab_dopamine"))

    def test_importer_classes(self):
        gr_importer = GoodreadsImporter(dry_run=True)
        self.assertEqual(gr_importer.collection_name, "books")
        self.assertTrue(gr_importer.dry_run)

        imdb_importer = IMDbImporter(dry_run=True)
        self.assertEqual(imdb_importer.collection_name, "media")
        self.assertTrue(imdb_importer.dry_run)

    @patch("requests.Session.get")
    def test_apple_podcasts_client(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "resultCount": 1,
            "results": [{
                "collectionName": "Huberman Lab",
                "artistName": "Andrew Huberman",
                "genres": ["Health & Fitness", "Science"],
                "trackCount": 150,
                "artworkUrl600": "https://example.com/art.jpg",
                "feedUrl": "https://example.com/feed.xml"
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = ApplePodcastsClient()
        results = client.search(show_name="Huberman Lab", limit=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["podcast_name"], "Huberman Lab")
        self.assertEqual(results[0]["host"], "Andrew Huberman")
        self.assertEqual(results[0]["host_or_artist"], "Andrew Huberman")


if __name__ == "__main__":
    unittest.main()
