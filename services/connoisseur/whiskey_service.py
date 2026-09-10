"""
Whiskey domain service: Single Malts, Bourbon, Rye, and World Whiskies.
"""

from typing import Optional, List, Dict, Any
from services.base_repository import BaseFirestoreRepository
from services.connoisseur.base import BaseConnoisseurService


class WhiskeyService(BaseConnoisseurService):
    """
    Dedicated service for managing Whiskey, Scotch, Bourbon, and Rye spirits.
    """

    def __init__(self, repository: Optional[BaseFirestoreRepository] = None):
        super().__init__("whiskey", repository=repository)

    def log_bottle(
        self,
        name: str,
        distillery: str,
        region: Optional[str] = None,
        vintage_or_age: Optional[str] = None,
        cask_finish: Optional[str] = None,
        abv: Optional[str] = None,
        peat_level: Optional[str] = None,
        status: str = "owned",
        user_rating: Optional[float] = None,
        tasting_notes: Optional[List[str]] = None,
        review: Optional[str] = "",
        personal_notes: Optional[str] = "",
        price_tier: Optional[str] = None,
        date_experienced: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Specialized logger for whiskey bottles with cask, abv, and peat specs.
        """
        specs: Dict[str, Any] = {}
        if cask_finish:
            specs["cask"] = cask_finish.strip()
        if abv:
            specs["abv"] = abv.strip()
        if peat_level:
            specs["peat_level"] = peat_level.strip()

        return self.log(
            name=name,
            maker_or_brand=distillery,
            origin_or_region=region,
            vintage_or_year=vintage_or_age,
            status=status,
            user_rating=user_rating,
            flavor_or_scent_notes=tasting_notes,
            specs=specs,
            review=review,
            personal_notes=personal_notes,
            price_tier=price_tier,
            date_experienced=date_experienced,
        )
