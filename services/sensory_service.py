"""
Sensory Vault Facade & Coordinator:
Provides a unified interface over individual connoisseur domain services:
WhiskeyService, WineService, CoffeeService, TeaService, GinService,
ChocolateService, PerfumeService, and WatchService.
"""

from typing import Optional, List, Dict, Any
from collections import Counter

from services.base_repository import BaseFirestoreRepository
from services.connoisseur import (
    BaseConnoisseurService,
    WhiskeyService,
    WineService,
    CoffeeService,
    TeaService,
    GinService,
    ChocolateService,
    PerfumeService,
    WatchService,
)


class SensoryService(BaseFirestoreRepository):
    """
    Facade and service coordinator over specialized connoisseur domain services.
    Adheres to the Single Responsibility Principle by delegating category-specific
    operations to dedicated domain service classes.
    """

    def __init__(
        self,
        whiskey_service: Optional[WhiskeyService] = None,
        wine_service: Optional[WineService] = None,
        coffee_service: Optional[CoffeeService] = None,
        tea_service: Optional[TeaService] = None,
        gin_service: Optional[GinService] = None,
        chocolate_service: Optional[ChocolateService] = None,
        perfume_service: Optional[PerfumeService] = None,
        watch_service: Optional[WatchService] = None,
    ):
        super().__init__("sensory_vault")
        self.whiskey = whiskey_service or WhiskeyService(repository=self)
        self.wine = wine_service or WineService(repository=self)
        self.coffee = coffee_service or CoffeeService(repository=self)
        self.tea = tea_service or TeaService(repository=self)
        self.gin = gin_service or GinService(repository=self)
        self.chocolate = chocolate_service or ChocolateService(repository=self)
        self.perfume = perfume_service or PerfumeService(repository=self)
        self.watch = watch_service or WatchService(repository=self)

        self._registry: Dict[str, BaseConnoisseurService] = {
            "whiskey": self.whiskey,
            "wine": self.wine,
            "coffee": self.coffee,
            "tea": self.tea,
            "gin": self.gin,
            "chocolate": self.chocolate,
            "perfume": self.perfume,
            "watch": self.watch,
        }

    def _get_service_for_category(self, category: str) -> BaseConnoisseurService:
        """Resolve specialized service from category name or synonym."""
        c_clean = category.strip().lower()
        synonyms = {
            "whisky": "whiskey",
            "scotch": "whiskey",
            "bourbon": "whiskey",
            "fragrance": "perfume",
            "cologne": "perfume",
            "scent": "perfume",
            "watches": "watch",
            "timepiece": "watch",
            "cacao": "chocolate",
            "choc": "chocolate",
        }
        normalized = synonyms.get(c_clean, c_clean)
        return self._registry.get(normalized, self.whiskey)

    def log_item(
        self,
        category: str,
        name: str,
        maker_or_brand: str,
        origin_or_region: Optional[str] = None,
        vintage_or_year: Optional[str] = None,
        status: str = "owned",
        user_rating: Optional[float] = None,
        flavor_or_scent_notes: Optional[List[str]] = None,
        specs: Optional[Dict[str, Any]] = None,
        review: Optional[str] = "",
        personal_notes: Optional[str] = "",
        price_tier: Optional[str] = None,
        date_experienced: Optional[str] = None,
        item_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Delegate logging to the appropriate specialized domain service class.
        """
        sub_service = self._get_service_for_category(category)
        return sub_service.log(
            name=name,
            maker_or_brand=maker_or_brand,
            origin_or_region=origin_or_region,
            vintage_or_year=vintage_or_year,
            status=status,
            user_rating=user_rating,
            flavor_or_scent_notes=flavor_or_scent_notes,
            specs=specs,
            review=review,
            personal_notes=personal_notes,
            price_tier=price_tier,
            date_experienced=date_experienced,
            item_id=item_id,
        )

    def update_item(
        self,
        item_id: str,
        user_rating: Optional[float] = None,
        status: Optional[str] = None,
        review: Optional[str] = None,
        personal_notes: Optional[str] = None,
        flavor_or_scent_notes: Optional[List[str]] = None,
        specs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update an item by finding its category and delegating to the specialized domain service.
        """
        existing = self.get_by_id(item_id)
        if not existing:
            return {"status": "error", "message": f"Item '{item_id}' not found in sensory vault."}

        category = existing.get("category", "whiskey")
        sub_service = self._get_service_for_category(category)
        return sub_service.update(
            item_id=item_id,
            user_rating=user_rating,
            status=status,
            review=review,
            personal_notes=personal_notes,
            flavor_or_scent_notes=flavor_or_scent_notes,
            specs=specs,
        )

    def search(
        self,
        query: str = "",
        category: Optional[str] = None,
        status: Optional[str] = None,
        min_rating: Optional[float] = None,
        tag: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search sensory vault items. If category is provided, delegates to that specific domain service.
        Otherwise, aggregates search results across all items.
        """
        if category:
            sub_service = self._get_service_for_category(category)
            return sub_service.search(
                query=query,
                status=status,
                min_rating=min_rating,
                tag=tag,
                limit=limit,
            )

        q_norm = query.lower().strip()
        tag_norm = tag.lower().strip() if tag else None
        status_norm = status.lower().strip() if status else None

        results = []
        for item in self.stream_all():
            if status_norm and item.get("status") != status_norm:
                continue
            if min_rating and (item.get("user_rating") or 0) < min_rating:
                continue
            if tag_norm and not any(tag_norm in n.lower() for n in item.get("flavor_or_scent_notes", [])):
                continue

            if q_norm:
                searchable = " ".join([
                    str(item.get("name", "")),
                    str(item.get("maker_or_brand", "")),
                    str(item.get("origin_or_region", "")),
                    str(item.get("review", "")),
                    str(item.get("personal_notes", "")),
                    " ".join(item.get("flavor_or_scent_notes", [])),
                ]).lower()
                if q_norm not in searchable:
                    continue

            results.append(item)
            if len(results) >= limit:
                break

        return results

    def get_stats(self) -> Dict[str, Any]:
        """
        Generate macro analytics across the entire sensory vault.
        """
        items = self.stream_all()
        by_category = Counter()
        by_status = Counter()
        notes_counter = Counter()
        makers_counter = Counter()
        ratings = []

        for it in items:
            cat = it.get("category", "other")
            by_category[cat] += 1
            by_status[it.get("status", "owned")] += 1
            if it.get("maker_or_brand"):
                makers_counter[it["maker_or_brand"]] += 1
            for note in it.get("flavor_or_scent_notes", []):
                notes_counter[note.lower()] += 1
            if it.get("user_rating"):
                ratings.append(it["user_rating"])

        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

        return {
            "total_items": len(items),
            "by_category": dict(by_category),
            "by_status": dict(by_status),
            "average_rating": avg_rating,
            "top_flavor_notes": [n for n, _ in notes_counter.most_common(8)],
            "top_makers_or_brands": [m for m, _ in makers_counter.most_common(5)],
        }
