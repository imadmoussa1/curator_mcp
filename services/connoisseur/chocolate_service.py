"""
Chocolate domain service: Bean-to-Bar, Single-Origin, and Cacao Profiles.
"""

from typing import Optional, List, Dict, Any
from services.base_repository import BaseFirestoreRepository
from services.connoisseur.base import BaseConnoisseurService


class ChocolateService(BaseConnoisseurService):
    """
    Dedicated service for managing bean-to-bar and artisanal single-origin chocolates.
    """

    def __init__(self, repository: Optional[BaseFirestoreRepository] = None):
        super().__init__("chocolate", repository=repository)

    def log_chocolate(
        self,
        name: str,
        chocolatier_or_maker: str,
        cacao_percentage: int,
        bean_origin: Optional[str] = None,
        cacao_variety: Optional[str] = None,
        conching_notes: Optional[str] = None,
        status: str = "owned",
        user_rating: Optional[float] = None,
        flavor_notes: Optional[List[str]] = None,
        review: Optional[str] = "",
        pairing_notes: Optional[str] = "",
        price_tier: Optional[str] = None,
        date_tasted: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Specialized logger for chocolate bars with cacao percentage and bean variety specs.
        """
        specs: Dict[str, Any] = {"cacao_pct": cacao_percentage}
        if bean_origin:
            specs["bean_origin"] = bean_origin.strip()
        if cacao_variety:
            specs["cacao_variety"] = cacao_variety.strip()
        if conching_notes:
            specs["conching"] = conching_notes.strip()

        return self.log(
            name=name,
            maker_or_brand=chocolatier_or_maker,
            origin_or_region=bean_origin,
            status=status,
            user_rating=user_rating,
            flavor_or_scent_notes=flavor_notes,
            specs=specs,
            review=review,
            personal_notes=pairing_notes,
            price_tier=price_tier,
            date_experienced=date_tasted,
        )
