"""
Gin domain service: Craft Gins, Botanicals, and Distillation Styles.
"""

from typing import Optional, List, Dict, Any
from services.base_repository import BaseFirestoreRepository
from services.connoisseur.base import BaseConnoisseurService


class GinService(BaseConnoisseurService):
    """
    Dedicated service for managing craft gins and botanical spirits.
    """

    def __init__(self, repository: Optional[BaseFirestoreRepository] = None):
        super().__init__("gin", repository=repository)

    def log_gin(
        self,
        name: str,
        distillery: str,
        country_or_region: Optional[str] = None,
        style: Optional[str] = None,
        botanicals: Optional[List[str]] = None,
        abv: Optional[str] = None,
        status: str = "owned",
        user_rating: Optional[float] = None,
        flavor_notes: Optional[List[str]] = None,
        review: Optional[str] = "",
        garnish_and_tonic_notes: Optional[str] = "",
        price_tier: Optional[str] = None,
        date_tasted: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Specialized logger for gins with botanicals, ABV, and style specs.
        """
        specs: Dict[str, Any] = {}
        if style:
            specs["style"] = style.strip()
        if abv:
            specs["abv"] = abv.strip()
        if botanicals:
            specs["botanicals"] = [b.strip() for b in botanicals if b.strip()]

        return self.log(
            name=name,
            maker_or_brand=distillery,
            origin_or_region=country_or_region,
            status=status,
            user_rating=user_rating,
            flavor_or_scent_notes=flavor_notes,
            specs=specs,
            review=review,
            personal_notes=garnish_and_tonic_notes,
            price_tier=price_tier,
            date_experienced=date_tasted,
        )
