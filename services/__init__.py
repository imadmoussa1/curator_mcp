"""
Domain and external API services for life_os_mcp.
"""

from services.base_repository import BaseFirestoreRepository
from services.book_service import BookService
from services.media_service import MediaService
from services.quote_service import QuoteService
from services.podcast_service import PodcastService
from services.recommendation_service import RecommendationService
from services.external.books_client import BookMetadataClient
from services.external.tmdb_client import TMDBClient
from services.external.podcasts_client import ApplePodcastsClient

__all__ = [
    "BaseFirestoreRepository",
    "BookService",
    "MediaService",
    "QuoteService",
    "PodcastService",
    "RecommendationService",
    "BookMetadataClient",
    "TMDBClient",
    "ApplePodcastsClient",
]
