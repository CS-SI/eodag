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

import datetime
import re
from typing import Any, Optional

import dateutil.parser
from dateutil import tz

from eodag.utils.exceptions import ValidationError

RFC3339_PATTERN = (
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:T(\d{2}):(\d{2}):(\d{2})(\.\d+)?"
    r"(Z|([+-])(\d{2}):(\d{2}))?)?$"
)


def get_datetime(arguments: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Get start and end dates from a dict containing `/` separated dates in `datetime` item

    :param arguments: dict containing a single date or `/` separated dates in `datetime` item
    :returns: Start date and end date from datetime string (duplicate value if only one date as input)
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


def rfc3339_str_to_datetime(s: str) -> datetime.datetime:
    """Convert a string conforming to RFC 3339 to a :class:`datetime.datetime`.

    :param s: The string to convert to :class:`datetime.datetime`

    :returns: The datetime represented by the ISO8601 (RFC 3339) formatted string

    raises: :class:`ValidationError`
    """
    # Uppercase the string
    s = s.upper()

    # Match against RFC3339 regex.
    result = re.match(RFC3339_PATTERN, s)
    if not result:
        raise ValidationError("Invalid RFC3339 datetime.")

    return dateutil.parser.isoparse(s).replace(tzinfo=datetime.timezone.utc)
