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
from services.external.tmdb_client import TMDBClient


class MediaService(BaseFirestoreRepository):
    """Business logic and persistence layer for Movies and TV Series."""

    def __init__(self, tmdb_client: Optional[TMDBClient] = None):
        super().__init__("media")
        self.tmdb_client = tmdb_client or TMDBClient()

    @staticmethod
    def _normalize_title(title: str) -> str:
        if not title:
            return ""
        t = title.strip().lower()
        t = re.sub(r"^(the|a|an)\s+", "", t)
        return re.sub(r"[^a-z0-9]", "", t)

    def find_existing(
        self,
        title: str,
        media_type: Optional[str] = None,
        year: Optional[int] = None,
        tmdb_id: Optional[int] = None,
        media_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a movie or series already exists in the database.
        Checks:
          1. Direct ID match (IMDb Const ID or custom doc id)
          2. TMDB ID match
          3. Exact title match (case-insensitive)
          4. Normalized alphanumeric title match
        """
        if media_id:
            doc = self.get(media_id.strip())
            if doc:
                return doc

        norm_target = self._normalize_title(title)
        raw_title = title.strip().lower()

        docs = self.stream_all()
        for doc in docs:
            # 1. Match by tmdb_id if present
            if tmdb_id and doc.get("tmdb_id") and int(doc["tmdb_id"]) == int(tmdb_id):
                return doc

            doc_title = (doc.get("title") or "").strip()
            if not doc_title:
                continue

            doc_year = doc.get("year")
            # Exact title match
            if doc_title.lower() == raw_title:
                if year and doc_year and abs(int(doc_year) - int(year)) > 1:
                    continue
                return doc

            # Normalized title match
            doc_norm = self._normalize_title(doc_title)
            if norm_target and doc_norm == norm_target:
                if year and doc_year and abs(int(doc_year) - int(year)) > 1:
                    continue
                return doc

        return None

    def _enrich_from_tmdb(
        self,
        title: str,
        media_type: str = "movie",
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Fetch metadata from TMDB if available."""
        if not self.tmdb_client or not getattr(self.tmdb_client, "api_key", None):
            return {}
        try:
            m_type = "tv" if media_type and media_type.lower() in ("tv", "tvseries", "tvminiseries", "series") else "movie"
            results = self.tmdb_client.search(title=title, media_type=m_type, year=year)
            if results and isinstance(results, list) and not results[0].get("error"):
                return results[0]
        except Exception:
            pass
        return {}

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
        """Add a movie or series to user's watchlist with de-duplication and TMDB auto-enrichment."""
        # 1. Fetch TMDB data first if available
        tmdb_data = self._enrich_from_tmdb(title=title, media_type=media_type, year=year)
        tmdb_id = tmdb_data.get("tmdb_id")
        canonical_title = tmdb_data.get("title") or title.strip()

        # 2. De-duplication check: avoid adding duplicates
        existing = self.find_existing(
            title=title,
            media_type=media_type,
            year=year or (int(tmdb_data["release_date"][:4]) if tmdb_data.get("release_date") and tmdb_data["release_date"][:4].isdigit() else None),
            tmdb_id=tmdb_id,
            media_id=media_id
        )
        if not existing and canonical_title.lower() != title.strip().lower():
            existing = self.find_existing(title=canonical_title, media_type=media_type, tmdb_id=tmdb_id)

        if existing:
            doc_id = existing["id"]
            existing_status = existing.get("status", "watchlist")
            if existing_status == "watchlist":
                return {
                    "status": "already_exists",
                    "message": f"'{existing.get('title', title)}' is already on your watchlist (ID: {doc_id}). Duplicate prevented.",
                    "media": existing
                }
            else:
                existing["status"] = "watchlist"
                existing["updated_at"] = datetime.now(timezone.utc)
                if notes:
                    existing["notes"] = f"{existing.get('notes', '')} | {notes}".strip(" | ")
                self.set(doc_id, existing)
                return {
                    "status": "updated",
                    "message": f"'{existing.get('title', title)}' was previously marked as {existing_status}; updated to watchlist (duplicate prevented).",
                    "media": existing
                }

        # 3. New entry: Enrich with TMDB metadata
        final_year = year
        if final_year is None and tmdb_data.get("release_date"):
            date_str = tmdb_data["release_date"]
            if len(date_str) >= 4 and date_str[:4].isdigit():
                try:
                    final_year = int(date_str[:4])
                except ValueError:
                    pass

        final_genres = genres or []
        if not final_genres and tmdb_data.get("genres"):
            final_genres = tmdb_data["genres"]

        final_imdb_rating = imdb_rating
        if final_imdb_rating is None and tmdb_data.get("vote_average"):
            try:
                final_imdb_rating = round(float(tmdb_data["vote_average"]), 1)
            except (ValueError, TypeError):
                pass

        doc_id = media_id.strip() if media_id else self._generate_media_id(canonical_title)
        media = MediaModel(
            id=doc_id,
            title=canonical_title,
            media_type=media_type.strip(),
            status="watchlist",
            year=final_year,
            genres=final_genres,
            directors=directors or [],
            imdb_rating=final_imdb_rating,
            notes=notes or "",
            tmdb_id=tmdb_id,
            poster_url=tmdb_data.get("poster_url"),
            overview=tmdb_data.get("overview"),
            updated_at=datetime.now(timezone.utc)
        )
        self.set(doc_id, media.to_firestore_dict())
        enriched_msg = " (auto-enriched with TMDB metadata)" if tmdb_data else ""
        return {
            "status": "success",
            "message": f"Added '{canonical_title}' to watchlist{enriched_msg}.",
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
        notes: Optional[str] = "",
        review: Optional[str] = "",
        user_notes: Optional[str] = "",
        date_watched: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log a film or episode as watched with de-duplication and TMDB auto-enrichment."""
        # 1. Fetch TMDB data
        tmdb_data = self._enrich_from_tmdb(title=title, media_type=media_type, year=year)
        tmdb_id = tmdb_data.get("tmdb_id")
        canonical_title = tmdb_data.get("title") or title.strip()

        rating = max(1, min(10, user_rating)) if user_rating is not None else None
        written_review = (review or "").strip()
        u_notes = (user_notes or "").strip()
        legacy_notes = (notes or "").strip()
        if not written_review and legacy_notes:
            written_review = legacy_notes

        if not date_watched:
            date_watched = datetime.now().strftime("%Y-%m-%d")

        # 2. De-duplication check: check if it already exists
        existing = self.find_existing(
            title=title,
            media_type=media_type,
            year=year or (int(tmdb_data["release_date"][:4]) if tmdb_data.get("release_date") and tmdb_data["release_date"][:4].isdigit() else None),
            tmdb_id=tmdb_id,
            media_id=media_id
        )
        if not existing and canonical_title.lower() != title.strip().lower():
            existing = self.find_existing(title=canonical_title, media_type=media_type, tmdb_id=tmdb_id)

        if existing:
            # Update existing record instead of creating a duplicate
            doc_id = existing["id"]
            existing["status"] = "watched"
            if rating is not None:
                existing["user_rating"] = rating
            if written_review:
                existing["review"] = written_review
            if u_notes:
                existing["user_notes"] = u_notes
            existing["date_watched"] = date_watched
            if legacy_notes:
                existing["notes"] = f"{existing.get('notes', '')} | {legacy_notes}".strip(" | ")
            elif written_review:
                existing["notes"] = written_review

            # Enrich missing metadata if existing doc didn't have it
            if not existing.get("poster_url") and tmdb_data.get("poster_url"):
                existing["poster_url"] = tmdb_data["poster_url"]
            if not existing.get("overview") and tmdb_data.get("overview"):
                existing["overview"] = tmdb_data["overview"]
            if not existing.get("tmdb_id") and tmdb_id:
                existing["tmdb_id"] = tmdb_id
            if not existing.get("year") and tmdb_data.get("release_date"):
                try:
                    existing["year"] = int(tmdb_data["release_date"][:4])
                except (ValueError, TypeError):
                    pass
            if not existing.get("genres") and tmdb_data.get("genres"):
                existing["genres"] = tmdb_data["genres"]

            existing["updated_at"] = datetime.now(timezone.utc)
            self.set(doc_id, existing)
            return {
                "status": "success",
                "message": f"Updated existing entry for '{existing.get('title', canonical_title)}' as watched (duplicate prevented).",
                "media": existing
            }

        # 3. New entry: Enrich with TMDB metadata
        final_year = year
        if final_year is None and tmdb_data.get("release_date"):
            date_str = tmdb_data["release_date"]
            if len(date_str) >= 4 and date_str[:4].isdigit():
                try:
                    final_year = int(date_str[:4])
                except ValueError:
                    pass

        final_genres = genres or []
        if not final_genres and tmdb_data.get("genres"):
            final_genres = tmdb_data["genres"]

        final_imdb_rating = tmdb_data.get("vote_average")
        if final_imdb_rating is not None:
            try:
                final_imdb_rating = round(float(final_imdb_rating), 1)
            except (ValueError, TypeError):
                final_imdb_rating = None

        doc_id = media_id.strip() if media_id else self._generate_media_id(canonical_title)
        media = MediaModel(
            id=doc_id,
            title=canonical_title,
            media_type=media_type.strip(),
            user_rating=rating,
            status="watched",
            year=final_year,
            genres=final_genres,
            directors=directors or [],
            notes=legacy_notes or written_review,
            review=written_review,
            user_notes=u_notes,
            date_watched=date_watched,
            imdb_rating=final_imdb_rating,
            tmdb_id=tmdb_id,
            poster_url=tmdb_data.get("poster_url"),
            overview=tmdb_data.get("overview"),
            updated_at=datetime.now(timezone.utc)
        )
        self.set(doc_id, media.to_firestore_dict())
        enriched_msg = " (auto-enriched with TMDB metadata)" if tmdb_data else ""
        return {
            "status": "success",
            "message": f"Logged '{canonical_title}' ({media_type}) as watched{enriched_msg}" + (f" with IMDb rating {rating}/10." if rating else "."),
            "media": media.to_firestore_dict()
        }

    def update_status(
        self,
        media_id: Optional[str] = None,
        title: Optional[str] = None,
        status: str = "watched",
        user_rating: Optional[int] = None,
        review: Optional[str] = None,
        user_notes: Optional[str] = None,
        date_watched: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update a movie or TV show's status (IMDb system: 'watched' or 'watchlist'),
        with optional 1-10 IMDb user rating, written review, personal notes, and date.
        Locates the media by media_id (IMDb Const ID) or title search.
        """
        target_doc = None
        if media_id:
            target_doc = self.get(media_id.strip())

        if not target_doc and title:
            matches = self.search(query=title, limit=1)
            if matches:
                target_doc = self.get(matches[0]["id"])

        if not target_doc:
            return {
                "status": "error",
                "message": f"Media not found by ID '{media_id}' or title '{title}'. Consider adding it first."
            }

        doc_id = target_doc["id"]
        status_clean = status.strip().lower()
        if "watch" in status_clean and "list" not in status_clean:
            status_clean = "watched"
        elif "list" in status_clean:
            status_clean = "watchlist"

        target_doc["status"] = status_clean
        target_doc["updated_at"] = datetime.now(timezone.utc)

        if user_rating is not None:
            target_doc["user_rating"] = max(1, min(10, int(user_rating)))

        if review is not None:
            target_doc["review"] = review.strip()
            # Keep legacy notes in sync
            target_doc["notes"] = review.strip()

        if user_notes is not None:
            target_doc["user_notes"] = user_notes.strip()

        if date_watched is not None:
            target_doc["date_watched"] = date_watched.strip()
        elif status_clean == "watched" and not target_doc.get("date_watched"):
            target_doc["date_watched"] = datetime.now().strftime("%Y-%m-%d")

        self.set(doc_id, target_doc)
        return {
            "status": "success",
            "message": f"Updated media '{target_doc.get('title')}' status to '{status_clean}'.",
            "media": target_doc
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
