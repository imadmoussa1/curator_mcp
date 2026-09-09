"""
External API client for Book & Media Discovery:
- Books: Google Books API with automatic Open Library API fallback for resilience against rate limits.
- Media: The Movie Database (TMDB) API for plot overviews, posters, and recommendation engines.
"""

import os
from typing import Optional, List, Dict, Any
import requests

from config import GOOGLE_BOOKS_API_KEY, TMDB_API_KEY


# ============================================================================
# 1. BOOK SERVICES (Google Books + Open Library Fallback)
# ============================================================================

GOOGLE_BOOKS_BASE_URL = "https://www.googleapis.com/books/v1/volumes"
OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"


def _search_open_library(query: str, author: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Fallback search using Open Library API."""
    params: Dict[str, Any] = {"limit": limit}
    if author:
        params["author"] = author
        params["title"] = query
    else:
        params["q"] = query

    try:
        resp = requests.get(OPEN_LIBRARY_SEARCH_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return [{"error": f"Failed to query Open Library: {str(e)}"}]

    results: List[Dict[str, Any]] = []
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


def search_google_books(query: str, author: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Searches Google Books API. If Google Books is rate-limited (429) or unavailable,
    automatically falls back to Open Library API.
    """
    q_parts = [query.strip()]
    if author:
        q_parts.append(f'inauthor:"{author.strip()}"')
    full_q = " ".join(q_parts)

    params: Dict[str, Any] = {
        "q": full_q,
        "maxResults": min(max(1, limit), 10),
        "printType": "books",
    }
    if GOOGLE_BOOKS_API_KEY:
        params["key"] = GOOGLE_BOOKS_API_KEY

    try:
        resp = requests.get(GOOGLE_BOOKS_BASE_URL, params=params, timeout=10)
        if resp.status_code == 429:
            # Fallback to Open Library when rate limited
            return _search_open_library(query, author=author, limit=limit)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        # Fallback to Open Library
        return _search_open_library(query, author=author, limit=limit)

    items = data.get("items", [])
    if not items:
        return _search_open_library(query, author=author, limit=limit)

    results: List[Dict[str, Any]] = []
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


def find_similar_books(title: str, author: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """
    Finds books similar to a given title by identifying the seed book's
    categories and subject tags, then discovering related works.
    Falls back cleanly to Open Library if needed.
    """
    seed_results = search_google_books(title, author=author, limit=1)
    if not seed_results or "error" in seed_results[0]:
        return {
            "status": "error",
            "message": f"Could not find seed book: {title}",
            "recommendations": []
        }

    seed = seed_results[0]
    categories = seed.get("categories", [])
    authors = seed.get("authors", [])

    # Discovery query
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
    if GOOGLE_BOOKS_API_KEY:
        params["key"] = GOOGLE_BOOKS_API_KEY

    raw_items = []
    try:
        resp = requests.get(GOOGLE_BOOKS_BASE_URL, params=params, timeout=10)
        if resp.status_code == 200:
            raw_items = resp.json().get("items", [])
    except Exception:
        pass

    recommendations: List[Dict[str, Any]] = []
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

    # Fallback to Open Library if Google Books returned no recommendations
    if not recommendations:
        ol_results = _search_open_library(
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


# ============================================================================
# 2. THE MOVIE DATABASE (TMDB) API
# ============================================================================

TMDB_BASE_URL = "https://api.themoviedb.org/3"

TMDB_GENRES = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
    99: "Documentary", 18: "Drama", 10751: "Family", 14: "Fantasy", 36: "History",
    27: "Horror", 10402: "Music", 9648: "Mystery", 10749: "Romance", 878: "Sci-Fi",
    10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western",
    10759: "Action & Adventure", 10762: "Kids", 10763: "News", 10764: "Reality",
    10765: "Sci-Fi & Fantasy", 10766: "Soap", 10767: "Talk", 10768: "War & Politics"
}


def _get_tmdb_headers_or_params() -> tuple[Dict[str, str], Dict[str, str]]:
    headers = {"accept": "application/json"}
    params = {}
    if TMDB_API_KEY:
        if TMDB_API_KEY.startswith("ey"):
            headers["Authorization"] = f"Bearer {TMDB_API_KEY}"
        else:
            params["api_key"] = TMDB_API_KEY
    return headers, params


def search_tmdb(title: str, media_type: str = "movie", year: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Searches TMDB for a movie or TV show.
    Returns details including overview, release date, vote average, poster URL, and TMDB ID.
    """
    if not TMDB_API_KEY:
        return [{
            "status": "config_required",
            "message": "TMDB_API_KEY is not set. Get a free API key at https://www.themoviedb.org/settings/api "
                       "and add TMDB_API_KEY=your_key to your .env file."
        }]

    endpoint = "search/movie" if "movie" in media_type.lower() else "search/tv"
    headers, params = _get_tmdb_headers_or_params()
    params["query"] = title.strip()
    if year:
        if "movie" in media_type.lower():
            params["year"] = str(year)
        else:
            params["first_air_date_year"] = str(year)

    try:
        resp = requests.get(f"{TMDB_BASE_URL}/{endpoint}", headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return [{"error": f"Failed to query TMDB: {str(e)}"}]

    results: List[Dict[str, Any]] = []
    for item in data.get("results", [])[:5]:
        media_name = item.get("title") or item.get("name")
        release_date = item.get("release_date") or item.get("first_air_date", "")
        poster = item.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else ""
        genres = [TMDB_GENRES.get(gid, "Other") for gid in item.get("genre_ids", [])]

        results.append({
            "tmdb_id": item.get("id"),
            "title": media_name,
            "media_type": "movie" if "movie" in media_type.lower() else "tv",
            "release_date": release_date,
            "overview": item.get("overview", ""),
            "vote_average": item.get("vote_average"),
            "vote_count": item.get("vote_count"),
            "genres": genres,
            "poster_url": poster_url,
        })

    return results


def find_similar_media(title: str, media_type: str = "movie", limit: int = 5) -> Dict[str, Any]:
    """
    Uses TMDB's recommendation algorithm to find movies or TV series similar to a title.
    """
    if not TMDB_API_KEY:
        return {
            "status": "config_required",
            "message": "TMDB_API_KEY is not set in .env. Get a free API key at "
                       "https://www.themoviedb.org/settings/api to enable live movie/series recommendations.",
            "recommendations": []
        }

    search_res = search_tmdb(title, media_type=media_type)
    if not search_res or "error" in search_res[0] or "status" in search_res[0]:
        return {
            "status": "error",
            "message": f"Could not find title '{title}' on TMDB.",
            "recommendations": []
        }

    seed = search_res[0]
    tmdb_id = seed.get("tmdb_id")
    endpoint_type = "movie" if "movie" in media_type.lower() else "tv"

    headers, params = _get_tmdb_headers_or_params()
    url = f"{TMDB_BASE_URL}/{endpoint_type}/{tmdb_id}/recommendations"

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        raw_items = data.get("results", [])
        if not raw_items:
            url_similar = f"{TMDB_BASE_URL}/{endpoint_type}/{tmdb_id}/similar"
            resp_sim = requests.get(url_similar, headers=headers, params=params, timeout=10)
            if resp_sim.ok:
                raw_items = resp_sim.json().get("results", [])
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fetch TMDB recommendations: {str(e)}",
            "recommendations": []
        }

    recommendations: List[Dict[str, Any]] = []
    for item in raw_items[:limit]:
        media_name = item.get("title") or item.get("name")
        release_date = item.get("release_date") or item.get("first_air_date", "")
        poster = item.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else ""
        genres = [TMDB_GENRES.get(gid, "Other") for gid in item.get("genre_ids", [])]

        recommendations.append({
            "tmdb_id": item.get("id"),
            "title": media_name,
            "media_type": endpoint_type,
            "release_date": release_date,
            "overview": item.get("overview", ""),
            "vote_average": item.get("vote_average"),
            "genres": genres,
            "poster_url": poster_url,
        })

    return {
        "status": "success",
        "seed_media": {
            "title": seed.get("title"),
            "tmdb_id": tmdb_id,
            "genres": seed.get("genres"),
            "vote_average": seed.get("vote_average"),
        },
        "recommendations": recommendations,
    }


# ============================================================================
# 3. PODCAST SEARCH API (iTunes / Apple Podcasts Search - Free & No Key)
# ============================================================================

ITUNES_PODCAST_URL = "https://itunes.apple.com/search"


def search_podcast_online(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search for podcasts online via Apple Podcasts API.
    Returns show name, artist/host, genres, episode count, artwork URL, and feed URL.
    Works free with zero API key.
    """
    params = {
        "media": "podcast",
        "term": query.strip(),
        "limit": min(max(1, limit), 10),
    }
    try:
        resp = requests.get(ITUNES_PODCAST_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return [{"error": f"Failed to search podcasts: {str(e)}"}]

    results: List[Dict[str, Any]] = []
    for item in data.get("results", []):
        results.append({
            "podcast_name": item.get("collectionName") or item.get("trackName", "Unknown Podcast"),
            "host_or_artist": item.get("artistName", ""),
            "genres": item.get("genres", []),
            "episode_count": item.get("trackCount"),
            "artwork_url": item.get("artworkUrl600") or item.get("artworkUrl100", ""),
            "feed_url": item.get("feedUrl", ""),
            "podcast_url": item.get("collectionViewUrl", ""),
        })

    return results

