# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
from typing import Any, Callable, Coroutine, Dict, TypeVar

import orjson
from cachetools import LRUCache
from fastapi import FastAPI, Request
from redis.asyncio import Redis

from eodag.rest.config import Settings

logger = logging.getLogger("eodag.rest.utils")

T = TypeVar("T")


def init_cache(app: FastAPI) -> None:
    """Connect to redis or default to local cache"""
    settings = Settings.from_environment()

    if settings.redis_hostname:
        r = Redis(
            host=settings.redis_hostname,
            password=settings.redis_password,
            port=settings.redis_port,
            ssl=settings.redis_ssl,
            decode_responses=True,
        )
        app.state.redis = r
    else:
        app.state.cache = LRUCache(maxsize=settings.local_cache_maxsize)


async def redis_cached(
    fn: Callable[[], Coroutine[Any, Any, T]], cache_key: str, request: Request
) -> T:
    """Either get the result from Redis or run the function and cache the result."""
    settings = Settings.from_environment()

    host = request.url.hostname
    host_cache_key = f"{cache_key}:{host}"

    try:
        r: Redis[Any] = request.app.state.redis
        cached: Any = await r.get(host_cache_key)
        if cached:
            logger.debug("Cache result hit")
            return orjson.loads(cached)  # type: ignore
    except Exception as e:
        logger.error(f"Error in cache: {e}")
        if settings.debug:
            raise

    result = await fn()

    logger.debug("Perf: cacheable resource fetch time")
    try:
        if r:
            await r.set(host_cache_key, orjson.dumps(result), settings.redis_ttl)  # type: ignore
    except Exception as e:
        logger.error(f"Error in cache: {e}")
        if settings.debug:
            raise

    return result


async def local_cached(
    fn: Callable[[], Coroutine[Any, Any, T]], cache_key: str, request: Request
) -> T:
    """Either get the result from local cache or run the function and cache the result."""
    settings = Settings.from_environment()

    try:
        c: Dict[str, Any] = request.app.state.cache

        if cached := c.get(cache_key):
            logger.debug("Cache result hit")
            return orjson.loads(cached)  # type: ignore
    except Exception as e:
        logger.error(f"Error in cache: {e}")
        if settings.debug:
            raise

    result = await fn()

    try:
        c[cache_key] = orjson.dumps(result)  # type: ignore
    except Exception as e:
        logger.error(f"Error in cache: {e}")
        if settings.debug:
            raise

    return result
