"""
Base Firestore repository implementing common database operations.
Provides typed access, structured querying, and batch management with in-memory TTL caching.
"""

import time
from typing import Any, Dict, List, Optional
from google.cloud.firestore_v1.base_query import FieldFilter
from config import get_db


class BaseFirestoreRepository:
    """
    Generic repository pattern providing data access abstractions over Firestore collections
    with built-in read-reduction TTL caching and cost-optimized aggregations.
    """

    def __init__(
        self,
        collection_name: str,
        db: Optional[Any] = None,
        cache_ttl_seconds: int = 180
    ):
        self.collection_name = collection_name
        self._db = db
        self._cache_ttl = cache_ttl_seconds
        self._cached_all: Optional[List[Dict[str, Any]]] = None
        self._cache_timestamp: float = 0.0

    @property
    def collection(self):
        """Returns Firestore collection reference."""
        client = self._db if self._db is not None else get_db()
        return client.collection(self.collection_name)

    def _invalidate_cache(self) -> None:
        """Invalidate in-memory cache upon write/delete operations."""
        self._cached_all = None
        self._cache_timestamp = 0.0

    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single document by ID, or None if not found."""
        doc = self.collection.document(doc_id.strip()).get()
        return doc.to_dict() if doc.exists else None

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Alias for get_by_id."""
        return self.get_by_id(doc_id)

    def set(self, doc_id: str, data: Dict[str, Any], merge: bool = True) -> None:
        """Upsert a document by ID and invalidate read cache."""
        self.collection.document(doc_id.strip()).set(data, merge=merge)
        self._invalidate_cache()

    def delete(self, doc_id: str) -> None:
        """Delete a document by ID and invalidate read cache."""
        self.collection.document(doc_id.strip()).delete()
        self._invalidate_cache()

    def filter_by(self, field: str, op: str, value: Any, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query documents matching a specific field condition."""
        query = self.collection.where(filter=FieldFilter(field, op, value))
        if limit:
            query = query.limit(limit)
        return [doc.to_dict() for doc in query.stream()]

    def stream_all(self, limit: Optional[int] = None, bypass_cache: bool = False) -> List[Dict[str, Any]]:
        """
        Stream all documents in the collection with in-memory TTL caching to minimize Firestore reads.
        """
        now = time.time()
        # Serve from cache if still valid and no limit constraint is smaller than cached dataset
        if not bypass_cache and self._cached_all is not None and (now - self._cache_timestamp < self._cache_ttl):
            if limit:
                return self._cached_all[:limit]
            return list(self._cached_all)

        query = self.collection
        if limit and bypass_cache:
            query = query.limit(limit)
            return [doc.to_dict() for doc in query.stream()]

        docs = [doc.to_dict() for doc in query.stream()]
        self._cached_all = docs
        self._cache_timestamp = now

        if limit:
            return docs[:limit]
        return list(docs)

    def count(self) -> int:
        """
        Count total documents in the collection using Firestore aggregation query (1 read per 1,000 docs).
        Falls back to cached stream count if aggregation query is unsupported.
        """
        try:
            aggregate_query = self.collection.count()
            results = aggregate_query.get()
            return int(results[0][0].value)
        except Exception:
            return len(self.stream_all())
