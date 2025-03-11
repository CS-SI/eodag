# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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
from typing import TYPE_CHECKING

from eodag.plugins.apis.base import Api
from eodag.plugins.download.http import HTTPDownload
from eodag.plugins.search.build_search_result import ECMWFSearch

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger("eodag.apis.ecmwf_group")


class EcmwfGroupApi(Api, ECMWFSearch, HTTPDownload):
    """ECMWF Group API plugin"""

    def do_search(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Should perform the actual search request."""
        return [{}]
