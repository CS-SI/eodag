# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
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

import logging
import os
from typing import Any, Optional

import requests

from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT, path_to_uri, uri_to_path
from eodag.utils.exceptions import RequestError, TimeOutError

logger = logging.getLogger("eodag.utils.requests")


def fetch_json(
    url: str,
    req_session: Optional[requests.Session] = None,
    auth: Optional[requests.auth.AuthBase] = None,
    timeout: float = HTTP_REQ_TIMEOUT,
) -> Any:
    """
    Fetches http/distant or local json file

    :param url: url from which the file can be fetched
    :param req_session: (optional) requests session
    :param auth: (optional) authenticated object if request needs authentication
    :param timeout: (optional) authenticated object
    :returns: json file content
    """
    if req_session is None:
        req_session = requests.sessions.Session()
    try:
        if not url.lower().startswith("http"):
            url = path_to_uri(os.path.abspath(url))
            req_session.mount("file://", LocalFileAdapter())

        headers = USER_AGENT
        logger.debug(f"fetching {url}")
        res = req_session.get(
            url,
            headers=headers,
            auth=auth,
            timeout=timeout,
        )
        res.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise TimeOutError(exc, timeout=timeout) from exc
    except requests.exceptions.RequestException as exc:
        raise RequestError.from_error(exc, f"Unable to fetch {url}") from exc
    else:
        return res.json()


class LocalFileAdapter(requests.adapters.BaseAdapter):
    """Protocol Adapter to allow Requests to GET file:// URLs inspired
    by https://stackoverflow.com/questions/10123929/fetch-a-file-from-a-local-url-with-python-requests/27786580
    `LocalFileAdapter` class available for the moment (on the 2024-04-22)
    """

    @staticmethod
    def _chkpath(method: str, path: str) -> tuple[int, str]:
        """Return an HTTP status for the given filesystem path.

        :param method: method of the request
        :param path: path of the given file
        :returns: HTTP status and its associated message
        """
        if method.lower() in ("put", "delete"):
            return 501, "Not Implemented"  # TODO
        elif method.lower() not in ("get", "head"):
            return 405, "Method Not Allowed"
        elif os.path.isdir(path):
            return 400, "Path Not A File"
        elif not os.path.isfile(path):
            return 404, "File Not Found"
        elif not os.access(path, os.R_OK):
            return 403, "Access Denied"
        else:
            return 200, "OK"

    def send(
        self, request: requests.PreparedRequest, *args: Any, **kwargs: Any
    ) -> requests.Response:
        """Wraps a file, described in request, in a Response object.

        :param request: The PreparedRequest being "sent".
        :param kwargs: (not used) additional arguments of the request
        :returns: a Response object containing the file
        """
        response = requests.Response()

        if request.method is None or request.url is None:
            raise RequestError("Method or url of the request is missing")

        path_url = uri_to_path(request.url)

        response.status_code, response.reason = self._chkpath(request.method, path_url)
        if response.status_code == 200 and request.method.lower() != "head":
            try:
                response.raw = open(path_url, "rb")
            except (OSError, IOError) as err:
                response.status_code = 500
                response.reason = str(err)
        response.url = request.url
        response.request = request

        return response

    def close(self):
        """Closes without cleaning up adapter specific items."""
        pass
