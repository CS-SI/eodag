# -*- coding: utf-8 -*-
# Copyright 2025, CS GROUP - France, https://www.cs-soprasteria.com/
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
import functools
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger("eodag.cache")

R = TypeVar("R")


def instance_cached_method(
    maxsize: int = 128,
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """
    Decorator to cache an instance method using functools.lru_cache on a per-instance basis.

    This decorator creates a separate LRU cache for each instance of the class,
    ensuring that cached results are not shared across instances.

    The cache stores up to `maxsize` entries (default 128), which matches the
    default cache size of functools.lru_cache. This default provides a good balance
    between memory consumption and cache hit rate for most use cases.

    :param maxsize: Maximum number of cached calls to store per instance.
                    Defaults to 128, consistent with functools.lru_cache.
    :return: Decorated method with per-instance caching enabled.
    """

    def decorator(method: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(method)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> R:
            cache_name = f"_cached_{method.__name__}"
            if not hasattr(self, cache_name):
                cached = functools.lru_cache(maxsize=maxsize)(
                    method.__get__(self, type(self))
                )
                setattr(self, cache_name, cached)

            cached_func = getattr(self, cache_name)
            before_hits = cached_func.cache_info().hits
            result = cached_func(*args, **kwargs)
            after_hits = cached_func.cache_info().hits

            if after_hits > before_hits:
                logger.debug(
                    f"Cache hit for {method.__qualname__} with args={args}, kwargs={kwargs}"
                )
            return result

        return wrapper

    return decorator
