"""
Apple Podcasts Search API client.
Provides free podcast metadata, artwork, and RSS feed discovery without requiring an API key.
"""

from typing import List, Dict, Any
import requests


class ApplePodcastsClient:
    """Client for iTunes / Apple Podcasts public search API."""

    BASE_URL = "https://itunes.apple.com/search"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()

    def search(self, show_name: str = "", query: str = "", limit: int = 5) -> List[Dict[str, Any]]:
        """Search podcast shows by name or keywords."""
        search_term = (show_name or query).strip()
        if not search_term:
            return []

        params = {
            "media": "podcast",
            "term": search_term,
            "limit": min(max(1, limit), 10),
        }
        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return [{"error": f"Failed to search Apple Podcasts: {str(e)}"}]

        results = []
        for item in data.get("results", []):
            artist = item.get("artistName", "")
            results.append({
                "podcast_name": item.get("collectionName") or item.get("trackName", "Unknown Podcast"),
                "host": artist,
                "host_or_artist": artist,
                "genres": item.get("genres", []),
                "episode_count": item.get("trackCount"),
                "artwork_url": item.get("artworkUrl600") or item.get("artworkUrl100", ""),
                "feed_url": item.get("feedUrl", ""),
                "podcast_url": item.get("collectionViewUrl", ""),
            })
        return results
