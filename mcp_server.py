"""
FastMCP Server for life_os_mcp (Personal Entertainment OS).
Exposes tools for Gemini to query reading/watching history, manage watchlists and reading lists,
log newly watched/read content, and analyze taste profiles to provide hyper-personalized recommendations.
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from collections import Counter

from fastmcp import FastMCP
from config import get_db
from models import BookModel, MediaModel

# Initialize FastMCP Server
mcp = FastMCP("Personal-Entertainment-OS")


def _generate_id(prefix: str, text: str) -> str:
    """Generates a clean identifier if none is provided."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    short_uuid = uuid.uuid4().hex[:6]
    return f"{prefix}_{slug[:20]}_{short_uuid}"


# ============================================================================
# 1. TASTE PROFILE & STATS (Designed for Gemini Recommendation Engines)
# ============================================================================

@mcp.tool()
def get_user_taste_profile() -> Dict[str, Any]:
    """
    Retrieve an aggregated taste profile of the user based on their highly rated books and media.
    Gemini should use this tool when generating personalized entertainment recommendations.
    Returns:
        Favorite genres, top directors, top authors, highest rated books (4-5 stars),
        and highest rated movies/series (8-10 stars).
    """
    db = get_db()

    # Query highly rated books (user_rating >= 4)
    books_ref = db.collection("books")
    rated_books_query = books_ref.where("user_rating", ">=", 4).stream()

    top_books = []
    author_counts = Counter()
    for doc in rated_books_query:
        b = doc.to_dict()
        top_books.append({
            "title": b.get("title"),
            "author": b.get("author"),
            "user_rating": b.get("user_rating"),
            "notes": b.get("notes_and_reviews") or ""
        })
        if b.get("author"):
            author_counts[b["author"]] += 1

    # Query highly rated media (user_rating >= 8)
    media_ref = db.collection("media")
    rated_media_query = media_ref.where("user_rating", ">=", 8).stream()

    top_media = []
    genre_counts = Counter()
    director_counts = Counter()
    for doc in rated_media_query:
        m = doc.to_dict()
        top_media.append({
            "title": m.get("title"),
            "media_type": m.get("media_type"),
            "user_rating": m.get("user_rating"),
            "imdb_rating": m.get("imdb_rating"),
            "genres": m.get("genres", []),
            "directors": m.get("directors", [])
        })
        for g in m.get("genres", []):
            genre_counts[g] += 1
        for d in m.get("directors", []):
            director_counts[d] += 1

    return {
        "status": "success",
        "taste_summary": {
            "top_genres": [g for g, _ in genre_counts.most_common(5)],
            "top_directors": [d for d, _ in director_counts.most_common(5)],
            "top_authors": [a for a, _ in author_counts.most_common(5)],
        },
        "favorite_books_sample": top_books[:10],
        "favorite_media_sample": top_media[:10],
        "total_highly_rated_books": len(top_books),
        "total_highly_rated_media": len(top_media),
    }


@mcp.tool()
def get_entertainment_stats() -> Dict[str, Any]:
    """
    Get high-level summary metrics across the user's entertainment database.
    Shows total read books, currently reading, to-read queue, watched media vs watchlist.
    """
    db = get_db()

    # Books breakdown
    books_ref = db.collection("books").stream()
    book_shelves = Counter()
    book_ratings = []
    total_books = 0

    for doc in books_ref:
        total_books += 1
        b = doc.to_dict()
        shelf = b.get("shelf", "unknown")
        book_shelves[shelf] += 1
        r = b.get("user_rating")
        if r and r > 0:
            book_ratings.append(r)

    # Media breakdown
    media_ref = db.collection("media").stream()
    media_status = Counter()
    media_types = Counter()
    media_ratings = []
    total_media = 0

    for doc in media_ref:
        total_media += 1
        m = doc.to_dict()
        status = m.get("status", "unknown")
        media_status[status] += 1
        m_type = m.get("media_type", "movie")
        media_types[m_type] += 1
        r = m.get("user_rating")
        if r and r > 0:
            media_ratings.append(r)

    avg_book_rating = round(sum(book_ratings) / len(book_ratings), 2) if book_ratings else None
    avg_media_rating = round(sum(media_ratings) / len(media_ratings), 2) if media_ratings else None

    return {
        "books": {
            "total": total_books,
            "read": book_shelves.get("read", 0),
            "currently_reading": book_shelves.get("currently-reading", 0),
            "to_read": book_shelves.get("to-read", 0),
            "avg_user_rating": avg_book_rating,
        },
        "media": {
            "total": total_media,
            "watched": media_status.get("watched", 0),
            "watchlist": media_status.get("watchlist", 0),
            "types": dict(media_types),
            "avg_user_rating": avg_media_rating,
        }
    }


# ============================================================================
# 2. READING LIST & WATCHLIST (What I want to read or watch)
# ============================================================================

@mcp.tool()
def get_reading_list(shelf: str = "to-read", limit: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieve books from the user's reading queue (default 'to-read', or 'currently-reading').
    Args:
        shelf: 'to-read' or 'currently-reading'
        limit: Maximum number of books to return (default: 20)
    """
    db = get_db()
    docs = db.collection("books").where("shelf", "==", shelf.strip().lower()).limit(limit).stream()
    results = []
    for doc in docs:
        b = doc.to_dict()
        results.append({
            "id": doc.id,
            "title": b.get("title"),
            "author": b.get("author"),
            "avg_rating": b.get("avg_rating"),
            "shelf": b.get("shelf"),
            "notes": b.get("notes_and_reviews")
        })
    return results


@mcp.tool()
def get_watchlist(media_type: Optional[str] = None, genre: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieve movies or TV series currently on the user's watchlist (items they want to watch).
    Args:
        media_type: Optional filter by type (e.g. 'movie', 'tvSeries', 'tvMiniSeries')
        genre: Optional filter by genre (e.g. 'Sci-Fi', 'Drama', 'Comedy')
        limit: Maximum items to return (default: 20)
    """
    db = get_db()
    query = db.collection("media").where("status", "==", "watchlist")
    if media_type:
        query = query.where("media_type", "==", media_type)

    docs = query.limit(limit * 2 if genre else limit).stream()
    results = []
    for doc in docs:
        m = doc.to_dict()
        genres = m.get("genres", [])
        if genre and not any(g.lower() == genre.lower() for g in genres):
            continue
        results.append({
            "id": doc.id,
            "title": m.get("title"),
            "media_type": m.get("media_type"),
            "year": m.get("year"),
            "imdb_rating": m.get("imdb_rating"),
            "genres": genres,
            "directors": m.get("directors", []),
            "notes": m.get("notes")
        })
        if len(results) >= limit:
            break
    return results


@mcp.tool()
def add_to_reading_list(title: str, author: str, book_id: Optional[str] = None, notes: Optional[str] = "") -> Dict[str, Any]:
    """
    Add a new book recommendation to the user's 'to-read' shelf.
    Gemini should use this when the user says: 'Add [Book] to my reading list' or agrees to a recommendation.
    """
    db = get_db()
    doc_id = book_id.strip() if book_id else _generate_id("gr", f"{title}_{author}")
    book = BookModel(
        id=doc_id,
        title=title.strip(),
        author=author.strip(),
        shelf="to-read",
        notes_and_reviews=notes or "",
        updated_at=datetime.now(timezone.utc)
    )
    db.collection("books").document(doc_id).set(book.to_firestore_dict(), merge=True)
    return {
        "status": "success",
        "message": f"Added '{title}' by {author} to reading list.",
        "book": book.to_firestore_dict()
    }


@mcp.tool()
def add_to_watchlist(
    title: str,
    media_type: str = "movie",
    media_id: Optional[str] = None,
    year: Optional[int] = None,
    genres: Optional[List[str]] = None,
    directors: Optional[List[str]] = None,
    imdb_rating: Optional[float] = None,
    notes: Optional[str] = ""
) -> Dict[str, Any]:
    """
    Add a movie or series to the user's watchlist (what they want to watch).
    Gemini should call this when the user wants to bookmark a recommended movie or TV show.
    """
    db = get_db()
    doc_id = media_id.strip() if media_id else _generate_id("tt", title)
    media = MediaModel(
        id=doc_id,
        title=title.strip(),
        media_type=media_type.strip(),
        status="watchlist",
        year=year,
        genres=genres or [],
        directors=directors or [],
        imdb_rating=imdb_rating,
        notes=notes or "",
        updated_at=datetime.now(timezone.utc)
    )
    db.collection("media").document(doc_id).set(media.to_firestore_dict(), merge=True)
    return {
        "status": "success",
        "message": f"Added '{title}' to watchlist.",
        "media": media.to_firestore_dict()
    }


# ============================================================================
# 3. LOGGING CONSUMED ITEMS (What I watched or read)
# ============================================================================

@mcp.tool()
def log_read_book(
    title: str,
    author: str,
    user_rating: int,
    book_id: Optional[str] = None,
    notes: Optional[str] = "",
    date_read: Optional[str] = None
) -> Dict[str, Any]:
    """
    Log a book that the user has read, recording user rating (0-5) and notes.
    Gemini should call this when the user says: 'I just finished reading [Book] and give it 5 stars'.
    """
    db = get_db()
    doc_id = book_id.strip() if book_id else _generate_id("gr", f"{title}_{author}")
    if not date_read:
        date_read = datetime.now().strftime("%Y-%m-%d")

    book = BookModel(
        id=doc_id,
        title=title.strip(),
        author=author.strip(),
        user_rating=max(0, min(5, user_rating)),
        shelf="read",
        notes_and_reviews=notes or "",
        date_read=date_read,
        updated_at=datetime.now(timezone.utc)
    )
    db.collection("books").document(doc_id).set(book.to_firestore_dict(), merge=True)
    return {
        "status": "success",
        "message": f"Logged '{title}' by {author} as read with rating {user_rating}/5.",
        "book": book.to_firestore_dict()
    }


@mcp.tool()
def log_watched_media(
    title: str,
    media_type: str = "movie",
    user_rating: Optional[int] = None,
    media_id: Optional[str] = None,
    year: Optional[int] = None,
    genres: Optional[List[str]] = None,
    directors: Optional[List[str]] = None,
    notes: Optional[str] = ""
) -> Dict[str, Any]:
    """
    Log a movie or TV show episode/season that the user watched.
    Gemini should call this when the user says: 'I watched Inception last night, give it a 9/10'.
    """
    db = get_db()
    doc_id = media_id.strip() if media_id else _generate_id("tt", title)
    rating = max(1, min(10, user_rating)) if user_rating is not None else None

    media = MediaModel(
        id=doc_id,
        title=title.strip(),
        media_type=media_type.strip(),
        user_rating=rating,
        status="watched",
        year=year,
        genres=genres or [],
        directors=directors or [],
        notes=notes or "",
        updated_at=datetime.now(timezone.utc)
    )
    db.collection("media").document(doc_id).set(media.to_firestore_dict(), merge=True)
    return {
        "status": "success",
        "message": f"Logged '{title}' ({media_type}) as watched" + (f" with rating {rating}/10." if rating else "."),
        "media": media.to_firestore_dict()
    }


# ============================================================================
# 4. SEARCH & DETAILS
# ============================================================================

@mcp.tool()
def search_books(query: str, shelf: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search books in Firestore by title or author keywords.
    Args:
        query: Search term (e.g. 'Dune', 'Brandon Sanderson')
        shelf: Optional shelf filter ('read', 'currently-reading', 'to-read')
        limit: Max results (default: 10)
    """
    db = get_db()
    col_ref = db.collection("books")
    if shelf:
        col_ref = col_ref.where("shelf", "==", shelf.strip().lower())

    # Stream and match locally for keyword flexibility
    q_norm = query.strip().lower()
    matches = []
    for doc in col_ref.stream():
        b = doc.to_dict()
        title = (b.get("title") or "").lower()
        author = (b.get("author") or "").lower()
        if q_norm in title or q_norm in author:
            matches.append({
                "id": doc.id,
                "title": b.get("title"),
                "author": b.get("author"),
                "user_rating": b.get("user_rating"),
                "avg_rating": b.get("avg_rating"),
                "shelf": b.get("shelf"),
                "notes": b.get("notes_and_reviews")
            })
            if len(matches) >= limit:
                break
    return matches


@mcp.tool()
def search_media(
    query: str,
    media_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search movies and TV shows in Firestore by title or director.
    Args:
        query: Search term (e.g. 'Nolan', 'Interstellar')
        media_type: Optional filter ('movie', 'tvSeries', etc.)
        status: Optional filter ('watched', 'watchlist')
        limit: Max results (default: 10)
    """
    db = get_db()
    col_ref = db.collection("media")
    if media_type:
        col_ref = col_ref.where("media_type", "==", media_type)
    if status:
        col_ref = col_ref.where("status", "==", status)

    q_norm = query.strip().lower()
    matches = []
    for doc in col_ref.stream():
        m = doc.to_dict()
        title = (m.get("title") or "").lower()
        directors = [d.lower() for d in m.get("directors", [])]
        if q_norm in title or any(q_norm in d for d in directors):
            matches.append({
                "id": doc.id,
                "title": m.get("title"),
                "media_type": m.get("media_type"),
                "year": m.get("year"),
                "user_rating": m.get("user_rating"),
                "imdb_rating": m.get("imdb_rating"),
                "status": m.get("status"),
                "genres": m.get("genres", []),
                "directors": m.get("directors", [])
            })
            if len(matches) >= limit:
                break
    return matches


@mcp.tool()
def get_book_details(book_id: str) -> Dict[str, Any]:
    """Retrieve full details of a specific book by its Goodreads ID."""
    db = get_db()
    doc = db.collection("books").document(book_id.strip()).get()
    if not doc.exists:
        return {"status": "error", "message": f"Book with ID '{book_id}' not found."}
    return {"status": "success", "book": doc.to_dict()}


@mcp.tool()
def get_media_details(media_id: str) -> Dict[str, Any]:
    """Retrieve full details of a specific movie or show by its IMDb Const ID."""
    db = get_db()
    doc = db.collection("media").document(media_id.strip()).get()
    if not doc.exists:
        return {"status": "error", "message": f"Media with ID '{media_id}' not found."}
    return {"status": "success", "media": doc.to_dict()}


if __name__ == "__main__":
    # Runs standard FastMCP server over stdio
    mcp.run()
