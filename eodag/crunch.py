# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, https://www.csgroup.eu/
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
"""Crunch filters import gateway"""

from .plugins.crunch.filter_date import FilterDate  # noqa
from .plugins.crunch.filter_latest_intersect import FilterLatestIntersect  # noqa
from .plugins.crunch.filter_latest_tpl_name import FilterLatestByName  # noqa
from .plugins.crunch.filter_overlap import FilterOverlap  # noqa
from .plugins.crunch.filter_property import FilterProperty  # noqa
