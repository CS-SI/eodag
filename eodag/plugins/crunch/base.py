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
# limitations under the License
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from eodag.plugins.base import PluginTopic

if TYPE_CHECKING:
    from eodag.api.product import EOProduct


class Crunch(PluginTopic):
    """Base cruncher"""

    def __init__(self, config: Optional[Dict[str, Any]]) -> None:
        self.config = config if config is not None else {}

    def proceed(
        self, products: List[EOProduct], **search_params: Any
    ) -> List[EOProduct]:
        """Implementation of how the results must be crunched"""
        raise NotImplementedError
