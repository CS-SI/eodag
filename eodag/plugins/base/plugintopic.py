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

from .eodagpluginmount import EODAGPluginMount

if TYPE_CHECKING:
    from eodag.config import PluginConfig


class PluginTopic(metaclass=EODAGPluginMount):
    """Base of all plugin topics in eodag"""

    def __init__(self, provider: str, config: PluginConfig) -> None:
        self.config = config
        self.provider = provider

    def __repr__(self) -> str:
        config = getattr(self, "config", None)
        priority = ""
        if config is not None and hasattr(config, "priority"):
            priority = str(config.priority)  # is an int
        return "{}(provider={}, priority={}, topic={})".format(
            self.__class__.__name__,
            getattr(self, "provider", ""),
            priority,
            self.__class__.mro()[-3].__name__,
        )


__all__ = ["PluginTopic"]
