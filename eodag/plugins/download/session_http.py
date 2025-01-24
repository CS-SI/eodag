# -*- coding: utf-8 -*-
# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from requests import Session

from eodag.plugins.download.http import HTTPDownload

if TYPE_CHECKING:
    from requests import PreparedRequest, Response

logger = logging.getLogger("eodag.download.session_http")


class SessionWithHeaderRedirection(Session):
    """:class:`requests.Session` overridden with header redirection."""

    AUTH_HOST = "urs.earthdata.nasa.gov"

    # Overrides from the library to keep headers when redirected to or from the NASA auth host.
    def rebuild_auth(
        self, prepared_request: PreparedRequest, response: Response
    ) -> None:
        """Rebuild the auth information in the prepared request."""
        headers = prepared_request.headers
        url = prepared_request.url
        if "Authorization" in headers:
            original_parsed = urlparse(response.request.url)
            redirect_parsed = urlparse(url)

            if (
                (original_parsed.hostname != redirect_parsed.hostname)
                and redirect_parsed.hostname != self.AUTH_HOST
                and original_parsed.hostname != self.AUTH_HOST
            ):
                del headers["Authorization"]


class SessionHTTPDownload(HTTPDownload):
    """SessionHTTPDownload plugin. Handles product download over HTTP protocol, while keeping the session."""

    HTTPSession = SessionWithHeaderRedirection
