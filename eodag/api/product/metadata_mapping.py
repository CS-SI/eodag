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
import ast
import logging
import re
from datetime import datetime, timedelta
from functools import partial
from string import Formatter

import geojson
import pyproj
from dateutil.parser import isoparse
from dateutil.tz import UTC, tzutc
from jsonpath_ng.jsonpath import Child, Fields, Index
from lxml import etree
from lxml.etree import XPathEvalError
from shapely import wkt
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import transform

from eodag.utils import (
    DEFAULT_PROJ,
    cached_parse,
    deepcopy,
    get_timestamp,
    items_recursive_apply,
    nested_pairs2dict,
)

logger = logging.getLogger("eodag.api.product.metadata_mapping")

SEP = r"#"
INGEST_CONVERSION_REGEX = re.compile(
    r"^{(?P<path>[^#]*)" + SEP + r"(?P<converter>[^\d\W]\w*)(\((?P<args>.*)\))*}$"
)
NOT_AVAILABLE = "Not Available"
NOT_MAPPED = "Not Mapped"
ONLINE_STATUS = "ONLINE"
STAGING_STATUS = "STAGING"
OFFLINE_STATUS = "OFFLINE"
COORDS_ROUNDING_PRECISION = 4
WKT_MAX_LEN = 1600


def get_metadata_path(map_value):
    """Return the jsonpath or xpath to the value of a EO product metadata in a provider
    search result.

    The path is retrieved depending on if the metadata is queryable (the value
    associated to it in the provider search config metadata mapping is a list) or not
    (the value is directly the string corresponding to the path).

    Assume we have the following provider config::

        provider:
            ...
            search:
                ...
                metadata_mapping:
                    productType:
                        - productType
                        - $.properties.productType
                    id: $.properties.id
                    ...
                ...
            ...

    Then the metadata `id` is not queryable for this provider meanwhile `productType`
    is queryable. The first value of the `metadata_mapping.productType` is how the
    eodag search parameter `productType` is interpreted in the
    :class:`~eodag.plugins.search.base.Search` plugin implemented by `provider`, and is
    used when eodag delegates search process to the corresponding plugin.

    :param map_value: The value originating from the definition of `metadata_mapping`
                      in the provider search config. For example, it is the list
                      `['productType', '$.properties.productType']` with the sample
                      above. Or the string `$.properties.id`.
    :type map_value: str or list(str)
    :returns: Either, None and the path to the metadata value, or a list of converter
             and its args, and the path to the metadata value.
    :rtype: tuple(list(str) or None, str)
    """
    path = get_metadata_path_value(map_value)
    try:
        match = INGEST_CONVERSION_REGEX.match(path)
    except TypeError as e:
        logger.error("Could not match regex on metadata path '%s'" % str(path))
        raise e
    if match:
        g = match.groupdict()
        return [g["converter"], g["args"]], g["path"]
    return None, path


def get_metadata_path_value(map_value):
    """Get raw metadata path without converter"""
    return map_value[1] if isinstance(map_value, list) else map_value


def get_search_param(map_value):
    """See :func:`~eodag.api.product.metadata_mapping.get_metadata_path`

    :param map_value: The value originating from the definition of `metadata_mapping`
                      in the provider search config
    :type map_value: list
    :returns: The value of the search parameter as defined in the provider config
    :rtype: str
    """
    # Assume that caller will pass in the value as a list
    return map_value[0]


def format_metadata(search_param, *args, **kwargs):
    """Format a string of form {<field_name>#<conversion_function>}

    The currently understood converters are:
        - ``datetime_to_timestamp_milliseconds``: converts a utc date string to a timestamp in
          milliseconds
        - ``to_rounded_wkt``: simplify the WKT of a geometry
        - ``to_bounds_lists``: convert to list(s) of bounds
        - ``to_nwse_bounds``: convert to North,West,South,East bounds
        - ``to_nwse_bounds_str``: convert to North,West,South,East bounds string with given separator
        - ``to_geojson``: convert to a GeoJSON (via __geo_interface__ if exists)
        - ``from_ewkt``: convert EWKT to shapely geometry / WKT in DEFAULT_PROJ
        - ``to_ewkt``: convert to EWKT (Extended Well-Known text)
        - ``from_georss``: convert GeoRSS to shapely geometry / WKT in DEFAULT_PROJ
        - ``csv_list``: convert to a comma separated list
        - ``to_iso_utc_datetime_from_milliseconds``: convert a utc timestamp in given
          milliseconds to a utc iso datetime
        - ``to_iso_utc_datetime``: convert a UTC datetime string to ISO UTC datetime
          string
        - ``to_iso_date``: remove the time part of a iso datetime string
        - ``remove_extension``: on a string that contains dots, only take the first
          part of the list obtained by splitting the string on dots
        - ``get_group_name``: get the matching regex group name
        - ``replace_str``: execute "string".replace(old, new)
        - ``recursive_sub_str``: recursively substitue in the structure (e.g. dict)
          values matching a regex
        - ``slice_str``: slice a string (equivalent to s[start, end, step])
        - ``fake_l2a_title_from_l1c``: used to generate SAFE format metadata for data from AWS
        - ``s2msil2a_title_to_aws_productinfo``: used to generate SAFE format metadata for data from AWS

    :param search_param: The string to be formatted
    :type search_param: str
    :param args: (optional) Additional arguments to use in the formatting process
    :type args: tuple
    :param kwargs: (optional) Additional named-arguments to use when formatting
    :type kwargs: Any
    :returns: The formatted string
    :rtype: str
    """

    class MetadataFormatter(Formatter):
        CONVERSION_REGEX = re.compile(
            r"^(?P<field_name>.+)"
            + SEP
            + r"(?P<converter>[^\d\W]\w*)(\((?P<args>.*)\))*$"
        )

        def __init__(self):
            self.custom_converter = None
            self.custom_args = None

        def get_field(self, field_name, args, kwargs):
            conversion_func_spec = self.CONVERSION_REGEX.match(field_name)
            # Register a custom converter if any for later use (see convert_field)
            # This is done because we don't have the value associated to field_name at
            # this stage
            if conversion_func_spec:
                field_name = conversion_func_spec.groupdict()["field_name"]
                converter = conversion_func_spec.groupdict()["converter"]
                self.custom_args = conversion_func_spec.groupdict()["args"]
                self.custom_converter = getattr(self, "convert_{}".format(converter))
            return super(MetadataFormatter, self).get_field(field_name, args, kwargs)

        def convert_field(self, value, conversion):
            # Do custom conversion if any (see get_field)
            if self.custom_converter is not None:
                if self.custom_args is not None and value is not None:
                    converted = self.custom_converter(value, self.custom_args)
                elif value is not None:
                    converted = self.custom_converter(value)
                else:
                    converted = ""
                # Clear this state variable in case the same converter is used to
                # resolve other named arguments
                self.custom_converter = None
                self.custom_args = None
                return converted
            return super(MetadataFormatter, self).convert_field(value, conversion)

        @staticmethod
        def convert_datetime_to_timestamp_milliseconds(date_time):
            """Convert a date_time (str) to a Unix timestamp in milliseconds

            "2021-04-21T18:27:19.123Z" => "1619029639123"
            "2021-04-21" => "1618963200000"
            "2021-04-21T00:00:00+02:00" => "1618956000000"
            """
            return int(1e3 * get_timestamp(date_time))

        @staticmethod
        def convert_to_iso_utc_datetime_from_milliseconds(timestamp):
            """Convert a timestamp in milliseconds (int) to its ISO8601 UTC format

            1619029639123 => "2021-04-21T18:27:19.123Z"
            """
            try:
                return (
                    datetime.fromtimestamp(timestamp / 1e3, tzutc())
                    .isoformat(timespec="milliseconds")
                    .replace("+00:00", "Z")
                )
            except TypeError:
                return timestamp

        @staticmethod
        def convert_to_iso_utc_datetime(date_time, timespec="milliseconds"):
            """Convert a date_time (str) to its ISO 8601 representation in UTC

            "2021-04-21" => "2021-04-21T00:00:00.000Z"
            "2021-04-21T00:00:00.000+02:00" => "2021-04-20T22:00:00.000Z"

            The optional argument timespec specifies the number of additional
            terms of the time to include. Valid options are 'auto', 'hours',
            'minutes', 'seconds', 'milliseconds' and 'microseconds'.
            """
            try:
                dt = isoparse(date_time)
            except ValueError:
                return date_time
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=UTC)
            elif dt.tzinfo is not UTC:
                dt = dt.astimezone(UTC)
            return dt.isoformat(timespec=timespec).replace("+00:00", "Z")

        @staticmethod
        def convert_to_iso_date(datetime_string, time_delta_args_str="0,0,0,0,0,0,0"):
            """Convert an ISO8601 datetime (str) to its ISO8601 date format

            "2021-04-21T18:27:19.123Z" => "2021-04-21"
            "2021-04-21" => "2021-04-21"
            "2021-04-21T00:00:00+06:00" => "2021-04-20" !
            """
            dt = isoparse(datetime_string)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=UTC)
            elif dt.tzinfo is not UTC:
                dt = dt.astimezone(UTC)
            time_delta_args = ast.literal_eval(time_delta_args_str)
            dt += timedelta(*time_delta_args)
            return dt.isoformat()[:10]

        @staticmethod
        def convert_to_rounded_wkt(value):
            wkt_value = wkt.dumps(value, rounding_precision=COORDS_ROUNDING_PRECISION)
            # If needed, simplify WKT to prevent too long request failure
            tolerance = 0.1
            while len(wkt_value) > WKT_MAX_LEN and tolerance <= 1:
                logger.debug(
                    "Geometry WKT is too long (%s), trying to simplify it with tolerance %s",
                    len(wkt_value),
                    tolerance,
                )
                wkt_value = wkt.dumps(
                    value.simplify(tolerance),
                    rounding_precision=COORDS_ROUNDING_PRECISION,
                )
                tolerance += 0.1
            if len(wkt_value) > WKT_MAX_LEN and tolerance > 1:
                logger.warning("Failed to reduce WKT length lower than %s", WKT_MAX_LEN)
            return wkt_value

        @staticmethod
        def convert_to_bounds_lists(input_geom):
            if isinstance(input_geom, MultiPolygon):
                geoms = [geom for geom in input_geom.geoms]
                # sort with larger one at first (stac-browser only plots first one)
                geoms.sort(key=lambda x: x.area, reverse=True)
                return [list(x.bounds[0:4]) for x in geoms]
            else:
                return [list(input_geom.bounds[0:4])]

        @staticmethod
        def convert_to_nwse_bounds(input_geom):
            return list(input_geom.bounds[-1:] + input_geom.bounds[:-1])

        @staticmethod
        def convert_to_nwse_bounds_str(input_geom, separator=","):
            return separator.join(
                str(x) for x in MetadataFormatter.convert_to_nwse_bounds(input_geom)
            )

        @staticmethod
        def convert_to_geojson(string):
            return geojson.dumps(string)

        @staticmethod
        def convert_from_ewkt(ewkt_string):
            """Convert EWKT (Extended Well-Known text) to shapely geometry"""

            ewkt_regex = re.compile(r"^(?P<proj>[A-Za-z]+=[0-9]+);(?P<wkt>.*)$")
            ewkt_match = ewkt_regex.match(ewkt_string)
            if ewkt_match:
                g = ewkt_match.groupdict()
                from_proj = g["proj"].replace("SRID", "EPSG").replace("=", ":")
                input_geom = wkt.loads(g["wkt"])

                from_proj = pyproj.Proj(from_proj)
                to_proj = pyproj.Proj(DEFAULT_PROJ)

                if from_proj != to_proj:
                    # reproject
                    project = partial(pyproj.transform, from_proj, to_proj)
                    return transform(project, input_geom)
                else:
                    return input_geom
            else:
                logger.warning(f"Could not read {ewkt_string} as EWKT")
                return ewkt_string

        @staticmethod
        def convert_to_ewkt(input_geom):
            """Convert shapely geometry to EWKT (Extended Well-Known text)"""

            proj = DEFAULT_PROJ.upper().replace("EPSG", "SRID").replace(":", "=")
            wkt_geom = MetadataFormatter.convert_to_rounded_wkt(input_geom)

            return f"{proj};{wkt_geom}"

        @staticmethod
        def convert_from_georss(georss):
            """Convert GeoRSS to shapely geometry"""

            if "polygon" in georss.tag:
                # Polygon
                coords_list = georss.text.split()
                polygon_args = [
                    (float(coords_list[2 * i]), float(coords_list[2 * i + 1]))
                    for i in range(int(len(coords_list) / 2))
                ]
                return Polygon(polygon_args)
            elif len(georss) == 1 and "multisurface" in georss[0].tag.lower():
                # Multipolygon
                from_proj = getattr(georss[0], "attrib", {}).get("srsName", None)
                if from_proj:
                    from_proj = pyproj.Proj(from_proj)
                    to_proj = pyproj.Proj(DEFAULT_PROJ)
                    project = partial(pyproj.transform, from_proj, to_proj)

                # function to get deepest elements
                def flatten_elements(nested):

                    for e in nested:
                        if len(e) > 0:
                            yield from flatten_elements(e)
                        else:
                            yield e

                polygons_list = []
                for elem in flatten_elements(georss[0]):
                    coords_list = elem.text.split()
                    polygon_args = [
                        (float(coords_list[2 * i]), float(coords_list[2 * i + 1]))
                        for i in range(int(len(coords_list) / 2))
                    ]
                    polygon = Polygon(polygon_args)
                    # reproject if needed
                    if from_proj and from_proj != to_proj:
                        polygons_list.append(transform(project, polygon))
                    else:
                        polygons_list.append(polygon)

                return MultiPolygon(polygons_list)

            else:
                logger.warning(
                    f"Incoming GeoRSS format not supported yet: {str(georss)}"
                )
                return georss

        @staticmethod
        def convert_csv_list(values_list):
            if isinstance(values_list, list):
                return ",".join([str(x) for x in values_list])
            else:
                return values_list

        @staticmethod
        def convert_remove_extension(string):
            parts = string.split(".")
            if parts:
                return parts[0]
            return ""

        @staticmethod
        def convert_get_group_name(string, pattern):
            try:
                return re.search(pattern, str(string)).lastgroup
            except AttributeError:
                logger.warning(
                    "Could not extract property from %s using %s", string, pattern
                )
                return NOT_AVAILABLE

        @staticmethod
        def convert_replace_str(string, args):
            old, new = ast.literal_eval(args)
            return re.sub(old, new, string)

        @staticmethod
        def convert_recursive_sub_str(input_obj, args):
            old, new = ast.literal_eval(args)
            return items_recursive_apply(
                input_obj,
                lambda k, v, x, y: re.sub(x, y, v) if isinstance(v, str) else v,
                **{"x": old, "y": new},
            )

        @staticmethod
        def convert_dict_update(input_dict, args):
            """Converts"""
            new_items_list = ast.literal_eval(args)

            new_items_dict = nested_pairs2dict(new_items_list)

            return dict(input_dict, **new_items_dict)

        @staticmethod
        def convert_slice_str(string, args):
            cmin, cmax, cstep = [x.strip() for x in args.split(",")]
            return string[int(cmin) : int(cmax) : int(cstep)]

        @staticmethod
        def convert_fake_l2a_title_from_l1c(string):
            id_regex = re.compile(
                r"^(?P<id1>\w+)_(?P<id2>\w+)_(?P<id3>\w+)_(?P<id4>\w+)_(?P<id5>\w+)_(?P<id6>\w+)_(?P<id7>\w+)$"
            )
            id_match = id_regex.match(string)
            if id_match:
                id_dict = id_match.groupdict()
                return "%s_MSIL2A_%s____________%s________________" % (
                    id_dict["id1"],
                    id_dict["id3"],
                    id_dict["id6"],
                )
            else:
                logger.error("Could not extract fake title from %s" % string)
                return NOT_AVAILABLE

        @staticmethod
        def convert_s2msil2a_title_to_aws_productinfo(string):
            id_regex = re.compile(
                r"^(?P<id1>\w+)_(?P<id2>\w+)_(?P<year>[0-9]{4})(?P<month>[0-9]{2})(?P<day>[0-9]{2})T[0-9]+_"
                + r"(?P<id4>[A-Z0-9_]+)_(?P<id5>[A-Z0-9_]+)_T(?P<tile1>[0-9]{2})(?P<tile2>[A-Z])(?P<tile3>[A-Z]{2})_"
                + r"(?P<id7>[A-Z0-9_]+)$"
            )
            id_match = id_regex.match(string)
            if id_match:
                id_dict = id_match.groupdict()
                return (
                    "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/%s/%s/%s/%s/%s/%s/0/{collection}.json"
                    % (
                        id_dict["tile1"],
                        id_dict["tile2"],
                        id_dict["tile3"],
                        id_dict["year"],
                        int(id_dict["month"]),
                        int(id_dict["day"]),
                    )
                )
            else:
                logger.error("Could not extract title infos from %s" % string)
                return NOT_AVAILABLE

    # if stac extension colon separator `:` is in search search params, parse it to prevent issues with vformat
    if re.search(r"{[a-zA-Z0-9_-]*:[a-zA-Z0-9_-]*}", search_param):
        search_param = re.sub(
            r"{([a-zA-Z0-9_-]*):([a-zA-Z0-9_-]*)}", r"{\1_COLON_\2}", search_param
        )
        kwargs = {k.replace(":", "_COLON_"): v for k, v in kwargs.items()}

    return MetadataFormatter().vformat(search_param, args, kwargs)


def properties_from_json(json, mapping, discovery_config=None):
    """Extract properties from a provider json result.

    :param json: The representation of a provider result as a json object
    :type json: dict
    :param mapping: A mapping between :class:`~eodag.api.product._product.EOProduct`'s metadata
                    keys and the location of the values of these properties in the json
                    representation, expressed as a
                    `jsonpath <http://goessner.net/articles/JsonPath/>`_
    :param discovery_config: (optional) metadata discovery configuration dict, accepting among other items
                             `discovery_pattern` (Regex pattern for metadata key discovery, e.g. "^[a-zA-Z]+$"),
                             `discovery_path` (String representation of jsonpath)
    :type discovery_config: dict
    :returns: The metadata of the :class:`~eodag.api.product._product.EOProduct`
    :rtype: dict
    """
    properties = {}
    templates = {}
    used_jsonpaths = []
    for metadata, value in mapping.items():
        # Treat the case when the value is from a queryable metadata
        if isinstance(value, list):
            conversion_or_none, path_or_text = value[1]
        else:
            conversion_or_none, path_or_text = value
        if isinstance(path_or_text, str):
            if re.search(r"({[^{}]+})+", path_or_text):
                templates[metadata] = path_or_text
            else:
                properties[metadata] = path_or_text
        else:
            match = path_or_text.find(json)
            if len(match) == 1:
                extracted_value = match[0].value
                used_jsonpaths.append(match[0].full_path)
            else:
                extracted_value = NOT_AVAILABLE
            if extracted_value is None:
                properties[metadata] = None
            else:
                if conversion_or_none is None:
                    properties[metadata] = extracted_value
                else:
                    # reformat conversion_or_none as metadata#converter(args) or metadata#converter
                    if (
                        len(conversion_or_none) > 1
                        and isinstance(conversion_or_none, list)
                        and conversion_or_none[1] is not None
                    ):
                        conversion_or_none = "%s(%s)" % (
                            conversion_or_none[0],
                            conversion_or_none[1],
                        )
                    elif isinstance(conversion_or_none, list):
                        conversion_or_none = conversion_or_none[0]

                    # check if conversion uses variables to format
                    if re.search(r"({[^{}]+})+", conversion_or_none):
                        conversion_or_none = conversion_or_none.format(**properties)

                    properties[metadata] = format_metadata(
                        "{%s%s%s}" % (metadata, SEP, conversion_or_none),
                        **{metadata: extracted_value},
                    )
        # properties as python objects when possible (format_metadata returns only strings)
        try:
            properties[metadata] = ast.literal_eval(properties[metadata])
        except Exception:
            pass

    # Resolve templates
    for metadata, template in templates.items():
        try:
            properties[metadata] = template.format(**properties)
        except ValueError:
            logger.warning(
                f"Could not parse {metadata} ({template}) using product properties"
            )
            logger.debug(f"available properties: {properties}")
            properties[metadata] = NOT_AVAILABLE

    # adds missing discovered properties
    if not discovery_config:
        discovery_config = {}
    discovery_pattern = discovery_config.get("metadata_pattern", None)
    discovery_path = discovery_config.get("metadata_path", None)
    if discovery_pattern and discovery_path:
        discovered_properties = cached_parse(discovery_path).find(json)
        for found_jsonpath in discovered_properties:
            if "metadata_path_id" in discovery_config.keys():
                found_key_paths = cached_parse(
                    discovery_config["metadata_path_id"]
                ).find(found_jsonpath.value)
                if not found_key_paths:
                    continue
                found_key = found_key_paths[0].value
                used_jsonpath = Child(
                    found_jsonpath.full_path,
                    cached_parse(discovery_config["metadata_path_value"]),
                )
            else:
                # default key got from metadata_path
                found_key = found_jsonpath.path.fields[-1]
                used_jsonpath = found_jsonpath.full_path
            if (
                re.compile(discovery_pattern).match(found_key)
                and found_key not in properties.keys()
                and used_jsonpath not in used_jsonpaths
            ):
                if "metadata_path_value" in discovery_config.keys():
                    found_value_path = cached_parse(
                        discovery_config["metadata_path_value"]
                    ).find(found_jsonpath.value)
                    properties[found_key] = (
                        found_value_path[0].value if found_value_path else NOT_AVAILABLE
                    )
                else:
                    # default value got from metadata_path
                    properties[found_key] = found_jsonpath.value

                # properties as python objects when possible (format_metadata returns only strings)
                try:
                    properties[found_key] = ast.literal_eval(properties[found_key])
                except Exception:
                    pass

    return properties


def properties_from_xml(
    xml_as_text,
    mapping,
    empty_ns_prefix="ns",
    discovery_config=None,
):
    """Extract properties from a provider xml result.

    :param xml_as_text: The representation of a provider result as xml
    :type xml_as_text: str
    :param mapping: A mapping between :class:`~eodag.api.product._product.EOProduct`'s metadata
                    keys and the location of the values of these properties in the xml
                    representation, expressed as a
                    `xpath <https://www.w3schools.com/xml/xml_xpath.asp>`_
    :param empty_ns_prefix: (optional) The name to give to the default namespace of `xml_as_text`.
                            This is a technical workaround for the limitation of lxml
                            not supporting empty namespace prefix. The
                            xpath in `mapping` must use this value to be able to
                            correctly reach empty-namespace prefixed elements
    :type empty_ns_prefix: str
    :param discovery_config: (optional) metadata discovery configuration dict, accepting among other items
                             `discovery_pattern` (Regex pattern for metadata key discovery, e.g. "^[a-zA-Z]+$"),
                             `discovery_path` (String representation of xpath)
    :type discovery_config: dict
    :returns: the metadata of the :class:`~eodag.api.product._product.EOProduct`
    :rtype: dict
    """
    properties = {}
    templates = {}
    used_xpaths = []
    root = etree.XML(xml_as_text)
    for metadata, value in mapping.items():
        # Treat the case when the value is from a queryable metadata
        if isinstance(value, list):
            conversion_or_none, path_or_text = value[1]
        else:
            conversion_or_none, path_or_text = value
        try:
            extracted_value = root.xpath(
                path_or_text,
                namespaces={k or empty_ns_prefix: v for k, v in root.nsmap.items()},
            )
            if len(extracted_value) == 1:
                if conversion_or_none is None:
                    properties[metadata] = extracted_value[0]
                else:
                    # reformat conversion_or_none as metadata#converter(args) or metadata#converter
                    if (
                        len(conversion_or_none) > 1
                        and isinstance(conversion_or_none, list)
                        and conversion_or_none[1] is not None
                    ):
                        conversion_or_none = "%s(%s)" % (
                            conversion_or_none[0],
                            conversion_or_none[1],
                        )
                    elif isinstance(conversion_or_none, list):
                        conversion_or_none = conversion_or_none[0]
                    properties[metadata] = format_metadata(
                        "{%s%s%s}" % (metadata, SEP, conversion_or_none),
                        **{metadata: extracted_value[0]},
                    )
                # store element tag in used_xpaths
                used_xpaths.append(
                    getattr(
                        root.xpath(
                            path_or_text.replace("/text()", ""),
                            namespaces={
                                k or empty_ns_prefix: v for k, v in root.nsmap.items()
                            },
                        )[0],
                        "tag",
                        None,
                    )
                )
            # If there are multiple matches, consider the result as a list, doing a
            # formatting if any
            elif len(extracted_value) > 1:
                if conversion_or_none is None:
                    properties[metadata] = extracted_value
                else:
                    # reformat conversion_or_none as metadata#converter(args) or metadata#converter
                    if (
                        len(conversion_or_none) > 1
                        and isinstance(conversion_or_none, list)
                        and conversion_or_none[1] is not None
                    ):
                        conversion_or_none = "%s(%s)" % (
                            conversion_or_none[0],
                            conversion_or_none[1],
                        )
                    elif isinstance(conversion_or_none, list):
                        conversion_or_none = conversion_or_none[0]

                    # check if conversion uses variables to format
                    if re.search(r"({[^{}]+})+", conversion_or_none):
                        conversion_or_none = conversion_or_none.format(**properties)

                    properties[metadata] = [
                        format_metadata(
                            "{%s%s%s}"
                            % (
                                metadata,
                                SEP,
                                conversion_or_none,
                            ),  # Re-build conversion format identifier
                            **{metadata: extracted_value_item},
                        )
                        for extracted_value_item in extracted_value
                    ]
            # If there is no matched value (empty list), mark the metadata as not
            # available
            else:
                properties[metadata] = NOT_AVAILABLE
        except XPathEvalError:
            # Assume the mapping is to be passed as is, in which case we readily
            # register it, or is a template, in which case we register it for later
            # formatting resolution using previously successfully resolved properties
            # Ignore any transformation specified. If a value is to be passed as is,
            # we don't want to transform it further
            if re.search(r"({[^{}]+})+", path_or_text):
                templates[metadata] = path_or_text
            else:
                properties[metadata] = path_or_text
    # Resolve templates
    for metadata, template in templates.items():
        properties[metadata] = template.format(**properties)

    # adds missing discovered properties
    if not discovery_config:
        discovery_config = {}
    discovery_pattern = discovery_config.get("metadata_pattern", None)
    discovery_path = discovery_config.get("metadata_path", None)
    if discovery_pattern and discovery_path:
        # discovered_properties = discovery_path.find(json)
        discovered_properties = root.xpath(
            discovery_path,
            namespaces={k or empty_ns_prefix: v for k, v in root.nsmap.items()},
        )
        for found_xpath in discovered_properties:
            found_key = found_xpath.tag.rpartition("}")[-1]
            if (
                re.compile(discovery_pattern).match(found_key)
                and found_key not in properties.keys()
                and found_xpath.tag not in used_xpaths
            ):
                properties[found_key] = found_xpath.text

    return properties


def mtd_cfg_as_jsonpath(
    src_dict, dest_dict={}, common_jsonpath=None, keep_conversion=True
):
    """Metadata configuration dictionary to jsonpath objects dictionnay
    Transform every src_dict value from jsonpath str to jsonpath object

    :param src_dict: Input dict containing jsonpath str as values
    :type src_dict: dict
    :param dest_dict: (optional) Output dict containing jsonpath objects as values
    :type dest_dict: dict
    :param common_jsonpath: (optional) common jsonpath used optimize jsonpath build process
    :type common_jsonpath: str
    :param keep_conversion: (optional) whether to keep conversion on parse error or not
    :type keep_conversion: bool
    :returns: dest_dict
    :rtype: dict
    """
    if common_jsonpath:
        common_jsonpath_parsed = cached_parse(common_jsonpath)
        common_jsonpath_match = re.compile(
            rf"^{re.escape(common_jsonpath)}\.[a-zA-Z0-9-_:\.\[\]\"]+$"
        )
        array_field_match = re.compile(r"^[a-zA-Z0-9-_:]+\[[0-9]+\]$")
    else:
        common_jsonpath_match = None
    if not dest_dict:
        dest_dict = deepcopy(src_dict)
    for metadata in src_dict:
        if metadata not in dest_dict:
            dest_dict[metadata] = (None, NOT_MAPPED)
        else:
            conversion, path = get_metadata_path(dest_dict[metadata])
            try:
                # combine with common jsonpath if possible
                if common_jsonpath_match and common_jsonpath_match.match(path):
                    path_suffix = path[len(common_jsonpath) + 1 :]
                    path_splits = path_suffix.split(".")
                    parsed_path = common_jsonpath_parsed
                    for path_split in path_splits:
                        path_split = path_split.strip("'").strip('"')
                        if "[" in path_split and array_field_match.match(path_split):
                            # simple array field
                            indexed_path, index = path_split[:-1].split("[")
                            index = int(index)
                            parsed_path = Child(
                                Child(parsed_path, Fields(indexed_path)),
                                Index(index=index),
                            )
                            continue
                        elif "[" in path_split:
                            # nested array field
                            parsed_path = cached_parse(path)
                            break
                        else:
                            parsed_path = Child(parsed_path, Fields(path_split))
                else:
                    parsed_path = cached_parse(path)
                # If the metadata is queryable (i.e a list of 2 elements), replace the value of the last item
                if len(dest_dict[metadata]) == 2:
                    dest_dict[metadata][1] = (conversion, parsed_path)
                else:
                    dest_dict[metadata] = (conversion, parsed_path)
            except Exception:  # jsonpath_ng does not provide a proper exception
                # Keep path as this and its associated conversion (or None if not keep_conversion)
                if not keep_conversion:
                    conversion = None
                if len(dest_dict[metadata]) == 2:
                    dest_dict[metadata][1] = (conversion, path)
                else:
                    dest_dict[metadata] = (conversion, path)

            # Put the updated mapping at the end
            dest_dict[metadata] = dest_dict.pop(metadata)

    return dest_dict


# Keys taken from OpenSearch extension for Earth Observation http://docs.opengeospatial.org/is/13-026r9/13-026r9.html
# For a metadata to be queryable, The way to query it must be specified in the
# provider metadata_mapping configuration parameter. It will be automatically
# detected as queryable by eodag when this is done
OSEO_METADATA_MAPPING = {
    # Opensearch resource identifier within the search engine context (in our case
    # within the context of the data provider)
    "uid": "$.uid",
    # OpenSearch Parameters for Collection Search (Table 3)
    "productType": "$.properties.productType",
    "doi": "$.properties.doi",
    "platform": "$.properties.platform",
    "platformSerialIdentifier": "$.properties.platformSerialIdentifier",
    "instrument": "$.properties.instrument",
    "sensorType": "$.properties.sensorType",
    "compositeType": "$.properties.compositeType",
    "processingLevel": "$.properties.processingLevel",
    "orbitType": "$.properties.orbitType",
    "spectralRange": "$.properties.spectralRange",
    "wavelengths": "$.properties.wavelengths",
    "hasSecurityConstraints": "$.properties.hasSecurityConstraints",
    "dissemination": "$.properties.dissemination",
    # INSPIRE obligated OpenSearch Parameters for Collection Search (Table 4)
    "title": "$.properties.title",
    "topicCategory": "$.properties.topicCategory",
    "keyword": "$.properties.keyword",
    "abstract": "$.properties.abstract",
    "resolution": "$.properties.resolution",
    "organisationName": "$.properties.organisationName",
    "organisationRole": "$.properties.organisationRole",
    "publicationDate": "$.properties.publicationDate",
    "lineage": "$.properties.lineage",
    "useLimitation": "$.properties.useLimitation",
    "accessConstraint": "$.properties.accessConstraint",
    "otherConstraint": "$.properties.otherConstraint",
    "classification": "$.properties.classification",
    "language": "$.properties.language",
    "specification": "$.properties.specification",
    # OpenSearch Parameters for Product Search (Table 5)
    "parentIdentifier": "$.properties.parentIdentifier",
    "productionStatus": "$.properties.productionStatus",
    "acquisitionType": "$.properties.acquisitionType",
    "orbitNumber": "$.properties.orbitNumber",
    "orbitDirection": "$.properties.orbitDirection",
    "track": "$.properties.track",
    "frame": "$.properties.frame",
    "swathIdentifier": "$.properties.swathIdentifier",
    "cloudCover": "$.properties.cloudCover",
    "snowCover": "$.properties.snowCover",
    "lowestLocation": "$.properties.lowestLocation",
    "highestLocation": "$.properties.highestLocation",
    "productVersion": "$.properties.productVersion",
    "productQualityStatus": "$.properties.productQualityStatus",
    "productQualityDegradationTag": "$.properties.productQualityDegradationTag",
    "processorName": "$.properties.processorName",
    "processingCenter": "$.properties.processingCenter",
    "creationDate": "$.properties.creationDate",
    "modificationDate": "$.properties.modificationDate",
    "processingDate": "$.properties.processingDate",
    "sensorMode": "$.properties.sensorMode",
    "archivingCenter": "$.properties.archivingCenter",
    "processingMode": "$.properties.processingMode",
    # OpenSearch Parameters for Acquistion Parameters Search (Table 6)
    "availabilityTime": "$.properties.availabilityTime",
    "acquisitionStation": "$.properties.acquisitionStation",
    "acquisitionSubType": "$.properties.acquisitionSubType",
    "startTimeFromAscendingNode": "$.properties.startTimeFromAscendingNode",
    "completionTimeFromAscendingNode": "$.properties.completionTimeFromAscendingNode",
    "illuminationAzimuthAngle": "$.properties.illuminationAzimuthAngle",
    "illuminationZenithAngle": "$.properties.illuminationZenithAngle",
    "illuminationElevationAngle": "$.properties.illuminationElevationAngle",
    "polarizationMode": "$.properties.polarizationMode",
    "polarizationChannels": "$.properties.polarizationChannels",
    "antennaLookDirection": "$.properties.antennaLookDirection",
    "minimumIncidenceAngle": "$.properties.minimumIncidenceAngle",
    "maximumIncidenceAngle": "$.properties.maximumIncidenceAngle",
    "dopplerFrequency": "$.properties.dopplerFrequency",
    "incidenceAngleVariation": "$.properties.incidenceAngleVariation",
}
DEFAULT_METADATA_MAPPING = dict(
    OSEO_METADATA_MAPPING,
    **{
        # Custom parameters (not defined in the base document referenced above)
        # id differs from uid. The id is an identifier by which a product which is
        # distributed by many providers can be retrieved (a property that it has in common
        # in the catalogues of all the providers on which it is referenced)
        "id": "$.id",
        # The geographic extent of the product
        "geometry": "$.geometry",
        # The url of the quicklook
        "quicklook": "$.properties.quicklook",
        # The url to download the product "as is" (literal or as a template to be completed
        # either after the search result is obtained from the provider or during the eodag
        # download phase)
        "downloadLink": "$.properties.downloadLink",
    },
)
