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

from urllib.parse import parse_qs, urlparse

import requests.auth
from requests.exceptions import RequestException

from eodag.plugins.authentication import Authentication
from eodag.utils.exceptions import AuthenticationError
from eodag.utils.stac_reader import HTTP_REQ_TIMEOUT


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

        auth = QueryStringAuth(**self.config.credentials)

        auth_uri = getattr(self.config, "auth_uri", None)
        if auth_uri:
            try:
                response = requests.get(
                    auth_uri,
                    timeout=HTTP_REQ_TIMEOUT,
                    auth=auth,
                )
                response.raise_for_status()
            except RequestException as e:
                raise AuthenticationError(f"Could no authenticate: {str(e)}")

        return auth


class QueryStringAuth(requests.auth.AuthBase):
    """ "QueryStringAuth custom authentication class to be used with requests module"""

    def __init__(self, **parse_args):
        self.parse_args = parse_args

    def __call__(self, request):
        """Perform the actual authentication"""
        parts = urlparse(request.url)
        query_dict = parse_qs(parts.query)
        query_dict.update(self.parse_args)
        url_without_args = parts._replace(query=None).geturl()

        request.prepare_url(url_without_args, query_dict)
        return request
