"""
External catalog client for sensory goods:
- Open Food Facts (Free, open database for tea, coffee, wine, chocolate)
- Whisky Hunter API (Open distillery & whisky data)
- TheCocktailDB (Open ingredients, gin & spirits botanical database)
"""

import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger("curator_mcp.catalog_client")


class ConnoisseurCatalogClient:
    """
    Client for querying open sensory, food, and spirits catalogs.
    """

    OPEN_FOOD_FACTS_SEARCH = "https://world.openfoodfacts.org/cgi/search.pl"
    WHISKY_HUNTER_API = "https://whiskyhunter.net/api/distilleries_info/"
    COCKTAIL_DB_INGREDIENT = "https://www.thecocktaildb.com/api/json/v1/1/search.php"

    def __init__(self, timeout: int = 6):
        self.timeout = timeout

    def search_open_food_facts(self, query: str, category_tag: Optional[str] = None, page_size: int = 5) -> List[Dict[str, Any]]:
        """
        Search Open Food Facts for tea, coffee, chocolate, or wine products.
        Returns product name, brand, origin/terroir, and ingredients/nutriments.
        """
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": page_size,
        }
        if category_tag:
            params["tagtype_0"] = "categories"
            params["tag_contains_0"] = "contains"
            params["tag_0"] = category_tag

        try:
            resp = requests.get(
                self.OPEN_FOOD_FACTS_SEARCH,
                params=params,
                headers={"User-Agent": "CuratorMCP - PersonalTasteEngine/1.0"},
                timeout=self.timeout
            )
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for p in data.get("products", []):
                    name = p.get("product_name") or p.get("product_name_en")
                    if not name:
                        continue
                    results.append({
                        "name": name,
                        "brand": p.get("brands") or "Unknown Maker",
                        "origins": p.get("origins") or p.get("countries") or "",
                        "categories": p.get("categories") or "",
                        "labels": p.get("labels") or "",
                        "barcode": p.get("code") or "",
                        "image_url": p.get("image_url") or "",
                    })
                return results
        except Exception as e:
            logger.warning(f"Open Food Facts lookup failed: {e}")
        return []

    def search_whisky_distilleries(self, query: str) -> List[Dict[str, Any]]:
        """
        Search Whisky Hunter for Scotch & world distilleries and regions.
        """
        try:
            resp = requests.get(
                self.WHISKY_HUNTER_API,
                headers={"User-Agent": "CuratorMCP - PersonalTasteEngine/1.0"},
                timeout=self.timeout
            )
            if resp.status_code == 200:
                distilleries = resp.json()
                q_lower = query.lower()
                matches = [
                    {
                        "name": d.get("name"),
                        "country": d.get("country"),
                        "whiskybase_id": d.get("id"),
                    }
                    for d in distilleries
                    if q_lower in d.get("name", "").lower() or q_lower in d.get("country", "").lower()
                ]
                return matches[:10]
        except Exception as e:
            logger.warning(f"Whisky Hunter lookup failed: {e}")
        return []

    def search_catalog(self, category: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Unified search router across open sensory databases.
        """
        cat_lower = category.lower()
        if "whisky" in cat_lower or "whiskey" in cat_lower or "scotch" in cat_lower:
            results = self.search_whisky_distilleries(query)
            if results:
                return results[:limit]

        # For tea, coffee, wine, chocolate, fallback to Open Food Facts
        tag_map = {
            "tea": "teas",
            "coffee": "coffees",
            "chocolate": "chocolates",
            "wine": "wines",
            "gin": "gins",
        }
        tag = tag_map.get(cat_lower)
        return self.search_open_food_facts(query, category_tag=tag, page_size=limit)
