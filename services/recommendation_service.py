"""
Recommendation and taste profiling engine.
Synthesizes user ratings across Firestore and queries external APIs with automatic library deduplication.
"""

import re
from datetime import datetime
from typing import Dict, Any, List, Optional
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
        quote_service: Optional[Any] = None,
        podcast_service: Optional[Any] = None,
    ):
        self.book_service = book_service
        self.media_service = media_service
        self.books_client = books_client
        self.tmdb_client = tmdb_client
        self.quote_service = quote_service
        self.podcast_service = podcast_service

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

    def generate_cultural_wrapped(self, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Synthesizes an all-in-one personal 'Curator Wrapped' annual retrospective across:
        - Books read and rated in the target year
        - Movies & series watched in the target year
        - Podcasts listened to in the target year
        - Memorable quotes & mental models collected
        - Synthesized 'Cultural Archetype' persona
        """
        target_year = year or datetime.now().year
        year_str = str(target_year)

        # 1. Books in year
        books_in_year = []
        book_ratings = []
        book_authors = Counter()
        for b in self.book_service.stream_all():
            d_read = b.get("date_read") or ""
            # Match specific year, or all read books if year is not provided
            if d_read.startswith(year_str) or (b.get("shelf") == "read" and year is None):
                books_in_year.append(b)
                if b.get("user_rating"):
                    book_ratings.append(b["user_rating"])
                if b.get("author"):
                    book_authors[b["author"]] += 1

        books_in_year.sort(key=lambda x: x.get("user_rating") or 0, reverse=True)
        avg_book_rating = round(sum(book_ratings) / len(book_ratings), 2) if book_ratings else None

        # 2. Media in year
        media_in_year = []
        media_ratings = []
        genres_in_year = Counter()
        directors_in_year = Counter()
        for m in self.media_service.stream_all():
            if m.get("status") != "watched":
                continue
            notes = m.get("notes") or ""
            match = re.search(r"Rated on (\d{4})-\d{2}-\d{2}", notes)
            date_rated = match.group(1) if match else ""
            if date_rated.startswith(year_str) or year is None:
                media_in_year.append(m)
                if m.get("user_rating"):
                    media_ratings.append(m["user_rating"])
                for g in m.get("genres", []):
                    genres_in_year[g] += 1
                for d in m.get("directors", []):
                    directors_in_year[d] += 1

        media_in_year.sort(key=lambda x: x.get("user_rating") or 0, reverse=True)
        avg_media_rating = round(sum(media_ratings) / len(media_ratings), 2) if media_ratings else None

        # 3. Quotes & Mental Models
        quotes_list = []
        quote_themes = Counter()
        if self.quote_service:
            for q in self.quote_service.stream_all():
                quotes_list.append(q)
                for tag in q.get("theme_tags", []):
                    quote_themes[tag.lower()] += 1

        # 4. Podcasts
        podcasts_in_year = []
        pod_topics = Counter()
        if self.podcast_service:
            for p in self.podcast_service.stream_all():
                p_date = p.get("date_listened") or ""
                if p_date.startswith(year_str) or p.get("status") == "listened":
                    podcasts_in_year.append(p)
                    for topic in p.get("topics", []):
                        pod_topics[topic.lower()] += 1

        # 5. Synthesize Cultural Archetype
        top_genres = [g for g, _ in genres_in_year.most_common(3)]
        top_themes = [t for t, _ in quote_themes.most_common(3)]

        if "Sci-Fi" in top_genres and any(t in top_themes for t in ("stoicism", "discipline", "mindset")):
            archetype = "The Cybernetic Stoic"
            desc = "You balance futuristic imagination and visionary cinema with rigorous personal philosophy and mental discipline."
        elif "Drama" in top_genres or "Crime" in top_genres:
            archetype = "The Inquisitive Realist"
            desc = "Drawn to human psychology, moral dilemmas, and intense character-driven narratives."
        elif "Comedy" in top_genres or "Romance" in top_genres:
            archetype = "The Classical Humanist"
            desc = "Appreciating timeless wit, human connection, and witty storytelling across the golden eras."
        else:
            archetype = "The Renaissance Polymath"
            desc = "A diverse intellectual appetite that moves seamlessly between cinema, literature, and deep ideas."

        return {
            "status": "success",
            "year": target_year,
            "cultural_archetype": {
                "title": archetype,
                "summary": desc,
            },
            "summary_metrics": {
                "total_books_read": len(books_in_year),
                "avg_book_rating": avg_book_rating,
                "total_media_watched": len(media_in_year),
                "avg_media_rating": avg_media_rating,
                "total_podcasts_listened": len(podcasts_in_year),
                "total_quotes_collected": len(quotes_list),
            },
            "top_genres": [g for g, _ in genres_in_year.most_common(5)],
            "top_directors": [d for d, _ in directors_in_year.most_common(5)],
            "top_authors": [a for a, _ in book_authors.most_common(5)],
            "top_philosophies_and_themes": [t for t, _ in quote_themes.most_common(5)],
            "masterpieces_and_favorites": {
                "top_books": [
                    {"title": b.get("title"), "author": b.get("author"), "rating": f"{b.get('user_rating')}★"}
                    for b in books_in_year[:5] if b.get("user_rating", 0) >= 4
                ],
                "top_films": [
                    {"title": m.get("title"), "year": m.get("year"), "rating": f"{m.get('user_rating')}/10"}
                    for m in media_in_year[:5] if m.get("user_rating", 0) >= 8
                ]
            }
        }
