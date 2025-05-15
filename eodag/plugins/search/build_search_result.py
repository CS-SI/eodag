# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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

import functools
import hashlib
import logging
import re
from collections import OrderedDict
from datetime import date, datetime, timedelta, timezone
from types import MethodType
from typing import TYPE_CHECKING, Annotated, Any, Optional, Union
from urllib.parse import quote_plus, unquote_plus

import geojson
import orjson
from dateutil.parser import isoparse
from dateutil.tz import tzutc
from dateutil.utils import today
from pydantic import Field
from pydantic.fields import FieldInfo
from requests.auth import AuthBase
from shapely.geometry.base import BaseGeometry
from typing_extensions import get_args  # noqa: F401

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import (
    DEFAULT_GEOMETRY,
    NOT_AVAILABLE,
    OFFLINE_STATUS,
    STAGING_STATUS,
    format_metadata,
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
)
from eodag.api.search_result import RawSearchResult
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.qssearch import PostJsonSearch, QueryStringSearch
from eodag.types import json_field_definition_to_python  # noqa: F401
from eodag.types.queryables import Queryables, QueryablesDict
from eodag.utils import (
    DEFAULT_MISSION_START_DATE,
    DEFAULT_SEARCH_TIMEOUT,
    deepcopy,
    dict_items_recursive_sort,
    get_geometry_from_various,
    is_range_in_range,
)
from eodag.utils.exceptions import DownloadError, NotAvailableError, ValidationError
from eodag.utils.requests import fetch_json

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.build_search_result")

ECMWF_PREFIX = "ecmwf:"

# keywords from ECMWF keyword database + "dataset" (not part of database but exists)
# database: https://confluence.ecmwf.int/display/UDOC/Keywords+in+MARS+and+Dissemination+requests
ECMWF_KEYWORDS = {
    "dataset",
    "accuracy",
    "activity",
    "anoffset",
    "bitmap",
    "block",
    "channel",
    "class",
    "database",
    "date",
    "diagnostic",
    "direction",
    "domain",
    "duplicates",
    "expect",
    "expver",
    "fcmonth",
    "fcperiod",
    "fieldset",
    "filter",
    "format",
    "frame",
    "frequency",
    "generation",
    "grid",
    "hdate",
    "ident",
    "interpolation",
    "intgrid",
    "iteration",
    "latitude",
    "levelist",
    "levtype",
    "longitude",
    "lsm",
    "method",
    "number",
    "obsgroup",
    "obstype",
    "origin",
    "packing",
    "padding",
    "param",
    "priority",
    "product",
    "range",
    "realization",
    "refdate",
    "reference",
    "reportype",
    "repres",
    "resolution",
    "rotation",
    "section",
    "source",
    "step",
    "stream",
    "system",
    "target",
    "time",
    "truncation",
    "type",
    "use",
}

# additional keywords from copernicus services
COP_DS_KEYWORDS = {
    "aerosol_type",
    "altitude",
    "product_type",
    "band",
    "cdr_type",
    "data_format",
    "dataset_type",
    "day",
    "download_format",
    "ensemble_member",
    "experiment",
    "forcing_type",
    "gcm",
    "hday",
    "hmonth",
    "horizontal_resolution",
    "hydrological_model",
    "hydrological_year",
    "hyear",
    "input_observations",
    "leadtime_hour",
    "leadtime_month",
    "level",
    "location",
    "model",
    "model_level",
    "model_levels",
    "month",
    "nominal_day",
    "originating_centre",
    "period",
    "pressure_level",
    "processing_level",
    "processing_type",
    "product_version",
    "quantity",
    "rcm",
    "region",
    "release_version",
    "satellite",
    "sensor",
    "sensor_and_algorithm",
    "soil_level",
    "sky_type",
    "statistic",
    "system_version",
    "temporal_aggregation",
    "time_aggregation",
    "time_reference",
    "time_step",
    "variable",
    "variable_type",
    "version",
    "year",
}

ALLOWED_KEYWORDS = ECMWF_KEYWORDS | COP_DS_KEYWORDS

END = "completionTimeFromAscendingNode"

START = "startTimeFromAscendingNode"


def ecmwf_mtd() -> dict[str, Any]:
    """
    Make metadata mapping dict from a list of defined ECMWF Keywords

    We automatically add the #to_geojson convert to prevent modification of entries by eval() in the metadata mapping.

    keyword:
        - keyword
        - $."keyword"#to_geojson

    :return: metadata mapping dict
    """
    return {k: [k, f'{{$."{k}"#to_geojson}}'] for k in ALLOWED_KEYWORDS}


def _update_properties_from_element(
    prop: dict[str, Any], element: dict[str, Any], values: list[str]
) -> None:
    """updates a property dict with the given values based on the information from the element dict
    e.g. the type is set based on the type of the element
    """
    # multichoice elements are transformed into array
    if element["type"] in ("StringListWidget", "StringListArrayWidget"):
        prop["type"] = "array"
        if values:
            prop["items"] = {"type": "string", "enum": sorted(values)}

    # single choice elements are transformed into string
    elif element["type"] in (
        "StringChoiceWidget",
        "DateRangeWidget",
        "FreeformInputWidget",
    ):
        prop["type"] = "string"
        if values:
            prop["enum"] = sorted(values)

    # a bbox element
    elif element["type"] in ["GeographicExtentWidget", "GeographicExtentMapWidget"]:
        prop.update(
            {
                "type": "array",
                "minItems": 4,
                "additionalItems": False,
                "items": [
                    {
                        "type": "number",
                        "maximum": 180,
                        "minimum": -180,
                        "description": "West border of the bounding box",
                    },
                    {
                        "type": "number",
                        "maximum": 90,
                        "minimum": -90,
                        "description": "South border of the bounding box",
                    },
                    {
                        "type": "number",
                        "maximum": 180,
                        "minimum": -180,
                        "description": "East border of the bounding box",
                    },
                    {
                        "type": "number",
                        "maximum": 90,
                        "minimum": -90,
                        "description": "North border of the bounding box",
                    },
                ],
            }
        )

    # DateRangeWidget is a calendar date picker
    if element["type"] == "DateRangeWidget":
        prop["description"] = "date formatted like yyyy-mm-dd/yyyy-mm-dd"

    if description := element.get("help"):
        prop["description"] = description


def ecmwf_format(v: str) -> str:
    """Add ECMWF prefix to value v if v is a ECMWF keyword."""
    return ECMWF_PREFIX + v if v in ALLOWED_KEYWORDS else v


def get_min_max(
    value: Optional[Union[str, list[str]]] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Returns the min and max from a list of strings or the same string if a single string is given."""
    if isinstance(value, list):
        sorted_values = sorted(value)
        return sorted_values[0], sorted_values[-1]
    return value, value


def append_time(input_date: date, time: Optional[str]) -> datetime:
    """
    Parses a time string in format HHMM and appends it to a date.

    if the time string is in format HH:MM we convert it to HHMM
    """
    if not time:
        time = "0000"
    time = time.replace(":", "")
    if time == "2400":
        time = "0000"
    dt = datetime.combine(input_date, datetime.strptime(time, "%H%M").time())
    dt.replace(tzinfo=timezone.utc)
    return dt


def parse_date(
    date_str: str, time: Optional[Union[str, list[str]]]
) -> tuple[datetime, datetime]:
    """Parses a date string in formats YYYY-MM-DD, YYYMMDD, solo or in start/end or start/to/end intervals."""
    if "to" in date_str:
        start_date_str, end_date_str = date_str.split("/to/")
    elif "/" in date_str:
        dates = date_str.split("/")
        start_date_str = dates[0]
        end_date_str = dates[-1]
    else:
        start_date_str = end_date_str = date_str

    # Update YYYYMMDD formatted dates
    if re.match(r"^\d{8}$", start_date_str):
        start_date_str = (
            f"{start_date_str[:4]}-{start_date_str[4:6]}-{start_date_str[6:]}"
        )
    if re.match(r"^\d{8}$", end_date_str):
        end_date_str = f"{end_date_str[:4]}-{end_date_str[4:6]}-{end_date_str[6:]}"

    start_date = datetime.fromisoformat(start_date_str.rstrip("Z"))
    end_date = datetime.fromisoformat(end_date_str.rstrip("Z"))

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
) -> tuple[datetime, datetime]:
    """Extracts and returns the year, month, day, and time from the parameters."""

    def build_date(year, month=None, day=None, time=None) -> datetime:
        """Datetime from default_date with updated year, month, day and time."""
        updated_date = datetime(int(year), 1, 1).replace(
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


def ecmwf_temporal_to_eodag(
    params: dict[str, Any]
) -> tuple[Optional[str], Optional[str]]:
    """
    Converts ECMWF temporal parameters to EODAG temporal parameters.

    ECMWF temporal parameters:
        - **year** or **hyear**: Union[str, list[str]] — Year(s) as a string or list of strings.
        - **month** or **hmonth**: Union[str, list[str]] — Month(s) as a string or list of strings.
        - **day** or **hday**: Union[str, list[str]] — Day(s) as a string or list of strings.
        - **time**: str — A string representing the time in the format `HHMM` (e.g., `0200`, `0800`, `1400`).
        - **date**: str — A string in one of the formats:
            - `YYYY-MM-DD`
            - `YYYY-MM-DD/YYYY-MM-DD`
            - `YYYY-MM-DD/to/YYYY-MM-DD`

    :param params: Dictionary containing ECMWF temporal parameters.
    :return: A tuple with:
        - **start**: A string in the format `YYYY-MM-DDTHH:MM:SSZ`.
        - **end**: A string in the format `YYYY-MM-DDTHH:MM:SSZ`.
    """
    start = end = None

    if date := params.get("date"):
        start, end = parse_date(date, params.get("time"))

    elif year := params.get("year") or params.get("hyear"):
        year = params.get("year") or params.get("hyear")
        month = params.get("month") or params.get("hmonth")
        day = params.get("day") or params.get("hday")
        time = params.get("time")

        start, end = parse_year_month_day(year, month, day, time)

    if start and end:
        return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        return None, None


class ECMWFSearch(PostJsonSearch):
    """ECMWF search plugin.

    This plugin builds a :class:`~eodag.api.search_result.SearchResult` containing a single product
    using given query parameters as product properties.

    The available configuration parameters inherits from parent classes, with some particular parameters
    for this plugin.

    :param provider: An eodag providers configuration dictionary
    :param config: Search plugin configuration:

        * :attr:`~eodag.config.PluginConfig.remove_from_query` (``list[str]``): List of parameters
          used to parse metadata but that must not be included to the query
        * :attr:`~eodag.config.PluginConfig.end_date_excluded` (``bool``): Set to `False` if
          provider does not include end date to search
        * :attr:`~eodag.config.PluginConfig.discover_queryables`
          (:class:`~eodag.config.PluginConfig.DiscoverQueryables`): configuration to fetch the queryables from a
          provider queryables endpoint; It has the following keys:

          * :attr:`~eodag.config.PluginConfig.DiscoverQueryables.fetch_url` (``str``): url to fetch the queryables valid
            for all product types
          * :attr:`~eodag.config.PluginConfig.DiscoverQueryables.product_type_fetch_url` (``str``): url to fetch the
            queryables for a specific product type
          * :attr:`~eodag.config.PluginConfig.DiscoverQueryables.constraints_url` (``str``): url of the constraint file
            used to build queryables
    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        config.metadata_mapping = {
            **ecmwf_mtd(),
            **{
                "id": "$.id",
                "title": "$.id",
                "storageStatus": OFFLINE_STATUS,
                "downloadLink": "$.null",
                "geometry": ["feature", "$.geometry"],
                "defaultGeometry": "POLYGON((180 -90, 180 90, -180 90, -180 -90, 180 -90))",
            },
            **config.metadata_mapping,
        }

        super().__init__(provider, config)

        # ECMWF providers do not feature any api_endpoint or next_page_query_obj.
        # Searched is faked by EODAG.
        self.config.__dict__.setdefault("api_endpoint", "")
        self.config.pagination.setdefault("next_page_query_obj", "{{}}")

        # defaut conf for accepting custom query params
        self.config.__dict__.setdefault(
            "discover_metadata",
            {
                "auto_discovery": False,
                "search_param": "{metadata}",
                "metadata_pattern": "^[a-zA-Z0-9][a-zA-Z0-9_]*$",
            },
        )

    def do_search(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Should perform the actual search request.

        :param args: arguments to be used in the search
        :param kwargs: keyword arguments to be used in the search
        :return: list containing the results from the provider in json format
        """
        # no real search. We fake it all
        return [{}]

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> tuple[list[EOProduct], Optional[int]]:
        """Build ready-to-download SearchResult

        :param prep: :class:`~eodag.plugins.search.PreparedSearch` object containing information needed for the search
        :param kwargs: keyword arguments to be used in the search
        :returns: list of products and number of products (optional)
        """
        product_type = prep.product_type
        if not product_type:
            product_type = kwargs.get("productType", None)
        kwargs = self._preprocess_search_params(kwargs, product_type)
        result, num_items = super().query(prep, **kwargs)
        if prep.count and not num_items:
            num_items = 1

        return result, num_items

    def clear(self) -> None:
        """Clear search context"""
        super().clear()

    def build_query_string(
        self, product_type: str, query_dict: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Build The query string using the search parameters

        :param product_type: product type id
        :param query_dict: keyword arguments to be used in the query string
        :return: formatted query params and encode query string
        """
        query_dict["_date"] = f"{query_dict.get(START)}/{query_dict.get(END)}"

        # Reorder kwargs to make sure year/month/day/time if set overwrite default datetime.
        priority_keys = [
            START,
            END,
        ]
        ordered_kwargs = {k: query_dict[k] for k in priority_keys if k in query_dict}
        ordered_kwargs.update(query_dict)

        return super().build_query_string(
            product_type=product_type, query_dict=ordered_kwargs
        )

    def _preprocess_search_params(
        self, params: dict[str, Any], product_type: Optional[str]
    ) -> dict[str, Any]:
        """Preprocess search parameters before making a request to the CDS API.

        This method is responsible for checking and updating the provided search parameters
        to ensure that required parameters like 'productType', 'startTimeFromAscendingNode',
        'completionTimeFromAscendingNode', and 'geometry' are properly set. If not specified
        in the input parameters, default values or values from the configuration are used.

        :param params: Search parameters to be preprocessed.
        :param product_type: (optional) product type id
        """
        _dc_qs = params.get("_dc_qs", None)
        if _dc_qs is not None:
            # if available, update search params using datacube query-string
            _dc_qp = geojson.loads(unquote_plus(unquote_plus(_dc_qs)))
            if "/to/" in _dc_qp.get("date", ""):
                params[START], params[END] = _dc_qp["date"].split("/to/")
            elif "/" in _dc_qp.get("date", ""):
                (params[START], params[END],) = _dc_qp[
                    "date"
                ].split("/")
            elif _dc_qp.get("date", None):
                params[START] = params[END] = _dc_qp["date"]

            if "/" in _dc_qp.get("area", ""):
                params["geometry"] = _dc_qp["area"].split("/")

        params = {
            k.removeprefix(ECMWF_PREFIX): v for k, v in params.items() if v is not None
        }

        # dates
        # check if default dates have to be added
        if getattr(self.config, "dates_required", False):
            self._check_date_params(params, product_type)

        # adapt end date if it is midnight
        if END in params:
            end_date_excluded = getattr(self.config, "end_date_excluded", True)
            is_datetime = True
            try:
                end_date = datetime.strptime(params[END], "%Y-%m-%dT%H:%M:%SZ")
                end_date = end_date.replace(tzinfo=tzutc())
            except ValueError:
                try:
                    end_date = datetime.strptime(
                        params[END],
                        "%Y-%m-%dT%H:%M:%S.%fZ",
                    )
                    end_date = end_date.replace(tzinfo=tzutc())
                except ValueError:
                    end_date = isoparse(params[END])
                    is_datetime = False
            start_date = isoparse(params[START])
            if (
                not end_date_excluded
                and is_datetime
                and end_date > start_date
                and end_date
                == end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            ):
                end_date += timedelta(days=-1)
                params[END] = end_date.isoformat()

        # geometry
        if "geometry" in params:
            params["geometry"] = get_geometry_from_various(geometry=params["geometry"])

        return params

    def _check_date_params(
        self, keywords: dict[str, Any], product_type: Optional[str]
    ) -> None:
        """checks if start and end date are present in the keywords and adds them if not"""

        if START and END in keywords:
            return

        product_type_conf = getattr(self.config, "metadata_mapping", {})
        if (
            product_type
            and product_type in self.config.products
            and "metadata_mapping" in self.config.products[product_type]
        ):
            product_type_conf = self.config.products[product_type]["metadata_mapping"]

        # start time given, end time missing
        if START in keywords:
            keywords[END] = (
                keywords[START]
                if END in product_type_conf
                else self.get_product_type_cfg_value(
                    "missionEndDate", today().isoformat()
                )
            )
            return

        if END in product_type_conf:
            mapping = product_type_conf[START]
            if not isinstance(mapping, list):
                mapping = product_type_conf[END]
            if isinstance(mapping, list):
                # if startTime is not given but other time params (e.g. year/month/(day)) are given,
                # no default date is required
                start, end = ecmwf_temporal_to_eodag(keywords)
                if start is None:
                    keywords[START] = self.get_product_type_cfg_value(
                        "missionStartDate", DEFAULT_MISSION_START_DATE
                    )
                    keywords[END] = (
                        keywords[START]
                        if END in product_type_conf
                        else self.get_product_type_cfg_value(
                            "missionEndDate", today().isoformat()
                        )
                    )
                else:
                    keywords[START] = start
                    keywords[END] = end

    def _get_product_type_queryables(
        self, product_type: Optional[str], alias: Optional[str], filters: dict[str, Any]
    ) -> QueryablesDict:
        """Override to set additional_properties to false."""
        default_values: dict[str, Any] = deepcopy(
            getattr(self.config, "products", {}).get(product_type, {})
        )
        default_values.pop("metadata_mapping", None)

        filters["productType"] = product_type
        queryables = self.discover_queryables(**{**default_values, **filters}) or {}

        return QueryablesDict(additional_properties=False, **queryables)

    def discover_queryables(
        self, **kwargs: Any
    ) -> Optional[dict[str, Annotated[Any, FieldInfo]]]:
        """Fetch queryables list from provider using its constraints file

        :param kwargs: additional filters for queryables (`productType` and other search
                       arguments)
        :returns: fetched queryable parameters dict
        """
        product_type = kwargs.pop("productType")

        pt_config = self.get_product_type_def_params(product_type)

        default_values = deepcopy(pt_config)
        default_values.pop("metadata_mapping", None)
        filters = {**default_values, **kwargs}

        if "start" in filters:
            filters[START] = filters.pop("start")
        if "end" in filters:
            filters[END] = filters.pop("end")

        # extract default datetime
        processed_filters = self._preprocess_search_params(
            deepcopy(filters), product_type
        )

        constraints_url = format_metadata(
            getattr(self.config, "discover_queryables", {}).get("constraints_url", ""),
            **filters,
        )
        constraints: list[dict[str, Any]] = self._fetch_data(constraints_url)

        form_url = format_metadata(
            getattr(self.config, "discover_queryables", {}).get("form_url", ""),
            **filters,
        )
        form: list[dict[str, Any]] = self._fetch_data(form_url)

        formated_filters = self.format_as_provider_keyword(
            product_type, processed_filters
        )
        # we re-apply kwargs input to consider override of year, month, day and time.
        for k, v in {**default_values, **kwargs}.items():
            key = k.removeprefix(ECMWF_PREFIX)

            if key not in ALLOWED_KEYWORDS | {
                START,
                END,
                "geom",
                "geometry",
            }:
                raise ValidationError(
                    f"{key} is not a queryable parameter for {self.provider}"
                )

            formated_filters[key] = v

        # we use non empty filters as default to integrate user inputs
        # it is needed because pydantic json schema does not represent "value"
        # but only "default"
        non_empty_formated: dict[str, Any] = {
            k: v
            for k, v in formated_filters.items()
            if v and (not isinstance(v, list) or all(v))
        }

        required_keywords: set[str] = set()

        # calculate available values
        if constraints:
            # Apply constraints filtering
            available_values = self.available_values_from_constraints(
                constraints,
                non_empty_formated,
                form_keywords=[f["name"] for f in form],
            )

            # Pre-compute the required keywords (present in all constraint dicts)
            # when form, required keywords are extracted directly from form
            if not form:
                required_keywords = set.intersection(
                    *(map(lambda d: set(d.keys()), constraints))
                )

        else:
            values_url = getattr(self.config, "available_values_url", "")
            if not values_url:
                return self.queryables_from_metadata_mapping(product_type)
            if "{" in values_url:
                values_url = values_url.format(**filters)
            data = self._fetch_data(values_url)
            available_values = data["constraints"]
            required_keywords = data.get("required", [])

        # To check if all keywords are queryable parameters, we check if they are in the
        # available values or the product type config (available values calculated from the
        # constraints might not include all queryables)
        for keyword in filters:
            if (
                keyword
                not in available_values.keys()
                | pt_config.keys()
                | {
                    START,
                    END,
                    "geom",
                }
                and keyword not in [f["name"] for f in form]
                and keyword.removeprefix(ECMWF_PREFIX)
                not in set(list(available_values.keys()) + [f["name"] for f in form])
            ):
                raise ValidationError(f"{keyword} is not a queryable parameter")

        # generate queryables
        if form:
            queryables = self.queryables_by_form(
                form,
                available_values,
                non_empty_formated,
            )
        else:
            queryables = self.queryables_by_values(
                available_values, list(required_keywords), non_empty_formated
            )

        # ecmwf:date is replaced by start and end.
        # start and end filters are supported whenever combinations of "year", "month", "day" filters exist
        if (
            queryables.pop(f"{ECMWF_PREFIX}date", None)
            or f"{ECMWF_PREFIX}year" in queryables
            or f"{ECMWF_PREFIX}hyear" in queryables
        ):
            queryables.update(
                {
                    "start": Queryables.get_with_default(
                        "start", processed_filters.get(START)
                    ),
                    "end": Queryables.get_with_default(
                        "end",
                        processed_filters.get(END),
                    ),
                }
            )

        # area is geom in EODAG.
        if queryables.pop("area", None):
            queryables["geom"] = Annotated[
                Union[str, dict[str, float], BaseGeometry],
                Field(
                    None,
                    description="Read EODAG documentation for all supported geometry format.",
                ),
            ]

        return queryables

    def available_values_from_constraints(
        self,
        constraints: list[dict[str, Any]],
        input_keywords: dict[str, Any],
        form_keywords: list[str],
    ) -> dict[str, list[str]]:
        """
        Filter constraints using input_keywords. Return list of available queryables.
        All constraint entries must have the same parameters.

        :param constraints: list of constraints received from the provider
        :param input_keywords: dict of input parameters given by the user
        :param form_keywords: list of keyword names from the provider form endpoint
        :return: dict with available values for each parameter
        """
        # get ordered constraint keywords
        constraints_keywords = list(
            OrderedDict.fromkeys(k for c in constraints for k in c.keys())
        )

        # prepare ordered input keywords formatted as provider's keywords
        # required to filter with constraints
        ordered_keywords = (
            [kw for kw in form_keywords if kw in constraints_keywords]
            if form_keywords
            else constraints_keywords
        )

        # filter constraint entries matching input keyword values
        filtered_constraints: list[dict[str, Any]]

        parsed_keywords: list[str] = []
        for keyword in ordered_keywords:
            values = input_keywords.get(keyword)

            if values is None:
                parsed_keywords.append(keyword)
                continue

            # we only compare list of strings.
            if isinstance(values, dict):
                raise ValidationError(
                    f"Parameter value as object is not supported: {keyword}={values}"
                )

            # We convert every single value to a list of string
            filter_v = values if isinstance(values, (list, tuple)) else [values]

            # We strip values of superfluous quotes (added by mapping converter to_geojson).
            # ECMWF accept values with /to/. We need to split it to an array
            # ECMWF accept values in format val1/val2. We need to split it to an array
            sep = re.compile(r"/to/|/")
            filter_v = [i for v in filter_v for i in sep.split(str(v))]

            # special handling for time 0000 converted to 0 by pre-formating with metadata_mapping
            if keyword.split(":")[-1] == "time":
                filter_v = ["0000" if str(v) == "0" else v for v in filter_v]

            # Collect missing values to report errors
            missing_values = set(filter_v)

            # Filter constraints and check for missing values
            filtered_constraints = []
            for entry in constraints:
                # Filter based on the presence of any value in filter_v
                entry_values = entry.get(keyword, [])

                # date constraint may be intervals. We identify intervals with a "/" in the value
                # we assume that if the first value is an interval, all values are intervals
                present_values = []
                if keyword == "date" and "/" in entry[keyword][0]:
                    input_range = values
                    if isinstance(values, list):
                        input_range = values[0]
                    if any(is_range_in_range(x, input_range) for x in entry[keyword]):
                        present_values = filter_v
                else:
                    present_values = [
                        value for value in filter_v if value in entry_values
                    ]

                # Remove present values from the missing_values set
                missing_values -= set(present_values)

                if present_values:
                    filtered_constraints.append(entry)

            # raise an error as no constraint entry matched the input keywords
            # raise an error if one value from input is not allowed
            if not filtered_constraints or missing_values:
                allowed_values = list(
                    {value for c in constraints for value in c.get(keyword, [])}
                )
                # restore ecmwf: prefix before raising error
                keyword = ECMWF_PREFIX + keyword

                all_keywords_str = ""
                if len(parsed_keywords) > 1:
                    keywords = [
                        f"{ECMWF_PREFIX + k}={pk}"
                        for k in parsed_keywords
                        if (pk := input_keywords.get(k))
                    ]
                    all_keywords_str = f" with {', '.join(keywords)}"

                raise ValidationError(
                    f"{keyword}={values} is not available"
                    f"{all_keywords_str}."
                    f" Allowed values are {', '.join(allowed_values)}."
                )

            parsed_keywords.append(keyword)
            constraints = filtered_constraints

        available_values: dict[str, Any] = {k: set() for k in ordered_keywords}

        # we aggregate the constraint entries left
        for entry in constraints:
            for key, value in entry.items():
                available_values[key].update(value)

        return {k: list(v) for k, v in available_values.items()}

    def queryables_by_form(
        self,
        form: list[dict[str, Any]],
        available_values: dict[str, list[str]],
        defaults: dict[str, Any],
    ) -> dict[str, Annotated[Any, FieldInfo]]:
        """
        Generate Annotated field definitions from form entries and available values
        Used by Copernicus services like cop_cds, cop_ads, cop_ewds.

        :param form: data fetched from the form endpoint of the provider
        :param available_values: available values for each parameter
        :param defaults: default values for the parameters
        :return: dict of annotated queryables
        """
        queryables: dict[str, Annotated[Any, FieldInfo]] = {}

        required_list: list[str] = []
        for element in form:
            name: str = element["name"]

            # those are not parameter elements.
            if name in ("area_group", "global", "warning", "licences"):
                continue
            if "type" not in element or element["type"] == "FreeEditionWidget":
                # FreeEditionWidget used to select the whole available region
                # and to provide comments for the dataset
                continue

            # ordering done by id -> set id to high value if not present -> element will be last
            if "id" not in element:
                element["id"] = 100

            prop = {"title": element.get("label", name)}

            details = element.get("details", {})

            # add values from form if keyword was not in constraints
            values = (
                available_values[name]
                if name in available_values
                else details.get("values")
            )

            # updates the properties with the values given based on the information from the element
            _update_properties_from_element(prop, element, values)

            default = defaults.get(name)

            if details:
                fields = details.get("fields")
                if fields and (comment := fields[0].get("comment")):
                    prop["description"] = comment

            if name == "area" and isinstance(default, dict):
                default = list(default.values())

            # sometimes form returns default as array instead of string
            if default and prop.get("type") == "string" and isinstance(default, list):
                default = ",".join(default)

            is_required = bool(element.get("required"))
            if is_required:
                required_list.append(name)

            queryables[ecmwf_format(name)] = Annotated[
                get_args(
                    json_field_definition_to_python(
                        prop,
                        default_value=default,
                        required=is_required,
                    )
                )
            ]

        return queryables

    def queryables_by_values(
        self,
        available_values: dict[str, list[str]],
        required_keywords: list[str],
        defaults: dict[str, Any],
    ) -> dict[str, Annotated[Any, FieldInfo]]:
        """
        Generate Annotated field definitions from available values.
        Used by ECMWF data providers like dedt_lumi.

        :param available_values: available values for each parameter
        :param required_keywords: list of required parameters
        :param defaults: default values for the parameters
        :return: dict of annotated queryables
        """
        # Rename keywords from form with metadata mapping.
        # Needed to map constraints like "xxxx" to eodag parameter "ecmwf:xxxx"
        required = [ecmwf_format(k) for k in required_keywords]  # noqa: F841

        queryables: dict[str, Annotated[Any, FieldInfo]] = {}
        for name, values in available_values.items():
            # Rename keywords from form with metadata mapping.
            # Needed to map constraints like "xxxx" to eodag parameter "ecmwf:xxxx"
            key = ecmwf_format(name)

            queryables[key] = Annotated[
                get_args(
                    json_field_definition_to_python(
                        {"type": "string", "title": name, "enum": values},
                        default_value=defaults.get(name),
                        required=bool(key in required),
                    )
                )
            ]

        return queryables

    def format_as_provider_keyword(
        self, product_type: str, properties: dict[str, Any]
    ) -> dict[str, Any]:
        """Return provider equivalent keyword names from EODAG keywords.

        :param product_type: product type id
        :param properties: dict of properties to be formatted
        :return: dict of formatted properties
        """
        properties["productType"] = product_type

        # provider product type specific conf
        product_type_def_params = self.get_product_type_def_params(
            product_type, format_variables=properties
        )

        # Add to the query, the queryable parameters set in the provider product type definition
        properties.update(
            {
                k: v
                for k, v in product_type_def_params.items()
                if k not in properties.keys()
                and k in self.config.metadata_mapping.keys()
                and isinstance(self.config.metadata_mapping[k], list)
            }
        )
        qp, _ = self.build_query_string(product_type, properties)

        return qp

    def _fetch_data(self, url: str) -> Any:
        """
        fetches from a provider elements like constraints or forms.

        :param url: url from which the constraints can be fetched
        :returns: json file content fetched from the provider
        """
        if not url:
            return []

        auth = (
            self.auth
            if hasattr(self, "auth") and isinstance(self.auth, AuthBase)
            else None
        )
        timeout = getattr(self.config, "timeout", DEFAULT_SEARCH_TIMEOUT)
        return functools.lru_cache()(fetch_json)(url, auth=auth, timeout=timeout)

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> list[EOProduct]:
        """Build :class:`~eodag.api.product._product.EOProduct` from provider result

        :param results: Raw provider result as single dict in list
        :param kwargs: Search arguments
        :returns: list of single :class:`~eodag.api.product._product.EOProduct`
        """

        product_type = kwargs.get("productType")

        result = results[0]

        # datacube query string got from previous search
        _dc_qs = kwargs.pop("_dc_qs", None)
        if _dc_qs is not None:
            qs = unquote_plus(unquote_plus(_dc_qs))
            sorted_unpaginated_qp = geojson.loads(qs)
        else:
            sorted_unpaginated_qp = dict_items_recursive_sort(results.query_params)

        # remove unwanted query params
        for param in getattr(self.config, "remove_from_query", []):
            sorted_unpaginated_qp.pop(param, None)

        if result:
            properties = result
            properties.update(result.pop("request_params", None) or {})

            properties = {k: v for k, v in properties.items() if not k.startswith("__")}

            properties["geometry"] = properties.get("area") or DEFAULT_GEOMETRY

            start, end = ecmwf_temporal_to_eodag(properties)
            properties["startTimeFromAscendingNode"] = start
            properties["completionTimeFromAscendingNode"] = end

        else:
            # use all available query_params to parse properties
            result_data: dict[str, Any] = {
                **results.product_type_def_params,
                **sorted_unpaginated_qp,
                **{"qs": sorted_unpaginated_qp},
            }

            # update result with product_type_def_params and search args if not None (and not auth)
            kwargs.pop("auth", None)
            result_data.update(results.product_type_def_params)
            result_data = {
                **result_data,
                **{k: v for k, v in kwargs.items() if v is not None},
            }

            properties = properties_from_json(
                result_data,
                self.config.metadata_mapping,
                discovery_config=getattr(self.config, "discover_metadata", {}),
            )

            query_hash = hashlib.sha1(str(result_data).encode("UTF-8")).hexdigest()

            properties["title"] = properties["id"] = (
                (product_type or kwargs.get("dataset", self.provider)).upper()
                + "_ORDERABLE_"
                + query_hash
            )
            # use product_type_config as default properties
            product_type_config = getattr(self.config, "product_type_config", {})
            properties = dict(product_type_config, **properties)

        qs = geojson.dumps(sorted_unpaginated_qp)

        # used by server mode to generate downloadlink href
        # TODO: to remove once the legacy server is removed
        properties["_dc_qs"] = quote_plus(qs)

        product = EOProduct(
            provider=self.provider,
            properties={ecmwf_format(k): v for k, v in properties.items()},
            **kwargs,
        )

        # backup original register_downloader to register_downloader_only
        product.register_downloader_only = product.register_downloader
        # patched register_downloader that will also update properties
        product.register_downloader = MethodType(patched_register_downloader, product)

        return [product]

    def count_hits(
        self, count_url: Optional[str] = None, result_type: Optional[str] = None
    ) -> int:
        """Count method that will always return 1.

        :param count_url: not used, only here because this method overwrites count_hits from the parent class
        :param result_type: not used, only here because this method overwrites count_hits from the parent class
        :return: always 1
        """
        return 1


def _check_id(product: EOProduct) -> EOProduct:
    """Check if the id is the one of an existing job.

    If the job exists, poll it, otherwise, raise an error.

    :param product: The product to check the id for
    :raises: :class:`~eodag.utils.exceptions.ValidationError`
    """
    if not (product_id := product.search_kwargs.get("id")):
        return product

    if "ORDERABLE" in product_id:
        return product

    on_response_mm = getattr(product.downloader.config, "order_on_response", {}).get(
        "metadata_mapping", {}
    )
    if not on_response_mm:
        return product

    logger.debug(f"Update product properties using given orderId {product_id}")
    on_response_mm_jsonpath = mtd_cfg_as_conversion_and_querypath(
        on_response_mm,
    )
    properties_update = properties_from_json(
        {}, {**on_response_mm_jsonpath, **{"orderId": (None, product_id)}}
    )
    product.properties.update(
        {k: v for k, v in properties_update.items() if v != NOT_AVAILABLE}
    )

    auth = product.downloader_auth.authenticate() if product.downloader_auth else None

    # try to poll the job corresponding to the given id
    try:
        product.downloader._order_status(product=product, auth=auth)  # type: ignore
    # when a NotAvailableError is catched, it means the product is not ready and still needs to be polled
    except NotAvailableError:
        product.properties["storageStatus"] = STAGING_STATUS
    except Exception as e:
        if (
            isinstance(e, DownloadError) or isinstance(e, ValidationError)
        ) and "order status could not be checked" in e.args[0]:
            raise ValidationError(
                f"Item {product_id} does not exist with {product.provider}."
            ) from e
        raise ValidationError(e.args[0]) from e

    # update product id
    product.properties["id"] = product_id
    # update product type if needed
    if product.product_type is None:
        product.product_type = product.properties.get("ecmwf:dataset")
    # update product title
    product.properties["title"] = (
        (product.product_type or product.provider).upper() + "_" + product_id
    )
    # use NOT_AVAILABLE as fallback product_type to avoid using guess_product_type
    if product.product_type is None:
        product.product_type = NOT_AVAILABLE

    return product


def patched_register_downloader(self, downloader, authenticator):
    """Register product donwloader and update properties if searched by id.

    :param self: product to which information should be added
    :param downloader: The download method that it can use
                    :class:`~eodag.plugins.download.base.Download` or
                    :class:`~eodag.plugins.api.base.Api`
    :param authenticator: The authentication method needed to perform the download
                        :class:`~eodag.plugins.authentication.base.Authentication`
    """
    # register downloader
    self.register_downloader_only(downloader, authenticator)
    # and also update properties
    _check_id(self)


class MeteoblueSearch(ECMWFSearch):
    """MeteoblueSearch search plugin.

    This plugin, which inherits from :class:`~eodag.plugins.search.build_search_result.ECMWFSearch`,
    performs a POST request and uses its result to build a single :class:`~eodag.api.search_result.SearchResult`
    object.

    The available configuration parameters are inherited from parent classes, with some a particularity
    for pagination for this plugin.

    :param provider: An eodag providers configuration dictionary
    :param config: Search plugin configuration:

        * :attr:`~eodag.config.PluginConfig.pagination` (:class:`~eodag.config.PluginConfig.Pagination`)
          (**mandatory**): The configuration of how the pagination is done on the provider. For
          this plugin it has the node:

          * :attr:`~eodag.config.PluginConfig.Pagination.next_page_query_obj` (``str``): The
            additional parameters needed to perform search. These parameters won't be included in
            the result. This must be a json dict formatted like ``{{"foo":"bar"}}`` because it
            will be passed to a :meth:`str.format` method before being loaded as json.
    """

    def collect_search_urls(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> tuple[list[str], int]:
        """Wraps PostJsonSearch.collect_search_urls to force product count to 1

        :param prep: :class:`~eodag.plugins.search.PreparedSearch` object containing information for the search
        :param kwargs: keyword arguments used in the search
        :return: list of search url and number of results
        """
        urls, _ = super().collect_search_urls(prep, **kwargs)
        return urls, 1

    def do_search(
        self, prep: PreparedSearch = PreparedSearch(items_per_page=None), **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Perform the actual search request, and return result in a single element.

        :param prep: :class:`~eodag.plugins.search.PreparedSearch` object containing information for the search
        :param kwargs: keyword arguments to be used in the search
        :return: list containing the results from the provider in json format
        """

        prep.url = prep.search_urls[0]
        prep.info_message = f"Sending search request: {prep.url}"
        prep.exception_message = (
            f"Skipping error while searching for {self.provider}"
            f" {self.__class__.__name__} instance"
        )
        response = self._request(prep)

        return [response.json()]

    def build_query_string(
        self, product_type: str, query_dict: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Build The query string using the search parameters

        :param product_type: product type id
        :param query_dict: keyword arguments to be used in the query string
        :return: formatted query params and encode query string
        """
        return QueryStringSearch.build_query_string(self, product_type, query_dict)

    def normalize_results(self, results, **kwargs):
        """Build :class:`~eodag.api.product._product.EOProduct` from provider result

        :param results: Raw provider result as single dict in list
        :param kwargs: Search arguments
        :returns: list of single :class:`~eodag.api.product._product.EOProduct`
        """

        product_type = kwargs.get("productType")

        result = results[0]

        # datacube query string got from previous search
        _dc_qs = kwargs.pop("_dc_qs", None)
        if _dc_qs is not None:
            qs = unquote_plus(unquote_plus(_dc_qs))
            sorted_unpaginated_query_params = geojson.loads(qs)
        else:
            next_page_query_obj = orjson.loads(
                self.config.pagination["next_page_query_obj"].format()
            )
            unpaginated_query_params = {
                k: v
                for k, v in results.query_params.items()
                if (k, v) not in next_page_query_obj.items()
            }
            # query hash, will be used to build a product id
            sorted_unpaginated_query_params = dict_items_recursive_sort(
                unpaginated_query_params
            )

        # use all available query_params to parse properties
        result = dict(
            result,
            **sorted_unpaginated_query_params,
            qs=sorted_unpaginated_query_params,
        )

        qs = geojson.dumps(sorted_unpaginated_query_params)

        query_hash = hashlib.sha1(str(qs).encode("UTF-8")).hexdigest()

        # update result with product_type_def_params and search args if not None (and not auth)
        kwargs.pop("auth", None)
        result.update(results.product_type_def_params)
        result = dict(result, **{k: v for k, v in kwargs.items() if v is not None})

        # parse properties
        parsed_properties = properties_from_json(
            result,
            self.config.metadata_mapping,
            discovery_config=getattr(self.config, "discover_metadata", {}),
        )

        properties = {
            # use product_type_config as default properties
            **getattr(self.config, "product_type_config", {}),
            **{ecmwf_format(k): v for k, v in parsed_properties.items()},
        }

        def slugify(date_str: str) -> str:
            return date_str.split("T")[0].replace("-", "")

        # build product id
        product_id = (product_type or self.provider).upper()

        start = properties.get(START, NOT_AVAILABLE)
        end = properties.get(END, NOT_AVAILABLE)

        if start != NOT_AVAILABLE:
            product_id += f"_{slugify(start)}"
            if end != NOT_AVAILABLE:
                product_id += f"_{slugify(end)}"

        product_id += f"_{query_hash}"

        properties["id"] = properties["title"] = product_id

        # used by server mode to generate downloadlink href
        properties["_dc_qs"] = quote_plus(qs)

        product = EOProduct(
            provider=self.provider,
            productType=product_type,
            properties=properties,
        )
        # use product_type_config as default properties
        product_type_config = getattr(self.config, "product_type_config", {})
        product.properties = dict(product_type_config, **product.properties)

        return [
            product,
        ]


class WekeoECMWFSearch(ECMWFSearch):
    """
    WekeoECMWFSearch search plugin.

    This plugin, which inherits from :class:`~eodag.plugins.search.build_search_result.ECMWFSearch`,
    performs a POST request and uses its result to build a single :class:`~eodag.api.search_result.SearchResult`
    object. In contrast to ECMWFSearch or MeteoblueSearch, the products are only build with information
    returned by the provider.

    The available configuration parameters are inherited from parent classes, with some a particularity
    for pagination for this plugin.

    :param provider: An eodag providers configuration dictionary
    :param config: Search plugin configuration:

        * :attr:`~eodag.config.PluginConfig.pagination` (:class:`~eodag.config.PluginConfig.Pagination`)
          (**mandatory**): The configuration of how the pagination is done on the provider. For
          this plugin it has the node:

          * :attr:`~eodag.config.PluginConfig.Pagination.next_page_query_obj` (``str``): The
            additional parameters needed to perform search. These parameters won't be included in
            the result. This must be a json dict formatted like ``{{"foo":"bar"}}`` because it
            will be passed to a :meth:`str.format` method before being loaded as json.
    """

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> list[EOProduct]:
        """Build :class:`~eodag.api.product._product.EOProduct` from provider result

        :param results: Raw provider result as single dict in list
        :param kwargs: Search arguments
        :returns: list of single :class:`~eodag.api.product._product.EOProduct`
        """

        if kwargs.get("id") and "ORDERABLE" not in kwargs["id"]:
            # id is order id (only letters and numbers) -> use parent normalize results
            return super().normalize_results(results, **kwargs)

        # formating of orderLink requires access to the productType value.
        results.data = [
            {**result, **results.product_type_def_params} for result in results
        ]

        normalized = QueryStringSearch.normalize_results(self, results, **kwargs)

        if not normalized:
            return normalized

        # remove unwanted query params
        excluded_query_params = getattr(self.config, "remove_from_query", [])
        filtered_query_params = {
            k: v
            for k, v in results.query_params.items()
            if k not in excluded_query_params
        }
        for product in normalized:
            properties = {**product.properties, **results.query_params}
            properties["_dc_qs"] = quote_plus(orjson.dumps(filtered_query_params))
            product.properties = {ecmwf_format(k): v for k, v in properties.items()}

            # update product and title the same way as in parent class
            splitted_id = product.properties.get("title", "").split("-")
            dataset = "_".join(splitted_id[:-1])
            query_hash = splitted_id[-1]
            product.properties["title"] = product.properties["id"] = (
                (product.product_type or dataset or self.provider).upper()
                + "_ORDERABLE_"
                + query_hash
            )

        return normalized

    def do_search(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Should perform the actual search request.

        :param args: arguments to be used in the search
        :param kwargs: keyword arguments to be used in the search
        :return: list containing the results from the provider in json format
        """
        if "id" in kwargs and "ORDERABLE" not in kwargs["id"]:
            # id is order id (only letters and numbers) -> use parent normalize results.
            # No real search. We fake it all, then check order status using given id
            return [{}]
        else:
            return QueryStringSearch.do_search(self, *args, **kwargs)
