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

import requests
from requests.auth import AuthBase
from requests.exceptions import RequestException

from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT
from eodag.utils.exceptions import AuthenticationError, TimeOutError

from ..base import Authentication
from .querystringauth import QueryStringAuth


class HttpQueryStringAuth(Authentication):
    """An Authentication plugin using HTTP query string parameters.

    This plugin sends credentials as query-string parameters.

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): HttpQueryStringAuth
        * :attr:`~eodag.config.PluginConfig.auth_uri` (``str``): used to check the credentials
          given in the configuration

    Using :class:`~eodag.plugins.download.protocol.http.HTTPDownload` a download link
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

    def authenticate(self) -> AuthBase:
        """Authenticate"""
        self.validate_config_credentials()

        auth = QueryStringAuth(**self.config.credentials)

        auth_uri = getattr(self.config, "auth_uri", None)
        ssl_verify = getattr(self.config, "ssl_verify", True)

        if auth_uri:
            try:
                response = requests.get(
                    auth_uri,
                    timeout=HTTP_REQ_TIMEOUT,
                    headers=USER_AGENT,
                    auth=auth,
                    verify=ssl_verify,
                )
                response.raise_for_status()
            except requests.exceptions.Timeout as exc:
                raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
            except RequestException as e:
                raise AuthenticationError("Could no authenticate", str(e)) from e

        return auth


__all__ = ["HttpQueryStringAuth"]
