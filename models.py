"""
Data schemas and models for life_os_mcp using Pydantic.
Validates books, media, quotes, and podcasts entries before writing to Firestore.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class BookModel(BaseModel):
    """Schema for books in the Firestore 'books' collection following Goodreads schema."""
    id: str = Field(..., description="Goodreads Book ID (string)")
    title: str = Field(..., description="Book title")
    author: str = Field(..., description="Book author name")
    user_rating: int = Field(default=0, ge=0, le=5, description="User rating from 0 (unrated) to 5 stars (Goodreads system)")
    avg_rating: float = Field(default=0.0, ge=0.0, le=5.0, description="Community average rating")
    shelf: str = Field(
        default="to-read",
        description="Reading status shelf: read, currently-reading, to-read"
    )
    notes_and_reviews: str = Field(default="", description="User notes or review text (legacy field)")
    review: str = Field(default="", description="Goodreads written review text")
    private_notes: str = Field(default="", description="Goodreads personal private notes")
    date_started: Optional[str] = Field(default=None, description="Date started reading in YYYY-MM-DD format")
    date_read: Optional[str] = Field(default=None, description="Date read in YYYY-MM-DD format or timestamp string")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    @field_validator("shelf")
    @classmethod
    def validate_shelf(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if v_clean in ("read", "currently-reading", "to-read"):
            return v_clean
        # Map common Goodreads variations
        if "current" in v_clean:
            return "currently-reading"
        if "to" in v_clean and "read" in v_clean:
            return "to-read"
        return "read" if "read" in v_clean else v_clean

    def to_firestore_dict(self) -> dict:
        data = self.model_dump()
        # Keep notes_and_reviews in sync for backward compatibility
        if not data.get("notes_and_reviews") and (data.get("review") or data.get("private_notes")):
            parts = []
            if data.get("review"):
                parts.append(f"Review: {data['review']}")
            if data.get("private_notes"):
                parts.append(f"Private Notes: {data['private_notes']}")
            data["notes_and_reviews"] = " | ".join(parts)
        if not data.get("updated_at"):
            data["updated_at"] = datetime.now(timezone.utc)
        return data


class MediaModel(BaseModel):
    """Schema for movies & series in the Firestore 'media' collection following IMDb schema."""
    id: str = Field(..., description="IMDb Const ID (e.g. tt0111161)")
    title: str = Field(..., description="Title of the movie or series")
    media_type: str = Field(
        default="movie",
        description="Type of media: movie, tvSeries, tvMiniSeries, etc."
    )
    user_rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="User rating from 1 to 10 (IMDb rating system, nullable if unrated watchlist item)"
    )
    imdb_rating: Optional[float] = Field(default=None, ge=0.0, le=10.0, description="Community IMDb rating")
    year: Optional[int] = Field(default=None, description="Release year")
    genres: List[str] = Field(default_factory=list, description="List of genres")
    directors: List[str] = Field(default_factory=list, description="List of directors")
    runtime_mins: Optional[int] = Field(default=None, ge=1, description="Runtime in minutes")
    status: str = Field(
        default="watchlist",
        description="Status: watched or watchlist"
    )
    notes: str = Field(default="", description="User notes or comments (legacy field)")
    review: str = Field(default="", description="IMDb written user review")
    user_notes: str = Field(default="", description="Personal user notes")
    date_watched: Optional[str] = Field(default=None, description="Date watched in YYYY-MM-DD format")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if v_clean in ("watched", "watchlist"):
            return v_clean
        return "watched" if "watch" in v_clean and "list" not in v_clean else "watchlist"

    def to_firestore_dict(self) -> dict:
        data = self.model_dump()
        # Keep notes in sync for backward compatibility
        if not data.get("notes") and (data.get("review") or data.get("user_notes")):
            parts = []
            if data.get("review"):
                parts.append(f"Review: {data['review']}")
            if data.get("user_notes"):
                parts.append(f"Notes: {data['user_notes']}")
            data["notes"] = " | ".join(parts)
        if not data.get("updated_at"):
            data["updated_at"] = datetime.now(timezone.utc)
        return data


class QuoteModel(BaseModel):
    """Schema for memorable quotes from books, movies, or shows in 'quotes' collection."""
    id: str = Field(..., description="Unique Quote ID (e.g. quote_...)")
    quote_text: str = Field(..., description="The quote or excerpt text")
    source_type: str = Field(default="book", description="Type of source: 'book' or 'media'")
    source_title: str = Field(..., description="Title of the book, movie, or series")
    source_id: Optional[str] = Field(default=None, description="Optional Goodreads Book ID or IMDb Const ID")
    speaker_or_author: str = Field(default="", description="Author name (books) or character name (movies/shows)")
    theme_tags: List[str] = Field(default_factory=list, description="Tags like discipline, uncertainty, habit, courage")
    notes: str = Field(default="", description="Personal reflections, context, or takeaways")
    favorite: bool = Field(default=False, description="Flag for user's all-time favorite quotes")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp of creation/update")

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, v: str) -> str:
        v_clean = v.strip().lower()
        return "media" if any(k in v_clean for k in ("movie", "tv", "film", "series", "media")) else "book"

    def to_firestore_dict(self) -> dict:
        data = self.model_dump()
        if not data.get("updated_at"):
            data["updated_at"] = datetime.now(timezone.utc)
        return data


class PodcastModel(BaseModel):
    """Schema for podcast episodes in the 'podcasts' collection."""
    id: str = Field(..., description="Unique Podcast Episode ID (e.g. pod_...)")
    podcast_name: str = Field(..., description="Name of the podcast show (e.g. Huberman Lab, Lex Fridman)")
    episode_title: str = Field(..., description="Title of the specific episode")
    host: str = Field(default="", description="Podcast host name")
    guest: Optional[str] = Field(default=None, description="Interview guest name if applicable")
    status: str = Field(default="queue", description="Status: 'queue' or 'listened'")
    user_rating: Optional[int] = Field(default=None, ge=1, le=10, description="User rating from 1 to 10")
    topics: List[str] = Field(default_factory=list, description="Topics/concepts covered (e.g. neuroscience, AI)")
    key_takeaways: str = Field(default="", description="Personal notes or main lessons learned")
    episode_url: Optional[str] = Field(default=None, description="Link to episode on Spotify, Apple, or YouTube")
    duration_mins: Optional[int] = Field(default=None, description="Approximate duration in minutes")
    date_listened: Optional[str] = Field(default=None, description="Date listened in YYYY-MM-DD format")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp of creation/update")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        v_clean = v.strip().lower()
        return "listened" if "listen" in v_clean or "done" in v_clean or "heard" in v_clean else "queue"

    def to_firestore_dict(self) -> dict:
        data = self.model_dump()
        if not data.get("updated_at"):
            data["updated_at"] = datetime.now(timezone.utc)
        return data


# ============================================================================
# SENSORY & CONNOISSEUR VAULT MODELS
# (Tea, Coffee, Whiskey, Gin, Wine, Chocolate, Perfume, Watches)
# ============================================================================

class SensoryCategory(str, Enum):
    """Supported luxury, artisanal, and sensory item categories."""
    TEA = "tea"
    COFFEE = "coffee"
    WHISKEY = "whiskey"
    GIN = "gin"
    WINE = "wine"
    CHOCOLATE = "chocolate"
    PERFUME = "perfume"
    WATCH = "watch"


class SensoryStatus(str, Enum):
    """Collection status for sensory/connoisseur items."""
    OWNED = "owned"          # In cellar, cabinet, humidor, or collection
    WISHLIST = "wishlist"    # Want to acquire or sample
    SAMPLED = "sampled"      # Tried at a tasting, flight, or cafe
    FINISHED = "finished"    # Bottle emptied, bag finished, or sample depleted


class SensoryItemModel(BaseModel):
    """
    Schema for sensory goods, luxury items, and tasting journal in 'sensory_vault'.
    Supports tea, whiskey, coffee, gin, wine, chocolate, perfume, and watches.
    """
    id: str = Field(..., description="Unique Item ID (e.g. sens_tea_01, sens_whisk_02)")
    category: str = Field(..., description="Category: tea, coffee, whiskey, gin, wine, chocolate, perfume, watch")
    name: str = Field(..., description="Item or edition name (e.g. Hibiki 21, Baccarat Rouge 540, Yirgacheffe Natural)")
    maker_or_brand: str = Field(..., description="Distillery, roaster, estate, perfumer, watchmaker, or chocolatier")
    origin_or_region: Optional[str] = Field(default=None, description="Terroir, country, or region (e.g. Islay, Grasse, Uji, Oaxaca)")
    vintage_or_year: Optional[str] = Field(default=None, description="Vintage year, batch, or watch reference number")
    status: str = Field(default="owned", description="Status: owned, wishlist, sampled, finished")
    user_rating: Optional[float] = Field(default=None, ge=1.0, le=10.0, description="Personal rating from 1.0 to 10.0")
    flavor_or_scent_notes: List[str] = Field(default_factory=list, description="Tasting wheel tags or olfactory accords (e.g. smoky, peat, bergamot, iris, cacao)")
    specs: Dict[str, Any] = Field(default_factory=dict, description="Domain technical specifications (cask, abv, process, caliber, steep temp, cacao %)")
    review: str = Field(default="", description="Tasting critique, olfactory impression, or horology review")
    personal_notes: str = Field(default="", description="Private notes, cellar bin, purchase price, or serving suggestions")
    price_tier: Optional[str] = Field(default=None, description="Price tier: $, $$, $$$, $$$$, or $$$$$")
    date_experienced: Optional[str] = Field(default=None, description="Date tasted, acquired, or worn in YYYY-MM-DD format")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp of creation/update")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        v_clean = v.strip().lower()
        valid_cats = {c.value for c in SensoryCategory}
        # Normalize common synonyms
        synonyms = {
            "whisky": "whiskey",
            "scotch": "whiskey",
            "bourbon": "whiskey",
            "fragrance": "perfume",
            "cologne": "perfume",
            "scent": "perfume",
            "watches": "watch",
            "timepiece": "watch",
            "horology": "watch",
            "cacao": "chocolate",
            "choc": "chocolate",
        }
        normalized = synonyms.get(v_clean, v_clean)
        if normalized in valid_cats:
            return normalized
        return v_clean

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if "wish" in v_clean or "want" in v_clean:
            return "wishlist"
        if "sample" in v_clean or "tasted" in v_clean or "tried" in v_clean:
            return "sampled"
        if "finish" in v_clean or "empty" in v_clean or "done" in v_clean:
            return "finished"
        return "owned"

    def to_firestore_dict(self) -> dict:
        data = self.model_dump()
        if not data.get("updated_at"):
            data["updated_at"] = datetime.now(timezone.utc)
        return data


# ============================================================================
# RESTAURANTS & FINE DINING MODELS
# ============================================================================

class RestaurantStatus(str, Enum):
    """Dining wishlist & visit tracking status."""
    VISITED = "visited"      # Dined at
    WISHLIST = "wishlist"    # Want to visit / on radar
    BOOKED = "booked"        # Upcoming confirmed reservation


class RestaurantModel(BaseModel):
    """
    Schema for restaurants, cafes, wine bars, and culinary experiences in 'restaurants'.
    """
    id: str = Field(..., description="Unique Restaurant ID (e.g. rest_le_bernardin)")
    name: str = Field(..., description="Name of the restaurant or venue")
    city: str = Field(..., description="City (e.g. Tokyo, Paris, New York, London)")
    neighborhood: Optional[str] = Field(default=None, description="District or area (e.g. Ginza, Mayfair, SoHo, Marais)")
    cuisine: str = Field(..., description="Cuisine type (e.g. Omakase, Modern French, Neo-Bistro, Basque)")
    status: str = Field(default="visited", description="Status: visited, wishlist, booked")
    user_rating: Optional[float] = Field(default=None, ge=1.0, le=10.0, description="Personal rating from 1.0 to 10.0")
    michelin_status: Optional[str] = Field(default=None, description="Michelin distinction: 1-Star, 2-Star, 3-Star, Bib Gourmand, Selected, or None")
    price_tier: Optional[str] = Field(default=None, description="Price tier: $, $$, $$$, or $$$$")
    standout_dishes: List[str] = Field(default_factory=list, description="Memorable dishes, tasting menu highlights, or signature courses")
    notes_and_review: str = Field(default="", description="Detailed food review, wine pairing critique, service & ambiance impressions")
    vibe_tags: List[str] = Field(default_factory=list, description="Atmosphere tags (e.g. romantic, counter seating, late night, natural wine)")
    url_or_reservation: Optional[str] = Field(default=None, description="Link to Resy, OpenTable, TableCheck, or website")
    date_visited: Optional[str] = Field(default=None, description="Date visited in YYYY-MM-DD format")
    updated_at: Optional[datetime] = Field(default=None, description="Timestamp of creation/update")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        v_clean = v.strip().lower()
        if "wish" in v_clean or "radar" in v_clean or "want" in v_clean:
            return "wishlist"
        if "book" in v_clean or "reserv" in v_clean or "upcoming" in v_clean:
            return "booked"
        return "visited"

    def to_firestore_dict(self) -> dict:
        data = self.model_dump()
        if not data.get("updated_at"):
            data["updated_at"] = datetime.now(timezone.utc)
        return data


# ============================================================================
# LONG-TERM PERSONAL MEMORY & AMBIENT CONTEXT MODELS
# ============================================================================

class MemoryCategory(str, Enum):
    """Categorization for long-term personal memories, quirks, and directives."""
    PREFERENCE = "preference"      # General tastes (e.g. "Prefers intimate omakase counter seating")
    DISLIKE = "dislike"            # Strict dislikes/guardrails (e.g. "Dislikes jump-scares and 3D movies")
    GOAL = "goal"                  # Current goals (e.g. "Aiming to read 24 books in 2026")
    HABIT = "habit"                # Routine or pattern (e.g. "Reads late at night, drinks pour-over in morning")
    CONTEXT = "context"            # Temporary or life context (e.g. "Traveling to Tokyo in October 2026")
    DIRECTIVE = "directive"        # Permanent instructions (e.g. "Always suggest 2 book alternatives")


class MemoryModel(BaseModel):
    """
    Schema for personal memories, constraints, and ambient directives in 'personal_memory'.
    """
    id: str = Field(..., description="Unique Memory ID (e.g. mem_pref_a1b2c3)")
    category: str = Field(
        default="preference",
        description="Memory category: preference, dislike, goal, habit, context, directive"
    )
    content: str = Field(..., description="The concrete memory, fact, preference, or instruction to retain")
    tags: List[str] = Field(default_factory=list, description="Descriptive tags for indexing and search")
    importance: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Importance level from 1 (minor quirk) to 5 (critical hard directive)"
    )
    source: str = Field(
        default="user_explicit",
        description="Source of memory: user_explicit, conversation_observation"
    )
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        v_clean = v.strip().lower()
        valid = {c.value for c in MemoryCategory}
        if v_clean in valid:
            return v_clean
        if "dislike" in v_clean or "avoid" in v_clean or "hate" in v_clean:
            return "dislike"
        if "goal" in v_clean or "aim" in v_clean or "target" in v_clean:
            return "goal"
        if "habit" in v_clean or "routine" in v_clean:
            return "habit"
        if "direct" in v_clean or "rule" in v_clean or "instruct" in v_clean:
            return "directive"
        if "context" in v_clean or "trip" in v_clean or "travel" in v_clean or "life" in v_clean:
            return "context"
        return "preference"

    def to_firestore_dict(self) -> dict:
        data = self.model_dump()
        now = datetime.now(timezone.utc)
        if not data.get("created_at"):
            data["created_at"] = now
        data["updated_at"] = now
        return data
