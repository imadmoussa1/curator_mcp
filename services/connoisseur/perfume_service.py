"""
Perfume domain service: Fragrances, Niche Scents, and Olfactory Pyramids.
"""

from typing import Optional, List, Dict, Any
from services.base_repository import BaseFirestoreRepository
from services.connoisseur.base import BaseConnoisseurService


class PerfumeService(BaseConnoisseurService):
    """
    Dedicated service for managing fragrances, niche extraits, and olfactory accords.
    """

    def __init__(self, repository: Optional[BaseFirestoreRepository] = None):
        super().__init__("perfume", repository=repository)

    def log_fragrance(
        self,
        name: str,
        house_or_perfumer: str,
        concentration: Optional[str] = "Eau de Parfum",
        top_notes: Optional[str] = None,
        heart_notes: Optional[str] = None,
        base_notes: Optional[str] = None,
        sillage: Optional[str] = None,
        longevity_hrs: Optional[int] = None,
        season_suitability: Optional[str] = None,
        status: str = "owned",
        user_rating: Optional[float] = None,
        accords: Optional[List[str]] = None,
        review: Optional[str] = "",
        wearing_notes: Optional[str] = "",
        price_tier: Optional[str] = None,
        date_acquired: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Specialized logger for fragrances with olfactory pyramid (top/heart/base) and concentration.
        """
        specs: Dict[str, Any] = {}
        if concentration:
            specs["concentration"] = concentration.strip()
        if top_notes:
            specs["top_notes"] = top_notes.strip()
        if heart_notes:
            specs["heart_notes"] = heart_notes.strip()
        if base_notes:
            specs["base_notes"] = base_notes.strip()
        if sillage:
            specs["sillage"] = sillage.strip()
        if longevity_hrs:
            specs["longevity_hrs"] = longevity_hrs
        if season_suitability:
            specs["season"] = season_suitability.strip()

        return self.log(
            name=name,
            maker_or_brand=house_or_perfumer,
            status=status,
            user_rating=user_rating,
            flavor_or_scent_notes=accords,
            specs=specs,
            review=review,
            personal_notes=wearing_notes,
            price_tier=price_tier,
            date_experienced=date_acquired,
        )
