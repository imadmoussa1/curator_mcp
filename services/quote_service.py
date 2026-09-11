"""
Domain service managing quotes, excerpts, mental models, and reflections.
"""

from datetime import datetime, timezone
import random
import uuid
import re
from typing import Optional, List, Dict, Any

from models import QuoteModel
from services.base_repository import BaseFirestoreRepository


class QuoteService(BaseFirestoreRepository):
    """Business logic and persistence layer for Quotes and Mental Models."""

    def __init__(self):
        super().__init__("quotes")

    def _generate_quote_id(self, source_title: str, speaker_or_author: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", f"{source_title}_{speaker_or_author}".lower()).strip("_")
        return f"quote_{slug[:25]}_{uuid.uuid4().hex[:6]}"

    @staticmethod
    def _normalize_text(s: str) -> str:
        if not s:
            return ""
        return re.sub(r"[^a-z0-9]", "", s.strip().lower())

    def find_existing(self, quote_text: str, source_title: Optional[str] = None) -> Optional[Dict[str, Any]]:
        norm_q = self._normalize_text(quote_text)
        norm_s = self._normalize_text(source_title) if source_title else ""
        for doc in self.stream_all():
            dq = self._normalize_text(doc.get("quote_text") or "")
            if dq == norm_q or (len(norm_q) > 20 and norm_q in dq) or (len(dq) > 20 and dq in norm_q):
                if norm_s:
                    ds = self._normalize_text(doc.get("source_title") or "")
                    if ds == norm_s or norm_s in ds or ds in norm_s:
                        return doc
                else:
                    return doc
        return None

    def add(
        self,
        quote_text: str,
        source_title: str,
        source_type: str = "book",
        speaker_or_author: Optional[str] = "",
        theme_tags: Optional[List[str]] = None,
        notes: Optional[str] = "",
        favorite: bool = False
    ) -> Dict[str, Any]:
        """Save a memorable quote with metadata."""
        existing = self.find_existing(quote_text, source_title)
        if existing:
            doc_id = existing["id"]
            if theme_tags:
                existing["theme_tags"] = list(set(existing.get("theme_tags", []) + theme_tags))
            if favorite:
                existing["favorite"] = True
            if notes:
                existing["notes"] = f"{existing.get('notes', '')} | {notes}".strip(" | ")
            existing["updated_at"] = datetime.now(timezone.utc)
            self.set(doc_id, existing)
            return {
                "status": "already_exists",
                "message": f"Quote from '{source_title}' already exists; updated tags/notes (duplicate prevented).",
                "quote": existing
            }

        quote_id = self._generate_quote_id(source_title, speaker_or_author or "")
        quote = QuoteModel(
            id=quote_id,
            quote_text=quote_text.strip(),
            source_type=source_type,
            source_title=source_title.strip(),
            speaker_or_author=speaker_or_author.strip() if speaker_or_author else "",
            theme_tags=theme_tags or [],
            notes=notes or "",
            favorite=favorite,
            updated_at=datetime.now(timezone.utc)
        )
        self.set(quote_id, quote.to_firestore_dict())
        return {
            "status": "success",
            "message": f"Saved quote from '{source_title}'.",
            "quote": quote.to_firestore_dict()
        }

    def get_random(self, theme: Optional[str] = None, source_type: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve a random quote, optionally filtered by theme or source type."""
        docs = self.stream_all()
        if source_type:
            s_norm = "media" if "media" in source_type.lower() or "movie" in source_type.lower() else "book"
            docs = [q for q in docs if q.get("source_type", "").lower() == s_norm]

        if theme:
            t_norm = theme.lower().strip()
            docs = [q for q in docs if any(t_norm in tag.lower() for tag in q.get("theme_tags", []))]

        if not docs:
            return {"status": "not_found", "message": "No matching quotes found in your database."}

        selected = random.choice(docs)
        return {"status": "success", "quote": selected}

    def search(
        self,
        query: str,
        theme: Optional[str] = None,
        source_title: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search saved quotes by keywords, themes, author, or title."""
        q_norm = query.lower().strip()
        t_norm = theme.lower().strip() if theme else None
        title_norm = source_title.lower().strip() if source_title else None

        matches = []
        for q in self.stream_all():
            text = (q.get("quote_text") or "").lower()
            speaker = (q.get("speaker_or_author") or "").lower()
            source = (q.get("source_title") or "").lower()
            tags = [tag.lower() for tag in q.get("theme_tags", [])]

            if query and not (q_norm in text or q_norm in speaker or q_norm in source):
                continue
            if t_norm and not any(t_norm in tag for tag in tags):
                continue
            if title_norm and title_norm not in source:
                continue

            matches.append(q)
            if len(matches) >= limit:
                break
        return matches

    def list_favorites(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve favorited quotes."""
        return self.filter_by("favorite", "==", True, limit=limit)
