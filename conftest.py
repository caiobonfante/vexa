"""Root conftest — add package paths so tests can import meeting_api and admin_models."""

import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent
sys.path.insert(0, str(_repo / "packages" / "meeting-api"))
sys.path.insert(0, str(_repo / "libs" / "admin-models"))
