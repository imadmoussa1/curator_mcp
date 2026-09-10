"""
Unit tests for PairingService, FastMCP Context Resources, and FastMCP Prompts.
"""

import unittest
from unittest.mock import MagicMock
from services.pairing_service import PairingService
from mcp_server import (
    get_taste_profile_context,
    get_active_queues_context,
    get_daily_digest_context,
    daily_briefing,
    tasting_session,
    weekend_curation,
    get_aesthetic_pairing,
    get_dining_course_pairing,
)


class TestPairingAndMCPSuperpowers(unittest.TestCase):

    def setUp(self):
        self.mock_sensory = MagicMock()
        self.mock_sensory.stream_all.return_value = [
            {"name": "Lagavulin 16", "maker_or_brand": "Lagavulin", "category": "whiskey", "status": "owned"},
            {"name": "Uji Gyokuro", "maker_or_brand": "Ippodo", "category": "tea", "status": "owned"},
        ]
        self.pairing_service = PairingService(sensory_service=self.mock_sensory)

    def test_book_pairing_scifi(self):
        res = self.pairing_service.get_pairing_for_book(title="Dune", author="Frank Herbert")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["anchor"]["title"], "Dune")
        self.assertIn("Lapsang Souchong", res["beverage_pairing"]["recommendation"])
        self.assertIn("Oud Wood", res["fragrance_atmosphere"]["fragrance_name"])
        self.assertIn("Lagavulin 16 by Lagavulin", res["owned_cellar_alternatives"])

    def test_book_pairing_japanese_zen(self):
        res = self.pairing_service.get_pairing_for_book(title="Norwegian Wood", author="Haruki Murakami")
        self.assertEqual(res["status"], "success")
        self.assertIn("Gyokuro", res["beverage_pairing"]["recommendation"])
        self.assertIn("Tam Dao", res["fragrance_atmosphere"]["fragrance_name"])

    def test_book_pairing_noir(self):
        res = self.pairing_service.get_pairing_for_book(title="The Big Sleep", author="Raymond Chandler")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["beverage_pairing"]["category"], "whiskey")
        self.assertIn("Bourbon", res["beverage_pairing"]["recommendation"])

    def test_media_pairing(self):
        res = self.pairing_service.get_pairing_for_media(title="Blade Runner 2049", media_type="movie")
        self.assertEqual(res["status"], "success")
        self.assertIn("Whisky", res["cocktail_or_spirit_pairing"])
        self.assertIn("amber", res["ambient_fragrance"].lower())

    def test_dish_pairing(self):
        sushi_res = self.pairing_service.get_pairing_for_dish(dish_or_cuisine="Omakase Nigiri")
        self.assertEqual(sushi_res["status"], "success")
        self.assertIn("Sake", sushi_res["recommended_pairing"])

        steak_res = self.pairing_service.get_pairing_for_dish(dish_or_cuisine="Dry-Aged Ribeye")
        self.assertEqual(steak_res["status"], "success")
        self.assertIn("Cabernet", steak_res["recommended_pairing"])

    def test_fastmcp_resources(self):
        # Context Resources should return rich strings
        taste_ctx = get_taste_profile_context()
        self.assertIsInstance(taste_ctx, str)
        self.assertIn("User Cultural & Taste Profile", taste_ctx)

        queue_ctx = get_active_queues_context()
        self.assertIsInstance(queue_ctx, str)
        self.assertIn("Active Queues", queue_ctx)

        digest_ctx = get_daily_digest_context()
        self.assertIsInstance(digest_ctx, str)
        self.assertIn("Daily Curator Digest", digest_ctx)

    def test_fastmcp_prompts(self):
        briefing_p = daily_briefing()
        self.assertIsInstance(briefing_p, str)
        self.assertIn("Taste & Cultural Intelligence Curator", briefing_p)

        tasting_p = tasting_session(category="whiskey", item_name="Springbank 15")
        self.assertIsInstance(tasting_p, str)
        self.assertIn("Springbank 15", tasting_p)
        self.assertIn("Master Tasting", tasting_p)

        weekend_p = weekend_curation(mood="rainy day cozy")
        self.assertIsInstance(weekend_p, str)
        self.assertIn("rainy day cozy", weekend_p)

    def test_fastmcp_pairing_tools(self):
        tool_res = get_aesthetic_pairing(anchor_type="book", title_or_name="Meditations", author_or_creator="Marcus Aurelius")
        self.assertEqual(tool_res["status"], "success")
        self.assertIn("beverage_pairing", tool_res)

        dining_tool_res = get_dining_course_pairing(dish_or_cuisine="Truffle Pasta")
        self.assertEqual(dining_tool_res["status"], "success")
        self.assertIn("recommended_pairing", dining_tool_res)


if __name__ == "__main__":
    unittest.main()
