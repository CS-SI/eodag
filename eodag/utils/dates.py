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

import calendar
import datetime as dt
import re
from typing import Any, Iterator, Optional, Union

import dateutil.parser
from dateutil import tz
from dateutil.parser import isoparse
from dateutil.tz import UTC

from eodag.utils.exceptions import ValidationError

STAC_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

RFC3339_PATTERN = (
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:T(\d{2}):(\d{2}):(\d{2})(\.\d+)?"
    r"(Z|([+-])(\d{2}):(\d{2}))?)?$"
)

# yyyy-mm-dd
DATE_PATTERN = r"\d{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[0-1])"

# yyyymmdd
COMPACT_DATE_PATTERN = r"\d{4}(0[1-9]|1[0-2])([0-2][0-9]|3[0-1])"

# yyyy-mm-dd/yyyy-mm-dd, yyyy-mm-dd/to/yyyy-mm-dd
DATE_RANGE_PATTERN = DATE_PATTERN + r"(/to/|/)" + DATE_PATTERN

# yyyymmdd/yyyymmdd, yyyymmdd/to/yyyymmdd
COMPACT_DATE_RANGE_PATTERN = COMPACT_DATE_PATTERN + r"(/to/|/)" + COMPACT_DATE_PATTERN


def get_timestamp(date_time: str) -> float:
    """Return the Unix timestamp of an ISO8601 date/datetime in seconds.

    If the datetime has no offset, it is assumed to be an UTC datetime.

    :param date_time: The datetime string to return as timestamp
    :returns: The timestamp corresponding to the ``date_time`` string in seconds
    :raises ValueError: If ``date_time`` cannot be parsed as ISO8601

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


def datetime_range(start: dt.datetime, end: dt.datetime) -> Iterator[dt.datetime]:
    """Generator function for all dates in-between ``start`` and ``end`` date.

    :param start: Start date
    :param end: End date
    :returns: Generator of dates

    Examples:
        >>> from datetime import datetime
        >>> dtr = datetime_range(datetime(2020, 12, 31), datetime(2021, 1, 2))
        >>> next(dtr)
        datetime.datetime(2020, 12, 31, 0, 0)
        >>> next(dtr)
        datetime.datetime(2021, 1, 1, 0, 0)
        >>> next(dtr)
        datetime.datetime(2021, 1, 2, 0, 0)
        >>> next(dtr)
        Traceback (most recent call last):
        ...
        StopIteration
    """
    delta = end - start
    for nday in range(delta.days + 1):
        yield start + dt.timedelta(days=nday)


def is_range_in_range(valid_range: str, check_range: str) -> bool:
    """Check if the check_range is completely within the valid_range.

    This function checks if both the start and end dates of the check_range
    are within the start and end dates of the valid_range.

    :param valid_range: The valid date range in the format 'YYYY-MM-DD/YYYY-MM-DD'.
    :param check_range: The date range to check in the format 'YYYY-MM-DD/YYYY-MM-DD'.
    :returns: True if check_range is within valid_range, otherwise False.
    :raises ValueError: If date parts cannot be parsed as ISO8601

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

    # Convert the strings to datetime objects
    start_valid_dt = isoparse(start_valid)
    end_valid_dt = isoparse(end_valid)
    start_check_dt = isoparse(start_check)
    end_check_dt = isoparse(end_check)

    # Check if check_range is within valid_range
    return start_valid_dt <= start_check_dt and end_valid_dt >= end_check_dt


def get_datetime(arguments: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Get start and end dates from a dict containing `/` separated dates in `datetime` item

    :param arguments: dict containing a single date or `/` separated dates in `datetime` item
    :returns: Start date and end date from datetime string (duplicate value if only one date as input)
    :raises ValidationError: If a date string cannot be parsed

    Examples:
        >>> get_datetime({"datetime": "2023-03-01/2023-03-31"})
        ('2023-03-01T00:00:00.000Z', '2023-03-31T00:00:00.000Z')
        >>> get_datetime({"datetime": "2023-03-01"})
        ('2023-03-01T00:00:00.000Z', '2023-03-01T00:00:00.000Z')
        >>> get_datetime({"datetime": "../2023-03-31"})
        (None, '2023-03-31T00:00:00.000Z')
        >>> get_datetime({"datetime": "2023-03-01/.."})
        ('2023-03-01T00:00:00.000Z', None)
        >>> get_datetime({"dtstart": "2023-03-01", "dtend": "2023-03-31"})
        ('2023-03-01T00:00:00.000Z', '2023-03-31T00:00:00.000Z')
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

    :param date: The date to parse
    :returns: The datetime represented with ISO 8601 UTC format
    :raises ValidationError: If the date string cannot be parsed

    Examples:
        >>> from eodag.utils.exceptions import ValidationError
        >>> get_date("2023-09-23")
        '2023-09-23T00:00:00.000Z'
        >>> get_date(None) is None
        True
        >>> get_date("invalid-date")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        ValidationError
    """

    if not date:
        return None
    result = to_iso_utc_string(date)
    if result is None:
        raise ValidationError("invalid input date: %s" % date)
    return result


def rfc3339_str_to_datetime(s: str) -> dt.datetime:
    """Convert a string conforming to RFC 3339 to a :class:`datetime.datetime`.

    :param s: The string to convert to :class:`datetime.datetime`
    :returns: The datetime represented by the ISO8601 (RFC 3339) formatted string
    :raises ValidationError: If the string does not conform to RFC 3339

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

    return dateutil.parser.isoparse(s).replace(tzinfo=dt.timezone.utc)


def get_min_max(
    value: Optional[Union[str, list[str]]] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Returns the min and max from a list of strings or the same string if a single string is given.

    :param value: a single string or a list of strings
    :returns: a tuple with the min and max values

    Examples:
        >>> get_min_max(["a", "c", "b"])
        ('a', 'c')
        >>> get_min_max(["a"])
        ('a', 'a')
        >>> get_min_max("a")
        ('a', 'a')
    """
    if isinstance(value, list):
        sorted_values = sorted(value)
        return sorted_values[0], sorted_values[-1]
    return value, value


def append_time(input_date: dt.date, time: Optional[str] = None) -> dt.datetime:
    """Appends a string-formatted time to a date.

    :param input_date: Date to combine with the time
    :param time: (optional) time string in format HHMM, HH:MM or HH_MM
    :returns: Datetime obtained by appenting the time to the date

    Examples:
        >>> from eodag.utils.dates import append_time
        >>> from datetime import date
        >>> append_time(date(2020, 12, 13))
        datetime.datetime(2020, 12, 13, 0, 0)
        >>> append_time(date(2020, 12, 13), "")
        datetime.datetime(2020, 12, 13, 0, 0)
        >>> append_time(date(2020, 12, 13), "2400")
        datetime.datetime(2020, 12, 13, 0, 0)
        >>> append_time(date(2020, 12, 13), "14_31")
        datetime.datetime(2020, 12, 13, 14, 31)
    """
    if not time:
        time = "0000"
    time = re.sub(":|_", "", time)
    if time == "2400":
        time = "0000"
    combined_dt = dt.datetime.combine(
        input_date, dt.datetime.strptime(time, "%H%M").time()
    )
    combined_dt.replace(tzinfo=dt.timezone.utc)
    return combined_dt


def parse_date(
    date: str, time: Optional[Union[str, list[str]]] = None
) -> tuple[dt.datetime, dt.datetime]:
    """Parses a date string in formats YYYY-MM-DD, YYYMMDD, solo or in start/end or start/to/end intervals.

    :param date: Single or interval date string
    :returns: A tuple with the start and end datetime
    :raises ValidationError: If a date string cannot be parsed

    Examples:
        >>> parse_date("2020-12-15")
        (datetime.datetime(2020, 12, 15, 0, 0, tzinfo=tzutc()), datetime.datetime(2020, 12, 15, 0, 0, tzinfo=tzutc()))
        >>> parse_date("2020-12-15/to/20201230")
        (datetime.datetime(2020, 12, 15, 0, 0, tzinfo=tzutc()), datetime.datetime(2020, 12, 30, 0, 0, tzinfo=tzutc()))
    """
    if "to" in date:
        start_date_str, end_date_str = date.split("/to/")
    elif "/" in date:
        dates = date.split("/")
        start_date_str = dates[0]
        end_date_str = dates[-1]
    else:
        start_date_str = end_date_str = date

    # Update YYYYMMDD formatted dates
    if re.match(r"^\d{8}$", start_date_str):
        start_date_str = (
            f"{start_date_str[:4]}-{start_date_str[4:6]}-{start_date_str[6:]}"
        )
    if re.match(r"^\d{8}$", end_date_str):
        end_date_str = f"{end_date_str[:4]}-{end_date_str[4:6]}-{end_date_str[6:]}"

    start_date = parse_to_utc(start_date_str)
    end_date = parse_to_utc(end_date_str)

    if time:
        start_t, end_t = get_min_max(time)
        start_date = append_time(start_date.date(), start_t)
        end_date = append_time(end_date.date(), end_t)

    return start_date, end_date


def parse_year_month_day(
    year: Union[str, list[str]],
    month: Optional[Union[str, list[str]]] = None,
    day: Optional[Union[str, list[str]]] = None,
    time: Optional[Union[str, list[str]]] = None,
) -> tuple[dt.datetime, dt.datetime]:
    """Returns minimum and maximum datetimes from given lists of years, months, days, times.

    :param year: List of years or a single one
    :param month: (optional) List of months or a single one
    :param day: (optional) List of days or a single one
    :param time: (optional) List of times or a single one in the format HHMM, HH:MM or HH_MM
    :returns: A tuple with the start and end datetime

    Examples:
        >>> parse_year_month_day(["2020", "2021", "2022"], ["01", "03", "05"], "01", ["0000", "1200"])
        (datetime.datetime(2020, 1, 1, 0, 0), datetime.datetime(2022, 5, 1, 12, 0))
    """

    def build_date(year, month=None, day=None, time=None) -> dt.datetime:
        """Datetime from default_date with updated year, month, day and time."""
        updated_date = dt.datetime(int(year), 1, 1).replace(
            month=int(month) if month is not None else 1,
            day=int(day) if day is not None else 1,
        )
        if time is not None:
            updated_date = append_time(updated_date.date(), time)
        return updated_date

    start_y, end_y = get_min_max(year)
    start_m, end_m = get_min_max(month)
    start_d, end_d = get_min_max(day)
    start_t, end_t = get_min_max(time)

    start_date = build_date(start_y, start_m, start_d, start_t)
    end_date = build_date(end_y, end_m, end_d, end_t)

    return start_date, end_date


def format_date(date: dt.datetime) -> str:
    """Format a ``datetime`` with the format 'YYYY-MM-DD'.

    :param date: Datetime to format
    :returns: Date string in the format 'YYYY-MM-DD'

    Examples:
        >>> from datetime import datetime
        >>> format_date(datetime(2020, 12, 2))
        '2020-12-02'
        >>> format_date(datetime(2020, 12, 2, 11, 22, 33))
        '2020-12-02'
    """
    return date.isoformat()[:10]


def format_date_range(start: dt.datetime, end: dt.datetime) -> str:
    """Format a range with the format 'YYYY-MM-DD/YYYY-MM-DD'.

    :param start: Start datetime
    :param end: End datetime
    :returns: Date range in the format 'YYYY-MM-DD/YYYY-MM-DD'

    Examples:
        >>> from datetime import datetime
        >>> format_date_range(datetime(2020, 12, 2, 11, 22, 33), datetime(2020, 12, 31))
        '2020-12-02/2020-12-31'
    """
    return f"{format_date(start)}/{format_date(end)}"


def validate_datetime_param(
    value: Optional[Union[str, list[str]]],
    param_name: str,
    formatters: list[str],
) -> Optional[list[str]]:
    """Validate and collect parameter values matching any of the given datetime formats.

    Ensures each value can be parsed by at least one of the ``formatters``
    (``datetime.strptime`` patterns), and returns the sorted list of valid values.

    :param value: Raw value(s) from search parameters (string or list of strings)
    :param param_name: Parameter name (used in error messages)
    :param formatters: ``datetime.strptime`` format strings used for validation
    :returns: Sorted list of valid values, or ``None`` if ``value`` is ``None``
    :raises ValidationError: If none of the values match any formatter

    Examples:
        >>> validate_datetime_param(["2023", "2024"], "year", ["%Y"])
        ['2023', '2024']
        >>> validate_datetime_param("12:00", "time", ["%H:%M", "%H%M"])
        ['12:00']
        >>> validate_datetime_param(None, "year", ["%Y"]) is None
        True
        >>> validate_datetime_param("bad", "year", ["%Y"])  # doctest: +ELLIPSIS
        Traceback (most recent call last):
            ...
        eodag.utils.exceptions.ValidationError: Malformed parameter "year": ...
    """
    if value is None:
        return None

    if not isinstance(value, list):
        value = [value]

    buffer = []
    has_error = None
    for item in value:
        for formatter in formatters:
            try:
                # Prepend a dummy year when format contains %d without %Y
                # to avoid ambiguity (deprecated in 3.14, error in 3.15+)
                if "%d" in formatter and "%Y" not in formatter:
                    dt.datetime.strptime(f"2000 {item}", f"%Y {formatter}")
                else:
                    dt.datetime.strptime(item, formatter)
                buffer.append(item)
            except Exception as e:
                has_error = e

    if has_error is not None and len(buffer) == 0:
        raise ValidationError(
            'Malformed parameter "{}": {}'.format(param_name, str(has_error))
        )

    buffer.sort()
    return buffer


def time_values_to_hhmm(time_values: list[str]) -> list[str]:
    """Convert time values to 4-digit HHMM format.

    Strips non-digit characters (e.g. ``"12:00"`` -> ``"1200"``, ``"06:00"`` -> ``"0600"``),
    then right-pads with zeros to handle 2-digit hour-only values (e.g. ``"06"`` -> ``"0600"``).
    Deduplicates while preserving order.

    :param time_values: List of time strings in various formats
    :returns: List of unique time strings in HHMM format

    Examples:
        >>> time_values_to_hhmm(["12:00", "06:00"])
        ['1200', '0600']
        >>> time_values_to_hhmm(["12:00", "12:00"])
        ['1200']
        >>> time_values_to_hhmm(["06"])
        ['0600']
    """
    buffer: list[str] = []
    for time_str in time_values:
        time_str = re.sub("[^0-9]+", "", time_str)
        time_str = time_str.ljust(4, "0")
        if time_str not in buffer:
            buffer.append(time_str)
    return buffer


def ensure_utc(value: dt.datetime) -> dt.datetime:
    """Ensure a datetime is UTC-aware.

    If the datetime is naive, it is assumed to be UTC.
    If it already has a timezone, it is converted to UTC.

    :param value: A datetime object
    :returns: A timezone-aware datetime in UTC

    Examples:
        >>> from datetime import datetime, timezone
        >>> ensure_utc(datetime(2020, 1, 1, 12, 0))
        datetime.datetime(2020, 1, 1, 12, 0, tzinfo=tzutc())
        >>> ensure_utc(datetime(2021, 4, 21, 0, 0, tzinfo=timezone.utc))
        datetime.datetime(2021, 4, 21, 0, 0, tzinfo=tzutc())
    """
    if not value.tzinfo:
        return value.replace(tzinfo=tz.UTC)
    return value.astimezone(tz.UTC)


def parse_to_utc(raw: str) -> dt.datetime:
    """Parse a date string to a UTC-aware datetime.

    Uses ``dateutil.parser.isoparse`` for ISO strings. Falls back to
    ``dateutil.parser.parse`` for non-ISO formats. Always returns a
    timezone-aware datetime in UTC.

    :param raw: A date string
    :returns: A timezone-aware datetime in UTC
    :raises ValidationError: If the string cannot be parsed

    Examples:
        >>> parse_to_utc("2020-01-01")
        datetime.datetime(2020, 1, 1, 0, 0, tzinfo=tzutc())
        >>> parse_to_utc("2021-04-21T00:00:00+02:00")
        datetime.datetime(2021, 4, 20, 22, 0, tzinfo=tzutc())
        >>> parse_to_utc("invalid")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
            ...
        ValidationError
    """
    try:
        parsed = isoparse(raw)
    except (ValueError, TypeError):
        try:
            parsed = dateutil.parser.parse(raw)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Cannot parse date: {raw!r}") from e
    if not parsed.tzinfo:
        parsed = parsed.replace(tzinfo=tz.UTC)
    return parsed.astimezone(tz.UTC)


def to_iso_utc_string(
    raw: Optional[Union[dt.datetime, str]],
) -> Optional[str]:
    """Convert a datetime or date string to an ISO 8601 UTC string with millisecond precision.

    :param raw: A datetime object or date string to convert
    :returns: ISO 8601 formatted UTC string (``YYYY-MM-DDTHH:MM:SS.sssZ``), or ``None``

    Examples:
        >>> from datetime import datetime
        >>> to_iso_utc_string(datetime(2020, 1, 1, 12, 0))
        '2020-01-01T12:00:00.000Z'
        >>> to_iso_utc_string("2020-01-01")
        '2020-01-01T00:00:00.000Z'
        >>> to_iso_utc_string("2021-04-21T00:00:00+02:00")
        '2021-04-20T22:00:00.000Z'
        >>> to_iso_utc_string(None) is None
        True
    """
    if raw is None:
        return None
    try:
        utc_dt = ensure_utc(raw) if isinstance(raw, dt.datetime) else parse_to_utc(raw)
        return utc_dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    except (ValidationError, OverflowError):
        return None


def compute_date_range_from_params(
    date: Optional[str] = None,
    time: Optional[list[str]] = None,
    year: Optional[list[str]] = None,
    month: Optional[list[str]] = None,
    day: Optional[list[str]] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Compute start/end ISO UTC datetime strings from date parameters.

    Handles two modes:

    - **date** + optional **time**: parse the date string and apply time bounds
    - **year** + optional **month**/**day**/**time**: compute bounds from year/month/day/time ranges

    Time values are expected in HHMM format (see :func:`time_values_to_hhmm`).

    Returns ``(None, None)`` if neither ``date`` nor ``year`` is provided.

    :param date: Date string (single date, or interval with ``/`` or ``/to/``)
    :param time: List of normalized time strings in HHMM format
    :param year: List of year strings
    :param month: List of month strings (zero-padded)
    :param day: List of day strings (zero-padded)
    :returns: Tuple of (start_datetime, end_datetime) as ISO UTC strings
    :raises ValidationError: If a date string cannot be parsed

    Examples:
        >>> compute_date_range_from_params(date="2020-12-15")
        ('2020-12-15T00:00:00.000Z', '2020-12-15T00:00:00.000Z')
        >>> compute_date_range_from_params(date="2020-12-15", time=["0600", "1800"])
        ('2020-12-15T06:00:00.000Z', '2020-12-15T18:00:00.000Z')
        >>> compute_date_range_from_params(year=["2020", "2021"])
        ('2020-01-01T00:00:00.000Z', '2021-12-31T23:59:59.000Z')
        >>> compute_date_range_from_params(year=["2020"], month=["03"], day=["15"])
        ('2020-03-15T00:00:00.000Z', '2020-03-15T23:59:59.000Z')
        >>> compute_date_range_from_params()
        (None, None)
    """
    if date is not None:
        start, end = parse_date(date, time)
        return to_iso_utc_string(start), to_iso_utc_string(end)

    if year is not None:
        min_year, max_year = year[0], year[-1]

        if month:
            min_month, max_month = month[0], month[-1]
        else:
            min_month, max_month = "01", "12"

        _, last_day = calendar.monthrange(int(max_year), int(max_month))
        min_day = "01"
        max_day = str(last_day).zfill(2)

        if day:
            if min_day <= day[0] <= max_day:
                min_day = day[0]
            if min_day <= day[-1] <= max_day:
                max_day = day[-1]

        if time:
            min_time = f"{time[0][0:2]}:{time[0][2:4]}:00.000"
            max_time = f"{time[-1][0:2]}:{time[-1][2:4]}:00.000"
        else:
            min_time, max_time = "00:00:00.000", "23:59:59.000"

        start_str = f"{min_year}-{min_month}-{min_day}T{min_time}Z"
        end_str = f"{max_year}-{max_month}-{max_day}T{max_time}Z"
        return start_str, end_str

    return None, None
