"""
Data schemas and models for life_os_mcp using Pydantic.
Validates books, media, quotes, and podcasts entries before writing to Firestore.
"""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class BookModel(BaseModel):
    """Schema for books in the Firestore 'books' collection."""
    id: str = Field(..., description="Goodreads Book ID (string)")
    title: str = Field(..., description="Book title")
    author: str = Field(..., description="Book author name")
    user_rating: int = Field(default=0, ge=0, le=5, description="User rating from 0 (unrated) to 5 stars")
    avg_rating: float = Field(default=0.0, ge=0.0, le=5.0, description="Community average rating")
    shelf: str = Field(
        default="to-read",
        description="Reading status shelf: read, currently-reading, to-read"
    )
    notes_and_reviews: str = Field(default="", description="User notes or review text")
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
        if not data.get("updated_at"):
            data["updated_at"] = datetime.now(timezone.utc)
        return data


class MediaModel(BaseModel):
    """Schema for movies & series in the Firestore 'media' collection."""
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
        description="User rating from 1 to 10 (nullable if unrated watchlist item)"
    )
    imdb_rating: Optional[float] = Field(default=None, ge=0.0, le=10.0, description="Community IMDb rating")
    year: Optional[int] = Field(default=None, description="Release year")
    genres: List[str] = Field(default_factory=list, description="List of genres")
    directors: List[str] = Field(default_factory=list, description="List of directors")
    status: str = Field(
        default="watchlist",
        description="Status: watched or watchlist"
    )
    notes: str = Field(default="", description="User notes or comments")
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
