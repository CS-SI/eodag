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
import time
from typing import Any, Callable, Coroutine, Dict, Optional, TypeVar

import orjson
from cachetools import LRUCache
from fastapi import FastAPI, Request
from redis.asyncio import Redis

from eodag.rest.config import Settings
from eodag.utils import deepcopy

logger = logging.getLogger("eodag.rest.utils")

T = TypeVar("T")


def init_cache(app: FastAPI) -> None:
    """Connect to redis or default to local cache"""
    settings = Settings.from_environment()

    app.state.cache = LRUCache(maxsize=settings.local_cache_maxsize)

    if settings.redis_hostname:
        r = Redis(
            host=settings.redis_hostname,
            password=settings.redis_password,
            port=settings.redis_port,
            ssl=settings.redis_ssl,
            decode_responses=True,
        )
        app.state.redis = r


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


async def cached_item_collection(
    fn: Callable[[], Coroutine[Any, Any, Dict[str, Any]]],
    cache_key: str,
    request: Request,
) -> Dict[str, Any]:
    """
    Cache an item collection search result
    Either get the result from redis or run the function and cache the result.
    """
    settings = Settings.from_environment()

    host = request.url.hostname
    host_cache_key = f"{cache_key}:{host}"

    try:
        ts = time.perf_counter()
        r: Redis[Any] = request.app.state.redis
        cached: Any = await r.get(host_cache_key)
        if cached:
            logger.debug("Cache result hit")
            item_collection: Dict[str, Any] = orjson.loads(cached)
            for i, item in enumerate(item_collection["features"]):
                cached_item = await r.get(item)
                if not cached_item:
                    raise ValueError(f"item {item} not found")
                item_collection["features"][i] = orjson.loads(cached_item)
            te = time.perf_counter()
            logger.debug(f"Perf: retrieved from cache: {te - ts:0.4f}")
            return item_collection
    except Exception as e:
        logger.error(f"Error in cache: {e}")
        if settings.debug:
            raise

    ts = time.perf_counter()
    item_collection = await fn()
    te = time.perf_counter()

    logger.debug(f"Perf: cacheable resource fetch time: {te - ts:0.4f}")

    ts = time.perf_counter()
    cached_item_collection = deepcopy(item_collection)
    features = cached_item_collection["features"]

    try:
        if r:
            # we assume all items belong to the same provider and collection
            provider = next(
                p["name"]
                for p in features[0]["properties"]["providers"]
                if "host" in p["roles"]
            )
            collection = features[0]["collection"]
            for i, item in enumerate(features):
                i_key = f'{provider}:{collection}:{item["id"]}:{host}'
                await r.set(i_key, orjson.dumps(item), settings.redis_ttl)
                features[i] = i_key
            await r.set(
                host_cache_key, orjson.dumps(cached_item_collection), settings.redis_ttl
            )
            te = time.perf_counter()
            logger.debug(f"Perf: cache set: {te - ts:0.4f}")
    except Exception as e:
        logger.error(f"Error in cache: {e}")
        if settings.debug:
            raise

    return item_collection


async def cached_item(
    request: Request, provider: str, collection: str, item: str
) -> Optional[Dict[str, Any]]:
    """
    Extract cached item from redis
    """
    settings = Settings.from_environment()

    host = request.url.hostname
    host_cache_key = f"{provider}:{collection}:{item}:{host}"

    try:
        r: Redis[Any] = request.app.state.redis
        cached: Any = await r.get(host_cache_key)
        if cached:
            logger.debug("Cache result hit")
            return orjson.loads(cached)
    except Exception as e:
        logger.error(f"Error in cache: {e}")
        if settings.debug:
            raise
    return None
