"""
Unit tests for models and CSV parsing logic in Curator MCP.
Can be executed without live Firebase credentials.
"""

import unittest
from pathlib import Path
import pandas as pd

from models import BookModel, MediaModel
from importers.goodreads_importer import (
    clean_book_id,
    parse_date_read,
    parse_goodreads_dataframe,
)
from importers.imdb_importer import (
    clean_list_field,
    parse_imdb_dataframe,
)


class TestBookModel(unittest.TestCase):
    def test_book_model_valid(self):
        book = BookModel(
            id="12345",
            title="Dune",
            author="Frank Herbert",
            user_rating=5,
            avg_rating=4.25,
            shelf="read",
            notes_and_reviews="Classic sci-fi",
            date_read="2023-01-01"
        )
        data = book.to_firestore_dict()
        self.assertEqual(data["id"], "12345")
        self.assertEqual(data["title"], "Dune")
        self.assertEqual(data["user_rating"], 5)
        self.assertEqual(data["shelf"], "read")
        self.assertIn("updated_at", data)

    def test_book_shelf_normalization(self):
        b1 = BookModel(id="1", title="A", author="B", shelf="currently-reading")
        self.assertEqual(b1.shelf, "currently-reading")

        b2 = BookModel(id="2", title="A", author="B", shelf="to-read")
        self.assertEqual(b2.shelf, "to-read")

        b3 = BookModel(id="3", title="A", author="B", shelf="current")
        self.assertEqual(b3.shelf, "currently-reading")


class TestMediaModel(unittest.TestCase):
    def test_media_model_valid(self):
        media = MediaModel(
            id="tt0111161",
            title="The Shawshank Redemption",
            media_type="movie",
            user_rating=10,
            imdb_rating=9.3,
            year=1994,
            genres=["Drama"],
            directors=["Frank Darabont"],
            status="watched"
        )
        data = media.to_firestore_dict()
        self.assertEqual(data["id"], "tt0111161")
        self.assertEqual(data["status"], "watched")
        self.assertEqual(data["genres"], ["Drama"])
        self.assertEqual(data["directors"], ["Frank Darabont"])

    def test_watchlist_nullable_rating(self):
        media = MediaModel(
            id="tt15239678",
            title="Dune: Part Two",
            media_type="movie",
            user_rating=None,
            status="watchlist"
        )
        data = media.to_firestore_dict()
        self.assertIsNone(data["user_rating"])
        self.assertEqual(data["status"], "watchlist")


class TestImporters(unittest.TestCase):
    def test_clean_book_id(self):
        self.assertEqual(clean_book_id('="12345"'), "12345")
        self.assertEqual(clean_book_id('58065033'), "58065033")
        self.assertEqual(clean_book_id('123.0'), "123")

    def test_parse_date_read(self):
        self.assertEqual(parse_date_read("2023/04/15"), "2023-04-15")
        self.assertEqual(parse_date_read("2023-04-15"), "2023-04-15")
        self.assertIsNone(parse_date_read(""))
        self.assertIsNone(parse_date_read(None))

    def test_clean_list_field(self):
        self.assertEqual(clean_list_field("Action, Adventure, Sci-Fi"), ["Action", "Adventure", "Sci-Fi"])
        self.assertEqual(clean_list_field("Drama"), ["Drama"])
        self.assertEqual(clean_list_field(""), [])
        self.assertEqual(clean_list_field(None), [])

    def test_goodreads_sample_csv_parsing(self):
        sample_path = Path(__file__).resolve().parent.parent / "sample_data" / "goodreads_sample.csv"
        self.assertTrue(sample_path.exists())
        df = pd.read_csv(sample_path, dtype=str)
        books = parse_goodreads_dataframe(df)
        self.assertEqual(len(books), 6)
        titles = [b.title for b in books]
        self.assertIn("Project Hail Mary", titles)
        self.assertIn("The Dispossessed", titles)
        self.assertEqual(books[0].user_rating, 5)

    def test_imdb_sample_csv_parsing(self):
        sample_dir = Path(__file__).resolve().parent.parent / "sample_data"
        p_ratings = sample_dir / "imdb_ratings_sample.csv"
        p_watchlist = sample_dir / "imdb_watchlist_sample.csv"
        self.assertTrue(p_ratings.exists())
        self.assertTrue(p_watchlist.exists())

        df_ratings = pd.read_csv(p_ratings, dtype=str)
        rated_items = parse_imdb_dataframe(df_ratings, default_status="watched")
        self.assertEqual(len(rated_items), 6)
        self.assertEqual(rated_items[0].status, "watched")
        self.assertEqual(rated_items[0].user_rating, 10)

        df_watchlist = pd.read_csv(p_watchlist, dtype=str)
        watchlist_items = parse_imdb_dataframe(df_watchlist, default_status="watchlist")
        self.assertEqual(len(watchlist_items), 5)
        self.assertEqual(watchlist_items[0].status, "watchlist")
        self.assertIsNone(watchlist_items[0].user_rating)


if __name__ == "__main__":
    unittest.main()
