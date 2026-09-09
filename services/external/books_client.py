"""
Book metadata client utilizing Google Books API with automatic Open Library fallback.
"""

from typing import Optional, List, Dict, Any
import requests
from config import GOOGLE_BOOKS_API_KEY


class OpenLibraryClient:
    """Client for Open Library public REST API."""

    BASE_URL = "https://openlibrary.org/search.json"

    def __init__(self, timeout: int = 10):
        self.session = requests.Session()
        self.timeout = timeout

    def search(self, query: str, author: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search Open Library for book records."""
        params: Dict[str, Any] = {"limit": limit}
        if author:
            params["author"] = author
            params["title"] = query
        else:
            params["q"] = query

        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return [{"error": f"Open Library error: {str(e)}"}]

        results = []
        for doc in data.get("docs", [])[:limit]:
            cover_id = doc.get("cover_i")
            thumbnail = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else ""
            subjects = doc.get("subject", [])
            categories = subjects[:3] if isinstance(subjects, list) else []

            results.append({
                "source": "open_library",
                "title": doc.get("title", "Untitled"),
                "subtitle": "",
                "authors": doc.get("author_name", []),
                "published_date": str(doc.get("first_publish_year", "")),
                "description": "",
                "categories": categories,
                "page_count": doc.get("number_of_pages_median"),
                "average_rating": doc.get("ratings_average"),
                "ratings_count": doc.get("ratings_count"),
                "thumbnail": thumbnail,
                "info_link": f"https://openlibrary.org{doc.get('key', '')}",
            })
        return results


class BookMetadataClient:
    """
    Unified client for book metadata lookup and recommendation discovery.
    Queries Google Books and falls back to Open Library on rate limits or errors.
    """

    GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 10):
        self.api_key = api_key or GOOGLE_BOOKS_API_KEY
        self.timeout = timeout
        self.session = requests.Session()
        self.open_library = OpenLibraryClient(timeout=timeout)

    def search(self, query: str, author: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search books by title, author, or keywords."""
        q_parts = [query.strip()]
        if author:
            q_parts.append(f'inauthor:"{author.strip()}"')
        full_q = " ".join(q_parts)

        params: Dict[str, Any] = {
            "q": full_q,
            "maxResults": min(max(1, limit), 10),
            "printType": "books",
        }
        if self.api_key:
            params["key"] = self.api_key

        try:
            resp = self.session.get(self.GOOGLE_BOOKS_URL, params=params, timeout=self.timeout)
            if resp.status_code == 429:
                return self.open_library.search(query, author=author, limit=limit)
            resp.raise_for_status()
            data = resp.json()
        except Exception:
            return self.open_library.search(query, author=author, limit=limit)

        items = data.get("items", [])
        if not items:
            return self.open_library.search(query, author=author, limit=limit)

        results = []
        for item in items:
            vol = item.get("volumeInfo", {})
            images = vol.get("imageLinks", {})
            results.append({
                "source": "google_books",
                "google_book_id": item.get("id"),
                "title": vol.get("title", "Untitled"),
                "subtitle": vol.get("subtitle", ""),
                "authors": vol.get("authors", []),
                "published_date": vol.get("publishedDate", ""),
                "description": vol.get("description", ""),
                "categories": vol.get("categories", []),
                "page_count": vol.get("pageCount"),
                "average_rating": vol.get("averageRating"),
                "ratings_count": vol.get("ratingsCount"),
                "thumbnail": images.get("thumbnail") or images.get("smallThumbnail", ""),
                "info_link": vol.get("infoLink", ""),
            })
        return results

    def find_similar(self, title: str, author: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        """Find related books based on seed book's themes, categories, or author."""
        seed_results = self.search(title, author=author, limit=1)
        if not seed_results or "error" in seed_results[0]:
            return {
                "status": "error",
                "message": f"Could not find seed book: {title}",
                "recommendations": []
            }

        seed = seed_results[0]
        categories = seed.get("categories", [])
        authors = seed.get("authors", [])

        discover_q = ""
        if categories:
            primary_cat = categories[0].split("/")[0].strip()
            discover_q = f'subject:"{primary_cat}"'
        elif authors:
            discover_q = f'inauthor:"{authors[0]}"'
        else:
            discover_q = title

        params: Dict[str, Any] = {
            "q": discover_q,
            "maxResults": min(max(2, limit + 3), 15),
            "orderBy": "relevance",
            "printType": "books",
        }
        if self.api_key:
            params["key"] = self.api_key

        raw_items = []
        try:
            resp = self.session.get(self.GOOGLE_BOOKS_URL, params=params, timeout=self.timeout)
            if resp.status_code == 200:
                raw_items = resp.json().get("items", [])
        except Exception:
            pass

        recommendations = []
        seed_title_norm = title.lower().strip()

        if raw_items:
            for item in raw_items:
                vol = item.get("volumeInfo", {})
                item_title = vol.get("title", "")
                if item_title.lower().strip() == seed_title_norm:
                    continue

                images = vol.get("imageLinks", {})
                recommendations.append({
                    "title": item_title,
                    "authors": vol.get("authors", []),
                    "published_date": vol.get("publishedDate", ""),
                    "description": vol.get("description", ""),
                    "categories": vol.get("categories", []),
                    "average_rating": vol.get("averageRating"),
                    "thumbnail": images.get("thumbnail", ""),
                    "info_link": vol.get("infoLink", ""),
                })
                if len(recommendations) >= limit:
                    break

        if not recommendations:
            ol_results = self.open_library.search(
                categories[0] if categories else (authors[0] if authors else title),
                limit=limit + 2
            )
            for r in ol_results:
                if r.get("title", "").lower().strip() != seed_title_norm and "error" not in r:
                    recommendations.append(r)
                if len(recommendations) >= limit:
                    break

        return {
            "status": "success",
            "seed_book": {
                "title": seed.get("title"),
                "authors": seed.get("authors"),
                "categories": seed.get("categories"),
            },
            "recommendations": recommendations[:limit],
        }
