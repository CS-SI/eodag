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
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import requests
from requests import RequestException
from requests.adapters import HTTPAdapter
from urllib3 import Retry

from eodag.plugins.authentication.base import Authentication
from eodag.utils import USER_AGENT
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError, RequestError
from eodag.utils.http import HttpRequests, HttpResponse
from eodag.utils.stac_reader import HTTP_REQ_TIMEOUT

logger = logging.getLogger("eodag.authentication.token")


class TokenAuth(Authentication):
    """TokenAuth authentication plugin"""

    def __init__(self, provider, config):
        super(TokenAuth, self).__init__(provider, config)
        self.token: str = ""
        self.headers: Dict = {}
        self.validity_period: timedelta = None
        self.expiration_time: datetime = None

    @staticmethod
    def str_to_timedelta(duration_str: str) -> timedelta:
        """
        Parses a string representing a duration and returns a timedelta object.

        Args:
            duration_str (str): A string representing a duration. The string should be in the format 'Nd', 'Nh',
            or 'Nm', where N is an integer value and d, h, and m represent days, hours, and minutes, respectively.

        Returns:
            timedelta: A timedelta object representing the duration specified by the input string.

        Raises:
            ValueError: If the input string is not in a valid format.
        """
        unit = duration_str[-1]
        value = int(duration_str[:-1])

        if unit == "h":
            delta = timedelta(hours=value)
        elif unit == "m":
            delta = timedelta(minutes=value)
        elif unit == "d":
            delta = timedelta(days=value)
        else:
            raise ValueError(f"Invalid unit: {unit}")

        return delta

    def validate_config_credentials(self):
        """Validate configured credentials"""
        try:
            super(TokenAuth, self).validate_config_credentials()
            # format auth_uri using credentials if needed
            self.config.auth_uri = self.config.auth_uri.format(
                **self.config.credentials
            )
            # format headers if needed
            self.config.headers = {
                header: value.format(**self.config.credentials)
                for header, value in getattr(self.config, "headers", {}).items()
            }

            if getattr(self.config, "validity_period", None):
                self.validity_period = TokenAuth.str_to_timedelta(
                    self.config.validity_period
                )

        except (KeyError, ValueError) as e:
            raise MisconfiguredError(
                f"Invalid configuration for provider {self.provider}: {e}"
            )

        if "$token" not in self.config.headers.get("Authorization", ""):
            raise MisconfiguredError(
                "Cannot generate headers. ",
                "Authorization header is missing from auth configuration.",
            )

    def authenticate(self):
        """Authenticate"""
        self.validate_config_credentials()

        # append headers to req if some are specified in config
        req_kwargs = (
            {"headers": dict(self.config.headers, **USER_AGENT)}
            if hasattr(self.config, "headers")
            else {"headers": USER_AGENT}
        )
        s = requests.Session()
        retries = Retry(
            total=3, backoff_factor=2, status_forcelist=[401, 429, 500, 502, 503, 504]
        )
        s.mount(self.config.auth_uri, HTTPAdapter(max_retries=retries))
        try:
            # First get the token
            if getattr(self.config, "request_method", "POST") == "POST":
                response = s.post(
                    self.config.auth_uri,
                    data=self.config.credentials,
                    timeout=HTTP_REQ_TIMEOUT,
                    **req_kwargs,
                )
            else:
                cred = self.config.credentials
                response = s.get(
                    self.config.auth_uri,
                    auth=(cred["username"], cred["password"]),
                    timeout=HTTP_REQ_TIMEOUT,
                    **req_kwargs,
                )
            response.raise_for_status()
        except RequestException as e:
            response_text = getattr(e.response, "text", "").strip()
            raise AuthenticationError(
                f"Could no get authentication token: {str(e)}, {response_text}"
            )

        if getattr(self.config, "token_type", "text") == "json":
            self.token = response.json()[self.config.token_key]
        else:
            self.token = response.text

        self.headers = self.config.headers.copy()
        self.headers["Authorization"] = self.headers["Authorization"].replace(
            "$token", self.token
        )

        if self.validity_period:
            self.expiration_time = datetime.now() + self.validity_period

    def is_authenticated(self) -> bool:
        """
        Checks if the user is authenticated and if the token is still valid.

        :return: True if the user has a valid token that has not expired, False otherwise.
        """
        if not self.token:
            return False
        if self.expiration_time and datetime.now() > self.expiration_time:
            return False
        return True

    def http_requests(self) -> HttpRequests:
        """
        Returns an instance of the TokenAuthHttpRequests class.

        This function defines a nested class named TokenAuthHttpRequests that is a subclass of HttpRequests.
        The nested class provides implementations for the `get` and `post` methods that make authenticated HTTP requests
        using a token-based authentication method.

        Args:
            self: The object on which the method is called.

        Returns:
            TokenAuthHttpRequests: An instance of the TokenAuthHttpRequests class.
        """
        return TokenAuthHttpRequests(self)


class TokenAuthHttpRequests(HttpRequests):
    """
    A subclass of HttpRequests that makes authenticated HTTP requests using a token-based authentication method.
    """

    def __init__(self, auth: TokenAuth):
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
        for i in range(retries):
            try:
                if not self.auth.is_authenticated():
                    self.auth.authenticate()

                self.default_headers["Authorization"] = f"Bearer {self.auth.token}"

                return super()._request(
                    method=method,
                    url=url,
                    data=data,
                    json=json,
                    headers=headers,
                    retries=1,
                    delay=0,
                    unquoted_params=unquoted_params,
                    **kwargs,
                )
            except RequestError as e:
                if 400 <= e.response.status_code < 600:
                    raise e
                elif i < retries - 1:  # i is zero indexed
                    time.sleep(delay)  # wait before trying again
                    continue
                else:
                    raise e
