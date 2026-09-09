# Personal Entertainment OS (`life_os_mcp`)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastMCP](https://img.shields.io/badge/MCP-FastMCP-brightgreen.svg)](https://github.com/jlowin/fastmcp)
[![Google Cloud Firestore](https://img.shields.io/badge/Database-Firestore-orange.svg)](https://cloud.google.com/firestore)
[![Tests: 21 Passing](https://img.shields.io/badge/tests-21%20passing-success.svg)](#-testing--quality-assurance)

A production-grade **Model Context Protocol (MCP)** server and automated data ingestion pipeline that transforms **Google Cloud Firestore** into your private, intelligent entertainment memory, knowledge vault, and AI recommendation engine.

Connects natively to **Gemini**, **Claude Desktop**, and other MCP-compliant agents, enabling natural language tracking and exploration across:
1. **Books**: Library ingestion, to-read queue, currently-reading tracking, Google Books & Open Library live discovery.
2. **Movies & TV**: IMDb ratings and watchlist ingestion, TMDB discovery, and automated similar-media recommendations.
3. **Memorable Quotes & Mental Models**: Capturing principles, philosophies, and memorable dialogue with theme tagging and spaced retrieval.
4. **Podcasts**: Queue management, listening logs, guest tracking, key takeaways, and zero-key Apple Podcasts discovery.
5. **Taste Profiling & Smart Recommendations**: Synthesizes ratings across books and films to recommend new gems while strictly filtering out items already consumed or queued.

---

## 🏛️ Clean Architecture & Design

`life_os_mcp` is architected using **Domain-Driven Design (DDD)** and **Clean Architecture** principles. Rather than cramming business logic into a single file, the system is organized into modular, testable, and loosely-coupled components:

```mermaid
graph TD
    Client["MCP Client (Gemini / Claude Desktop / IDE)"] -->|JSON-RPC / stdio| FastMCP["Presentation Layer (mcp_server.py)"]
    
    subgraph "Domain Services Layer (services/)"
        FastMCP --> BS["BookService"]
        FastMCP --> MS["MediaService"]
        FastMCP --> QS["QuoteService"]
        FastMCP --> PS["PodcastService"]
        FastMCP --> RS["RecommendationService"]
    end
    
    subgraph "Data Access Layer (services/base_repository.py & importers/)"
        BS --> Repo["BaseFirestoreRepository"]
        MS --> Repo
        QS --> Repo
        PS --> Repo
        RS --> Repo
        
        GI["GoodreadsImporter"] --> BI["BaseImporter"]
        II["IMDbImporter"] --> BI
    end
    
    subgraph "External Clients (services/external/)"
        RS --> BC["BookMetadataClient"]
        RS --> TC["TMDBClient"]
        FastMCP --> BC
        FastMCP --> TC
        FastMCP --> PC["ApplePodcastsClient"]
    end
    
    Repo -->|Batch / Filter Query| Firestore[("Google Cloud Firestore")]
    BI -->|500-Doc Commits| Firestore
    BC -->|HTTP| GB["Google Books API"]
    BC -.->|Automatic 429 Fallback| OL["Open Library API"]
    TC -->|v3/v4 API| TMDB["The Movie Database"]
    PC -->|Public Search| AP["Apple Podcasts API"]
```

### Key Architectural Strengths:
- **Presentation Decoupling**: `mcp_server.py` acts as a thin controller exposing FastMCP tool endpoints that delegate directly to domain services.
- **Repository Pattern**: `BaseFirestoreRepository` encapsulates all Firestore CRUD and `FieldFilter` query operations.
- **Batch Processing**: `BaseImporter` implements safe 500-document batching chunks and dry-run simulation for CSV ingestion.
- **Resilient Fallbacks**: `BookMetadataClient` queries Google Books and transparently falls back to Open Library when rate limits (HTTP 429) occur.

---

## 📁 Repository Structure

```
life_os_mcp/
├── .env.example                       # Environment configuration template
├── .gitignore                         # Strict protection for credentials, .env, and CSVs
├── pyproject.toml                     # Python dependencies & build metadata
├── README.md                          # Comprehensive documentation
├── config.py                          # Firebase Admin SDK & lazy Firestore singleton
├── models.py                          # Pydantic data schemas (Book, Media, Quote, Podcast)
├── mcp_server.py                      # FastMCP presentation layer (25 tools)
│
├── services/                          # Domain & Application Services
│   ├── __init__.py                    # Public domain service exports
│   ├── base_repository.py             # Generic Firestore Repository with CRUD & filtering
│   ├── book_service.py                # Book library, queues, and reading logs
│   ├── media_service.py               # Movies/TV, watchlists, and rating logs
│   ├── quote_service.py               # Memorable quotes, tags, and spaced retrieval
│   ├── podcast_service.py             # Podcast queues, takeaways, and listening logs
│   ├── recommendation_service.py      # Taste profiling & cross-collection deduplication
│   │
│   └── external/                      # External Third-Party API Clients
│       ├── __init__.py
│       ├── books_client.py            # Google Books + Open Library fallback client
│       ├── tmdb_client.py             # The Movie Database (TMDB) API client
│       └── podcasts_client.py         # Apple Podcasts API client (zero-key)
│
├── importers/                         # Ingestion Pipelines
│   ├── __init__.py
│   ├── base.py                        # Abstract BaseImporter with 500-doc chunking
│   ├── goodreads_importer.py          # Goodreads CSV ingestion pipeline
│   └── imdb_importer.py               # IMDb ratings & watchlist CSV ingestion pipeline
│
├── sample_data/                       # Safe, synthetic datasets for testing
│   ├── goodreads_sample.csv
│   ├── imdb_ratings_sample.csv
│   └── imdb_watchlist_sample.csv
│
└── tests/                             # Automated Test Suite (21 tests)
    ├── test_models_and_importers.py   # Schema validation & CSV parser tests
    ├── test_domain_services.py        # Domain services, OOP repositories, & client mocks
    ├── test_quotes_and_podcasts.py    # Quotes, podcasts, and metadata tests
    └── test_services.py               # External API fallback and error handling tests
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python**: `3.10` or newer.
- **Google Cloud / Firebase Project**: With **Cloud Firestore** enabled in Native mode.
- **Firebase Service Account**: Downloaded JSON credentials key.

### 2. Installation

Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/your-username/life_os_mcp.git
cd life_os_mcp

# Using python venv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .
```

### 3. Firebase Service Account Configuration

1. In the [Firebase Console](https://console.firebase.google.com/), go to **Project Settings** > **Service accounts**.
2. Click **Generate new private key** and save the JSON file.
3. Move the file into your project directory (e.g. `service-account.json`).
4. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
5. Edit `.env`:
   ```ini
   FIREBASE_CREDENTIALS_PATH=./service-account.json
   
   # Optional: For movie & TV posters, overviews, and similar media recommendations
   TMDB_API_KEY=your_tmdb_api_key_here
   
   # Optional: For higher Google Books quota (basic search works without a key)
   GOOGLE_BOOKS_API_KEY=your_google_books_key_here
   ```

---

## 📥 Data Ingestion Pipelines

Import your existing personal libraries into Firestore using the batch importers.

### Goodreads Library Import
Export your library from **Goodreads** (`My Books` > `Import and Export` > `Export Library`):

```bash
# Preview records without writing (Dry Run)
python -m importers.goodreads_importer path/to/goodreads_library_export.csv --dry-run

# Execute batch write into Firestore 'books' collection
python -m importers.goodreads_importer path/to/goodreads_library_export.csv
```

### IMDb Ratings & Watchlist Import
Export your data from **IMDb** (`Your Activity` > `Ratings` > Export & `Your Watchlist` > Export):

```bash
# Ingest both ratings and watchlist simultaneously
python -m importers.imdb_importer \
  --ratings path/to/ratings.csv \
  --watchlist path/to/watchlist.csv

# Or ingest either file individually
python -m importers.imdb_importer --ratings path/to/ratings.csv
python -m importers.imdb_importer --watchlist path/to/watchlist.csv
```
*Note: If an item exists in both files, `imdb_importer` automatically marks it as `watched` with the user's rating taking precedence.*

---

## 🛠️ Model Context Protocol (MCP) Tools

The server registers **25 specialized tools** categorized across five domains:

### 1. Taste Profile & Recommendations
| Tool Name | Parameters | Description |
|---|---|---|
| `get_user_taste_profile` | *none* | Aggregates favorite genres, top directors, authors, and 5★/10★ items. |
| `get_entertainment_stats` | *none* | Macro metrics across books, media, quotes, and podcasts. |
| `get_smart_recommendations` | `category`, `limit` | Intelligent AI recommender that queries similar items and automatically excludes consumed or queued titles. |

### 2. Books Management & Discovery
| Tool Name | Parameters | Description |
|---|---|---|
| `search_books` | `query`, `shelf`, `limit` | Search Firestore library by title or author keywords. |
| `get_reading_list` | `shelf`, `limit` | Retrieve books from `to-read` or `currently-reading` queues. |
| `add_to_reading_list` | `title`, `author`, `notes` | Add a recommended book directly to the reading queue. |
| `log_read_book` | `title`, `author`, `user_rating`, `notes`, `date_read` | Log a finished book with 0–5 rating and notes. |
| `get_book_details` | `book_id` | Fetch complete document for a book by Goodreads ID. |
| `lookup_book_online` | `title`, `author` | Query Google Books & Open Library for synopses and covers. |
| `find_similar_books_online` | `title`, `author`, `limit` | Discover books similar in theme and author style. |

### 3. Media (Movies & TV) Management & Discovery
| Tool Name | Parameters | Description |
|---|---|---|
| `search_media` | `query`, `media_type`, `status`, `limit` | Search movies and series by title or director. |
| `get_watchlist` | `media_type`, `genre`, `limit` | Retrieve watchlist items with optional genre filter. |
| `add_to_watchlist` | `title`, `media_type`, `year`, `genres`, `directors`, `notes` | Add a movie or show to the watchlist. |
| `log_watched_media` | `title`, `media_type`, `user_rating`, `notes` | Log a viewed film/series with 1–10 rating. |
| `get_media_details` | `media_id` | Fetch complete record by IMDb Const ID (`tt...`). |
| `lookup_media_online` | `title`, `media_type`, `year` | Query TMDB for synopsis, posters, and vote average. |
| `find_similar_media_online` | `title`, `media_type`, `limit` | Query TMDB recommendation algorithm for similar titles. |

### 4. Memorable Quotes & Mental Models
| Tool Name | Parameters | Description |
|---|---|---|
| `add_quote` | `quote_text`, `source_title`, `source_type`, `speaker_or_author`, `theme_tags`, `notes`, `favorite` | Save a quote or mental model from a book or film. |
| `get_random_quote` | `theme`, `source_type` | Spaced retrieval of a random quote for inspiration or decision-making. |
| `search_quotes` | `query`, `theme`, `source_title`, `limit` | Search saved quotes by keyword, speaker, or theme. |
| `list_favorite_quotes` | `limit` | Retrieve all quotes marked as all-time favorites. |

### 5. Podcasts
| Tool Name | Parameters | Description |
|---|---|---|
| `add_to_podcast_queue` | `podcast_name`, `episode_title`, `guest`, `topics`, `episode_url` | Add an episode to the listening queue. |
| `log_listened_podcast` | `podcast_name`, `episode_title`, `user_rating`, `guest`, `key_takeaways` | Log a completed episode with takeaways and rating. |
| `get_podcast_queue` | `limit` | View upcoming podcast episodes. |
| `search_podcasts` | `query`, `guest`, `topic`, `limit` | Search podcast archive by show, guest, or topic. |
| `lookup_podcast_online` | `query`, `limit` | Free online search via Apple Podcasts API for artwork and feeds. |

---

## 🔌 Connecting to MCP Clients

### Claude Desktop / Gemini / Antigravity IDE Configuration

Add the following configuration to your MCP config file (e.g. `claude_desktop_config.json` or `mcp_config.json`):

```json
{
  "mcpServers": {
    "personal-entertainment-os": {
      "command": "/path/to/life_os_mcp/.venv/bin/python",
      "args": [
        "/path/to/life_os_mcp/mcp_server.py"
      ],
      "env": {
        "FIREBASE_CREDENTIALS_PATH": "/path/to/life_os_mcp/service-account.json",
        "TMDB_API_KEY": "YOUR_TMDB_API_KEY_HERE"
      }
    }
  }
}
```

---

## 🔒 Security & Privacy Notice

This project is built for **public open-source publication** and adheres to strict security best practices:

1. **Zero Secret Leakage**:
   - The `.gitignore` strictly blocks all variations of credentials files (`service-account*.json`, `*firebase*.json`, `*credentials*.json`), environment files (`.env`), and personal user data (`*.csv`).
   - Only synthetic samples inside `sample_data/` are tracked by Git.
2. **Safe Lazy Loading**:
   - `config.py` uses lazy proxy initialization so that running unit tests, building wheels, or executing `--help` commands will never throw missing-key crashes or expose environment data.
3. **Audit Verification**:
   - The Git commit history has been audited to confirm no secrets, API tokens, or real user CSV files exist in any commit.

---

## 🧪 Testing & Quality Assurance

The codebase includes an automated unit test suite:

```bash
# Run all 21 unit tests
.venv/bin/python -m unittest discover -s tests
```

Tests cover:
- **Data Models**: Pydantic schema validation, shelf normalization, timestamp generation.
- **Importers**: Goodreads and IMDb CSV column mapping, Excel formatting cleanup, list field normalization.
- **Domain Services**: `BookService`, `MediaService`, `QuoteService`, `PodcastService`, `RecommendationService`.
- **External Clients**: Apple Podcasts API mocking, TMDB error resilience, and Google Books / Open Library HTTP fallbacks.

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.
