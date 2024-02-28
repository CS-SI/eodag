# -*- coding: utf-8 -*-
# Copyright 2023, CS Systemes d'Information, https://www.csgroup.eu/
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
import datetime
import re
from typing import Optional, Tuple

import dateutil.parser

RFC3339_PATTERN = (
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:T(\d{2}):(\d{2}):(\d{2})(\.\d+)?"
    r"(Z|([+-])(\d{2}):(\d{2}))?)?$"
)


def rfc3339_str_to_datetime(s: str) -> datetime.datetime:
    """Convert a string conforming to RFC 3339 to a :class:`datetime.datetime`.

    :param s: The string to convert to :class:`datetime.datetime`
    :type s: str

    :returns: The datetime represented by the ISO8601 (RFC 3339) formatted string
    :rtype: :class:`datetime.datetime`

    raises: :class:`ValueError`
    """
    # Uppercase the string
    s = s.upper()

    # Match against RFC3339 regex.
    result = re.match(RFC3339_PATTERN, s)
    if not result:
        raise ValueError("Invalid RFC3339 datetime.")

    return dateutil.parser.isoparse(s).replace(tzinfo=datetime.timezone.utc)


def str_to_interval(
    interval: Optional[str],
) -> Tuple[Optional[datetime.datetime], Optional[datetime.datetime]]:
    """Extract a tuple of datetimes from an interval string.

    Interval strings are defined by
    OGC API - Features Part 1 for the datetime query parameter value. These follow the
    form '1985-04-12T23:20:50.52Z/1986-04-12T23:20:50.52Z', and allow either the start
    or end (but not both) to be open-ended with '..' or ''.

    :param interval: The interval string to convert to a :class:`datetime.datetime`
        tuple.
    :type interval: str

    :raises: :class:`ValueError`
    """
    if not interval:
        return (None, None)

    if "/" not in interval:
        date = rfc3339_str_to_datetime(interval)
        return (date, date)

    values = interval.split("/")
    if len(values) != 2:
        raise ValueError(
            f"Interval string '{interval}' contains more than one forward slash."
        )

    start = None
    end = None
    if values[0] not in ["..", ""]:
        start = rfc3339_str_to_datetime(values[0])
    if values[1] not in ["..", ""]:
        end = rfc3339_str_to_datetime(values[1])

    if start is None and end is None:
        raise ValueError("Double open-ended intervals are not allowed.")
    if start is not None and end is not None and start > end:
        raise ValueError("Start datetime cannot be before end datetime.")
    else:
        return start, end
