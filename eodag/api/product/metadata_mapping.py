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
import json
import logging
import re
from datetime import datetime, timedelta
from string import Formatter

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
    get_timestamp,
    items_recursive_apply,
    nested_pairs2dict,
    string_to_jsonpath,
    update_nested_dict,
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
COMPLEX_QS_REGEX = re.compile(r"^(.+=)?([^=]*)({.+})+([^=&]*)$")


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
        def convert_to_bounds(input_geom):
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
                    from_proj = pyproj.CRS(from_proj)
                    to_proj = pyproj.CRS(DEFAULT_PROJ)
                    project = pyproj.Transformer.from_crs(
                        from_proj, to_proj, always_xy=True
                    ).transform

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

        @staticmethod
        def convert_split_id_into_s1_params(product_id):
            parts = re.split(r"_(?!_)", product_id)
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
        def convert_get_processing_level_from_s1_id(product_id):
            parts = re.split(r"_(?!_)", product_id)
            level = "LEVEL" + parts[3][0]
            return level

        @staticmethod
        def convert_get_sensor_mode_from_s1_id(product_id):
            parts = re.split(r"_(?!_)", product_id)
            return parts[1]

        @staticmethod
        def convert_get_processing_level_from_s2_id(product_id):
            parts = re.split(r"_(?!_)", product_id)
            processing_level = "S2" + parts[1]
            return processing_level

        @staticmethod
        def convert_split_id_into_s3_params(product_id):
            parts = re.split(r"_(?!_)", product_id)
            params = {"productType": product_id[4:15]}
            start_date = datetime.strptime(
                product_id[16:31], "%Y%m%dT%H%M%S"
            ) - timedelta(seconds=1)
            params["startDate"] = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_date = datetime.strptime(
                product_id[32:47], "%Y%m%dT%H%M%S"
            ) + timedelta(seconds=1)
            params["endDate"] = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            params["timeliness"] = parts[-2]
            params["sat"] = "Sentinel-" + parts[0][1:]
            return params

        @staticmethod
        def convert_split_id_into_s5p_params(product_id):
            parts = re.split(r"_(?!_)", product_id)
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
        def convert_get_processing_level_from_s5p_id(product_id):
            parts = re.split(r"_(?!_)", product_id)
            processing_level = parts[2].replace("_", "")
            return processing_level

        @staticmethod
        def convert_split_cop_dem_id(product_id):
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
        def convert_get_corine_product_type(start_date, end_date):
            start_year = start_date[:4]
            end_year = end_date[:4]
            years = [1990, 2000, 2006, 2012, 2018]
            if start_year == end_year and int(start_year) in years:
                product_type = "Corine Land Cover " + start_year
            elif int(start_year) > years[-1]:
                product_type = "Corine Land Cover " + str(years[-1])
            else:
                max_interception = 0
                sel_years = [1990, 2000]
                for i, year in enumerate(years[:-1]):
                    if int(end_year) < years[i + 1] and i == 0:
                        sel_years = [year, years[i + 1]]
                        break
                    elif int(start_year) > years[i + 1]:
                        continue
                    else:
                        interception = min(years[i + 1], int(end_year)) - max(
                            year, int(start_year)
                        )
                        if interception > max_interception:
                            max_interception = interception
                            sel_years = [year, years[i + 1]]
                product_type = (
                    "Corine Land Change " + str(sel_years[0]) + " " + str(sel_years[1])
                )

            return product_type

        @staticmethod
        def convert_split_corine_id(product_id):
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
        def convert_get_ecmwf_efas_reforecast_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            day = start_date[8:10]
            product_type = [
                "control_forecast",
                "ensemble_perturbed_forecasts"
            ]
            multi_strings = [
                {"name": "soil_level", "value": ["1","2","3"]},
                {"name": "hmonth", "value": [month]},
                {"name": "hyear", "value": [year]},
                {"name": "leadtime_hour", "value": [
                    "0",
                    "6",
                    "12",
                    "18",
                    "24",
                    "30",
                    "36",
                    "42",
                    "48",
                    "54",
                    "60",
                    "66",
                    "72",
                    "78",
                    "84",
                    "90",
                    "96",
                    "102",
                    "108",
                    "114",
                    "120",
                    "126",
                    "132",
                    "138",
                    "144",
                    "150",
                    "156",
                    "162",
                    "168",
                    "174",
                    "180",
                    "186",
                    "192",
                    "198",
                    "204",
                    "210",
                    "216",
                    "222",
                    "228",
                    "234",
                    "240",
                    "246",
                    "252",
                    "258",
                    "264",
                    "270",
                    "276",
                    "282",
                    "288",
                    "294",
                    "300",
                    "306",
                    "312",
                    "318",
                    "324",
                    "330",
                    "336",
                    "342",
                    "348",
                    "354",
                    "360",
                    "366",
                    "372",
                    "378",
                    "384",
                    "390",
                    "396",
                    "402",
                    "408",
                    "414",
                    "420",
                    "426",
                    "432",
                    "438",
                    "444",
                    "450",
                    "456",
                    "462",
                    "468",
                    "474",
                    "480",
                    "486",
                    "492",
                    "498",
                    "504",
                    "510",
                    "516",
                    "522",
                    "528",
                    "534",
                    "540",
                    "546",
                    "552",
                    "558",
                    "564",
                    "570",
                    "576",
                    "582",
                    "588",
                    "594",
                    "600",
                    "606",
                    "612",
                    "618",
                    "624",
                    "630",
                    "636",
                    "642",
                    "648",
                    "654",
                    "660",
                    "666",
                    "672",
                    "678",
                    "684",
                    "690",
                    "696",
                    "702",
                    "708",
                    "714",
                    "720",
                    "726",
                    "732",
                    "738",
                    "744",
                    "750",
                    "756",
                    "762",
                    "768",
                    "774",
                    "780",
                    "786",
                    "792",
                    "798",
                    "804",
                    "810",
                    "816",
                    "822",
                    "828",
                    "834",
                    "840",
                    "846",
                    "852",
                    "858",
                    "864",
                    "870",
                    "876",
                    "882",
                    "888",
                    "894",
                    "900",
                    "906",
                    "912",
                    "918",
                    "924",
                    "930",
                    "936",
                    "942",
                    "948",
                    "954",
                    "960",
                    "966",
                    "972",
                    "978",
                    "984",
                    "990",
                    "996",
                    "1002",
                    "1008",
                    "1014",
                    "1020",
                    "1026",
                    "1032",
                    "1038",
                    "1044",
                    "1050",
                    "1056",
                    "1062",
                    "1068",
                    "1074",
                    "1080",
                    "1086",
                    "1092",
                    "1098",
                    "1104"
                ]
                },
                {"name": "hday", "value": [day]},
                {"name": "product_type", "value": product_type},
            ]
            string_choices = [
                            {"name": "variable", "value": "volumetric_soil_moisture"},
                            {"name": "model_levels", "value": "soil_levels"},
                            {"name": "format", "value": "grib.zip"}
            ]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }
        
        @staticmethod
        def convert_get_ecmwf_efas_seasonal_reforecast_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            multi_strings = [
                {"name": "soil_level", "value": ["1","2","3"]},
                {"name": "hyear", "value": [year]},
                {"name": "hmonth", "value": [month]},
                {"name": "leadtime_hour", "value": [
                        "24",
                        "48",
                        "72",
                        "96",
                        "120",
                        "144",
                        "168",
                        "192",
                        "216",
                        "240",
                        "264",
                        "288",
                        "312",
                        "336",
                        "360",
                        "384",
                        "408",
                        "432",
                        "456",
                        "480",
                        "504",
                        "528",
                        "552",
                        "576",
                        "600",
                        "624",
                        "648",
                        "672",
                        "696",
                        "720",
                        "744",
                        "768",
                        "792",
                        "816",
                        "840",
                        "864",
                        "888",
                        "912",
                        "936",
                        "960",
                        "984",
                        "1008",
                        "1032",
                        "1056",
                        "1080",
                        "1104",
                        "1128",
                        "1152",
                        "1176",
                        "1200",
                        "1224",
                        "1248",
                        "1272",
                        "1296",
                        "1320",
                        "1344",
                        "1368",
                        "1392",
                        "1416",
                        "1440",
                        "1464",
                        "1488",
                        "1512",
                        "1536",
                        "1560",
                        "1584",
                        "1608",
                        "1632",
                        "1656",
                        "1680",
                        "1704",
                        "1728",
                        "1752",
                        "1776",
                        "1800",
                        "1824",
                        "1848",
                        "1872",
                        "1896",
                        "1920",
                        "1944",
                        "1968",
                        "1992",
                        "2016",
                        "2040",
                        "2064",
                        "2088",
                        "2112",
                        "2136",
                        "2160",
                        "2184",
                        "2208",
                        "2232",
                        "2256",
                        "2280",
                        "2304",
                        "2328",
                        "2352",
                        "2376",
                        "2400",
                        "2424",
                        "2448",
                        "2472",
                        "2496",
                        "2520",
                        "2544",
                        "2568",
                        "2592",
                        "2616",
                        "2640",
                        "2664",
                        "2688",
                        "2712",
                        "2736",
                        "2760",
                        "2784",
                        "2808",
                        "2832",
                        "2856",
                        "2880",
                        "2904",
                        "2928",
                        "2952",
                        "2976",
                        "3000",
                        "3024",
                        "3048",
                        "3072",
                        "3096",
                        "3120",
                        "3144",
                        "3168",
                        "3192",
                        "3216",
                        "3240",
                        "3264",
                        "3288",
                        "3312",
                        "3336",
                        "3360",
                        "3384",
                        "3408",
                        "3432",
                        "3456",
                        "3480",
                        "3504",
                        "3528",
                        "3552",
                        "3576",
                        "3600",
                        "3624",
                        "3648",
                        "3672",
                        "3696",
                        "3720",
                        "3744",
                        "3768",
                        "3792",
                        "3816",
                        "3840",
                        "3864",
                        "3888",
                        "3912",
                        "3936",
                        "3960",
                        "3984",
                        "4008",
                        "4032",
                        "4056",
                        "4080",
                        "4104",
                        "4128",
                        "4152",
                        "4176",
                        "4200",
                        "4224",
                        "4248",
                        "4272",
                        "4296",
                        "4320",
                        "4344",
                        "4368",
                        "4392",
                        "4416",
                        "4440",
                        "4464",
                        "4488",
                        "4512",
                        "4536",
                        "4560",
                        "4584",
                        "4608",
                        "4632",
                        "4656",
                        "4680",
                        "4704",
                        "4728",
                        "4752",
                        "4776",
                        "4800",
                        "4824",
                        "4848",
                        "4872",
                        "4896",
                        "4920",
                        "4944",
                        "4968",
                        "4992",
                        "5016",
                        "5040",
                        "5064",
                        "5088",
                        "5112",
                        "5136",
                        "5160"
                    ]
                },
            ]
            string_choices = [{"name": "variable", "value": "volumetric_soil_moisture"},
                              {"name": "model_levels", "value": "soil_levels"},
                              {"name": "format", "value": "grib.zip"}
                            ]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }
        
        @staticmethod
        def convert_get_ecmwf_glofas_reforecast_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            day = start_date[8:10]
            product_type = [
                "control_reforecast",
                "ensemble_perturbed_reforecasts"
            ]
            multi_strings = [
                {"name": "variable", "value": ["river_discharge_in_the_last_24_hours"]},
                {"name": "system_version", "value": ["version_4_0","version_2_2","version_3_1"]},
                {"name": "hydrological_model", "value": ["htessel_lisflood","lisflood"]},
                {"name": "hyear", "value": [year]},
                {"name": "hmonth", "value": [month]},
                {"name": "hday", "value": [day]},
                {"name": "leadtime_hour", "value": [
                        "24",
                        "48",
                        "72",
                        "96",
                        "120",
                        "144",
                        "168",
                        "192",
                        "216",
                        "240",
                        "264",
                        "288",
                        "312",
                        "336",
                        "360",
                        "384",
                        "408",
                        "432",
                        "456",
                        "480",
                        "504",
                        "528",
                        "552",
                        "576",
                        "600",
                        "624",
                        "648",
                        "672",
                        "696",
                        "720",
                        "744",
                        "768",
                        "792",
                        "816",
                        "840",
                        "864",
                        "888",
                        "912",
                        "936",
                        "960",
                        "984",
                        "1008",
                        "1032",
                        "1056",
                        "1080",
                        "1104"
                    ]
                },
                {"name": "product_type", "value": product_type},
            ]
            string_choices = [{"name": "format", "value": "grib"}]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }
        
        @staticmethod
        def convert_get_ecmwf_glofas_seasonal_reforecast_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            multi_strings = [
                {"name": "variable", "value": ["river_discharge_in_the_last_24_hours"]},
                {"name": "system_version", "value": ["version_2_2","version_3_1"]},
                {"name": "hydrological_model", "value": ["htessel_lisflood","lisflood"]},
                {"name": "hyear", "value": [year]},
                {"name": "hmonth", "value": [month]},
                {"name": "leadtime_hour", "value": [
                        "24",
                        "48",
                        "72",
                        "96",
                        "120",
                        "144",
                        "168",
                        "192",
                        "216",
                        "240",
                        "264",
                        "288",
                        "312",
                        "336",
                        "360",
                        "384",
                        "408",
                        "432",
                        "456",
                        "480",
                        "504",
                        "528",
                        "552",
                        "576",
                        "600",
                        "624",
                        "648",
                        "672",
                        "696",
                        "720",
                        "744",
                        "768",
                        "792",
                        "816",
                        "840",
                        "864",
                        "888",
                        "912",
                        "936",
                        "960",
                        "984",
                        "1008",
                        "1032",
                        "1056",
                        "1080",
                        "1104",
                        "1128",
                        "1152",
                        "1176",
                        "1200",
                        "1224",
                        "1248",
                        "1272",
                        "1296",
                        "1320",
                        "1344",
                        "1368",
                        "1392",
                        "1416",
                        "1440",
                        "1464",
                        "1488",
                        "1512",
                        "1536",
                        "1560",
                        "1584",
                        "1608",
                        "1632",
                        "1656",
                        "1680",
                        "1704",
                        "1728",
                        "1752",
                        "1776",
                        "1800",
                        "1824",
                        "1848",
                        "1872",
                        "1896",
                        "1920",
                        "1944",
                        "1968",
                        "1992",
                        "2016",
                        "2040",
                        "2064",
                        "2088",
                        "2112",
                        "2136",
                        "2160",
                        "2184",
                        "2208",
                        "2232",
                        "2256",
                        "2280",
                        "2304",
                        "2328",
                        "2352",
                        "2376",
                        "2400",
                        "2424",
                        "2448",
                        "2472",
                        "2496",
                        "2520",
                        "2544",
                        "2568",
                        "2592",
                        "2616",
                        "2640",
                        "2664",
                        "2688",
                        "2712",
                        "2736",
                        "2760",
                        "2784",
                        "2808",
                        "2832",
                        "2856",
                        "2880",
                        "2904",
                        "2928",
                        "2952",
                        "2976",
                        "3000",
                        "3024",
                        "3048",
                        "3072",
                        "3096",
                        "3120",
                        "3144",
                        "3168",
                        "3192",
                        "3216",
                        "3240",
                        "3264",
                        "3288",
                        "3312",
                        "3336",
                        "3360",
                        "3384",
                        "3408",
                        "3432",
                        "3456",
                        "3480",
                        "3504",
                        "3528",
                        "3552",
                        "3576",
                        "3600",
                        "3624",
                        "3648",
                        "3672",
                        "3696",
                        "3720",
                        "3744",
                        "3768",
                        "3792",
                        "3816",
                        "3840",
                        "3864",
                        "3888",
                        "3912",
                        "3936",
                        "3960",
                        "3984",
                        "4008",
                        "4032",
                        "4056",
                        "4080",
                        "4104",
                        "4128",
                        "4152",
                        "4176",
                        "4200",
                        "4224",
                        "4248",
                        "4272",
                        "4296",
                        "4320",
                        "4344",
                        "4368",
                        "4392",
                        "4416",
                        "4440",
                        "4464",
                        "4488",
                        "4512",
                        "4536",
                        "4560",
                        "4584",
                        "4608",
                        "4632",
                        "4656",
                        "4680",
                        "4704",
                        "4728",
                        "4752",
                        "4776",
                        "4800",
                        "4824",
                        "4848",
                        "4872",
                        "4896",
                        "4920",
                        "4944",
                        "4968",
                        "4992",
                        "5016",
                        "5040",
                        "5064",
                        "5088",
                        "5112",
                        "5136",
                        "5160"
                    ]
                },
            ]
            string_choices = [{"name": "format", "value": "grib"}]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }
            
        @staticmethod
        def convert_get_ecmwf_glofas_seasonal_reforecast_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            multi_strings = [
                {"name": "variable", "value": ["river_discharge_in_the_last_24_hours"]},
                {"name": "system_version", "value": ["version_2_2","version_3_1"]},
                {"name": "hydrological_model", "value": ["htessel_lisflood","lisflood"]},
                {"name": "hyear", "value": [year]},
                {"name": "hmonth", "value": [month]},
                {"name": "leadtime_hour", "value": [
                        "24",
                        "48",
                        "72",
                        "96",
                        "120",
                        "144",
                        "168",
                        "192",
                        "216",
                        "240",
                        "264",
                        "288",
                        "312",
                        "336",
                        "360",
                        "384",
                        "408",
                        "432",
                        "456",
                        "480",
                        "504",
                        "528",
                        "552",
                        "576",
                        "600",
                        "624",
                        "648",
                        "672",
                        "696",
                        "720",
                        "744",
                        "768",
                        "792",
                        "816",
                        "840",
                        "864",
                        "888",
                        "912",
                        "936",
                        "960",
                        "984",
                        "1008",
                        "1032",
                        "1056",
                        "1080",
                        "1104",
                        "1128",
                        "1152",
                        "1176",
                        "1200",
                        "1224",
                        "1248",
                        "1272",
                        "1296",
                        "1320",
                        "1344",
                        "1368",
                        "1392",
                        "1416",
                        "1440",
                        "1464",
                        "1488",
                        "1512",
                        "1536",
                        "1560",
                        "1584",
                        "1608",
                        "1632",
                        "1656",
                        "1680",
                        "1704",
                        "1728",
                        "1752",
                        "1776",
                        "1800",
                        "1824",
                        "1848",
                        "1872",
                        "1896",
                        "1920",
                        "1944",
                        "1968",
                        "1992",
                        "2016",
                        "2040",
                        "2064",
                        "2088",
                        "2112",
                        "2136",
                        "2160",
                        "2184",
                        "2208",
                        "2232",
                        "2256",
                        "2280",
                        "2304",
                        "2328",
                        "2352",
                        "2376",
                        "2400",
                        "2424",
                        "2448",
                        "2472",
                        "2496",
                        "2520",
                        "2544",
                        "2568",
                        "2592",
                        "2616",
                        "2640",
                        "2664",
                        "2688",
                        "2712",
                        "2736",
                        "2760",
                        "2784",
                        "2808",
                        "2832",
                        "2856",
                        "2880",
                        "2904",
                        "2928",
                        "2952",
                        "2976",
                        "3000",
                        "3024",
                        "3048",
                        "3072",
                        "3096",
                        "3120",
                        "3144",
                        "3168",
                        "3192",
                        "3216",
                        "3240",
                        "3264",
                        "3288",
                        "3312",
                        "3336",
                        "3360",
                        "3384",
                        "3408",
                        "3432",
                        "3456",
                        "3480",
                        "3504",
                        "3528",
                        "3552",
                        "3576",
                        "3600",
                        "3624",
                        "3648",
                        "3672",
                        "3696",
                        "3720",
                        "3744",
                        "3768",
                        "3792",
                        "3816",
                        "3840",
                        "3864",
                        "3888",
                        "3912",
                        "3936",
                        "3960",
                        "3984",
                        "4008",
                        "4032",
                        "4056",
                        "4080",
                        "4104",
                        "4128",
                        "4152",
                        "4176",
                        "4200",
                        "4224",
                        "4248",
                        "4272",
                        "4296",
                        "4320",
                        "4344",
                        "4368",
                        "4392",
                        "4416",
                        "4440",
                        "4464",
                        "4488",
                        "4512",
                        "4536",
                        "4560",
                        "4584",
                        "4608",
                        "4632",
                        "4656",
                        "4680",
                        "4704",
                        "4728",
                        "4752",
                        "4776",
                        "4800",
                        "4824",
                        "4848",
                        "4872",
                        "4896",
                        "4920",
                        "4944",
                        "4968",
                        "4992",
                        "5016",
                        "5040",
                        "5064",
                        "5088",
                        "5112",
                        "5136",
                        "5160"
                    ]
                },
            ]
            string_choices = [{"name": "format", "value": "grib"}]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }
        
        @staticmethod
        def convert_get_ecmwf_sis_params(start_date, end_date):
            start_year = max(int(start_date[:4]), 1970)
            end_year = min(int(end_date[:4]), 2100)
            slices = [[1971, 2000], [2011, 2040], [2041, 2070], [2071, 2100]]
            variable_type = "absolute_values"
            horizontal_resolution = "5_km"
            processing_type = "bias_corrected"
            if [start_year, end_year] in slices:
                product_type = "climate_impact_indicators"
                time_aggregation = ["annual_mean", "monthly_mean"]
                variable = [
                    "2m_air_temperature",
                    "highest_5_day_precipitation_amount",
                    "longest_dry_spells",
                    "number_of_dry_spells",
                    "precipitation",
                ]
                if end_year == 2000:
                    experiment = ["historical"]
                else:
                    experiment = ["rcp_2_6", "rcp_8_5", "rcp_4_5"]
                period = [str(start_year) + "_" + str(end_year)]
                ensemble_member = ["r12i1p1", "r1i1p1", "r2i1p1"]
            else:
                product_type = "essential_climate_variables"
                time_aggregation = ["daily"]
                variable = [
                    "2m_air_temperature",
                    "precipitation",
                ]  # variables available for this product type
                if end_year <= 2005:
                    experiment = ["historical"]
                else:
                    experiment = ["rcp_2_6", "rcp_8_5", "rcp_4_5"]
                period = []
                for y in range(start_year, end_year + 1):
                    period.append(str(y))
                ensemble_member = ["r12i1p1"]
            params = {
                "stringChoiceValues": [
                    {"name": "product_type", "value": product_type},
                    {"name": "processing_type", "value": processing_type},
                    {"name": "variable_type", "value": variable_type},
                    {"name": "horizontal_resolution", "value": horizontal_resolution},
                    {"name": "rcm", "value": "cclm4_8_17"},
                    {"name": "gcm", "value": "ec_earth"},
                    {"name": "format", "value": "zip"},
                ],
                "multiStringSelectValues": [
                    {"name": "variable", "value": variable},
                    {"name": "experiment", "value": experiment},
                    {"name": "period", "value": period},
                    {"name": "time_aggregation", "value": time_aggregation},
                    {"name": "ensemble_member", "value": ensemble_member},
                ],
            }
            return {
                "multiStringSelectValues": params["multiStringSelectValues"],
                "stringChoiceValues": params["stringChoiceValues"],
            }

        @staticmethod
        def convert_get_ecmwf_fire_historical_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            day = start_date[8:10]
            product_type = [
                "ensemble_spread",
                "ensemble_mean",
                "ensemble_members",
                "reanalysis",
            ]
            multi_strings = [
                {"name": "month", "value": [month]},
                {"name": "year", "value": [year]},
                {"name": "day", "value": [day]},
                {
                    "name": "variable",
                    "value": [
                        "build_up_index",
                        "danger_risk",
                        "drought_code",
                        "duff_moisture_code",
                        "fine_fuel_moisture_code",
                        "fire_daily_severity_rating",
                        "fire_weather_index",
                        "initial_fire_spread_index",
                        "fire_danger_index",
                        "keetch_byram_drought_index",
                        "burning_index",
                        "energy_release_component",
                        "ignition_component",
                        "spread_component"
                    ],
                },
                {"name": "version", "value": ["3.0","3.1","4.0"]},
                {"name": "dataset", "value": ["Consolidated dataset", "Intermediate dataset"]},
                {"name": "product_type", "value": product_type},
            ]
            string_choices = [{"name": "format", "value": "tgz"}]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }
        
        @staticmethod
        def convert_get_ecmwf_era5pl_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            day = start_date[8:10]
            hour = start_date[11:14] + "00"
            hour_num = int(start_date[11:13])
            if hour_num % 3 == 0:
                product_type = [
                    "ensemble_spread",
                    "ensemble_mean",
                    "ensemble_members",
                    "reanalysis",
                ]
            else:
                product_type = ["reanalysis"]
            multi_strings = [
                {"name": "month", "value": [month]},
                {"name": "year", "value": [year]},
                {
                    "name": "pressure_level",
                    "value": [
                        "1",
                        "2",
                        "3",
                        "5",
                        "7",
                        "10",
                        "20",
                        "30",
                        "50",
                        "70",
                        "100",
                        "125",
                        "150",
                        "175",
                        "200",
                        "225",
                        "250",
                        "300",
                        "350",
                        "400",
                        "450",
                        "500",
                        "550",
                        "600",
                        "650",
                        "700",
                        "750",
                        "775",
                        "800",
                        "825",
                        "850",
                        "875",
                        "900",
                        "925",
                        "950",
                        "975",
                        "1000",
                    ],
                },
                {"name": "time", "value": [hour]},
                {"name": "day", "value": [day]},
                {
                    "name": "variable",
                    "value": [
                        "divergence",
                        "fraction_of_cloud_cover",
                        "geopotential",
                        "ozone_mass_mixing_ratio",
                        "potential_vorticity",
                        "relative_humidity",
                        "specific_cloud_ice_water_content",
                        "specific_cloud_liquid_water_content",
                        "specific_humidity",
                        "specific_rain_water_content",
                        "specific_snow_water_content",
                        "temperature",
                        "u_component_of_wind",
                        "v_component_of_wind",
                        "vertical_velocity",
                        "vorticity",
                    ],
                },
                {"name": "product_type", "value": product_type},
            ]
            string_choices = [{"name": "format", "value": "grib"}]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }
        
        @staticmethod
        def convert_get_ecmwf_era5pl_monthly_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            day = start_date[8:10]
            hour = start_date[11:14] + "00"
            hour_num = int(start_date[11:13])
            product_type = [
                "monthly_averaged_ensemble_members",
                "monthly_averaged_ensemble_members_by_hour_of_day",
                "monthly_averaged_reanalysis",
                "monthly_averaged_reanalysis_by_hour_of_day"
            ]
            multi_strings = [
                {"name": "month", "value": [month]},
                {"name": "year", "value": [year]},
                {
                    "name": "pressure_level",
                    "value": [
                        "1",
                        "2",
                        "3",
                        "5",
                        "7",
                        "10",
                        "20",
                        "30",
                        "50",
                        "70",
                        "100",
                        "125",
                        "150",
                        "175",
                        "200",
                        "225",
                        "250",
                        "300",
                        "350",
                        "400",
                        "450",
                        "500",
                        "550",
                        "600",
                        "650",
                        "700",
                        "750",
                        "775",
                        "800",
                        "825",
                        "850",
                        "875",
                        "900",
                        "925",
                        "950",
                        "975",
                        "1000",
                    ],
                },
                {"name": "time", "value": [hour]},
                {"name": "day", "value": [day]},
                {
                    "name": "variable",
                    "value": [
                        "divergence",
                        "fraction_of_cloud_cover",
                        "geopotential",
                        "ozone_mass_mixing_ratio",
                        "potential_vorticity",
                        "relative_humidity",
                        "specific_cloud_ice_water_content",
                        "specific_cloud_liquid_water_content",
                        "specific_humidity",
                        "specific_rain_water_content",
                        "specific_snow_water_content",
                        "temperature",
                        "u_component_of_wind",
                        "v_component_of_wind",
                        "vertical_velocity",
                        "vorticity",
                    ],
                },
                {"name": "product_type", "value": product_type},
            ]
            string_choices = [{"name": "format", "value": "grib"}]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }

        @staticmethod
        def convert_get_ecmwf_era5land_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            day = start_date[8:10]
            hour = start_date[11:14] + "00"
            multi_strings = [
                {
                    "name": "variable",
                    "value": [
                        "evaporation_from_bare_soil",
                        "evaporation_from_open_water_surfaces_excluding_oceans",
                        "evaporation_from_the_top_of_canopy",
                        "evaporation_from_vegetation_transpiration",
                        "potential_evaporation",
                        "runoff",
                        "snow_evaporation",
                        "sub_surface_runoff",
                        "surface_runoff",
                        "total_evaporation",
                        "10m_u_component_of_wind",
                        "10m_v_component_of_wind",
                        "surface_pressure",
                        "total_precipitation",
                        "leaf_area_index_high_vegetation",
                        "leaf_area_index_low_vegetation",
                    ],
                },
                {"name": "day", "value": [day]},
                {"name": "time", "value": [hour]},
            ]
            string_choices = [
                {"name": "format", "value": "grib"},
                {"name": "year", "value": year},
                {"name": "month", "value": month},
            ]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }

        @staticmethod
        def convert_get_ecmwf_era5sl_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            day = start_date[8:10]
            hour = start_date[11:14] + "00"
            hour_num = int(start_date[11:13])
            if hour_num % 3 == 0:
                product_type = [
                    "ensemble_spread",
                    "ensemble_mean",
                    "ensemble_members",
                    "reanalysis",
                ]
            else:
                product_type = ["reanalysis", "ensemble_members"]
            multi_strings = [
                {"name": "time", "value": [hour]},
                {"name": "day", "value": [day]},
                {"name": "month", "value": [month]},
                {"name": "year", "value": [year]},
                {
                    "name": "variable",
                    "value": [
                        "10m_u_component_of_wind",
                        "10m_v_component_of_wind",
                        "2m_dewpoint_temperature",
                        "2m_temperature",
                        "mean_sea_level_pressure",
                        "mean_wave_direction",
                        "mean_wave_period",
                        "sea_surface_temperature",
                        "significant_height_of_combined_wind_waves_and_swell",
                        "surface_pressure",
                        "total_precipitation",
                    ],
                },
                {"name": "product_type", "value": product_type},
            ]
            string_choices = [{"name": "format", "value": "grib"}]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }
        
        @staticmethod
        def convert_get_ecmwf_era5sl_monthly_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            hour = start_date[11:14] + "00"
            hour_num = int(start_date[11:13])
            if hour_num % 3 == 0:
                product_type = [
                    "monthly_averaged_ensemble_members",
                    "monthly_averaged_ensemble_members_by_hour_of_day",
                ]
            else:
                product_type = [
                    "monthly_averaged_reanalysis",
                    "monthly_averaged_reanalysis_by_hour_of_day"
                ]
            multi_strings = [
                {"name": "time", "value": [hour]},
                {"name": "month", "value": [month]},
                {"name": "year", "value": [year]},
                {
                    "name": "variable",
                    "value": [
                        "10m_u_component_of_wind",
                        "10m_v_component_of_wind",
                        "2m_dewpoint_temperature",
                        "2m_temperature",
                        "mean_sea_level_pressure",
                        "mean_wave_direction",
                        "mean_wave_period",
                        "sea_surface_temperature",
                        "significant_height_of_combined_wind_waves_and_swell",
                        "surface_pressure",
                        "total_precipitation"
                    ],
                },
                {"name": "product_type", "value": product_type},
            ]
            string_choices = [{"name": "format", "value": "grib"}]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }

        @staticmethod
        def convert_get_ecmwf_era5land_monthly_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            hour = start_date[11:14] + "00"
            hour_num = int(start_date[11:13])
            if hour_num % 3 == 0:
                product_type = [
                    "monthly_averaged_reanalysis",
                    "monthly_averaged_reanalysis_by_hour_of_day",
                ]
            else:
                product_type = ["monthly_averaged_reanalysis_by_hour_of_day"]
            multi_strings = [
                {"name": "time", "value": [hour]},
                {"name": "product_type", "value": product_type},
                {
                    "name": "variable",
                    "value": [
                        "snow_albedo",
                        "snow_cover",
                        "snow_density",
                        "snow_depth",
                        "snow_depth_water_equivalent",
                        "snowfall",
                        "snowmelt",
                        "temperature_of_snow_layer",
                        "skin_reservoir_content",
                        "volumetric_soil_water_layer_1",
                        "volumetric_soil_water_layer_2",
                        "volumetric_soil_water_layer_3",
                        "volumetric_soil_water_layer_4",
                        "forecast_albedo",
                        "surface_latent_heat_flux",
                        "surface_net_solar_radiation",
                        "surface_net_thermal_radiation",
                        "surface_sensible_heat_flux",
                        "surface_solar_radiation_downwards",
                        "surface_thermal_radiation_downwards",
                        "evaporation_from_bare_soil",
                        "evaporation_from_open_water_surfaces_excluding_oceans",
                        "evaporation_from_the_top_of_canopy",
                        "evaporation_from_vegetation_transpiration",
                        "potential_evaporation",
                        "runoff",
                        "snow_evaporation",
                        "sub_surface_runoff",
                        "surface_runoff",
                        "total_evaporation",
                        "10m_u_component_of_wind",
                        "10m_v_component_of_wind",
                        "surface_pressure",
                        "total_precipitation",
                        "leaf_area_index_high_vegetation",
                        "leaf_area_index_low_vegetation",
                    ],
                },
                {"name": "year", "value": [year]},
                {"name": "month", "value": [month]},
            ]
            string_choices = [{"name": "format", "value": "grib"}]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }
        
        @staticmethod
        def convert_get_ecmwf_glaciers_em_change_params(start_date):
            year = start_date[:4]
            file_versions = [
                            "20170405",
                            "20171004",
                            "20180601",
                            "20181103",
                            "20191202",
                            "20200824"
            ]
            file_version = [fv for fv in file_versions if fv.startswith(year)]
            if len(file_version)==0:
                file_version = file_versions
            multi_strings = [
                                {"name": "product_type",
                                    "value": ["elevation_change", "mass_balance"]
                                },
                                {"name": "file_version", "value": file_version}
            ]
            string_choices = [{"name": "format", "value": "tgz"},
                              {"name": "variable", "value": "all"}
            ]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }
        
        @staticmethod
        def convert_get_ecmwf_sea_level_black_sea_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            day = start_date[8:10]
            multi_strings = [
                                {"name": "year", "value": [year]},
                                {"name": "month", "value": [month]},
                                {"name": "day", "value": [day]},
            ]
            string_choices = [{"name": "format", "value": "tgz"},
                              {"name": "variable", "value": "all"}
            ]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }
        
        @staticmethod
        def convert_get_ecmwf_uerra_europe_sl_params(start_date):
            year = start_date[:4]
            month = start_date[5:7]
            day = start_date[8:10]
            time = start_date[11:16]
            multi_strings = [
                {"name": "time", "value": ["00:00", "06:00", "12:00", "18:00"]},
                # {"name": "day", "value": [str(d).zfill(2) for d in range(1, 32)]},
                # {"name": "year", "value": [str(y).zfill(4) for y in range(1961, 2020)]},
                {"name": "year", "value": [year]},
                {"name": "month", "value": [str(month).zfill(2)]},
                {"name": "day", "value": [str(day).zfill(2)]},
                {"name": "time", "value": [time]},
            ]
            string_choices = [
                                {"name": "origin", "value": "mescan_surfex"},
                                {"name": "variable", "value": "10m_wind_direction"},
                                {"name": "format", "value": "grib"}
            ]
            return {
                "multiStringSelectValues": multi_strings,
                "stringChoiceValues": string_choices,
            }

    for match in re.findall(r"\([A-Za-z]+\)", search_param):
        param = match.replace("(", "").replace(")", "")
        if param in kwargs:
            search_param = search_param.replace(param, kwargs[param])

    # if stac extension colon separator `:` is in search params, parse it to prevent issues with vformat
    if re.search(r"{[a-zA-Z0-9_-]*:[a-zA-Z0-9_-]*}", search_param):
        search_param = re.sub(
            r"{([a-zA-Z0-9_-]*):([a-zA-Z0-9_-]*)}", r"{\1_COLON_\2}", search_param
        )
        kwargs = {k.replace(":", "_COLON_"): v for k, v in kwargs.items()}

    while re.search(r"\([a-zA-Z0-9_-]*:[a-zA-Z0-9_-]*", search_param):
        search_param = re.sub(
            r"(\([a-zA-Z0-9_-]*):([a-zA-Z0-9_-]*)", r"\1_COLON_\2", search_param
        )

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


def mtd_cfg_as_conversion_and_querypath(src_dict, dest_dict={}, result_type="json"):
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


def format_query_params(product_type, config, **kwargs):
    """format the search parameters to query parameters"""
    if "raise_errors" in kwargs.keys():
        del kwargs["raise_errors"]
    # . not allowed in eodag_search_key, replaced with %2E
    kwargs = {k.replace(".", "%2E"): v for k, v in kwargs.items()}

    query_params = {}
    # Get all the search parameters that are recognised as queryables by the
    # provider (they appear in the queryables dictionary)
    queryables = _get_queryables(kwargs, config)

    for eodag_search_key, provider_search_key in queryables.items():
        user_input = kwargs[eodag_search_key]

        if COMPLEX_QS_REGEX.match(provider_search_key):
            parts = provider_search_key.split("=")
            if len(parts) == 1:
                formatted_query_param = format_metadata(
                    provider_search_key, product_type, **kwargs
                )
                if "{{" in provider_search_key:
                    # retrieve values from hashes where keys are given in the param
                    if "}[" in formatted_query_param:
                        formatted_query_param = _resolve_hashes(
                            formatted_query_param.replace("'", '"')
                        )
                    # json query string (for POST request)
                    update_nested_dict(
                        query_params, orjson.loads(formatted_query_param)
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
    literal_search_params.update(_format_free_text_search(config, **kwargs))
    for provider_search_key, provider_value in literal_search_params.items():
        if isinstance(provider_value, list):
            query_params.setdefault(provider_search_key, []).extend(provider_value)
        else:
            query_params.setdefault(provider_search_key, []).append(provider_value)
    return query_params


def _resolve_hashes(formatted_query_param):
    while '}["' in formatted_query_param:
        ind_open = formatted_query_param.find('}["')
        ind_close = formatted_query_param.find('"]', ind_open)
        hash_start = formatted_query_param[:ind_open].rfind(": {") + 2
        h = orjson.loads(formatted_query_param[hash_start : ind_open + 1])
        ind_key_start = formatted_query_param.find('"', ind_open) + 1
        key = formatted_query_param[ind_key_start:ind_close]
        value = h[key]
        if isinstance(value, str):
            formatted_query_param = formatted_query_param.replace(
                formatted_query_param[hash_start : ind_close + 2], '"' + value + '"'
            )
        else:
            formatted_query_param = formatted_query_param.replace(
                formatted_query_param[hash_start : ind_close + 2], json.dumps(value)
            )
    return formatted_query_param


def _format_free_text_search(config, **kwargs):
    """Build the free text search parameter using the search parameters"""
    query_params = {}
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
                    and isinstance(config.metadata_mapping.get(kw, []), list)
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


def _get_queryables(search_params, config):
    """Retrieve the metadata mappings that are query-able"""
    logger.debug("Retrieving queryable metadata from metadata_mapping")
    queryables = {}
    for eodag_search_key, user_input in search_params.items():
        if user_input is not None:
            md_mapping = config.metadata_mapping.get(
                eodag_search_key, (None, NOT_MAPPED)
            )
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
