# -*- coding: utf-8 -*-
# Copyright 2023, CS GROUP - France, https://www.csgroup.eu/
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
import logging
import re
from datetime import datetime
from typing import Any, Dict
from urllib.parse import unquote

from eodag.plugins.authentication.base import Authentication
from eodag.utils import format_dict_items
from eodag.utils.exceptions import AuthenticationError
from eodag.utils.http import HttpRequestParams, http

logger = logging.getLogger("eodag.plugins.auth.sas_auth")


class SignedURLs:
    """
    A class used to represent Signed URLs.

    :param str signed_url: The signed URL.
    :param datetime expiration_date: The expiration date of the signed URL.
    """

    signed_url: str
    expiration_date: datetime

    def __init__(self, signed_url: str, expiration_date: datetime) -> None:
        """
        Initialize the SignedURLs class.

        :param str signed_url: The signed URL.
        :param datetime expiration_date: The expiration date of the signed URL.
        """
        self.signed_url = signed_url
        self.expiration_date = expiration_date


class SASAuth(Authentication):
    """SASAuth authentication plugin"""

    # current URL to authenticate
    url: str = ""
    # signed URLs store
    signed_urls: Dict[str, SignedURLs] = {}

    def __init__(self, provider, config):
        super().__init__(provider, config)
        self.apikey: str = getattr(self.config, "credentials", {}).get("apikey", "")
        self.headers = format_dict_items(self.config.headers, apikey=self.apikey)
        self.signed_url_key = self.config.signed_url_key

    def validate_config_credentials(self) -> None:
        """Validate configured credentials"""
        # credentials are optional
        pass

    def authenticate(self, **kwargs: Any) -> Any:
        """
        Authenticates a URL by making a GET request and storing the signed URL and its expiration date.

        :param url: The URL to authenticate.
        :raises AuthenticationError: If the signed URL could not be retrieved.
        """
        # authenticate only if required
        if self.is_authenticated():
            return

        self.validate_config_credentials()

        try:
            response = http.get(self.url, headers=self.headers)
            signed_url: str = response.json().get(self.signed_url_key)
        except Exception as e:
            raise AuthenticationError(f"Could no get signed url: {str(e)}")

        match = re.search(r"se=([^&]+)", signed_url)
        if match:
            expiration_date_str = unquote(match.group(1))
            expiration_date = datetime.fromisoformat(expiration_date_str.rstrip("Z"))
        else:
            logger.debug("Expiration date not found in SAS token.")
            expiration_date = datetime.utcnow()

        self.signed_urls[self.url] = SignedURLs(signed_url, expiration_date)

    def is_authenticated(self) -> bool:
        """
        Checks if a URL is authenticated.

        A URL is considered authenticated if it's in the list of signed URLs and its expiration date has not passed.

        :param url: The URL to check.
        :return: True if the URL is authenticated, False otherwise.
        """
        signed_url_info = self.signed_urls.get(self.url)

        if signed_url_info is None:
            # The URL is not in the list of signed URLs.
            return False

        # Check if the current date and time is before the expiration date.
        if datetime.utcnow() < signed_url_info.expiration_date:
            # The signed URL has not expired yet.
            return True
        else:
            # The signed URL has expired.
            return False

    def prepare_authenticated_http_request(
        self, params: HttpRequestParams
    ) -> HttpRequestParams:
        """
        Prepare an authenticated HTTP request.

        :param HttpRequestParams params: The parameters for the HTTP request.

        :return: The parameters for the authenticated HTTP request.
        :rtype: HttpRequestParams

        :note: This function modifies the `params` instance directly and also returns it. The returned value is the same
            instance that was passed in, not a new one.
        """
        self.url = params.url
        self.authenticate()
        params.url = self.signed_urls[params.url].signed_url

        return params
