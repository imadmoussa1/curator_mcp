"""
Data schemas and models for life_os_mcp using Pydantic.
Validates books and media entries before writing to Firestore.
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
