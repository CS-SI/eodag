# -*- coding: utf-8 -*-
# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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
"""eodag.rest.dates methods that must be importable without eodag[server] installeds"""

import datetime
import re
from datetime import datetime as dt
from typing import Any, Iterator, Optional

import dateutil.parser
from dateutil import tz
from dateutil.parser import isoparse
from dateutil.tz import UTC

from eodag.utils.exceptions import ValidationError

RFC3339_PATTERN = (
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:T(\d{2}):(\d{2}):(\d{2})(\.\d+)?"
    r"(Z|([+-])(\d{2}):(\d{2}))?)?$"
)


def get_timestamp(date_time: str) -> float:
    """Return the Unix timestamp of an ISO8601 date/datetime in seconds.

    If the datetime has no offset, it is assumed to be an UTC datetime.

    :param date_time: The datetime string to return as timestamp
    :returns: The timestamp corresponding to the ``date_time`` string in seconds

    Examples:
        >>> get_timestamp("2023-09-23T12:34:56Z")  # doctest: +ELLIPSIS
        1695472496.0
        >>> get_timestamp("2023-09-23T12:34:56+02:00")  # doctest: +ELLIPSIS
        1695465296.0
        >>> get_timestamp("2023-09-23")  # doctest: +ELLIPSIS
        1695427200.0
    """
    dt = isoparse(date_time)
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def datetime_range(start: dt, end: dt) -> Iterator[dt]:
    """Generator function for all dates in-between ``start`` and ``end`` date."""
    delta = end - start
    for nday in range(delta.days + 1):
        yield start + datetime.timedelta(days=nday)


def is_range_in_range(valid_range: str, check_range: str) -> bool:
    """Check if the check_range is completely within the valid_range.

    This function checks if both the start and end dates of the check_range
    are within the start and end dates of the valid_range.

    :param valid_range: The valid date range in the format 'YYYY-MM-DD/YYYY-MM-DD'.
    :param check_range: The date range to check in the format 'YYYY-MM-DD/YYYY-MM-DD'.
    :returns: True if check_range is within valid_range, otherwise False.

    Examples:
        >>> is_range_in_range("2023-01-01/2023-12-31", "2023-03-01/2023-03-31")
        True
        >>> is_range_in_range("2023-01-01/2023-12-31", "2022-12-01/2023-03-31")
        False
        >>> is_range_in_range("2023-01-01/2023-12-31", "2023-11-01/2024-01-01")
        False
        >>> is_range_in_range("2023-01-01/2023-12-31", "invalid-range")
        False
        >>> is_range_in_range("invalid-range", "2023-03-01/2023-03-31")
        False
    """
    if "/" not in valid_range or "/" not in check_range:
        return False

    # Split the date ranges into start and end dates
    start_valid, end_valid = valid_range.split("/")
    start_check, end_check = check_range.split("/")

    # Convert the strings to datetime objects using fromisoformat
    start_valid_dt = datetime.datetime.fromisoformat(start_valid)
    end_valid_dt = datetime.datetime.fromisoformat(end_valid)
    start_check_dt = datetime.datetime.fromisoformat(start_check)
    end_check_dt = datetime.datetime.fromisoformat(end_check)

    # Check if check_range is within valid_range
    return start_valid_dt <= start_check_dt and end_valid_dt >= end_check_dt


def get_datetime(arguments: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Get start and end dates from a dict containing `/` separated dates in `datetime` item

    :param arguments: dict containing a single date or `/` separated dates in `datetime` item
    :returns: Start date and end date from datetime string (duplicate value if only one date as input)

    Examples:
        >>> get_datetime({"datetime": "2023-03-01/2023-03-31"})
        ('2023-03-01T00:00:00', '2023-03-31T00:00:00')
        >>> get_datetime({"datetime": "2023-03-01"})
        ('2023-03-01T00:00:00', '2023-03-01T00:00:00')
        >>> get_datetime({"datetime": "../2023-03-31"})
        (None, '2023-03-31T00:00:00')
        >>> get_datetime({"datetime": "2023-03-01/.."})
        ('2023-03-01T00:00:00', None)
        >>> get_datetime({"dtstart": "2023-03-01", "dtend": "2023-03-31"})
        ('2023-03-01T00:00:00', '2023-03-31T00:00:00')
        >>> get_datetime({})
        (None, None)
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
    """
    Check if the input date can be parsed as a date

    Examples:
        >>> from eodag.utils.exceptions import ValidationError
        >>> get_date("2023-09-23")
        '2023-09-23T00:00:00'
        >>> get_date(None) is None
        True
        >>> get_date("invalid-date")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        ValidationError
    """

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

    Examples:
        >>> from eodag.utils.exceptions import ValidationError
        >>> rfc3339_str_to_datetime("2023-09-23T12:34:56Z")
        datetime.datetime(2023, 9, 23, 12, 34, 56, tzinfo=datetime.timezone.utc)

        >>> rfc3339_str_to_datetime("invalid-date")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        ValidationError
    """
    # Uppercase the string
    s = s.upper()

    # Match against RFC3339 regex.
    result = re.match(RFC3339_PATTERN, s)
    if not result:
        raise ValidationError("Invalid RFC3339 datetime.")

    return dateutil.parser.isoparse(s).replace(tzinfo=datetime.timezone.utc)
