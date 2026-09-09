"""
The Movie Database (TMDB) API client for movie and series discovery.
"""

from typing import Optional, List, Dict, Any
import requests
from config import TMDB_API_KEY


class TMDBClient:
    """Client for TMDB v3/v4 API endpoints."""

    BASE_URL = "https://api.themoviedb.org/3"

    GENRE_MAP = {
        28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy", 80: "Crime",
        99: "Documentary", 18: "Drama", 10751: "Family", 14: "Fantasy", 36: "History",
        27: "Horror", 10402: "Music", 9648: "Mystery", 10749: "Romance", 878: "Sci-Fi",
        10770: "TV Movie", 53: "Thriller", 10752: "War", 37: "Western",
        10759: "Action & Adventure", 10762: "Kids", 10763: "News", 10764: "Reality",
        10765: "Sci-Fi & Fantasy", 10766: "Soap", 10767: "Talk", 10768: "War & Politics"
    }

    def __init__(self, api_key: Optional[str] = None, timeout: int = 10):
        self.api_key = api_key or TMDB_API_KEY
        self.timeout = timeout
        self.session = requests.Session()

    def _headers_and_params(self) -> tuple[Dict[str, str], Dict[str, str]]:
        headers = {"accept": "application/json"}
        params = {}
        if self.api_key:
            if self.api_key.startswith("ey"):
                headers["Authorization"] = f"Bearer {self.api_key}"
            else:
                params["api_key"] = self.api_key
        return headers, params

    def search(self, title: str, media_type: str = "movie", year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search TMDB for a movie or TV show title."""
        if not self.api_key:
            return [{
                "status": "config_required",
                "message": "TMDB_API_KEY is not set in .env. Get a free API key at "
                           "https://www.themoviedb.org/settings/api to enable movie lookups."
            }]

        endpoint = "search/movie" if "movie" in media_type.lower() else "search/tv"
        headers, params = self._headers_and_params()
        params["query"] = title.strip()
        if year:
            if "movie" in media_type.lower():
                params["year"] = str(year)
            else:
                params["first_air_date_year"] = str(year)

        try:
            resp = self.session.get(f"{self.BASE_URL}/{endpoint}", headers=headers, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return [{"error": f"Failed to query TMDB: {str(e)}"}]

        results = []
        for item in data.get("results", [])[:5]:
            media_name = item.get("title") or item.get("name")
            release_date = item.get("release_date") or item.get("first_air_date", "")
            poster = item.get("poster_path")
            poster_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else ""
            genres = [self.GENRE_MAP.get(gid, "Other") for gid in item.get("genre_ids", [])]

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

    def find_similar(self, title: str, media_type: str = "movie", limit: int = 5) -> Dict[str, Any]:
        """Find recommendations and similar titles via TMDB."""
        if not self.api_key:
            return {
                "status": "config_required",
                "message": "TMDB_API_KEY is not set in .env. Get a free API key at "
                           "https://www.themoviedb.org/settings/api to enable recommendations.",
                "recommendations": []
            }

        search_res = self.search(title, media_type=media_type)
        if not search_res or "error" in search_res[0] or "status" in search_res[0]:
            return {
                "status": "error",
                "message": f"Could not find title '{title}' on TMDB.",
                "recommendations": []
            }

        seed = search_res[0]
        tmdb_id = seed.get("tmdb_id")
        endpoint_type = "movie" if "movie" in media_type.lower() else "tv"

        headers, params = self._headers_and_params()
        url = f"{self.BASE_URL}/{endpoint_type}/{tmdb_id}/recommendations"

        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
            resp.raise_for_status()
            raw_items = resp.json().get("results", [])
            if not raw_items:
                url_sim = f"{self.BASE_URL}/{endpoint_type}/{tmdb_id}/similar"
                resp_sim = self.session.get(url_sim, headers=headers, params=params, timeout=self.timeout)
                if resp_sim.ok:
                    raw_items = resp_sim.json().get("results", [])
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to fetch TMDB recommendations: {str(e)}",
                "recommendations": []
            }

        recommendations = []
        for item in raw_items[:limit]:
            media_name = item.get("title") or item.get("name")
            release_date = item.get("release_date") or item.get("first_air_date", "")
            poster = item.get("poster_path")
            poster_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else ""
            genres = [self.GENRE_MAP.get(gid, "Other") for gid in item.get("genre_ids", [])]

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

    def get_watch_providers(
        self,
        title: str,
        media_type: str = "movie",
        country: str = "US"
    ) -> Dict[str, Any]:
        """
        Lookup streaming providers (subscription, rental, buy) via TMDB / JustWatch data.
        Args:
            title: Movie or series title
            media_type: 'movie' or 'tv'
            country: ISO 3166-1 alpha-2 country code (default 'US', also 'GB', 'CA', etc.)
        """
        if not self.api_key:
            return {
                "status": "config_required",
                "message": "TMDB_API_KEY is not set in .env. Get a free API key at "
                           "https://www.themoviedb.org/settings/api to enable streaming lookups."
            }

        search_res = self.search(title, media_type=media_type)
        if not search_res or "error" in search_res[0] or "status" in search_res[0]:
            return {
                "status": "error",
                "message": f"Could not find title '{title}' on TMDB to check streaming availability."
            }

        seed = search_res[0]
        tmdb_id = seed.get("tmdb_id")
        endpoint_type = "movie" if "movie" in media_type.lower() else "tv"

        headers, params = self._headers_and_params()
        url = f"{self.BASE_URL}/{endpoint_type}/{tmdb_id}/watch/providers"

        try:
            resp = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json().get("results", {})
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to fetch streaming providers: {str(e)}"
            }

        country_code = country.strip().upper()
        country_data = data.get(country_code, {})

        if not country_data:
            avail_countries = list(data.keys())
            return {
                "status": "not_available_in_country",
                "title": seed.get("title"),
                "country": country_code,
                "message": f"No streaming providers currently reported for {country_code}.",
                "available_in_countries": avail_countries[:10],
            }

        def clean_providers(prov_list):
            if not prov_list:
                return []
            return [
                {
                    "provider_name": p.get("provider_name"),
                    "provider_id": p.get("provider_id"),
                    "logo_url": f"https://image.tmdb.org/t/p/original{p.get('logo_path')}" if p.get("logo_path") else ""
                }
                for p in prov_list
            ]

        return {
            "status": "success",
            "title": seed.get("title"),
            "media_type": endpoint_type,
            "country": country_code,
            "justwatch_link": country_data.get("link", ""),
            "streaming_subscriptions": clean_providers(country_data.get("flatrate")),
            "rent": clean_providers(country_data.get("rent")),
            "buy": clean_providers(country_data.get("buy")),
            "free": clean_providers(country_data.get("free") or country_data.get("ads")),
        }
