"""
Domain and external API services for life_os_mcp.
"""

from services.base_repository import BaseFirestoreRepository
from services.book_service import BookService
from services.media_service import MediaService
from services.quote_service import QuoteService
from services.podcast_service import PodcastService
from services.restaurant_service import RestaurantService
from services.sensory_service import SensoryService
from services.memory_service import MemoryService
from services.recommendation_service import RecommendationService
from services.pairing_service import PairingService

from services.connoisseur import (
    BaseConnoisseurService,
    WhiskeyService,
    WineService,
    CoffeeService,
    TeaService,
    GinService,
    ChocolateService,
    PerfumeService,
    WatchService,
)

from services.external.books_client import BookMetadataClient
from services.external.tmdb_client import TMDBClient
from services.external.podcasts_client import ApplePodcastsClient
from services.external.catalog_client import ConnoisseurCatalogClient

__all__ = [
    "BaseFirestoreRepository",
    "BookService",
    "MediaService",
    "QuoteService",
    "PodcastService",
    "RestaurantService",
    "SensoryService",
    "MemoryService",
    "RecommendationService",
    "PairingService",
    "BaseConnoisseurService",
    "WhiskeyService",
    "WineService",
    "CoffeeService",
    "TeaService",
    "GinService",
    "ChocolateService",
    "PerfumeService",
    "WatchService",
    "BookMetadataClient",
    "TMDBClient",
    "ApplePodcastsClient",
    "ConnoisseurCatalogClient",
]
