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
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse

from requests.auth import AuthBase

if TYPE_CHECKING:
    from requests import PreparedRequest


class QueryStringAuth(AuthBase):
    """ "QueryStringAuth custom authentication class to be used with requests module"""

    def __init__(self, **parse_args: Any) -> None:
        self.parse_args = parse_args

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Perform the actual authentication"""
        parts = urlparse(str(request.url))
        query_dict = parse_qs(parts.query)
        query_dict.update(self.parse_args)
        url_without_args = parts._replace(query="").geturl()

        request.prepare_url(url_without_args, query_dict)
        return request


__all__ = ["QueryStringAuth"]
