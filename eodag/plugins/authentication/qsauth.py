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
from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
from httpx import Auth, RequestError

from eodag.plugins.authentication import Authentication
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT
from eodag.utils.exceptions import AuthenticationError, TimeOutError

if TYPE_CHECKING:
    from typing import Any, Iterator

    from httpx import Request


class HttpQueryStringAuth(Authentication):
    """An Authentication plugin using HTTP query string parameters.

    This plugin sends credentials as query-string parameters.

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): HttpQueryStringAuth
        * :attr:`~eodag.config.PluginConfig.auth_uri` (``str``): used to check the credentials
          given in the configuration

    Using :class:`~eodag.plugins.download.http.HTTPDownload` a download link
    ``http://example.com?foo=bar`` will become
    ``http://example.com?foo=bar&apikey=XXX&otherkey=YYY`` if associated to the following
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

    If ``auth_uri`` is specified (optional), it will be used to check credentials through
    :meth:`~eodag.plugins.authentication.query_string.HttpQueryStringAuth.authenticate`
    """

    def authenticate(self) -> Auth:
        """Authenticate"""
        self.validate_config_credentials()

        auth = QueryStringAuth(**self.config.credentials)

        auth_uri = getattr(self.config, "auth_uri", None)
        ssl_verify = getattr(self.config, "ssl_verify", True)

        if auth_uri:
            try:
                with httpx.Client(verify=ssl_verify) as client:
                    response = client.get(
                        auth_uri,
                        timeout=HTTP_REQ_TIMEOUT,
                        headers=USER_AGENT,
                        auth=auth,
                    )
                    response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
            except RequestError as e:
                raise AuthenticationError("Could no authenticate", str(e)) from e

        return auth


class QueryStringAuth(Auth):
    """ "QueryStringAuth custom authentication class to be used with requests module"""

    def __init__(self, **parse_args: Any) -> None:
        self.parse_args = parse_args

    def auth_flow(self, request: Request) -> Iterator[Request]:
        """Perform the actual authentication"""
        request.url = request.url.copy_merge_params(self.parse_args)
        yield request
