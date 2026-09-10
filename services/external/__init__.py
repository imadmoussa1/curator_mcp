"""
External API clients for Google Books, Open Library, TMDB, Apple Podcasts, and Connoisseur Catalogs.
"""

from services.external.books_client import BookMetadataClient
from services.external.tmdb_client import TMDBClient
from services.external.podcasts_client import ApplePodcastsClient
from services.external.catalog_client import ConnoisseurCatalogClient

__all__ = [
    "BookMetadataClient",
    "TMDBClient",
    "ApplePodcastsClient",
    "ConnoisseurCatalogClient",
]
