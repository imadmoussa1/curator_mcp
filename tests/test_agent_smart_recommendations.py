"""
Unit tests for AI Agent Smart Recommendation Briefing, Candidate Vetting, and MCP presentation layer.
"""

import unittest
from unittest.mock import MagicMock, patch

from services.recommendation_service import RecommendationService
from mcp_server import (
    get_agent_recommendation_brief,
    vet_recommendation_candidate,
    smart_recommendation_consultation,
    get_taste_dna_dossier,
)


class TestAgentSmartRecommendations(unittest.TestCase):

    def setUp(self):
        # Mock book service
        self.mock_books = MagicMock()
        self.mock_books.stream_all.return_value = [
            {"title": "Neuromancer", "author": "William Gibson", "user_rating": 5, "notes_and_reviews": "Pioneering cyberpunk", "shelf": "read"},
            {"title": "Snow Crash", "author": "Neal Stephenson", "user_rating": 4, "notes_and_reviews": "Great metaverse satire", "shelf": "read"},
            {"title": "Boring Thriller", "author": "Generic Author", "user_rating": 2, "notes_and_reviews": "Predictable plot", "shelf": "read"},
        ]

        # Mock media service
        self.mock_media = MagicMock()
        self.mock_media.stream_all.return_value = [
            {"title": "Blade Runner 2049", "year": 2017, "media_type": "movie", "user_rating": 10, "directors": ["Denis Villeneuve"], "genres": ["Sci-Fi", "Drama"], "status": "watched"},
            {"title": "Arrival", "year": 2016, "media_type": "movie", "user_rating": 9, "directors": ["Denis Villeneuve"], "genres": ["Sci-Fi"], "status": "watched"},
            {"title": "Mediocre Action", "year": 2021, "media_type": "movie", "user_rating": 4, "directors": ["No Name"], "genres": ["Action"], "status": "watched"},
        ]

        # Mock sensory service
        self.mock_sensory = MagicMock()
        self.mock_sensory.stream_all.return_value = [
            {"name": "Lagavulin 16", "maker_or_brand": "Lagavulin", "category": "whiskey", "user_rating": 9.5, "flavor_or_scent_notes": ["peat", "smoke", "sea salt"], "status": "owned"},
            {"name": "Worka Sakaro", "maker_or_brand": "Sey Coffee", "category": "coffee", "user_rating": 9.0, "flavor_or_scent_notes": ["jasmine", "peach", "citrus"], "status": "owned"},
        ]

        # Mock restaurant service
        self.mock_restaurants = MagicMock()
        self.mock_restaurants.stream_all.return_value = [
            {"name": "Sushi Sawada", "city": "Tokyo", "cuisine": "Omakase", "user_rating": 9.8, "vibe_tags": ["intimate counter", "traditional"], "status": "visited"},
        ]

        # Mock podcast service
        self.mock_podcasts = MagicMock()
        self.mock_podcasts.stream_all.return_value = [
            {"title": "Hardcore History", "episode_title": "Supernova in the East", "user_rating": 5, "topics": ["history", "war"], "status": "listened"},
        ]

        self.service = RecommendationService(
            book_service=self.mock_books,
            media_service=self.mock_media,
            books_client=MagicMock(),
            tmdb_client=MagicMock(),
            podcast_service=self.mock_podcasts,
            sensory_service=self.mock_sensory,
            restaurant_service=self.mock_restaurants,
        )

    def test_get_agent_recommendation_brief_books(self):
        brief = self.service.get_agent_recommendation_brief(domain="books", mood_or_intent="philosophical cyberpunk")
        self.assertEqual(brief["status"], "success")
        self.assertEqual(brief["domain"], "books")

        data = brief["briefing_for_ai_agent"]
        self.assertIn("user_taste_dna", data)
        self.assertTrue(len(data["user_taste_dna"]["top_rated_anchors"]) >= 2)
        self.assertIn("William Gibson", data["user_taste_dna"]["dominant_affinities"]["creators_or_cuisines"])

        # Check negative exclusion catalog
        exclusions = data["negative_exclusion_catalog"]["sample_excluded_titles"]
        self.assertTrue(any("Neuromancer" in title for title in exclusions))
        self.assertTrue(any("Snow Crash" in title for title in exclusions))

        # Check guardrails
        self.assertTrue(any("Boring Thriller" in g for g in data["guardrails_and_dislikes"]))

        # Check web search directives
        self.assertTrue(len(data["suggested_web_search_directives"]) >= 2)
        self.assertTrue(any("William Gibson" in q for q in data["suggested_web_search_directives"]))

    def test_get_agent_recommendation_brief_movies(self):
        brief = self.service.get_agent_recommendation_brief(domain="movies", mood_or_intent="atmospheric sci-fi")
        self.assertEqual(brief["status"], "success")
        data = brief["briefing_for_ai_agent"]
        self.assertIn("Denis Villeneuve", data["user_taste_dna"]["dominant_affinities"]["creators_or_cuisines"])
        self.assertTrue(any("Blade Runner 2049" in t for t in data["negative_exclusion_catalog"]["sample_excluded_titles"]))

    def test_get_agent_recommendation_brief_sensory(self):
        brief_whiskey = self.service.get_agent_recommendation_brief(domain="whiskey")
        self.assertEqual(brief_whiskey["status"], "success")
        data = brief_whiskey["briefing_for_ai_agent"]
        self.assertIn("Lagavulin", data["user_taste_dna"]["dominant_affinities"]["creators_or_cuisines"])
        self.assertTrue(any("Lagavulin 16" in t for t in data["negative_exclusion_catalog"]["sample_excluded_titles"]))

    def test_get_agent_recommendation_brief_restaurants(self):
        brief_rest = self.service.get_agent_recommendation_brief(domain="restaurants", target_location="Tokyo")
        self.assertEqual(brief_rest["status"], "success")
        data = brief_rest["briefing_for_ai_agent"]
        self.assertIn("Sushi Sawada", data["negative_exclusion_catalog"]["sample_excluded_titles"][0])

    def test_vet_candidate_collision(self):
        # User already read Neuromancer
        res = self.service.vet_recommendation_candidate(domain="books", title_or_name="Neuromancer")
        self.assertEqual(res["status"], "collision_detected")
        self.assertFalse(res["is_clean_recommendation"])
        self.assertIn("already in the user's collection", res["message"])

    def test_vet_candidate_clean_discovery(self):
        # Hyperion is a clean discovery
        res = self.service.vet_recommendation_candidate(
            domain="books",
            title_or_name="Hyperion",
            maker_or_creator="Dan Simmons",
            attributes=["sci-fi", "cyberpunk", "space opera"]
        )
        self.assertEqual(res["status"], "approved_clean_discovery")
        self.assertTrue(res["is_clean_recommendation"])
        self.assertIn("%", res["taste_affinity_score"])
        self.assertTrue(len(res["personalization_tethers"]) > 0)

    @patch("mcp_server.memory_service.get_relevant_constraints")
    @patch("mcp_server.memory_service.recall")
    @patch("mcp_server.sensory_service.stream_all")
    @patch("mcp_server.recommendation_service.generate_cultural_wrapped")
    @patch("mcp_server.recommendation_service.get_taste_profile")
    def test_mcp_presentation_layer(self, mock_taste, mock_wrapped, mock_stream, mock_recall, mock_constraints):
        mock_stream.return_value = []
        mock_recall.return_value = []
        mock_constraints.return_value = []
        mock_wrapped.return_value = {"cultural_archetype": {"title": "The Polymath", "summary": "Diverse appetite"}}
        mock_taste.return_value = {"taste_summary": {"top_authors": ["Gibson"], "top_directors": ["Villeneuve"], "top_genres": ["Sci-Fi"]}}

        # Test FastMCP prompt
        prompt = smart_recommendation_consultation(domain="movies", mood_or_craving="dystopian slow-burn")
        self.assertIn("get_agent_recommendation_brief", prompt)
        self.assertIn("vet_recommendation_candidate", prompt)

        # Test FastMCP resource
        dossier = get_taste_dna_dossier()
        self.assertIn("Curator MCP - User Taste DNA Dossier", dossier)

        # Test FastMCP tool calls directly
        tool_brief = get_agent_recommendation_brief(domain="coffee", mood_or_intent="fruity anaerobic")
        self.assertEqual(tool_brief["status"], "success")

        tool_vet = vet_recommendation_candidate(domain="coffee", title_or_name="Pink Bourbon", maker_or_creator="Sey Coffee")
        self.assertEqual(tool_vet["status"], "approved_clean_discovery")


if __name__ == "__main__":
    unittest.main()
