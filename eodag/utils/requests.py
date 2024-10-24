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

import requests
import requests.auth

from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT
from eodag.utils.exceptions import RequestError, TimeOutError

logger = logging.getLogger("eodag.utils.requests")


def fetch_json(
    url: str,
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
    logger.debug(f"fetching GET {url}")
    try:
        res = requests.get(
            url,
            headers=USER_AGENT,
            auth=auth,
            timeout=timeout,
        )
        res.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
    except requests.exceptions.RequestException as exc:
        raise RequestError.from_error(exc, f"Unable to fetch {url}") from exc
    else:
        return res.json()
