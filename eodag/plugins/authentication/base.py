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
from typing import Any, Dict, List, Optional

from eodag.plugins.base import PluginTopic
from eodag.utils.exceptions import MisconfiguredError
from eodag.utils.http import HttpRequestParams, HttpRequests, HttpResponse


class Authentication(PluginTopic):
    """Plugins authentication Base plugin"""

    def __init__(self, provider, config):
        """
        Initialize the Authentication class.

        :param provider: The provider for the service.
        :param config: The configuration for the service.
        """
        super().__init__(provider, config)
        self.http = HttpRequests()

    def authenticate(self, **kwargs: Any) -> Any:
        """
        Authenticate with the service.

        :param kwargs: Additional keyword arguments.

        :raises NotImplementedError: This is an abstract method that should be implemented by subclasses.
        """
        raise NotImplementedError

    def validate_config_credentials(self):
        """
        Validate configured credentials.

        :raises MisconfiguredError: If the credentials configuration is missing or incomplete.
        """
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
        Instead, they should modify the `prepare_authenticated_http_request` method to customize the authentication
        process.

        :return: An instance of the AuthenticatedHttpRequests class.
        :rtype: AuthenticatedHttpRequests
        """
        return AuthenticatedHttpRequests(self)

    def prepare_authenticated_http_request(
        self, params: HttpRequestParams
    ) -> HttpRequestParams:
        """
        Prepare an authenticated HTTP request.

        :param HttpRequestParams params: The parameters for the HTTP request.

        :return: The parameters for the authenticated HTTP request.
        :rtype: HttpRequestParams

        :raises NotImplementedError: This is an abstract method that should be implemented by subclasses.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement the prepare_authenticated_http_request method."
        )


class AuthenticatedHttpRequests(HttpRequests):
    """
    This class is a child of the HttpRequests class and is used for making HTTP requests with authentication.
    It prepares the HTTP request by adding authentication details to the request parameters before sending it.
    The authentication details are added using an authentication plugin.

    :param Authentication auth: An instance of the Authentication class used for authentication. This can be any
        authentication plugin that provides a `prepare_authenticated_http_request` method.
    :param dict default_headers: A dictionary of default headers to be included in all requests. Defaults to None.
    """

    def __init__(
        self, auth: Authentication, default_headers: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Initialize the AuthenticatedHttpRequests class.

        :param Authentication auth: An instance of the Authentication class used for authentication.
        :param dict default_headers: A dictionary of default headers to be included in all requests. Defaults to None.
        """
        super().__init__(default_headers)
        self.auth = auth

    def _send_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        unquoted_params: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """
        Sends an HTTP request with authentication. Before sending the request, it prepares the request
        by adding authentication details to the request parameters using an authentication plugin.

        :param str method: The HTTP method for the request.
        :param str url: The URL for the request.
        :param dict headers: A dictionary of headers to send with the request. Defaults to None.
        :param int timeout: The timeout for the request in seconds. If not provided, self.timeout will be used.
            Defaults to None.
        :param List[str] unquoted_params: A list of parameters that should not be URL encoded. Defaults to None.
        :param kwargs: Optional arguments that `requests.request` takes.

        :return: The HTTP response received from the server.
        :rtype: HttpResponse

        :raises Exception: If an error occurs while sending the request.
        """
        return super()._send_request(
            **self.auth.prepare_authenticated_http_request(
                params=HttpRequestParams(
                    method=method,
                    url=url,
                    headers=headers or {},
                    timeout=timeout,
                    unquoted_params=unquoted_params,
                    extra_params=kwargs,
                )
            ).to_dict()
        )
