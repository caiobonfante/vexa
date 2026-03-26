"""FastAPI application — Meeting API.

Startup: init DB, connect Redis, configure webhook delivery.
Shutdown: close Redis.

All container operations delegate to Runtime API via httpx.
"""

import asyncio
import logging
import os

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared_models.database import init_db, async_session_local
from shared_models.webhook_delivery import set_redis_client as set_webhook_redis
from shared_models.webhook_retry_worker import (
    start_retry_worker,
    stop_retry_worker,
    set_session_factory as set_retry_session_factory,
)

from .config import REDIS_URL, CORS_ORIGINS
from .meetings import router as meetings_router, set_redis
from .callbacks import router as callbacks_router
from .voice_agent import router as voice_agent_router
from .recordings import router as recordings_router

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("meeting_api")

app = FastAPI(
    title="Meeting API",
    description="Meeting bot management — join/stop bots, voice agent, recordings, webhooks",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers — no prefix, routes already carry /bots etc.
app.include_router(meetings_router)
app.include_router(callbacks_router)
app.include_router(voice_agent_router)
app.include_router(recordings_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.on_event("startup")
async def startup():
    logger.info("Starting Meeting API...")

    # Database
    await init_db()
    logger.info("Database initialized")

    # Redis
    redis_client = None
    try:
        redis_client = aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        await redis_client.ping()
        logger.info("Redis connected")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}", exc_info=True)
        redis_client = None

    set_redis(redis_client)
    app.state.redis = redis_client

    # Webhook retry worker
    set_retry_session_factory(async_session_local)
    if redis_client is not None:
        set_webhook_redis(redis_client)
        asyncio.create_task(start_retry_worker(redis_client))
        logger.info("Webhook retry worker started")
    else:
        logger.warning("Webhook retry worker NOT started — Redis unavailable")

    logger.info("Meeting API ready")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down Meeting API...")

    await stop_retry_worker()

    if hasattr(app.state, "redis") and app.state.redis:
        try:
            await app.state.redis.close()
            logger.info("Redis closed")
        except Exception as e:
            logger.error(f"Error closing Redis: {e}", exc_info=True)
