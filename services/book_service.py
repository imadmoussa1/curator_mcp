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

    def search(self, query: str = "", shelf: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search books by title or author keywords with optional shelf filter."""
        q_norm = query.strip().lower()
        matches = []
        docs = self.stream_all()

        for b in docs:
            if shelf and b.get("shelf", "").lower() != shelf.strip().lower():
                continue
            title = (b.get("title") or "").lower()
            author = (b.get("author") or "").lower()
            if not q_norm or q_norm in title or q_norm in author:
                matches.append({
                    "id": b.get("id"),
                    "title": b.get("title"),
                    "author": b.get("author"),
                    "user_rating": b.get("user_rating"),
                    "avg_rating": b.get("avg_rating"),
                    "shelf": b.get("shelf"),
                    "date_read": b.get("date_read"),
                    "notes": b.get("notes_and_reviews"),
                })
                if len(matches) >= limit:
                    break
        return matches

    def get_recently_read(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve most recently finished and rated books, sorted by date read descending."""
        docs = self.filter_by("shelf", "==", "read")
        items = []
        for b in docs:
            d_read = b.get("date_read") or "1970-01-01"
            items.append({
                "id": b.get("id"),
                "title": b.get("title"),
                "author": b.get("author"),
                "user_rating": b.get("user_rating"),
                "avg_rating": b.get("avg_rating"),
                "shelf": b.get("shelf"),
                "date_read": b.get("date_read"),
                "notes": b.get("notes_and_reviews"),
                "_sort_date": d_read,
            })
        items.sort(key=lambda x: x["_sort_date"], reverse=True)
        for it in items:
            it.pop("_sort_date", None)
        return items[:limit]

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

    @staticmethod
    def _normalize_str(s: str) -> str:
        if not s:
            return ""
        st = s.strip().lower()
        st = re.sub(r"^(the|a|an)\s+", "", st)
        return re.sub(r"[^a-z0-9]", "", st)

    def find_existing(self, title: str, author: Optional[str] = None, book_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find existing book by ID, exact title/author, or normalized title/author."""
        if book_id:
            doc = self.get(book_id.strip())
            if doc:
                return doc
        norm_t = self._normalize_str(title)
        raw_t = title.strip().lower()
        norm_a = self._normalize_str(author) if author else ""
        docs = self.stream_all()
        for doc in docs:
            b_title = (doc.get("title") or "").strip()
            if not b_title:
                continue
            b_author = (doc.get("author") or "").strip()
            # Match title
            if b_title.lower() == raw_t or (norm_t and self._normalize_str(b_title) == norm_t):
                if norm_a and b_author:
                    doc_norm_a = self._normalize_str(b_author)
                    if norm_a in doc_norm_a or doc_norm_a in norm_a:
                        return doc
                else:
                    return doc
        return None

    def add_to_reading_list(self, title: str, author: str, book_id: Optional[str] = None, notes: Optional[str] = "") -> Dict[str, Any]:
        """Add a book to 'to-read' shelf with de-duplication."""
        existing = self.find_existing(title=title, author=author, book_id=book_id)
        if existing:
            doc_id = existing["id"]
            existing_shelf = existing.get("shelf", "to-read")
            if existing_shelf == "to-read":
                return {
                    "status": "already_exists",
                    "message": f"'{existing.get('title', title)}' is already on your reading list (ID: {doc_id}). Duplicate prevented.",
                    "book": existing
                }
            else:
                existing["shelf"] = "to-read"
                existing["updated_at"] = datetime.now(timezone.utc)
                if notes:
                    existing["notes_and_reviews"] = f"{existing.get('notes_and_reviews', '')} | {notes}".strip(" | ")
                self.set(doc_id, existing)
                return {
                    "status": "updated",
                    "message": f"'{existing.get('title', title)}' was marked as {existing_shelf}; updated to to-read shelf (duplicate prevented).",
                    "book": existing
                }

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
        review: Optional[str] = "",
        private_notes: Optional[str] = "",
        date_read: Optional[str] = None
    ) -> Dict[str, Any]:
        """Log a finished book with Goodreads rating (0-5 stars) and de-duplication."""
        if not date_read:
            date_read = datetime.now().strftime("%Y-%m-%d")

        written_review = (review or "").strip()
        priv_notes = (private_notes or "").strip()
        legacy_notes = (notes or "").strip()
        if not written_review and legacy_notes:
            written_review = legacy_notes

        existing = self.find_existing(title=title, author=author, book_id=book_id)
        if existing:
            doc_id = existing["id"]
            existing["shelf"] = "read"
            existing["user_rating"] = max(0, min(5, user_rating))
            if written_review:
                existing["review"] = written_review
                existing["notes_and_reviews"] = written_review
            if priv_notes:
                existing["private_notes"] = priv_notes
            existing["date_read"] = date_read
            existing["updated_at"] = datetime.now(timezone.utc)
            self.set(doc_id, existing)
            return {
                "status": "success",
                "message": f"Updated existing book '{existing.get('title', title)}' as read (duplicate prevented).",
                "book": existing
            }

        doc_id = book_id.strip() if book_id else self._generate_book_id(title, author)
        book = BookModel(
            id=doc_id,
            title=title.strip(),
            author=author.strip(),
            user_rating=max(0, min(5, user_rating)),
            shelf="read",
            notes_and_reviews=legacy_notes or written_review,
            review=written_review,
            private_notes=priv_notes,
            date_read=date_read,
            updated_at=datetime.now(timezone.utc)
        )
        self.set(doc_id, book.to_firestore_dict())
        return {
            "status": "success",
            "message": f"Logged '{title}' by {author} as read with Goodreads rating {user_rating}/5.",
            "book": book.to_firestore_dict()
        }

    def update_status(
        self,
        book_id: Optional[str] = None,
        title: Optional[str] = None,
        shelf: str = "read",
        user_rating: Optional[int] = None,
        review: Optional[str] = None,
        private_notes: Optional[str] = None,
        date_read: Optional[str] = None,
        date_started: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update a book's reading status/shelf (Goodreads system: 'read', 'currently-reading', 'to-read'),
        with optional user rating (0-5 stars), written review, private notes, and dates.
        Locates the book by book_id or fuzzy title match.
        """
        target_doc = None
        if book_id:
            target_doc = self.get(book_id.strip())

        if not target_doc and title:
            matches = self.search(query=title, limit=1)
            if matches:
                target_doc = self.get(matches[0]["id"])

        if not target_doc:
            return {
                "status": "error",
                "message": f"Book not found by ID '{book_id}' or title '{title}'. Consider adding it first."
            }

        doc_id = target_doc["id"]
        shelf_clean = shelf.strip().lower()
        if "current" in shelf_clean:
            shelf_clean = "currently-reading"
        elif "to" in shelf_clean and "read" in shelf_clean:
            shelf_clean = "to-read"
        elif "read" in shelf_clean:
            shelf_clean = "read"

        target_doc["shelf"] = shelf_clean
        target_doc["updated_at"] = datetime.now(timezone.utc)

        if user_rating is not None:
            target_doc["user_rating"] = max(0, min(5, int(user_rating)))

        if review is not None:
            target_doc["review"] = review.strip()
            # Keep legacy notes_and_reviews in sync
            target_doc["notes_and_reviews"] = review.strip()

        if private_notes is not None:
            target_doc["private_notes"] = private_notes.strip()

        if date_started is not None:
            target_doc["date_started"] = date_started.strip()

        if date_read is not None:
            target_doc["date_read"] = date_read.strip()
        elif shelf_clean == "read" and not target_doc.get("date_read"):
            target_doc["date_read"] = datetime.now().strftime("%Y-%m-%d")

        self.set(doc_id, target_doc)
        return {
            "status": "success",
            "message": f"Updated book '{target_doc.get('title')}' status to '{shelf_clean}'.",
            "book": target_doc
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
