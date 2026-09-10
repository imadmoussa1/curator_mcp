"""
Tea domain service: Loose-Leaf, Matcha, Oolong, Pu-erh, and Brewing Recipes.
"""

from typing import Optional, List, Dict, Any
from services.base_repository import BaseFirestoreRepository
from services.connoisseur.base import BaseConnoisseurService


class TeaService(BaseConnoisseurService):
    """
    Dedicated service for managing fine teas, terroirs, and infusion parameters.
    """

    def __init__(self, repository: Optional[BaseFirestoreRepository] = None):
        super().__init__("tea", repository=repository)

    def log_tea(
        self,
        name: str,
        producer_or_house: str,
        origin_region: Optional[str] = None,
        harvest_year_or_season: Optional[str] = None,
        brew_temp_c: Optional[int] = None,
        steep_time_secs: Optional[int] = None,
        oxidation_level: Optional[str] = None,
        status: str = "owned",
        user_rating: Optional[float] = None,
        flavor_notes: Optional[List[str]] = None,
        review: Optional[str] = "",
        gaiwan_infusion_notes: Optional[str] = "",
        price_tier: Optional[str] = None,
        date_tasted: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Specialized logger for tea leaves with brewing temperature and steep time.
        """
        specs: Dict[str, Any] = {}
        if brew_temp_c:
            specs["brew_temp_c"] = brew_temp_c
        if steep_time_secs:
            specs["steep_time_secs"] = steep_time_secs
        if oxidation_level:
            specs["oxidation"] = oxidation_level.strip()

        return self.log(
            name=name,
            maker_or_brand=producer_or_house,
            origin_or_region=origin_region,
            vintage_or_year=harvest_year_or_season,
            status=status,
            user_rating=user_rating,
            flavor_or_scent_notes=flavor_notes,
            specs=specs,
            review=review,
            personal_notes=gaiwan_infusion_notes,
            price_tier=price_tier,
            date_experienced=date_tasted,
        )
