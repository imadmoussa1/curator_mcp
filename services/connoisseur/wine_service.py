"""
Wine domain service: Fine Wine, Vintages, Varietals, and Cellaring.
"""

from typing import Optional, List, Dict, Any
from services.base_repository import BaseFirestoreRepository
from services.connoisseur.base import BaseConnoisseurService


class WineService(BaseConnoisseurService):
    """
    Dedicated service for managing fine wine, cellars, and vintages.
    """

    def __init__(self, repository: Optional[BaseFirestoreRepository] = None):
        super().__init__("wine", repository=repository)

    def log_wine(
        self,
        name: str,
        producer_or_estate: str,
        region_or_appellation: Optional[str] = None,
        vintage: Optional[str] = None,
        varietal: Optional[str] = None,
        body: Optional[str] = None,
        tannin: Optional[str] = None,
        acidity: Optional[str] = None,
        status: str = "owned",
        user_rating: Optional[float] = None,
        tasting_notes: Optional[List[str]] = None,
        review: Optional[str] = "",
        cellar_location: Optional[str] = "",
        price_tier: Optional[str] = None,
        date_tasted: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Specialized logger for wine bottles with varietal and structure specs.
        """
        specs: Dict[str, Any] = {}
        if varietal:
            specs["varietal"] = varietal.strip()
        if body:
            specs["body"] = body.strip()
        if tannin:
            specs["tannin"] = tannin.strip()
        if acidity:
            specs["acidity"] = acidity.strip()

        return self.log(
            name=name,
            maker_or_brand=producer_or_estate,
            origin_or_region=region_or_appellation,
            vintage_or_year=vintage,
            status=status,
            user_rating=user_rating,
            flavor_or_scent_notes=tasting_notes,
            specs=specs,
            review=review,
            personal_notes=cellar_location,
            price_tier=price_tier,
            date_experienced=date_tasted,
        )
