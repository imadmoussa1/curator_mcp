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
    SensoryService,
    RestaurantService,
    RecommendationService,
    PairingService,
    BookMetadataClient,
    TMDBClient,
    ApplePodcastsClient,
    ConnoisseurCatalogClient,
)

# Initialize FastMCP Server
mcp = FastMCP("Curator-MCP")

# Dependency Injection & Service Initialization
book_service = BookService()
media_service = MediaService()
quote_service = QuoteService()
podcast_service = PodcastService()
sensory_service = SensoryService()
restaurant_service = RestaurantService()

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
)

pairing_service = PairingService(
    book_service=book_service,
    media_service=media_service,
    sensory_service=sensory_service,
    restaurant_service=restaurant_service,
)


# ============================================================================
# 0. CLAUDE DESKTOP NATIVE CONTEXT RESOURCES (@mcp.resource)
# ============================================================================

@mcp.resource("curator://context/taste_profile")
def get_taste_profile_context() -> str:
    """
    Live background context resource providing Claude Desktop with the user's
    taste preferences, 5-star books, 10/10 films, sensory flavor notes, and favorite cuisines.
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
    Live background context resource providing Claude Desktop with currently reading books,
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
    Live background context resource providing a morning brief: Quote of the Day,
    active reading goal, and summary statistics.
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
        f"**Quote of the Day**: \"{quote.get('quote_text', 'Live deliberately.')}\" — {quote.get('speaker_or_author', 'Unknown')} (*{quote.get('source_title', 'Curator')}*)",
        f"**Total Books Tracked**: {stats['books'].get('total_books', 0)} ({stats['books'].get('read', 0)} completed)",
        f"**Total Media Watched**: {stats['media'].get('watched', 0)} ({stats['media'].get('watchlist', 0)} in watchlist)",
        f"**Sensory Vault Items**: {stats['vault'].get('total_items', 0)} items",
        f"**Restaurants Cataloged**: {stats['restaurants'].get('total_places', 0)} places",
    ]
    return "\n".join(lines)


@mcp.resource("curator://context/taste_dna_dossier")
def get_taste_dna_dossier() -> str:
    """
    Live background context resource exposing the comprehensive Taste DNA dossier
    of the user across literature, cinema, culinary, and artisanal categories.
    """
    profile = recommendation_service.get_taste_profile()
    sensory = recommendation_service.get_sensory_taste_profile() if hasattr(recommendation_service, "get_sensory_taste_profile") else {}
    wrapped = recommendation_service.generate_cultural_wrapped()
    lines = [
        "# Curator MCP - User Taste DNA Dossier",
        f"**Cultural Archetype**: {wrapped.get('cultural_archetype', {}).get('title', 'The Polymath')} — {wrapped.get('cultural_archetype', {}).get('summary', '')}",
        f"**Top Literary Authors**: {', '.join(profile.get('taste_summary', {}).get('top_authors', [])[:5])}",
        f"**Top Cinematic Directors**: {', '.join(profile.get('taste_summary', {}).get('top_directors', [])[:5])}",
        f"**Top Film & Show Genres**: {', '.join(profile.get('taste_summary', {}).get('top_genres', [])[:5])}",
        f"**Top Sensory Accords**: {', '.join(sensory.get('top_flavor_and_scent_accords', [])[:6])}",
        f"**Top Artisans & Distilleries**: {', '.join(sensory.get('favorite_makers_or_distilleries', [])[:5])}",
    ]
    return "\n".join(lines)


# ============================================================================
# 0.5 CLAUDE DESKTOP 1-CLICK PROMPTS (@mcp.prompt)
# ============================================================================

@mcp.prompt("smart_recommendation_consultation")
def smart_recommendation_consultation(domain: str = "movies", mood_or_craving: str = "") -> str:
    """
    Orchestrate an elite, internet-powered recommendation session.
    Instructs the AI agent to retrieve the user's taste brief, run live web searches
    for fresh/hidden gems, vet candidates, and present a curated choice.
    """
    craving_str = f" for '{mood_or_craving}'" if mood_or_craving else ""
    return (
        f"The user wants a smart, highly personalized recommendation in '{domain}'{craving_str}.\n"
        "As an AI agent with internet search access, follow this elite curation workflow:\n"
        "1. Call `get_agent_recommendation_brief(domain='{domain}', mood_or_intent='{mood_or_craving}')` to get their Taste DNA and strict Negative Exclusion Catalog.\n"
        "2. Execute live internet searches using the suggested queries in the brief to discover fresh, acclaimed, or obscure candidates (e.g. 2024-2026 releases or hidden masterpieces).\n"
        "3. For your top 1-2 discovered candidates, call `vet_recommendation_candidate(domain='{domain}', title_or_name=...)` to guarantee ZERO library collisions and get verified affinity scores.\n"
        "4. Present the final curated recommendation with an evocative review and explicit connection to their past 10/10 favorites."
    )


@mcp.prompt("daily_briefing")
def daily_briefing() -> str:
    """
    Generate an inspiring morning intellectual briefing for Claude Desktop.
    Claude will synthesize your active reading status, quote of the day,
    and suggest an evening cultural or culinary recommendation.
    """
    return (
        "You are the user's personal Taste & Cultural Intelligence Curator. "
        "Review their active queues, current book progress, and quote of the day. "
        "Provide a concise, elegant morning briefing structured as:\n"
        "1. 💡 Thought for the Day (reflect on their Quote of the Day)\n"
        "2. 📖 Reading & Intellectual Focus (mention what they are currently reading)\n"
        "3. 🎬 Evening Wind-Down Recommendation (pick an ideal film from their watchlist or an aesthetic beverage pairing)\n"
        "Keep the tone sophisticated, encouraging, and clear."
    )


@mcp.prompt("tasting_session")
def tasting_session(category: str = "whiskey", item_name: str = "") -> str:
    """
    Interactive sensory tasting interview where Claude acts as a Master Sommelier,
    Barista, Perfumer, or Horologist to log an artisanal item with precise specs.
    """
    item_str = f" for '{item_name}'" if item_name else ""
    return (
        f"You are conducting a Master Tasting & Evaluation Session in the domain of '{category}'{item_str}. "
        "Act as a world-class connoisseur and guide the user through a sensory evaluation:\n"
        "1. Appearance / Origin / Provenance check\n"
        "2. Aroma / Nose (top notes, primary accords, subtlety)\n"
        "3. Palate / Taste profile (texture, acidity/tannin/sweetness/peat)\n"
        "4. Finish / Longevity & Final Rating (1.0 to 10.0 scale)\n"
        "Ask questions one step at a time or invite them to share their impressions, "
        "then offer to log the completed evaluation directly into their Sensory Vault via `log_sensory_item`."
    )


@mcp.prompt("weekend_curation")
def weekend_curation(mood: Optional[str] = None) -> str:
    """
    Prompts Claude to curate an entire weekend cultural itinerary
    (Movie from watchlist + Wine/Spirit/Tea pairing + Book chapter + Dining spot).
    """
    mood_str = f" with a '{mood}' aesthetic" if mood else ""
    return (
        f"Curate a complete, luxurious weekend cultural and culinary itinerary{mood_str}. "
        "Leverage the tools in Curator MCP to select:\n"
        "1. 🍿 Cinema Pick: A movie from their watchlist matching their free time and mood\n"
        "2. 🍷 Beverage / Sensory Pairing: A wine, tea, or craft cocktail that pairs with the movie\n"
        "3. 📚 Reading Session: A recommended time and book from their reading list\n"
        "4. 🍽️ Dining Experience: A restaurant from their dining wishlist or a curated neighborhood gem\n"
        "Present the plan with evocative descriptions and explain why each element complements the other."
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
    Get macro metrics across all collections: Books, Movies/Series, Quotes, Podcasts,
    Sensory Vault (Tea, Whiskey, Coffee, Gin, Wine, Chocolate, Perfume, Watches), and Restaurants.
    Returns counts, breakdowns, and average ratings.
    """
    return {
        "books": book_service.get_stats(),
        "media": media_service.get_stats(),
        "quotes": {"total": len(quote_service.stream_all())},
        "podcasts": podcast_service.get_stats(),
        "sensory_vault": sensory_service.get_stats(),
        "restaurants": restaurant_service.get_stats(),
    }


@mcp.tool()
def get_agent_recommendation_brief(
    domain: str,
    mood_or_intent: Optional[str] = None,
    target_location: Optional[str] = None
) -> Dict[str, Any]:
    """
    Call this tool FIRST when the user asks for recommendations.
    Equips you (the AI agent) with the user's complete Taste DNA, items to strictly avoid
    (Negative Exclusion Catalog), low-rated guardrails, and targeted web search strategies
    to discover fresh, extraordinary recommendations using your web search tool.
    Args:
        domain: 'books', 'movies', 'tv', 'whiskey', 'coffee', 'tea', 'wine', 'gin', 'chocolate', 'perfume', 'watch', 'restaurants', 'podcasts'
        mood_or_intent: Optional vibe, genre, or craving constraint (e.g. 'cerebral slow-burn sci-fi', 'peated sherry finish', 'funky natural wine counter')
        target_location: City or region (crucial for restaurants, e.g. 'Tokyo', 'London', 'Paris', 'New York')
    """
    return recommendation_service.get_agent_recommendation_brief(
        domain=domain,
        mood_or_intent=mood_or_intent,
        target_location=target_location
    )


@mcp.tool()
def vet_recommendation_candidate(
    domain: str,
    title_or_name: str,
    maker_or_creator: Optional[str] = None,
    attributes: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Before presenting a candidate you found via web search to the user, call this tool
    to verify it is NOT already in their library, collection, or wishlist (collision check),
    and to receive calculated taste affinity scores and personalized connection hooks.
    Args:
        domain: 'books', 'movies', 'tv', 'whiskey', 'coffee', 'tea', 'wine', 'gin', 'chocolate', 'perfume', 'watch', 'restaurants', 'podcasts'
        title_or_name: Title of book/film/podcast or name of restaurant/bottle/fragrance
        maker_or_creator: Author, director, roaster, distillery, chef, or perfume house
        attributes: List of flavor notes, genres, vibe tags, or stylistic attributes
    """
    return recommendation_service.vet_recommendation_candidate(
        domain=domain,
        title_or_name=title_or_name,
        maker_or_creator=maker_or_creator,
        attributes=attributes
    )


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
    review: Optional[str] = "",
    private_notes: Optional[str] = "",
    notes: Optional[str] = "",
    date_read: Optional[str] = None
) -> Dict[str, Any]:
    """
    Log a book the user has finished reading, following the Goodreads rating system (0 to 5 stars),
    with optional written review, personal private notes, and date read (YYYY-MM-DD).
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


@mcp.tool()
def update_book_status(
    title: Optional[str] = None,
    book_id: Optional[str] = None,
    shelf: str = "read",
    user_rating: Optional[int] = None,
    review: Optional[str] = None,
    private_notes: Optional[str] = None,
    date_read: Optional[str] = None,
    date_started: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update the reading status/shelf and add/edit reviews for a book using the Goodreads review system.
    Args:
        title: Title of the book (searched if book_id not provided)
        book_id: Goodreads Book ID (exact document match)
        shelf: Goodreads shelf: 'read', 'currently-reading', or 'to-read'
        user_rating: Goodreads rating from 0 (unrated) to 5 stars
        review: Written review text (equivalent to Goodreads 'My Review')
        private_notes: Personal reflections or highlights (equivalent to Goodreads 'Private Notes')
        date_read: Completion date in YYYY-MM-DD format
        date_started: Date started reading in YYYY-MM-DD format
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
    review: Optional[str] = "",
    user_notes: Optional[str] = "",
    notes: Optional[str] = "",
    date_watched: Optional[str] = None
) -> Dict[str, Any]:
    """
    Log a movie or TV show the user watched, following the IMDb rating system (1 to 10),
    with optional written review, personal notes, and date watched (YYYY-MM-DD).
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
        review=review,
        user_notes=user_notes,
        date_watched=date_watched,
    )


@mcp.tool()
def update_media_status(
    title: Optional[str] = None,
    media_id: Optional[str] = None,
    status: str = "watched",
    user_rating: Optional[int] = None,
    review: Optional[str] = None,
    user_notes: Optional[str] = None,
    date_watched: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update a movie or TV show's status ('watched' or 'watchlist') and add/edit reviews using the IMDb review system.
    Args:
        title: Title of the movie or series (searched if media_id not provided)
        media_id: IMDb Const ID (e.g. tt0111161, exact document match)
        status: Status: 'watched' or 'watchlist'
        user_rating: IMDb user rating from 1 to 10
        review: Written review text (e.g. thoughts on directing, cinematography, performances)
        user_notes: Personal notes or viewing context
        date_watched: Date watched in YYYY-MM-DD format
    """
    return media_service.update_status(
        media_id=media_id,
        title=title,
        status=status,
        user_rating=user_rating,
        review=review,
        user_notes=user_notes,
        date_watched=date_watched,
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
# 6. SENSORY & CONNOISSEUR VAULT
# (Tea, Whiskey, Coffee, Gin, Wine, Chocolate, Perfume, Watches)
# ============================================================================

@mcp.tool()
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
    Log or upsert an artisanal, sensory, or luxury item in your Sensory Vault.
    Supported categories:
    - 'tea': Loose-leaf, matcha, oolongs, pu-erh (specs: brew_temp, steep_time, oxidation)
    - 'whiskey': Single malt, bourbon, rye, Japanese (specs: cask, abv, peat_level)
    - 'coffee': Specialty coffee beans & origins (specs: roast_level, process, altitude)
    - 'gin': Craft gins & spirits (specs: botanicals, abv, style)
    - 'wine': Fine wine & vintages (specs: varietal, body, tannin, acidity)
    - 'chocolate': Bean-to-bar & single-origin (specs: cacao_pct, bean_origin, conching)
    - 'perfume': Fragrances & niche scents (specs: top_notes, heart_notes, base_notes, concentration)
    - 'watch': Horology & luxury timepieces (specs: caliber, case_size_mm, power_reserve, water_resistance)

    Args:
        category: tea, whiskey, coffee, gin, wine, chocolate, perfume, watch
        name: Name of item or edition (e.g. 'Lagavulin 16', 'Baccarat Rouge 540', 'Speedmaster Pro')
        maker_or_brand: Producer, distillery, roaster, perfumer, or watchmaker
        origin_or_region: Origin/terroir (e.g. 'Islay', 'Grasse, France', 'Yirgacheffe, Ethiopia')
        vintage_or_year: Vintage year or watch reference number (e.g. '2018' or 'Ref. 126610LN')
        status: 'owned' (in cabinet/collection), 'wishlist', 'sampled', 'finished'
        user_rating: 1.0 to 10.0 scale
        flavor_or_scent_notes: Tasting wheel descriptors or olfactory accords (e.g. ['peat', 'smoke', 'vanilla'])
        specs: Domain technical details dictionary
        review: Tasting review, olfactory impression, or horology review
        personal_notes: Private cellar bin, batch info, or purchase price
        price_tier: $, $$, $$$, $$$$, or $$$$$
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


@mcp.tool()
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
    Update tasting impressions, rating, or status (e.g. mark wishlist item as sampled or owned).
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


@mcp.tool()
def search_sensory_vault(
    query: str = "",
    category: Optional[str] = None,
    status: Optional[str] = None,
    min_rating: Optional[float] = None,
    tag: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Search your personal sensory vault (tea, coffee, whiskey, gin, wine, chocolate, perfume, watches)
    by keyword, category, status (owned/wishlist/sampled), minimum rating, or flavor/scent tag.
    """
    return sensory_service.search(
        query=query,
        category=category,
        status=status,
        min_rating=min_rating,
        tag=tag,
        limit=limit,
    )


@mcp.tool()
def get_sensory_taste_profile() -> Dict[str, Any]:
    """
    Retrieve an aggregated connoisseur sensory profile: top flavor notes, favorite distillers/perfumers/makers,
    preferred terroirs and origins, and highlight masterpieces across the sensory vault.
    """
    return recommendation_service.get_sensory_taste_profile()


@mcp.tool()
def search_open_product_catalog(
    category: str,
    query: str,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """
    Query open product databases (Open Food Facts & Whisky Hunter) for tea, coffee, wine, chocolate, or whisky.
    Returns product names, brands, origins, barcodes, and distilleries.
    Works free with zero API key required.
    """
    return catalog_client.search_catalog(category=category, query=query, limit=limit)


# ============================================================================
# 7. FINE DINING & RESTAURANT JOURNAL
# ============================================================================

@mcp.tool()
def log_restaurant(
    name: str,
    city: str,
    cuisine: str,
    neighborhood: Optional[str] = None,
    status: str = "visited",
    user_rating: Optional[float] = None,
    michelin_status: Optional[str] = None,
    price_tier: Optional[str] = None,
    standout_dishes: Optional[List[str]] = None,
    notes_and_review: Optional[str] = "",
    vibe_tags: Optional[List[str]] = None,
    url_or_reservation: Optional[str] = None,
    date_visited: Optional[str] = None,
    restaurant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Log a restaurant visit or add a restaurant/cafe/wine bar to your dining wishlist.
    Args:
        name: Name of venue (e.g. 'Le Bernardin', 'Septime', 'Sushi Sawada')
        city: City (e.g. 'New York', 'Paris', 'Tokyo', 'London')
        cuisine: Cuisine type (e.g. 'Omakase', 'Modern French', 'Neo-Bistro', 'Italian')
        neighborhood: District (e.g. 'Ginza', 'SoHo', '11th Arr.')
        status: 'visited' (dined at), 'wishlist' (want to go), 'booked' (upcoming reservation)
        user_rating: 1.0 to 10.0 scale
        michelin_status: '1-Star', '2-Star', '3-Star', 'Bib Gourmand', 'Selected', or None
        price_tier: $, $$, $$$, or $$$$
        standout_dishes: Memorable dishes, tasting menu highlights, or signature courses
        notes_and_review: Food critique, wine pairing comments, service & ambiance
        vibe_tags: Atmosphere tags (e.g. ['romantic', 'intimate counter', 'natural wine', 'wood fire'])
        url_or_reservation: Link to Resy, OpenTable, TableCheck, or website
        date_visited: YYYY-MM-DD format
    """
    return restaurant_service.log_restaurant(
        name=name,
        city=city,
        cuisine=cuisine,
        neighborhood=neighborhood,
        status=status,
        user_rating=user_rating,
        michelin_status=michelin_status,
        price_tier=price_tier,
        standout_dishes=standout_dishes,
        notes_and_review=notes_and_review,
        vibe_tags=vibe_tags,
        url_or_reservation=url_or_reservation,
        date_visited=date_visited,
        restaurant_id=restaurant_id,
    )


@mcp.tool()
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
    Update dining notes, dishes, or change status from wishlist to visited with rating.
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


@mcp.tool()
def search_restaurants(
    query: str = "",
    city: Optional[str] = None,
    cuisine: Optional[str] = None,
    status: Optional[str] = None,
    vibe: Optional[str] = None,
    min_rating: Optional[float] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Search your dining vault and wishlists by keyword, city, cuisine, status (visited/wishlist), or vibe tag.
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


@mcp.tool()
def get_dining_stats() -> Dict[str, Any]:
    """
    Retrieve macro metrics on your dining life: total places visited, wishlist count,
    top cities explored, top cuisines, Michelin-starred counts, and average ratings.
    """
    return restaurant_service.get_stats()


# ============================================================================
# 8. MULTIMODAL SENSORY & CULTURAL PAIRINGS
# ============================================================================


@mcp.tool()
def get_aesthetic_pairing(
    anchor_type: str,
    title_or_name: str,
    author_or_creator: Optional[str] = None,
    mood: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate an aesthetic cross-domain multimodal pairing connecting literature or cinema
    with sensory connoisseur goods (tea, coffee, single malt, wine, chocolate, fragrance, sonic vibe).

    Args:
        anchor_type: 'book' or 'movie' / 'media'
        title_or_name: Title of the book or movie (e.g. 'Dune', 'Norwegian Wood', 'Blade Runner 2049')
        author_or_creator: Optional author name or film director
        mood: Optional vibe constraint (e.g. 'rainy day', 'cyberpunk', 'zen', 'dark noir', 'classical')

    Returns:
        Curated beverage pairing with rationale, matching items in your owned cellar/cabinet,
        olfactory fragrance accord, single-origin chocolate pairing, and acoustic sonic ambiance.
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


@mcp.tool()
def get_dining_course_pairing(
    dish_or_cuisine: str,
    dining_style: Optional[str] = "dinner",
) -> Dict[str, Any]:
    """
    Generate a beverage or cellar pairing (fine wine, craft cocktail, or cold-brew tea)
    tailored to a specific culinary dish or restaurant course.

    Args:
        dish_or_cuisine: Dish name or cuisine style (e.g. 'Omakase Nigiri', 'Dry-Aged Wagyu Ribeye', 'Truffle Tagliolini')
        dining_style: 'dinner', 'lunch', 'tasting_menu', or 'casual'
    """
    return pairing_service.get_pairing_for_dish(
        dish_or_cuisine=dish_or_cuisine,
        dining_style=dining_style,
    )


# ============================================================================
# SERVER RUNNER
# ============================================================================

if __name__ == "__main__":
    mcp.run()
