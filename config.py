"""
Configuration and Firebase initialization for life_os_mcp.
Loads environment variables and sets up the Google Cloud Firestore client.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
PORT = int(os.getenv("PORT", "8000"))
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")

_db = None


def get_db():
    """
    Initializes and returns the Firestore client singleton.
    Raises RuntimeError if Firebase credentials cannot be located.
    """
    global _db
    if _db is not None:
        return _db

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred = None
            cred_path = None

            if FIREBASE_CREDENTIALS_PATH:
                cred_path = Path(FIREBASE_CREDENTIALS_PATH)
                if not cred_path.is_absolute():
                    cred_path = BASE_DIR / cred_path

            # Check specified credentials path
            if cred_path and cred_path.exists():
                cred = credentials.Certificate(str(cred_path))
                firebase_admin.initialize_app(cred)
            # Check default service-account.json in project root
            elif (BASE_DIR / "service-account.json").exists():
                cred = credentials.Certificate(str(BASE_DIR / "service-account.json"))
                firebase_admin.initialize_app(cred)
            # Check GOOGLE_APPLICATION_CREDENTIALS or gcloud environment
            elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred)
            else:
                try:
                    # Attempt default initialization (e.g. within GCP environment)
                    firebase_admin.initialize_app()
                except Exception:
                    raise RuntimeError(
                        "Firebase credentials not found! Please set FIREBASE_CREDENTIALS_PATH "
                        "in your .env file or place 'service-account.json' in the project directory."
                    )

        _db = firestore.client()
        return _db
    except Exception as e:
        raise RuntimeError(f"Failed to initialize Firestore client: {e}") from e


class _LazyDbProxy:
    """
    Proxy object allowing `from config import db` while deferring actual
    connection until first operation, preventing import-time crashes when
    running CLI help or tests.
    """
    def __getattr__(self, name):
        return getattr(get_db(), name)

    def __repr__(self):
        try:
            return repr(get_db())
        except Exception:
            return "<FirestoreClient (uninitialized - set FIREBASE_CREDENTIALS_PATH)>"


db = _LazyDbProxy()
