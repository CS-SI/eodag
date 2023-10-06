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
from typing import Any, Dict, List, Optional, Union
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from eodag.plugins.authentication import Authentication

logger = logging.getLogger("eodag.authentication.qsauth")


class HttpQueryStringAuth(Authentication):
    """An Authentication plugin using HTTP query string parameters.

    This plugin sends credentials as query-string parameters.
    Using :class:`~eodag.plugins.download.http.HTTPDownload` a download link
    `http://example.com?foo=bar` will become
    `http://example.com?foo=bar&apikey=XXX&otherkey=YYY` if associated to the following
    configuration::

        provider:
            credentials:
                apikey: XXX
                otherkey: YYY

    The plugin is configured as follows in the providers config file::

        provider:
            ...
            auth:
                plugin: HttpQueryStringAuth
                auth_uri: 'http://example.com?foo=bar'
                ...
            ...

    If `auth_uri` is specified (optional), it will be used to check credentials through
    :meth:`~eodag.plugins.authentication.query_string.HttpQueryStringAuth.authenticate`
    """

    def authenticate(self):
        """Authenticate"""
        self.validate_config_credentials()

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
        Prepares an authenticated HTTP request.

        This function adds authentication details to the request parameters. It first authenticates the session by calling `self.authenticate()`. Then it adds the credentials stored in `self.config.credentials` to the query parameters of the URL.

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
            dict: A dictionary with all the request parameters including the modified URL.

        Raises:
            Exception: If an error occurs while authenticating.
        """
        self.authenticate()

        parts = urlparse(url)
        query_dict = parse_qs(parts.query)
        query_dict.update(self.config.credentials)

        # Convert the updated query parameters back into a string
        query_string = urlencode(query_dict, doseq=True)

        # Construct the new URL
        new_parts = parts._replace(query=query_string)
        url = urlunparse(new_parts)

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
