"""Tests for the scheduler module."""
import asyncio
import json
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from shared_models.scheduler import (
    schedule_job,
    cancel_job,
    get_job,
    list_jobs,
    recover_orphaned_jobs,
    JOBS_KEY,
    EXECUTING_KEY,
    HISTORY_KEY,
    IDEMPOTENCY_PREFIX,
)


def _make_spec(execute_at=None, url="/bots", method="POST", body=None, idem_key=None):
    """Helper to build a job spec."""
    return {
        "execute_at": execute_at or time.time() + 300,
        "request": {"method": method, "url": url, "body": body or {"test": True}},
        "metadata": {"source": "test"},
        "idempotency_key": idem_key,
    }


class MockRedis:
    """Minimal async Redis mock for sorted set + hash operations."""

    def __init__(self):
        self.zset = {}  # key -> {member: score}
        self.hashes = {}  # key -> {field: value}
        self.strings = {}  # key -> (value, expiry)

    async def zadd(self, key, mapping):
        if key not in self.zset:
            self.zset[key] = {}
        self.zset[key].update(mapping)
        return len(mapping)

    async def zrem(self, key, member):
        if key in self.zset and member in self.zset[key]:
            del self.zset[key][member]
            return 1
        return 0

    async def zrange(self, key, start, end):
        if key not in self.zset:
            return []
        items = sorted(self.zset[key].items(), key=lambda x: x[1])
        return [k for k, v in items]

    async def zrangebyscore(self, key, min_score, max_score):
        if key not in self.zset:
            return []
        max_val = float(max_score) if max_score != "-inf" else float("-inf")
        return [k for k, v in self.zset.get(key, {}).items() if v <= max_val]

    async def hset(self, key, field, value):
        if key not in self.hashes:
            self.hashes[key] = {}
        self.hashes[key][field] = value

    async def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    async def hdel(self, key, field):
        if key in self.hashes and field in self.hashes[key]:
            del self.hashes[key][field]
            return 1
        return 0

    async def hgetall(self, key):
        return dict(self.hashes.get(key, {}))

    async def get(self, key):
        item = self.strings.get(key)
        return item[0] if item else None

    async def set(self, key, value, ex=None):
        self.strings[key] = (value, ex)

    async def expire(self, key, ttl):
        pass


class TestScheduleJob(unittest.IsolatedAsyncioTestCase):

    async def test_schedule_creates_job(self):
        redis = MockRedis()
        spec = _make_spec()
        job = await schedule_job(redis, spec)

        assert job["job_id"].startswith("job_")
        assert job["status"] == "pending"
        assert job["request"]["method"] == "POST"
        assert job["request"]["url"] == "/bots"
        assert len(redis.zset.get(JOBS_KEY, {})) == 1

    async def test_schedule_requires_execute_at(self):
        redis = MockRedis()
        with self.assertRaises(ValueError):
            await schedule_job(redis, {"request": {"url": "/bots"}})

    async def test_schedule_requires_url(self):
        redis = MockRedis()
        with self.assertRaises(ValueError):
            await schedule_job(redis, {"execute_at": time.time() + 100, "request": {}})

    async def test_idempotency_prevents_duplicate(self):
        redis = MockRedis()
        spec = _make_spec(idem_key="test_key_1")

        job1 = await schedule_job(redis, spec)
        job2 = await schedule_job(redis, spec)

        assert job1["job_id"] == job2["job_id"]
        assert len(redis.zset.get(JOBS_KEY, {})) == 1  # only one job in queue

    async def test_different_idempotency_keys_create_separate_jobs(self):
        redis = MockRedis()
        job1 = await schedule_job(redis, _make_spec(idem_key="key_a"))
        job2 = await schedule_job(redis, _make_spec(idem_key="key_b"))

        assert job1["job_id"] != job2["job_id"]
        assert len(redis.zset.get(JOBS_KEY, {})) == 2

    async def test_no_idempotency_key_allows_duplicates(self):
        redis = MockRedis()
        job1 = await schedule_job(redis, _make_spec())
        job2 = await schedule_job(redis, _make_spec())

        assert job1["job_id"] != job2["job_id"]
        assert len(redis.zset.get(JOBS_KEY, {})) == 2

    async def test_iso_timestamp_parsed(self):
        redis = MockRedis()
        spec = _make_spec(execute_at="2026-03-24T10:00:00+00:00")
        job = await schedule_job(redis, spec)
        assert isinstance(job["execute_at"], float)

    async def test_default_retry_config(self):
        redis = MockRedis()
        job = await schedule_job(redis, _make_spec())
        assert job["retry"]["max_attempts"] == 3
        assert job["retry"]["attempt"] == 0
        assert len(job["retry"]["backoff"]) == 3


class TestCancelJob(unittest.IsolatedAsyncioTestCase):

    async def test_cancel_removes_from_queue(self):
        redis = MockRedis()
        job = await schedule_job(redis, _make_spec())
        result = await cancel_job(redis, job["job_id"])

        assert result is not None
        assert result["status"] == "cancelled"
        assert len(redis.zset.get(JOBS_KEY, {})) == 0

    async def test_cancel_nonexistent_returns_none(self):
        redis = MockRedis()
        result = await cancel_job(redis, "job_nonexistent")
        assert result is None

    async def test_cancel_stores_in_history(self):
        redis = MockRedis()
        job = await schedule_job(redis, _make_spec())
        await cancel_job(redis, job["job_id"])

        history = await redis.hget(HISTORY_KEY, job["job_id"])
        assert history is not None
        assert json.loads(history)["status"] == "cancelled"


class TestGetJob(unittest.IsolatedAsyncioTestCase):

    async def test_get_pending_job(self):
        redis = MockRedis()
        job = await schedule_job(redis, _make_spec())
        found = await get_job(redis, job["job_id"])
        assert found is not None
        assert found["job_id"] == job["job_id"]

    async def test_get_nonexistent_returns_none(self):
        redis = MockRedis()
        found = await get_job(redis, "job_nope")
        assert found is None


class TestListJobs(unittest.IsolatedAsyncioTestCase):

    async def test_list_all_pending(self):
        redis = MockRedis()
        await schedule_job(redis, _make_spec())
        await schedule_job(redis, _make_spec())
        jobs = await list_jobs(redis)
        assert len(jobs) == 2

    async def test_list_with_source_filter(self):
        redis = MockRedis()
        spec1 = _make_spec()
        spec1["metadata"] = {"source": "calendar"}
        spec2 = _make_spec()
        spec2["metadata"] = {"source": "manual"}

        await schedule_job(redis, spec1)
        await schedule_job(redis, spec2)

        cal_jobs = await list_jobs(redis, source="calendar")
        assert len(cal_jobs) == 1
        assert cal_jobs[0]["metadata"]["source"] == "calendar"


class TestRecoverOrphaned(unittest.IsolatedAsyncioTestCase):

    async def test_recover_re_queues_executing_jobs(self):
        redis = MockRedis()
        job = {"job_id": "job_orphan", "status": "executing", "execute_at": time.time() - 10}
        await redis.hset(EXECUTING_KEY, "job_orphan", json.dumps(job))

        recovered = await recover_orphaned_jobs(redis)
        assert recovered == 1
        assert len(redis.zset.get(JOBS_KEY, {})) == 1

        executing = await redis.hgetall(EXECUTING_KEY)
        assert len(executing) == 0


if __name__ == "__main__":
    unittest.main()
