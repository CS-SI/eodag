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

from eodag.plugins.authentication import Authentication
from eodag.utils.http import HttpRequests, HttpResponse


class HTTPHeaderAuth(Authentication):
    """HTTPHeaderAuth Authentication plugin.

    This plugin enables implementation of custom HTTP authentication scheme (other than Basic, Digest, Token
    negotiation et al.) using HTTP headers.

    The plugin is configured as follows in the providers config file::

        provider:
            ...
            auth:
                plugin: HTTPHeaderAuth
                headers:
                    Authorization: "Something {userinput}"
                    X-Special-Header: "Fixed value"
                    X-Another-Special-Header: "{oh-my-another-user-input}"
                ...
            ...

    As you can see in the sample above, the maintainer of `provider` define the headers that will be used in the
    authentication process as-is, by giving their names (e.g. `Authorization`) and their value (e.g
    `"Something {userinput}"`) as regular Python string templates that enable passing in the user input necessary to
    compute its identity. The user input awaited in the header value string must be present in the user config file.
    In the sample above, the plugin await for user credentials to be specified as::

        provider:
            credentials:
                userinput: XXX
                oh-my-another-user-input: YYY

    Expect an undefined behaviour if you use empty braces in header value strings.
    """

    def authenticate(self):
        """Authenticate"""
        self.validate_config_credentials()
        self.headers = {
            header: value.format(**self.config.credentials)
            for header, value in self.config.headers.items()
        }

    def http_requests(self) -> HttpRequests:
        """
        Returns an instance of HeaderAuthHttpRequests initialized with the current instance.

        This method is used to create a new HTTP request object that uses header-based authentication.
        The returned object provides implementations for the requests methods that make authenticated HTTP requests.

        :return: An instance of HeaderAuthHttpRequests initialized with the current instance.
        """
        return HeaderAuthHttpRequests(header_auth=self)


class HeaderAuthHttpRequests(HttpRequests):
    """
    This class is a child of the HttpRequests class and is used for making HTTP requests with header authentication.

    Attributes:
        header_auth (HTTPHeaderAuth): An instance of the HTTPHeaderAuth class used for header authentication.
        default_headers (dict, optional): A dictionary of default headers to be included in all requests.
        Defaults to None.
    """

    def __init__(
        self,
        header_auth: HTTPHeaderAuth,
        default_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        The constructor for the HeaderAuthHttpRequests class.

        Parameters:
            header_auth (HTTPHeaderAuth): An instance of the HTTPHeaderAuth class used for header authentication.
            default_headers (dict, optional): A dictionary of default headers to be included in all requests.
            Defaults to None.
        """
        super().__init__(default_headers)
        self.header_auth = header_auth

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
        Sends an HTTP request with header authentication.

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
        self.header_auth.authenticate()

        headers = headers or {}
        headers = {**self.header_auth.headers, **headers}

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
