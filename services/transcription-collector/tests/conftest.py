"""conftest.py -- pytest path setup for transcription-collector unit tests."""
import sys
import os

# Set required env vars BEFORE importing anything that touches shared_models.database
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_pass")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")

# Add service root so `import filters`, `import config`, etc. work
SERVICE_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, SERVICE_ROOT)

# Add shared-models so any shared imports resolve
SHARED_MODELS = os.path.join(os.path.dirname(__file__), "..", "..", "..", "libs", "shared-models")
sys.path.insert(0, SHARED_MODELS)
