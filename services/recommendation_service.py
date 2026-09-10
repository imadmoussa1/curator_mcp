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


class RecommendationService:
    """
    Intelligent recommendation and taste profiling service.
    """

    def __init__(
        self,
        book_service: BookService,
        media_service: MediaService,
        books_client: Optional[Any] = None,
        tmdb_client: Optional[Any] = None,
        quote_service: Optional[Any] = None,
        podcast_service: Optional[Any] = None,
        sensory_service: Optional[Any] = None,
        restaurant_service: Optional[Any] = None,
        memory_service: Optional[Any] = None,
    ):
        self.book_service = book_service
        self.media_service = media_service
        self.books_client = books_client
        self.tmdb_client = tmdb_client
        self.quote_service = quote_service
        self.podcast_service = podcast_service
        self.sensory_service = sensory_service
        self.restaurant_service = restaurant_service
        self.memory_service = memory_service

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

    # ========================================================================
    # AGENT-EMPOWERED SMART RECOMMENDATION DOSSIER & CANDIDATE VETTING
    # ========================================================================

    def get_agent_recommendation_brief(
        self,
        domain: str,
        mood_or_intent: Optional[str] = None,
        target_location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Produce a high-signal Recommendation Dossier specifically engineered for an autonomous AI agent
        (such as Claude Desktop with internet access).

        Provides:
        1. Negative Exclusion List: All titles/makers/venues the user has already consumed, read, or wishlisted.
        2. Personal Taste DNA: 10/10 anchors, specific review excerpts, favorite creators, flavor/scent accords.
        3. Guardrails & Dislikes: Low-rated items and reasons.
        4. Targeted Web Search Directives: High-signal search queries engineered for the AI agent to run on the web.
        5. Evaluation Rubric: Criteria to select and justify the recommendation.
        """
        dom = domain.lower().strip()
        mood_str = f" with vibe: '{mood_or_intent}'" if mood_or_intent else ""
        loc_str = f" in {target_location}" if target_location else ""

        # Normalize domain alias
        if dom in ("film", "movie", "cinema"):
            dom = "movies"
        elif dom in ("series", "show"):
            dom = "tv"
        elif dom in ("book", "reading", "literature"):
            dom = "books"
        elif dom in ("restaurant", "food", "dining"):
            dom = "restaurants"
        elif dom in ("podcast", "shows"):
            dom = "podcasts"

        top_anchors: List[Dict[str, Any]] = []
        excluded_items: List[str] = []
        guardrails: List[str] = []
        fav_creators: Counter = Counter()
        fav_tags: Counter = Counter()
        web_queries: List[str] = []

        # --- 1. BOOKS ---
        if dom == "books":
            for b in self.book_service.stream_all():
                title = b.get("title") or ""
                author = b.get("author") or ""
                rating = b.get("user_rating")
                notes = b.get("notes_and_reviews") or ""
                if title:
                    excluded_items.append(f"{title} by {author}" if author else title)
                if rating and rating >= 4:
                    top_anchors.append({
                        "title": title,
                        "author": author,
                        "user_rating": f"{rating}/5 stars",
                        "personal_notes": notes,
                    })
                    if author:
                        fav_creators[author] += 1
                elif rating and rating <= 2:
                    guardrails.append(f"Rated '{title}' low ({rating}/5): {notes or 'did not resonate'}")

            top_authors_list = [a for a, _ in fav_creators.most_common(4)]
            anchor_titles = [a["title"] for a in top_anchors[:3]]

            web_queries = [
                f"books for fans of {', '.join(top_authors_list[:2])} {mood_or_intent or 'literary fiction'}",
                f"critically acclaimed books similar to {' and '.join(anchor_titles[:2])} recent releases",
                f"underrated indie press novels {mood_or_intent or 'compelling narrative'} book reviews",
            ]

        # --- 2. MOVIES & TV ---
        elif dom in ("movies", "tv", "media"):
            media_type_filter = "movie" if dom == "movies" else ("tv" if dom == "tv" else None)
            for m in self.media_service.stream_all():
                title = m.get("title") or ""
                year = m.get("year") or ""
                m_type = m.get("media_type") or "movie"
                rating = m.get("user_rating")
                notes = m.get("notes") or ""
                genres = m.get("genres", [])
                directors = m.get("directors", [])

                if title:
                    label = f"{title} ({year})" if year else title
                    excluded_items.append(label)

                if media_type_filter and m_type.lower() != media_type_filter:
                    continue

                if rating and rating >= 8:
                    top_anchors.append({
                        "title": title,
                        "year": year,
                        "media_type": m_type,
                        "directors": directors,
                        "genres": genres,
                        "user_rating": f"{rating}/10",
                        "personal_notes": notes,
                    })
                    for d in directors:
                        fav_creators[d] += 1
                    for g in genres:
                        fav_tags[g] += 1
                elif rating and rating <= 5:
                    guardrails.append(f"Rated '{title}' low ({rating}/10): {notes or 'disliked tone/pacing'}")

            top_dirs = [d for d, _ in fav_creators.most_common(3)]
            top_g = [g for g, _ in fav_tags.most_common(3)]
            anchor_films = [a["title"] for a in top_anchors[:2]]

            web_queries = [
                f"atmospheric cinema recommendations like {' and '.join(anchor_films)} {mood_or_intent or ''}",
                f"hidden gem {'movies' if dom == 'movies' else 'series'} for fans of {', '.join(top_dirs)}",
                f"criterion collection or international {', '.join(top_g)} recommendations high rating",
            ]

        # --- 3. SENSORY VAULT (Whiskey, Coffee, Tea, Wine, Gin, Chocolate, Perfume, Watch) ---
        elif self.sensory_service and dom in (
            "whiskey", "coffee", "tea", "wine", "gin", "chocolate", "perfume", "watch"
        ):
            items = self.sensory_service.stream_all()
            for it in items:
                name = it.get("name") or ""
                cat = it.get("category") or ""
                maker = it.get("maker_or_brand") or ""
                rating = it.get("user_rating")
                notes_list = it.get("flavor_or_scent_notes", [])
                personal_notes = it.get("personal_notes") or it.get("review") or ""

                if name:
                    excluded_items.append(f"{name} ({maker})" if maker else name)

                if cat != dom:
                    continue

                if rating and rating >= 8.0:
                    top_anchors.append({
                        "name": name,
                        "maker_or_brand": maker,
                        "rating": f"{rating}/10",
                        "accords_and_notes": notes_list,
                        "personal_notes": personal_notes,
                    })
                    if maker:
                        fav_creators[maker] += 1
                    for n in notes_list:
                        fav_tags[n.lower()] += 1
                elif rating and rating <= 5.0:
                    guardrails.append(f"Rated '{name}' low ({rating}/10): {personal_notes or 'unfavorable balance'}")

            top_makers = [m for m, _ in fav_creators.most_common(3)]
            top_accords = [n for n, _ in fav_tags.most_common(4)]

            if dom == "coffee":
                web_queries = [
                    f"specialty coffee roasters single origin {', '.join(top_accords[:2])} {mood_or_intent or 'light roast'}",
                    f"top micro-roasters international shipping like {', '.join(top_makers or ['Sey', 'Manhattan'])}",
                ]
            elif dom == "whiskey":
                web_queries = [
                    f"single malt whisky reviews notes of {', '.join(top_accords[:3])} non-chill filtered",
                    f"independent bottler cask strength whisky {mood_or_intent or 'complex finish'}",
                ]
            elif dom == "perfume":
                web_queries = [
                    f"niche perfume fragrantica {', '.join(top_accords[:3])} {mood_or_intent or 'long lasting extrait'}",
                    f"artisanal fragrance houses similar to {', '.join(top_makers or ['Frederic Malle', 'BDK'])}",
                ]
            elif dom == "tea":
                web_queries = [
                    f"artisan single estate loose leaf tea {', '.join(top_accords[:2])} spring harvest",
                    f"authentic gongfu tea tasting notes {mood_or_intent or 'oolong or white tea'}",
                ]
            elif dom == "wine":
                web_queries = [
                    f"natural low-intervention wine producer {', '.join(top_accords[:2])} reviews",
                    f"exceptional terroir wine vintage recommendations {mood_or_intent or 'structured elegant'}",
                ]
            else:
                web_queries = [
                    f"curated artisanal {dom} recommendations notes of {', '.join(top_accords[:2])}",
                    f"best craft {dom} makers 2024 2025 reviews",
                ]

        # --- 4. RESTAURANTS & FINE DINING ---
        elif self.restaurant_service and dom == "restaurants":
            city_target = target_location.strip().title() if target_location else None
            for r in self.restaurant_service.stream_all():
                name = r.get("name") or ""
                city = r.get("city") or ""
                cuisine = r.get("cuisine") or ""
                rating = r.get("user_rating")
                vibes = r.get("vibe_tags", [])
                dishes = r.get("standout_dishes", [])
                notes = r.get("notes_and_review") or ""

                if name:
                    excluded_items.append(f"{name} ({city})" if city else name)

                if rating and rating >= 8.0:
                    top_anchors.append({
                        "name": name,
                        "city": city,
                        "cuisine": cuisine,
                        "rating": f"{rating}/10",
                        "vibe_tags": vibes,
                        "standout_dishes": dishes,
                        "personal_notes": notes,
                    })
                    if cuisine:
                        fav_creators[cuisine] += 1
                    for v in vibes:
                        fav_tags[v.lower()] += 1
                elif rating and rating <= 5.0:
                    guardrails.append(f"Disliked '{name}' ({rating}/10): {notes or 'mediocre execution'}")

            top_cuisines = [c for c, _ in fav_creators.most_common(3)]
            top_vibes = [v for v, _ in fav_tags.most_common(3)]
            dest_city = city_target or "Tokyo"

            web_queries = [
                f"best new restaurant openings {dest_city} {', '.join(top_vibes[:2])} Eater Michelin Guide",
                f"intimate counter dining {dest_city} {mood_or_intent or 'seasonal tasting menu'}",
                f"exceptional culinary gems {dest_city} {', '.join(top_cuisines[:2])} natural wine",
            ]

        # --- 5. PODCASTS ---
        elif self.podcast_service and dom == "podcasts":
            for p in self.podcast_service.stream_all():
                title = p.get("title") or ""
                ep = p.get("episode_title") or ""
                rating = p.get("user_rating")
                notes = p.get("takeaways_and_insights") or ""
                topics = p.get("topics", [])

                if title:
                    excluded_items.append(f"{title} - {ep}" if ep else title)

                if rating and rating >= 4:
                    top_anchors.append({
                        "podcast": title,
                        "episode": ep,
                        "rating": f"{rating}/5 stars",
                        "topics": topics,
                        "notes": notes,
                    })
                    for t in topics:
                        fav_tags[t.lower()] += 1

            top_topics = [t for t, _ in fav_tags.most_common(3)]
            web_queries = [
                f"deep dive podcast episodes {', '.join(top_topics)} {mood_or_intent or 'high signal'}",
                f"intellectual podcast interviews longform {mood_or_intent or 'philosophy science craft'}",
            ]

        else:
            return {
                "status": "error",
                "message": f"Unsupported or unconfigured domain '{domain}'. Supported domains: books, movies, tv, whiskey, coffee, tea, wine, gin, chocolate, perfume, watch, restaurants, podcasts.",
            }

        # Seamlessly incorporate remembered user preferences, habits, and constraints
        remembered_preferences = []
        if self.memory_service:
            memory_constraints = self.memory_service.get_relevant_constraints(domain=dom)
            guardrails.extend(memory_constraints)
            remembered_preferences = [
                m.get("content") for m in self.memory_service.recall(query=dom, category="preference", limit=5)
            ]

        taste_dna: Dict[str, Any] = {
            "top_rated_anchors": top_anchors[:8],
            "dominant_affinities": {
                "creators_or_cuisines": [c for c, _ in fav_creators.most_common(5)],
                "flavor_accords_or_vibes": [t for t, _ in fav_tags.most_common(6)],
            },
        }
        if remembered_preferences:
            taste_dna["remembered_personal_preferences"] = remembered_preferences

        return {
            "status": "success",
            "domain": dom,
            "briefing_for_ai_agent": {
                "role_directive": (
                    f"You are the user's bespoke taste curator with internet search access. "
                    f"The user is seeking an elite recommendation in '{dom}'{mood_str}{loc_str}. "
                    "Analyze their Taste DNA, execute live web searches to find fresh, exceptional candidates, "
                    "and STRICTLY avoid any item in the Negative Exclusion Catalog."
                ),
                "user_taste_dna": taste_dna,
                "negative_exclusion_catalog": {
                    "instruction": "CRITICAL: Never recommend anything in this catalog. The user has already read, watched, visited, or tasted it.",
                    "total_excluded_items": len(excluded_items),
                    "sample_excluded_titles": excluded_items[:60],
                    "all_excluded_names_normalized": [
                        re.sub(r"[^\w\s]", "", str(name).lower()).strip()
                        for name in excluded_items
                    ],
                },
                "guardrails_and_dislikes": guardrails[:8],
                "suggested_web_search_directives": web_queries,
                "selection_rubric": [
                    "1. Uniqueness: Avoid cliché suggestions; discover hidden masterpieces, artisanal releases, or recent acclaimed debuts.",
                    "2. Direct Taste Tether: State explicitly which of their 10/10 anchors inspired this choice.",
                    "3. Pre-vetting: Call 'vet_recommendation_candidate' before delivering your final pick to ensure zero library collisions.",
                ],
            },
        }

    def vet_recommendation_candidate(
        self,
        domain: str,
        title_or_name: str,
        maker_or_creator: Optional[str] = None,
        attributes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Tool for the AI Agent: Vet a recommendation candidate found via internet search against the user's
        curated library and taste profile before presenting it.

        Checks:
        1. Exact and fuzzy collision detection across user's history and wishlists.
        2. Calculates taste affinity match score (0-100%).
        3. Identifies specific personalization tether hooks.
        """
        dom = domain.lower().strip()
        if dom in ("film", "movie", "cinema"):
            dom = "movies"
        elif dom in ("series", "show"):
            dom = "tv"
        elif dom in ("book", "reading", "literature"):
            dom = "books"
        elif dom in ("restaurant", "food", "dining"):
            dom = "restaurants"

        raw_cand = title_or_name.strip()
        cand_norm = re.sub(r"[^\w\s]", "", raw_cand.lower()).strip()
        cand_tokens = set(cand_norm.split())

        creator_norm = re.sub(r"[^\w\s]", "", (maker_or_creator or "").lower()).strip()
        cand_attrs = [a.lower().strip() for a in (attributes or [])]

        collision = None
        user_library_docs = []

        if dom == "books":
            user_library_docs = self.book_service.stream_all()
        elif dom in ("movies", "tv", "media"):
            user_library_docs = self.media_service.stream_all()
        elif self.sensory_service and dom in (
            "whiskey", "coffee", "tea", "wine", "gin", "chocolate", "perfume", "watch"
        ):
            user_library_docs = [
                it for it in self.sensory_service.stream_all()
                if it.get("category") == dom
            ]
        elif self.restaurant_service and dom == "restaurants":
            user_library_docs = self.restaurant_service.stream_all()
        elif self.podcast_service and dom == "podcasts":
            user_library_docs = self.podcast_service.stream_all()

        # Check for collision
        for doc in user_library_docs:
            doc_name = (doc.get("title") or doc.get("name") or "").strip()
            doc_norm = re.sub(r"[^\w\s]", "", doc_name.lower()).strip()
            doc_tokens = set(doc_norm.split())

            # Exact match or high token overlap
            if doc_norm == cand_norm or (cand_norm and cand_norm in doc_norm) or (doc_norm and doc_norm in cand_norm):
                collision = {
                    "matched_item": doc_name,
                    "status": doc.get("status") or doc.get("shelf") or "in_library",
                    "user_rating": doc.get("user_rating"),
                    "notes": doc.get("notes_and_reviews") or doc.get("notes") or doc.get("personal_notes") or "",
                }
                break
            # Fuzzy token overlap check (if title has 3+ words and matches completely)
            if len(cand_tokens) >= 3 and cand_tokens == doc_tokens:
                collision = {
                    "matched_item": doc_name,
                    "status": doc.get("status") or doc.get("shelf") or "in_library",
                    "user_rating": doc.get("user_rating"),
                    "notes": doc.get("notes_and_reviews") or doc.get("notes") or doc.get("personal_notes") or "",
                }
                break

        if collision:
            return {
                "status": "collision_detected",
                "is_clean_recommendation": False,
                "message": f"'{raw_cand}' is already in the user's collection ({collision['status']}). Do not recommend this.",
                "collision_details": collision,
            }

        # Calculate affinity score
        top_anchors = []
        user_creators = Counter()
        user_affinities = Counter()

        for doc in user_library_docs:
            rating = doc.get("user_rating") or 0
            if rating >= 8.0 or rating >= 4:  # 8/10 or 4/5
                top_anchors.append(doc)
                c = doc.get("author") or doc.get("maker_or_brand") or doc.get("cuisine")
                if c:
                    user_creators[str(c).lower()] += 1
                for d in doc.get("directors", []):
                    user_creators[str(d).lower()] += 1
                for g in doc.get("genres", []):
                    user_affinities[str(g).lower()] += 1
                for n in doc.get("flavor_or_scent_notes", []):
                    user_affinities[str(n).lower()] += 1
                for v in doc.get("vibe_tags", []):
                    user_affinities[str(v).lower()] += 1

        affinity_score = 75
        hooks = []

        # Creator match
        if creator_norm and any(creator_norm in c or c in creator_norm for c in user_creators):
            affinity_score += 15
            hooks.append(f"Created by {maker_or_creator}, who aligns with user's top-rated creators")

        # Attribute/note matches
        matched_notes = []
        for attr in cand_attrs:
            if any(attr in aff or aff in attr for aff in user_affinities):
                matched_notes.append(attr)

        if matched_notes:
            affinity_score += min(18, len(matched_notes) * 6)
            hooks.append(f"Shares specific flavor/thematic accords: {', '.join(matched_notes[:3])}")

        if not hooks and top_anchors:
            sample_anchor = (top_anchors[0].get("title") or top_anchors[0].get("name"))
            hooks.append(f"Aesthetic resonance inspired by user's 5★/10★ rating of '{sample_anchor}'")

        affinity_score = min(98, affinity_score)

        return {
            "status": "approved_clean_discovery",
            "is_clean_recommendation": True,
            "candidate": raw_cand,
            "maker_or_creator": maker_or_creator,
            "taste_affinity_score": f"{affinity_score}%",
            "personalization_tethers": hooks,
            "verdict": "Vetted successfully. Safe and highly recommended to present to the user.",
        }
