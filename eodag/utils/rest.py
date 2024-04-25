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
"""eodag.rest.utils methods that must be importable without eodag[server] installed"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import dateutil.parser
from dateutil import tz

from eodag.utils.exceptions import ValidationError


def get_datetime(arguments: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Get start and end dates from a dict containing `/` separated dates in `datetime` item

    :param arguments: dict containing a single date or `/` separated dates in `datetime` item
    :type arguments: dict
    :returns: Start date and end date from datetime string (duplicate value if only one date as input)
    :rtype: Tuple[Optional[str], Optional[str]]
    """
    datetime_str = arguments.pop("datetime", None)

    if datetime_str:
        datetime_split = datetime_str.split("/")
        if len(datetime_split) > 1:
            dtstart = datetime_split[0] if datetime_split[0] != ".." else None
            dtend = datetime_split[1] if datetime_split[1] != ".." else None
        elif len(datetime_split) == 1:
            # same time for start & end if only one is given
            dtstart, dtend = datetime_split[0:1] * 2
        else:
            return None, None

        return get_date(dtstart), get_date(dtend)

    else:
        # return already set (dtstart, dtend) or None
        dtstart = get_date(arguments.pop("dtstart", None))
        dtend = get_date(arguments.pop("dtend", None))
        return get_date(dtstart), get_date(dtend)


def get_date(date: Optional[str]) -> Optional[str]:
    """Check if the input date can be parsed as a date"""

    if not date:
        return None
    try:
        return (
            dateutil.parser.parse(date)
            .replace(tzinfo=tz.UTC)
            .isoformat()
            .replace("+00:00", "")
        )
    except ValueError as e:
        exc = ValidationError("invalid input date: %s" % e)
        raise exc
