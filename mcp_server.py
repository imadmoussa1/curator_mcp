"""
FastMCP Server for Curator MCP (Personal AI Curator & Entertainment Vault).

Senior Architecture Presentation Layer:
Exposes tools for Gemini / Claude to manage:
1. Books (Read, Currently-Reading, To-Read) & Online Discovery (Google Books / Open Library)
2. Media (Watched, Watchlist) & Online Discovery (TMDB)
3. Memorable Quotes & Mental Models (Books & Movie/TV quotes, reflections)
4. Podcasts (Queue, Listened, Guest tracking, Key Takeaways, Online Search)
5. Taste Profile Aggregation & Smart AI Recommendations

All core domain logic is decoupled into services/ and repositories/.
"""

from typing import Optional, List, Dict, Any
from fastmcp import FastMCP

from services import (
    BookService,
    MediaService,
    QuoteService,
    PodcastService,
    RecommendationService,
    BookMetadataClient,
    TMDBClient,
    ApplePodcastsClient,
)

# Initialize FastMCP Server
mcp = FastMCP("Curator-MCP")

# Dependency Injection & Service Initialization
book_service = BookService()
media_service = MediaService()
quote_service = QuoteService()
podcast_service = PodcastService()

books_client = BookMetadataClient()
tmdb_client = TMDBClient()
podcast_client = ApplePodcastsClient()

recommendation_service = RecommendationService(
    book_service=book_service,
    media_service=media_service,
    books_client=books_client,
    tmdb_client=tmdb_client,
    quote_service=quote_service,
    podcast_service=podcast_service,
)


# ============================================================================
# 1. TASTE PROFILE & HIGH-LEVEL METRICS
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
    return recommendation_service.get_taste_profile()


@mcp.tool()
def get_entertainment_stats() -> Dict[str, Any]:
    """
    Get macro metrics across all collections: Books, Movies/Series, Quotes, and Podcasts.
    Returns counts, shelf breakdowns, and average ratings.
    """
    return {
        "books": book_service.get_stats(),
        "media": media_service.get_stats(),
        "quotes": {"total": len(quote_service.stream_all())},
        "podcasts": podcast_service.get_stats(),
    }


@mcp.tool()
def get_smart_recommendations(category: str = "all", limit: int = 5) -> Dict[str, Any]:
    """
    Generate fresh, intelligent recommendations by taking the user's top-rated items from Firestore,
    querying external APIs for similar items, and automatically filtering out any books or media
    the user has already read, watched, or already has on their queues.
    Args:
        category: 'books', 'movies', 'tv', or 'all'
        limit: Max recommendations per category
    """
    return recommendation_service.get_smart_recommendations(category=category, limit=limit)


@mcp.tool()
def generate_cultural_wrapped(year: Optional[int] = None) -> Dict[str, Any]:
    """
    Generate an all-in-one 'Curator Wrapped' annual retrospective summarizing the user's intellectual
    and entertainment year across Books, Movies/Series, Podcasts, and Quotes.
    Includes total counts, average ratings, top directors/authors, masterpieces, and a dynamic
    'Cultural Archetype' persona (e.g. 'The Cybernetic Stoic', 'The Inquisitive Realist').
    Args:
        year: Target year (e.g. 2026). If omitted, analyzes all-time or latest activity.
    """
    return recommendation_service.generate_cultural_wrapped(year=year)


# ============================================================================
# 2. BOOKS MANAGEMENT & DISCOVERY
# ============================================================================

@mcp.tool()
def search_books(query: str = "", shelf: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search books in Firestore library by title or author keywords with optional shelf filter
    ('read', 'currently-reading', 'to-read').
    """
    return book_service.search(query=query, shelf=shelf, limit=limit)


@mcp.tool()
def get_recently_read_books(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieve the most recently finished and rated books, sorted chronologically by date read descending.
    Gemini / Claude should call this when the user asks:
    - 'What was the last book I read and rated?'
    - 'What did I read recently?'
    - 'Show my recent reading history.'
    """
    return book_service.get_recently_read(limit=limit)


@mcp.tool()
def get_reading_list(shelf: str = "to-read", limit: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieve books from user's reading queue (default 'to-read', or 'currently-reading').
    """
    return book_service.get_reading_list(shelf=shelf, limit=limit)


@mcp.tool()
def add_to_reading_list(
    title: str,
    author: str,
    book_id: Optional[str] = None,
    notes: Optional[str] = ""
) -> Dict[str, Any]:
    """
    Add a new book recommendation to the user's 'to-read' shelf.
    """
    return book_service.add_to_reading_list(title=title, author=author, book_id=book_id, notes=notes)


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
    Log a book the user has read, with user rating (0-5), review notes, and completion date.
    """
    return book_service.log_read(
        title=title,
        author=author,
        user_rating=user_rating,
        book_id=book_id,
        notes=notes,
        date_read=date_read,
    )


@mcp.tool()
def get_book_details(book_id: str) -> Dict[str, Any]:
    """
    Retrieve full details of a specific book by its Goodreads ID.
    """
    doc = book_service.get(book_id.strip())
    if not doc:
        return {"status": "error", "message": f"Book with ID '{book_id}' not found."}
    return {"status": "success", "book": doc}


@mcp.tool()
def lookup_book_online(title: str, author: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search Google Books API (with Open Library automatic fallback) for rich metadata
    (full synopsis, publisher, categories, page count, cover image, and average rating).
    """
    return books_client.search(query=title, author=author, limit=5)


@mcp.tool()
def find_similar_books_online(title: str, author: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """
    Find books similar to a given title by querying Google Books / Open Library for the seed
    book's themes, categories, and author relationships.
    """
    return books_client.find_similar(title=title, author=author, limit=limit)


# ============================================================================
# 3. MEDIA (MOVIES & TV SERIES) MANAGEMENT & DISCOVERY
# ============================================================================

@mcp.tool()
def search_media(
    query: str = "",
    media_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search movies and TV shows in Firestore library by title or director keywords.
    """
    return media_service.search(query=query, media_type=media_type, status=status, limit=limit)


@mcp.tool()
def get_recently_watched_media(limit: int = 10, media_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve the most recently watched and rated movies or TV series, sorted chronologically by rating date descending.
    Gemini / Claude should call this when the user asks:
    - 'What was the last thing I watched and rated?'
    - 'What movies did I watch recently?'
    - 'Show my recent viewing history.'
    """
    return media_service.get_recently_watched(limit=limit, media_type=media_type)


@mcp.tool()
def get_watchlist(
    media_type: Optional[str] = None,
    genre: Optional[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Retrieve movies or TV series currently on user's watchlist with optional genre or media_type filter.
    """
    return media_service.get_watchlist(media_type=media_type, genre=genre, limit=limit)


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
    Add a movie or series to user's watchlist.
    """
    return media_service.add_to_watchlist(
        title=title,
        media_type=media_type,
        media_id=media_id,
        year=year,
        genres=genres,
        directors=directors,
        imdb_rating=imdb_rating,
        notes=notes,
    )


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
    Log a movie or TV show the user watched with rating (1-10) and notes.
    """
    return media_service.log_watched(
        title=title,
        media_type=media_type,
        user_rating=user_rating,
        media_id=media_id,
        year=year,
        genres=genres,
        directors=directors,
        notes=notes,
    )


@mcp.tool()
def get_media_details(media_id: str) -> Dict[str, Any]:
    """
    Retrieve full details of a specific movie or show by its IMDb Const ID.
    """
    doc = media_service.get(media_id.strip())
    if not doc:
        return {"status": "error", "message": f"Media with ID '{media_id}' not found."}
    return {"status": "success", "media": doc}


@mcp.tool()
def lookup_media_online(title: str, media_type: str = "movie", year: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Search TMDB (The Movie Database) for a movie or TV show to get synopsis overview,
    poster URL, vote average, release date, and genres.
    Requires TMDB_API_KEY in .env.
    """
    return tmdb_client.search(title=title, media_type=media_type, year=year)


@mcp.tool()
def find_similar_media_online(title: str, media_type: str = "movie", limit: int = 5) -> Dict[str, Any]:
    """
    Use TMDB's recommendation algorithm to find movies or TV series similar to a title.
    Requires TMDB_API_KEY in .env.
    """
    return tmdb_client.find_similar(title=title, media_type=media_type, limit=limit)


@mcp.tool()
def get_streaming_providers(title: str, media_type: str = "movie", country: str = "US") -> Dict[str, Any]:
    """
    Check where a movie or TV show is currently streaming (Netflix, HBO Max, Prime, Apple TV+, etc.),
    available to rent, or buy via TMDB / JustWatch.
    Args:
        title: Movie or series title
        media_type: 'movie' or 'tv'
        country: ISO country code (default 'US', also 'GB', 'CA', 'AU', etc.)
    """
    return tmdb_client.get_watch_providers(title=title, media_type=media_type, country=country)


@mcp.tool()
def curate_for_tonight(
    max_runtime_mins: Optional[int] = None,
    genre: Optional[str] = None,
    min_imdb_rating: Optional[float] = None,
    media_type: Optional[str] = "movie",
    count: int = 3
) -> Dict[str, Any]:
    """
    Smart evening curation engine. Filters your watchlist by your available time (runtime in minutes),
    mood (genre like 'Sci-Fi', 'Thriller', 'Comedy'), and minimum IMDb rating.
    Gemini / Claude should call this when the user asks:
    - 'I have 90 minutes tonight, what should I watch from my watchlist?'
    - 'Pick a great comedy under 100 minutes from my watchlist.'
    - 'What's a high-rated thriller to watch tonight?'
    """
    return media_service.curate_for_tonight(
        max_runtime_mins=max_runtime_mins,
        genre=genre,
        min_imdb_rating=min_imdb_rating,
        media_type=media_type,
        count=count,
    )


# ============================================================================
# 4. MEMORABLE QUOTES & MENTAL MODELS
# ============================================================================

@mcp.tool()
def add_quote(
    quote_text: str,
    source_title: str,
    source_type: str = "book",
    speaker_or_author: Optional[str] = "",
    theme_tags: Optional[List[str]] = None,
    notes: Optional[str] = "",
    favorite: bool = False
) -> Dict[str, Any]:
    """
    Save a memorable quote or mental model from a book, movie, or TV show.
    """
    return quote_service.add(
        quote_text=quote_text,
        source_title=source_title,
        source_type=source_type,
        speaker_or_author=speaker_or_author,
        theme_tags=theme_tags,
        notes=notes,
        favorite=favorite,
    )


@mcp.tool()
def get_random_quote(theme: Optional[str] = None, source_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve a random memorable quote for reflection, inspiration, or decision-making.
    Optionally filter by theme (e.g. 'discipline', 'stoicism') or source type ('book', 'media').
    """
    return quote_service.get_random(theme=theme, source_type=source_type)


@mcp.tool()
def search_quotes(
    query: str,
    theme: Optional[str] = None,
    source_title: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search your saved quotes by keyword in the quote text, author/speaker, theme tags, or source title.
    """
    return quote_service.search(query=query, theme=theme, source_title=source_title, limit=limit)


@mcp.tool()
def list_favorite_quotes(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieve all quotes marked as favorite.
    """
    return quote_service.list_favorites(limit=limit)


# ============================================================================
# 5. PODCAST TRACKING & EPISODES
# ============================================================================

@mcp.tool()
def add_to_podcast_queue(
    podcast_name: str,
    episode_title: str,
    guest: Optional[str] = None,
    topics: Optional[List[str]] = None,
    episode_url: Optional[str] = None,
    duration_mins: Optional[int] = None
) -> Dict[str, Any]:
    """
    Add an episode to your podcast queue to listen to later.
    """
    return podcast_service.add_to_queue(
        podcast_name=podcast_name,
        episode_title=episode_title,
        guest=guest,
        topics=topics,
        episode_url=episode_url,
        duration_mins=duration_mins,
    )


@mcp.tool()
def log_listened_podcast(
    podcast_name: str,
    episode_title: str,
    user_rating: Optional[int] = None,
    guest: Optional[str] = None,
    key_takeaways: Optional[str] = "",
    topics: Optional[List[str]] = None,
    date_listened: Optional[str] = None
) -> Dict[str, Any]:
    """
    Log a podcast episode you listened to, recording key takeaways, guest, topics, and rating (1-10).
    """
    return podcast_service.log_listened(
        podcast_name=podcast_name,
        episode_title=episode_title,
        user_rating=user_rating,
        guest=guest,
        key_takeaways=key_takeaways,
        topics=topics,
        date_listened=date_listened,
    )


@mcp.tool()
def get_podcast_queue(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieve episodes currently in your podcast listening queue.
    """
    return podcast_service.get_queue(limit=limit)


@mcp.tool()
def search_podcasts(
    query: str,
    guest: Optional[str] = None,
    topic: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search your podcast database by show name, episode title, guest name, or topic.
    """
    return podcast_service.search(query=query, guest=guest, topic=topic, limit=limit)


@mcp.tool()
def lookup_podcast_online(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search for podcast shows online via Apple Podcasts API.
    Returns show name, artist/host, genres, episode count, artwork URL, and feed URL.
    Works free with zero API key required.
    """
    return podcast_client.search(show_name=query, limit=limit)


# ============================================================================
# SERVER RUNNER
# ============================================================================

if __name__ == "__main__":
    mcp.run()
