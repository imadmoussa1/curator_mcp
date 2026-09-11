"""
FastMCP Server for Curator MCP (Personal AI Curator & Entertainment Vault).

Senior Architecture Presentation Layer:
Exposes tools for Claude Desktop, Google Antigravity, and Gemini agents to interact with:
1. Books (Read, Currently-Reading, To-Read) & Online Discovery (Google Books / Open Library)
2. Media (Watched, Watchlist) & Online Discovery (TMDB)
3. Memorable Quotes & Mental Models (Books, Cinema, Reflections)
4. Podcasts (Queue, Listened, Guest Tracking, Key Takeaways, Directory Search)
5. Taste Profile Aggregation & Smart AI Recommendations
6. Sensory & Connoisseur Vault (Whiskey, Wine, Coffee, Tea, Gin, Chocolate, Fragrance, Watches)
7. Restaurants & Dining Journal (Visited, Wishlist, Michelin, City, Cuisine)
8. Multimodal Aesthetic & Sensory Pairings (Literature/Cinema with artisanal beverages)
9. Persistent Personal Memory Vault & Ambient Directives

Token Optimization Architecture:
- Decouples developer documentation from LLM prompt payload overhead.
- Supports lightweight Slim Mode (19 high-leverage tools) and Full Mode (all 50 tools).
- Minified tool descriptions injected into client schemas while preserving full PEP-257
  Google-style docstrings in source code for human engineers, IDEs, and linters.
"""

import os
import sys
import warnings
from pathlib import Path

# Suppress library deprecation warnings to prevent stderr pollution from corrupting MCP stdio JSON-RPC
warnings.filterwarnings("ignore")

# Ensure repository root is always prioritized in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from typing import Optional, List, Dict, Any, Callable
from fastmcp import FastMCP
from config import CURATOR_SLIM_MODE

from services import (
    BookService,
    MediaService,
    QuoteService,
    PodcastService,
    SensoryService,
    RestaurantService,
    MemoryService,
    RecommendationService,
    PairingService,
    BookMetadataClient,
    TMDBClient,
    ApplePodcastsClient,
    ConnoisseurCatalogClient,
)

# Token optimization flag: slim mode registers 19 core tools (~4,500 tokens), full mode registers 50 tools (~13,000 tokens)
IS_SLIM = (CURATOR_SLIM_MODE and "--full" not in sys.argv) or ("--slim" in sys.argv)

# Initialize FastMCP Server singleton
mcp = FastMCP("Curator-MCP")

# Dependency Injection & Domain Service Initialization
book_service = BookService()
media_service = MediaService()
quote_service = QuoteService()
podcast_service = PodcastService()
sensory_service = SensoryService()
restaurant_service = RestaurantService()
memory_service = MemoryService()

books_client = BookMetadataClient()
tmdb_client = TMDBClient()
podcast_client = ApplePodcastsClient()
catalog_client = ConnoisseurCatalogClient()

recommendation_service = RecommendationService(
    book_service=book_service,
    media_service=media_service,
    books_client=books_client,
    tmdb_client=tmdb_client,
    quote_service=quote_service,
    podcast_service=podcast_service,
    sensory_service=sensory_service,
    restaurant_service=restaurant_service,
    memory_service=memory_service,
)

pairing_service = PairingService(
    sensory_service=sensory_service,
    restaurant_service=restaurant_service,
)


def curator_tool(
    slim: bool = False,
    description: Optional[str] = None,
) -> Callable:
    """
    Registers an MCP tool with FastMCP adhering to clean architecture and prompt engineering best practices.

    Decouples developer documentation from LLM prompt payload overhead:
    - If `description` is provided, FastMCP registers this concise, high-signal instruction string into the
      JSON Schema sent to the LLM on every turn.
    - If `description` is omitted, FastMCP falls back to the function's `__doc__`.
    - In Slim Mode (IS_SLIM=True), only tools with `slim=True` are registered to preserve prompt budget.

    Args:
        slim: Whether this tool is registered in lightweight Slim Mode.
        description: Concise prompt-engineered description sent to the LLM client.

    Returns:
        Callable decorator registering the target function.
    """
    def decorator(fn: Callable) -> Callable:
        if not IS_SLIM or slim:
            tool_desc = description or fn.__doc__
            mcp.tool(description=tool_desc)(fn)
        return fn
    return decorator


# ============================================================================
# 0. CONTEXT RESOURCES (@mcp.resource)
# ============================================================================

@mcp.resource("curator://context/taste_profile")
def get_taste_profile_context() -> str:
    """
    Live background context resource providing Claude Desktop and agents with
    the user's taste preferences, 5-star books, 10/10 films, sensory flavor notes,
    and favorite cuisines.
    """
    profile = recommendation_service.get_taste_profile()
    sensory_profile = recommendation_service.get_sensory_taste_profile()
    dining_stats = restaurant_service.get_stats()

    summary_lines = [
        "# User Cultural & Taste Profile (Curator MCP)",
        f"**Top Genres**: {', '.join(profile.get('taste_summary', {}).get('top_genres', []))}",
        f"**Top Directors**: {', '.join(profile.get('taste_summary', {}).get('top_directors', []))}",
        f"**Top Authors**: {', '.join(profile.get('taste_summary', {}).get('top_authors', []))}",
        f"**Top Flavor & Scent Accords**: {', '.join(sensory_profile.get('top_flavor_and_scent_accords', []))}",
        f"**Favorite Dining Cuisines**: {', '.join(dining_stats.get('top_cuisines', []))}",
        f"**Favorite Dining Cities**: {', '.join(dining_stats.get('top_cities', []))}",
    ]
    return "\n".join(summary_lines)


@mcp.resource("curator://context/active_queues")
def get_active_queues_context() -> str:
    """
    Live background context resource providing agents with currently reading books,
    movie watchlist items, and podcast queue.
    """
    reading_now = book_service.get_reading_list(shelf="currently-reading", limit=5)
    to_read = book_service.get_reading_list(shelf="to-read", limit=5)
    watchlist = media_service.get_watchlist(limit=5)
    pod_queue = podcast_service.get_queue(limit=5)

    lines = ["# Active Queues & Currently Consuming (Curator MCP)"]
    if reading_now:
        lines.append(f"**Currently Reading**: {', '.join([b.get('title') for b in reading_now])}")
    if to_read:
        lines.append(f"**Up Next on Bookshelf**: {', '.join([b.get('title') for b in to_read])}")
    if watchlist:
        lines.append(f"**Movie Watchlist**: {', '.join([m.get('title') for m in watchlist])}")
    if pod_queue:
        lines.append(f"**Podcast Queue**: {', '.join([p.get('episode_title') for p in pod_queue])}")
    return "\n".join(lines)


@mcp.resource("curator://context/daily_digest")
def get_daily_digest_context() -> str:
    """
    Live background context resource providing a morning intellectual briefing:
    Quote of the Day, active reading metrics, and macro entertainment statistics.
    """
    quote = quote_service.get_random()
    stats = {
        "books": book_service.get_stats(),
        "media": media_service.get_stats(),
        "vault": sensory_service.get_stats(),
        "restaurants": restaurant_service.get_stats(),
    }
    lines = [
        "# Daily Curator Digest",
        f"**Quote of the Day**: \"{quote.get('quote_text', 'Live deliberately.')}\" — {quote.get('speaker_or_author', 'Unknown')}",
        f"**Books Tracked**: {stats['books'].get('total_books', 0)} ({stats['books'].get('read', 0)} read)",
        f"**Media Watched**: {stats['media'].get('watched', 0)} ({stats['media'].get('watchlist', 0)} in watchlist)",
        f"**Sensory Vault**: {stats['vault'].get('total_items', 0)} items",
        f"**Restaurants**: {stats['restaurants'].get('total_places', 0)} places",
    ]
    return "\n".join(lines)


@mcp.resource("curator://context/taste_dna_dossier")
def get_taste_dna_dossier() -> str:
    """
    Comprehensive Taste DNA dossier across literature, cinema, and culinary arts,
    including the user's cultural archetype analysis.
    """
    profile = recommendation_service.get_taste_profile()
    sensory = recommendation_service.get_sensory_taste_profile() if hasattr(recommendation_service, "get_sensory_taste_profile") else {}
    wrapped = recommendation_service.generate_cultural_wrapped()
    lines = [
        "# Curator MCP - User Taste DNA Dossier",
        f"**Cultural Archetype**: {wrapped.get('cultural_archetype', {}).get('title', 'The Polymath')} — {wrapped.get('cultural_archetype', {}).get('summary', '')}",
        f"**Top Authors**: {', '.join(profile.get('taste_summary', {}).get('top_authors', [])[:5])}",
        f"**Top Directors**: {', '.join(profile.get('taste_summary', {}).get('top_directors', [])[:5])}",
        f"**Top Genres**: {', '.join(profile.get('taste_summary', {}).get('top_genres', [])[:5])}",
        f"**Top Sensory Accords**: {', '.join(sensory.get('top_flavor_and_scent_accords', [])[:6])}",
    ]
    return "\n".join(lines)


@mcp.resource("curator://context/personal_memory")
def get_personal_memory_context() -> str:
    """
    Active long-term personal memories, critical directives, habits, and constraints.
    """
    return memory_service.get_personal_memory_summary()


# ============================================================================
# 0.5 INTERACTIVE PROMPTS (@mcp.prompt)
# ============================================================================

@mcp.prompt("smart_recommendation_consultation")
def smart_recommendation_consultation(domain: str = "movies", mood_or_craving: str = "") -> str:
    """
    Orchestrate an internet-powered recommendation session with Taste DNA vetting.

    Args:
        domain: Category for recommendation ('books', 'movies', 'whiskey', etc.).
        mood_or_craving: Desired atmospheric vibe or intent.
    """
    craving_str = f" for '{mood_or_craving}'" if mood_or_craving else ""
    return (
        f"The user wants a recommendation in '{domain}'{craving_str}.\n"
        "1. Call `get_agent_recommendation_brief(domain='{domain}', mood_or_intent='{mood_or_craving}')` for Taste DNA.\n"
        "2. Search the web for fresh, acclaimed, or hidden gem candidates matching their style.\n"
        "3. Call `vet_recommendation_candidate(domain='{domain}', title_or_name=...)` to check collision and affinity.\n"
        "4. Present the curated recommendation with a rationale connected to past favorites."
    )


@mcp.prompt("daily_briefing")
def daily_briefing() -> str:
    """
    Generate a morning intellectual briefing with reading status, quote of the day, and wind-down pick.
    """
    return (
        "You are the user's personal Taste & Cultural Curator. "
        "Review active queues and quote of the day. Provide a concise morning briefing: "
        "1) Thought for the Day, 2) Reading Focus, 3) Evening Wind-Down Pick."
    )


@mcp.prompt("tasting_session")
def tasting_session(category: str = "whiskey", item_name: str = "") -> str:
    """
    Interactive sensory tasting interview to evaluate and log an artisanal item.

    Args:
        category: Sensory domain ('whiskey', 'wine', 'tea', 'coffee', 'perfume').
        item_name: Specific item being tasted or sampled.
    """
    item_str = f" for '{item_name}'" if item_name else ""
    return (
        f"Conduct a Master Tasting Session in '{category}'{item_str}. "
        "Evaluate: 1) Origin/Provenance, 2) Aroma/Nose, 3) Palate/Taste, 4) Finish & Rating (1-10). "
        "Offer to log the evaluation via `log_sensory_item`."
    )


@mcp.prompt("weekend_curation")
def weekend_curation(mood: Optional[str] = None) -> str:
    """
    Curate a weekend cultural itinerary (Film pick + Beverage pairing + Book reading + Dining spot).

    Args:
        mood: Optional aesthetic or thematic mood for the weekend.
    """
    mood_str = f" with a '{mood}' aesthetic" if mood else ""
    return (
        f"Curate a complete weekend cultural itinerary{mood_str}: "
        "1) Film pick from watchlist, 2) Beverage pairing, 3) Book reading session, 4) Dining experience."
    )


# ============================================================================
# 1. TASTE PROFILE & HIGH-LEVEL RECOMMENDATIONS
# ============================================================================

@curator_tool(
    slim=True,
    description="Retrieve user taste profile including top genres, directors, authors, and highest-rated favorites."
)
def get_user_taste_profile() -> Dict[str, Any]:
    """
    Retrieve an aggregated taste profile of the user based on highly-rated books and media.

    Synthesizes user ratings (>= 8/10 for media, >= 4/5 for books) across Firestore collections
    to compute top creators, favorite genres, and sample favorites.

    Returns:
        Dictionary containing taste summary, favorite samples, and totals.
    """
    return recommendation_service.get_taste_profile()


@curator_tool(
    slim=True,
    description="Get macro statistics across books, movies, podcasts, quotes, sensory vault, and restaurants."
)
def get_entertainment_stats() -> Dict[str, Any]:
    """
    Compute and return macro statistics across all cataloged entertainment and lifestyle collections.

    Returns:
        Dictionary containing summary metrics for books, media, quotes, podcasts, sensory items,
        dining venues, and stored personal memories.
    """
    return {
        "books": book_service.get_stats(),
        "media": media_service.get_stats(),
        "quotes": {"total": len(quote_service.stream_all())},
        "podcasts": podcast_service.get_stats(),
        "sensory_vault": sensory_service.get_stats(),
        "restaurants": restaurant_service.get_stats(),
        "memories": memory_service.get_stats(),
    }


@curator_tool(
    slim=True,
    description="Retrieve Taste DNA, anchor favorites, avoidances, and web search queries for a domain."
)
def get_agent_recommendation_brief(
    domain: str,
    mood_or_intent: Optional[str] = None,
    target_location: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a comprehensive recommendation brief for an autonomous AI curator agent.

    Provides the user's Taste DNA (top anchors, creator affinities, sensory accords),
    a negative exclusion catalog to avoid items already consumed, and targeted web search
    directives for finding fresh candidates.

    Args:
        domain: Target category ('books', 'movies', 'whiskey', 'wine', 'restaurants', etc.).
        mood_or_intent: Optional atmospheric vibe or craving (e.g. 'cozy rainy night noir').
        target_location: Optional geographic context for dining and physical experiences.

    Returns:
        Dictionary containing briefing directives, taste DNA, negative exclusions, and suggested queries.
    """
    return recommendation_service.get_agent_recommendation_brief(
        domain=domain,
        mood_or_intent=mood_or_intent,
        target_location=target_location,
    )


@curator_tool(
    slim=True,
    description="Check a recommendation candidate for library collision and calculate taste affinity score."
)
def vet_recommendation_candidate(
    domain: str,
    title_or_name: str,
    maker_or_creator: Optional[str] = None,
    attributes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Vet a recommendation candidate against the user's catalog to prevent duplicates and evaluate taste fit.

    Performs fuzzy matching across existing Firestore collections and scores affinity against
    the user's top-rated creators, genres, or flavor notes.

    Args:
        domain: The entertainment domain ('books', 'movies', 'whiskey', etc.).
        title_or_name: Title of the book/movie or name of the artisanal item/venue.
        maker_or_creator: Author, director, brand, or chef (optional).
        attributes: Associated genres, flavor accords, or tags (optional).

    Returns:
        Dictionary indicating collision status, past ratings if previously logged, and affinity score.
    """
    return recommendation_service.vet_recommendation_candidate(
        domain=domain,
        title_or_name=title_or_name,
        maker_or_creator=maker_or_creator,
        attributes=attributes,
    )


@curator_tool(
    slim=False,
    description="Generate annual cultural retrospective across reading, cinema, dining, and sensory experiences."
)
def generate_cultural_wrapped(year: Optional[int] = None) -> Dict[str, Any]:
    """
    Synthesizes an all-in-one personal 'Curator Wrapped' annual retrospective.

    Aggregates books read, movies watched, podcasts consumed, memorable quotes saved,
    and sensory items experienced within the target year.

    Args:
        year: Calendar year to analyze (defaults to current year).

    Returns:
        Dictionary containing annual statistics, top-rated items, and cultural archetype analysis.
    """
    return recommendation_service.generate_cultural_wrapped(year=year)


# ============================================================================
# 1.5 UNIFIED CROSS-VAULT SEARCH (High-Leverage Tool for Low Token Usage)
# ============================================================================

@curator_tool(
    slim=True,
    description="Unified search across all collections (books, media, sensory goods, restaurants, quotes)."
)
def search_vault(
    query: str,
    domain: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Execute a unified cross-vault search across all cataloged domains.

    Designed for maximum token efficiency, this tool queries books, movies, sensory goods,
    dining venues, and quotes in a single invocation.

    Args:
        query: Search keywords matching titles, creators, tags, or tasting notes.
        domain: Optional domain filter ('books', 'media', 'movies', 'sensory', 'restaurants', 'quotes').
        limit: Maximum matches per domain. Defaults to 5.

    Returns:
        Dictionary containing grouped search matches across matching domains.
    """
    results: Dict[str, Any] = {}
    dom = (domain or "").lower().strip()

    if not dom or "book" in dom:
        b_matches = book_service.search(query=query, limit=limit)
        if b_matches:
            results["books"] = b_matches
    if not dom or "media" in dom or "movie" in dom or "tv" in dom:
        m_matches = media_service.search(query=query, limit=limit)
        if m_matches:
            results["media"] = m_matches
    if not dom or "sensory" in dom or any(k in dom for k in ("wine", "whiskey", "coffee", "tea")):
        s_matches = sensory_service.search(query=query, limit=limit)
        if s_matches:
            results["sensory"] = s_matches
    if not dom or "restaurant" in dom or "dining" in dom or "food" in dom:
        r_matches = restaurant_service.search(query=query, limit=limit)
        if r_matches:
            results["restaurants"] = r_matches
    if not dom or "quote" in dom:
        q_matches = quote_service.search(query=query, limit=limit)
        if q_matches:
            results["quotes"] = q_matches

    return {
        "status": "success",
        "query": query,
        "matches": results,
    }


# ============================================================================
# 2. BOOKS & READING QUEUES
# ============================================================================

@curator_tool(
    slim=True,
    description="Search books in Firestore by query and optional shelf ('read', 'currently-reading', 'to-read')."
)
def search_books(query: str = "", shelf: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Search books in Firestore by title or author keywords with optional shelf filter.

    Args:
        query: Keyword string to match against title or author.
        shelf: Optional shelf filter ('read', 'currently-reading', 'to-read').
        limit: Maximum number of matched records to return. Defaults to 5.

    Returns:
        List of matching book records.
    """
    return book_service.search(query=query, shelf=shelf, limit=limit)


@curator_tool(
    slim=False,
    description="Get most recently finished and rated books sorted by date read descending."
)
def get_recently_read_books(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve most recently finished and rated books, sorted by date read descending.

    Args:
        limit: Maximum number of books to return. Defaults to 5.

    Returns:
        List of finished book records with ratings and read dates.
    """
    return book_service.get_recently_read(limit=limit)


@curator_tool(
    slim=True,
    description="Get books from user's reading queue ('to-read' or 'currently-reading')."
)
def get_reading_list(shelf: str = "to-read", limit: int = 8) -> List[Dict[str, Any]]:
    """
    Retrieve books from user's reading queue ('to-read' or 'currently-reading').

    Args:
        shelf: Queue name ('to-read' or 'currently-reading'). Defaults to 'to-read'.
        limit: Maximum number of books to return. Defaults to 8.

    Returns:
        List of queued book records.
    """
    return book_service.get_reading_list(shelf=shelf, limit=limit)


@curator_tool(
    slim=False,
    description="Add a book recommendation to the user's 'to-read' shelf with deduplication."
)
def add_to_reading_list(
    title: str,
    author: str,
    book_id: Optional[str] = None,
    notes: Optional[str] = "",
) -> Dict[str, Any]:
    """
    Add a book to the 'to-read' shelf with automatic duplicate detection.

    Args:
        title: Book title.
        author: Book author.
        book_id: Optional custom book ID.
        notes: Optional initial notes or recommendation rationale.

    Returns:
        Dictionary indicating status and created/updated book record.
    """
    return book_service.add_to_reading_list(title=title, author=author, book_id=book_id, notes=notes)


@curator_tool(
    slim=True,
    description="Log a completed book with rating (0-5 stars), optional review, and date read."
)
def log_read_book(
    title: str,
    author: str,
    user_rating: int,
    book_id: Optional[str] = None,
    review: Optional[str] = "",
    private_notes: Optional[str] = "",
    notes: Optional[str] = "",
    date_read: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Log a finished book with Goodreads rating (0-5 stars), review, private notes, and date read.

    Args:
        title: Book title.
        author: Author name.
        user_rating: Star rating (0 to 5).
        book_id: Optional existing book ID.
        review: Public review or literary analysis.
        private_notes: Private reflections or takeaways.
        notes: General legacy notes.
        date_read: ISO date read (YYYY-MM-DD), defaults to today.

    Returns:
        Dictionary confirming log status and updated book record.
    """
    return book_service.log_read(
        title=title,
        author=author,
        user_rating=user_rating,
        book_id=book_id,
        notes=notes,
        review=review,
        private_notes=private_notes,
        date_read=date_read,
    )


@curator_tool(
    slim=False,
    description="Update book shelf ('read', 'currently-reading', 'to-read'), rating, review, or reading dates."
)
def update_book_status(
    title: Optional[str] = None,
    book_id: Optional[str] = None,
    shelf: str = "read",
    user_rating: Optional[int] = None,
    review: Optional[str] = None,
    private_notes: Optional[str] = None,
    date_read: Optional[str] = None,
    date_started: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update book shelf status, user rating, reviews, or active reading dates.

    Args:
        title: Book title (used if book_id is omitted).
        book_id: Specific Firestore book record ID.
        shelf: Target shelf ('read', 'currently-reading', 'to-read').
        user_rating: Updated star rating (0-5).
        review: Updated review text.
        private_notes: Updated private notes.
        date_read: Date finished (YYYY-MM-DD).
        date_started: Date commenced reading (YYYY-MM-DD).

    Returns:
        Dictionary confirming status change.
    """
    return book_service.update_status(
        book_id=book_id,
        title=title,
        shelf=shelf,
        user_rating=user_rating,
        review=review,
        private_notes=private_notes,
        date_read=date_read,
        date_started=date_started,
    )


@curator_tool(
    slim=False,
    description="Get full details, notes, and reviews for a book by ID."
)
def get_book_details(book_id: str) -> Dict[str, Any]:
    """
    Retrieve full metadata, reading dates, and personal notes for a book.

    Args:
        book_id: Unique record ID of the book in Firestore.

    Returns:
        Complete book dictionary.
    """
    return book_service.get_details(book_id=book_id)


@curator_tool(
    slim=False,
    description="Search online book metadata via Google Books and Open Library."
)
def lookup_book_online(title: str, author: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Query external bibliographical APIs (Google Books, Open Library) for metadata.

    Args:
        title: Book title keyword.
        author: Optional author name.

    Returns:
        List of metadata records with page count, publication year, categories, and synopsis.
    """
    return books_client.search(query=title, author=author)


@curator_tool(
    slim=False,
    description="Discover related books online based on themes, categories, or author."
)
def find_similar_books_online(title: str, author: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """
    Discover related books online based on shared themes, subject classifications, or author.

    Args:
        title: Seed book title.
        author: Optional author name.
        limit: Max recommendations. Defaults to 5.

    Returns:
        Dictionary containing seed metadata and list of recommendations.
    """
    return books_client.find_similar(title=title, author=author, limit=limit)


# ============================================================================
# 3. MOVIES & WATCHLIST
# ============================================================================

@curator_tool(
    slim=True,
    description="Search movies and series in library by title, director, or genre."
)
def search_media(
    query: str = "",
    media_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search movies and TV series in Firestore by title, director, or genre keywords.

    Args:
        query: Search keywords.
        media_type: Optional filter ('Movie', 'TV Series').
        status: Optional watch status ('watched', 'watchlist').
        limit: Max results to return. Defaults to 5.

    Returns:
        List of matched media records.
    """
    return media_service.search(query=query, media_type=media_type, status=status, limit=limit)


@curator_tool(
    slim=False,
    description="Get recently watched movies/series sorted by date rated descending."
)
def get_recently_watched_media(limit: int = 5, media_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieve recently watched and rated movies or series, sorted chronologically descending.

    Args:
        limit: Max results. Defaults to 5.
        media_type: Optional filter ('Movie', 'TV Series').

    Returns:
        List of watched media items with ratings.
    """
    return media_service.get_recently_watched(limit=limit, media_type=media_type)


@curator_tool(
    slim=True,
    description="Get movie and TV watchlist with optional type and genre filter."
)
def get_watchlist(
    media_type: Optional[str] = None,
    genre: Optional[str] = None,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """
    Retrieve items from the user's movie and series watchlist.

    Args:
        media_type: Optional filter ('Movie', 'TV Series').
        genre: Optional genre filter (e.g. 'Sci-Fi', 'Thriller').
        limit: Maximum results to return. Defaults to 8.

    Returns:
        List of watchlist records.
    """
    return media_service.get_watchlist(media_type=media_type, genre=genre, limit=limit)


@curator_tool(
    slim=False,
    description="Add a movie or series to watchlist with optional priority and notes."
)
def add_to_watchlist(
    title: str,
    media_type: str = "movie",
    year: Optional[int] = None,
    tmdb_id: Optional[int] = None,
    imdb_id: Optional[str] = None,
    priority: int = 3,
    notes: Optional[str] = "",
) -> Dict[str, Any]:
    """
    Add a movie or TV series to the watchlist with automatic TMDB enrichment.

    Args:
        title: Title of the film or series.
        media_type: 'movie' or 'tv'.
        year: Release year (optional).
        tmdb_id: TMDB identifier (optional).
        imdb_id: IMDb identifier (optional).
        priority: Priority from 1 (low) to 5 (must-watch).
        notes: Rationale or context for adding.

    Returns:
        Dictionary confirming status and enriched watchlist entry.
    """
    return media_service.add_to_watchlist(
        title=title,
        media_type=media_type,
        year=year,
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
        priority=priority,
        notes=notes,
    )


@curator_tool(
    slim=True,
    description="Log watched movie or episode with rating (1-10), review, and date."
)
def log_watched_media(
    title: str,
    user_rating: int,
    media_type: str = "movie",
    year: Optional[int] = None,
    tmdb_id: Optional[int] = None,
    imdb_id: Optional[str] = None,
    review: Optional[str] = "",
    date_watched: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Log a completed film or series with IMDb-scale user rating (1-10) and auto-enrichment.

    Args:
        title: Title of the media item.
        user_rating: Integer rating from 1 to 10.
        media_type: 'movie' or 'tv'.
        year: Release year.
        tmdb_id: TMDB ID (optional).
        imdb_id: IMDb ID (optional).
        review: Review notes or critical appraisal.
        date_watched: ISO date string (YYYY-MM-DD), defaults to today.

    Returns:
        Dictionary confirming log status and persisted media record.
    """
    return media_service.log_watched(
        title=title,
        user_rating=user_rating,
        media_type=media_type,
        year=year,
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
        review=review,
        date_watched=date_watched,
    )


@curator_tool(
    slim=False,
    description="Update media status ('watched', 'watchlist'), rating, or review."
)
def update_media_status(
    media_id: str,
    status: Optional[str] = None,
    user_rating: Optional[int] = None,
    review: Optional[str] = None,
    priority: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Update status, rating, priority, or reviews for an existing media item.

    Args:
        media_id: Record ID in Firestore.
        status: Updated status ('watched', 'watchlist').
        user_rating: Updated user rating (1-10).
        review: Updated review commentary.
        priority: Updated priority level (1-5).

    Returns:
        Dictionary confirming status update.
    """
    return media_service.update_status(
        media_id=media_id,
        status=status,
        user_rating=user_rating,
        review=review,
        priority=priority,
    )


@curator_tool(
    slim=False,
    description="Get full details and notes for a movie or show by ID."
)
def get_media_details(media_id: str) -> Dict[str, Any]:
    """
    Retrieve full metadata, directors, cast, genres, and notes for a movie or series.

    Args:
        media_id: Unique record ID of the media item.

    Returns:
        Complete media record dictionary.
    """
    return media_service.get_details(media_id=media_id)


@curator_tool(
    slim=False,
    description="Search TMDB for movies or TV series metadata."
)
def lookup_media_online(title: str, media_type: str = "movie", year: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Query TMDB API for live cinema and television metadata.

    Args:
        title: Title query keyword.
        media_type: 'movie' or 'tv'.
        year: Optional release year.

    Returns:
        List of matching titles with synopsis, vote average, and poster references.
    """
    return tmdb_client.search(title=title, media_type=media_type, year=year)


@curator_tool(
    slim=False,
    description="Find similar movies or TV series recommendations via TMDB."
)
def find_similar_media_online(title: str, media_type: str = "movie", limit: int = 5) -> Dict[str, Any]:
    """
    Discover similar films or series recommendations via TMDB's algorithmic relations.

    Args:
        title: Seed film or TV series title.
        media_type: 'movie' or 'tv'.
        limit: Max candidates to return. Defaults to 5.

    Returns:
        Dictionary containing seed metadata and list of recommendations.
    """
    return tmdb_client.find_similar(title=title, media_type=media_type, limit=limit)


@curator_tool(
    slim=False,
    description="Get streaming, rental, and purchase options for a title via TMDB."
)
def get_streaming_providers(title: str, media_type: str = "movie", country: str = "US") -> Dict[str, Any]:
    """
    Find live streaming providers, digital rental, and purchase availability via TMDB/JustWatch.

    Args:
        title: Movie or series title.
        media_type: 'movie' or 'tv'.
        country: ISO 3166-1 two-letter country code (default 'US').

    Returns:
        Dictionary with stream, rent, and buy provider listings.
    """
    return tmdb_client.get_watch_providers(title=title, media_type=media_type, country=country)


@curator_tool(
    slim=True,
    description="Filter watchlist by available time (minutes), genre, and IMDb rating."
)
def curate_for_tonight(
    max_runtime_mins: Optional[int] = None,
    genre: Optional[str] = None,
    min_imdb_rating: Optional[float] = None,
    media_type: Optional[str] = "movie",
    count: int = 3,
) -> Dict[str, Any]:
    """
    Smart evening curation filter for watchlist items based on available time and preferences.

    Args:
        max_runtime_mins: Maximum runtime in minutes (e.g. 120 for 2 hours).
        genre: Preferred genre filter (e.g. 'Sci-Fi', 'Comedy', 'Drama').
        min_imdb_rating: Minimum IMDb score (e.g. 7.5).
        media_type: 'movie' or 'tv'. Defaults to 'movie'.
        count: Number of curated options to present. Defaults to 3.

    Returns:
        Dictionary containing curated evening selections tailored to constraints.
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

@curator_tool(
    slim=False,
    description="Save a memorable quote or mental model with author, source, and theme tags."
)
def add_quote(
    quote_text: str,
    source_title: str,
    source_type: str = "book",
    speaker_or_author: Optional[str] = "",
    theme_tags: Optional[List[str]] = None,
    notes: Optional[str] = "",
    favorite: bool = False,
) -> Dict[str, Any]:
    """
    Save a memorable quote, philosophical reflection, or mental model to Firestore.

    Args:
        quote_text: Verbatim quote text or aphorism.
        source_title: Origin work (book, movie, essay, podcast).
        source_type: 'book', 'media', 'podcast', or 'general'.
        speaker_or_author: Author or speaker name.
        theme_tags: Conceptual or philosophical tags (e.g. ['stoicism', 'epistemology']).
        notes: Personal reflection or interpretation.
        favorite: Mark as favorite quote.

    Returns:
        Dictionary confirming creation.
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


@curator_tool(
    slim=False,
    description="Retrieve a random quote, optionally filtered by theme or source type."
)
def get_random_quote(theme: Optional[str] = None, source_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve a random quote from the collection, with optional thematic filtering.

    Args:
        theme: Optional theme tag filter (e.g. 'existentialism', 'discipline').
        source_type: Optional source filter ('book', 'media', etc.).

    Returns:
        Random quote dictionary.
    """
    return quote_service.get_random(theme=theme, source_type=source_type)


@curator_tool(
    slim=False,
    description="Search saved quotes by keyword, theme tag, or author."
)
def search_quotes(
    query: str = "",
    theme: Optional[str] = None,
    source_title: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search saved quotes by text keywords, thematic tags, or source titles.

    Args:
        query: Search keywords matching quote text or speaker.
        theme: Theme tag filter.
        source_title: Source title filter.
        limit: Max matches. Defaults to 5.

    Returns:
        List of matched quote records.
    """
    return quote_service.search(query=query, theme=theme, source_title=source_title, limit=limit)


@curator_tool(
    slim=False,
    description="Retrieve user's favorite saved quotes."
)
def list_favorite_quotes(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve quotes marked as personal favorites.

    Args:
        limit: Max quotes to return. Defaults to 5.

    Returns:
        List of favorite quote records.
    """
    return quote_service.list_favorites(limit=limit)


# ============================================================================
# 5. PODCASTS
# ============================================================================

@curator_tool(
    slim=False,
    description="Add a podcast episode to the listen queue with optional notes."
)
def add_to_podcast_queue(
    podcast_title: str,
    episode_title: str,
    feed_url: Optional[str] = None,
    notes: Optional[str] = "",
) -> Dict[str, Any]:
    """
    Add a podcast episode to the user's active listening queue.

    Args:
        podcast_title: Show/Podcast name.
        episode_title: Title of the specific episode.
        feed_url: Optional RSS or Apple Podcasts URL.
        notes: Context or recommendation reason.

    Returns:
        Confirmation dictionary.
    """
    return podcast_service.add_to_queue(
        podcast_title=podcast_title,
        episode_title=episode_title,
        feed_url=feed_url,
        notes=notes,
    )


@curator_tool(
    slim=False,
    description="Log listened podcast with rating (1-5), key takeaways, and topics."
)
def log_listened_podcast(
    podcast_title: str,
    episode_title: str,
    user_rating: int,
    key_takeaways: Optional[str] = "",
    topics: Optional[List[str]] = None,
    guests: Optional[List[str]] = None,
    date_listened: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Log a completed podcast episode with takeaways, guest tracking, and rating.

    Args:
        podcast_title: Show name.
        episode_title: Episode title.
        user_rating: Rating from 1 to 5.
        key_takeaways: Core insights or notes.
        topics: Topical tags (e.g. ['neuroscience', 'longevity']).
        guests: Names of interview guests.
        date_listened: Date completed (YYYY-MM-DD).

    Returns:
        Confirmation dictionary.
    """
    return podcast_service.log_listened(
        podcast_title=podcast_title,
        episode_title=episode_title,
        user_rating=user_rating,
        key_takeaways=key_takeaways,
        topics=topics,
        guests=guests,
        date_listened=date_listened,
    )


@curator_tool(
    slim=False,
    description="Get podcast queue."
)
def get_podcast_queue(limit: int = 8) -> List[Dict[str, Any]]:
    """
    Retrieve episodes from the user's podcast queue.

    Args:
        limit: Max episodes to return. Defaults to 8.

    Returns:
        List of queued episode dictionaries.
    """
    return podcast_service.get_queue(limit=limit)


@curator_tool(
    slim=False,
    description="Search podcast listening history by query or topic."
)
def search_podcasts(
    query: str = "",
    topic: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search podcast catalog by show, episode, guest, or topical subject.

    Args:
        query: Search keywords.
        topic: Specific topic tag.
        status: 'queue' or 'listened'.
        limit: Max results. Defaults to 5.

    Returns:
        List of matching podcast records.
    """
    return podcast_service.search(query=query, topic=topic, status=status, limit=limit)


@curator_tool(
    slim=False,
    description="Search Apple Podcasts directory for shows and episodes."
)
def lookup_podcast_online(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Query Apple Podcasts directory for online shows, artwork, and descriptions.

    Args:
        query: Show or host keyword.
        limit: Max results. Defaults to 5.

    Returns:
        List of online podcast directory listings.
    """
    return podcast_client.search(query=query, limit=limit)


# ============================================================================
# 6. SENSORY & CONNOISSEUR VAULT
# ============================================================================

@curator_tool(
    slim=True,
    description="Log or update an item in the Sensory Vault (tea, whiskey, coffee, wine, gin, perfume, watch)."
)
def log_sensory_item(
    category: str,
    name: str,
    maker_or_brand: str,
    origin_or_region: Optional[str] = None,
    vintage_or_year: Optional[str] = None,
    status: str = "owned",
    user_rating: Optional[float] = None,
    flavor_or_scent_notes: Optional[List[str]] = None,
    specs: Optional[Dict[str, Any]] = None,
    review: Optional[str] = "",
    personal_notes: Optional[str] = "",
    price_tier: Optional[str] = None,
    date_experienced: Optional[str] = None,
    item_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Log an artisanal or luxury item into the Sensory Vault.

    Supports dedicated connoisseur domains: whiskey, wine, coffee, tea, gin,
    chocolate, perfume, and luxury mechanical timepieces.

    Args:
        category: Domain ('whiskey', 'wine', 'coffee', 'tea', 'gin', 'chocolate', 'perfume', 'watch').
        name: Name of bottle, vintage, bean, blend, fragrance, or reference.
        maker_or_brand: Producer, distillery, roaster, estate, or maison.
        origin_or_region: Terroir or country of origin (e.g. 'Islay, Scotland', 'Yirgacheffe, Ethiopia').
        vintage_or_year: Vintage year or production release.
        status: 'owned', 'wishlist', or 'experienced'.
        user_rating: Rating from 1.0 to 10.0.
        flavor_or_scent_notes: Flavor accords, nose aromas, or olfactory pyramid notes.
        specs: Domain-specific technical specifications (ABV, processing method, movement caliber).
        review: Detailed tasting appraisal.
        personal_notes: Private reflections or cellaring notes.
        price_tier: Pricing bracket ('$', '$$', '$$$', '$$$$').
        date_experienced: Date tasted or acquired (YYYY-MM-DD).
        item_id: Optional existing item ID.

    Returns:
        Confirmation dictionary with created/updated item.
    """
    return sensory_service.log_item(
        category=category,
        name=name,
        maker_or_brand=maker_or_brand,
        origin_or_region=origin_or_region,
        vintage_or_year=vintage_or_year,
        status=status,
        user_rating=user_rating,
        flavor_or_scent_notes=flavor_or_scent_notes,
        specs=specs,
        review=review,
        personal_notes=personal_notes,
        price_tier=price_tier,
        date_experienced=date_experienced,
        item_id=item_id,
    )


@curator_tool(
    slim=False,
    description="Update sensory tasting impressions, rating, or status."
)
def update_sensory_item(
    item_id: str,
    user_rating: Optional[float] = None,
    status: Optional[str] = None,
    review: Optional[str] = None,
    personal_notes: Optional[str] = None,
    flavor_or_scent_notes: Optional[List[str]] = None,
    specs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Update sensory tasting notes, rating, ownership status, or technical specifications.

    Args:
        item_id: Unique record ID in sensory_vault.
        user_rating: Updated rating (1.0 - 10.0).
        status: Updated status ('owned', 'wishlist', 'experienced').
        review: Updated review text.
        personal_notes: Updated private notes.
        flavor_or_scent_notes: Updated list of notes.
        specs: Updated domain specifications.

    Returns:
        Dictionary confirming update.
    """
    return sensory_service.update_item(
        item_id=item_id,
        user_rating=user_rating,
        status=status,
        review=review,
        personal_notes=personal_notes,
        flavor_or_scent_notes=flavor_or_scent_notes,
        specs=specs,
    )


@curator_tool(
    slim=True,
    description="Search sensory vault items by keyword, category, rating, or flavor tag."
)
def search_sensory_vault(
    query: str = "",
    category: Optional[str] = None,
    status: Optional[str] = None,
    min_rating: Optional[float] = None,
    tag: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search sensory vault items by keyword, domain category, rating threshold, or tasting accord.

    Args:
        query: Keyword matching name, brand, origin, or notes.
        category: Domain filter ('whiskey', 'wine', 'coffee', 'tea', 'gin', 'chocolate', 'perfume', 'watch').
        status: Ownership filter ('owned', 'wishlist', 'experienced').
        min_rating: Minimum rating threshold (1.0 to 10.0).
        tag: Flavor or aroma accord tag (e.g. 'peat', 'bergamot', 'jasmine').
        limit: Max results to return. Defaults to 5.

    Returns:
        List of matching sensory vault records with compacted note summaries.
    """
    return sensory_service.search(
        query=query,
        category=category,
        status=status,
        min_rating=min_rating,
        tag=tag,
        limit=limit,
    )


@curator_tool(
    slim=False,
    description="Aggregate sensory flavor profiles, accords, and luxury preferences."
)
def get_sensory_taste_profile() -> Dict[str, Any]:
    """
    Compute macro sensory profile across cellared spirits, wines, teas, and fragrances.

    Returns:
        Dictionary containing top flavor accords, favorite producers, and category breakdowns.
    """
    return recommendation_service.get_sensory_taste_profile()


@curator_tool(
    slim=False,
    description="Search open sensory product databases (Open Food Facts, Whisky Hunter, TheCocktailDB)."
)
def search_open_product_catalog(
    query: str,
    category: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Query open-source consumer and connoisseur databases for products and tasting data.

    Args:
        query: Product or brand search query.
        category: Optional category filter ('whiskey', 'wine', 'tea', 'cocktail', 'food').
        limit: Max results to return. Defaults to 5.

    Returns:
        List of product records with origin, ingredients, and brand info.
    """
    return catalog_client.search_by_category(query=query, category=category, limit=limit)


# ============================================================================
# 7. RESTAURANTS & DINING JOURNAL
# ============================================================================

@curator_tool(
    slim=True,
    description="Log a restaurant or dining experience in dining journal or wishlist."
)
def log_restaurant(
    name: str,
    city: str,
    cuisine: str,
    neighborhood: Optional[str] = None,
    status: str = "wishlist",
    user_rating: Optional[float] = None,
    standout_dishes: Optional[List[str]] = None,
    notes_and_review: Optional[str] = "",
    vibe_tags: Optional[List[str]] = None,
    michelin_stars: Optional[int] = None,
    price_tier: Optional[str] = None,
    date_visited: Optional[str] = None,
    url_or_reservation: Optional[str] = None,
    restaurant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Log a restaurant record into the dining journal or travel wishlist.

    Args:
        name: Name of the restaurant or establishment.
        city: City where located (e.g. 'Tokyo', 'London', 'San Francisco').
        cuisine: Primary cuisine category (e.g. 'Japanese', 'Nordic', 'Italian').
        neighborhood: Specific district or quarter (e.g. 'Ginza', 'Mayfair').
        status: 'visited' or 'wishlist'.
        user_rating: Rating from 1.0 to 10.0 (if visited).
        standout_dishes: Must-order menu items or tasting course highlights.
        notes_and_review: Dining notes, reservation tips, or food review.
        vibe_tags: Atmosphere tags (e.g. ['omakase', 'intimate', 'speakeasy']).
        michelin_stars: 1, 2, or 3 Michelin stars (optional).
        price_tier: Price bracket ('$', '$$', '$$$', '$$$$').
        date_visited: Date of dining experience (YYYY-MM-DD).
        url_or_reservation: Website or reservation link (Resy/OpenTable).
        restaurant_id: Optional custom ID.

    Returns:
        Confirmation dictionary with created/updated restaurant record.
    """
    return restaurant_service.log_restaurant(
        name=name,
        city=city,
        cuisine=cuisine,
        neighborhood=neighborhood,
        status=status,
        user_rating=user_rating,
        standout_dishes=standout_dishes,
        notes_and_review=notes_and_review,
        vibe_tags=vibe_tags,
        michelin_stars=michelin_stars,
        price_tier=price_tier,
        date_visited=date_visited,
        url_or_reservation=url_or_reservation,
        restaurant_id=restaurant_id,
    )


@curator_tool(
    slim=False,
    description="Update restaurant review, standout dishes, rating, or status."
)
def update_restaurant(
    restaurant_id: str,
    status: Optional[str] = None,
    user_rating: Optional[float] = None,
    standout_dishes: Optional[List[str]] = None,
    notes_and_review: Optional[str] = None,
    vibe_tags: Optional[List[str]] = None,
    date_visited: Optional[str] = None,
    url_or_reservation: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update dining venue record after a visit or change in recommendation status.

    Args:
        restaurant_id: Record ID in restaurants collection.
        status: Updated status ('visited', 'wishlist').
        user_rating: Rating from 1.0 to 10.0.
        standout_dishes: Updated standout dishes.
        notes_and_review: Updated dining review.
        vibe_tags: Updated vibe keywords.
        date_visited: Date visited (YYYY-MM-DD).
        url_or_reservation: Updated reservation link.

    Returns:
        Confirmation dictionary.
    """
    return restaurant_service.update_restaurant(
        restaurant_id=restaurant_id,
        status=status,
        user_rating=user_rating,
        standout_dishes=standout_dishes,
        notes_and_review=notes_and_review,
        vibe_tags=vibe_tags,
        date_visited=date_visited,
        url_or_reservation=url_or_reservation,
    )


@curator_tool(
    slim=True,
    description="Search dining vault by keyword, city, cuisine, status, or vibe tag."
)
def search_restaurants(
    query: str = "",
    city: Optional[str] = None,
    cuisine: Optional[str] = None,
    status: Optional[str] = None,
    vibe: Optional[str] = None,
    min_rating: Optional[float] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Search and filter cataloged dining venues by city, cuisine, status, or vibe.

    Args:
        query: Keyword query matching name, neighborhood, or dishes.
        city: City filter (e.g. 'Tokyo', 'London', 'Paris').
        cuisine: Cuisine category (e.g. 'Japanese', 'French', 'Seafood').
        status: 'visited' or 'wishlist'.
        vibe: Atmospheric tag (e.g. 'omakase', 'romantic', 'casual').
        min_rating: Minimum rating (1.0 to 10.0).
        limit: Max results. Defaults to 5.

    Returns:
        List of matching restaurant records.
    """
    return restaurant_service.search(
        query=query,
        city=city,
        cuisine=cuisine,
        status=status,
        vibe=vibe,
        min_rating=min_rating,
        limit=limit,
    )


@curator_tool(
    slim=False,
    description="Get dining statistics: places visited, wishlist, top cities, and cuisines."
)
def get_dining_stats() -> Dict[str, Any]:
    """
    Compute macro dining statistics across visited and wishlist restaurants.

    Returns:
        Dictionary containing visited totals, wishlist counts, top cities, and cuisines.
    """
    return restaurant_service.get_stats()


# ============================================================================
# 8. MULTIMODAL SENSORY & CULTURAL PAIRINGS
# ============================================================================

@curator_tool(
    slim=True,
    description="Generate aesthetic cross-domain pairing connecting books/movies with sensory beverages."
)
def get_aesthetic_pairing(
    anchor_type: str,
    title_or_name: str,
    author_or_creator: Optional[str] = None,
    mood: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Synthesize an aesthetic cross-domain pairing connecting literature/cinema with sensory beverages and atmospheres.

    Pairing Engine matches tonal attributes, geographical origins, and sensory accords
    (e.g., pairing Murakami with Japanese Gyokuro tea and Hinoki fragrance).

    Args:
        anchor_type: 'book' or 'media'/'movie'.
        title_or_name: Title of the book or film.
        author_or_creator: Author or director (optional).
        mood: Atmospheric intention (e.g. 'melancholic rain', 'late-night focus').

    Returns:
        Dictionary containing beverage pairing, ambient fragrance, and cellar alternatives.
    """
    a_type = anchor_type.lower().strip()
    if "book" in a_type:
        return pairing_service.get_pairing_for_book(
            title=title_or_name,
            author=author_or_creator,
            mood=mood,
        )
    return pairing_service.get_pairing_for_media(
        title=title_or_name,
        media_type="movie",
        mood=mood,
    )


@curator_tool(
    slim=False,
    description="Generate beverage or cellar pairing tailored to a culinary dish."
)
def get_dining_course_pairing(
    dish_or_cuisine: str,
    dining_style: Optional[str] = "dinner",
) -> Dict[str, Any]:
    """
    Synthesize an artisanal beverage or cellar pairing tailored to a culinary dish or cuisine.

    Args:
        dish_or_cuisine: Dish name or cuisine style (e.g. 'Dry-Aged Ribeye', 'Omakase Nigiri').
        dining_style: 'dinner', 'lunch', or 'tasting'. Defaults to 'dinner'.

    Returns:
        Dictionary with pairing recommendation, rationale, and tasting notes.
    """
    return pairing_service.get_pairing_for_dish(
        dish_or_cuisine=dish_or_cuisine,
        dining_style=dining_style,
    )


# ============================================================================
# 9. LONG-TERM PERSONAL MEMORY & DIRECTIVES
# ============================================================================

@curator_tool(
    slim=True,
    description="Store a personal preference, habit, directive, or constraint in long-term memory."
)
def store_memory(
    content: str,
    category: str = "preference",
    tags: Optional[List[str]] = None,
    importance: int = 3,
) -> Dict[str, Any]:
    """
    Store or update a personal preference, habit, directive, or constraint in long-term memory.

    Call this tool autonomously when the user shares personal constraints, quirks,
    or facts that should persist across future conversations.

    Args:
        content: The fact, preference, or directive to remember (e.g. 'Prefers dark roast pour-overs').
        category: 'preference', 'dislike', 'goal', 'habit', 'context', or 'directive'.
        tags: Optional topic keywords for indexing (e.g. ['coffee', 'beverages']).
        importance: Integer priority from 1 (minor quirk) to 5 (critical hard directive).

    Returns:
        Dictionary confirming storage and unique memory ID.
    """
    return memory_service.store(
        content=content,
        category=category,
        tags=tags,
        importance=importance,
        source="user_explicit",
    )


@curator_tool(
    slim=True,
    description="Recall stored memories and directives matching a topic or category."
)
def recall_memories(
    query: Optional[str] = None,
    category: Optional[str] = None,
    min_importance: int = 1,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Recall stored personal memories, habits, and directives matching a topic or category.

    Args:
        query: Keyword or topic query (e.g. 'coffee', 'tokyo', 'reading').
        category: Category filter ('preference', 'dislike', 'goal', 'habit', 'context', 'directive').
        min_importance: Minimum importance threshold (1 to 5). Defaults to 1.
        limit: Max results to return. Defaults to 5.

    Returns:
        Dictionary containing matched memories.
    """
    results = memory_service.recall(
        query=query,
        category=category,
        min_importance=min_importance,
        limit=limit,
    )
    return {
        "status": "success",
        "query": query,
        "category": category,
        "total_matches": len(results),
        "memories": results,
    }


@curator_tool(
    slim=False,
    description="Delete a stored personal memory by ID."
)
def forget_memory(memory_id: str) -> Dict[str, Any]:
    """
    Delete an outdated, obsolete, or retracted personal memory by ID.

    Args:
        memory_id: Unique identifier of the memory to remove.

    Returns:
        Dictionary confirming deletion.
    """
    return memory_service.forget(memory_id=memory_id)


@curator_tool(
    slim=False,
    description="Get memory vault statistics and high-importance directives count."
)
def get_memory_stats() -> Dict[str, Any]:
    """
    Compute summary metrics of the personal memory vault.

    Returns:
        Dictionary containing total memory counts, high-importance directives, category breakdown, and top tags.
    """
    return memory_service.get_stats()


# ============================================================================
# SERVER RUNNER
# ============================================================================

if __name__ == "__main__":
    mcp.run()
