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
from typing import Any

from eodag.plugins.authentication import Authentication
from eodag.utils.http import HttpRequestParams, add_qs_params, http

logger = logging.getLogger("eodag.authentication.token")


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

    def validate_config_credentials(self):
        """Validate configured credentials"""
        super().validate_config_credentials()
        self.credentials = self.config.credentials
        self.auth_uri = getattr(self.config, "auth_uri", "")

    def authenticate(self, **kwargs: Any) -> Any:
        """Authenticate"""
        self.validate_config_credentials()

        if self.auth_uri:
            http.get(add_qs_params(self.auth_uri, **self.credentials))

    def prepare_authenticated_http_request(
        self, params: HttpRequestParams
    ) -> HttpRequestParams:
        """
        Prepare an authenticated HTTP request.

        :param HttpRequestParams params: The parameters for the HTTP request.

        :return: The parameters for the authenticated HTTP request.
        :rtype: HttpRequestParams

        :note: This function modifies the `params` instance directly and also returns it. The returned value is the same
            instance that was passed in, not a new one.
        """
        self.authenticate()
        params.url = add_qs_params(params.url, **self.credentials)

        return params
