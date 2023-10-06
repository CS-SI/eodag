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

from eodag.plugins.authentication.base import Authentication


class OAuth(Authentication):
    """OAuth authentication plugin"""

    def __init__(self, provider, config):
        super(OAuth, self).__init__(provider, config)
        self.access_key = None
        self.secret_key = None

    def authenticate(self):
        """Authenticate"""
        self.validate_config_credentials()
        self.access_key = self.config.credentials["aws_access_key_id"]
        self.secret_key = self.config.credentials["aws_secret_access_key"]
        return self.access_key, self.secret_key

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
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Prepares an authenticated HTTP request with header authentication.

        This function adds authentication details to the request headers. It first authenticates the session by calling `self.header_auth.authenticate()`. Then it updates the headers with the authentication headers from `self.header_auth`.

        Parameters:
            method (str): The HTTP method for the request.
            url (str): The URL for the request.
            data (dict or bytes, optional): The data to send in the body of the request. Defaults to None.
            json (dict, optional): The JSON data to send in the body of the request. Defaults to None.
            headers (dict, optional): A dictionary of headers to send with the request. Defaults to None.
            retries (int, optional): The number of times to retry the request in case of failure. Defaults to 3.
            delay (int, optional): The delay between retries in seconds. Defaults to 1.
            timeout (int, optional): The timeout for the request in seconds. Defaults to 10.
            unquoted_params (list of str, optional): A list of parameters that should not be URL encoded. Defaults to None.
            **kwargs: Variable length keyword arguments.

        Returns:
            dict: A dictionary with all the request parameters including the possibly modified headers.

        Raises:
            Exception: If an error occurs while authenticating.
        """
        self.authenticate()

        raise NotImplementedError("This function has not been implemented yet")

        # return {
        #     "method": method,
        #     "url": url,
        #     "data": data,
        #     "json": json,
        #     "headers": headers,
        #     "retries": retries,
        #     "delay": delay,
        #     "timeout": timeout,
        #     "unquoted_params": unquoted_params,
        #     **kwargs
        # }
