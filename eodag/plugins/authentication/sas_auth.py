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
from typing import Any, Dict, List, Optional, Union
from urllib.parse import unquote

from eodag.plugins.authentication.base import Authentication
from eodag.utils import format_dict_items
from eodag.utils.exceptions import AuthenticationError
from eodag.utils.http import http

logger = logging.getLogger("eodag.plugins.auth.sas_auth")


class SASAuth(Authentication):
    """SASAuth authentication plugin"""

    def __init__(self):
        self.signed_urls: Dict[str, Dict[str, Union[str, datetime]]] = {}

    def validate_config_credentials(self) -> None:
        """Validate configured credentials"""
        # credentials are optional
        pass

    def authenticate(self, url: str) -> None:
        """
        Authenticates a URL by making a GET request and storing the signed URL and its expiration date.

        :param url: The URL to authenticate.
        :raises AuthenticationError: If the signed URL could not be retrieved.
        """
        self.validate_config_credentials()

        apikey = getattr(self.config, "credentials", {}).get("apikey", "")
        headers = format_dict_items(self.config.headers, apikey=apikey)

        try:
            response = http.get(url, headers=headers)
            signed_url = response.json().get(self.config.signed_url_key)
        except Exception as e:
            raise AuthenticationError(f"Could no get signed url: {str(e)}")

        match = re.search(r"se=([^&]+)", signed_url)
        if match:
            expiration_date_str = unquote(match.group(1))
            expiration_date = datetime.fromisoformat(expiration_date_str.rstrip("Z"))
        else:
            logger.debug("Expiration date not found in SAS token.")
            expiration_date = datetime.utcnow()

        signed_url_info = {"signed_url": signed_url, "expiration_date": expiration_date}

        self.signed_urls[url] = signed_url_info

    def is_authenticated(self, url: str) -> bool:
        """
        Checks if a URL is authenticated.

        A URL is considered authenticated if it's in the list of signed URLs and its expiration date has not passed.

        :param url: The URL to check.
        :return: True if the URL is authenticated, False otherwise.
        """
        signed_url_info = self.signed_urls.get(url)

        if signed_url_info is None:
            # The URL is not in the list of signed URLs.
            return False

        # Check if the current date and time is before the expiration date.
        if datetime.utcnow() < signed_url_info["expiration_date"]:
            # The signed URL has not expired yet.
            return True
        else:
            # The signed URL has expired.
            return False

    def prepare_authenticated_request(
        self,
        method: str,
        url: str,
        data: Optional[Union[Dict[str, Any], bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 3,
        delay: int = 1,
        timeout: int = 10,
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        if not self.is_authenticated(url):
            self.authenticate()

        url = self.signed_urls[url]

        return {
            "method": method,
            "url": url,
            "data": data,
            "json": json,
            "headers": headers,
            "retries": retries,
            "delay": delay,
            "timeout": timeout,
            "unquoted_params": unquoted_params,
            **kwargs,
        }
