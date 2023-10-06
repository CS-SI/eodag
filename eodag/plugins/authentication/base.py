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

from typing import Any, Dict, ForwardRef, List, Optional, Union

from eodag.plugins.base import PluginTopic
from eodag.utils.exceptions import MisconfiguredError
from eodag.utils.http import HttpRequests, HttpResponse


class Authentication(PluginTopic):
    """Plugins authentication Base plugin"""

    def authenticate(self):
        """Authenticate"""
        raise NotImplementedError

    def validate_config_credentials(self):
        """Validate configured credentials"""
        # No credentials dict in the config
        try:
            credentials = self.config.credentials
        except AttributeError:
            raise MisconfiguredError(
                f"Missing credentials configuration for provider {self.provider}"
            )
        # Empty credentials dict
        if not credentials:
            raise MisconfiguredError(
                f"Missing credentials for provider {self.provider}"
            )
        # Credentials keys but values are None.
        missing_credentials = [
            cred_name
            for cred_name, cred_value in credentials.items()
            if cred_value is None
        ]
        if missing_credentials:
            raise MisconfiguredError(
                "The following credentials are missing for provider {}: {}".format(
                    self.provider, ", ".join(missing_credentials)
                )
            )

    def http_requests(self) -> "AuthenticatedHttpRequests":
        """
        Returns an instance of the AuthenticatedHttpRequests class.

        This function provides an instance of the AuthenticatedHttpRequests class
        that can be used to make authenticated HTTP requests. Subclasses should not override this method.
        Instead, they should modify the `prepare_authenticated_request` method to customize the authentication process.

        Returns:
            AuthenticatedHttpRequests: An instance of the AuthenticatedHttpRequests class.
        """
        return AuthenticatedHttpRequests(self)

    def prepare_authenticated_request(self):
        """
        Prepares an authenticated HTTP request.

        This function should be implemented by subclasses to add authentication details to the request parameters.
        The implementation will depend on the specific authentication method used.

        Raises:
            NotImplementedError: This is an abstract method that should be implemented by subclasses.
        """
        raise NotImplementedError


class AuthenticatedHttpRequests(HttpRequests):
    """
    This class is a child of the HttpRequests class and is used for making HTTP requests with authentication.
    It prepares the HTTP request by adding authentication details to the request parameters before sending it.
    The authentication details are added using an authentication plugin.

    Attributes:
        auth (Authentication): An instance of the Authentication class used for authentication. This can be any authentication plugin that provides a `prepare_authenticated_request` method.
        default_headers (dict, optional): A dictionary of default headers to be included in all requests.
        Defaults to None.
    """

    def __init__(
        self, auth: Authentication, default_headers: Optional[Dict[str, str]] = None
    ) -> None:
        """
        The constructor for the AuthenticatedHttpRequests class.

        Parameters:
            auth (Authentication): An instance of the Authentication class used for authentication. This can be any authentication plugin that provides a `prepare_authenticated_request` method.
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
        Sends an HTTP request with authentication. Before sending the request, it prepares the request
        by adding authentication details to the request parameters using an authentication plugin.

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
        super()._send_request(
            **self.auth.prepare_authenticated_request(
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
        )
