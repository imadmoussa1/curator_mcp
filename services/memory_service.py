"""
Domain service managing long-term personal memory, user preferences,
habits, quirks, and ambient directives with Firestore persistence and TTL caching.
"""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import re
from typing import Any, Dict, List, Optional

from models import MemoryCategory, MemoryModel
from services.base_repository import BaseFirestoreRepository


class MemoryService(BaseFirestoreRepository):
    """
    Business logic and persistence layer for Personal Long-Term Memory.
    Equips AI agents with persistent working knowledge of user preferences,
    habits, goals, and behavioral guardrails across chat sessions.
    """

    def __init__(self, db: Optional[Any] = None, cache_ttl_seconds: int = 180):
        super().__init__("personal_memory", db=db, cache_ttl_seconds=cache_ttl_seconds)

    def _generate_memory_id(self, category: str, content: str) -> str:
        """Create a deterministic unique memory ID based on category and content hash."""
        clean_cat = category.strip().lower()[:6]
        content_hash = hashlib.sha256(content.strip().lower().encode("utf-8")).hexdigest()[:8]
        return f"mem_{clean_cat}_{content_hash}"

    def store(
        self,
        content: str,
        category: str = "preference",
        tags: Optional[List[str]] = None,
        importance: int = 3,
        source: str = "user_explicit",
    ) -> Dict[str, Any]:
        """
        Store or update a personal memory, preference, habit, or directive.
        Automatically deduplicates similar memories and updates them in place.

        Args:
            content: The text of the fact, preference, or directive.
            category: 'preference', 'dislike', 'goal', 'habit', 'context', or 'directive'.
            tags: Optional list of topic keywords for quick indexing.
            importance: 1 (minor detail) to 5 (critical hard directive).
            source: 'user_explicit' or 'conversation_observation'.
        """
        raw_content = content.strip()
        if not raw_content:
            return {"status": "error", "message": "Memory content cannot be empty."}

        norm_content = re.sub(r"[^\w\s]", "", raw_content.lower()).strip()
        all_memories = self.stream_all()

        # Check for existing memory with identical or near-identical content
        existing_doc = None
        for doc in all_memories:
            doc_norm = re.sub(r"[^\w\s]", "", (doc.get("content") or "").lower()).strip()
            if doc_norm == norm_content or (len(norm_content) > 15 and norm_content in doc_norm):
                existing_doc = doc
                break

        action = "updated" if existing_doc else "created"
        memory_id = existing_doc["id"] if existing_doc else self._generate_memory_id(category, raw_content)

        # Merge tags
        combined_tags = list(set((existing_doc.get("tags", []) if existing_doc else []) + (tags or [])))

        model = MemoryModel(
            id=memory_id,
            category=category,
            content=raw_content,
            tags=combined_tags,
            importance=max(1, min(5, importance)),
            source=source,
            created_at=existing_doc.get("created_at") if existing_doc else datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.set(memory_id, model.to_firestore_dict())

        return {
            "status": "success",
            "action": action,
            "message": f"Successfully {action} memory in '{model.category}'.",
            "memory": model.to_firestore_dict(),
        }

    def recall(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        min_importance: int = 1,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Recall stored memories filtered by topic query, category, and minimum importance.

        Args:
            query: Keyword search against content and tags.
            category: Optional category filter.
            min_importance: Filter out memories below this threshold (1-5).
            limit: Maximum items to return.
        """
        docs = self.stream_all()

        # Filter by minimum importance
        docs = [d for d in docs if (d.get("importance") or 3) >= min_importance]

        # Filter by category if specified
        if category:
            cat_norm = category.strip().lower()
            docs = [d for d in docs if d.get("category", "").lower() == cat_norm]

        # Filter and score by query if specified
        if query and query.strip():
            query_tokens = set(re.sub(r"[^\w\s]", "", query.lower()).split())
            scored = []
            for d in docs:
                content_text = (d.get("content") or "").lower()
                tags_text = " ".join([t.lower() for t in d.get("tags", [])])
                searchable = f"{content_text} {tags_text}"

                score = sum(1 for token in query_tokens if token in searchable)
                if score > 0:
                    scored.append((score, d.get("importance", 3), d))

            # Sort by match score desc, importance desc
            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            return [item[2] for item in scored[:limit]]

        # Default sort: importance desc, updated_at desc
        docs.sort(
            key=lambda x: (
                x.get("importance", 3),
                str(x.get("updated_at") or "")
            ),
            reverse=True
        )
        return docs[:limit]

    def forget(self, memory_id: str) -> Dict[str, Any]:
        """Delete an outdated or retracted memory by ID."""
        doc = self.get_by_id(memory_id)
        if not doc:
            return {"status": "error", "message": f"Memory with ID '{memory_id}' not found."}

        self.delete(memory_id)
        return {
            "status": "success",
            "message": f"Successfully deleted memory '{memory_id}'.",
            "forgotten_content": doc.get("content"),
        }

    def list_all(
        self,
        category: Optional[str] = None,
        min_importance: int = 1,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """List active memories."""
        return self.recall(category=category, min_importance=min_importance, limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        """Return memory counts broken down by category."""
        all_memories = self.stream_all()
        cat_counter = Counter()
        tag_counter = Counter()
        high_importance_count = 0

        for m in all_memories:
            cat_counter[m.get("category", "preference")] += 1
            if (m.get("importance") or 3) >= 4:
                high_importance_count += 1
            for t in m.get("tags", []):
                tag_counter[t.lower()] += 1

        return {
            "total_memories": len(all_memories),
            "high_importance_directives": high_importance_count,
            "category_breakdown": dict(cat_counter),
            "top_tags": [t for t, _ in tag_counter.most_common(8)],
        }

    def get_relevant_constraints(self, domain: Optional[str] = None) -> List[str]:
        """
        Extract high-priority dislikes, directives, and dietary/content constraints
        for injection into recommendation briefings and agent workflows.
        """
        memories = self.stream_all()
        constraints = []
        for m in memories:
            cat = m.get("category", "").lower()
            imp = m.get("importance", 3)
            content = m.get("content", "")
            tags = [t.lower() for t in m.get("tags", [])]

            if cat in ("dislike", "directive") or imp >= 4:
                if domain:
                    d_norm = domain.lower().strip()
                    if d_norm in content.lower() or any(d_norm in t for t in tags) or cat == "directive":
                        constraints.append(f"[{cat.upper()}] {content}")
                else:
                    constraints.append(f"[{cat.upper()}] {content}")
        return constraints

    def get_personal_memory_summary(self) -> str:
        """
        Generate synthesized Markdown representation of the user's active memories
        and directives for the Claude Desktop MCP Resource (curator://context/personal_memory).
        """
        all_memories = self.stream_all()
        if not all_memories:
            return (
                "# User Personal Memory & Ambient Directives (Curator MCP)\n"
                "*No personal memories stored yet. Tell Claude to 'remember that...' to populate.*"
            )

        directives_and_dislikes = []
        goals_and_context = []
        preferences_and_habits = []

        for m in sorted(all_memories, key=lambda x: x.get("importance", 3), reverse=True):
            cat = m.get("category", "").lower()
            imp = m.get("importance", 3)
            stars = "★" * imp
            line = f"- **[{m.get('id')}]** {m.get('content')} *({stars} {cat})*"

            if cat in (MemoryCategory.DIRECTIVE.value, MemoryCategory.DISLIKE.value):
                directives_and_dislikes.append(line)
            elif cat in (MemoryCategory.GOAL.value, MemoryCategory.CONTEXT.value):
                goals_and_context.append(line)
            elif imp >= 4:
                directives_and_dislikes.append(line)
            else:
                preferences_and_habits.append(line)

        md_sections = ["# User Personal Memory & Ambient Directives (Curator MCP)"]

        if directives_and_dislikes:
            md_sections.append("## 🚨 Critical Directives, Guardrails & Dislikes")
            md_sections.extend(directives_and_dislikes)

        if goals_and_context:
            md_sections.append("## 🎯 Active Life Context & Goals")
            md_sections.extend(goals_and_context)

        if preferences_and_habits:
            md_sections.append("## ⭐ Personal Preferences & Lifestyle Habits")
            md_sections.extend(preferences_and_habits)

        return "\n".join(md_sections)
