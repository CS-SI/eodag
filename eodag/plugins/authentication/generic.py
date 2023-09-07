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

from typing import Any, Dict, List, Optional, Union

from requests.auth import HTTPBasicAuth, HTTPDigestAuth

from eodag.plugins.authentication.base import Authentication
from eodag.utils.http import HttpRequests, HttpResponse


class GenericAuth(Authentication):
    """GenericAuth authentication plugin"""

    def authenticate(self):
        """Authenticate"""
        self.validate_config_credentials()
        method = getattr(self.config, "method", None)
        if not method:
            method = "basic"
        if method == "basic":
            return HTTPBasicAuth(
                self.config.credentials["username"],
                self.config.credentials["password"],
            )
        if method == "digest":
            return HTTPDigestAuth(
                self.config.credentials["username"],
                self.config.credentials["password"],
            )

    def http_requests(self) -> HttpRequests:
        """
        Returns an instance of GenericAuthHttpRequests for sending HTTP requests
        with basic-based authentication or digest-based authentication.

        :return: An instance of GenericAuthHttpRequests.
        """
        return GenericAuthHttpRequests(self)


class GenericAuthHttpRequests(HttpRequests):
    """
    A class for sending HTTP requests with token-based authentication.
    """

    def __init__(self, auth: GenericAuth):
        """
        Initialize the GenericAuthHttpRequests instance with an authentication object.

        :param auth: The authentication object to use for token-based authentication.
        """
        super().__init__()
        self.auth = auth

    def _request(
        self,
        method: str,
        url: str,
        data: Optional[Union[Dict[str, Any], bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 3,
        delay: int = 1,
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """
        Sends an HTTP request to the specified URL with token-based authentication.

        If the request fails due to a requests.exceptions.RequestException, it will wait for the specified delay
        and then try again. If all attempts fail, it will re-raise the last exception.

        Args:
            method (str): The HTTP method to use for the request (e.g., "GET" or "POST").
            url (str): The URL to send the request to.
            data (dict, optional): Dictionary, list of tuples or bytes to send in the body of the request.
            json (dict, optional): JSON data to send in the body of the request.
            headers (dict, optional): Dictionary of HTTP headers to send with the request.
            retries (int): The number of times to attempt the request before giving up.
            delay (int): The number of seconds to wait between attempts.
            unquoted_params (List[str], optional): A list of URL parameters that should not be quoted.
            **kwargs: Optional arguments that `requests.request` takes.

        Returns:
            HttpResponse: The response from the server.
        """
        return super()._request(
            method=method,
            url=url,
            data=data,
            json=json,
            headers=headers,
            retries=retries,
            delay=delay,
            unquoted_params=unquoted_params,
            auth=self.auth.authenticate(),
            **kwargs,
        )
