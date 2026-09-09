"""
Domain service managing movies, series, watchlists, and viewing logs.
"""

from datetime import datetime, timezone
import re
import uuid
from typing import Optional, List, Dict, Any
from collections import Counter

from models import MediaModel
from services.base_repository import BaseFirestoreRepository


class MediaService(BaseFirestoreRepository):
    """Business logic and persistence layer for Movies and TV Series."""

    def __init__(self):
        super().__init__("media")

    def _generate_media_id(self, title: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", title.lower()).strip("_")
        return f"tt_{slug[:25]}_{uuid.uuid4().hex[:6]}"

    def search(
        self,
        query: str = "",
        media_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search media by title or director with optional type/status filters."""
        q_norm = query.strip().lower()
        matches = []
        docs = self.stream_all()

        for m in docs:
            if media_type and m.get("media_type", "").lower() != media_type.lower():
                continue
            if status and m.get("status", "").lower() != status.lower():
                continue
            title = (m.get("title") or "").lower()
            directors = [d.lower() for d in m.get("directors", [])]
            if not q_norm or q_norm in title or any(q_norm in d for d in directors):
                matches.append({
                    "id": m.get("id"),
                    "title": m.get("title"),
                    "media_type": m.get("media_type"),
                    "year": m.get("year"),
                    "user_rating": m.get("user_rating"),
                    "imdb_rating": m.get("imdb_rating"),
                    "status": m.get("status"),
                    "genres": m.get("genres", []),
                    "directors": m.get("directors", []),
                    "notes": m.get("notes"),
                })
                if len(matches) >= limit:
                    break
        return matches

    def get_recently_watched(self, limit: int = 10, media_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve most recently watched and rated movies or series, sorted by date rated descending."""
        docs = self.filter_by("status", "==", "watched")
        items = []
        for m in docs:
            if media_type and m.get("media_type", "").lower() != media_type.lower():
                continue
            notes = m.get("notes") or ""
            match = re.search(r"Rated on (\d{4}-\d{2}-\d{2})", notes)
            date_rated = match.group(1) if match else "1970-01-01"
            items.append({
                "id": m.get("id"),
                "title": m.get("title"),
                "media_type": m.get("media_type"),
                "year": m.get("year"),
                "user_rating": m.get("user_rating"),
                "imdb_rating": m.get("imdb_rating"),
                "date_rated": date_rated if date_rated != "1970-01-01" else None,
                "genres": m.get("genres", []),
                "directors": m.get("directors", []),
                "notes": notes,
                "_sort_date": date_rated,
            })
        items.sort(key=lambda x: x["_sort_date"], reverse=True)
        for it in items:
            it.pop("_sort_date", None)
        return items[:limit]

    def get_watchlist(
        self,
        media_type: Optional[str] = None,
        genre: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Retrieve items from user's watchlist with optional genre or type filter."""
        docs = self.filter_by("status", "==", "watchlist")
        results = []
        for m in docs:
            if media_type and m.get("media_type", "").lower() != media_type.lower():
                continue
            genres = m.get("genres", [])
            if genre and not any(g.lower() == genre.lower() for g in genres):
                continue
            results.append({
                "id": m.get("id"),
                "title": m.get("title"),
                "media_type": m.get("media_type"),
                "year": m.get("year"),
                "imdb_rating": m.get("imdb_rating"),
                "genres": genres,
                "directors": m.get("directors", []),
                "notes": m.get("notes"),
            })
            if len(results) >= limit:
                break
        return results

    def add_to_watchlist(
        self,
        title: str,
        media_type: str = "movie",
        media_id: Optional[str] = None,
        year: Optional[int] = None,
        genres: Optional[List[str]] = None,
        directors: Optional[List[str]] = None,
        imdb_rating: Optional[float] = None,
        notes: Optional[str] = ""
    ) -> Dict[str, Any]:
        """Add a movie or series to user's watchlist."""
        doc_id = media_id.strip() if media_id else self._generate_media_id(title)
        media = MediaModel(
            id=doc_id,
            title=title.strip(),
            media_type=media_type.strip(),
            status="watchlist",
            year=year,
            genres=genres or [],
            directors=directors or [],
            imdb_rating=imdb_rating,
            notes=notes or "",
            updated_at=datetime.now(timezone.utc)
        )
        self.set(doc_id, media.to_firestore_dict())
        return {
            "status": "success",
            "message": f"Added '{title}' to watchlist.",
            "media": media.to_firestore_dict()
        }

    def log_watched(
        self,
        title: str,
        media_type: str = "movie",
        user_rating: Optional[int] = None,
        media_id: Optional[str] = None,
        year: Optional[int] = None,
        genres: Optional[List[str]] = None,
        directors: Optional[List[str]] = None,
        notes: Optional[str] = ""
    ) -> Dict[str, Any]:
        """Log a film or episode as watched with optional 1-10 rating."""
        doc_id = media_id.strip() if media_id else self._generate_media_id(title)
        rating = max(1, min(10, user_rating)) if user_rating is not None else None

        media = MediaModel(
            id=doc_id,
            title=title.strip(),
            media_type=media_type.strip(),
            user_rating=rating,
            status="watched",
            year=year,
            genres=genres or [],
            directors=directors or [],
            notes=notes or "",
            updated_at=datetime.now(timezone.utc)
        )
        self.set(doc_id, media.to_firestore_dict())
        return {
            "status": "success",
            "message": f"Logged '{title}' ({media_type}) as watched" + (f" with rating {rating}/10." if rating else "."),
            "media": media.to_firestore_dict()
        }

    def get_stats(self) -> Dict[str, Any]:
        """Calculates media breakdown by status, types, and average rating."""
        docs = self.stream_all()
        status_counts = Counter()
        type_counts = Counter()
        ratings = []
        for m in docs:
            status_counts[m.get("status", "unknown")] += 1
            type_counts[m.get("media_type", "movie")] += 1
            r = m.get("user_rating")
            if r and r > 0:
                ratings.append(r)
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
        return {
            "total": len(docs),
            "watched": status_counts.get("watched", 0),
            "watchlist": status_counts.get("watchlist", 0),
            "types": dict(type_counts),
            "avg_user_rating": avg_rating,
        }

    def curate_for_tonight(
        self,
        max_runtime_mins: Optional[int] = None,
        genre: Optional[str] = None,
        min_imdb_rating: Optional[float] = None,
        media_type: Optional[str] = "movie",
        count: int = 3
    ) -> Dict[str, Any]:
        """
        Smart curation engine for your evening.
        Filters your watchlist by available time (runtime), mood (genre), and minimum IMDb rating,
        and provides personalized recommendations with context.
        """
        watchlist = self.filter_by("status", "==", "watchlist")
        candidates = []

        g_norm = genre.lower().strip() if genre else None
        mtype_norm = media_type.lower().strip() if media_type else None

        for m in watchlist:
            if mtype_norm and m.get("media_type", "").lower() != mtype_norm:
                continue

            genres = [g.lower() for g in m.get("genres", [])]
            if g_norm and not any(g_norm in g for g in genres):
                continue

            imdb_rating = m.get("imdb_rating") or 0.0
            if min_imdb_rating and imdb_rating < min_imdb_rating:
                continue

            runtime = m.get("runtime_mins")
            if max_runtime_mins and runtime and runtime > max_runtime_mins:
                continue

            candidates.append(m)

        candidates.sort(
            key=lambda x: (x.get("imdb_rating") or 0.0, x.get("year") or 0),
            reverse=True
        )

        selected = candidates[:count]
        picks = []
        for c in selected:
            runtime_str = f"{c.get('runtime_mins')} mins" if c.get("runtime_mins") else "Runtime unlisted"
            reason_parts = []
            if c.get("imdb_rating"):
                reason_parts.append(f"Strong community rating ({c.get('imdb_rating')}/10)")
            if c.get("directors"):
                reason_parts.append(f"Directed by {', '.join(c.get('directors'))}")
            if c.get("runtime_mins"):
                reason_parts.append(f"Fits runtime ({runtime_str})")

            picks.append({
                "id": c.get("id"),
                "title": c.get("title"),
                "year": c.get("year"),
                "media_type": c.get("media_type"),
                "imdb_rating": c.get("imdb_rating"),
                "runtime": runtime_str,
                "genres": c.get("genres", []),
                "directors": c.get("directors", []),
                "why_this_fits": " • ".join(reason_parts),
                "notes": c.get("notes", ""),
            })

        return {
            "status": "success",
            "filters_applied": {
                "max_runtime_mins": max_runtime_mins,
                "genre": genre,
                "min_imdb_rating": min_imdb_rating,
                "media_type": media_type,
            },
            "total_matches_in_watchlist": len(candidates),
            "curated_picks": picks,
        }
