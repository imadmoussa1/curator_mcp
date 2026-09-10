"""
Unit tests for modular, decoupled connoisseur domain services:
WhiskeyService, WineService, CoffeeService, TeaService, GinService,
ChocolateService, PerfumeService, WatchService, and SensoryService facade.
"""

import unittest
from unittest.mock import MagicMock
from services.connoisseur import (
    WhiskeyService,
    WineService,
    CoffeeService,
    TeaService,
    GinService,
    ChocolateService,
    PerfumeService,
    WatchService,
)
from services.sensory_service import SensoryService


class TestConnoisseurModularServices(unittest.TestCase):

    def _setup_mock_storage(self, service):
        fake_storage = {}

        def mock_set(doc_id, data, merge=True):
            if merge and doc_id in fake_storage:
                fake_storage[doc_id].update(data)
            else:
                fake_storage[doc_id] = dict(data)

        service.set = MagicMock(side_effect=mock_set)
        service.get_by_id = MagicMock(side_effect=lambda doc_id: fake_storage.get(doc_id))
        service.stream_all = MagicMock(side_effect=lambda limit=None: list(fake_storage.values()))
        return fake_storage

    def test_whiskey_service_isolated(self):
        ws = WhiskeyService()
        self._setup_mock_storage(ws)

        res = ws.log_bottle(
            name="A'bunadh Batch 75",
            distillery="Aberlour",
            region="Speyside, Scotland",
            cask_finish="Oloroso Sherry Butts",
            abv="60.8%",
            peat_level="Unpeated",
            user_rating=9.6,
            tasting_notes=["sherry", "dark chocolate", "raisin", "orange peel", "cinnamon"],
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["item"]["category"], "whiskey")
        self.assertEqual(res["item"]["specs"]["cask"], "Oloroso Sherry Butts")
        self.assertEqual(res["item"]["specs"]["abv"], "60.8%")

        # Search scoped to whiskey
        search_res = ws.search(tag="sherry")
        self.assertEqual(len(search_res), 1)

        stats = ws.get_stats()
        self.assertEqual(stats["category"], "whiskey")
        self.assertEqual(stats["total_items"], 1)

    def test_wine_service_isolated(self):
        wine_s = WineService()
        self._setup_mock_storage(wine_s)

        res = wine_s.log_wine(
            name="Tignanello",
            producer_or_estate="Marchesi Antinori",
            region_or_appellation="Tuscany, Italy",
            vintage="2019",
            varietal="Sangiovese / Cabernet",
            body="Full",
            tannin="Structured",
            acidity="Vibrant",
            user_rating=9.5,
            tasting_notes=["black cherry", "leather", "balsamic", "tobacco"],
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["item"]["category"], "wine")
        self.assertEqual(res["item"]["specs"]["varietal"], "Sangiovese / Cabernet")

        matches = wine_s.search(tag="leather")
        self.assertEqual(len(matches), 1)

    def test_coffee_service_isolated(self):
        cs = CoffeeService()
        self._setup_mock_storage(cs)

        res = cs.log_beans(
            name="Worka Sakaro",
            roaster="Sey Coffee",
            origin_country_or_farm="Gedeb, Ethiopia",
            process_method="Anaerobic Natural",
            roast_level="Light",
            altitude_m=2100,
            user_rating=9.7,
            flavor_notes=["peach", "candied citrus", "jasmine tea"],
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["item"]["category"], "coffee")
        self.assertEqual(res["item"]["specs"]["process"], "Anaerobic Natural")

        matches = cs.search(query="Sey")
        self.assertEqual(len(matches), 1)

    def test_tea_service_isolated(self):
        ts = TeaService()
        self._setup_mock_storage(ts)

        res = ts.log_tea(
            name="Da Hong Pao",
            producer_or_house="Wuyi Rock Tea Estate",
            origin_region="Wuyi Mountains, China",
            harvest_year_or_season="Spring 2024",
            brew_temp_c=95,
            steep_time_secs=30,
            oxidation_level="Medium-Heavy",
            user_rating=9.3,
            flavor_notes=["mineral rock", "roasted orchid", "honeyed wood"],
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["item"]["category"], "tea")
        self.assertEqual(res["item"]["specs"]["brew_temp_c"], 95)
        self.assertEqual(res["item"]["specs"]["steep_time_secs"], 30)

    def test_gin_service_isolated(self):
        gs = GinService()
        self._setup_mock_storage(gs)

        res = gs.log_gin(
            name="Schwarzwald Dry 47",
            distillery="Monkey 47",
            country_or_region="Black Forest, Germany",
            style="Dry Gin",
            botanicals=["lingonberry", "spruce", "juniper", "sage"],
            abv="47%",
            user_rating=9.4,
            flavor_notes=["pine", "botanical complexity", "berry tartness"],
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["item"]["category"], "gin")
        self.assertEqual(res["item"]["specs"]["abv"], "47%")
        self.assertIn("lingonberry", res["item"]["specs"]["botanicals"])

    def test_chocolate_service_isolated(self):
        choc_s = ChocolateService()
        self._setup_mock_storage(choc_s)

        res = choc_s.log_chocolate(
            name="Porcelana 70%",
            chocolatier_or_maker="Amedei",
            cacao_percentage=70,
            bean_origin="Venezuela",
            cacao_variety="Criollo",
            user_rating=9.5,
            flavor_notes=["toasted almond", "olive wood", "butterscotch"],
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["item"]["category"], "chocolate")
        self.assertEqual(res["item"]["specs"]["cacao_pct"], 70)
        self.assertEqual(res["item"]["specs"]["cacao_variety"], "Criollo")

    def test_perfume_service_isolated(self):
        ps = PerfumeService()
        self._setup_mock_storage(ps)

        res = ps.log_fragrance(
            name="Gris Charnel",
            house_or_perfumer="BDK Parfums",
            concentration="Extrait de Parfum",
            top_notes="Cardamom, Black Tea, Fig",
            heart_notes="Iris, Bourbon Vetiver, Cistus",
            base_notes="Sandalwood, Cedar, Tonka Bean",
            user_rating=9.8,
            accords=["spicy", "woody", "tea", "powdery"],
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["item"]["category"], "perfume")
        self.assertEqual(res["item"]["specs"]["concentration"], "Extrait de Parfum")
        self.assertIn("Cardamom", res["item"]["specs"]["top_notes"])

    def test_watch_service_isolated(self):
        watch_s = WatchService()
        self._setup_mock_storage(watch_s)

        res = watch_s.log_timepiece(
            name="Submariner Date",
            watchmaker_or_brand="Rolex",
            reference_number="126610LN",
            movement_type="Automatic",
            caliber="Rolex 3235",
            case_size_mm=41,
            power_reserve_hrs=70,
            water_resistance="300m",
            complications=["Date"],
            user_rating=9.7,
            tags=["iconic", "diver", "cerachrom"],
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["item"]["category"], "watch")
        self.assertEqual(res["item"]["specs"]["caliber"], "Rolex 3235")
        self.assertEqual(res["item"]["specs"]["case_size_mm"], 41)

    def test_sensory_service_facade_delegation(self):
        # Create sensory facade with our mocked sub-services
        ws = WhiskeyService()
        self._setup_mock_storage(ws)
        ps = PerfumeService()
        self._setup_mock_storage(ps)

        facade = SensoryService(whiskey_service=ws, perfume_service=ps)

        # Log through facade
        res_whiskey = facade.log_item(
            category="whisky",  # Synonym normalization
            name="Lagavulin 16",
            maker_or_brand="Lagavulin",
            origin_or_region="Islay",
            user_rating=9.5,
            flavor_or_scent_notes=["peat", "smoke"],
        )
        self.assertEqual(res_whiskey["status"], "success")
        self.assertEqual(res_whiskey["item"]["category"], "whiskey")

        # Category search delegates to specialized service
        results = facade.search(category="whiskey", tag="peat")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Lagavulin 16")


if __name__ == "__main__":
    unittest.main()
