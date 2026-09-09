"""
IMDb CSV Importer for life_os_mcp.
Ingests IMDb ratings.csv and watchlist.csv exports into the Firestore 'media' collection.

OOP Senior Architecture: Subclasses BaseImporter with typed parsing and validation.

Usage:
    python -m importers.imdb_importer --ratings path/to/ratings.csv --watchlist path/to/watchlist.csv
    python -m importers.imdb_importer --ratings path/to/ratings.csv
    python -m importers.imdb_importer --watchlist path/to/watchlist.csv --dry-run
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime, timezone

from models import MediaModel
from importers.base import BaseImporter


def clean_list_field(val: Any) -> List[str]:
    """Splits comma-separated genres or directors into a clean list of trimmed strings."""
    if pd.isna(val) or val is None:
        return []
    s = str(val).strip()
    if not s:
        return []
    return [item.strip() for item in s.split(",") if item.strip()]


class IMDbImporter(BaseImporter):
    """
    Data ingestion pipeline for IMDb ratings and watchlist CSV exports.
    Normalizes schemas, deduplicates IDs across ratings & watchlist, and batches writes to Firestore.
    """

    def __init__(self, dry_run: bool = False):
        super().__init__(collection_name="media", dry_run=dry_run)

    def parse_dataframe(self, df: pd.DataFrame, default_status: str = "watched") -> List[MediaModel]:
        """
        Parses IMDb export dataframe into MediaModel instances.
        Extracts Const (ID), Your Rating, Date Rated, Title, Title Type, IMDb Rating, Year, Genres, Directors.
        """
        col_map = {}
        for col in df.columns:
            norm = col.strip().lower().replace(" ", "_").replace("-", "_")
            col_map[norm] = col

        def get_val(row, *candidates, default=None):
            for c in candidates:
                c_norm = c.lower().replace(" ", "_").replace("-", "_")
                if c_norm in col_map:
                    val = row[col_map[c_norm]]
                    if not pd.isna(val) and val is not None and str(val).strip() != "":
                        return val
            return default

        media_items: List[MediaModel] = []

        for _, row in df.iterrows():
            const_id = get_val(row, "Const", "const", "imdb_id", "id")
            if not const_id:
                continue
            const_id = str(const_id).strip()

            title = str(get_val(row, "Title", "title", default="Untitled")).strip()
            media_type = str(get_val(row, "Title Type", "title_type", "type", default="movie")).strip()

            # User rating
            raw_user_rating = get_val(row, "Your Rating", "your_rating", "user_rating", "rating")
            user_rating = None
            if raw_user_rating is not None:
                try:
                    user_rating = int(float(raw_user_rating))
                    user_rating = max(1, min(10, user_rating))
                except (ValueError, TypeError):
                    user_rating = None

            # IMDb rating
            raw_imdb_rating = get_val(row, "IMDb Rating", "imdb_rating", "avg_rating")
            imdb_rating = None
            if raw_imdb_rating is not None:
                try:
                    imdb_rating = float(raw_imdb_rating)
                    imdb_rating = max(0.0, min(10.0, imdb_rating))
                except (ValueError, TypeError):
                    imdb_rating = None

            # Year
            raw_year = get_val(row, "Year", "year", "release_year")
            year = None
            if raw_year is not None:
                try:
                    year = int(float(raw_year))
                except (ValueError, TypeError):
                    year = None

            genres = clean_list_field(get_val(row, "Genres", "genres", default=""))
            directors = clean_list_field(get_val(row, "Directors", "directors", "director", default=""))

            date_rated = get_val(row, "Date Rated", "date_rated")
            notes = f"Rated on {date_rated}" if date_rated else ""

            # Status: if user provided a rating, mark watched; otherwise use default_status
            status = "watched" if user_rating is not None else default_status

            item = MediaModel(
                id=const_id,
                title=title,
                media_type=media_type,
                user_rating=user_rating,
                imdb_rating=imdb_rating,
                year=year,
                genres=genres,
                directors=directors,
                status=status,
                notes=notes,
                updated_at=datetime.now(timezone.utc),
            )
            media_items.append(item)

        return media_items

    def parse_file(self, file_path: str, default_status: str = "watched") -> List[MediaModel]:
        """Parses a single IMDb CSV file (ratings or watchlist)."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"IMDb CSV file not found: {file_path}")

        print(f"🎬 Reading IMDb CSV: {path.name}...")
        df = pd.read_csv(path, dtype=str)
        return self.parse_dataframe(df, default_status=default_status)

    def parse_imdb_files(
        self,
        ratings_path: Optional[str] = None,
        watchlist_path: Optional[str] = None,
    ) -> List[MediaModel]:
        """
        Parses watchlist and/or ratings files and merges them.
        If a title appears in both, the rated version (with watched status and rating) takes precedence.
        """
        if not ratings_path and not watchlist_path:
            raise ValueError("Must provide at least one of ratings_path or watchlist_path")

        all_items: Dict[str, MediaModel] = {}

        if watchlist_path:
            watch_items = self.parse_file(watchlist_path, default_status="watchlist")
            for item in watch_items:
                all_items[item.id] = item
            print(f"  ↳ Loaded {len(watch_items)} watchlist items.")

        if ratings_path:
            rate_items = self.parse_file(ratings_path, default_status="watched")
            for item in rate_items:
                all_items[item.id] = item
            print(f"  ↳ Loaded {len(rate_items)} rated items.")

        media_list = list(all_items.values())
        print(f"✅ Total unique media items parsed: {len(media_list)}")
        return media_list

    def import_files(
        self,
        ratings_path: Optional[str] = None,
        watchlist_path: Optional[str] = None,
    ) -> int:
        """Parses and ingests IMDb ratings and/or watchlist files in batches of 500."""
        media_list = self.parse_imdb_files(ratings_path=ratings_path, watchlist_path=watchlist_path)
        return self.upsert_batch(media_list)


def parse_imdb_dataframe(df: pd.DataFrame, default_status: str) -> List[MediaModel]:
    """Backwards-compatible wrapper function for parse_dataframe."""
    importer = IMDbImporter()
    return importer.parse_dataframe(df, default_status=default_status)


def ingest_imdb_files(
    ratings_path: Optional[str] = None,
    watchlist_path: Optional[str] = None,
    dry_run: bool = False,
) -> int:
    """Backwards-compatible wrapper function for IMDb ingestion."""
    importer = IMDbImporter(dry_run=dry_run)
    return importer.import_files(ratings_path=ratings_path, watchlist_path=watchlist_path)


def main():
    parser = argparse.ArgumentParser(description="Ingest IMDb export CSVs into Firestore 'media' collection.")
    parser.add_argument("--ratings", help="Path to IMDb ratings.csv export")
    parser.add_argument("--watchlist", help="Path to IMDb watchlist.csv export")
    parser.add_argument("--dry-run", action="store_true", help="Parse and print preview without writing to Firestore")

    args = parser.parse_args()
    if not args.ratings and not args.watchlist:
        parser.error("Please specify at least one of --ratings or --watchlist")

    try:
        ingest_imdb_files(
            ratings_path=args.ratings,
            watchlist_path=args.watchlist,
            dry_run=args.dry_run,
        )
    except Exception as e:
        print(f"❌ Ingestion failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
