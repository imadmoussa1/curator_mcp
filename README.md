# Personal Entertainment OS (`life_os_mcp`)

A Python-based **Model Context Protocol (MCP)** server and automated data ingestion pipeline that turns **Google Cloud Firestore** into your personal entertainment memory and recommendation engine. 

Designed to be connected directly to **Gemini**, allowing you to log what you've watched or read, maintain your watchlists and reading queues, and receive personalized recommendations powered by your taste history.

---

## 🌟 Key Features

- **Automated Data Ingestion**:
  - **Goodreads**: Ingest full library CSV exports (ratings, shelves, dates read, reviews) into Firestore with 500-doc batching.
  - **IMDb**: Ingest both `ratings.csv` (`watched`) and `watchlist.csv` (`watchlist`) with genre/director list normalization.
- **FastMCP Server ("Personal-Entertainment-OS")**:
  - **Taste Profile Aggregator**: Extracts top genres, directors, authors, and highest-rated media to give Gemini deep context on your preferences.
  - **Active Lists**: Manage what you want to read (`to-read`, `currently-reading`) and watch (`watchlist`).
  - **Activity Logging**: Log newly finished books or movies/shows with ratings and reviews on the fly.
  - **Fast Search & Retrieval**: Search across your personal database by title, author, director, shelf, or genre.
- **Modern Python Architecture**: Built with `uv`, `fastmcp`, `firebase-admin`, `pandas`, and `pydantic`.

---

## 📁 Project Structure

```
life_os_mcp/
├── .env.example                       # Environment configuration template
├── .gitignore                         # Protects service keys and local venvs
├── pyproject.toml                     # uv project dependencies
├── README.md                          # Documentation and setup guide
├── config.py                          # Firebase Admin SDK & Firestore client initialization
├── models.py                          # Pydantic schemas for books and media
├── mcp_server.py                      # FastMCP server with Gemini-tailored tools
├── importers/
│   ├── __init__.py
│   ├── goodreads_importer.py          # Goodreads CSV batch ingestion script
│   └── imdb_importer.py               # IMDb ratings & watchlist CSV batch ingestion script
├── sample_data/                       # Sample data for testing out of the box
│   ├── goodreads_sample.csv
│   ├── imdb_ratings_sample.csv
│   └── imdb_watchlist_sample.csv
└── tests/
    └── test_models_and_importers.py   # Unit tests for schemas and parser logic
```

---

## 🗄️ Firestore Schema

### 1. `books` Collection
| Field | Type | Description |
|---|---|---|
| `id` | string | Goodreads Book ID (document ID) |
| `title` | string | Book title |
| `author` | string | Author name |
| `user_rating` | integer | User's rating (0 = unrated, 1–5 stars) |
| `avg_rating` | float | Goodreads community average rating |
| `shelf` | string | Reading status: `read`, `currently-reading`, `to-read` |
| `notes_and_reviews` | string | Personal review or notes |
| `date_read` | string/timestamp | Date completed (`YYYY-MM-DD`) |
| `updated_at` | timestamp | Last updated timestamp |

### 2. `media` Collection (Movies & TV Series)
| Field | Type | Description |
|---|---|---|
| `id` | string | IMDb Const ID (e.g. `tt0111161`) |
| `title` | string | Title of movie or series |
| `media_type` | string | `movie`, `tvSeries`, `tvMiniSeries` |
| `user_rating` | integer/null | User rating (1–10; nullable for unrated watchlist items) |
| `imdb_rating` | float | IMDb community rating |
| `year` | integer | Release year |
| `genres` | list of strings | e.g. `["Sci-Fi", "Adventure"]` |
| `directors` | list of strings | e.g. `["Christopher Nolan"]` |
| `status` | string | `watched` or `watchlist` |
| `notes` | string | Personal notes or date rated |
| `updated_at` | timestamp | Last updated timestamp |

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
- Python 3.10+
- [`uv`](https://github.com/astral-sh/uv) package manager:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### 2. Install Project Dependencies
In the `life_os_mcp` directory, create a virtual environment and install dependencies:
```bash
cd life_os_mcp
uv venv
source .venv/bin/activate
uv pip install -e .
```

### 3. Configure Firebase Cloud Firestore
1. Open the [Firebase Console](https://console.firebase.google.com/) and select or create a project.
2. In the sidebar, click **Build > Firestore Database** and create a database in Production or Test mode.
3. Go to **Project Settings > Service Accounts**.
4. Click **Generate New Private Key** and download the resulting JSON file.
5. Place the key in the project directory (e.g. `service-account.json`) or specify its path in `.env`:
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```env
   FIREBASE_CREDENTIALS_PATH=./service-account.json
   PORT=8000
   ```

---

## 📥 Ingestion Pipelines

### How to Export Your Data
- **Goodreads**: Go to **My Books > Import and Export** (in the left sidebar) > click **Export Library** to download `goodreads_library_export.csv`.
- **IMDb**: Go to **Your Ratings** > click the three dots (`...`) > **Export** to download `ratings.csv`. Do the same in **Your Watchlist** to download `watchlist.csv`.

### Running the Importers

#### 1. Goodreads Importer
```bash
# Preview parsing without writing to Firestore (dry run)
python -m importers.goodreads_importer sample_data/goodreads_sample.csv --dry-run

# Ingest into Firestore in 500-document batches
python -m importers.goodreads_importer path/to/your_goodreads_library_export.csv
```

#### 2. IMDb Importer
```bash
# Preview parsing without writing to Firestore (dry run)
python -m importers.imdb_importer --ratings sample_data/imdb_ratings_sample.csv --watchlist sample_data/imdb_watchlist_sample.csv --dry-run

# Ingest both ratings (watched) and watchlist (watchlist)
python -m importers.imdb_importer --ratings path/to/ratings.csv --watchlist path/to/watchlist.csv

# Or ingest individually
python -m importers.imdb_importer --ratings path/to/ratings.csv
python -m importers.imdb_importer --watchlist path/to/watchlist.csv
```

---

## 🤖 Using with Gemini & MCP Clients

### Running the FastMCP Server directly
```bash
python mcp_server.py
```

### Connecting to Gemini / MCP Clients
Add the server definition to your MCP client configuration (such as `mcp_config.json` in Antigravity IDE, Claude Desktop, or Gemini MCP tool runner):

```json
{
  "mcpServers": {
    "personal-entertainment-os": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/imad/workspace/life_os_mcp",
        "run",
        "python",
        "mcp_server.py"
      ],
      "env": {
        "FIREBASE_CREDENTIALS_PATH": "/Users/imad/workspace/life_os_mcp/service-account.json"
      }
    }
  }
}
```

### Example Gemini Prompts
Once connected, Gemini will automatically call the appropriate MCP tools:

1. **Recommendations Based on History**:
   > *"Based on my favorite books and movies, what sci-fi movie should I watch this weekend?"*  
   > ↳ Gemini calls `get_user_taste_profile()` and `get_watchlist()`, analyzes your top-rated directors and genres, and suggests matching titles.

2. **Adding to Watchlist / Reading List**:
   > *"Add 'Children of Time' by Adrian Tchaikovsky to my to-read reading list."*  
   > ↳ Gemini calls `add_to_reading_list(title="Children of Time", author="Adrian Tchaikovsky")`.

3. **Logging What You Just Watched/Read**:
   > *"I just finished reading Dune Messiah and loved it, give it 5 stars."*  
   > ↳ Gemini calls `log_read_book(title="Dune Messiah", author="Frank Herbert", user_rating=5)`.

4. **Checking Queues**:
   > *"What movies are currently on my watchlist?"*  
   > ↳ Gemini calls `get_watchlist(media_type="movie")`.

---

## 🧪 Running Tests

Run the test suite to verify model validations and CSV parsing logic:
```bash
python -m unittest discover -s tests
```
All unit tests run locally without requiring live Firebase credentials.
