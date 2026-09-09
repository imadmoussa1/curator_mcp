"""
Domain service managing podcast queues, listening logs, guests, and takeaways.
"""

from datetime import datetime, timezone
import uuid
import re
from typing import Optional, List, Dict, Any
from collections import Counter

from models import PodcastModel
from services.base_repository import BaseFirestoreRepository


class PodcastService(BaseFirestoreRepository):
    """Business logic and persistence layer for Podcasts."""

    def __init__(self):
        super().__init__("podcasts")

    def _generate_podcast_id(self, podcast_name: str, episode_title: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", f"{podcast_name}_{episode_title}".lower()).strip("_")
        return f"pod_{slug[:25]}_{uuid.uuid4().hex[:6]}"

    def add_to_queue(
        self,
        podcast_name: str,
        episode_title: str,
        guest: Optional[str] = None,
        topics: Optional[List[str]] = None,
        episode_url: Optional[str] = None,
        duration_mins: Optional[int] = None
    ) -> Dict[str, Any]:
        """Add an episode to the listening queue."""
        doc_id = self._generate_podcast_id(podcast_name, episode_title)
        podcast = PodcastModel(
            id=doc_id,
            podcast_name=podcast_name.strip(),
            episode_title=episode_title.strip(),
            guest=guest.strip() if guest else None,
            status="queue",
            topics=topics or [],
            episode_url=episode_url,
            duration_mins=duration_mins,
            updated_at=datetime.now(timezone.utc)
        )
        self.set(doc_id, podcast.to_firestore_dict())
        return {
            "status": "success",
            "message": f"Added '{episode_title}' ({podcast_name}) to podcast queue.",
            "podcast": podcast.to_firestore_dict()
        }

    def log_listened(
        self,
        podcast_name: str,
        episode_title: str,
        user_rating: Optional[int] = None,
        guest: Optional[str] = None,
        key_takeaways: Optional[str] = "",
        topics: Optional[List[str]] = None,
        date_listened: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log a podcast as completed with ratings and takeaways."""
        doc_id = self._generate_podcast_id(podcast_name, episode_title)
        if not date_listened:
            date_listened = datetime.now().strftime("%Y-%m-%d")

        podcast = PodcastModel(
            id=doc_id,
            podcast_name=podcast_name.strip(),
            episode_title=episode_title.strip(),
            guest=guest.strip() if guest else None,
            status="listened",
            user_rating=max(1, min(10, user_rating)) if user_rating else None,
            key_takeaways=key_takeaways or "",
            topics=topics or [],
            date_listened=date_listened,
            updated_at=datetime.now(timezone.utc)
        )
        self.set(doc_id, podcast.to_firestore_dict())
        return {
            "status": "success",
            "message": f"Logged '{episode_title}' ({podcast_name}) as listened.",
            "podcast": podcast.to_firestore_dict()
        }

    def get_queue(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve queued podcast episodes."""
        return self.filter_by("status", "==", "queue", limit=limit)

    def search(
        self,
        query: str,
        guest: Optional[str] = None,
        topic: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search podcast records by show, title, guest, or topic."""
        q_norm = query.lower().strip()
        g_norm = guest.lower().strip() if guest else None
        t_norm = topic.lower().strip() if topic else None

        matches = []
        for p in self.stream_all():
            name = (p.get("podcast_name") or "").lower()
            title = (p.get("episode_title") or "").lower()
            pod_guest = (p.get("guest") or "").lower()
            topics = [t.lower() for t in p.get("topics", [])]

            if query and not (q_norm in name or q_norm in title or q_norm in pod_guest):
                continue
            if g_norm and g_norm not in pod_guest:
                continue
            if t_norm and not any(t_norm in t for t in topics):
                continue

            matches.append(p)
            if len(matches) >= limit:
                break
        return matches

    def get_stats(self) -> Dict[str, Any]:
        """Calculates podcast queue size and total listened."""
        docs = self.stream_all()
        status_counts = Counter(p.get("status", "queue") for p in docs)
        return {
            "total": len(docs),
            "listened": status_counts.get("listened", 0),
            "queue": status_counts.get("queue", 0),
        }
