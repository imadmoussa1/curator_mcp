"""
Recommendation and taste profiling engine.
Synthesizes user ratings across Firestore and queries external APIs with automatic library deduplication.
"""

from typing import Dict, Any, List
from collections import Counter
from google.cloud.firestore_v1.base_query import FieldFilter

from services.book_service import BookService
from services.media_service import MediaService
from services.external.books_client import BookMetadataClient
from services.external.tmdb_client import TMDBClient


class RecommendationService:
    """
    Intelligent recommendation and taste profiling service.
    """

    def __init__(
        self,
        book_service: BookService,
        media_service: MediaService,
        books_client: BookMetadataClient,
        tmdb_client: TMDBClient,
    ):
        self.book_service = book_service
        self.media_service = media_service
        self.books_client = books_client
        self.tmdb_client = tmdb_client

    def get_taste_profile(self) -> Dict[str, Any]:
        """
        Synthesize user taste preferences across books and media.
        Identifies top authors, directors, and genres from items rated 4+ stars or 8+ out of 10.
        """
        # Books (rated >= 4)
        top_books = []
        author_counts = Counter()
        for doc in self.book_service.collection.where(filter=FieldFilter("user_rating", ">=", 4)).stream():
            b = doc.to_dict()
            top_books.append({
                "title": b.get("title"),
                "author": b.get("author"),
                "user_rating": b.get("user_rating"),
                "notes": b.get("notes_and_reviews") or ""
            })
            if b.get("author"):
                author_counts[b["author"]] += 1

        # Media (rated >= 8)
        top_media = []
        genre_counts = Counter()
        director_counts = Counter()
        for doc in self.media_service.collection.where(filter=FieldFilter("user_rating", ">=", 8)).stream():
            m = doc.to_dict()
            top_media.append({
                "title": m.get("title"),
                "media_type": m.get("media_type"),
                "user_rating": m.get("user_rating"),
                "imdb_rating": m.get("imdb_rating"),
                "genres": m.get("genres", []),
                "directors": m.get("directors", [])
            })
            for g in m.get("genres", []):
                genre_counts[g] += 1
            for d in m.get("directors", []):
                director_counts[d] += 1

        return {
            "status": "success",
            "taste_summary": {
                "top_genres": [g for g, _ in genre_counts.most_common(5)],
                "top_directors": [d for d, _ in director_counts.most_common(5)],
                "top_authors": [a for a, _ in author_counts.most_common(5)],
            },
            "favorite_books_sample": top_books[:10],
            "favorite_media_sample": top_media[:10],
            "total_highly_rated_books": len(top_books),
            "total_highly_rated_media": len(top_media),
        }

    def get_smart_recommendations(self, category: str = "all", limit: int = 5) -> Dict[str, Any]:
        """
        Generate intelligent recommendations using top favorites as seeds.
        Filters out any title already existing in user's library or queues.
        """
        recommendations: Dict[str, Any] = {"status": "success"}

        # Existing inventory for deduplication
        existing_books = {
            (doc.to_dict().get("title") or "").lower().strip()
            for doc in self.book_service.collection.stream()
            if doc.to_dict().get("title")
        }
        existing_media = {
            (doc.to_dict().get("title") or "").lower().strip()
            for doc in self.media_service.collection.stream()
            if doc.to_dict().get("title")
        }

        # 1. Book recommendations
        if category in ("books", "all"):
            high_books = list(self.book_service.collection.where(filter=FieldFilter("user_rating", ">=", 5)).limit(3).stream())
            if not high_books:
                high_books = list(self.book_service.collection.where(filter=FieldFilter("user_rating", ">=", 4)).limit(3).stream())

            book_recs = []
            for b_doc in high_books:
                b_data = b_doc.to_dict()
                seed_title = b_data.get("title", "")
                if not seed_title:
                    continue
                sim = self.books_client.find_similar(seed_title, author=b_data.get("author"), limit=3)
                for r in sim.get("recommendations", []):
                    r_title = r.get("title", "").strip()
                    if r_title.lower() not in existing_books and not any(r_title == br["title"] for br in book_recs):
                        r["inspired_by"] = seed_title
                        book_recs.append(r)
                    if len(book_recs) >= limit:
                        break
                if len(book_recs) >= limit:
                    break
            recommendations["book_recommendations"] = book_recs[:limit]

        # 2. Media recommendations
        if category in ("movies", "tv", "all"):
            high_media = list(self.media_service.collection.where(filter=FieldFilter("user_rating", ">=", 10)).limit(3).stream())
            if not high_media:
                high_media = list(self.media_service.collection.where(filter=FieldFilter("user_rating", ">=", 8)).limit(3).stream())

            media_recs = []
            for m_doc in high_media:
                m_data = m_doc.to_dict()
                seed_title = m_data.get("title", "")
                m_type = "movie" if "movie" in (m_data.get("media_type") or "movie").lower() else "tv"
                sim = self.tmdb_client.find_similar(seed_title, media_type=m_type, limit=4)
                for r in sim.get("recommendations", []):
                    r_title = r.get("title", "").strip()
                    if r_title.lower() not in existing_media and not any(r_title == mr["title"] for mr in media_recs):
                        r["inspired_by"] = seed_title
                        media_recs.append(r)
                    if len(media_recs) >= limit:
                        break
                if len(media_recs) >= limit:
                    break
            recommendations["media_recommendations"] = media_recs[:limit]

        return recommendations
