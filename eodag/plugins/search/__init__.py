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

from eodag.utils import DEFAULT_ITEMS_PER_PAGE, DEFAULT_PAGE

if TYPE_CHECKING:
    from typing import Any, Optional, Union

    from requests.auth import AuthBase

    from eodag.plugins.authentication.base import Authentication
    from eodag.types import S3SessionKwargs


@dataclass
class PreparedSearch:
    """An object collecting needed information for search."""

    product_type: Optional[str] = None
    page: Optional[int] = DEFAULT_PAGE
    items_per_page: Optional[int] = DEFAULT_ITEMS_PER_PAGE
    auth: Optional[Union[AuthBase, S3SessionKwargs]] = None
    auth_plugin: Optional[Authentication] = None
    count: bool = True
    url: Optional[str] = None
    info_message: Optional[str] = None
    exception_message: Optional[str] = None

    need_count: bool = field(init=False, repr=False)
    query_params: dict[str, Any] = field(init=False, repr=False)
    query_string: str = field(init=False, repr=False)
    search_urls: list[str] = field(init=False, repr=False)
    product_type_def_params: dict[str, Any] = field(init=False, repr=False)
    total_items_nb: int = field(init=False, repr=False)
    sort_by_qs: str = field(init=False, repr=False)
