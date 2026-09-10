"""
Domain service managing dining experiences, restaurant wishlists, and gastronomic journals:
Restaurants, Cafes, Wine Bars, and Omakase Counters.
Stored in the Firestore 'restaurants' collection.
"""

from datetime import datetime, timezone
import uuid
import re
from typing import Optional, List, Dict, Any
from collections import Counter

from models import RestaurantModel
from services.base_repository import BaseFirestoreRepository


class RestaurantService(BaseFirestoreRepository):
    """
    Business logic and persistence layer for fine dining and culinary discovery.
    """

    def __init__(self):
        super().__init__("restaurants")

    def _generate_restaurant_id(self, city: str, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", f"{city}_{name}".lower()).strip("_")
        return f"rest_{slug[:28]}_{uuid.uuid4().hex[:6]}"

    def log_restaurant(
        self,
        name: str,
        city: str,
        cuisine: str,
        neighborhood: Optional[str] = None,
        status: str = "visited",
        user_rating: Optional[float] = None,
        michelin_status: Optional[str] = None,
        price_tier: Optional[str] = None,
        standout_dishes: Optional[List[str]] = None,
        notes_and_review: Optional[str] = "",
        vibe_tags: Optional[List[str]] = None,
        url_or_reservation: Optional[str] = None,
        date_visited: Optional[str] = None,
        restaurant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Log a restaurant visit or add a restaurant to the dining wishlist.
        """
        doc_id = restaurant_id.strip() if restaurant_id else self._generate_restaurant_id(city, name)
        if not date_visited and status == "visited":
            date_visited = datetime.now().strftime("%Y-%m-%d")

        rating_val = None
        if user_rating is not None:
            rating_val = round(max(1.0, min(10.0, float(user_rating))), 1)

        rest = RestaurantModel(
            id=doc_id,
            name=name.strip(),
            city=city.strip().title(),
            neighborhood=neighborhood.strip() if neighborhood else None,
            cuisine=cuisine.strip().title(),
            status=status,
            user_rating=rating_val,
            michelin_status=michelin_status,
            price_tier=price_tier,
            standout_dishes=[d.strip() for d in (standout_dishes or []) if d.strip()],
            notes_and_review=notes_and_review or "",
            vibe_tags=[v.strip().lower() for v in (vibe_tags or []) if v.strip()],
            url_or_reservation=url_or_reservation,
            date_visited=date_visited,
            updated_at=datetime.now(timezone.utc),
        )

        self.set(doc_id, rest.to_firestore_dict())
        return {
            "status": "success",
            "message": f"Successfully logged restaurant '{rest.name}' in {rest.city} ({rest.status}).",
            "restaurant": rest.to_firestore_dict()
        }

    def update_restaurant(
        self,
        restaurant_id: str,
        status: Optional[str] = None,
        user_rating: Optional[float] = None,
        standout_dishes: Optional[List[str]] = None,
        notes_and_review: Optional[str] = None,
        vibe_tags: Optional[List[str]] = None,
        date_visited: Optional[str] = None,
        url_or_reservation: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update dining review, dishes, or change status from wishlist to visited.
        """
        existing = self.get_by_id(restaurant_id)
        if not existing:
            return {"status": "error", "message": f"Restaurant '{restaurant_id}' not found."}

        updates: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc)}
        if status is not None:
            updates["status"] = status.strip().lower()
        if user_rating is not None:
            updates["user_rating"] = round(max(1.0, min(10.0, float(user_rating))), 1)
        if standout_dishes is not None:
            updates["standout_dishes"] = [d.strip() for d in standout_dishes if d.strip()]
        if notes_and_review is not None:
            updates["notes_and_review"] = notes_and_review.strip()
        if vibe_tags is not None:
            updates["vibe_tags"] = [v.strip().lower() for v in vibe_tags if v.strip()]
        if date_visited is not None:
            updates["date_visited"] = date_visited
        if url_or_reservation is not None:
            updates["url_or_reservation"] = url_or_reservation

        self.set(restaurant_id, updates, merge=True)
        return {
            "status": "success",
            "message": f"Updated restaurant '{restaurant_id}'.",
            "restaurant_id": restaurant_id,
            "updated_fields": list(updates.keys())
        }

    def search(
        self,
        query: str = "",
        city: Optional[str] = None,
        cuisine: Optional[str] = None,
        status: Optional[str] = None,
        vibe: Optional[str] = None,
        min_rating: Optional[float] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search and filter restaurant records by city, cuisine, vibe tag, or keywords.
        """
        q_norm = query.lower().strip()
        city_norm = city.lower().strip() if city else None
        cuisine_norm = cuisine.lower().strip() if cuisine else None
        status_norm = status.lower().strip() if status else None
        vibe_norm = vibe.lower().strip() if vibe else None

        results = []
        for r in self.stream_all():
            if city_norm and city_norm not in r.get("city", "").lower():
                continue
            if cuisine_norm and cuisine_norm not in r.get("cuisine", "").lower():
                continue
            if status_norm and r.get("status") != status_norm:
                continue
            if min_rating and (r.get("user_rating") or 0) < min_rating:
                continue
            if vibe_norm and not any(vibe_norm in v.lower() for v in r.get("vibe_tags", [])):
                continue

            if q_norm:
                searchable = " ".join([
                    str(r.get("name", "")),
                    str(r.get("city", "")),
                    str(r.get("neighborhood", "")),
                    str(r.get("cuisine", "")),
                    str(r.get("notes_and_review", "")),
                    " ".join(r.get("standout_dishes", [])),
                    " ".join(r.get("vibe_tags", [])),
                ]).lower()
                if q_norm not in searchable:
                    continue

            results.append(r)
            if len(results) >= limit:
                break

        return results

    def get_stats(self) -> Dict[str, Any]:
        """
        Generate macro analytics across the dining collection.
        """
        restaurants = self.stream_all()
        by_status = Counter()
        by_city = Counter()
        by_cuisine = Counter()
        michelin_counter = Counter()
        ratings = []

        for r in restaurants:
            by_status[r.get("status", "visited")] += 1
            if r.get("city"):
                by_city[r["city"]] += 1
            if r.get("cuisine"):
                by_cuisine[r["cuisine"]] += 1
            if r.get("michelin_status"):
                michelin_counter[r["michelin_status"]] += 1
            if r.get("user_rating"):
                ratings.append(r["user_rating"])

        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0

        return {
            "total_places": len(restaurants),
            "by_status": dict(by_status),
            "top_cities": [c for c, _ in by_city.most_common(5)],
            "top_cuisines": [cu for cu, _ in by_cuisine.most_common(5)],
            "michelin_count": dict(michelin_counter),
            "average_rating": avg_rating,
        }
