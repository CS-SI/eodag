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
"""Miscellaneous utilities to be used throughout eodag.

Everything that does not fit into one of the specialised categories of utilities in
this package should go here
"""

from __future__ import annotations

import ast
import datetime
import errno
import functools
import hashlib
import inspect
import logging as py_logging
import mimetypes
import os
import re
import shutil
import ssl
import string
import sys
import types
import unicodedata
import warnings
from collections import defaultdict
from copy import deepcopy as copy_deepcopy
from dataclasses import dataclass
from datetime import datetime as dt
from email.message import Message
from glob import glob
from importlib.metadata import metadata
from itertools import repeat, starmap
from pathlib import Path
from tempfile import mkdtemp
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Union,
    cast,
)

# All modules using these should import them from utils package
from urllib.parse import (  # noqa; noqa
    parse_qs,
    parse_qsl,
    quote,
    unquote,
    urlencode,
    urljoin,
    urlparse,
    urlsplit,
)
from urllib.request import url2pathname

if sys.version_info >= (3, 12):
    from typing import Unpack  # type: ignore # noqa
else:
    from typing_extensions import Unpack  # noqa


import click
import orjson
import shapefile
import shapely.wkt
import yaml
from dateutil.parser import isoparse
from dateutil.tz import UTC
from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse
from jsonpath_ng.jsonpath import Child, Fields, Index, Root, Slice
from requests import HTTPError, Response
from shapely.geometry import Polygon, shape
from shapely.geometry.base import GEOMETRY_TYPES, BaseGeometry
from tqdm.auto import tqdm

from eodag.utils import logging as eodag_logging
from eodag.utils.exceptions import MisconfiguredError

if TYPE_CHECKING:
    from jsonpath_ng import JSONPath

    from eodag.api.product._product import EOProduct


logger = py_logging.getLogger("eodag.utils")

DEFAULT_PROJ = "EPSG:4326"

GENERIC_PRODUCT_TYPE = "GENERIC_PRODUCT_TYPE"
GENERIC_STAC_PROVIDER = "generic_stac_provider"

STAC_SEARCH_PLUGINS = [
    "StacSearch",
    "StacListAssets",
    "StaticStacSearch",
]

eodag_version = metadata("eodag")["Version"]
USER_AGENT = {"User-Agent": f"eodag/{eodag_version}"}

HTTP_REQ_TIMEOUT = 5  # in seconds
DEFAULT_SEARCH_TIMEOUT = 20  # in seconds
DEFAULT_STREAM_REQUESTS_TIMEOUT = 60  # in seconds

REQ_RETRY_TOTAL = 3
REQ_RETRY_BACKOFF_FACTOR = 2
REQ_RETRY_STATUS_FORCELIST = [401, 429, 500, 502, 503, 504]

# default wait times in minutes
DEFAULT_DOWNLOAD_WAIT = 0.2  # in minutes
DEFAULT_DOWNLOAD_TIMEOUT = 10  # in minutes

JSONPATH_MATCH = re.compile(r"^[\{\(]*\$(\..*)*$")
WORKABLE_JSONPATH_MATCH = re.compile(r"^\$(\.[a-zA-Z0-9-_:\.\[\]\"\(\)=\?\*]+)*$")
ARRAY_FIELD_MATCH = re.compile(r"^[a-zA-Z0-9-_:]+(\[[0-9\*]+\])+$")

# pagination defaults
DEFAULT_PAGE = 1
DEFAULT_ITEMS_PER_PAGE = 20
# Default maximum number of items per page requested by search_all. 50 instead of 20
# (DEFAULT_ITEMS_PER_PAGE) to increase it to the known and current minimum value (mundi)
DEFAULT_MAX_ITEMS_PER_PAGE = 50

# default product-types start date
DEFAULT_MISSION_START_DATE = "2015-01-01T00:00:00.000Z"

# default token expiration margin in seconds
DEFAULT_TOKEN_EXPIRATION_MARGIN = 60

# update missing mimetypes
mimetypes.add_type("text/xml", ".xsd")
mimetypes.add_type("application/x-grib", ".grib")
mimetypes.add_type("application/x-grib2", ".grib2")
# jp2 is missing on windows
mimetypes.add_type("image/jp2", ".jp2")


def _deprecated(reason: str = "", version: Optional[str] = None) -> Callable[..., Any]:
    """Simple decorator to mark functions/methods/classes as deprecated.

    Warning: Does not work with staticmethods!

    @deprecate(reason="why", version="1.2")
    def foo():
        pass
    foo()
    DeprecationWarning: Call to deprecated function/method foo (why) -- Deprecated since v1.2
    """

    def decorator(callable: Callable[..., Any]) -> Any:
        if inspect.isclass(callable):
            ctype = "class"
        else:
            ctype = "function/method"
        cname = callable.__name__
        reason_ = f"({reason})" if reason else ""
        version_ = f" -- Deprecated since v{version}" if version else ""

        @functools.wraps(callable)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with warnings.catch_warnings():
                warnings.simplefilter("always", DeprecationWarning)
                warnings.warn(
                    f"Call to deprecated {ctype} {cname} {reason_}{version_}",
                    category=DeprecationWarning,
                    stacklevel=2,
                )
            return callable(*args, **kwargs)

        return wrapper

    return decorator


class FloatRange(click.types.FloatParamType):
    """A parameter that works similar to :data:`click.FLOAT` but restricts the
    value to fit into a range. Fails if the value doesn't fit into the range.
    """

    name = "percentage"

    def __init__(
        self, min: Optional[float] = None, max: Optional[float] = None
    ) -> None:
        self.min = min
        self.max = max

    def convert(
        self,
        value: Any,
        param: Optional[click.core.Parameter],
        ctx: Optional[click.core.Context],
    ) -> Any:
        """Convert value"""
        rv = click.types.FloatParamType.convert(self, value, param, ctx)
        if (
            self.min is not None
            and rv < self.min
            or self.max is not None
            and rv > self.max
        ):
            if self.min is None:
                self.fail(
                    "%s is bigger than the maximum valid value " "%s." % (rv, self.max),
                    param,
                    ctx,
                )
            elif self.max is None:
                self.fail(
                    "%s is smaller than the minimum valid value "
                    "%s." % (rv, self.min),
                    param,
                    ctx,
                )
            else:
                self.fail(
                    "%s is not in the valid range of %s to %s."
                    % (rv, self.min, self.max),
                    param,
                    ctx,
                )
        return rv

    def __repr__(self) -> str:
        return "FloatRange(%r, %r)" % (self.min, self.max)


def slugify(value: Any, allow_unicode: bool = False) -> str:
    """Copied from Django Source code, only modifying last line (no need for safe
    strings).

    source: https://github.com/django/django/blob/master/django/utils/text.py

    Convert to ASCII if ``allow_unicode`` is ``False``. Convert spaces to hyphens.
    Remove characters that aren't alphanumerics, underscores, or hyphens.
    Convert to lowercase. Also strip leading and trailing whitespace.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def sanitize(value: str) -> str:
    """Sanitize string to be used as a name of a directory.

    >>> sanitize('productName')
    'productName'
    >>> sanitize('name with multiple  spaces')
    'name_with_multiple_spaces'
    >>> sanitize('âtre fête île alcôve bûche çà génèse où Noël ovoïde capharnaüm')
    'atre_fete_ile_alcove_buche_ca_genese_ou_Noel_ovoide_capharnaum'
    >>> sanitize('replace,ponctuation:;signs!?byunderscorekeeping-hyphen.dot_and_underscore')   # noqa
    'replace_ponctuation_signs_byunderscorekeeping-hyphen.dot_and_underscore'
    """
    # remove accents
    rv = strip_accents(value)
    # replace punctuation signs and spaces by underscore
    # keep hyphen, dot and underscore from punctuation
    tobereplaced = re.sub(r"[-_.]", "", string.punctuation)
    # add spaces to be removed
    tobereplaced += r"\s"

    rv = re.sub(r"[" + tobereplaced + r"]+", "_", rv)
    return str(rv)


def strip_accents(s: str) -> str:
    """Strip accents of a string.

    >>> strip_accents('productName')
    'productName'
    >>> strip_accents('génèse')
    'genese'
    >>> strip_accents('preserve-punct-special-chars:;,?!§%$£œ')
    'preserve-punct-special-chars:;,?!§%$£œ'
    """
    # Mn stands for a nonspacing combining mark
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def uri_to_path(uri: str) -> str:
    """
    Convert a file URI (e.g. ``file:///tmp``) to a local path (e.g. ``/tmp``)
    """
    if not uri.startswith("file"):
        raise ValueError("A file URI must be provided (e.g. 'file:///tmp'")
    _, _, path, _, _ = urlsplit(uri)
    # On Windows urlsplit returns the path starting with a slash ('/C:/User)
    path = url2pathname(path)
    # url2pathname removes it
    return path


def path_to_uri(path: str) -> str:
    """Convert a local absolute path to a file URI"""
    return Path(path).as_uri()


def mutate_dict_in_place(func: Callable[[Any], Any], mapping: dict[Any, Any]) -> None:
    """Apply func to values of mapping.

    The mapping object's values are modified in-place. The function is recursive,
    allowing to also modify values of nested dicts that may be level-1 values of
    mapping.

    :param func: A function to apply to each value of mapping which is not a dict object
    :param mapping: A Python dict object
    :returns: None
    """
    for key, value in mapping.items():
        if isinstance(value, dict):
            mutate_dict_in_place(func, value)
        else:
            mapping[key] = func(value)


def merge_mappings(mapping1: dict[Any, Any], mapping2: dict[Any, Any]) -> None:
    """Merge two mappings with string keys, values from ``mapping2`` overriding values
    from ``mapping1``.

    Do its best to detect the key in ``mapping1`` to override. For example:

    >>> mapping2 = {"keya": "new"}
    >>> mapping1 = {"keyA": "obsolete"}
    >>> merge_mappings(mapping1, mapping2)
    >>> mapping1
    {'keyA': 'new'}

    If ``mapping2`` has a key that cannot be detected in ``mapping1``, this new key is
    added to ``mapping1`` as is.

    :param mapping1: The mapping containing values to be overridden
    :param mapping2: The mapping containing values that will override the first mapping
    """
    # A mapping between mapping1 keys as lowercase strings and original mapping1 keys
    m1_keys_lowercase = {key.lower(): key for key in mapping1}
    for key, value in mapping2.items():
        if isinstance(value, dict):
            try:
                merge_mappings(mapping1[key], value)
            except KeyError:
                # If the key from mapping2 is not in mapping1, it is either key is
                # the lowercased form of the corresponding key in mapping1 or because
                # key is a new key to be added in mapping1
                current_value = mapping1.setdefault(m1_keys_lowercase.get(key, key), {})
                if not current_value:
                    current_value.update(value)
                else:
                    merge_mappings(current_value, value)
        else:
            # Even for "scalar" values (a.k.a not nested structures), first check if
            # the key from mapping1 is not the lowercase version of a key in mapping2.
            # Otherwise, create the key in mapping1. This is the meaning of
            # `m1_keys_lowercase.get(key, key)`
            current_value = mapping1.get(m1_keys_lowercase.get(key, key))
            if current_value is not None:
                current_value_type = type(current_value)
                new_value_type = type(value)
                try:
                    # If current or new value is a list (search queryable parameter), simply replace current with new
                    if (
                        new_value_type == list
                        and current_value_type != list
                        or new_value_type != list
                        and current_value_type == list
                    ):
                        mapping1[m1_keys_lowercase.get(key, key)] = value
                    else:
                        mapping1[m1_keys_lowercase.get(key, key)] = cast_scalar_value(
                            value, current_value_type
                        )
                except (TypeError, ValueError):
                    # Ignore any override value that does not have the same type
                    # as the default value
                    logger.debug(
                        f"Ignored '{key}' setting override from '{current_value}' to '{value}', "
                        f"(could not cast {new_value_type} to {current_value_type})"
                    )
                    pass
            else:
                mapping1[key] = value


def maybe_generator(obj: Any) -> Iterator[Any]:
    """Generator function that get an arbitrary object and generate values from it if
    the object is a generator."""
    if isinstance(obj, types.GeneratorType):
        for elt in obj:
            yield elt
    else:
        yield obj


def get_timestamp(date_time: str) -> float:
    """Return the Unix timestamp of an ISO8601 date/datetime in seconds.

    If the datetime has no offset, it is assumed to be an UTC datetime.

    :param date_time: The datetime string to return as timestamp
    :returns: The timestamp corresponding to the ``date_time`` string in seconds
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


class DownloadedCallback:
    """Example class for callback after each download in :meth:`~eodag.api.core.EODataAccessGateway.download_all`"""

    def __call__(self, product: EOProduct) -> None:
        """Callback

        :param product: The downloaded EO product
        """
        logger.debug("Download finished for the product %s", product)


class ProgressCallback(tqdm):
    """A callable used to render progress to users for long running processes.

    It inherits from :class:`tqdm.auto.tqdm`, and accepts the same arguments on
    instantiation: ``iterable``, ``desc``, ``total``, ``leave``, ``file``, ``ncols``,
    ``mininterval``, ``maxinterval``, ``miniters``, ``ascii``, ``disable``, ``unit``,
    ``unit_scale``, ``dynamic_ncols``, ``smoothing``, ``bar_format``, ``initial``,
    ``position``, ``postfix``, ``unit_divisor``.

    It can be globally disabled using ``eodag.utils.logging.setup_logging(0)`` or
    ``eodag.utils.logging.setup_logging(level, no_progress_bar=True)``, and
    individually disabled using ``disable=True``.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.kwargs = kwargs.copy()
        if "unit" not in kwargs:
            kwargs["unit"] = "B"
        if "unit_scale" not in kwargs:
            kwargs["unit_scale"] = True
        if "desc" not in kwargs:
            kwargs["desc"] = ""
        if "position" not in kwargs:
            kwargs["position"] = 0
        if "disable" not in kwargs:
            kwargs["disable"] = eodag_logging.disable_tqdm
        if "dynamic_ncols" not in kwargs:
            kwargs["dynamic_ncols"] = True

        super(ProgressCallback, self).__init__(*args, **kwargs)

    def __call__(self, increment: int, total: Optional[int] = None) -> None:
        """Update the progress bar.

        :param increment: Amount of data already processed
        :param total: (optional) Maximum amount of data to be processed
        """
        if total is not None and total != self.total:
            self.reset(total=total)

        self.update(increment)

    def copy(self, *args: Any, **kwargs: Any) -> ProgressCallback:
        """Returns another progress callback using the same initial
        keyword-arguments.

        Optional ``args`` and ``kwargs`` parameters will be used to create a
        new :class:`~eodag.utils.ProgressCallback` instance, overriding initial
        `kwargs`.
        """

        return ProgressCallback(*args, **dict(self.kwargs, **kwargs))


@_deprecated(reason="Use ProgressCallback class instead", version="2.2.1")
class NotebookProgressCallback(tqdm):
    """A custom progress bar to be used inside Jupyter notebooks"""

    pass


@_deprecated(reason="Use ProgressCallback class instead", version="2.2.1")
def get_progress_callback() -> tqdm:
    """Get progress_callback"""

    return tqdm()


def repeatfunc(func: Callable[..., Any], n: int, *args: Any) -> starmap:
    """Call ``func`` ``n`` times with ``args``"""
    return starmap(func, repeat(args, n))


def makedirs(dirpath: str) -> None:
    """Create a directory in filesystem with parents if necessary"""
    try:
        os.makedirs(dirpath)
    except OSError as err:
        # Reraise the error unless it's about an already existing directory
        if err.errno != errno.EEXIST or not os.path.isdir(dirpath):
            raise


def rename_subfolder(dirpath: str, name: str) -> None:
    """Rename first subfolder found in ``dirpath`` with given ``name``,
    raise :class:`RuntimeError` if no subfolder can be found

    :param dirpath: path to the directory containing the subfolder
    :param name: new name of the subfolder
    :raises: :class:`RuntimeError`

    Example:

    >>> import os
    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as tmpdir:
    ...     somefolder = os.path.join(tmpdir, "somefolder")
    ...     otherfolder = os.path.join(tmpdir, "otherfolder")
    ...     os.makedirs(somefolder)
    ...     assert os.path.isdir(somefolder) and not os.path.isdir(otherfolder)
    ...     rename_subfolder(tmpdir, "otherfolder")
    ...     assert not os.path.isdir(somefolder) and os.path.isdir(otherfolder)

    Before::

        $ tree <tmp-folder>
        <tmp-folder>
        └── somefolder
            └── somefile

    After::

        $ tree <tmp-folder>
        <tmp-folder>
        └── otherfolder
            └── somefile

    """
    try:
        subdir, *_ = (p for p in glob(os.path.join(dirpath, "*")) if os.path.isdir(p))
    except ValueError:
        raise RuntimeError(f"No subfolder was found in {dirpath}")

    os.rename(
        subdir,
        os.path.join(dirpath, name),
    )


def rename_with_version(file_path: str, suffix: str = "old") -> str:
    """
    Renames a file by appending and incrementing a version number if a conflict exists.

    :param file_path: full path of the file to rename
    :param suffix: suffix preceding version number in case of name conflict
    :returns: new file path with the version appended or incremented

    Example:

    >>> import tempfile
    >>> from pathlib import Path
    >>> with tempfile.TemporaryDirectory() as tmpdir:
    ...     file_path = (Path(tmpdir) / "foo.txt")
    ...     file_path.touch()
    ...     (Path(tmpdir) / "foo_old1.txt").touch()
    ...     expected = str(Path(tmpdir) / "foo_old2.txt")
    ...     assert expected == rename_with_version(str(file_path))

    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"The file '{file_path}' does not exist.")

    dir_path, file_name = os.path.split(file_path)
    file_base, file_ext = os.path.splitext(file_name)

    new_file_path = file_path

    # loop and iterate on conflicting existing files
    version = 0
    while os.path.exists(new_file_path):
        version += 1
        new_file_name = f"{file_base}_{suffix}{version}{file_ext}"
        new_file_path = os.path.join(dir_path, new_file_name)

    # Rename the file
    os.rename(file_path, new_file_path)
    return new_file_path


def format_dict_items(
    config_dict: dict[str, Any], **format_variables: Any
) -> dict[Any, Any]:
    r"""Recursively apply :meth:`str.format` to ``**format_variables`` on ``config_dict`` values

    >>> format_dict_items(
    ...     {"foo": {"bar": "{a}"}, "baz": ["{b}?", "{b}!"]},
    ...     **{"a": "qux", "b": "quux"},
    ... ) == {"foo": {"bar": "qux"}, "baz": ["quux?", "quux!"]}
    True

    :param config_dict: Dictionary having values that need to be parsed
    :param format_variables: Variables used as args for parsing
    :returns: Updated dict
    """
    return dict_items_recursive_apply(config_dict, format_string, **format_variables)


def jsonpath_parse_dict_items(
    jsonpath_dict: dict[str, Any], values_dict: dict[str, Any]
) -> dict[Any, Any]:
    """Recursively parse :class:`jsonpath_ng.JSONPath` elements in dict

    >>> import jsonpath_ng.ext as jsonpath
    >>> jsonpath_parse_dict_items(
    ...     {"foo": {"bar": parse("$.a.b")}, "qux": [parse("$.c"), parse("$.c")]},
    ...     {"a":{"b":"baz"}, "c":"quux"}
    ... ) == {'foo': {'bar': 'baz'}, 'qux': ['quux', 'quux']}
    True

    :param jsonpath_dict: Dictionary having :class:`jsonpath_ng.JSONPath` values that need to be parsed
    :param values_dict: Values dict used as args for parsing
    :returns: Updated dict
    """
    return dict_items_recursive_apply(jsonpath_dict, parse_jsonpath, **values_dict)


def update_nested_dict(
    old_dict: dict[Any, Any],
    new_dict: dict[Any, Any],
    extend_list_values: bool = False,
    allow_empty_values: bool = False,
    allow_extend_duplicates: bool = True,
) -> dict[Any, Any]:
    """Update recursively ``old_dict`` items with ``new_dict`` ones

    >>> update_nested_dict(
    ...     {"a": {"a.a": 1, "a.b": 2}, "b": 3},
    ...     {"a": {"a.a": 10}}
    ... ) == {'a': {'a.a': 10, 'a.b': 2}, 'b': 3}
    True
    >>> update_nested_dict(
    ...     {"a": {"a.a": [1, 2]}},
    ...     {"a": {"a.a": [10, 2]}},
    ...     extend_list_values=True,
    ...     allow_extend_duplicates=True
    ... ) == {'a': {'a.a': [1, 2, 10, 2]}}
    True
    >>> update_nested_dict(
    ...     {"a": {"a.a": [1, 2]}},
    ...     {"a": {"a.a": [10, 2]}},
    ...     extend_list_values=True,
    ...     allow_extend_duplicates=False
    ... ) == {'a': {'a.a': [1, 2, 10]}}
    True
    >>> update_nested_dict(
    ...     {"a": {"a.a": 1, "a.b": 2}, "b": 3},
    ...     {"a": {"a.a": None}},
    ... ) == {'a': {'a.a': 1, 'a.b': 2}, 'b': 3}
    True
    >>> update_nested_dict(
    ...     {"a": {"a.a": 1, "a.b": 2}, "b": 3},
    ...     {"a": {"a.a": None}},
    ...     allow_empty_values=True
    ... ) == {'a': {'a.a': None, 'a.b': 2}, 'b': 3}
    True

    :param old_dict: Dict to be updated
    :param new_dict: Incomming dict
    :param extend_list_values: (optional) Extend old_dict value if both old/new values are lists
    :param allow_empty_values: (optional) Allow update with empty values
    :returns: Updated dict
    """
    for k, v in new_dict.items():
        if k in old_dict.keys():
            if isinstance(v, dict) and isinstance(old_dict[k], dict):
                old_dict[k] = update_nested_dict(
                    old_dict[k],
                    v,
                    extend_list_values=extend_list_values,
                    allow_empty_values=allow_empty_values,
                    allow_extend_duplicates=allow_extend_duplicates,
                )
            elif (
                extend_list_values
                and isinstance(old_dict[k], list)
                and isinstance(v, list)
                and (
                    # no common elements
                    not any([x for x in v if x in old_dict[k]])
                    # common elements
                    or any([x for x in v if x in old_dict[k]])
                    and allow_extend_duplicates
                )
            ):
                old_dict[k].extend(v)
            elif (
                extend_list_values
                and isinstance(old_dict[k], list)
                and isinstance(v, list)
                # common elements
                and any([x for x in v if x in old_dict[k]])
                and not allow_extend_duplicates
            ):
                old_dict[k].extend([x for x in v if x not in old_dict[k]])
            elif (v and not allow_empty_values) or allow_empty_values:
                old_dict[k] = v
        else:
            old_dict[k] = v
    return old_dict


def items_recursive_apply(
    input_obj: Union[dict[Any, Any], list[Any]],
    apply_method: Callable[..., Any],
    **apply_method_parameters: Any,
) -> Union[dict[Any, Any], list[Any]]:
    """Recursive apply method to items contained in input object (dict or list)

    >>> items_recursive_apply(
    ...     {"foo": {"bar":"baz"}, "qux": ["a","b"]},
    ...     lambda k,v,x: v.upper()+x, **{"x":"!"}
    ... ) == {'foo': {'bar': 'BAZ!'}, 'qux': ['A!', 'B!']}
    True
    >>> items_recursive_apply(
    ...     [{"foo": {"bar":"baz"}}, "qux"],
    ...     lambda k,v,x: v.upper()+x,
    ...     **{"x":"!"})
    [{'foo': {'bar': 'BAZ!'}}, 'QUX!']
    >>> items_recursive_apply(
    ...     "foo",
    ...     lambda k,v,x: v.upper()+x,
    ...     **{"x":"!"})
    'foo'

    :param input_obj: Input object (dict or list)
    :param apply_method: Method to be applied to dict elements
    :param apply_method_parameters: Optional parameters passed to the method
    :returns: Updated object
    """
    if isinstance(input_obj, dict):
        return dict_items_recursive_apply(
            input_obj, apply_method, **apply_method_parameters
        )
    elif isinstance(input_obj, list):
        return list_items_recursive_apply(
            input_obj, apply_method, **apply_method_parameters
        )
    else:
        logger.warning("Could not use items_recursive_apply on %s" % type(input_obj))
        return input_obj


def dict_items_recursive_apply(
    config_dict: dict[Any, Any],
    apply_method: Callable[..., Any],
    **apply_method_parameters: Any,
) -> dict[Any, Any]:
    """Recursive apply method to dict elements

    >>> dict_items_recursive_apply(
    ...     {"foo": {"bar": "baz"}, "qux": ["a", "b"]},
    ...     lambda k, v, x: v.upper() + x, **{"x": "!"}
    ... ) == {'foo': {'bar': 'BAZ!'}, 'qux': ['A!', 'B!']}
    True

    :param config_dict: Input nested dictionary
    :param apply_method: Method to be applied to dict elements
    :param apply_method_parameters: Optional parameters passed to the method
    :returns: Updated dict
    """
    result_dict: dict[Any, Any] = deepcopy(config_dict)
    for dict_k, dict_v in result_dict.items():
        if isinstance(dict_v, dict):
            result_dict[dict_k] = dict_items_recursive_apply(
                dict_v, apply_method, **apply_method_parameters
            )
        elif any(isinstance(dict_v, t) for t in (list, tuple)):
            result_dict[dict_k] = list_items_recursive_apply(
                list(dict_v), apply_method, **apply_method_parameters
            )
        else:
            result_dict[dict_k] = apply_method(
                dict_k, dict_v, **apply_method_parameters
            )

    return result_dict


def list_items_recursive_apply(
    config_list: list[Any],
    apply_method: Callable[..., Any],
    **apply_method_parameters: Any,
) -> list[Any]:
    """Recursive apply method to list elements

    >>> list_items_recursive_apply(
    ...     [{"foo": {"bar": "baz"}}, "qux"],
    ...     lambda k, v, x: v.upper() + x,
    ...     **{"x": "!"})
    [{'foo': {'bar': 'BAZ!'}}, 'QUX!']

    :param config_list: Input list containing nested lists/dicts
    :param apply_method: Method to be applied to list elements
    :param apply_method_parameters: Optional parameters passed to the method
    :returns: Updated list
    """
    result_list = deepcopy(config_list)
    for list_idx, list_v in enumerate(result_list):
        if isinstance(list_v, dict):
            result_list[list_idx] = dict_items_recursive_apply(
                list_v, apply_method, **apply_method_parameters
            )
        elif any(isinstance(list_v, t) for t in (list, tuple)):
            result_list[list_idx] = list_items_recursive_apply(
                list_v, apply_method, **apply_method_parameters
            )
        else:
            result_list[list_idx] = apply_method(
                list_idx, list_v, **apply_method_parameters
            )

    return result_list


def items_recursive_sort(
    input_obj: Union[list[Any], dict[Any, Any]],
) -> Union[list[Any], dict[Any, Any]]:
    """Recursive sort dict items contained in input object (dict or list)

    >>> items_recursive_sort(
    ...     {"b": {"b": "c", "a": 0}, "a": ["b", {2: 0, 0: 1, 1: 2}]},
    ... ) == {"a": ["b", {0: 1, 1: 2, 2: 0}], "b": {"a": 0, "b": "c"}}
    True
    >>> items_recursive_sort(["b", {2: 0, 0: 1, 1:2}])
    ['b', {0: 1, 1: 2, 2: 0}]
    >>> items_recursive_sort("foo")
    'foo'

    :param input_obj: Input object (dict or list)
    :returns: Updated object
    """
    if isinstance(input_obj, dict):
        return dict_items_recursive_sort(input_obj)
    elif isinstance(input_obj, list):
        return list_items_recursive_sort(input_obj)
    else:
        logger.warning("Could not use items_recursive_sort on %s" % type(input_obj))
        return input_obj


def dict_items_recursive_sort(config_dict: dict[Any, Any]) -> dict[Any, Any]:
    """Recursive sort dict elements

    >>> dict_items_recursive_sort(
    ...     {"b": {"b": "c", "a": 0}, "a": ["b", {2: 0, 0: 1, 1: 2}]},
    ... ) == {"a": ["b", {0: 1, 1: 2, 2: 0}], "b": {"a": 0, "b": "c"}}
    True

    :param config_dict: Input nested dictionary
    :returns: Updated dict
    """
    result_dict: dict[Any, Any] = deepcopy(config_dict)
    for dict_k, dict_v in result_dict.items():
        if isinstance(dict_v, dict):
            result_dict[dict_k] = dict_items_recursive_sort(dict_v)
        elif any(isinstance(dict_v, t) for t in (list, tuple)):
            result_dict[dict_k] = list_items_recursive_sort(dict_v)
        else:
            result_dict[dict_k] = dict_v

    return dict(sorted(result_dict.items()))


def list_items_recursive_sort(config_list: list[Any]) -> list[Any]:
    """Recursive sort dicts in list elements

    >>> list_items_recursive_sort(["b", {2: 0, 0: 1, 1: 2}])
    ['b', {0: 1, 1: 2, 2: 0}]

    :param config_list: Input list containing nested lists/dicts
    :returns: Updated list
    """
    result_list: list[Any] = deepcopy(config_list)
    for list_idx, list_v in enumerate(result_list):
        if isinstance(list_v, dict):
            result_list[list_idx] = dict_items_recursive_sort(list_v)
        elif any(isinstance(list_v, t) for t in (list, tuple)):
            result_list[list_idx] = list_items_recursive_sort(list_v)
        else:
            result_list[list_idx] = list_v

    return result_list


def string_to_jsonpath(*args: Any, force: bool = False) -> Union[str, JSONPath]:
    """Get :class:`jsonpath_ng.JSONPath` for ``$.foo.bar`` like string

    >>> string_to_jsonpath(None, "$.foo.bar")
    Child(Child(Root(), Fields('foo')), Fields('bar'))
    >>> string_to_jsonpath("$.foo.bar")
    Child(Child(Root(), Fields('foo')), Fields('bar'))
    >>> string_to_jsonpath('$.foo[0][*]')
    Child(Child(Child(Root(), Fields('foo')), Index(index=0)), Slice(start=None,end=None,step=None))
    >>> string_to_jsonpath("foo")
    'foo'
    >>> string_to_jsonpath("foo", force=True)
    Fields('foo')

    :param args: Last arg as input string value, to be converted
    :param force: force conversion even if input string is not detected as a :class:`jsonpath_ng.JSONPath`
    :returns: Parsed value
    """
    path_str: str = args[-1]
    if JSONPATH_MATCH.match(str(path_str)) or force:
        try:
            common_jsonpath = "$"
            common_jsonpath_parsed = Root()

            # combine with common jsonpath if possible
            if WORKABLE_JSONPATH_MATCH.match(path_str):
                path_suffix = path_str[len(common_jsonpath) + 1 :]
                path_splits = path_suffix.split(".") if path_suffix else []
                parsed_path = common_jsonpath_parsed
                for path_split in path_splits:
                    path_split = path_split.strip("'").strip('"')
                    if "[" in path_split and ARRAY_FIELD_MATCH.match(path_split):
                        # handle nested array
                        indexed_path_and_indexes = path_split[:-1].split("[")
                        indexed_path = indexed_path_and_indexes[0]
                        parsed_path = Child(parsed_path, Fields(indexed_path))
                        for idx in range(len(indexed_path_and_indexes) - 1):
                            index: Union[int, str] = (
                                indexed_path_and_indexes[idx + 1][:-1]
                                if idx < len(indexed_path_and_indexes) - 2
                                else indexed_path_and_indexes[idx + 1]
                            )
                            # wildcard index
                            if index == "*":
                                parsed_path = Child(
                                    parsed_path,
                                    Slice(start=None, end=None, step=None),
                                )
                                continue
                            try:
                                index = int(index)
                            except ValueError:
                                # unsupported index
                                parsed_path = cached_parse(path_str)
                                break
                            # integer index
                            parsed_path = Child(
                                parsed_path,
                                Index(index=index),
                            )
                    elif "[" in path_split:
                        # unsupported array field
                        parsed_path = cached_parse(path_str)
                        break
                    else:
                        parsed_path = Child(parsed_path, Fields(path_split))
                return parsed_path
            else:
                return cached_parse(path_str)

        except Exception:  # jsonpath_ng does not provide a proper exception
            # If str_value does not contain a jsonpath, return it as is
            return path_str
    else:
        return path_str


def format_string(key: str, str_to_format: Any, **format_variables: Any) -> Any:
    """Format ``"{foo}"``-like string

    >>> format_string(None, "foo {bar}, {baz} ?", **{"bar": "qux", "baz": "quux"})
    'foo qux, quux ?'

    :param key: Input item key
    :param str_to_format: Input item value, to be parsed
    :returns: Parsed value
    """
    if not isinstance(str_to_format, str):
        return str_to_format

    # eodag mappings function usage, e.g. '{foo#to_bar}'
    COMPLEX_QS_REGEX = re.compile(r"^(.+=)?([^=]*)({.+})+([^=&]*)$")
    if COMPLEX_QS_REGEX.match(str_to_format) and "#" in str_to_format:
        from eodag.api.product.metadata_mapping import format_metadata

        result = format_metadata(str_to_format, **format_variables)

    else:
        # defaultdict usage will return "" for missing keys in format_args
        try:
            result = str_to_format.format_map(defaultdict(str, **format_variables))
        except (ValueError, TypeError) as e:
            raise MisconfiguredError(
                f"Unable to format str={str_to_format} using {str(format_variables)}: {str(e)}"
            )

    # try to convert string to python object
    try:
        return ast.literal_eval(result)
    except (SyntaxError, ValueError):
        return result


def parse_jsonpath(
    key: str, jsonpath_obj: Union[str, jsonpath.Child], **values_dict: dict[str, Any]
) -> Optional[str]:
    """Parse jsonpah in ``jsonpath_obj`` using ``values_dict``

    >>> import jsonpath_ng.ext as jsonpath
    >>> parse_jsonpath(None, parse("$.foo.bar"), **{"foo": {"bar": "baz"}})
    'baz'

    :param key: Input item key
    :param jsonpath_obj: Input item value, to be parsed
    :param values_dict: Values used as args for parsing
    :returns: Parsed value
    """
    if isinstance(jsonpath_obj, jsonpath.Child):
        match = jsonpath_obj.find(values_dict)
        return match[0].value if len(match) == 1 else None
    else:
        return jsonpath_obj


def nested_pairs2dict(pairs: Union[list[Any], Any]) -> Union[Any, dict[Any, Any]]:
    """Create a dict using nested pairs

    >>> nested_pairs2dict([["foo", [["bar", "baz"]]]])
    {'foo': {'bar': 'baz'}}

    :param pairs: Pairs of key / value
    :returns: Created dict
    """
    d = {}
    try:
        for k, v in pairs:
            if isinstance(v, list):
                v = nested_pairs2dict(v)
            d[k] = v
    except ValueError:
        return pairs

    return d


def get_geometry_from_various(
    locations_config: list[dict[str, Any]] = [], **query_args: Any
) -> BaseGeometry:
    """Creates a ``shapely.geometry`` using given query kwargs arguments

    :param locations_config: (optional) EODAG locations configuration
    :param query_args: Query kwargs arguments from :meth:`~eodag.api.core.EODataAccessGateway.search`
    :returns: shapely Geometry found
    :raises: :class:`ValueError`
    """
    geom = None

    if "geometry" in query_args:
        geom_arg = query_args["geometry"]

        bbox_keys = ["lonmin", "latmin", "lonmax", "latmax"]
        if isinstance(geom_arg, dict) and geom_arg.get("type") in GEOMETRY_TYPES:
            # geojson geometry
            geom = cast(BaseGeometry, shape(geom_arg))
        elif isinstance(geom_arg, dict) and all(k in geom_arg for k in bbox_keys):
            # bbox dict
            geom = Polygon(
                (
                    (geom_arg["lonmin"], geom_arg["latmin"]),
                    (geom_arg["lonmin"], geom_arg["latmax"]),
                    (geom_arg["lonmax"], geom_arg["latmax"]),
                    (geom_arg["lonmax"], geom_arg["latmin"]),
                )
            )
        elif isinstance(geom_arg, (list, tuple)) and len(geom_arg) >= 4:
            # bbox list
            geom = Polygon(
                (
                    (geom_arg[0], geom_arg[1]),
                    (geom_arg[0], geom_arg[3]),
                    (geom_arg[2], geom_arg[3]),
                    (geom_arg[2], geom_arg[1]),
                )
            )
        elif isinstance(geom_arg, str):
            # WKT geometry
            geom = shapely.wkt.loads(geom_arg)
        elif isinstance(geom_arg, BaseGeometry):
            geom = geom_arg
        elif geom_arg is None:
            pass
        else:
            raise TypeError("Unexpected geometry type: {}".format(type(geom_arg)))

    # look for location name in locations configuration
    locations_dict = {loc["name"]: loc for loc in locations_config}
    # The location query kwargs can either be in query_args or in query_args["locations"],
    # support for which were added in 2.0.0 and 2.1.0 respectively.
    # The location query kwargs in query_args is supported for backward compatibility,
    # the recommended usage is that they are in query_args["locations"]
    locations = query_args.get("locations")
    locations = locations if locations is not None else {}
    # In query_args["locations"] we can check that the location_names are correct
    locations = locations if locations is not None else {}
    for location_name in locations:
        if location_name not in locations_dict:
            raise ValueError(
                f"The location name {location_name} is wrong. "
                f"It must be one of: {locations_dict.keys()}"
            )
    query_locations = {**query_args, **locations}
    for arg in query_locations.keys():
        if arg in locations_dict.keys():
            found = False
            pattern = rf"{query_locations[arg]}"
            attr = locations_dict[arg]["attr"]
            with shapefile.Reader(locations_dict[arg]["path"]) as shp:
                for shaperec in shp.shapeRecords():
                    if re.search(pattern, str(shaperec.record[attr])):
                        found = True
                        new_geom = shape(shaperec.shape)
                        # get geoms union
                        geom = new_geom.union(geom) if geom else new_geom
            if not found:
                raise ValueError(
                    f"No match found for the search location '{arg}' "
                    f"with the pattern '{pattern}'."
                )

    return geom


class MockResponse:
    """Fake requests response"""

    def __init__(
        self,
        json_data: Any = None,
        status_code: int = 200,
        headers: Optional[dict[str, Any]] = None,
    ) -> None:
        self.json_data = json_data
        self.status_code = status_code
        self.content = json_data
        self.headers = headers

    def json(self) -> Any:
        """Return json data"""
        return self.json_data

    def __iter__(self):
        yield self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def raise_for_status(self) -> None:
        """raises an exception when the status is not ok"""
        if self.status_code != 200:
            response = Response()
            response.status_code = self.status_code
            raise HTTPError(response=response)


def md5sum(file_path: str) -> str:
    """Get file MD5 checksum

    >>> import os
    >>> md5sum(os.devnull)
    'd41d8cd98f00b204e9800998ecf8427e'

    :param file_path: input file path
    :returns: MD5 checksum
    """
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def obj_md5sum(data: Any) -> str:
    """Get MD5 checksum from JSON serializable object

    >>> obj_md5sum(None)
    '37a6259cc0c1dae299a7866489dff0bd'

    :param data: JSON serializable input object
    :returns: MD5 checksum
    """
    return hashlib.md5(orjson.dumps(data, option=orjson.OPT_SORT_KEYS)).hexdigest()


@functools.lru_cache()
def cached_parse(str_to_parse: str) -> JSONPath:
    """Cached :func:`jsonpath_ng.ext.parse`

    >>> cached_parse.cache_clear()
    >>> cached_parse("$.foo")
    Child(Root(), Fields('foo'))
    >>> cached_parse.cache_info()
    CacheInfo(hits=0, misses=1, maxsize=128, currsize=1)
    >>> cached_parse("$.foo")
    Child(Root(), Fields('foo'))
    >>> cached_parse.cache_info()
    CacheInfo(hits=1, misses=1, maxsize=128, currsize=1)
    >>> cached_parse("$.bar")
    Child(Root(), Fields('bar'))
    >>> cached_parse.cache_info()
    CacheInfo(hits=1, misses=2, maxsize=128, currsize=2)

    :param str_to_parse: string to parse as :class:`jsonpath_ng.JSONPath`
    :returns: parsed :class:`jsonpath_ng.JSONPath`
    """
    return parse(str_to_parse)


@functools.lru_cache()
def _mutable_cached_yaml_load(config_path: str) -> Any:
    with open(
        os.path.abspath(os.path.realpath(config_path)), mode="r", encoding="utf-8"
    ) as fh:
        return yaml.load(fh, Loader=yaml.SafeLoader)


def cached_yaml_load(config_path: str) -> dict[str, Any]:
    """Cached :func:`yaml.load`

    :param config_path: path to the yaml configuration file
    :returns: loaded yaml configuration
    """
    return copy_deepcopy(_mutable_cached_yaml_load(config_path))


@functools.lru_cache()
def _mutable_cached_yaml_load_all(config_path: str) -> list[Any]:
    with open(config_path, "r") as fh:
        return list(yaml.load_all(fh, Loader=yaml.Loader))


def cached_yaml_load_all(config_path: str) -> list[Any]:
    """Cached :func:`yaml.load_all`

    Load all configurations stored in the configuration file as separated yaml documents

    :param config_path: path to the yaml configuration file
    :returns: list of configurations
    """
    return copy_deepcopy(_mutable_cached_yaml_load_all(config_path))


def get_bucket_name_and_prefix(
    url: str, bucket_path_level: Optional[int] = None
) -> tuple[Optional[str], Optional[str]]:
    """Extract bucket name and prefix from URL

    :param url: (optional) URL to use as product.location
    :param bucket_path_level: (optional) bucket location index in path.split('/')
    :returns: bucket_name and prefix as str
    """
    bucket, prefix = None, None

    scheme, netloc, path, _, _, _ = urlparse(url)
    subdomain = netloc.split(".")[0]
    path = path.strip("/")

    if "/" in path and scheme and subdomain == "s3" and bucket_path_level is None:
        bucket, prefix = path.split("/", 1)
    elif scheme and bucket_path_level is None:
        bucket = subdomain
        prefix = path
    elif not scheme and bucket_path_level is None:
        prefix = path
    elif bucket_path_level is not None:
        parts = path.split("/")
        bucket, prefix = (
            parts[bucket_path_level],
            "/".join(parts[(bucket_path_level + 1) :]),
        )

    return bucket, prefix


def flatten_top_directories(
    nested_dir_root: str, common_subdirs_path: Optional[str] = None
) -> None:
    """Flatten directory structure, removing common empty sub-directories

    :param nested_dir_root: Absolute path of the directory structure to flatten
    :param common_subdirs_path: (optional) Absolute path of the desired subdirectory to remove
    """
    if not common_subdirs_path:
        subpaths_list = [p for p in Path(nested_dir_root).glob("**/*") if p.is_file()]
        common_subdirs_path = os.path.commonpath(subpaths_list)

    if Path(common_subdirs_path).is_file():
        common_subdirs_path = os.path.dirname(common_subdirs_path)

    if nested_dir_root != common_subdirs_path:
        logger.debug(f"Flatten {common_subdirs_path} to {nested_dir_root}")
        tmp_path = mkdtemp()
        shutil.copytree(common_subdirs_path, tmp_path, dirs_exist_ok=True)
        shutil.rmtree(nested_dir_root)
        shutil.move(tmp_path, nested_dir_root)


def deepcopy(sth: Any) -> Any:
    """Customized and faster deepcopy inspired by https://stackoverflow.com/a/45858907

    ``_copy_list`` and ``_copy_dict`` dispatchers available for the moment

    :param sth: Object to copy
    :returns: Copied object
    """
    _dispatcher: dict[type[Any], Callable[..., Any]] = {}

    def _copy_list(
        input_list: list[Any], dispatch: dict[type[Any], Callable[..., Any]]
    ):
        ret = input_list.copy()
        for idx, item in enumerate(ret):
            cp = dispatch.get(type(item))
            if cp is not None:
                ret[idx] = cp(item, dispatch)
        return ret

    def _copy_dict(
        input_dict: dict[Any, Any], dispatch: dict[type[Any], Callable[..., Any]]
    ):
        ret = input_dict.copy()
        for key, value in ret.items():
            cp = dispatch.get(type(value))
            if cp is not None:
                ret[key] = cp(value, dispatch)
        return ret

    _dispatcher[list] = _copy_list
    _dispatcher[dict] = _copy_dict

    cp = _dispatcher.get(type(sth))
    if cp is None:
        return sth
    else:
        return cp(sth, _dispatcher)


def parse_header(header: str) -> Message:
    """Parse HTTP header

    >>> parse_header(
    ...     'Content-Disposition: form-data; name="field2"; filename="example.txt"'
    ... ).get_param("filename")
    'example.txt'

    :param header: header to parse
    :returns: parsed header
    """
    m = Message()
    m["content-type"] = header
    return m


def cast_scalar_value(value: Any, new_type: Any) -> Any:
    """Convert a scalar (not nested) value type to the given one

    >>> cast_scalar_value('1', int)
    1
    >>> cast_scalar_value(1, str)
    '1'
    >>> cast_scalar_value('false', bool)
    False

    :param value: the scalar value to convert
    :param new_type: the wanted type
    :returns: scalar ``value`` converted to ``new_type``
    """
    if isinstance(value, str) and new_type is bool:
        # Bool is a type with special meaning in Python, thus the special
        # case
        if value.capitalize() not in ("True", "False"):
            raise ValueError(
                "Only true or false strings (case insensitive) are "
                "allowed for booleans"
            )
        # Get the real Python value of the boolean. e.g: value='tRuE'
        # => eval(value.capitalize())=True.
        # str.capitalize() transforms the first character of the string
        # to a capital letter
        return eval(value.capitalize())

    return new_type(value)


@dataclass
class StreamResponse:
    """Represents a streaming response"""

    content: Iterable[bytes]
    headers: Optional[Mapping[str, str]] = None
    media_type: Optional[str] = None
    status_code: Optional[int] = None


def guess_file_type(file: str) -> Optional[str]:
    """Guess the mime type of a file or URL based on its extension,
    using eodag extended mimetypes definition

    >>> guess_file_type('foo.tiff')
    'image/tiff'
    >>> guess_file_type('foo.grib')
    'application/x-grib'

    :param file: file url or path
    :returns: guessed mime type
    """
    mime_type, _ = mimetypes.guess_type(file, False)
    if mime_type == "text/xml":
        return "application/xml"
    return mime_type


def guess_extension(type: str) -> Optional[str]:
    """Guess extension from mime type, using eodag extended mimetypes definition

    >>> guess_extension('image/tiff')
    '.tiff'
    >>> guess_extension('application/x-grib')
    '.grib'

    :param type: mime type
    :returns: guessed file extension
    """
    return mimetypes.guess_extension(type, strict=False)


def get_ssl_context(ssl_verify: bool) -> ssl.SSLContext:
    """
    Returns an SSL context based on ``ssl_verify`` argument.

    :param ssl_verify: :attr:`~eodag.config.PluginConfig.ssl_verify` parameter
    :returns: An SSL context object.
    """
    ctx = ssl.create_default_context()
    if not ssl_verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    else:
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def sort_dict(input_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively sorts a dict by keys.

    :param input_dict: input dict
    :returns: sorted dict

    >>> sort_dict({"b": {"c": 1, "a": 2, "b": 3}, "a": 4})
    {'a': 4, 'b': {'a': 2, 'b': 3, 'c': 1}}
    """
    return {
        k: sort_dict(v) if isinstance(v, dict) else v
        for k, v in sorted(input_dict.items())
    }


def dict_md5sum(input_dict: dict[str, Any]) -> str:
    """
    Hash nested dictionary

    :param input_dict: input dict
    :returns: hash

    >>> hd = dict_md5sum({"b": {"c": 1, "a": 2, "b": 3}, "a": 4})
    >>> hd
    'a195bcef1bb3b419e9e74b7cc5db8098'
    >>> assert(dict_md5sum({"a": 4, "b": {"b": 3, "c": 1, "a": 2}}) == hd)
    """
    return obj_md5sum(sort_dict(input_dict))


def remove_str_array_quotes(input_str: str) -> str:
    """Remove quotes around arrays to avoid json parsing errors

    :param input_str: string to format
    :returns: string without quotes surrounding array brackets

    >>> remove_str_array_quotes('"a":"["a", "b"]"')
    '"a":["a", "b"]'
    >>> remove_str_array_quotes('{"a":"["a", "b"]", "b": ["c", "d"]}')
    '{"a":["a", "b"], "b": ["c", "d"]}'
    """
    output_str = ""
    for i in range(0, len(input_str)):
        if i < len(input_str) - 1 and input_str[i] == '"' and input_str[i + 1] == "[":
            continue
        if input_str[i] == '"' and input_str[i - 1] == "]":
            continue
        output_str += input_str[i]
    return output_str
