import logging
import time
from ast import TypeVar
from typing import TYPE_CHECKING

import orjson
from redis import Redis

from eodag.rest.config import Settings

logger = logging.getLogger("eodag.rest.cache")

if TYPE_CHECKING:
    from typing import Any, Callable, Coroutine, Optional

    from fastapi import FastAPI, Request


def connect_to_redis(app: FastAPI) -> None:
    """Connect to redis and store instance and script hashes in app state."""
    settings = Settings.from_environment()

    if not settings.redis_hostname:
        # we assume Redis cache is not enabled
        # internal cache will be used instead
        app.state.redis = None
        return None

    r = Redis(
        host=settings.redis_hostname,
        password=settings.redis_password,
        port=settings.redis_port,
        ssl=settings.redis_ssl,
        decode_responses=True,
    )

    app.state.redis = r


T = TypeVar("T")


async def cached_result(
    fn: Callable[[], Coroutine[Any, Any, T]], cache_key: str, request: Request
) -> T:
    """Either get the result from redis or run the function and cache the result."""
    host = request.url.hostname
    host_cache_key = f"{cache_key}:{host}"
    settings = Settings.from_environment()
    r: Optional[Redis] = None
    try:
        r = request.app.state.redis
        if r:
            cached = await r.get(host_cache_key)
            if cached:
                logger.debug("Cache result hit")
                return orjson.loads(cached)
    except Exception as e:
        # Don't fail on redis failure
        logger.error(f"Error in cache: {e}")

    ts = time.perf_counter()
    result = await fn()
    te = time.perf_counter()
    logger.debug(f"Perf: cacheable resource fetch time {te - ts:0.4f}")
    try:
        if r:
            await r.set(host_cache_key, orjson.dumps(result), settings.redis_ttl)
    except Exception as e:
        # Don't fail on redis failure
        logger.error(f"Error in cache: {e}")

    return result


async def cached_order(request: Request):
    """cache for POST /download/order"""
    pass


async def cached_status(request: Request):
    """cache for GET /download/status"""
    pass


async def cached_data(cache_key: str, request: Request):
    """cache for GET /download/data"""
    r: Optional[Redis] = None

    host = request.url.hostname
    host_cache_key = f"{cache_key}:{host}"

    try:
        r = request.app.state.redis
        if r:
            await r.delete(host_cache_key)
    except Exception as e:
        logger.error(f"Error in cache: {e}")
    pass
