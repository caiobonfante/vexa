"""Shared fixtures for bot lifecycle E2E tests.

Requires a running meeting-api at localhost:8056 and Redis at localhost:6379.
"""

import json
import os
import time
from typing import Optional

import httpx
import pytest
import redis as redis_lib


def pytest_addoption(parser):
    parser.addoption("--meeting-url", default=os.getenv("MEETING_URL", ""))
    parser.addoption("--native-meeting-id", default=os.getenv("NATIVE_MEETING_ID", ""))
    parser.addoption("--api-key", default=os.getenv("BOT_API_KEY", ""))


API_BASE = os.getenv("MEETING_API_URL", "http://localhost:8056")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


@pytest.fixture(scope="session")
def api_key(request):
    """API key for user 5.  Mint one if not provided."""
    key = request.config.getoption("--api-key")
    if key:
        return key
    # Auto-mint via admin endpoint
    with httpx.Client(base_url=API_BASE, timeout=10) as c:
        resp = c.post(
            "/admin/users/5/tokens?scope=bot",
            headers={"X-Admin-API-Key": "changeme"},
        )
        resp.raise_for_status()
        return resp.json()["token"]


@pytest.fixture(scope="session")
def api_client(api_key):
    with httpx.Client(
        base_url=API_BASE,
        timeout=30,
        headers={"X-API-Key": api_key},
    ) as c:
        # Skip all tests if service unreachable
        # Gateway may not proxy /health (404), so catch both connection and HTTP errors
        try:
            r = c.get("/bots/status")
            r.raise_for_status()
        except (httpx.ConnectError, httpx.HTTPStatusError):
            pytest.skip(f"meeting-api not reachable at {API_BASE}")
        yield c


@pytest.fixture(scope="session")
def redis_client():
    r = redis_lib.from_url(REDIS_URL, decode_responses=True)
    try:
        r.ping()
    except redis_lib.ConnectionError:
        pytest.skip("Redis not available")
    yield r
    r.close()


@pytest.fixture(scope="session")
def meeting_url(request):
    url = request.config.getoption("--meeting-url")
    if not url:
        pytest.skip("--meeting-url not provided")
    return url


@pytest.fixture(scope="session")
def native_meeting_id(request):
    mid = request.config.getoption("--native-meeting-id")
    if not mid:
        pytest.skip("--native-meeting-id not provided")
    return mid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_meeting(
    client: httpx.Client,
    platform: str,
    native_id: str,
    meeting_db_id: Optional[int] = None,
) -> Optional[dict]:
    """Find a meeting by DB id (preferred) or native_id (fallback)."""
    resp = client.get("/meetings", params={"platform": platform, "limit": 20})
    if resp.status_code != 200:
        return None
    for m in resp.json().get("meetings", []):
        if meeting_db_id is not None:
            if m.get("id") == meeting_db_id:
                return m
        elif m.get("native_meeting_id") == native_id:
            return m
    return None


# Keep old name as alias for backward compat
get_meeting_by_native_id = get_meeting


def wait_for_status(
    client: httpx.Client,
    platform: str,
    native_id: str,
    target_statuses: list[str],
    timeout_s: int = 120,
    poll_interval: float = 2.0,
    meeting_db_id: Optional[int] = None,
) -> dict:
    """Poll GET /meetings until the meeting reaches one of *target_statuses*.

    Returns the meeting dict on success, raises TimeoutError otherwise.
    """
    deadline = time.time() + timeout_s
    last_status = None
    while time.time() < deadline:
        meeting = get_meeting(client, platform, native_id, meeting_db_id)
        if meeting:
            last_status = meeting.get("status")
            if last_status in target_statuses:
                return meeting
        time.sleep(poll_interval)
    raise TimeoutError(
        f"Meeting {platform}/{native_id} (db_id={meeting_db_id}) did not reach "
        f"{target_statuses} within {timeout_s}s (last status: {last_status})"
    )


class RedisEventCollector:
    """Background collector for Redis pub/sub events on meeting channels.

    Uses pattern subscribe (bm:meeting:*:status) so it can start BEFORE
    the bot is created. Filter by meeting_db_id when stopping.

    Usage:
        collector = RedisEventCollector(redis_client)
        collector.start()          # subscribe to all meeting status events
        # ... create bot, get meeting_db_id ...
        events = collector.stop(meeting_db_id=123)  # filter to this meeting
    """

    def __init__(self, redis_client: redis_lib.Redis, meeting_db_id: int = None):
        self.meeting_db_id = meeting_db_id
        self.pattern = "bm:meeting:*:status"
        self.pubsub = redis_client.pubsub()
        self.events: list[dict] = []
        self._thread = None

    def start(self):
        import threading

        self.pubsub.psubscribe(self.pattern)
        # Consume the subscribe confirmation message
        self.pubsub.get_message(timeout=2.0)

        self._stop_event = threading.Event()

        def _collect():
            while not self._stop_event.is_set():
                msg = self.pubsub.get_message(timeout=0.5)
                if msg and msg["type"] == "pmessage":
                    try:
                        self.events.append({"channel": msg["channel"], "data": json.loads(msg["data"])})
                    except (json.JSONDecodeError, TypeError):
                        pass

        self._thread = threading.Thread(target=_collect, daemon=True)
        self._thread.start()

    def stop(self, meeting_db_id: int = None) -> list[dict]:
        mid = meeting_db_id or self.meeting_db_id
        if self._stop_event:
            self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        self.pubsub.punsubscribe(self.pattern)
        self.pubsub.close()
        # Filter to the specific meeting if requested
        if mid:
            target_channel = f"bm:meeting:{mid}:status"
            filtered = [ev["data"] for ev in self.events if ev.get("channel") == target_channel]
            return filtered
        return [ev["data"] for ev in self.events]
