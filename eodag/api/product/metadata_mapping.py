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
from __future__ import annotations

import ast
import json
import logging
import re
from datetime import datetime, timedelta
from string import Formatter
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

import geojson
import orjson
import pyproj
from dateutil.parser import isoparse
from dateutil.tz import UTC, tzutc
from jsonpath_ng.jsonpath import Child
from lxml import etree
from lxml.etree import XPathEvalError
from shapely import wkt
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import transform

from eodag.utils import (
    DEFAULT_PROJ,
    deepcopy,
    dict_items_recursive_apply,
    get_geometry_from_various,
    get_timestamp,
    items_recursive_apply,
    nested_pairs2dict,
    string_to_jsonpath,
    update_nested_dict,
)

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.product.metadata_mapping")

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
COMPLEX_QS_REGEX = re.compile(r"^(.+=)?([^=]*)({.+})+([^=&]*)$")


def get_metadata_path(
    map_value: Union[str, List[str]]
) -> Tuple[Union[List[str], None], str]:
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


def get_metadata_path_value(map_value: Union[str, List[str]]) -> str:
    """Get raw metadata path without converter"""
    return map_value[1] if isinstance(map_value, list) else map_value


def get_search_param(map_value: List[str]) -> str:
    """See :func:`~eodag.api.product.metadata_mapping.get_metadata_path`

    :param map_value: The value originating from the definition of `metadata_mapping`
                      in the provider search config
    :type map_value: list
    :returns: The value of the search parameter as defined in the provider config
    :rtype: str
    """
    # Assume that caller will pass in the value as a list
    return map_value[0]


def format_metadata(search_param: str, *args: Tuple[Any], **kwargs: Any) -> str:
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
        - ``split_cop_dem_id``: get the bbox by splitting the product id
        - ``split_corine_id``: get the product type by splitting the product id
        - ``to_datetime_dict``: convert a datetime string to a dictionary where values are either a string or a list
        - ``get_ecmwf_time``: get the time of a datetime string in the ECMWF format

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

        def __init__(self) -> None:
            self.custom_converter = None
            self.custom_args = None

        def get_field(self, field_name: str, args: Any, kwargs: Any) -> Any:
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

        def convert_field(self, value: Any, conversion: Any) -> Any:
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
        def convert_datetime_to_timestamp_milliseconds(date_time: str) -> int:
            """Convert a date_time (str) to a Unix timestamp in milliseconds

            "2021-04-21T18:27:19.123Z" => "1619029639123"
            "2021-04-21" => "1618963200000"
            "2021-04-21T00:00:00+02:00" => "1618956000000"
            """
            return int(1e3 * get_timestamp(date_time))

        @staticmethod
        def convert_to_iso_utc_datetime_from_milliseconds(
            timestamp: int,
        ) -> Union[str, int]:
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
        def convert_to_iso_utc_datetime(
            date_time: str, timespec: str = "milliseconds"
        ) -> str:
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
        def convert_to_iso_date(
            datetime_string: str, time_delta_args_str: str = "0,0,0,0,0,0,0"
        ) -> str:
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
        def convert_to_rounded_wkt(value: BaseGeometry) -> str:
            wkt_value = cast(
                str, wkt.dumps(value, rounding_precision=COORDS_ROUNDING_PRECISION)
            )
            # If needed, simplify WKT to prevent too long request failure
            tolerance = 0.1
            while len(wkt_value) > WKT_MAX_LEN and tolerance <= 1:
                logger.debug(
                    "Geometry WKT is too long (%s), trying to simplify it with tolerance %s",
                    len(wkt_value),
                    tolerance,
                )
                wkt_value = cast(
                    str,
                    wkt.dumps(
                        value.simplify(tolerance),
                        rounding_precision=COORDS_ROUNDING_PRECISION,
                    ),
                )
                tolerance += 0.1
            if len(wkt_value) > WKT_MAX_LEN and tolerance > 1:
                logger.warning("Failed to reduce WKT length lower than %s", WKT_MAX_LEN)
            return wkt_value

        @staticmethod
        def convert_to_bounds_lists(input_geom: BaseGeometry) -> List[List[float]]:
            if isinstance(input_geom, MultiPolygon):
                geoms = [geom for geom in input_geom.geoms]
                # sort with larger one at first (stac-browser only plots first one)
                geoms.sort(key=lambda x: x.area, reverse=True)
                return [list(x.bounds[0:4]) for x in geoms]
            else:
                return [list(input_geom.bounds[0:4])]

        @staticmethod
        def convert_to_bounds(input_geom_unformatted: Any) -> List[float]:
            input_geom = get_geometry_from_various(geometry=input_geom_unformatted)
            if isinstance(input_geom, MultiPolygon):
                geoms = [geom for geom in input_geom.geoms]
                # sort with larger one at first (stac-browser only plots first one)
                geoms.sort(key=lambda x: x.area, reverse=True)
                min_lon = 180
                min_lat = 90
                max_lon = -180
                max_lat = -90
                for geom in geoms:
                    min_lon = min(min_lon, geom.bound[0])
                    min_lat = min(min_lat, geom.bound[1])
                    max_lon = max(max_lon, geom.bound[2])
                    max_lat = max(max_lat, geom.bound[3])
                return [min_lon, min_lat, max_lon, max_lat]
            else:
                return list(input_geom.bounds[0:4])

        @staticmethod
        def convert_to_nwse_bounds(input_geom: BaseGeometry) -> List[float]:
            return list(input_geom.bounds[-1:] + input_geom.bounds[:-1])

        @staticmethod
        def convert_to_nwse_bounds_str(
            input_geom: BaseGeometry, separator: str = ","
        ) -> str:
            return separator.join(
                str(x) for x in MetadataFormatter.convert_to_nwse_bounds(input_geom)
            )

        @staticmethod
        def convert_to_geojson(string: str) -> str:
            return geojson.dumps(string)

        @staticmethod
        def convert_from_ewkt(ewkt_string: str) -> Union[BaseGeometry, str]:
            """Convert EWKT (Extended Well-Known text) to shapely geometry"""

            ewkt_regex = re.compile(r"^(?P<proj>[A-Za-z]+=[0-9]+);(?P<wkt>.*)$")
            ewkt_match = ewkt_regex.match(ewkt_string)
            if ewkt_match:
                g = ewkt_match.groupdict()
                from_proj = g["proj"].replace("SRID", "EPSG").replace("=", ":")
                input_geom = wkt.loads(g["wkt"])

                from_proj = pyproj.CRS(from_proj)
                to_proj = pyproj.CRS(DEFAULT_PROJ)

                if from_proj != to_proj:
                    # reproject
                    project = pyproj.Transformer.from_crs(
                        from_proj, to_proj, always_xy=True
                    ).transform
                    return transform(project, input_geom)
                else:
                    return input_geom
            else:
                logger.warning(f"Could not read {ewkt_string} as EWKT")
                return ewkt_string

        @staticmethod
        def convert_to_ewkt(input_geom: BaseGeometry) -> str:
            """Convert shapely geometry to EWKT (Extended Well-Known text)"""

            proj = DEFAULT_PROJ.upper().replace("EPSG", "SRID").replace(":", "=")
            wkt_geom = MetadataFormatter.convert_to_rounded_wkt(input_geom)

            return f"{proj};{wkt_geom}"

        @staticmethod
        def convert_from_georss(georss: Any) -> Union[BaseGeometry, Any]:
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
                    from_proj = pyproj.CRS(from_proj)
                    to_proj = pyproj.CRS(DEFAULT_PROJ)
                    project = pyproj.Transformer.from_crs(
                        from_proj, to_proj, always_xy=True
                    ).transform

                # function to get deepest elements
                def flatten_elements(nested) -> Iterator[Any]:
                    for e in nested:
                        if len(e) > 0:
                            yield from flatten_elements(e)
                        else:
                            yield e

                polygons_list: List[Polygon] = []
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
        def convert_csv_list(values_list: Any) -> Any:
            if isinstance(values_list, list):
                return ",".join([str(x) for x in values_list])
            else:
                return values_list

        @staticmethod
        def convert_remove_extension(string: str) -> str:
            parts = string.split(".")
            if parts:
                return parts[0]
            return ""

        @staticmethod
        def convert_get_group_name(string: str, pattern: str) -> str:
            try:
                return re.search(pattern, str(string)).lastgroup
            except AttributeError:
                logger.warning(
                    "Could not extract property from %s using %s", string, pattern
                )
                return NOT_AVAILABLE

        @staticmethod
        def convert_replace_str(string: str, args: str) -> str:
            old, new = ast.literal_eval(args)
            return re.sub(old, new, string)

        @staticmethod
        def convert_recursive_sub_str(
            input_obj: Union[Dict[Any, Any], List[Any]], args: str
        ) -> Union[Dict[Any, Any], List[Any]]:
            old, new = ast.literal_eval(args)
            return items_recursive_apply(
                input_obj,
                lambda k, v, x, y: re.sub(x, y, v) if isinstance(v, str) else v,
                **{"x": old, "y": new},
            )

        @staticmethod
        def convert_dict_update(
            input_dict: Dict[Any, Any], args: str
        ) -> Dict[Any, Any]:
            """Converts"""
            new_items_list = ast.literal_eval(args)

            new_items_dict = nested_pairs2dict(new_items_list)

            return dict(input_dict, **new_items_dict)

        @staticmethod
        def convert_slice_str(string: str, args: str) -> str:
            cmin, cmax, cstep = [x.strip() for x in args.split(",")]
            return string[int(cmin) : int(cmax) : int(cstep)]

        @staticmethod
        def convert_fake_l2a_title_from_l1c(string: str) -> str:
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
        def convert_s2msil2a_title_to_aws_productinfo(string: str) -> str:
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

        @staticmethod
        def convert_split_id_into_s1_params(product_id: str) -> Dict[str, str]:
            parts: List[str] = re.split(r"_(?!_)", product_id)
            if len(parts) < 9:
                logger.error(
                    "id %s does not match expected Sentinel-1 id format", product_id
                )
                raise ValueError
            params = {"sensorMode": parts[1]}
            level = "LEVEL" + parts[3][0]
            params["processingLevel"] = level
            start_date = datetime.strptime(parts[4], "%Y%m%dT%H%M%S") - timedelta(
                seconds=1
            )
            params["startDate"] = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_date = datetime.strptime(parts[5], "%Y%m%dT%H%M%S") + timedelta(
                seconds=1
            )
            params["endDate"] = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            product_type = parts[2][:3]
            if product_type == "GRD" and parts[-1] == "COG":
                product_type = "GRD-COG"
            elif product_type == "GRD" and parts[-2] == "CARD" and parts[-1] == "BS":
                product_type = "CARD-BS"
            params["productType"] = product_type
            polarisation_mapping = {
                "SV": "VV",
                "SH": "HH",
                "DH": "HH+HV",
                "DV": "VV+VH",
            }
            polarisation = polarisation_mapping[parts[3][2:]]
            params["polarisation"] = polarisation
            return params

        @staticmethod
        def convert_get_processing_level_from_s1_id(product_id: str) -> str:
            parts: List[str] = re.split(r"_(?!_)", product_id)
            level = "LEVEL" + parts[3][0]
            return level

        @staticmethod
        def convert_get_sensor_mode_from_s1_id(product_id: str) -> str:
            parts: List[str] = re.split(r"_(?!_)", product_id)
            return parts[1]

        @staticmethod
        def convert_get_processing_level_from_s2_id(product_id: str) -> str:
            parts: List[str] = re.split(r"_(?!_)", product_id)
            processing_level = "S2" + parts[1]
            return processing_level

        @staticmethod
        def convert_split_id_into_s3_params(product_id: str) -> Dict[str, str]:
            parts: List[str] = re.split(r"_(?!_)", product_id)
            params = {"productType": product_id[4:15]}
            dates = re.findall("[0-9]{8}T[0-9]{6}", product_id)
            start_date = datetime.strptime(dates[0], "%Y%m%dT%H%M%S") - timedelta(
                seconds=1
            )
            params["startDate"] = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_date = datetime.strptime(dates[1], "%Y%m%dT%H%M%S") + timedelta(
                seconds=1
            )
            params["endDate"] = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            params["timeliness"] = parts[-2]
            params["sat"] = "Sentinel-" + parts[0][1:]
            return params

        @staticmethod
        def convert_split_id_into_s5p_params(product_id: str) -> Dict[str, str]:
            parts: List[str] = re.split(r"_(?!_)", product_id)
            params = {
                "productType": product_id[9:19],
                "processingMode": parts[1],
                "processingLevel": parts[2].replace("_", ""),
            }
            start_date = datetime.strptime(parts[-6], "%Y%m%dT%H%M%S") - timedelta(
                seconds=10
            )
            params["startDate"] = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_date = datetime.strptime(parts[-5], "%Y%m%dT%H%M%S") + timedelta(
                seconds=10
            )
            params["endDate"] = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            return params

        @staticmethod
        def convert_get_processing_level_from_s5p_id(product_id: str) -> str:
            parts: List[str] = re.split(r"_(?!_)", product_id)
            processing_level = parts[2].replace("_", "")
            return processing_level

        @staticmethod
        def convert_split_cop_dem_id(product_id: str) -> List[int]:
            parts = product_id.split("_")
            lattitude = parts[3]
            longitude = parts[5]
            if lattitude[0] == "N":
                lat_num = int(lattitude[1:])
            else:
                lat_num = -1 * int(lattitude[1:])
            if longitude[0] == "E":
                long_num = int(longitude[1:])
            else:
                long_num = -1 * int(longitude[1:])
            bbox = [long_num - 1, lat_num - 1, long_num + 1, lat_num + 1]
            return bbox

        @staticmethod
        def convert_split_corine_id(product_id: str) -> str:
            if "clc" in product_id:
                year = product_id.split("_")[1][3:]
                product_type = "Corine Land Cover " + year
            else:
                years = [1990, 2000, 2006, 2012, 2018]
                end_year = product_id[1:5]
                i = years.index(int(end_year))
                start_year = str(years[i - 1])
                product_type = "Corine Land Change " + start_year + " " + end_year
            return product_type

        @staticmethod
        def convert_to_datetime_dict(date: str, format: str) -> Dict[str, List[str]]:
            """Convert a date (str) to a dictionary where values are in the format given in argument

            date == "2021-04-21T18:27:19.123Z" and format == "list" => {
                "year": ["2021"],
                "month": ["04"],
                "day": ["21"],
                "hour": ["18"],
                "minute": ["27"],
                "second": ["19"],
            }
            date == "2021-04-21T18:27:19.123Z" and format == "string" => {
                "year": "2021",
                "month": "04",
                "day": "21",
                "hour": "18",
                "minute": "27",
                "second": "19",
            }
            date == "2021-04-21" and format == "list" => {
                "year": ["2021"],
                "month": ["04"],
                "day": ["21"],
                "hour": ["00"],
                "minute": ["00"],
                "second": ["00"],
            }
            """
            utc_date = MetadataFormatter.convert_to_iso_utc_datetime(date)
            date_object = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%S.%fZ")
            if format == "list":
                return {
                    "year": [date_object.strftime("%Y")],
                    "month": [date_object.strftime("%m")],
                    "day": [date_object.strftime("%d")],
                    "hour": [date_object.strftime("%H")],
                    "minute": [date_object.strftime("%M")],
                    "second": [date_object.strftime("%S")],
                }
            else:
                return {
                    "year": date_object.strftime("%Y"),
                    "month": date_object.strftime("%m"),
                    "day": date_object.strftime("%d"),
                    "hour": date_object.strftime("%H"),
                    "minute": date_object.strftime("%M"),
                    "second": date_object.strftime("%S"),
                }

        @staticmethod
        def convert_get_ecmwf_time(date: str) -> List[str]:
            """Get the time of a date (str) in the ECMWF format (["HH:00"])

            "2021-04-21T18:27:19.123Z" => ["18:00"]
            "2021-04-21" => ["00:00"]
            """
            return [
                str(MetadataFormatter.convert_to_datetime_dict(date, "str")["hour"])
                + ":00"
            ]

        @staticmethod
        def convert_get_dates_from_string(text: str, split_param="-"):
            reg = "[0-9]{8}" + split_param + "[0-9]{8}"
            dates_str = re.search(reg, text).group()
            dates = dates_str.split(split_param)
            start_date = datetime.strptime(dates[0], "%Y%m%d")
            end_date = datetime.strptime(dates[1], "%Y%m%d")
            return {
                "startDate": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "endDate": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }

    # if stac extension colon separator `:` is in search params, parse it to prevent issues with vformat
    if re.search(r"{[a-zA-Z0-9_-]*:[a-zA-Z0-9_-]*}", search_param):
        search_param = re.sub(
            r"{([a-zA-Z0-9_-]*):([a-zA-Z0-9_-]*)}", r"{\1_COLON_\2}", search_param
        )
        kwargs = {k.replace(":", "_COLON_"): v for k, v in kwargs.items()}

    return MetadataFormatter().vformat(search_param, args, kwargs)


def properties_from_json(
    json: Dict[str, Any],
    mapping: Dict[str, Any],
    discovery_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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
    properties: Dict[str, Any] = {}
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
            try:
                match = path_or_text.find(json)
            except KeyError:
                match = []
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
        discovered_properties = string_to_jsonpath(discovery_path).find(json)
        for found_jsonpath in discovered_properties:
            if "metadata_path_id" in discovery_config.keys():
                found_key_paths = string_to_jsonpath(
                    discovery_config["metadata_path_id"], force=True
                ).find(found_jsonpath.value)
                if not found_key_paths:
                    continue
                found_key = found_key_paths[0].value
                used_jsonpath = Child(
                    found_jsonpath.full_path,
                    string_to_jsonpath(
                        discovery_config["metadata_path_value"], force=True
                    ),
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
                    found_value_path = string_to_jsonpath(
                        discovery_config["metadata_path_value"], force=True
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
    xml_as_text: str,
    mapping: Any,
    empty_ns_prefix: str = "ns",
    discovery_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
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
    properties: Dict[str, Any] = {}
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
            if len(extracted_value) <= 1:
                if len(extracted_value) < 1:
                    # If there is no matched value (empty list), mark the metadata as not
                    # available
                    extracted_value = [NOT_AVAILABLE]
                else:
                    # store element tag in used_xpaths
                    used_xpaths.append(
                        getattr(
                            root.xpath(
                                path_or_text.replace("/text()", ""),
                                namespaces={
                                    k or empty_ns_prefix: v
                                    for k, v in root.nsmap.items()
                                },
                            )[0],
                            "tag",
                            None,
                        )
                    )
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

            # If there are multiple matches, consider the result as a list, doing a
            # formatting if any
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


def mtd_cfg_as_conversion_and_querypath(
    src_dict: Dict[str, Any],
    dest_dict: Optional[Dict[str, Any]] = {},
    result_type: str = "json",
) -> Dict[str, Any]:
    """Metadata configuration dictionary to querypath with conversion dictionnary
    Transform every src_dict value from jsonpath_str to tuple `(conversion, jsonpath_object)`
    or from xpath_str to tuple `(conversion, xpath_str)`

    :param src_dict: Input dict containing jsonpath str as values
    :type src_dict: dict
    :param dest_dict: (optional) Output dict containing jsonpath objects as values
    :type dest_dict: dict
    :returns: dest_dict
    :rtype: dict
    """
    # check if the configuration has already been converted
    some_configured_value = (
        next(iter(dest_dict.values())) if dest_dict else next(iter(src_dict.values()))
    )
    if (
        isinstance(some_configured_value, list)
        and isinstance(some_configured_value[1], tuple)
        or isinstance(some_configured_value, tuple)
    ):
        return dest_dict or src_dict

    if not dest_dict:
        dest_dict = deepcopy(src_dict)
    for metadata in src_dict:
        if metadata not in dest_dict:
            dest_dict[metadata] = (None, NOT_MAPPED)
        else:
            conversion, path = get_metadata_path(dest_dict[metadata])
            if result_type == "json":
                parsed_path = string_to_jsonpath(path)
                if isinstance(parsed_path, str):
                    # not a jsonpath: assume the mapping is to be passed as is. Ignore any transformation specified.
                    # If a value is to be passed as is, we don't want to transform it further
                    conversion = None
            else:
                parsed_path = path

            if len(dest_dict[metadata]) == 2:
                dest_dict[metadata][1] = (conversion, parsed_path)
            else:
                dest_dict[metadata] = (conversion, parsed_path)

            # Put the updated mapping at the end
            dest_dict[metadata] = dest_dict.pop(metadata)

    return dest_dict


def format_query_params(
    product_type: str, config: PluginConfig, **kwargs: Any
) -> Dict[str, Any]:
    """format the search parameters to query parameters"""
    if "raise_errors" in kwargs.keys():
        del kwargs["raise_errors"]
    # . not allowed in eodag_search_key, replaced with %2E
    kwargs = {k.replace(".", "%2E"): v for k, v in kwargs.items()}

    product_type_metadata_mapping = dict(
        config.metadata_mapping,
        **config.products.get(product_type, {}).get("metadata_mapping", {}),
    )

    query_params: Dict[str, Any] = {}
    # Get all the search parameters that are recognised as queryables by the
    # provider (they appear in the queryables dictionary)
    queryables = _get_queryables(kwargs, config, product_type_metadata_mapping)

    for eodag_search_key, provider_search_key in queryables.items():
        user_input = kwargs[eodag_search_key]

        if COMPLEX_QS_REGEX.match(provider_search_key):
            parts = provider_search_key.split("=")
            if len(parts) == 1:
                formatted_query_param = format_metadata(
                    provider_search_key, product_type, **kwargs
                )
                formatted_query_param = formatted_query_param.replace("'", '"')
                if "{{" in provider_search_key:
                    # retrieve values from hashes where keys are given in the param
                    if "}[" in formatted_query_param:
                        formatted_query_param = _resolve_hashes(formatted_query_param)
                    # json query string (for POST request)
                    update_nested_dict(
                        query_params,
                        orjson.loads(formatted_query_param),
                        extend_list_values=True,
                        allow_extend_duplicates=False,
                    )
                else:
                    query_params[eodag_search_key] = formatted_query_param
            else:
                provider_search_key, provider_value = parts
                query_params.setdefault(provider_search_key, []).append(
                    format_metadata(provider_value, product_type, **kwargs)
                )
        else:
            query_params[provider_search_key] = user_input
    # Now get all the literal search params (i.e params to be passed "as is"
    # in the search request)
    # ignore additional_params if it isn't a dictionary
    literal_search_params = getattr(config, "literal_search_params", {})
    if not isinstance(literal_search_params, dict):
        literal_search_params = {}

    # Now add formatted free text search parameters (this is for cases where a
    # complex query through a free text search parameter is available for the
    # provider and needed for the consumer)
    product_type_metadata_mapping = dict(
        config.metadata_mapping,
        **config.products.get(product_type, {}).get("metadata_mapping", {}),
    )
    literal_search_params.update(
        _format_free_text_search(config, product_type_metadata_mapping, **kwargs)
    )
    for provider_search_key, provider_value in literal_search_params.items():
        if isinstance(provider_value, list):
            query_params.setdefault(provider_search_key, []).extend(provider_value)
        else:
            query_params.setdefault(provider_search_key, []).append(provider_value)
    return query_params


def _resolve_hashes(formatted_query_param: str) -> str:
    """
    resolves structures of the format {"a": "abc", "b": "cde"}["a"] given in the formatted_query_param
    the structure is replaced by the value corresponding to the given key in the hash
    (in this case "abc")
    """
    # check if there is still a hash to be resolved
    while '}["' in formatted_query_param:
        # find and parse code between {}
        ind_open = formatted_query_param.find('}["')
        ind_close = formatted_query_param.find('"]', ind_open)
        hash_start = formatted_query_param[:ind_open].rfind(": {") + 2
        h = orjson.loads(formatted_query_param[hash_start : ind_open + 1])
        # find key and get value
        ind_key_start = formatted_query_param.find('"', ind_open) + 1
        key = formatted_query_param[ind_key_start:ind_close]
        value = h[key]
        # replace hash with value
        if isinstance(value, str):
            formatted_query_param = formatted_query_param.replace(
                formatted_query_param[hash_start : ind_close + 2], '"' + value + '"'
            )
        else:
            formatted_query_param = formatted_query_param.replace(
                formatted_query_param[hash_start : ind_close + 2], json.dumps(value)
            )
    return formatted_query_param


def _format_free_text_search(
    config: PluginConfig, metadata_mapping: Dict[str, Any], **kwargs: Any
) -> Dict[str, Any]:
    """Build the free text search parameter using the search parameters"""
    query_params: Dict[str, Any] = {}
    if not getattr(config, "free_text_search_operations", None):
        return query_params
    for param, operations_config in config.free_text_search_operations.items():
        union = operations_config["union"]
        wrapper = operations_config.get("wrapper", "{}")
        formatted_query = []
        for operator, operands in operations_config["operations"].items():
            # The Operator string is the operator wrapped with spaces
            operator = " {} ".format(operator)
            # Build the operation string by joining the formatted operands together
            # using the operation string
            operation_string = operator.join(
                format_metadata(operand, **kwargs)
                for operand in operands
                if any(
                    re.search(rf"{{{kw}[}}#]", operand)
                    and val is not None
                    and isinstance(metadata_mapping.get(kw, []), list)
                    for kw, val in kwargs.items()
                )
            )
            # Finally wrap the operation string as specified by the wrapper and add
            # it to the list of queries (only if the operation string is not empty)
            if operation_string:
                query = wrapper.format(operation_string)
                formatted_query.append(query)
        # Join the formatted query using the "union" config parameter, and then
        # wrap it with the Python format string specified in the "wrapper" config
        # parameter
        final_query = union.join(formatted_query)
        if len(operations_config["operations"]) > 1 and len(formatted_query) > 1:
            final_query = wrapper.format(query_params[param])
        if final_query:
            query_params[param] = final_query
    return query_params


def _get_queryables(
    search_params: Dict[str, Any],
    config: PluginConfig,
    metadata_mapping: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve the metadata mappings that are query-able"""
    logger.debug("Retrieving queryable metadata from metadata_mapping")
    queryables: Dict[str, Any] = {}
    for eodag_search_key, user_input in search_params.items():
        if user_input is not None:
            md_mapping = metadata_mapping.get(eodag_search_key, (None, NOT_MAPPED))
            _, md_value = md_mapping
            # query param from defined metadata_mapping
            if md_mapping is not None and isinstance(md_mapping, list):
                search_param = get_search_param(md_mapping)
                if search_param is not None:
                    queryables[eodag_search_key] = search_param
            # query param from metadata auto discovery
            elif md_value == NOT_MAPPED and getattr(
                config, "discover_metadata", {}
            ).get("auto_discovery", False):
                pattern = re.compile(
                    config.discover_metadata.get("metadata_pattern", "")
                )
                search_param_cfg = config.discover_metadata.get("search_param", "")
                if pattern.match(eodag_search_key) and isinstance(
                    search_param_cfg, str
                ):
                    search_param = search_param_cfg.format(metadata=eodag_search_key)
                    queryables[eodag_search_key] = search_param
                elif pattern.match(eodag_search_key) and isinstance(
                    search_param_cfg, dict
                ):
                    search_param_cfg_parsed = dict_items_recursive_apply(
                        search_param_cfg,
                        lambda k, v: v.format(metadata=eodag_search_key),
                    )
                    for k, v in search_param_cfg_parsed.items():
                        if getattr(config, k, None):
                            update_nested_dict(
                                getattr(config, k),
                                v,
                                extend_list_values=True,
                                allow_extend_duplicates=False,
                            )
                        else:
                            logger.warning(
                                "Could not use discover_metadata[search_param]: no entry for %s in plugin config",
                                k,
                            )
    return queryables


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
