"""
rfc3339.

Taken from stac_fastapi.types to not depend of stac_fastapi.types until it supports pydantic v2
https://github.com/stac-utils/stac-fastapi/issues/593

"""
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

import iso8601
from pystac.utils import datetime_to_str

RFC3339_PATTERN = (
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:T(\d{2}):(\d{2}):(\d{2})(\.\d+)?"
    r"(Z|([+-])(\d{2}):(\d{2}))?)?$"
)


def rfc3339_str_to_datetime(s: str) -> datetime:
    """Convert a string conforming to RFC 3339 to a :class:`datetime.datetime`.

    Uses :meth:`iso8601.parse_date` under the hood.

    Args:
        s (str) : The string to convert to :class:`datetime.datetime`.

    Returns:
        str: The datetime represented by the ISO8601 (RFC 3339) formatted string.

    Raises:
        ValueError: If the string is not a valid RFC 3339 string.
    """
    # Uppercase the string
    s = s.upper()

    # Match against RFC3339 regex.
    result = re.match(RFC3339_PATTERN, s)
    if not result:
        raise ValueError("Invalid RFC3339 datetime.")

    # Parse with pyiso8601
    return iso8601.parse_date(s)


def str_to_interval(
    interval: str,
) -> Optional[Tuple[Optional[datetime], Optional[datetime]]]:
    """Extract a tuple of datetimes from an interval string.

    Interval strings are defined by
    OGC API - Features Part 1 for the datetime query parameter value. These follow the
    form '1985-04-12T23:20:50.52Z/1986-04-12T23:20:50.52Z', and allow either the start
    or end (but not both) to be open-ended with '..' or ''.

    Args:
        interval (str) : The interval string to convert to a :class:`datetime.datetime`
        tuple.

    Raises:
        ValueError: If the string is not a valid interval string.
    """
    if not interval:
        raise ValueError("Empty interval string is invalid.")

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


def now_in_utc() -> datetime:
    """Return a datetime value of now with the UTC timezone applied."""
    return datetime.now(timezone.utc)


def now_to_rfc3339_str() -> str:
    """Return an RFC 3339 string representing now."""
    return datetime_to_str(now_in_utc())
