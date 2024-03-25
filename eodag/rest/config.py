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
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from eodag.rest.constants import DEFAULT_MAXSIZE, DEFAULT_TTL


class Settings(BaseSettings):
    """EODAG Server config"""

    # local cache config
    cache_ttl: int = Field(default=DEFAULT_TTL)
    local_cache_maxsize: int = Field(default=DEFAULT_MAXSIZE)

    redis_hostname: Optional[str] = Field(default=None)
    redis_password: Optional[str] = Field(default=None)
    redis_port: int = 6379
    redis_ssl: bool = True
    redis_ttl: int = Field(default=DEFAULT_TTL)

    debug: bool = False

    model_config = SettingsConfigDict(
        env_prefix="EODAG_", extra="ignore", env_nested_delimiter="__"
    )

    @classmethod
    @lru_cache(maxsize=1)
    def from_environment(cls) -> Settings:
        """Get settings"""
        return Settings()
