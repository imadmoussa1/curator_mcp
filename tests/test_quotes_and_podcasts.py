"""
Unit tests for Quotes and Podcasts data schemas and services.
"""

import unittest
from models import QuoteModel, PodcastModel
from services.external_api import search_podcast_online


class TestQuotesAndPodcasts(unittest.TestCase):
    def test_quote_model(self):
        q = QuoteModel(
            id="quote_fight_club_1",
            quote_text="The things you own end up owning you.",
            source_type="media",
            source_title="Fight Club",
            speaker_or_author="Tyler Durden",
            theme_tags=["consumerism", "freedom"],
            notes="Iconic quote on material detachment",
            favorite=True
        )
        d = q.to_firestore_dict()
        self.assertEqual(d["source_type"], "media")
        self.assertEqual(d["speaker_or_author"], "Tyler Durden")
        self.assertTrue(d["favorite"])
        self.assertIn("updated_at", d)

    def test_podcast_model(self):
        p = PodcastModel(
            id="pod_huberman_dopamine",
            podcast_name="Huberman Lab",
            episode_title="Controlling Your Dopamine For Motivation, Focus & Satisfaction",
            host="Andrew Huberman",
            guest=None,
            status="listened",
            user_rating=9,
            topics=["neuroscience", "dopamine", "motivation"],
            key_takeaways="Dopamine baseline vs peaks; cold exposure increases sustained baseline.",
            duration_mins=120
        )
        d = p.to_firestore_dict()
        self.assertEqual(d["status"], "listened")
        self.assertEqual(d["user_rating"], 9)
        self.assertIn("updated_at", d)

    def test_search_podcast_online(self):
        # Live test of free Apple Podcasts search API
        results = search_podcast_online("Huberman Lab", limit=2)
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        self.assertIn("podcast_name", results[0])
        self.assertIn("artwork_url", results[0])


if __name__ == "__main__":
    unittest.main()
