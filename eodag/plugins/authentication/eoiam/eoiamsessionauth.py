# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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

from typing import TYPE_CHECKING

import requests
from requests.auth import AuthBase

if TYPE_CHECKING:
    from .eoiamauth import EOIAMAuth


class EOIAMSessionAuth(AuthBase):
    """AuthBase wrapper using a requests.Session with lazy SAML login."""

    def __init__(self, auth_plugin: EOIAMAuth):
        """Initialize with the EOIAMAuth plugin to access its session and login method."""
        self.auth_plugin = auth_plugin

    def __call__(self, request):
        """
        This is called by requests before sending a request.
        We use the session's get/post to ensure login happens if needed.
        """

        session = self.auth_plugin.session
        try:
            resp = session.get(request.url, allow_redirects=True)
            if "Earth Observation Identity and Access Management System" in resp.text:
                resp = self.auth_plugin._login_from_html(resp.text, request.url)

            # Copy cookies from session to the request
            request.prepare_cookies(self.auth_plugin.session.cookies)

            return request
        finally:
            self.auth_plugin.session = requests.Session()


__all__ = ["EOIAMSessionAuth"]
