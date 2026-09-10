"""
Recommendation and taste profiling engine.
Synthesizes user ratings across Firestore and queries external APIs with automatic library deduplication.
"""

import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from collections import Counter
from google.cloud.firestore_v1.base_query import FieldFilter

from services.book_service import BookService
from services.media_service import MediaService
from services.external.books_client import BookMetadataClient
from services.external.tmdb_client import TMDBClient


class RecommendationService:
    """
    Intelligent recommendation and taste profiling service.
    """

    def __init__(
        self,
        book_service: BookService,
        media_service: MediaService,
        books_client: BookMetadataClient,
        tmdb_client: TMDBClient,
        quote_service: Optional[Any] = None,
        podcast_service: Optional[Any] = None,
        sensory_service: Optional[Any] = None,
        restaurant_service: Optional[Any] = None,
    ):
        self.book_service = book_service
        self.media_service = media_service
        self.books_client = books_client
        self.tmdb_client = tmdb_client
        self.quote_service = quote_service
        self.podcast_service = podcast_service
        self.sensory_service = sensory_service
        self.restaurant_service = restaurant_service

    def get_taste_profile(self) -> Dict[str, Any]:
        """
        Synthesize user taste preferences across books and media.
        Identifies top authors, directors, and genres from items rated 4+ stars or 8+ out of 10.
        """
        # Books (rated >= 4)
        top_books = []
        author_counts = Counter()
        for doc in self.book_service.collection.where(filter=FieldFilter("user_rating", ">=", 4)).stream():
            b = doc.to_dict()
            top_books.append({
                "title": b.get("title"),
                "author": b.get("author"),
                "user_rating": b.get("user_rating"),
                "notes": b.get("notes_and_reviews") or ""
            })
            if b.get("author"):
                author_counts[b["author"]] += 1

        # Media (rated >= 8)
        top_media = []
        genre_counts = Counter()
        director_counts = Counter()
        for doc in self.media_service.collection.where(filter=FieldFilter("user_rating", ">=", 8)).stream():
            m = doc.to_dict()
            top_media.append({
                "title": m.get("title"),
                "media_type": m.get("media_type"),
                "user_rating": m.get("user_rating"),
                "imdb_rating": m.get("imdb_rating"),
                "genres": m.get("genres", []),
                "directors": m.get("directors", [])
            })
            for g in m.get("genres", []):
                genre_counts[g] += 1
            for d in m.get("directors", []):
                director_counts[d] += 1

        return {
            "status": "success",
            "taste_summary": {
                "top_genres": [g for g, _ in genre_counts.most_common(5)],
                "top_directors": [d for d, _ in director_counts.most_common(5)],
                "top_authors": [a for a, _ in author_counts.most_common(5)],
            },
            "favorite_books_sample": top_books[:10],
            "favorite_media_sample": top_media[:10],
            "total_highly_rated_books": len(top_books),
            "total_highly_rated_media": len(top_media),
        }

    def get_smart_recommendations(
        self,
        category: str = "all",
        limit: int = 5,
        mood: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate personalized, taste-weighted recommendations synthesized from the user's
        viewing and reading history. Uses multi-signal ranking:
        1. Top favorites (10/10 and 9/10 media, 5-star books) as primary recommendation seeds
        2. Recency weighting (giving higher relevance to recent obsessions and genres)
        3. Genre affinity scoring based on user's highest rated categories
        4. Automatic exclusion of everything already watched, read, or queued
        5. Detailed AI explanation ('why_you_will_love_this') for each curated pick
        """
        recommendations: Dict[str, Any] = {"status": "success"}

        # Full inventory sets for strict deduplication
        all_books_docs = self.book_service.stream_all()
        all_media_docs = self.media_service.stream_all()

        existing_books = {
            (b.get("title") or "").lower().strip()
            for b in all_books_docs
            if b.get("title")
        }
        existing_media = {
            (m.get("title") or "").lower().strip()
            for m in all_media_docs
            if m.get("title")
        }

        # 1. Book recommendations
        if category in ("books", "all"):
            # Rank user's read books by rating desc, then recency
            rated_books = [
                b for b in all_books_docs
                if (b.get("user_rating") or 0) >= 4 and b.get("title")
            ]
            rated_books.sort(
                key=lambda x: (x.get("user_rating") or 0, x.get("date_read") or "1970-01-01"),
                reverse=True
            )

            # Extract user's top authors to compute affinity
            top_authors = Counter([b.get("author") for b in rated_books if b.get("author")])
            favorite_author_names = {a for a, _ in top_authors.most_common(5)}

            book_seeds = rated_books[:4]
            book_recs = []

            for seed in book_seeds:
                seed_title = seed.get("title", "")
                author = seed.get("author", "")
                user_rating = seed.get("user_rating", 5)

                sim = self.books_client.find_similar(seed_title, author=author, limit=4)
                for r in sim.get("recommendations", []):
                    r_title = r.get("title", "").strip()
                    r_author = r.get("author", "").strip()
                    if not r_title or r_title.lower() in existing_books:
                        continue
                    if any(r_title.lower() == br["title"].lower() for br in book_recs):
                        continue

                    # Calculate personalization match score
                    match_score = 85
                    reasons = [f"Because you rated '{seed_title}' {user_rating}/5 stars"]
                    if r_author in favorite_author_names:
                        match_score += 10
                        reasons.append(f"Written by {r_author}, one of your top authors")
                    if r.get("average_rating") and r.get("average_rating") >= 4.0:
                        match_score += 4
                        reasons.append(f"Strong community consensus ({r.get('average_rating')}/5.0)")

                    r["inspired_by"] = seed_title
                    r["affinity_match_score"] = f"{min(99, match_score)}%"
                    r["why_you_will_love_this"] = " • ".join(reasons)
                    book_recs.append(r)

                    if len(book_recs) >= limit:
                        break
                if len(book_recs) >= limit:
                    break

            recommendations["book_recommendations"] = book_recs[:limit]

        # 2. Media recommendations (Movies & TV)
        if category in ("movies", "tv", "all"):
            # Filter watched media rated 8-10
            watched_media = [
                m for m in all_media_docs
                if m.get("status") == "watched" and (m.get("user_rating") or 0) >= 8 and m.get("title")
            ]
            # Sort by user rating descending, then year
            watched_media.sort(
                key=lambda x: (x.get("user_rating") or 0, x.get("year") or 0),
                reverse=True
            )

            # Analyze user's favorite genres and directors
            user_genres = Counter()
            user_directors = Counter()
            for m in watched_media:
                for g in m.get("genres", []):
                    user_genres[g.lower()] += 1
                for d in m.get("directors", []):
                    user_directors[d.lower()] += 1

            top_fav_genres = {g for g, _ in user_genres.most_common(4)}
            top_fav_directors = {d for d, _ in user_directors.most_common(4)}

            media_seeds = watched_media[:5]
            media_recs = []

            for seed in media_seeds:
                seed_title = seed.get("title", "")
                user_rating = seed.get("user_rating", 10)
                m_type = "movie" if "movie" in (seed.get("media_type") or "movie").lower() else "tv"

                sim = self.tmdb_client.find_similar(seed_title, media_type=m_type, limit=4)
                for r in sim.get("recommendations", []):
                    r_title = r.get("title", "").strip()
                    if not r_title or r_title.lower() in existing_media:
                        continue
                    if any(r_title.lower() == mr["title"].lower() for mr in media_recs):
                        continue

                    # Calculate personalization match score & AI reasoning
                    match_score = 86
                    reasons = [f"Because you rated '{seed_title}' {user_rating}/10"]

                    rec_genres = [g.lower() for g in r.get("genres", [])]
                    shared_genres = [g.capitalize() for g in rec_genres if g in top_fav_genres]
                    if shared_genres:
                        match_score += 7
                        reasons.append(f"Matches your high affinity for {', '.join(shared_genres)}")

                    vote_avg = r.get("vote_average") or 0.0
                    if vote_avg >= 8.0:
                        match_score += 5
                        reasons.append(f"Acclaimed by viewers ({round(vote_avg, 1)}/10 on TMDB)")

                    r["inspired_by"] = seed_title
                    r["affinity_match_score"] = f"{min(99, match_score)}%"
                    r["why_you_will_love_this"] = " • ".join(reasons)
                    media_recs.append(r)

                    if len(media_recs) >= limit:
                        break
                if len(media_recs) >= limit:
                    break

            recommendations["media_recommendations"] = media_recs[:limit]

        return recommendations

    def generate_cultural_wrapped(self, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Synthesizes an all-in-one personal 'Curator Wrapped' annual retrospective across:
        - Books read and rated in the target year
        - Movies & series watched in the target year
        - Podcasts listened to in the target year
        - Memorable quotes & mental models collected
        - Synthesized 'Cultural Archetype' persona
        """
        target_year = year or datetime.now().year
        year_str = str(target_year)

        # 1. Books in year
        books_in_year = []
        book_ratings = []
        book_authors = Counter()
        for b in self.book_service.stream_all():
            d_read = b.get("date_read") or ""
            # Match specific year, or all read books if year is not provided
            if d_read.startswith(year_str) or (b.get("shelf") == "read" and year is None):
                books_in_year.append(b)
                if b.get("user_rating"):
                    book_ratings.append(b["user_rating"])
                if b.get("author"):
                    book_authors[b["author"]] += 1

        books_in_year.sort(key=lambda x: x.get("user_rating") or 0, reverse=True)
        avg_book_rating = round(sum(book_ratings) / len(book_ratings), 2) if book_ratings else None

        # 2. Media in year
        media_in_year = []
        media_ratings = []
        genres_in_year = Counter()
        directors_in_year = Counter()
        for m in self.media_service.stream_all():
            if m.get("status") != "watched":
                continue
            notes = m.get("notes") or ""
            match = re.search(r"Rated on (\d{4})-\d{2}-\d{2}", notes)
            date_rated = match.group(1) if match else ""
            if date_rated.startswith(year_str) or year is None:
                media_in_year.append(m)
                if m.get("user_rating"):
                    media_ratings.append(m["user_rating"])
                for g in m.get("genres", []):
                    genres_in_year[g] += 1
                for d in m.get("directors", []):
                    directors_in_year[d] += 1

        media_in_year.sort(key=lambda x: x.get("user_rating") or 0, reverse=True)
        avg_media_rating = round(sum(media_ratings) / len(media_ratings), 2) if media_ratings else None

        # 3. Quotes & Mental Models
        quotes_list = []
        quote_themes = Counter()
        if self.quote_service:
            for q in self.quote_service.stream_all():
                quotes_list.append(q)
                for tag in q.get("theme_tags", []):
                    quote_themes[tag.lower()] += 1

        # 4. Podcasts
        podcasts_in_year = []
        pod_topics = Counter()
        if self.podcast_service:
            for p in self.podcast_service.stream_all():
                p_date = p.get("date_listened") or ""
                if p_date.startswith(year_str) or p.get("status") == "listened":
                    podcasts_in_year.append(p)
                    for topic in p.get("topics", []):
                        pod_topics[topic.lower()] += 1

        # 5. Synthesize Cultural Archetype
        top_genres = [g for g, _ in genres_in_year.most_common(3)]
        top_themes = [t for t, _ in quote_themes.most_common(3)]

        if "Sci-Fi" in top_genres and any(t in top_themes for t in ("stoicism", "discipline", "mindset")):
            archetype = "The Cybernetic Stoic"
            desc = "You balance futuristic imagination and visionary cinema with rigorous personal philosophy and mental discipline."
        elif "Drama" in top_genres or "Crime" in top_genres:
            archetype = "The Inquisitive Realist"
            desc = "Drawn to human psychology, moral dilemmas, and intense character-driven narratives."
        elif "Comedy" in top_genres or "Romance" in top_genres:
            archetype = "The Classical Humanist"
            desc = "Appreciating timeless wit, human connection, and witty storytelling across the golden eras."
        else:
            archetype = "The Renaissance Polymath"
            desc = "A diverse intellectual appetite that moves seamlessly between cinema, literature, and deep ideas."

        return {
            "status": "success",
            "year": target_year,
            "cultural_archetype": {
                "title": archetype,
                "summary": desc,
            },
            "summary_metrics": {
                "total_books_read": len(books_in_year),
                "avg_book_rating": avg_book_rating,
                "total_media_watched": len(media_in_year),
                "avg_media_rating": avg_media_rating,
                "total_podcasts_listened": len(podcasts_in_year),
                "total_quotes_collected": len(quotes_list),
            },
            "top_genres": [g for g, _ in genres_in_year.most_common(5)],
            "top_directors": [d for d, _ in directors_in_year.most_common(5)],
            "top_authors": [a for a, _ in book_authors.most_common(5)],
            "top_philosophies_and_themes": [t for t, _ in quote_themes.most_common(5)],
            "masterpieces_and_favorites": {
                "top_books": [
                    {"title": b.get("title"), "author": b.get("author"), "rating": f"{b.get('user_rating')}★"}
                    for b in books_in_year[:5] if b.get("user_rating", 0) >= 4
                ],
                "top_films": [
                    {"title": m.get("title"), "year": m.get("year"), "rating": f"{m.get('user_rating')}/10"}
                    for m in media_in_year[:5] if m.get("user_rating", 0) >= 8
                ]
            }
        }

    # ========================================================================
    # SENSORY & CONNOISSEUR RECOMMENDATIONS
    # ========================================================================

    def get_sensory_taste_profile(self) -> Dict[str, Any]:
        """
        Aggregate connoisseur flavor profiles, olfactory accords, and luxury preferences.
        """
        if not self.sensory_service:
            return {"status": "error", "message": "SensoryService not configured."}

        items = self.sensory_service.stream_all()
        top_items = [it for it in items if (it.get("user_rating") or 0) >= 8.0]
        notes_counter = Counter()
        makers_counter = Counter()
        origins_counter = Counter()
        category_breakdown = Counter()

        for it in top_items:
            category_breakdown[it.get("category", "unknown")] += 1
            if it.get("maker_or_brand"):
                makers_counter[it["maker_or_brand"]] += 1
            if it.get("origin_or_region"):
                origins_counter[it["origin_or_region"]] += 1
            for note in it.get("flavor_or_scent_notes", []):
                notes_counter[note.lower()] += 1

        return {
            "status": "success",
            "total_items_in_vault": len(items),
            "highly_rated_count": len(top_items),
            "top_flavor_and_scent_accords": [n for n, _ in notes_counter.most_common(10)],
            "favorite_makers_or_distilleries": [m for m, _ in makers_counter.most_common(6)],
            "preferred_origins_and_regions": [o for o, _ in origins_counter.most_common(6)],
            "categories_explored": dict(category_breakdown),
            "highlight_masterpieces": [
                {
                    "name": it.get("name"),
                    "maker": it.get("maker_or_brand"),
                    "category": it.get("category"),
                    "rating": f"{it.get('user_rating')}/10",
                    "notes": it.get("flavor_or_scent_notes", []),
                }
                for it in top_items[:8]
            ],
        }

    def get_sensory_recommendations(
        self,
        category: Optional[str] = None,
        mood: Optional[str] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Synthesize smart tasting and luxury recommendations based on user's highest rated flavor notes,
        proven makers, and olfactory profiles.
        """
        if not self.sensory_service:
            return {"status": "error", "message": "SensoryService not configured."}

        items = self.sensory_service.stream_all()
        cat_norm = category.lower().strip() if category else None

        # Filter by category if specified
        relevant_items = [it for it in items if not cat_norm or it.get("category") == cat_norm]
        top_items = [it for it in relevant_items if (it.get("user_rating") or 0) >= 8.0] or relevant_items

        top_notes = Counter()
        favorite_makers = set()
        for it in top_items:
            if it.get("maker_or_brand"):
                favorite_makers.add(it["maker_or_brand"])
            for note in it.get("flavor_or_scent_notes", []):
                top_notes[note.lower()] += 1

        primary_accords = [n for n, _ in top_notes.most_common(6)]

        # Curated taste seeds by category
        catalogs: Dict[str, List[Dict[str, Any]]] = {
            "whiskey": [
                {"name": "Lagavulin 16 Year Old", "maker": "Lagavulin", "origin": "Islay, Scotland", "notes": ["peat", "smoke", "sea salt", "sherry wood", "rich dried fruit"]},
                {"name": "Springbank 15", "maker": "Springbank", "origin": "Campbeltown, Scotland", "notes": ["dunnage warehouse", "toffee", "maritime", "subtle smoke", "leather"]},
                {"name": "Glendronach 18 Allardice", "maker": "Glendronach", "origin": "Highlands, Scotland", "notes": ["oloroso sherry", "dark chocolate", "orange peel", "walnut"]},
                {"name": "Yamazaki 12 Year", "maker": "Suntory", "origin": "Osaka, Japan", "notes": ["mizunara oak", "persimmon", "peach", "clove", "candied orange"]},
                {"name": "Redbreast 12 Cask Strength", "maker": "Midleton", "origin": "Cork, Ireland", "notes": ["pot still spice", "creamy vanilla", "dried fruits", "toasted oak"]},
            ],
            "gin": [
                {"name": "Monkey 47 Schwarzwald Dry", "maker": "Black Forest Distillers", "origin": "Germany", "notes": ["lingonberries", "spruce", "complex botanicals", "juniper", "citrus"]},
                {"name": "The Botanist Islay Dry", "maker": "Bruichladdich", "origin": "Islay, Scotland", "notes": ["foraged florals", "chamomile", "thistle", "crisp citrus", "herbal"]},
                {"name": "Ki No Bi Kyoto Dry Gin", "maker": "Kyoto Distillery", "origin": "Kyoto, Japan", "notes": ["yuzu", "sansho pepper", "gyokuro tea", "hinoki cypress"]},
                {"name": "Hendrick's Neptunia", "maker": "Hendrick's", "origin": "Girvan, Scotland", "notes": ["coastal botanicals", "cucumber", "rose", "sea breeze"]},
            ],
            "wine": [
                {"name": "Barolo Monprivato", "maker": "Giuseppe Mascarello", "origin": "Piedmont, Italy", "notes": ["tar and roses", "red cherry", "truffle", "refined tannins", "mineral"]},
                {"name": "Gevrey-Chambertin", "maker": "Domaine Armand Rousseau", "origin": "Burgundy, France", "notes": ["pinot noir", "forest floor", "wild strawberry", "spice", "silky"]},
                {"name": "Viña Tondonia Reserva", "maker": "R. López de Heredia", "origin": "Rioja, Spain", "notes": ["tempranillo", "cigar box", "dried cherry", "vanilla", "balsamic"]},
                {"name": "Cornas 'Reynard'", "maker": "Thierry Allemand", "origin": "Northern Rhône, France", "notes": ["syrah", "crushed black pepper", "black olive", "smoky granite"]},
            ],
            "coffee": [
                {"name": "Worka Sakaro Anaerobic Natural", "maker": "Sey Coffee / Manhattan", "origin": "Gedeb, Yirgacheffe, Ethiopia", "notes": ["jasmine", "wild blueberry", "candied peach", "sparkling citrus"]},
                {"name": "Elida Estate Geisha Washed", "maker": "Lamastus Family Estates", "origin": "Boquete, Panama", "notes": ["bergamot", "white peach", "lemongrass", "silky tea body"]},
                {"name": "Pink Bourbon Thermal Shock", "maker": "Diego Bermudez", "origin": "Cauca, Colombia", "notes": ["tropical passionfruit", "strawberry cream", "lavender", "complex sweetness"]},
            ],
            "tea": [
                {"name": "Da Hong Pao (Big Red Robe)", "maker": "Wuyi Rock Tea Estate", "origin": "Wuyi Mountains, Fujian, China", "notes": ["mineral rock rhyme", "roasted orchid", "honeyed wood", "long sweet finish"]},
                {"name": "Uji Gyokuro 'Pearl Dew'", "maker": "Ippodo Tea", "origin": "Kyoto, Japan", "notes": ["deep umami", "sweet seaweed", "steamed sencha greens", "velvety mouthfeel"]},
                {"name": "Moonlight White (Yue Guang Bai)", "maker": "Jinggu Mountain Craft", "origin": "Yunnan, China", "notes": ["wild floral nectar", "apricot", "subtle beeswax", "smooth amber"]},
                {"name": "First Flush Darjeeling Castleton", "maker": "Castleton Estate", "origin": "Darjeeling, India", "notes": ["muscatel grape", "green almond", "crisp morning floral", "zesty"]},
            ],
            "chocolate": [
                {"name": "Guanaja 70%", "maker": "Valrhona", "origin": "Grand Cru Blend", "notes": ["intense dark cocoa", "warm wood", "roasted nuts", "elegant bitterness"]},
                {"name": "Porcelana 70% Single Origin", "maker": "Amedei", "origin": "Zulia, Venezuela", "notes": ["pure criollo", "toasted almond", "olive wood", "butterscotch", "low acidity"]},
                {"name": "Madagascar Sambirano 72%", "maker": "Dick Taylor / Akesson's", "origin": "Sambirano Valley, Madagascar", "notes": ["bright raspberry", "citrus acidity", "molasses", "fruity wine finish"]},
            ],
            "perfume": [
                {"name": "Oud Wood", "maker": "Tom Ford Private Blend", "origin": "USA", "notes": ["rare oud", "rosewood", "cardamom", "sichuan pepper", "sandalwood", "amber", "tonka bean"]},
                {"name": "Gris Charnel Extrait", "maker": "BDK Parfums", "origin": "Paris, France", "notes": ["cardamom", "black tea", "fig", "bourbon vetiver", "sandalwood", "tonka"]},
                {"name": "Portrait of a Lady", "maker": "Editions de Parfums Frédéric Malle", "origin": "France", "notes": ["turkish rose", "patchouli", "frankincense", "blackcurrant", "cinnamon"]},
                {"name": "Grand Soir", "maker": "Maison Francis Kurkdjian", "origin": "Paris, France", "notes": ["cistus labdanum", "benzoin", "vanilla", "amber accord", "tonka bean"]},
            ],
            "watch": [
                {"name": "Speedmaster Professional 'Moonwatch'", "maker": "Omega", "origin": "Switzerland", "notes": ["caliber 3861 co-axial", "step dial", "hesalite or sapphire", "iconic chronograph"]},
                {"name": "Submariner Date Ref. 126610LN", "maker": "Rolex", "origin": "Switzerland", "notes": ["caliber 3235", "cerachrom bezel", "300m water resistance", "oystersteel"]},
                {"name": "Santos de Cartier Medium", "maker": "Cartier", "origin": "France/Switzerland", "notes": ["caliber 1847 mc", "smartlink bracelet", "art deco aesthetic", "square case"]},
                {"name": "Grand Seiko 'Snowflake' SBGA211", "maker": "Grand Seiko", "origin": "Japan", "notes": ["spring drive 9r65", "zaratsu polishing", "titanium case", "snow texture dial"]},
            ],
        }

        # Filter out what's already in the vault
        existing_names = {str(it.get("name", "")).lower() for it in items}

        selected_category = cat_norm if cat_norm in catalogs else "whiskey"
        pool = catalogs.get(selected_category, catalogs["whiskey"])

        recommendations = []
        for candidate in pool:
            if candidate["name"].lower() in existing_names:
                continue

            # Calculate match score based on shared flavor/scent notes
            cand_notes = candidate.get("notes", [])
            matches = [n for n in cand_notes if any(n in top_n or top_n in n for top_n in primary_accords)]
            affinity_score = 80 + min(18, len(matches) * 6)

            match_reason = f"Shares affinity with your top sensory notes: {', '.join(matches[:3])}" if matches else f"Matches your affinity for artisanal {candidate['maker']} craftsmanship."

            recommendations.append({
                "category": selected_category,
                "name": candidate["name"],
                "maker_or_brand": candidate["maker"],
                "origin_or_region": candidate["origin"],
                "affinity_score": f"{affinity_score}% Match",
                "flavor_or_scent_notes": cand_notes,
                "why_you_will_love_this": match_reason,
            })
            if len(recommendations) >= limit:
                break

        return {
            "status": "success",
            "category": selected_category,
            "user_taste_anchors": {
                "top_sensory_accords": primary_accords[:5],
                "favorite_makers": list(favorite_makers)[:4],
            },
            "recommendations": recommendations,
        }

    # ========================================================================
    # RESTAURANT & FINE DINING RECOMMENDATIONS
    # ========================================================================

    def get_restaurant_recommendations(
        self,
        city: Optional[str] = None,
        vibe: Optional[str] = None,
        cuisine: Optional[str] = None,
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Synthesize dining and culinary recommendations based on user's past favorite restaurants,
        preferred ambiance vibe tags, and desired city.
        """
        if not self.restaurant_service:
            return {"status": "error", "message": "RestaurantService not configured."}

        all_restaurants = self.restaurant_service.stream_all()
        visited = [r for r in all_restaurants if r.get("status") == "visited"]
        top_visited = [r for r in visited if (r.get("user_rating") or 0) >= 8.0] or visited

        vibe_counts = Counter()
        cuisine_counts = Counter()
        for r in top_visited:
            if r.get("cuisine"):
                cuisine_counts[r["cuisine"]] += 1
            for v in r.get("vibe_tags", []):
                vibe_counts[v.lower()] += 1

        top_vibes = [v for v, _ in vibe_counts.most_common(4)]
        top_cuisines = [c for c, _ in cuisine_counts.most_common(3)]

        target_city = city.strip().title() if city else "Tokyo"

        # Curated gastro destinations by city
        city_catalog: Dict[str, List[Dict[str, Any]]] = {
            "Tokyo": [
                {"name": "Sushi Sawada", "neighborhood": "Ginza", "cuisine": "Omakase", "michelin": "2-Star", "vibes": ["intimate counter", "traditional", "artisan master"], "signature": "Wild Bluefin Tuna flight, Aged Kohada"},
                {"name": "L'Effervescence", "neighborhood": "Nishi-Azabu", "cuisine": "French-Japanese", "michelin": "3-Star", "vibes": ["zen elegance", "sustainable", "poetic storytelling"], "signature": "Whole Roasted Turnip, Autumn Mont Blanc"},
                {"name": "Florilège", "neighborhood": "Toranomon", "cuisine": "Modern French", "michelin": "2-Star", "vibes": ["open counter kitchen", "theatrical", "plant-forward"], "signature": "Beef carpaccio with smoked potato purée"},
                {"name": "Yakitori Torishiki", "neighborhood": "Meguro", "cuisine": "Yakitori", "michelin": "1-Star", "vibes": ["binchotan mastery", "counter only", "pure focus"], "signature": "Tsukune, Chicken skin, Smoked quail eggs"},
            ],
            "Paris": [
                {"name": "Septime", "neighborhood": "11th Arr.", "cuisine": "Neo-Bistro", "michelin": "1-Star", "vibes": ["natural wine", "relaxed excellence", "seasonal produce"], "signature": "Hay-smoked egg yolk with mushrooms"},
                {"name": "Plénitude", "neighborhood": "Cheval Blanc", "cuisine": "Modern French", "michelin": "3-Star", "vibes": ["broth & bouillon alchemy", "luxury sanctuary", "haute gastronomy"], "signature": "Ode to Broths, Sea bass in velvety emulsion"},
                {"name": "Clamato", "neighborhood": "Charonne", "cuisine": "Seafood Bar", "michelin": "Selected", "vibes": ["walk-in only", "lively counter", "natural wines", "raw bar"], "signature": "Ceviche with smoked oil, Mapo tofu with clams"},
            ],
            "New York": [
                {"name": "Le Bernardin", "neighborhood": "Midtown", "cuisine": "French Seafood", "michelin": "3-Star", "vibes": ["white tablecloth", "impeccable service", "timeless luxury"], "signature": "Tuna Tartare on toasted baguette, Poached Halibut"},
                {"name": "Atomix", "neighborhood": "NoMad", "cuisine": "Modern Korean", "michelin": "2-Star", "vibes": ["intimate horseshoe counter", "curated cards", "cutting-edge"], "signature": "Langoustine with smoked butter, Fermented chili sorbet"},
                {"name": "Via Carota", "neighborhood": "West Village", "cuisine": "Italian", "michelin": "Bib Gourmand", "vibes": ["rustic elegance", "bustling neighborhood gem", "exceptional pasta"], "signature": "Insalata Verde, Cacio e Pepe, Meyer lemon risotto"},
            ],
            "London": [
                {"name": "The Ledbury", "neighborhood": "Notting Hill", "cuisine": "Modern British", "michelin": "3-Star", "vibes": ["warm hospitality", "foraged British ingredients", "refined game"], "signature": "Jersey Royal potatoes with seaweed, Smoked deer"},
                {"name": "Brat", "neighborhood": "Shoreditch", "cuisine": "Basque-British", "michelin": "1-Star", "vibes": ["open wood-fire grill", "convivial upstairs loft", "low-intervention wine"], "signature": "Whole turbot grilled over wood coals, Burnt cheesecake"},
                {"name": "St. JOHN", "neighborhood": "Smithfield", "cuisine": "Nose-to-Tail British", "michelin": "1-Star", "vibes": ["minimalist temple", "timeless classics", "unfussy brilliance"], "signature": "Roast bone marrow and parsley salad, Eccles cake"},
            ],
        }

        existing_names = {str(r.get("name", "")).lower() for r in all_restaurants}
        candidates = city_catalog.get(target_city, city_catalog["Tokyo"])

        recommendations = []
        for cand in candidates:
            if cand["name"].lower() in existing_names:
                continue

            vibe_matches = [v for v in cand["vibes"] if any(v in tv or tv in v for tv in top_vibes)]
            match_reason = f"Matches your love for {cand['cuisine']} and vibes like {', '.join(vibe_matches or cand['vibes'][:2])}."

            recommendations.append({
                "city": target_city,
                "name": cand["name"],
                "neighborhood": cand["neighborhood"],
                "cuisine": cand["cuisine"],
                "michelin_status": cand["michelin"],
                "standout_dishes": [cand["signature"]],
                "vibe_tags": cand["vibes"],
                "why_you_will_love_this": match_reason,
            })
            if len(recommendations) >= limit:
                break

        return {
            "status": "success",
            "city": target_city,
            "user_dining_anchors": {
                "top_cuisines": top_cuisines,
                "favorite_vibes": top_vibes,
            },
            "recommendations": recommendations,
        }
