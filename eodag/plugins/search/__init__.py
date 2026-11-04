# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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
"""EODAG search package"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from eodag.utils import DEFAULT_LIMIT, DEFAULT_PAGE

if TYPE_CHECKING:
    from typing import Any

    from mypy_boto3_s3 import S3ServiceResource
    from requests.auth import AuthBase

    from eodag.plugins.authentication.base import Authentication


@dataclass
class PreparedSearch:
    """An object collecting needed information for search."""

    collection: str | None = None
    page: int | None = DEFAULT_PAGE
    limit: int | None = DEFAULT_LIMIT
    auth: AuthBase | S3ServiceResource | None = None
    auth_plugin: Authentication | None = None
    count: bool = True
    url: str | None = None
    info_message: str | None = None
    exception_message: str | None = None
    next_page_token: str | None = None
    next_page_token_key: str | None = None

    need_count: bool = field(init=False, repr=False)
    query_params: dict[str, Any] = field(init=False, repr=False)
    query_string: str = field(init=False, repr=False)
    search_urls: list[str] = field(init=False, repr=False)
    collection_def_params: dict[str, Any] = field(init=False, repr=False)
    total_items_nb: int = field(init=False, repr=False)
    sort_by_qs: str = field(init=False, repr=False)
    raise_errors: bool | None = field(init=False, repr=False)
