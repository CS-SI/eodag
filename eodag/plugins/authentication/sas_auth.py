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
from eodag.utils.http import HttpRequests, HttpResponse, http

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

    def http_requests(self) -> HttpRequests:
        """
        Returns an instance of SASAuthHttpRequests that makes authenticated HTTP requests using a
        SAS-based authentication method.

        The returned object is initialized with the current instance of SASAuth, which means it will
        use the same authentication information (signed URLs and their expiration dates) that have
        been stored in the current SASAuth instance.

        :return: An instance of SASAuthHttpRequests initialized with the current SASAuth instance.
        """
        return SASAuthHttpRequests(auth=self)


class SASAuthHttpRequests(HttpRequests):
    """
    This class is a child of the HttpRequests class and is used for making HTTP requests with SAS authentication.

    Attributes:
        auth (SASAuth): An instance of the SASAuth class used for SAS authentication.
        default_headers (dict, optional): A dictionary of default headers to be included in all requests.
        Defaults to None.
    """

    def __init__(
        self, auth: SASAuth, default_headers: Optional[Dict[str, str]] = None
    ) -> None:
        """
        The constructor for the SASAuthHttpRequests class.

        Parameters:
            auth (SASAuth): An instance of the SASAuth class used for SAS authentication.
            default_headers (dict, optional): A dictionary of default headers to be included in all requests.
            Defaults to None.
        """
        super().__init__(default_headers)
        self.auth = auth

    def _send_request(
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
    ) -> HttpResponse:
        """
        This method sends an HTTP request with SAS authentication.

        Parameters:
            method (str): The HTTP method to use for the request.
            url (str): The URL to send the request to.
            data (dict or bytes, optional): The data to include in the request body. Defaults to None.
            json (dict, optional): The JSON data to include in the request body. Defaults to None.
            headers (dict, optional): A dictionary of headers to include in the request. Defaults to None.
            retries (int, optional): The number of times to retry the request if it fails. Defaults to 3.
            delay (int, optional): The delay between retries in seconds. Defaults to 1.
            timeout (int, optional): The timeout for the request in seconds. Defaults to 10.
            unquoted_params (list of str, optional): A list of parameter names that should not be URL encoded.
            Defaults to None.
            **kwargs: Any additional keyword arguments are passed through to the request.

        Returns:
            HttpResponse: The server's response to the request.
        """

        if not self.auth.is_authenticated(url):
            self.auth.authenticate()

        return super()._send_request(
            method=method,
            url=self.auth.signed_urls[url],
            data=data,
            json=json,
            headers=headers,
            retries=retries,
            delay=delay,
            timeout=timeout,
            unquoted_params=unquoted_params,
            **kwargs,
        )
