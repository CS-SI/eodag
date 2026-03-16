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

import logging
from json import JSONDecodeError
from typing import TYPE_CHECKING, Optional

import requests
from requests.auth import AuthBase

from eodag.utils import HTTP_REQ_TIMEOUT
from eodag.utils.exceptions import AuthenticationError, TimeOutError

if TYPE_CHECKING:
    from typing import Pattern

    from requests import PreparedRequest

logger = logging.getLogger("eodag.auth.sas_auth")


class RequestsSASAuth(AuthBase):
    """A custom authentication class to be used with requests module"""

    def __init__(
        self,
        auth_uri: str,
        signed_url_key: str,
        headers: Optional[dict[str, str]] = None,
        ssl_verify: bool = True,
        matching_url: Optional[Pattern[str]] = None,
    ) -> None:
        self.auth_uri = auth_uri
        self.signed_url_key = signed_url_key
        self.headers = headers
        self.signed_urls: dict[str, str] = {}
        self.ssl_verify = ssl_verify
        self.matching_url = matching_url

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Perform the actual authentication"""
        # if matching_url is set, check if request.url matches
        if (
            self.matching_url
            and request.url
            and not self.matching_url.match(request.url)
        ):
            return request

        # update headers
        if self.headers and isinstance(self.headers, dict):
            for k, v in self.headers.items():
                request.headers[k] = v

        # request the signed_url
        req_signed_url = self.auth_uri.format(url=request.url)
        if req_signed_url not in self.signed_urls.keys():
            logger.debug(f"Signed URL request: {req_signed_url}")
            try:
                response = requests.get(
                    req_signed_url,
                    headers=self.headers,
                    timeout=HTTP_REQ_TIMEOUT,
                    verify=self.ssl_verify,
                )
                response.raise_for_status()
                signed_url = response.json().get(self.signed_url_key)
            except requests.exceptions.Timeout as exc:
                raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
            except (requests.RequestException, JSONDecodeError, KeyError) as e:
                raise AuthenticationError("Could no get signed url", str(e)) from e
            else:
                self.signed_urls[req_signed_url] = signed_url

        request.url = self.signed_urls[req_signed_url]

        return request


__all__ = ["RequestsSASAuth"]
