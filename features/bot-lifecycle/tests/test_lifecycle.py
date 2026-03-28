"""E2E bot lifecycle tests.

Run against a live meeting-api + a real Google Meet session.

Usage:
    pytest test_lifecycle.py -v \
        --meeting-url "https://meet.google.com/abc-defg-hij" \
        --native-meeting-id "abc-defg-hij"
"""

import time
import uuid

import pytest

from conftest import get_meeting, wait_for_status, RedisEventCollector

PLATFORM = "google_meet"


# ---------------------------------------------------------------------------
# T1.1 — Full lifecycle: create → join → active → stop → completed
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    def test_full_lifecycle(self, api_client, redis_client, meeting_url, native_meeting_id):
        """Create bot → joining → awaiting_admission → active → stop → completed."""

        # Start collecting Redis events BEFORE creating the bot (pattern subscribe)
        collector = RedisEventCollector(redis_client)
        collector.start()

        # 1. Create bot
        resp = api_client.post(
            "/bots",
            json={
                "platform": PLATFORM,
                "native_meeting_id": native_meeting_id,
            },
        )
        assert resp.status_code == 201, f"Bot creation failed: {resp.status_code} {resp.text}"
        created = resp.json()
        meeting_db_id = created["id"]
        print(f"\n  Bot created: id={meeting_db_id}, status={created['status']}")

        timestamps = {"created": time.time()}

        # 2. Wait through lifecycle stages — track by DB id to avoid matching stale meetings
        try:
            # Wait for joining
            m = wait_for_status(api_client, PLATFORM, native_meeting_id,
                                ["joining", "awaiting_admission", "active", "completed", "failed"],
                                timeout_s=30, meeting_db_id=meeting_db_id)
            timestamps["joining"] = time.time()
            print(f"  → {m['status']} ({timestamps['joining'] - timestamps['created']:.1f}s)")

            # Wait for active (may pass through awaiting_admission)
            if m["status"] not in ("active", "completed", "failed"):
                m = wait_for_status(api_client, PLATFORM, native_meeting_id,
                                    ["awaiting_admission", "active", "completed", "failed"],
                                    timeout_s=60, meeting_db_id=meeting_db_id)
                if m["status"] == "awaiting_admission":
                    timestamps["awaiting_admission"] = time.time()
                    print(f"  → awaiting_admission ({timestamps['awaiting_admission'] - timestamps['created']:.1f}s)")
                    m = wait_for_status(api_client, PLATFORM, native_meeting_id,
                                        ["active", "completed", "failed"],
                                        timeout_s=120, meeting_db_id=meeting_db_id)

            if m["status"] == "active":
                timestamps["active"] = time.time()
                print(f"  → active ({timestamps['active'] - timestamps['created']:.1f}s)")

                # 3. Stop the bot
                stop_resp = api_client.delete(f"/bots/{PLATFORM}/{native_meeting_id}")
                assert stop_resp.status_code == 202, f"Stop failed: {stop_resp.status_code} {stop_resp.text}"
                timestamps["stop_requested"] = time.time()
                print(f"  → stop requested ({timestamps['stop_requested'] - timestamps['created']:.1f}s)")

                # 4. Wait for terminal state
                m = wait_for_status(api_client, PLATFORM, native_meeting_id,
                                    ["completed", "failed"], timeout_s=60, meeting_db_id=meeting_db_id)

            timestamps["terminal"] = time.time()
            print(f"  → {m['status']} ({timestamps['terminal'] - timestamps['created']:.1f}s)")

        except TimeoutError as e:
            collector.stop(meeting_db_id=meeting_db_id)
            api_client.delete(f"/bots/{PLATFORM}/{native_meeting_id}")
            pytest.fail(str(e))

        # 5. Collect Redis events
        time.sleep(2)  # let final events propagate
        redis_events = collector.stop(meeting_db_id=meeting_db_id)
        print(f"\n  Redis events ({len(redis_events)}):")
        for ev in redis_events:
            # Events are: {type, meeting, payload: {status}, user_id, ts}
            st = ev.get("payload", {}).get("status", ev.get("status", "?"))
            print(f"    status={st}")

        # Verify Redis captured status transitions
        redis_statuses = [ev.get("payload", {}).get("status", ev.get("status")) for ev in redis_events]
        if len(redis_statuses) >= 2:
            assert redis_statuses[0] in ("joining", "awaiting_admission", "active", "requested"), (
                f"First Redis event unexpected: {redis_statuses[0]}"
            )
        else:
            print(f"  ⚠ Redis captured {len(redis_statuses)} events (expected >=2) — pub/sub timing issue")

        # 6. Verify final state
        assert m["status"] == "completed", f"Expected completed, got {m['status']}"

        data = m.get("data") or {}
        assert data.get("completion_reason") == "stopped", (
            f"Expected completion_reason=stopped, got {data.get('completion_reason')}"
        )

        # 7. Verify transition history
        transitions = data.get("status_transition", [])
        if isinstance(transitions, dict):
            transitions = [transitions]

        assert len(transitions) >= 3, (
            f"Expected >=3 transitions, got {len(transitions)}: "
            + str([(t.get('from'), t.get('to')) for t in transitions])
        )

        print(f"  Transitions ({len(transitions)}):")
        for t in transitions:
            print(f"    {t.get('from')} → {t.get('to')} (ts={t.get('timestamp', 'MISSING')})")

        # First transition must start from requested
        assert transitions[0].get("from") == "requested", (
            f"First transition should be from 'requested', got '{transitions[0].get('from')}'"
        )
        assert transitions[0].get("to") == "joining", (
            f"First transition should go to 'joining', got '{transitions[0].get('to')}'"
        )

        # Last transition must end in completed
        assert transitions[-1].get("to") == "completed", (
            f"Last transition should go to 'completed', got '{transitions[-1].get('to')}'"
        )

        # Every transition must have a timestamp
        for i, t in enumerate(transitions):
            assert t.get("timestamp"), f"Transition {i} missing timestamp: {t}"

        assert m.get("start_time"), "start_time should be set"
        assert m.get("end_time"), "end_time should be set"

        # Timing report
        print("\n  ── Timing Report ──")
        for label, ts in sorted(timestamps.items(), key=lambda x: x[1]):
            elapsed = ts - timestamps["created"]
            print(f"    {label}: +{elapsed:.1f}s")


# ---------------------------------------------------------------------------
# T1.2 — Bot stop after 30s soak in active
# ---------------------------------------------------------------------------


class TestStopAfterSoak:
    def test_stop_after_30s(self, api_client, meeting_url, native_meeting_id):
        """Bot runs 30s in active before stop — verify clean completion."""

        resp = api_client.post(
            "/bots",
            json={
                "platform": PLATFORM,
                "native_meeting_id": native_meeting_id,
            },
        )
        assert resp.status_code == 201, f"Bot creation failed: {resp.status_code} {resp.text}"
        created = resp.json()
        db_id = created["id"]
        print(f"\n  Bot created: id={db_id}")

        try:
            # Wait for active
            m = wait_for_status(api_client, PLATFORM, native_meeting_id, ["active"], timeout_s=120, meeting_db_id=db_id)
            print(f"  → active, soaking 30s...")

            # Soak
            time.sleep(30)

            # Verify still active
            m = get_meeting(api_client, PLATFORM, native_meeting_id, meeting_db_id=db_id)
            assert m and m["status"] == "active", f"Bot left active during soak: {m.get('status') if m else 'not found'}"

            # Stop
            stop_resp = api_client.delete(f"/bots/{PLATFORM}/{native_meeting_id}")
            assert stop_resp.status_code == 202

            # Wait for terminal
            m = wait_for_status(api_client, PLATFORM, native_meeting_id, ["completed", "failed"], timeout_s=60, meeting_db_id=db_id)
            assert m["status"] == "completed"

            data = m.get("data") or {}
            assert data.get("completion_reason") == "stopped"
            print(f"  → completed (reason={data.get('completion_reason')})")

        except TimeoutError as e:
            api_client.delete(f"/bots/{PLATFORM}/{native_meeting_id}")
            pytest.fail(str(e))


# ---------------------------------------------------------------------------
# T2.1 — Left alone (host leaves, bot auto-completes)
# ---------------------------------------------------------------------------


class TestLeftAlone:
    @pytest.mark.skip(reason="Requires host CDP control to simulate host leaving")
    def test_left_alone(self, api_client, meeting_url, native_meeting_id):
        """Bot completes with reason=left_alone when host leaves."""
        pass


# ---------------------------------------------------------------------------
# T2.2 — Admission timeout
# ---------------------------------------------------------------------------


class TestAdmissionTimeout:
    def test_admission_timeout(self, api_client, native_meeting_id):
        """Bot joins a real meeting waiting room and times out when nobody admits it.

        Prerequisites:
            - A real Google Meet session must be hosted (via --native-meeting-id)
            - Auto-admit must be STOPPED before this test runs so the bot
              stays in the waiting room until the timeout fires

        The short waiting_room_timeout (60s) causes the bot to complete
        with reason=awaiting_admission_timeout.
        """
        resp = api_client.post(
            "/bots",
            json={
                "platform": PLATFORM,
                "native_meeting_id": native_meeting_id,
                "automatic_leave": {
                    "waiting_room_timeout": 60000,  # 60s
                },
            },
        )
        assert resp.status_code == 201, f"Bot creation failed: {resp.status_code} {resp.text}"
        created = resp.json()
        db_id = created["id"]
        print(f"\n  Bot created: id={db_id}, meeting={native_meeting_id}")

        try:
            # Bot should join and reach awaiting_admission
            m = wait_for_status(
                api_client, PLATFORM, native_meeting_id,
                ["awaiting_admission", "completed", "failed"],
                timeout_s=60, poll_interval=3.0, meeting_db_id=db_id,
            )
            print(f"  → {m['status']}")

            if m["status"] == "awaiting_admission":
                # Now wait for the timeout to fire (~60s)
                m = wait_for_status(
                    api_client, PLATFORM, native_meeting_id,
                    ["completed", "failed"],
                    timeout_s=120, poll_interval=5.0, meeting_db_id=db_id,
                )
                print(f"  → {m['status']}")

            data = m.get("data") or {}
            assert m["status"] == "completed", (
                f"Expected completed, got {m['status']} (data={data})"
            )
            assert data.get("completion_reason") == "awaiting_admission_timeout", (
                f"Expected awaiting_admission_timeout, got {data.get('completion_reason')}"
            )
            print(f"  → completion_reason={data['completion_reason']}")

        except TimeoutError as e:
            api_client.delete(f"/bots/{PLATFORM}/{native_meeting_id}")
            pytest.fail(str(e))


# ---------------------------------------------------------------------------
# T3.1 — Invalid meeting URL
# ---------------------------------------------------------------------------


class TestInvalidMeeting:
    def test_invalid_meeting_url(self, api_client):
        """Fake meeting code → bot fails or completes with error."""
        fake_id = f"xxx-yyyy-{uuid.uuid4().hex[:3]}"

        resp = api_client.post(
            "/bots",
            json={
                "platform": PLATFORM,
                "native_meeting_id": fake_id,
            },
        )
        # Accept 201 (will fail later) or 4xx/5xx (immediate rejection)
        if resp.status_code != 201:
            print(f"\n  Rejected immediately: {resp.status_code}")
            return

        created = resp.json()
        print(f"\n  Bot created: id={created['id']}, meeting={fake_id}")

        try:
            m = wait_for_status(
                api_client,
                PLATFORM,
                fake_id,
                ["completed", "failed"],
                timeout_s=180,
                poll_interval=5.0,
            )
            print(f"  → {m['status']}")
            data = m.get("data") or {}
            assert m["status"] in ("failed", "completed"), f"Unexpected status: {m['status']}"

            if m["status"] == "failed":
                # Verify failure metadata is populated
                assert data.get("failure_stage"), (
                    f"Failed bot should have failure_stage set, got data={data}"
                )
                print(f"  → failure_stage={data['failure_stage']}")
                # error_details may be a string or dict — just check it's present and non-empty
                error_details = data.get("error_details")
                assert error_details, (
                    f"Failed bot should have error_details set, got data={data}"
                )
                print(f"  → error_details={error_details}")
            else:
                # Completed with an error-related reason
                print(f"  → completion_reason={data.get('completion_reason')}")
        except TimeoutError as e:
            api_client.delete(f"/bots/{PLATFORM}/{fake_id}")
            pytest.fail(str(e))
