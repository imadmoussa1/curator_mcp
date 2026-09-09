"""
Goodreads CSV Importer for life_os_mcp.
Ingests Goodreads library export CSV files into the Firestore 'books' collection.

OOP Senior Architecture: Subclasses BaseImporter with typed parsing and validation.

Usage:
    python -m importers.goodreads_importer path/to/goodreads_library_export.csv
    python -m importers.goodreads_importer path/to/goodreads_library_export.csv --dry-run
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, List, Any
import pandas as pd
from datetime import datetime, timezone

from models import BookModel
from importers.base import BaseImporter


def clean_book_id(val: Any) -> str:
    """Cleans Goodreads ID strings which occasionally contain Excel formatting like =\"12345\"."""
    s = str(val).strip()
    s = s.replace('="', '').replace('"', '').replace('=', '')
    if s.endswith('.0'):
        s = s[:-2]
    return s


def parse_date_read(val: Any) -> Optional[str]:
    """Parses date string or timestamp into YYYY-MM-DD."""
    if pd.isna(val) or val is None or str(val).strip() == "":
        return None
    try:
        dt = pd.to_datetime(val)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(val).strip()[:10]


class GoodreadsImporter(BaseImporter):
    """
    Data ingestion pipeline for Goodreads library export CSV files.
    Normalizes column schemas, converts rows to BookModel entities, and batches writes to Firestore.
    """

    def __init__(self, dry_run: bool = False):
        super().__init__(collection_name="books", dry_run=dry_run)

    def parse_dataframe(self, df: pd.DataFrame) -> List[BookModel]:
        """
        Parses and maps Goodreads DataFrame columns to BookModel instances.
        Handles column name variations gracefully across Goodreads export revisions.
        """
        col_map = {}
        for col in df.columns:
            norm = col.strip().lower().replace(" ", "_").replace("-", "_")
            col_map[norm] = col

        def get_val(row, *candidates, default=""):
            for c in candidates:
                c_norm = c.lower().replace(" ", "_").replace("-", "_")
                if c_norm in col_map:
                    val = row[col_map[c_norm]]
                    if not pd.isna(val):
                        return val
            return default

        books: List[BookModel] = []

        for _, row in df.iterrows():
            raw_id = get_val(row, "Book Id", "book_id", "id")
            book_id = clean_book_id(raw_id)
            if not book_id or book_id == "nan":
                continue

            title = str(get_val(row, "Title", "title", default="Untitled")).strip()
            author = str(get_val(row, "Author", "author", "author_l_f", default="Unknown")).strip()

            # Ratings
            try:
                user_rating = int(float(get_val(row, "My Rating", "my_rating", "rating", default=0)))
                user_rating = max(0, min(5, user_rating))
            except (ValueError, TypeError):
                user_rating = 0

            try:
                avg_rating = float(get_val(row, "Average Rating", "average_rating", "avg_rating", default=0.0))
                avg_rating = max(0.0, min(5.0, avg_rating))
            except (ValueError, TypeError):
                avg_rating = 0.0

            shelf = str(get_val(row, "Exclusive Shelf", "exclusive_shelf", "bookshelves", "shelf", default="to-read"))
            review = str(get_val(row, "My Review", "my_review", "review", default="")).strip()
            date_read = parse_date_read(get_val(row, "Date Read", "date_read", default=None))

            book = BookModel(
                id=book_id,
                title=title,
                author=author,
                user_rating=user_rating,
                avg_rating=avg_rating,
                shelf=shelf,
                notes_and_reviews=review,
                date_read=date_read,
                updated_at=datetime.now(timezone.utc),
            )
            books.append(book)

        return books

    def parse_file(self, file_path: str) -> List[BookModel]:
        """Reads Goodreads CSV and parses into typed BookModel instances."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Goodreads CSV file not found: {file_path}")

        print(f"📖 Reading Goodreads CSV: {path.name}...")
        df = pd.read_csv(path, dtype=str)
        books = self.parse_dataframe(df)
        print(f"✅ Successfully parsed {len(books)} books from CSV.")
        return books

    def import_file(self, file_path: str) -> int:
        """Parses and ingests a Goodreads CSV file in batches of 500."""
        books = self.parse_file(file_path)
        return self.upsert_batch(books)


def parse_goodreads_dataframe(df: pd.DataFrame) -> List[BookModel]:
    """Backwards-compatible wrapper function for parse_dataframe."""
    importer = GoodreadsImporter()
    return importer.parse_dataframe(df)


def ingest_goodreads_csv(csv_path: str, dry_run: bool = False) -> int:
    """Backwards-compatible wrapper function for Goodreads ingestion."""
    importer = GoodreadsImporter(dry_run=dry_run)
    return importer.import_file(csv_path)


def main():
    parser = argparse.ArgumentParser(description="Ingest Goodreads library export CSV into Firestore 'books' collection.")
    parser.add_argument("csv_path", help="Path to goodreads_library_export.csv")
    parser.add_argument("--dry-run", action="store_true", help="Parse and print preview without writing to Firestore")

    args = parser.parse_args()
    try:
        ingest_goodreads_csv(args.csv_path, dry_run=args.dry_run)
    except Exception as e:
        print(f"❌ Ingestion failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
