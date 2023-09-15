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
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from eodag.plugins.authentication.base import Authentication
from eodag.utils.exceptions import MisconfiguredError
from eodag.utils.http import HttpRequests, HttpResponse, http

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
        This static method converts a duration string into a timedelta object.

        Parameters:
            duration_str (str): A string representing the duration. The string should be in the format
            of "<value><unit>",
                                where <value> is an integer and <unit> is one of the following:
                                - 'h' for hours
                                - 'm' for minutes
                                - 'd' for days

        Returns:
            timedelta: A timedelta object representing the duration.

        Raises:
            ValueError: If the unit is not 'h', 'm', or 'd'.
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

        try:
            response = http.request(
                method=getattr(self.config, "request_method", "POST"),
                url=self.config.auth_uri,
                data=self.config.credentials,
                headers=getattr(self.config, "headers", None),
            )
        except Exception as e:
            response_text = getattr(e.response, "text", "").strip()
            logger.error(
                f"Could no get authentication token: {str(e)}, {response_text}"
            )
            raise e

        if getattr(self.config, "token_type", "text") == "json":
            self.token = response.json()[self.config.token_key]
        else:
            self.token = response.text

        self.headers = deepcopy(self.config.headers)
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
        Returns an instance of TokenAuthHttpRequests initialized with this TokenAuth instance.

        :return: An instance of TokenAuthHttpRequests initialized with this TokenAuth instance.
        """
        return TokenAuthHttpRequests(auth=self)


class TokenAuthHttpRequests(HttpRequests):
    """
    This class is a child of the HttpRequests class and is used for making HTTP requests with token authentication.

    Attributes:
        auth (TokenAuth): An instance of the TokenAuth class used for token authentication.
        default_headers (dict, optional): A dictionary of default headers to be included in all requests.
        Defaults to None.
    """

    def __init__(
        self, auth: TokenAuth, default_headers: Optional[Dict[str, str]] = None
    ) -> None:
        """
        The constructor for the TokenAuthHttpRequests class.

        Parameters:
            auth (TokenAuth): An instance of the TokenAuth class used for token authentication.
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
        Sends an HTTP request with token authentication.

        Parameters:
            method (str): The HTTP method for the request.
            url (str): The URL for the request.
            data (dict or bytes, optional): The data to send in the body of the request. Defaults to None.
            json (dict, optional): The JSON data to send in the body of the request. Defaults to None.
            headers (dict, optional): A dictionary of headers to send with the request. Defaults to None.
            retries (int, optional): The number of times to retry the request in case of failure. Defaults to 3.
            delay (int, optional): The delay between retries in seconds. Defaults to 1.
            timeout (int, optional): The timeout for the request in seconds. Defaults to 10.
            unquoted_params (list of str, optional): A list of parameters that should not be URL encoded.
            Defaults to None.
            **kwargs: Variable length keyword arguments.

        Returns:
            HttpResponse: The HTTP response received from the server.

        Raises:
            Exception: If an error occurs while sending the request.
        """
        if not self.auth.is_authenticated():
            self.auth.authenticate()

        headers = {**headers, **self.auth.headers} if headers else self.auth.headers

        super()._send_request(
            self,
            method=method,
            url=url,
            data=data,
            json=json,
            headers=headers,
            retries=retries,
            delay=delay,
            timeout=timeout,
            unquoted_params=unquoted_params,
            **kwargs,
        )
