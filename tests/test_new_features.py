"""
Unit tests for new features:
1. TMDB Streaming Providers (JustWatch data)
2. Curate My Night (Runtime and mood filter)
3. Curator Wrapped (Personal annual retrospective & archetype)
"""

import unittest
from unittest.mock import MagicMock, patch

from services.external.tmdb_client import TMDBClient
from services.media_service import MediaService
from services.book_service import BookService
from services.quote_service import QuoteService
from services.podcast_service import PodcastService
from services.recommendation_service import RecommendationService


class TestNewCuratorFeatures(unittest.TestCase):
    @patch.object(TMDBClient, "search")
    @patch("requests.Session.get")
    def test_tmdb_watch_providers(self, mock_get, mock_search):
        mock_search.return_value = [{"tmdb_id": 27205, "title": "Inception"}]
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "results": {
                "US": {
                    "link": "https://www.themoviedb.org/movie/27205/watch?locale=US",
                    "flatrate": [
                        {"provider_name": "Max", "provider_id": 1899, "logo_path": "/max.jpg"}
                    ],
                    "rent": [
                        {"provider_name": "Apple TV", "provider_id": 2, "logo_path": "/apple.jpg"}
                    ]
                }
            }
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        client = TMDBClient(api_key="dummy_test_key")
        res = client.get_watch_providers("Inception", media_type="movie", country="US")

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["title"], "Inception")
        self.assertEqual(len(res["streaming_subscriptions"]), 1)
        self.assertEqual(res["streaming_subscriptions"][0]["provider_name"], "Max")
        self.assertEqual(len(res["rent"]), 1)

    @patch.object(MediaService, "filter_by")
    def test_curate_for_tonight(self, mock_filter_by):
        mock_filter_by.return_value = [
            {
                "id": "tt1",
                "title": "Short Comedy",
                "year": 2020,
                "media_type": "movie",
                "genres": ["Comedy"],
                "imdb_rating": 8.0,
                "runtime_mins": 85,
                "directors": ["Director A"],
            },
            {
                "id": "tt2",
                "title": "Long Epic",
                "year": 2021,
                "media_type": "movie",
                "genres": ["Drama"],
                "imdb_rating": 9.0,
                "runtime_mins": 180,
                "directors": ["Director B"],
            },
            {
                "id": "tt3",
                "title": "Mid Sci-Fi",
                "year": 2022,
                "media_type": "movie",
                "genres": ["Sci-Fi", "Comedy"],
                "imdb_rating": 7.5,
                "runtime_mins": 95,
                "directors": ["Director C"],
            }
        ]

        service = MediaService()
        # Test filtering for under 100 mins comedy
        result = service.curate_for_tonight(max_runtime_mins=100, genre="comedy")
        self.assertEqual(result["status"], "success")
        picks = result["curated_picks"]
        self.assertEqual(len(picks), 2)
        # Short Comedy (8.0) should be ranked first before Mid Sci-Fi (7.5)
        self.assertEqual(picks[0]["title"], "Short Comedy")
        self.assertIn("85 mins", picks[0]["runtime"])

    @patch.object(BookService, "stream_all")
    @patch.object(MediaService, "stream_all")
    @patch.object(QuoteService, "stream_all")
    @patch.object(PodcastService, "stream_all")
    def test_cultural_wrapped(self, mock_podcasts, mock_quotes, mock_media, mock_books):
        mock_books.return_value = [
            {"id": "b1", "title": "Book 1", "author": "Author A", "user_rating": 5, "date_read": "2026-03-01", "shelf": "read"},
            {"id": "b2", "title": "Book 2", "author": "Author B", "user_rating": 4, "date_read": "2026-05-10", "shelf": "read"},
        ]
        mock_media.return_value = [
            {"id": "m1", "title": "Sci-Fi Film", "year": 2024, "status": "watched", "user_rating": 9, "genres": ["Sci-Fi", "Drama"], "directors": ["Director X"], "notes": "Rated on 2026-02-14"},
            {"id": "m2", "title": "Another Film", "year": 2023, "status": "watched", "user_rating": 8, "genres": ["Sci-Fi"], "directors": ["Director Y"], "notes": "Rated on 2026-04-10"},
        ]
        mock_quotes.return_value = [
            {"id": "q1", "quote_text": "Stay disciplined.", "theme_tags": ["stoicism", "discipline"]},
        ]
        mock_podcasts.return_value = [
            {"id": "p1", "podcast_name": "Show", "status": "listened", "date_listened": "2026-06-01", "topics": ["science"]},
        ]

        book_service = BookService()
        media_service = MediaService()
        quote_service = QuoteService()
        podcast_service = PodcastService()

        rec_service = RecommendationService(
            book_service=book_service,
            media_service=media_service,
            books_client=MagicMock(),
            tmdb_client=MagicMock(),
            quote_service=quote_service,
            podcast_service=podcast_service,
        )

        wrapped = rec_service.generate_cultural_wrapped(year=2026)
        self.assertEqual(wrapped["status"], "success")
        self.assertEqual(wrapped["year"], 2026)
        self.assertEqual(wrapped["summary_metrics"]["total_books_read"], 2)
        self.assertEqual(wrapped["summary_metrics"]["total_media_watched"], 2)
        self.assertEqual(wrapped["summary_metrics"]["total_quotes_collected"], 1)
        self.assertEqual(wrapped["summary_metrics"]["total_podcasts_listened"], 1)
        self.assertEqual(wrapped["cultural_archetype"]["title"], "The Cybernetic Stoic")

    @patch.object(BookService, "get")
    @patch.object(BookService, "set")
    def test_update_book_status_goodreads(self, mock_set, mock_get):
        mock_get.return_value = {
            "id": "12345",
            "title": "Clean Code",
            "author": "Robert C. Martin",
            "shelf": "to-read",
            "user_rating": 0,
            "review": "",
            "private_notes": ""
        }
        service = BookService()
        result = service.update_status(
            book_id="12345",
            shelf="read",
            user_rating=5,
            review="Essential reading for software craftsmanship.",
            private_notes="Reread chapter 3 on functions.",
            date_read="2026-09-09"
        )
        self.assertEqual(result["status"], "success")
        mock_set.assert_called_once()
        updated = result["book"]
        self.assertEqual(updated["shelf"], "read")
        self.assertEqual(updated["user_rating"], 5)
        self.assertEqual(updated["review"], "Essential reading for software craftsmanship.")
        self.assertEqual(updated["private_notes"], "Reread chapter 3 on functions.")
        self.assertEqual(updated["date_read"], "2026-09-09")

    @patch.object(MediaService, "get")
    @patch.object(MediaService, "set")
    def test_update_media_status_imdb(self, mock_set, mock_get):
        mock_get.return_value = {
            "id": "tt1375666",
            "title": "Inception",
            "status": "watchlist",
            "user_rating": None,
            "review": "",
            "user_notes": ""
        }
        service = MediaService()
        result = service.update_status(
            media_id="tt1375666",
            status="watched",
            user_rating=10,
            review="A masterclass in original high-concept cinematic storytelling.",
            user_notes="Watched in IMAX with friends.",
            date_watched="2026-09-09"
        )
        self.assertEqual(result["status"], "success")
        mock_set.assert_called_once()
        updated = result["media"]
        self.assertEqual(updated["status"], "watched")
        self.assertEqual(updated["user_rating"], 10)
        self.assertEqual(updated["review"], "A masterclass in original high-concept cinematic storytelling.")
        self.assertEqual(updated["user_notes"], "Watched in IMAX with friends.")
        self.assertEqual(updated["date_watched"], "2026-09-09")


if __name__ == "__main__":
    unittest.main()
