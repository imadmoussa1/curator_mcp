"""
Configuration and Firebase initialization for Curator MCP.
Loads environment variables and sets up the Google Cloud Firestore client.
"""

import os
import base64
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
PORT = int(os.getenv("PORT", "8000"))
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
GOOGLE_BOOKS_API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY", "")

# Token Optimization & Client Footprint Settings
CURATOR_SLIM_MODE = os.getenv("CURATOR_SLIM_MODE", "true").lower() in ("true", "1", "yes")
CURATOR_COMPACT_OUTPUTS = os.getenv("CURATOR_COMPACT_OUTPUTS", "true").lower() in ("true", "1", "yes")
CURATOR_DEFAULT_LIMIT = int(os.getenv("CURATOR_DEFAULT_LIMIT", "5"))

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

            # Check inline JSON / Base64 credentials first (ideal for Docker & Cloud deployments)
            firebase_json_env = os.getenv("FIREBASE_CREDENTIALS_JSON") or os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
            firebase_b64_env = os.getenv("FIREBASE_CREDENTIALS_BASE64") or os.getenv("FIREBASE_SERVICE_ACCOUNT_BASE64")

            if firebase_json_env:
                try:
                    cred_info = json.loads(firebase_json_env)
                    cred = credentials.Certificate(cred_info)
                    firebase_admin.initialize_app(cred)
                except Exception as ex:
                    raise RuntimeError(f"Invalid FIREBASE_CREDENTIALS_JSON provided: {ex}") from ex
            elif firebase_b64_env:
                try:
                    decoded = base64.b64decode(firebase_b64_env).decode("utf-8")
                    cred_info = json.loads(decoded)
                    cred = credentials.Certificate(cred_info)
                    firebase_admin.initialize_app(cred)
                except Exception as ex:
                    raise RuntimeError(f"Invalid FIREBASE_CREDENTIALS_BASE64 provided: {ex}") from ex
            elif FIREBASE_CREDENTIALS_PATH:
                cred_path = Path(FIREBASE_CREDENTIALS_PATH)
                if not cred_path.is_absolute():
                    cred_path = BASE_DIR / cred_path

                # Check specified credentials path
                if cred_path and cred_path.exists():
                    cred = credentials.Certificate(str(cred_path))
                    firebase_admin.initialize_app(cred)
                else:
                    raise RuntimeError(f"Specified FIREBASE_CREDENTIALS_PATH not found: {cred_path}")
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
