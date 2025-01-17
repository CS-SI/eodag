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
from typing import Any, Callable, Coroutine, TypeVar, cast

import orjson
from cachetools import LRUCache
from fastapi import FastAPI, Request

from eodag.rest.config import Settings
from eodag.utils import urlsplit

logger = logging.getLogger("eodag.rest.utils")

T = TypeVar("T")


def init_cache(app: FastAPI) -> None:
    """Connect to local cache"""
    settings = Settings.from_environment()

    app.state.cache = LRUCache(maxsize=settings.cache_maxsize)


async def cached(
    fn: Callable[[], Coroutine[Any, Any, T]], cache_key: str, request: Request
) -> T:
    """Either get the result from local cache or run the function and cache the result."""
    settings = Settings.from_environment()

    host = urlsplit(cast(str, request.state.url_root)).netloc

    host_cache_key = f"{cache_key}:{host}"

    try:
        c: dict[str, Any] = request.app.state.cache

        if cached := c.get(host_cache_key):
            logger.debug("Cache result hit")
            return orjson.loads(cached)  # type: ignore
    except Exception as e:
        logger.error(f"Error in cache: {e}")
        if settings.debug:
            raise

    result = await fn()

    try:
        c[host_cache_key] = orjson.dumps(result)  # type: ignore
    except Exception as e:
        logger.error(f"Error in cache: {e}")
        if settings.debug:
            raise

    return result
