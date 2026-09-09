"""
Domain service managing book inventory, reading queues, and reading logs.
"""

from datetime import datetime, timezone
import re
import uuid
from typing import Optional, List, Dict, Any
from collections import Counter

from models import BookModel
from services.base_repository import BaseFirestoreRepository


class BookService(BaseFirestoreRepository):
    """Business logic and persistence layer for Books."""

    def __init__(self):
        super().__init__("books")

    def _generate_book_id(self, title: str, author: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", f"{title}_{author}".lower()).strip("_")
        return f"gr_{slug[:25]}_{uuid.uuid4().hex[:6]}"

    def search(self, query: str, shelf: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search books by title or author keywords with optional shelf filter."""
        q_norm = query.strip().lower()
        matches = []
        docs = self.stream_all()

        for b in docs:
            if shelf and b.get("shelf", "").lower() != shelf.strip().lower():
                continue
            title = (b.get("title") or "").lower()
            author = (b.get("author") or "").lower()
            if q_norm in title or q_norm in author:
                matches.append({
                    "id": b.get("id"),
                    "title": b.get("title"),
                    "author": b.get("author"),
                    "user_rating": b.get("user_rating"),
                    "avg_rating": b.get("avg_rating"),
                    "shelf": b.get("shelf"),
                    "notes": b.get("notes_and_reviews"),
                })
                if len(matches) >= limit:
                    break
        return matches

    def get_reading_list(self, shelf: str = "to-read", limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve books from user's reading queue ('to-read' or 'currently-reading')."""
        docs = self.filter_by("shelf", "==", shelf.strip().lower(), limit=limit)
        return [
            {
                "id": b.get("id"),
                "title": b.get("title"),
                "author": b.get("author"),
                "avg_rating": b.get("avg_rating"),
                "shelf": b.get("shelf"),
                "notes": b.get("notes_and_reviews"),
            }
            for b in docs
        ]

    def add_to_reading_list(self, title: str, author: str, book_id: Optional[str] = None, notes: Optional[str] = "") -> Dict[str, Any]:
        """Add a book recommendation directly to the 'to-read' shelf."""
        doc_id = book_id.strip() if book_id else self._generate_book_id(title, author)
        book = BookModel(
            id=doc_id,
            title=title.strip(),
            author=author.strip(),
            shelf="to-read",
            notes_and_reviews=notes or "",
            updated_at=datetime.now(timezone.utc)
        )
        self.set(doc_id, book.to_firestore_dict())
        return {
            "status": "success",
            "message": f"Added '{title}' by {author} to reading list.",
            "book": book.to_firestore_dict()
        }

    def log_read(
        self,
        title: str,
        author: str,
        user_rating: int,
        book_id: Optional[str] = None,
        notes: Optional[str] = "",
        date_read: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log a finished book with user rating (0-5), review notes, and date read."""
        doc_id = book_id.strip() if book_id else self._generate_book_id(title, author)
        if not date_read:
            date_read = datetime.now().strftime("%Y-%m-%d")

        book = BookModel(
            id=doc_id,
            title=title.strip(),
            author=author.strip(),
            user_rating=max(0, min(5, user_rating)),
            shelf="read",
            notes_and_reviews=notes or "",
            date_read=date_read,
            updated_at=datetime.now(timezone.utc)
        )
        self.set(doc_id, book.to_firestore_dict())
        return {
            "status": "success",
            "message": f"Logged '{title}' by {author} as read with rating {user_rating}/5.",
            "book": book.to_firestore_dict()
        }

    def get_stats(self) -> Dict[str, Any]:
        """Calculates aggregated book shelf statistics and average rating."""
        docs = self.stream_all()
        shelves = Counter()
        ratings = []
        for b in docs:
            shelves[b.get("shelf", "unknown")] += 1
            r = b.get("user_rating")
            if r and r > 0:
                ratings.append(r)
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
        return {
            "total": len(docs),
            "read": shelves.get("read", 0),
            "currently_reading": shelves.get("currently-reading", 0),
            "to_read": shelves.get("to-read", 0),
            "avg_user_rating": avg_rating,
        }
