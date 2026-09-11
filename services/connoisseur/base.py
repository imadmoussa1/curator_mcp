"""
Base domain service for all connoisseur and sensory goods.
Provides typed access, scoping by category, and consistent validation.
"""

from datetime import datetime, timezone
import uuid
import re
from typing import Optional, List, Dict, Any
from collections import Counter

from models import SensoryItemModel
from services.base_repository import BaseFirestoreRepository


class BaseConnoisseurService(BaseFirestoreRepository):
    """
    Abstract base service for an individual connoisseur domain category
    (e.g., Whiskey, Wine, Coffee, Tea, Perfume, etc.).
    """

    def __init__(self, category_name: str, repository: Optional[BaseFirestoreRepository] = None):
        super().__init__("sensory_vault")
        self.category_name = category_name.lower().strip()
        self._repo = repository

    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        if self._repo:
            return self._repo.get_by_id(doc_id)
        return super().get_by_id(doc_id)

    def set(self, doc_id: str, data: Dict[str, Any], merge: bool = True) -> None:
        if self._repo:
            return self._repo.set(doc_id, data, merge=merge)
        return super().set(doc_id, data, merge=merge)

    def stream_all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if self._repo:
            return self._repo.stream_all(limit=limit)
        return super().stream_all(limit=limit)

    def _generate_id(self, maker: str, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", f"{self.category_name}_{maker}_{name}".lower()).strip("_")
        return f"sens_{slug[:28]}_{uuid.uuid4().hex[:6]}"

    @staticmethod
    def _normalize_str(s: str) -> str:
        if not s:
            return ""
        st = s.strip().lower()
        st = re.sub(r"^(the|a|an)\s+", "", st)
        return re.sub(r"[^a-z0-9]", "", st)

    def find_existing(self, name: str, maker_or_brand: str) -> Optional[Dict[str, Any]]:
        norm_n = self._normalize_str(name)
        norm_m = self._normalize_str(maker_or_brand)
        raw_n = name.strip().lower()
        raw_m = maker_or_brand.strip().lower()
        for doc in self.stream_all():
            if (doc.get("category") or "").lower() != self.category_name:
                continue
            dn = (doc.get("name") or "").strip().lower()
            dm = (doc.get("maker_or_brand") or "").strip().lower()
            if (dn == raw_n or self._normalize_str(dn) == norm_n) and (dm == raw_m or self._normalize_str(dm) == norm_m):
                return doc
        return None

    def log(
        self,
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
        Generic logger for items within this service's specific domain category.
        """
        rating_val = None
        if user_rating is not None:
            rating_val = round(max(1.0, min(10.0, float(user_rating))), 1)

        existing = self.find_existing(name, maker_or_brand)
        if existing:
            doc_id = existing["id"]
            existing["status"] = status
            if rating_val is not None:
                existing["user_rating"] = rating_val
            if flavor_or_scent_notes:
                existing["flavor_or_scent_notes"] = list(set(existing.get("flavor_or_scent_notes", []) + [n.strip().lower() for n in flavor_or_scent_notes if n.strip()]))
            if review:
                existing["review"] = review
            if personal_notes:
                existing["personal_notes"] = f"{existing.get('personal_notes', '')} | {personal_notes}".strip(" | ")
            if specs:
                existing.setdefault("specs", {}).update(specs)
            if date_experienced:
                existing["date_experienced"] = date_experienced
            existing["updated_at"] = datetime.now(timezone.utc)
            self.set(doc_id, existing)
            return {
                "status": "success",
                "message": f"Updated existing {self.category_name.capitalize()} '{existing.get('name', name)}' by {maker_or_brand} (duplicate prevented).",
                "item": existing
            }

        doc_id = item_id.strip() if item_id else self._generate_id(maker_or_brand, name)
        if not date_experienced:
            date_experienced = datetime.now().strftime("%Y-%m-%d")

        item = SensoryItemModel(
            id=doc_id,
            category=self.category_name,
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
            "message": f"Successfully logged {self.category_name.capitalize()} '{item.name}' by {item.maker_or_brand}.",
            "item": item.to_firestore_dict(),
        }

    def update(
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
        Update an existing item within this category.
        """
        existing = self.get_by_id(item_id)
        if not existing:
            return {"status": "error", "message": f"Item '{item_id}' not found."}
        if existing.get("category") != self.category_name:
            return {"status": "error", "message": f"Item '{item_id}' belongs to category '{existing.get('category')}', not '{self.category_name}'."}

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
            "message": f"Updated {self.category_name} item '{item_id}'.",
            "item_id": item_id,
            "updated_fields": list(updates.keys()),
        }

    def stream_category(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all documents strictly within this category.
        """
        results = [
            it for it in self.stream_all()
            if it.get("category") == self.category_name
        ]
        return results[:limit] if limit else results

    def search(
        self,
        query: str = "",
        status: Optional[str] = None,
        min_rating: Optional[float] = None,
        tag: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search items scoped strictly to this service's domain category.
        """
        q_norm = query.lower().strip()
        tag_norm = tag.lower().strip() if tag else None
        status_norm = status.lower().strip() if status else None

        results = []
        for item in self.stream_category():
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
        Generate macro metrics for this specific category.
        """
        items = self.stream_category()
        by_status = Counter()
        notes_counter = Counter()
        makers_counter = Counter()
        ratings = []

        for it in items:
            by_status[it.get("status", "owned")] += 1
            if it.get("maker_or_brand"):
                makers_counter[it["maker_or_brand"]] += 1
            for note in it.get("flavor_or_scent_notes", []):
                notes_counter[note.lower()] += 1
            if it.get("user_rating"):
                ratings.append(it["user_rating"])

        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

        return {
            "category": self.category_name,
            "total_items": len(items),
            "by_status": dict(by_status),
            "average_rating": avg_rating,
            "top_flavor_notes": [n for n, _ in notes_counter.most_common(8)],
            "top_makers_or_brands": [m for m, _ in makers_counter.most_common(5)],
        }
