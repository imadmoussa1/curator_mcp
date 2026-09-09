"""
IMDb CSV Importer for life_os_mcp.
Ingests IMDb ratings.csv and watchlist.csv exports into the Firestore 'media' collection.

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

from config import db, get_db
from models import MediaModel


BATCH_SIZE = 500


def clean_list_field(val: Any) -> List[str]:
    """Splits comma-separated genres or directors into a clean list of trimmed strings."""
    if pd.isna(val) or val is None:
        return []
    s = str(val).strip()
    if not s:
        return []
    return [item.strip() for item in s.split(",") if item.strip()]


def parse_imdb_dataframe(df: pd.DataFrame, default_status: str) -> List[MediaModel]:
    """
    Parses IMDb export dataframe into MediaModel instances.
    Extracts Const, Your Rating, Date Rated, Title, Title Type, IMDb Rating, Year, Genres, Directors.
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


def ingest_imdb_files(
    ratings_path: Optional[str] = None,
    watchlist_path: Optional[str] = None,
    dry_run: bool = False,
) -> int:
    """
    Ingests IMDb ratings and/or watchlist CSV files into Firestore 'media' collection in 500-doc batches.
    """
    if not ratings_path and not watchlist_path:
        raise ValueError("Must provide at least one of --ratings or --watchlist")

    all_items: Dict[str, MediaModel] = {}

    # Parse watchlist first (so ratings can overwrite/upgrade status to 'watched' if duplicate)
    if watchlist_path:
        p_watch = Path(watchlist_path)
        if not p_watch.exists():
            raise FileNotFoundError(f"Watchlist file not found: {watchlist_path}")
        print(f"🎬 Reading IMDb Watchlist CSV: {p_watch.name}...")
        df_watch = pd.read_csv(p_watch, dtype=str)
        watch_items = parse_imdb_dataframe(df_watch, default_status="watchlist")
        for item in watch_items:
            all_items[item.id] = item
        print(f"  ↳ Loaded {len(watch_items)} watchlist items.")

    # Parse ratings second
    if ratings_path:
        p_rate = Path(ratings_path)
        if not p_rate.exists():
            raise FileNotFoundError(f"Ratings file not found: {ratings_path}")
        print(f"⭐ Reading IMDb Ratings CSV: {p_rate.name}...")
        df_rate = pd.read_csv(p_rate, dtype=str)
        rate_items = parse_imdb_dataframe(df_rate, default_status="watched")
        for item in rate_items:
            all_items[item.id] = item
        print(f"  ↳ Loaded {len(rate_items)} rated items.")

    media_list = list(all_items.values())
    total = len(media_list)
    print(f"✅ Total unique media items to upsert: {total}")

    if dry_run:
        print(f"🔍 [DRY RUN] Would write {total} media items to Firestore 'media' collection.")
        if media_list:
            sample = media_list[0].to_firestore_dict()
            print(f"Sample media record:\n{sample}")
        return total

    client = get_db()
    media_ref = client.collection("media")

    written = 0
    current_batch = client.batch()
    batch_count = 0

    for item in media_list:
        doc_ref = media_ref.document(item.id)
        current_batch.set(doc_ref, item.to_firestore_dict(), merge=True)
        batch_count += 1

        if batch_count >= BATCH_SIZE:
            current_batch.commit()
            written += batch_count
            print(f"  ↳ Committed batch of {batch_count} records ({written}/{total})...")
            current_batch = client.batch()
            batch_count = 0

    if batch_count > 0:
        current_batch.commit()
        written += batch_count
        print(f"  ↳ Committed final batch of {batch_count} records ({written}/{total}).")

    print(f"🎉 Complete! Successfully upserted {written} media items into Firestore collection 'media'.")
    return written


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
