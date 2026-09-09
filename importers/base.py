"""
Base importer class handling batch writes and chunking into Firestore.
"""

from abc import ABC, abstractmethod
from typing import List, Any
import pandas as pd
from config import get_db


class BaseImporter(ABC):
    """
    Abstract base class for data ingestion pipelines into Firestore.
    Provides standard batch chunking, dry-run simulation, and progress tracking.
    """

    BATCH_SIZE = 500

    def __init__(self, collection_name: str, dry_run: bool = False):
        self.collection_name = collection_name
        self.dry_run = dry_run

    @property
    def client(self):
        return get_db()

    @property
    def collection(self):
        return self.client.collection(self.collection_name)

    @abstractmethod
    def parse_file(self, file_path: str) -> List[Any]:
        """Parse source export file into list of domain model instances."""
        pass

    def upsert_batch(self, items: List[Any]) -> int:
        """Upsert a list of model instances in batches of 500."""
        total = len(items)
        if total == 0:
            print("⚠️ No records to import.")
            return 0

        if self.dry_run:
            print(f"🔍 [DRY RUN] Would write {total} records to '{self.collection_name}'.")
            if items:
                print(f"Sample preview:\n{items[0].to_firestore_dict()}")
            return total

        written = 0
        current_batch = self.client.batch()
        batch_count = 0

        for item in items:
            doc_ref = self.collection.document(item.id)
            current_batch.set(doc_ref, item.to_firestore_dict(), merge=True)
            batch_count += 1

            if batch_count >= self.BATCH_SIZE:
                current_batch.commit()
                written += batch_count
                print(f"  ↳ Committed batch of {batch_count} records ({written}/{total})...")
                current_batch = self.client.batch()
                batch_count = 0

        if batch_count > 0:
            current_batch.commit()
            written += batch_count
            print(f"  ↳ Committed final batch of {batch_count} records ({written}/{total}).")

        print(f"🎉 Complete! Successfully upserted {written} records into collection '{self.collection_name}'.")
        return written
