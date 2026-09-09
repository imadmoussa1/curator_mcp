"""
Base Firestore repository implementing common database operations.
Provides typed access, structured querying, and batch management.
"""

from typing import Any, Dict, List, Optional
from google.cloud.firestore_v1.base_query import FieldFilter
from config import get_db


class BaseFirestoreRepository:
    """
    Generic repository pattern providing data access abstractions over Firestore collections.
    """

    def __init__(self, collection_name: str):
        self.collection_name = collection_name

    @property
    def collection(self):
        """Returns Firestore collection reference."""
        return get_db().collection(self.collection_name)

    def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single document by ID, or None if not found."""
        doc = self.collection.document(doc_id.strip()).get()
        return doc.to_dict() if doc.exists else None

    def set(self, doc_id: str, data: Dict[str, Any], merge: bool = True) -> None:
        """Upsert a document by ID."""
        self.collection.document(doc_id.strip()).set(data, merge=merge)

    def delete(self, doc_id: str) -> None:
        """Delete a document by ID."""
        self.collection.document(doc_id.strip()).delete()

    def filter_by(self, field: str, op: str, value: Any, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query documents matching a specific field condition."""
        query = self.collection.where(filter=FieldFilter(field, op, value))
        if limit:
            query = query.limit(limit)
        return [doc.to_dict() for doc in query.stream()]

    def stream_all(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Stream all documents in the collection."""
        query = self.collection
        if limit:
            query = query.limit(limit)
        return [doc.to_dict() for doc in query.stream()]

    def count(self) -> int:
        """Count total documents in the collection."""
        return len(self.stream_all())
