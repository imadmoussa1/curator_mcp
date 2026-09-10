"""
Unit tests for Sensory Vault (Tea, Whiskey, Coffee, Gin, Wine, Chocolate, Perfume, Watch)
and Restaurant & Fine Dining models, services, and recommendation algorithms.
"""

import unittest
from unittest.mock import MagicMock, patch
from models import (
    SensoryItemModel,
    RestaurantModel,
)
from services.sensory_service import SensoryService
from services.restaurant_service import RestaurantService
from services.recommendation_service import RecommendationService
from services.external.catalog_client import ConnoisseurCatalogClient


class TestSensoryAndRestaurants(unittest.TestCase):

    def test_sensory_item_model_whiskey(self):
        item = SensoryItemModel(
            id="sens_lagavulin_16",
            category="whisky",  # Tests synonym normalization to 'whiskey'
            name="16 Year Old",
            maker_or_brand="Lagavulin",
            origin_or_region="Islay, Scotland",
            vintage_or_year="2023",
            status="owned",
            user_rating=9.5,
            flavor_or_scent_notes=["peat", "smoke", "sea salt", "sherry cask"],
            specs={"cask": "ex-bourbon and sherry", "abv": "43%", "peat_ppm": 35},
            review="The quintessential Islay malt. Rich campfire smoke with lingering sweet dried fruit.",
            personal_notes="Cellar Shelf 2, Bottle 3",
            price_tier="$$$",
        )
        d = item.to_firestore_dict()
        self.assertEqual(d["category"], "whiskey")
        self.assertEqual(d["maker_or_brand"], "Lagavulin")
        self.assertEqual(d["user_rating"], 9.5)
        self.assertIn("peat", d["flavor_or_scent_notes"])
        self.assertEqual(d["specs"]["abv"], "43%")
        self.assertIn("updated_at", d)

    def test_sensory_item_model_perfume(self):
        item = SensoryItemModel(
            id="sens_oud_wood",
            category="fragrance",  # Tests synonym normalization to 'perfume'
            name="Oud Wood",
            maker_or_brand="Tom Ford",
            origin_or_region="USA",
            status="wishlist",
            user_rating=9.0,
            flavor_or_scent_notes=["oud", "rosewood", "cardamom", "sandalwood", "amber"],
            specs={
                "concentration": "Eau de Parfum",
                "top_notes": "Cardamom, Rosewood",
                "heart_notes": "Oud, Sandalwood, Vetiver",
                "base_notes": "Tonka bean, Amber",
            },
            review="Subtle, dark, luxurious smoky-amber masterpiece.",
        )
        d = item.to_firestore_dict()
        self.assertEqual(d["category"], "perfume")
        self.assertEqual(d["status"], "wishlist")
        self.assertEqual(d["specs"]["concentration"], "Eau de Parfum")

    def test_sensory_item_model_watch(self):
        item = SensoryItemModel(
            id="sens_speedmaster",
            category="timepiece",  # Tests synonym normalization to 'watch'
            name="Speedmaster Professional 'Moonwatch'",
            maker_or_brand="Omega",
            origin_or_region="Switzerland",
            vintage_or_year="Ref. 310.30.42.50.01.002",
            status="owned",
            user_rating=9.8,
            flavor_or_scent_notes=["iconic", "hesalite", "step-dial"],
            specs={
                "caliber": "Omega 3861 Co-Axial Master Chronometer",
                "case_size_mm": 42,
                "power_reserve_hrs": 50,
                "water_resistance": "50m",
            },
        )
        d = item.to_firestore_dict()
        self.assertEqual(d["category"], "watch")
        self.assertEqual(d["specs"]["case_size_mm"], 42)

    def test_sensory_item_model_tea_and_coffee_and_chocolate(self):
        tea = SensoryItemModel(
            id="sens_gyokuro",
            category="tea",
            name="Uji Gyokuro",
            maker_or_brand="Ippodo",
            origin_or_region="Kyoto, Japan",
            status="owned",
            user_rating=9.2,
            flavor_or_scent_notes=["umami", "sweet seaweed", "steamed greens"],
            specs={"brew_temp_c": 50, "steep_time_secs": 90},
        )
        self.assertEqual(tea.category, "tea")

        coffee = SensoryItemModel(
            id="sens_geisha",
            category="coffee",
            name="Panama Geisha Natural",
            maker_or_brand="Sey Coffee",
            origin_or_region="Boquete, Panama",
            status="sampled",
            user_rating=9.6,
            flavor_or_scent_notes=["bergamot", "jasmine", "peach"],
            specs={"process": "Natural", "altitude_m": 1850},
        )
        self.assertEqual(coffee.category, "coffee")

        chocolate = SensoryItemModel(
            id="sens_guanaja",
            category="cacao",  # Synonym normalization to chocolate
            name="Guanaja 70%",
            maker_or_brand="Valrhona",
            origin_or_region="France",
            status="owned",
            user_rating=8.8,
            flavor_or_scent_notes=["dark cocoa", "roasted nuts", "warm wood"],
            specs={"cacao_pct": 70},
        )
        self.assertEqual(chocolate.category, "chocolate")

    def test_restaurant_model(self):
        rest = RestaurantModel(
            id="rest_le_bernardin",
            name="Le Bernardin",
            city="New York",
            neighborhood="Midtown",
            cuisine="French Seafood",
            status="visited",
            user_rating=9.7,
            michelin_status="3-Star",
            price_tier="$$$$",
            standout_dishes=["Tuna Tartare with Foie Gras", "Poached Halibut with Daikon Cabbage"],
            notes_and_review="Flawless seafood execution, legendary service by Maguy Le Coze and Eric Ripert.",
            vibe_tags=["timeless luxury", "white tablecloth", "special occasion"],
        )
        d = rest.to_firestore_dict()
        self.assertEqual(d["city"], "New York")
        self.assertEqual(d["michelin_status"], "3-Star")
        self.assertEqual(len(d["standout_dishes"]), 2)
        self.assertIn("timeless luxury", d["vibe_tags"])
        self.assertIn("updated_at", d)

    def test_sensory_service_crud_mock(self):
        service = SensoryService()
        fake_storage = {}

        def mock_set(doc_id, data, merge=True):
            if merge and doc_id in fake_storage:
                fake_storage[doc_id].update(data)
            else:
                fake_storage[doc_id] = dict(data)

        service.set = MagicMock(side_effect=mock_set)
        service.get_by_id = MagicMock(side_effect=lambda doc_id: fake_storage.get(doc_id))
        service.stream_all = MagicMock(side_effect=lambda limit=None: list(fake_storage.values()))

        # Log item
        res = service.log_item(
            category="whiskey",
            name="Springbank 15",
            maker_or_brand="Springbank",
            origin_or_region="Campbeltown, Scotland",
            status="owned",
            user_rating=9.4,
            flavor_or_scent_notes=["toffee", "maritime", "dunnage", "smoke"],
            specs={"cask": "sherry wood", "abv": "46%"},
            review="Brilliant maritime complexity.",
        )
        self.assertEqual(res["status"], "success")
        item_id = res["item"]["id"]

        # Search by tag
        matches = service.search(tag="maritime")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["name"], "Springbank 15")

        # Search by category
        whiskeys = service.search(category="whiskey")
        self.assertEqual(len(whiskeys), 1)

        # Update item
        up_res = service.update_item(
            item_id=item_id,
            user_rating=9.8,
            flavor_or_scent_notes=["toffee", "maritime", "dunnage", "smoke", "dried fig"],
        )
        self.assertEqual(up_res["status"], "success")

        # Check stats
        stats = service.get_stats()
        self.assertEqual(stats["total_items"], 1)
        self.assertIn("whiskey", stats["by_category"])
        self.assertIn("toffee", stats["top_flavor_notes"])

    def test_restaurant_service_crud_mock(self):
        service = RestaurantService()
        fake_storage = {}

        def mock_set(doc_id, data, merge=True):
            if merge and doc_id in fake_storage:
                fake_storage[doc_id].update(data)
            else:
                fake_storage[doc_id] = dict(data)

        service.set = MagicMock(side_effect=mock_set)
        service.get_by_id = MagicMock(side_effect=lambda doc_id: fake_storage.get(doc_id))
        service.stream_all = MagicMock(side_effect=lambda limit=None: list(fake_storage.values()))

        # Log restaurant
        res = service.log_restaurant(
            name="Septime",
            city="Paris",
            cuisine="Neo-Bistro",
            neighborhood="11th Arr.",
            status="visited",
            user_rating=9.5,
            michelin_status="1-Star",
            price_tier="$$$",
            standout_dishes=["Smoked egg yolk with seasonal mushrooms"],
            vibe_tags=["natural wine", "relaxed excellence", "farm to table"],
        )
        self.assertEqual(res["status"], "success")
        rest_id = res["restaurant"]["id"]

        # Search by city
        paris_spots = service.search(city="Paris")
        self.assertEqual(len(paris_spots), 1)

        # Search by vibe
        wine_spots = service.search(vibe="natural wine")
        self.assertEqual(len(wine_spots), 1)

        # Update restaurant
        up_res = service.update_restaurant(
            restaurant_id=rest_id,
            standout_dishes=["Smoked egg yolk", "Roasted monkfish with wild garlic"],
        )
        self.assertEqual(up_res["status"], "success")

        # Stats
        stats = service.get_stats()
        self.assertEqual(stats["total_places"], 1)
        self.assertIn("Paris", stats["top_cities"])
        self.assertIn("Neo-Bistro", stats["top_cuisines"])

    def test_sensory_and_restaurant_recommendations(self):
        mock_sensory = MagicMock()
        mock_sensory.stream_all.return_value = [
            {
                "category": "whiskey",
                "name": "Lagavulin 16",
                "maker_or_brand": "Lagavulin",
                "user_rating": 9.5,
                "flavor_or_scent_notes": ["peat", "smoke", "sea salt"],
            },
            {
                "category": "perfume",
                "name": "Oud Wood",
                "maker_or_brand": "Tom Ford",
                "user_rating": 9.0,
                "flavor_or_scent_notes": ["oud", "rosewood", "amber"],
            }
        ]

        mock_dining = MagicMock()
        mock_dining.stream_all.return_value = [
            {
                "name": "Septime",
                "city": "Paris",
                "cuisine": "Neo-Bistro",
                "status": "visited",
                "user_rating": 9.5,
                "vibe_tags": ["natural wine", "relaxed excellence"],
            }
        ]

        rec_service = RecommendationService(
            book_service=MagicMock(),
            media_service=MagicMock(),
            books_client=MagicMock(),
            tmdb_client=MagicMock(),
            sensory_service=mock_sensory,
            restaurant_service=mock_dining,
        )

        # Sensory profile
        profile = rec_service.get_sensory_taste_profile()
        self.assertEqual(profile["status"], "success")
        self.assertIn("peat", profile["top_flavor_and_scent_accords"])
        self.assertIn("Lagavulin", profile["favorite_makers_or_distilleries"])

        # Sensory recommendation
        whiskey_recs = rec_service.get_sensory_recommendations(category="whiskey", limit=3)
        self.assertEqual(whiskey_recs["status"], "success")
        self.assertEqual(whiskey_recs["category"], "whiskey")
        self.assertGreater(len(whiskey_recs["recommendations"]), 0)

        # Restaurant recommendation
        dining_recs = rec_service.get_restaurant_recommendations(city="Paris", limit=2)
        self.assertEqual(dining_recs["status"], "success")
        self.assertEqual(dining_recs["city"], "Paris")
        self.assertGreater(len(dining_recs["recommendations"]), 0)

    @patch("requests.get")
    def test_catalog_client_mock(self, mock_get):
        # Mock Open Food Facts response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "products": [
                {
                    "product_name": "Single Origin Dark Chocolate 70%",
                    "brands": "Valrhona",
                    "origins": "Madagascar",
                    "code": "3338330001234",
                }
            ]
        }
        mock_get.return_value = mock_resp

        client = ConnoisseurCatalogClient()
        results = client.search_catalog(category="chocolate", query="Valrhona")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["brand"], "Valrhona")
        self.assertEqual(results[0]["barcode"], "3338330001234")


if __name__ == "__main__":
    unittest.main()
