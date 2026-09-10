"""
Domain service managing luxury, artisanal, and sensory items:
Tea, Coffee, Whiskey, Gin, Wine, Chocolate, Perfume, and Watches.
Stored in the Firestore 'sensory_vault' collection.
"""

from datetime import datetime, timezone
import uuid
import re
from typing import Optional, List, Dict, Any
from collections import Counter

from models import SensoryItemModel, SensoryCategory, SensoryStatus
from services.base_repository import BaseFirestoreRepository


class SensoryService(BaseFirestoreRepository):
    """
    Business logic and persistence layer for sensory goods and luxury timepieces.
    """

    def __init__(self):
        super().__init__("sensory_vault")

    def _generate_sensory_id(self, category: str, maker: str, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", f"{category}_{maker}_{name}".lower()).strip("_")
        return f"sens_{slug[:28]}_{uuid.uuid4().hex[:6]}"

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
        Log or upsert a sensory item (tea, coffee, whiskey, gin, wine, chocolate, perfume, watch).
        """
        doc_id = item_id.strip() if item_id else self._generate_sensory_id(category, maker_or_brand, name)
        if not date_experienced:
            date_experienced = datetime.now().strftime("%Y-%m-%d")

        rating_val = None
        if user_rating is not None:
            rating_val = round(max(1.0, min(10.0, float(user_rating))), 1)

        item = SensoryItemModel(
            id=doc_id,
            category=category,
            name=name.strip(),
            maker_or_brand=maker_or_brand.strip(),
            origin_or_region=origin_or_region.strip() if origin_or_region else None,
            vintage_or_year=str(vintage_or_year).strip() if vintage_or_year else None,
            status=status,
            user_rating=rating_val,
            flavor_or_scent_notes=[n.strip().lower() for n in (flavor_or_scent_notes or []) if n.strip()],
            specs=specs or {},
            review=review or "",
            personal_notes=personal_notes or "",
            price_tier=price_tier,
            date_experienced=date_experienced,
            updated_at=datetime.now(timezone.utc),
        )

        self.set(doc_id, item.to_firestore_dict())
        return {
            "status": "success",
            "message": f"Successfully logged {item.category.capitalize()} '{item.name}' by {item.maker_or_brand} to sensory vault.",
            "item": item.to_firestore_dict()
        }

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
        Update tasting notes, ratings, or status on an existing sensory item.
        """
        existing = self.get_by_id(item_id)
        if not existing:
            return {"status": "error", "message": f"Item '{item_id}' not found in sensory vault."}

        updates: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
        if user_rating is not None:
            updates["user_rating"] = round(max(1.0, min(10.0, float(user_rating))), 1)
        if status is not None:
            updates["status"] = status.strip().lower()
        if review is not None:
            updates["review"] = review.strip()
        if personal_notes is not None:
            updates["personal_notes"] = personal_notes.strip()
        if flavor_or_scent_notes is not None:
            updates["flavor_or_scent_notes"] = [n.strip().lower() for n in flavor_or_scent_notes if n.strip()]
        if specs is not None:
            merged_specs = existing.get("specs", {})
            merged_specs.update(specs)
            updates["specs"] = merged_specs

        self.set(item_id, updates, merge=True)
        return {
            "status": "success",
            "message": f"Updated sensory item '{item_id}'.",
            "item_id": item_id,
            "updated_fields": list(updates.keys())
        }

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
        Search and filter sensory items by query keywords, category, status, rating, or sensory notes.
        """
        q_norm = query.lower().strip()
        tag_norm = tag.lower().strip() if tag else None
        cat_norm = category.lower().strip() if category else None
        status_norm = status.lower().strip() if status else None

        results = []
        for item in self.stream_all():
            if cat_norm and item.get("category") != cat_norm:
                continue
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
        Generate macro analytics across the sensory vault.
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
