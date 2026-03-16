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
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from requests import PreparedRequest
from requests.auth import AuthBase


class RequestsTokenAuth(AuthBase):
    """A custom authentication class to be used with requests module"""

    def __init__(
        self,
        token: str,
        where: str,
        qs_key: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        self.token = token
        self.where = where
        self.qs_key = qs_key
        self.headers = headers

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Perform the actual authentication"""
        if self.headers and isinstance(self.headers, dict):
            for k, v in self.headers.items():
                request.headers[k] = v
        if self.where == "qs":
            parts = urlparse(str(request.url))
            qs = parse_qs(parts.query)
            if self.qs_key is not None:
                qs[self.qs_key] = [self.token]
            request.url = urlunparse(
                (
                    parts.scheme,
                    parts.netloc,
                    parts.path,
                    parts.params,
                    urlencode(qs),
                    parts.fragment,
                )
            )
        elif self.where == "header":
            request.headers["Authorization"] = request.headers.get(
                "Authorization", "Bearer {token}"
            ).format(token=self.token)
        return request


__all__ = ["RequestsTokenAuth"]
