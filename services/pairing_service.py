"""
Multimodal Sensory Pairing Engine:
Cross-domain aesthetic matching bridging literature, cinema, and culinary arts
with sensory connoisseur goods (tea, coffee, whiskey, gin, wine, chocolate, perfume).
"""

from typing import Optional, List, Dict, Any
import re


class PairingService:
    """
    Intelligent aesthetic synthesis engine matching intellectual media (books, films)
    with sensory experiences (beverages, olfactory accords, music, culinary pairings).
    """

    def __init__(
        self,
        book_service: Optional[Any] = None,
        media_service: Optional[Any] = None,
        sensory_service: Optional[Any] = None,
        restaurant_service: Optional[Any] = None,
    ):
        self.book_service = book_service
        self.media_service = media_service
        self.sensory_service = sensory_service
        self.restaurant_service = restaurant_service

    def _get_owned_sensory_items(self) -> List[Dict[str, Any]]:
        """Retrieve items the user currently has in their sensory vault."""
        if not self.sensory_service:
            return []
        return [it for it in self.sensory_service.stream_all() if it.get("status") in ("owned", "cellared")]

    def get_pairing_for_book(
        self,
        title: str,
        author: Optional[str] = None,
        mood: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate an aesthetic multimodal pairing for a book reading session.
        Combines beverage (tea, coffee, or spirit), ambient fragrance accord,
        dark chocolate pairing, and acoustic sonic atmosphere.
        """
        t_clean = title.lower().strip()
        a_clean = (author or "").lower().strip()
        m_clean = (mood or "").lower().strip()

        # Genre & Tone Detection Archetypes
        is_scifi_cyberpunk = any(k in t_clean or k in a_clean or k in m_clean for k in ("dune", "neuromancer", "cyber", "sci-fi", "blade", "foundation", "space", "future", "asimov", "dick"))
        is_japanese_zen = any(k in t_clean or k in a_clean or k in m_clean for k in ("murakami", "japan", "zen", "stoic", "meditations", "seneca", "aurelius", "haiku", "calm", "norwegian wood"))
        is_noir_crime = any(k in t_clean or k in a_clean or k in m_clean for k in ("noir", "detective", "crime", "thriller", "dark", "shadow", "chandler", "mystery", "sleep", "hammett"))
        is_classical_epic = any(k in t_clean or k in a_clean or k in m_clean for k in ("tolstoy", "dostoevsky", "classic", "history", "war", "peace", "odyssey", "homer", "marquez"))

        owned = self._get_owned_sensory_items()

        if is_scifi_cyberpunk:
            beverage = {
                "category": "tea" if "tea" in m_clean else "whiskey",
                "recommendation": "Smoky Lapsang Souchong or Peated Islay Single Malt (Lagavulin 16)",
                "tasting_notes": ["peat", "pine smoke", "dark fruit", "subtle sweetness"],
                "rationale": "The brooding smoke and mineral austerity echo futuristic industrial landscapes and sweeping desert expanses.",
            }
            fragrance = {
                "fragrance_name": "Tom Ford Oud Wood or Comme des Garçons Black",
                "olfactory_accords": ["smoky oud", "incense", "tar", "cedarwood"],
                "atmosphere": "Atmospheric, cerebral, and contemplative late-night immersion.",
            }
            chocolate = "85% Single-Origin Ecuador Dark Chocolate (earthy and smoky)."
            music = "Analog synth, Vangelis, or ambient drone soundscapes."

        elif is_japanese_zen:
            beverage = {
                "category": "tea" if "coffee" not in m_clean else "coffee",
                "recommendation": "Kyoto Uji Gyokuro or Light-Roast Ethiopian Yirgacheffe (Anaerobic Natural)",
                "tasting_notes": ["umami", "delicate florals", "peach nectar", "jasmine"],
                "rationale": "Clean, meditative clarity that sharpens cognitive focus without overwhelming sensory palate.",
            }
            fragrance = {
                "fragrance_name": "Diptyque Tam Dao or Le Labo Hinoki",
                "olfactory_accords": ["hinoki cypress", "mysore sandalwood", "white musk"],
                "atmosphere": "Serene cedar temple gardens and soft natural light.",
            }
            chocolate = "Matcha-infused single-origin white chocolate or 70% Criollo."
            music = "Solo piano (Ryuichi Sakamoto, Keith Jarrett) or ambient jazz."

        elif is_noir_crime:
            beverage = {
                "category": "whiskey",
                "recommendation": "Cask-Strength Bourbon or Speyside Single Malt in Sherry Casks (Aberlour A'bunadh)",
                "tasting_notes": ["dried fig", "leather", "toasted oak", "cinnamon spice"],
                "rationale": "High-proof warmth and deep amber sweetness cut through nocturnal intrigue and sharp tension.",
            }
            fragrance = {
                "fragrance_name": "Maison Margiela Jazz Club or BDK Gris Charnel",
                "olfactory_accords": ["tobacco leaf", "rum absolute", "vanilla bean", "pink pepper"],
                "atmosphere": "Rain-slicked streets, dim amber desk lamps, and velvet armchairs.",
            }
            chocolate = "72% Madagascar Dark Chocolate with sea salt."
            music = "Muted trumpet, cool jazz, Miles Davis (*Kind of Blue*)."

        elif is_classical_epic:
            beverage = {
                "category": "wine",
                "recommendation": "Full-Bodied Barolo or Aged Bordeaux (Cabernet Sauvignon blend)",
                "tasting_notes": ["tar", "dried roses", "black cherry", "earthy forest floor"],
                "rationale": "Stately tannins and architectural depth mirror sweeping historical drama and generational sagas.",
            }
            fragrance = {
                "fragrance_name": "Frederic Malle Portrait of a Lady",
                "olfactory_accords": ["turkish rose", "patchouli", "frankincense", "blackcurrant"],
                "atmosphere": "Aristocratic salons, gilded libraries, and old leather bindings.",
            }
            chocolate = "75% Venezuela Single Origin with toasted hazelnuts."
            music = "Chamber strings, Bach Cello Suites, or Rachmaninoff."

        else:
            beverage = {
                "category": "coffee",
                "recommendation": "Panamanian Geisha Pour-Over or Light Roasted Colombia Gesha",
                "tasting_notes": ["bergamot", "white peach", "candied citrus", "silky tea finish"],
                "rationale": "Vibrant acidity and aromatic brightness enhance reading comprehension and thoughtful leisure.",
            }
            fragrance = {
                "fragrance_name": "Maison Francis Kurkdjian Grand Soir or Byredo Gypsy Water",
                "olfactory_accords": ["amber", "vanilla", "bergamot", "pine needles"],
                "atmosphere": "Warm afternoon natural sunlight and cozy quietness.",
            }
            chocolate = "70% Single Origin Dominican Republic."
            music = "Acoustic folk, instrumental post-rock, or soft lo-fi."

        # Check if user has any matches in their own cellar/cabinet
        vault_matches = []
        for it in owned:
            if it.get("category") == beverage["category"]:
                vault_matches.append(f"{it.get('name')} by {it.get('maker_or_brand')}")

        return {
            "status": "success",
            "anchor": {"type": "book", "title": title, "author": author or "Unknown"},
            "beverage_pairing": beverage,
            "owned_cellar_alternatives": vault_matches[:3],
            "fragrance_atmosphere": fragrance,
            "chocolate_pairing": chocolate,
            "sonic_ambiance": music,
        }

    def get_pairing_for_media(
        self,
        title: str,
        media_type: str = "movie",
        mood: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate an atmospheric cocktail/spirit and sensory pairing for a film screening.
        """
        t_clean = title.lower().strip()
        m_clean = (mood or "").lower().strip()

        is_thriller_or_dark = any(k in t_clean or k in m_clean for k in ("shutter", "fincher", "se7en", "thriller", "dark", "batman", "crime", "detective"))
        is_scifi = any(k in t_clean or k in m_clean for k in ("interstellar", "2049", "blade", "matrix", "alien", "arrival", "sci-fi"))
        is_lighthearted_or_comedy = any(k in t_clean or k in m_clean for k in ("comedy", "wes anderson", "romance", "paris", "summer", "light", "quirky"))

        if is_scifi:
            spirit = "Japanese Whisky (Yamazaki 12) or Botanical Dry Gin Cocktail"
            scent = "Metallic amber, incense, and cedarwood"
            snack = "Smoked sea salt popcorn or 72% single-origin dark cacao nibs"
        elif is_thriller_or_dark:
            spirit = "Smoky Islay Scotch on the rocks (Lagavulin or Laphroaig)"
            scent = "Black pepper, birch tar, and leather"
            snack = "Charcuterie with aged prosciutto and sharp pecorino"
        elif is_lighthearted_or_comedy:
            spirit = "French 75 (Gin, Champagne, Lemon) or Pet-Nat Sparkling Wine"
            scent = "Sparkling bergamot, neroli, and white florals"
            snack = "Truffle parmesan crisps or candied citrus peel"
        else:
            spirit = "Classic Old Fashioned with aromatic bitters and orange twist"
            scent = "Amber, tonka bean, and roasted vanilla"
            snack = "Roasted rosemary marcona almonds"

        return {
            "status": "success",
            "anchor": {"type": "media", "title": title, "media_type": media_type},
            "cocktail_or_spirit_pairing": spirit,
            "ambient_fragrance": scent,
            "tasting_accompaniment": snack,
            "viewing_ritual": "Dim lights to warm amber (2200K), silence phone notifications, sip slowly during opening sequence.",
        }

    def get_pairing_for_dish(
        self,
        dish_or_cuisine: str,
        dining_style: Optional[str] = "dinner",
    ) -> Dict[str, Any]:
        """
        Suggest wine, tea, or craft cocktail pairings for a dish or restaurant course.
        """
        dish_clean = dish_or_cuisine.lower().strip()

        if any(k in dish_clean for k in ("sushi", "omakase", "raw fish", "sashimi", "crudo")):
            pairing = "Junmai Daiginjo Sake, Chablis (Chardonnay), or Cold-Brewed Gyokuro green tea"
            notes = "Mineral acidity and pristine elegance highlight delicate fish fats without overpowering."
        elif any(k in dish_clean for k in ("steak", "beef", "wagyu", "lamb", "game", "ribeye", "meat", "sirloin", "tenderloin")):
            pairing = "Full-bodied Cabernet Sauvignon, Syrah from Northern Rhône, or High-Proof Bourbon"
            notes = "Bold tannins bind to rich savory fats and char, unlocking umami depth."
        elif any(k in dish_clean for k in ("pasta", "truffle", "mushroom", "risotto")):
            pairing = "Piedmont Nebbiolo (Barolo), aged Pinot Noir, or roasted Oolong tea"
            notes = "Earthy autumn forest floor notes mirror mushroom and truffle terpenes."
        else:
            pairing = "Crisp Dry Riesling, Natural Pet-Nat, or Sparkling Mineral Water with Yuzu"
            notes = "Bright versatile acidity cleanses palate between varied bites."

        return {
            "status": "success",
            "dish": dish_or_cuisine,
            "dining_style": dining_style,
            "recommended_pairing": pairing,
            "tasting_notes": notes,
        }
