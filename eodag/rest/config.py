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
from typing import Annotated, Union

from pydantic import Field
from pydantic.functional_validators import BeforeValidator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Doc

from eodag.rest.constants import DEFAULT_MAXSIZE, DEFAULT_TTL


def str2liststr(raw: Union[str, list[str]]) -> list[str]:
    """Convert str to list[str]"""
    if isinstance(raw, list):
        return raw
    return raw.split(",")


class Settings(BaseSettings):
    """EODAG Server config"""

    # local cache config
    cache_ttl: int = Field(default=DEFAULT_TTL)
    cache_maxsize: int = Field(default=DEFAULT_MAXSIZE)

    debug: bool = False

    stac_api_title: str = "eodag-stac-api"
    stac_api_description: str = "STAC API provided by EODAG"
    stac_api_landing_id: str = "eodag-stac-api"

    origin_url_blacklist: Annotated[
        Union[str, list[str]],
        BeforeValidator(str2liststr),
        Doc(
            "Hide from clients items assets' alternative URLs starting with URLs from the list"
        ),
    ] = Field(default=[])

    model_config = SettingsConfigDict(
        env_prefix="EODAG_", extra="ignore", env_nested_delimiter="__"
    )

    @classmethod
    @lru_cache(maxsize=1)
    def from_environment(cls) -> Settings:
        """Get settings"""
        return Settings()
