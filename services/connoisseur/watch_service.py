"""
Watch domain service: Luxury Timepieces, Horology, Movements, and Calibers.
"""

from typing import Optional, List, Dict, Any
from services.base_repository import BaseFirestoreRepository
from services.connoisseur.base import BaseConnoisseurService


class WatchService(BaseConnoisseurService):
    """
    Dedicated service for managing luxury watches, reference numbers, and horology specs.
    """

    def __init__(self, repository: Optional[BaseFirestoreRepository] = None):
        super().__init__("watch", repository=repository)

    def log_timepiece(
        self,
        name: str,
        watchmaker_or_brand: str,
        reference_number: Optional[str] = None,
        movement_type: Optional[str] = None,
        caliber: Optional[str] = None,
        case_size_mm: Optional[int] = None,
        power_reserve_hrs: Optional[int] = None,
        water_resistance: Optional[str] = None,
        complications: Optional[List[str]] = None,
        status: str = "owned",
        user_rating: Optional[float] = None,
        tags: Optional[List[str]] = None,
        review: Optional[str] = "",
        provenance_notes: Optional[str] = "",
        price_tier: Optional[str] = None,
        date_acquired: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Specialized logger for watches with reference number, caliber, and case diameter.
        """
        specs: Dict[str, Any] = {}
        if movement_type:
            specs["movement_type"] = movement_type.strip()
        if caliber:
            specs["caliber"] = caliber.strip()
        if case_size_mm:
            specs["case_size_mm"] = case_size_mm
        if power_reserve_hrs:
            specs["power_reserve_hrs"] = power_reserve_hrs
        if water_resistance:
            specs["water_resistance"] = water_resistance.strip()
        if complications:
            specs["complications"] = [c.strip() for c in complications if c.strip()]

        return self.log(
            name=name,
            maker_or_brand=watchmaker_or_brand,
            vintage_or_year=reference_number,
            status=status,
            user_rating=user_rating,
            flavor_or_scent_notes=tags,
            specs=specs,
            review=review,
            personal_notes=provenance_notes,
            price_tier=price_tier,
            date_experienced=date_acquired,
        )
