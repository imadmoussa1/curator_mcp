"""
Unit tests for the Long-Term Personal Memory Vault, MemoryService,
and MCP ambient context resources.
"""

import unittest
from unittest.mock import MagicMock

from models import MemoryModel
from services.memory_service import MemoryService
from services.recommendation_service import RecommendationService
from mcp_server import (
    store_memory,
    recall_memories,
    forget_memory,
    get_memory_stats,
    get_personal_memory_context,
)


class TestMemoryService(unittest.TestCase):

    def setUp(self):
        # Mock repository database client
        self.mock_db = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_db.collection.return_value = self.mock_collection

        # In-memory document storage for the mock
        self.stored_docs = {}

        def mock_set(doc_id, data, merge=True):
            self.stored_docs[doc_id] = data

        def mock_get(doc_id):
            doc = MagicMock()
            if doc_id in self.stored_docs:
                doc.exists = True
                doc.to_dict.return_value = self.stored_docs[doc_id]
            else:
                doc.exists = False
            return doc

        def mock_delete(doc_id):
            self.stored_docs.pop(doc_id, None)

        def mock_stream():
            docs = []
            for doc_id, data in self.stored_docs.items():
                m = MagicMock()
                m.id = doc_id
                m.to_dict.return_value = data
                docs.append(m)
            return docs

        self.mock_collection.document.side_effect = lambda did: MagicMock(
            set=lambda data, merge=True: mock_set(did, data, merge),
            get=lambda: mock_get(did),
            delete=lambda: mock_delete(did)
        )
        self.mock_collection.stream.side_effect = mock_stream

        self.service = MemoryService(db=self.mock_db, cache_ttl_seconds=0)

    def test_memory_model_validation(self):
        m = MemoryModel(
            id="mem_test_1",
            category="dislike",
            content="Dislikes 3D movies due to eye strain",
            importance=5,
            tags=["cinema", "health"]
        )
        d = m.to_firestore_dict()
        self.assertEqual(d["category"], "dislike")
        self.assertEqual(d["importance"], 5)
        self.assertIn("cinema", d["tags"])
        self.assertIsNotNone(d["created_at"])
        self.assertIsNotNone(d["updated_at"])

    def test_store_and_deduplication(self):
        # 1. Store initial memory
        res1 = self.service.store(
            content="Prefers intimate counter seating at sushi restaurants",
            category="preference",
            tags=["dining", "sushi"],
            importance=4
        )
        self.assertEqual(res1["status"], "success")
        self.assertEqual(res1["action"], "created")
        mem_id = res1["memory"]["id"]

        # 2. Store identical/updated memory -> should update rather than duplicate
        res2 = self.service.store(
            content="Prefers intimate counter seating at sushi restaurants",
            category="preference",
            tags=["omakase"],
            importance=5
        )
        self.assertEqual(res2["status"], "success")
        self.assertEqual(res2["action"], "updated")
        self.assertEqual(res2["memory"]["id"], mem_id)
        self.assertEqual(res2["memory"]["importance"], 5)
        self.assertIn("omakase", res2["memory"]["tags"])
        self.assertIn("dining", res2["memory"]["tags"])

    def test_recall_and_importance_filtering(self):
        self.service.store("Never recommend horror movies with jump scares", category="dislike", importance=5, tags=["movies"])
        self.service.store("Visiting Tokyo and Kyoto in October 2026", category="context", importance=4, tags=["travel", "japan"])
        self.service.store("Prefers light-roast Ethiopian pour-over coffee", category="preference", importance=3, tags=["coffee"])
        self.service.store("Minor preference for hardcover books", category="preference", importance=1, tags=["books"])

        # Recall by query
        coffee_recs = self.service.recall(query="Ethiopian coffee")
        self.assertEqual(len(coffee_recs), 1)
        self.assertIn("Ethiopian", coffee_recs[0]["content"])

        # Recall by category
        dislikes = self.service.recall(category="dislike")
        self.assertEqual(len(dislikes), 1)
        self.assertEqual(dislikes[0]["category"], "dislike")

        # Recall by minimum importance (>= 4)
        crucial = self.service.recall(min_importance=4)
        self.assertEqual(len(crucial), 2)
        for c in crucial:
            self.assertGreaterEqual(c["importance"], 4)

    def test_forget_memory(self):
        res = self.service.store("Temporary note to forget", category="context", importance=2)
        mem_id = res["memory"]["id"]

        del_res = self.service.forget(mem_id)
        self.assertEqual(del_res["status"], "success")

        # Verify it no longer exists
        remaining = self.service.recall(query="Temporary note")
        self.assertEqual(len(remaining), 0)

    def test_personal_memory_summary_markdown(self):
        self.service.store("Always provide 2 book alternatives", category="directive", importance=5)
        self.service.store("Aiming to read 24 books in 2026", category="goal", importance=4)
        self.service.store("Prefers natural wine", category="preference", importance=3)

        summary = self.service.get_personal_memory_summary()
        self.assertIn("# User Personal Memory & Ambient Directives", summary)
        self.assertIn("Critical Directives", summary)
        self.assertIn("Active Life Context & Goals", summary)
        self.assertIn("Personal Preferences & Lifestyle Habits", summary)

    def test_recommendation_brief_memory_synergy(self):
        # Create recommendation service with memory_service attached
        mock_books = MagicMock()
        mock_books.stream_all.return_value = [
            {"title": "Dune", "author": "Frank Herbert", "user_rating": 5, "shelf": "read"}
        ]
        mock_media = MagicMock()
        mock_media.stream_all.return_value = [
            {"title": "Blade Runner 2049", "user_rating": 10, "status": "watched", "media_type": "movie"}
        ]

        # Add dislike constraint in memory
        self.service.store("Hates excessive CGI superhero spectacles", category="dislike", importance=5, tags=["movies"])
        self.service.store("Loves atmospheric Denis Villeneuve cinematography", category="preference", importance=4, tags=["movies"])

        rec_service = RecommendationService(
            book_service=mock_books,
            media_service=mock_media,
            memory_service=self.service,
        )

        brief = rec_service.get_agent_recommendation_brief(domain="movies")
        self.assertEqual(brief["status"], "success")
        guardrails = brief["briefing_for_ai_agent"]["guardrails_and_dislikes"]
        self.assertTrue(any("excessive CGI" in g for g in guardrails))

        dna = brief["briefing_for_ai_agent"]["user_taste_dna"]
        self.assertIn("remembered_personal_preferences", dna)
        self.assertTrue(any("Denis Villeneuve" in p for p in dna["remembered_personal_preferences"]))


class TestMemoryMCPTools(unittest.TestCase):

    def test_mcp_presentation_tools(self):
        # Test store_memory
        stored = store_memory(
            content="Prefers quiet coffee shops with good natural light",
            category="preference",
            tags=["coffee", "work"],
            importance=4,
        )
        self.assertEqual(stored["status"], "success")
        mem_id = stored["memory"]["id"]

        # Test recall_memories
        recalled = recall_memories(query="natural light")
        self.assertEqual(recalled["status"], "success")
        self.assertGreater(recalled["total_matches"], 0)

        # Test get_personal_memory_context resource
        context = get_personal_memory_context()
        self.assertIsInstance(context, str)
        self.assertIn("User Personal Memory & Ambient Directives", context)

        # Test stats
        stats = get_memory_stats()
        self.assertIn("total_memories", stats)

        # Clean up with forget_memory
        forget_res = forget_memory(mem_id)
        self.assertEqual(forget_res["status"], "success")


if __name__ == "__main__":
    unittest.main()
