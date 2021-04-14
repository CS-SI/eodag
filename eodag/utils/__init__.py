# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, http://www.c-s.fr
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
import ast
import copy
import errno
import functools
import inspect
import logging
import os
import re
import string
import types
import unicodedata
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from itertools import repeat, starmap

# All modules using these should import them from utils package
from urllib.parse import (  # noqa; noqa
    parse_qs,
    quote,
    urlencode,
    urljoin,
    urlparse,
    urlunparse,
)

import click
import shapefile
import shapely.wkt
from jsonpath_ng import jsonpath
from jsonpath_ng.ext import parse
from requests.auth import AuthBase
from shapely.geometry import Polygon, shape
from shapely.geometry.base import BaseGeometry
from tqdm import tqdm
from tqdm.notebook import tqdm as tqdm_notebook

from eodag.utils.notebook import check_ipython

DEFAULT_PROJ = "EPSG:4326"

logger = logging.getLogger("eodag.utils")

GENERIC_PRODUCT_TYPE = "GENERIC_PRODUCT_TYPE"


class RequestsTokenAuth(AuthBase):
    """A custom authentication class to be used with requests module"""

    def __init__(self, token, where, qs_key=None):
        self.token = token
        self.where = where
        self.qs_key = qs_key

    def __call__(self, request):
        """Perform the actual authentication"""
        if self.where == "qs":
            parts = urlparse(request.url)
            qs = parse_qs(parts.query)
            qs[self.qs_key] = self.token
            request.url = urlunparse(
                (
                    parts.scheme,
                    parts.netloc,
                    parts.path,
                    parts.params,
                    urlencode(qs),
                    parts.fragment,
                )
            )
        elif self.where == "header":
            request.headers["Authorization"] = "Bearer {}".format(self.token)
        return request


class FloatRange(click.types.FloatParamType):
    """A parameter that works similar to :data:`click.FLOAT` but restricts the
    value to fit into a range. Fails if the value doesn't fit into the range.
    """

    name = "percentage"

    def __init__(self, min=None, max=None):
        self.min = min
        self.max = max

    def convert(self, value, param, ctx):
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

    def __repr__(self):
        return "FloatRange(%r, %r)" % (self.min, self.max)


def slugify(value, allow_unicode=False):
    """Copied from Django Source code, only modifying last line (no need for safe
    strings).
    source: https://github.com/django/django/blob/master/django/utils/text.py

    Convert to ASCII if 'allow_unicode' is False. Convert spaces to hyphens.
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


def sanitize(value):
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


def strip_accents(s):
    """Strip accents of a string.

    >>> strip_accents('productName')
    'productName'
    >>> strip_accents('génèse')
    'genese'
    >>> strip_accents('preserve-punct-special-chars:;,?!§%$£œ')
    'preserve-punct-special-chars:;,?!§%$£œ'
    """
    # Mn stands for a nonspacing combining mark (e.g. '́')
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def mutate_dict_in_place(func, mapping):
    """Apply func to values of mapping.

    The mapping object's values are modified in-place. The function is recursive,
    allowing to also modify values of nested dicts that may be level-1 values of
    mapping.

    :param func: A function to apply to each value of mapping which is not a dict object
    :type func: func
    :param mapping: A Python dict object
    :type mapping: dict
    :returns: None
    """
    for key, value in mapping.items():
        if isinstance(value, dict):
            mutate_dict_in_place(func, value)
        else:
            mapping[key] = func(value)


def merge_mappings(mapping1, mapping2):
    """Merge two mappings with string keys, values from `mapping2` overriding values
    from `mapping1`.

    Do its best to detect the key in `mapping1` to override. For example, let's say
    we have::

        mapping2 = {"keya": "new"}
        mapping1 = {"keyA": "obsolete"}

    Then::

        merge_mappings(mapping1, mapping2) ==> {"keyA": "new"}

    If mapping2 has a key that cannot be detected in mapping1, this new key is added
    to mapping1 as is.

    :param dict mapping1: The mapping containing values to be overridden
    :param dict mapping2: The mapping containing values that will override the
                          first mapping
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
            # m1_keys_lowercase.get(key, key)
            current_value = mapping1.get(m1_keys_lowercase.get(key, key), None)
            if current_value is not None:
                current_value_type = type(current_value)
                if isinstance(value, str):
                    # Bool is a type with special meaning in Python, thus the special
                    # case
                    if current_value_type is bool:
                        if value.capitalize() not in ("True", "False"):
                            raise ValueError(
                                "Only true or false strings (case insensitive) are "
                                "allowed for booleans"
                            )
                        # Get the real Python value of the boolean. e.g: value='tRuE'
                        # => eval(value.capitalize())=True.
                        # str.capitalize() transforms the first character of the string
                        # to a capital letter
                        mapping1[m1_keys_lowercase.get(key, key)] = eval(
                            value.capitalize()
                        )
                    else:
                        mapping1[m1_keys_lowercase.get(key, key)] = current_value_type(
                            value
                        )
                else:
                    try:
                        mapping1[m1_keys_lowercase.get(key, key)] = current_value_type(
                            value
                        )
                    except TypeError:
                        # Ignore any override value that does not have the same type
                        # as the default value
                        pass
            else:
                mapping1[key] = value


def maybe_generator(obj):
    """Generator function that get an arbitrary object and generate values from it if
    the object is a generator."""
    if isinstance(obj, types.GeneratorType):
        for elt in obj:
            yield elt
    else:
        yield obj


def get_timestamp(date_time, date_format="%Y-%m-%dT%H:%M:%S", as_utc=False):
    """Returns the given UTC date_time string formatted with date_format as timestamp

    :param date_time: the datetime string to return as timestamp
    :type date_time: str
    :param date_format: (optional) the date format in which date_time is given,
                        defaults to '%Y-%m-%dT%H:%M:%S'
    :type date_format: str
    :param as_utc: (optional) if ``True``, consider the input ``date_time`` as UTC,
                        defaults to ``False``
    :type date_format: bool
    :returns: the timestamp corresponding to the date_time string in seconds
    :rtype: float

    .. versionchanged::
        2.1.0

            * The optional parameter ``as_utc`` to consider the input date as UTC.
    """
    dt = datetime.strptime(date_time, date_format)
    if as_utc:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


class ProgressCallback(object):
    """A callable used to render progress to users for long running processes"""

    def __init__(self, max_size=None):
        self.pb = None
        self.max_size = max_size
        self.unit = "B"
        self.unit_scale = True
        self.desc = ""
        self.position = 0

    def __call__(self, current_size, max_size=None):
        """Update the progress bar.

        :param current_size: amount of data already processed
        :type current_size: int
        :param max_size: maximum amount of data to be processed
        :type max_size: int
        """
        if max_size is not None:
            self.max_size = max_size
        if self.pb is None:
            self.pb = tqdm(
                total=self.max_size,
                unit=self.unit,
                unit_scale=self.unit_scale,
                desc=self.desc,
                position=self.position,
                dynamic_ncols=True,
            )
        self.pb.update(current_size)

    def reset(self):
        """Reset progress bar"""
        if hasattr(self.pb, "reset"):
            self.pb.reset(self.max_size)
            self.pb.total = self.max_size
            self.pb.unit = self.unit
            self.pb.unit_scale = self.unit_scale
            self.pb.desc = self.desc
            self.pb.position = self.position

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if hasattr(self.pb, "close"):
            self.pb.close()
        return False


class NotebookProgressCallback(ProgressCallback):
    """A custom progress bar to be used inside Jupyter notebooks"""

    def __call__(self, current_size, max_size=None):
        """Update the progress bar"""
        if max_size is not None:
            self.max_size = max_size
        if self.pb is None:
            self.pb = tqdm_notebook(
                total=self.max_size,
                unit=self.unit,
                unit_scale=self.unit_scale,
                desc=self.desc,
                position=self.position,
                dynamic_ncols=True,
            )
        self.pb.update(current_size)


def get_progress_callback():
    """Get progress_callback"""

    if check_ipython():
        return NotebookProgressCallback()
    else:
        return ProgressCallback()


def repeatfunc(func, n, *args):
    """Call `func` `n` times with `args`"""
    return starmap(func, repeat(args, n))


def makedirs(dirpath):
    """Create a directory in filesystem with parents if necessary"""
    try:
        os.makedirs(dirpath)
    except OSError as err:
        # Reraise the error unless it's about an already existing directory
        if err.errno != errno.EEXIST or not os.path.isdir(dirpath):
            raise


def format_dict_items(config_dict, **format_variables):
    r"""Recursive apply string.format(\**format_variables) to dict elements

    >>> format_dict_items(
    ...     {"foo": {"bar": "{a}"}, "baz": ["{b}?", "{b}!"]},
    ...     **{"a": "qux", "b":"quux"},
    ... ) == {"foo": {"bar": "qux"}, "baz": ["quux?", "quux!"]}
    True

    :param config_dict: dictionnary having values that need to be parsed
    :type config_dict: dict
    :param format_variables: variables used as args for parsing
    :type format_variables: dict
    :returns: updated dict
    :rtype: dict
    """
    return dict_items_recursive_apply(config_dict, format_string, **format_variables)


def jsonpath_parse_dict_items(jsonpath_dict, values_dict):
    """Recursive parse jsonpath elements in dict

    >>> import jsonpath_ng.ext as jsonpath
    >>> jsonpath_parse_dict_items(
    ...     {"foo": {"bar": parse("$.a.b")}, "qux": [parse("$.c"), parse("$.c")]},
    ...     {"a":{"b":"baz"}, "c":"quux"}
    ... ) == {'foo': {'bar': 'baz'}, 'qux': ['quux', 'quux']}
    True

    :param jsonpath_dict: dictionnary having values that need to be parsed
    :type jsonpath_dict: dict
    :param values_dict: values dict used as args for parsing
    :type values_dict: dict
    :returns: updated dict
    :rtype: dict
    """
    return dict_items_recursive_apply(jsonpath_dict, parse_jsonpath, **values_dict)


def update_nested_dict(old_dict, new_dict, extend_list_values=False):
    """Update recursively old_dict items with new_dict ones

    >>> update_nested_dict(
    ...     {"a": {"a.a": 1, "a.b": 2}, "b": 3},
    ...     {"a": {"a.a": 10}}
    ... ) == {'a': {'a.a': 10, 'a.b': 2}, 'b': 3}
    True
    >>> update_nested_dict(
    ...     {"a": {"a.a": [1, 2]}},
    ...     {"a": {"a.a": [10]}},
    ...     extend_list_values=True
    ... ) == {'a': {'a.a': [1, 2, 10]}}
    True

    :param old_dict: dict to be updated
    :type old_dict: dict
    :param new_dict: incomming dict
    :type new_dict: dict
    :param extend_list_values: extend old_dict value if both old/new values are lists
    :type extend_list_values: bool
    :returns: updated dict
    :rtype: dict
    """
    for k, v in new_dict.items():
        if k in old_dict.keys():
            if isinstance(v, dict) and isinstance(old_dict[k], dict):
                old_dict[k] = update_nested_dict(
                    old_dict[k], v, extend_list_values=extend_list_values
                )
            elif (
                extend_list_values
                and isinstance(old_dict[k], list)
                and isinstance(v, list)
            ):
                old_dict[k].extend(v)
            elif v:
                old_dict[k] = v
        else:
            old_dict[k] = v
    return old_dict


def items_recursive_apply(input_obj, apply_method, **apply_method_parameters):
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

    :param input_obj: input object (dict or list)
    :type input_obj: Union[dict,list]
    :param apply_method: method to be applied to dict elements
    :type apply_method: :func:`apply_method`
    :param apply_method_parameters: optional parameters passed to the method
    :type apply_method_parameters: dict
    :returns: updated object
    :rtype: Union[dict,list]
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


def dict_items_recursive_apply(config_dict, apply_method, **apply_method_parameters):
    """Recursive apply method to dict elements

    >>> dict_items_recursive_apply(
    ...     {"foo": {"bar":"baz"}, "qux": ["a","b"]},
    ...     lambda k,v,x: v.upper()+x, **{"x":"!"}
    ... ) == {'foo': {'bar': 'BAZ!'}, 'qux': ['A!', 'B!']}
    True

    :param config_dict: input nested dictionnary
    :type config_dict: dict
    :param apply_method: method to be applied to dict elements
    :type apply_method: :func:`apply_method`
    :param apply_method_parameters: optional parameters passed to the method
    :type apply_method_parameters: dict
    :returns: updated dict
    :rtype: dict
    """
    result_dict = copy.deepcopy(config_dict)
    for dict_k, dict_v in result_dict.items():
        if isinstance(dict_v, dict):
            result_dict[dict_k] = dict_items_recursive_apply(
                dict_v, apply_method, **apply_method_parameters
            )
        elif any(isinstance(dict_v, t) for t in (list, tuple)):
            result_dict[dict_k] = list_items_recursive_apply(
                dict_v, apply_method, **apply_method_parameters
            )
        else:
            result_dict[dict_k] = apply_method(
                dict_k, dict_v, **apply_method_parameters
            )

    return result_dict


def list_items_recursive_apply(config_list, apply_method, **apply_method_parameters):
    """Recursive apply method to list elements

    >>> list_items_recursive_apply(
    ...     [{"foo": {"bar":"baz"}}, "qux"],
    ...     lambda k,v,x: v.upper()+x,
    ...     **{"x":"!"})
    [{'foo': {'bar': 'BAZ!'}}, 'QUX!']

    :param config_list: input list containing nested lists/dicts
    :type config_list: list
    :param apply_method: method to be applied to list elements
    :type apply_method: :func:`apply_method`
    :param apply_method_parameters: optional parameters passed to the method
    :type apply_method_parameters: dict
    :returns: updated list
    :rtype: list
    """
    result_list = copy.deepcopy(config_list)
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


def string_to_jsonpath(key, str_value):
    """Get jsonpath for "$.foo.bar" like string

    >>> string_to_jsonpath(None, "$.foo.bar")
    Child(Child(Root(), Fields('foo')), Fields('bar'))

    :param key: input item key
    :type key: str
    :param str_value: input item value, to be converted
    :type str_value: str
    :returns: parsed value
    :rtype: str
    """
    if "$." in str(str_value):
        try:
            return parse(str_value)
        except Exception:  # jsonpath_ng does not provide a proper exception
            # If str_value does not contain a jsonpath, return it as is
            return str_value
    else:
        return str_value


def format_string(key, str_to_format, **format_variables):
    """Format "{foo}" like string

    >>> format_string(None, "foo {bar}, {baz} ?", **{"bar": "qux", "baz": "quux"})
    'foo qux, quux ?'

    :param key: input item key
    :type key: str
    :param str_to_format: input item value, to be parsed
    :type str_to_format: str
    :returns: parsed value
    :rtype: str
    """
    if isinstance(str_to_format, str):
        # eodag mappings function usage, e.g. '{foo#to_bar}'
        COMPLEX_QS_REGEX = re.compile(r"^(.+=)?([^=]*)({.+})+([^=&]*)$")
        if COMPLEX_QS_REGEX.match(str_to_format) and "#" in str_to_format:
            from eodag.api.product.metadata_mapping import format_metadata

            result = format_metadata(str_to_format, **format_variables)

        else:
            # defaultdict usage will return "" for missing keys in format_args
            try:
                result = str_to_format.format_map(defaultdict(str, **format_variables))
            except TypeError:
                logger.error("Unable to format str=%s" % str_to_format)
                raise

        # try to convert string to python object
        try:
            return ast.literal_eval(result)
        except (SyntaxError, ValueError):
            return result
    else:
        return str_to_format


def parse_jsonpath(key, jsonpath_obj, **values_dict):
    """Parse jsonpah in jsonpath_obj using values_dict

    >>> import jsonpath_ng.ext as jsonpath
    >>> parse_jsonpath(None, parse("$.foo.bar"), **{"foo":{"bar":"baz"}})
    'baz'

    :param key: input item key
    :type key: str
    :param jsonpath_obj: input item value, to be parsed
    :type jsonpath_obj: str
    :param values_dict: values used as args for parsing
    :type values_dict: dict
    :returns: parsed value
    :rtype: str
    """
    if isinstance(jsonpath_obj, jsonpath.Child):
        match = jsonpath_obj.find(values_dict)
        return match[0].value if len(match) == 1 else None
    else:
        return jsonpath_obj


def nested_pairs2dict(pairs):
    """Create a dict using nested pairs

    >>> nested_pairs2dict([["foo",[["bar","baz"]]]])
    {'foo': {'bar': 'baz'}}

    :param pairs: pairs [key, value]
    :type pairs: list
    :returns: created dict
    :rtype: dict
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


def get_geometry_from_various(locations_config=[], **query_args):
    """Creates a shapely geometry using given query kwargs arguments

    :param locations_config: EODAG locations configuration
    :type locations_config: list
    :param query_args: query kwargs arguments from core.search() method
    :type query_args: dict
    :returns: shapely geometry found
    :rtype: :class:`shapely.geometry.BaseGeometry`
    :raises: :class:`ValueError`
    """
    geom = None

    if "geometry" in query_args:
        geom_arg = query_args["geometry"]

        bbox_keys = ["lonmin", "latmin", "lonmax", "latmax"]
        if isinstance(geom_arg, dict) and all(k in geom_arg for k in bbox_keys):
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
            pattern = query_locations[arg]
            attr = locations_dict[arg]["attr"]
            with shapefile.Reader(locations_dict[arg]["path"]) as shp:
                for shaperec in shp.shapeRecords():
                    if re.search(pattern, shaperec.record[attr]):
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


class MockResponse(object):
    """Fake requests response"""

    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code
        self.content = json_data

    def json(self):
        """Return json data"""
        return self.json_data


def _deprecated(reason="", version=None):
    """Simple decorator to mark functions/methods/classes as deprecated.

    Warning: Does not work with staticmethods!

    @deprecate(reason="why", versoin="1.2")
    def foo():
        pass
    foo()
    DeprecationWarning: Call to deprecated function/method foo (why) -- Deprecated since v1.2
    """

    def decorator(callable):

        if inspect.isclass(callable):
            ctype = "class"
        else:
            ctype = "function/method"
        cname = callable.__name__
        reason_ = f"({reason})" if reason else ""
        version_ = f" -- Deprecated since v{version}" if version else ""

        @functools.wraps(callable)
        def wrapper(*args, **kwargs):
            warnings.simplefilter("always", DeprecationWarning)
            warnings.warn(
                f"Call to deprecated {ctype} {cname} {reason_}{version_}",
                category=DeprecationWarning,
                stacklevel=2,
            )
            warnings.simplefilter("default", DeprecationWarning)
            return callable(*args, **kwargs)

        return wrapper

    return decorator
