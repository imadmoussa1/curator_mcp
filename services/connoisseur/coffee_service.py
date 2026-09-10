"""
Coffee domain service: Specialty Coffee Beans, Roasters, and Brewing.
"""

from typing import Optional, List, Dict, Any
from services.base_repository import BaseFirestoreRepository
from services.connoisseur.base import BaseConnoisseurService


class CoffeeService(BaseConnoisseurService):
    """
    Dedicated service for managing specialty coffee beans, origins, and roasts.
    """

    def __init__(self, repository: Optional[BaseFirestoreRepository] = None):
        super().__init__("coffee", repository=repository)

    def log_beans(
        self,
        name: str,
        roaster: str,
        origin_country_or_farm: Optional[str] = None,
        process_method: Optional[str] = None,
        roast_level: Optional[str] = None,
        altitude_m: Optional[int] = None,
        status: str = "owned",
        user_rating: Optional[float] = None,
        flavor_notes: Optional[List[str]] = None,
        review: Optional[str] = "",
        brewing_recipe_notes: Optional[str] = "",
        price_tier: Optional[str] = None,
        date_roasted_or_tasted: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Specialized logger for coffee beans with process, roast, and altitude specs.
        """
        specs: Dict[str, Any] = {}
        if process_method:
            specs["process"] = process_method.strip()
        if roast_level:
            specs["roast"] = roast_level.strip()
        if altitude_m:
            specs["altitude_m"] = altitude_m

        return self.log(
            name=name,
            maker_or_brand=roaster,
            origin_or_region=origin_country_or_farm,
            vintage_or_year=None,
            status=status,
            user_rating=user_rating,
            flavor_or_scent_notes=flavor_notes,
            specs=specs,
            review=review,
            personal_notes=brewing_recipe_notes,
            price_tier=price_tier,
            date_experienced=date_roasted_or_tasted,
        )
