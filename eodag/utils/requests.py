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
from typing import Any, Optional

import httpx

from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT
from eodag.utils.exceptions import RequestError, TimeOutError

logger = logging.getLogger("eodag.utils.requests")


def fetch_json(
    url: str,
    req_session: Optional[httpx.Client] = None,
    auth: Optional[httpx.Auth] = None,
    timeout: float = HTTP_REQ_TIMEOUT,
) -> Any:
    """
    Fetches http/distant or local json file

    :param url: url from which the file can be fetched
    :param req_session: (optional) httpx client
    :param auth: (optional) authenticated object if request needs authentication
    :param timeout: (optional) timeout for the request
    :returns: json file content
    """
    close_session = False
    if req_session is None:
        req_session = httpx.Client()
        close_session = True

    try:
        if not url.lower().startswith("http"):
            # For local files, read directly
            file_path = url
            if url.startswith("file://"):
                from eodag.utils import uri_to_path

                file_path = uri_to_path(url)

            with open(file_path, "r", encoding="utf-8") as f:
                import json

                return json.load(f)
        else:
            headers = USER_AGENT
            logger.debug(f"fetching {url}")
            res = req_session.get(
                url,
                headers=headers,
                auth=auth,
                timeout=timeout,
            )
            res.raise_for_status()
            return res.json()
    except httpx.TimeoutException as exc:
        raise TimeOutError(exc, timeout=timeout) from exc
    except httpx.RequestError as exc:
        raise RequestError.from_error(exc, f"Unable to fetch {url}") from exc
    except (OSError, IOError, ValueError) as exc:
        raise RequestError.from_error(exc, f"Unable to fetch {url}") from exc
    finally:
        if close_session:
            req_session.close()
