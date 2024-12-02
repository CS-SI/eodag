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
from datetime import datetime, timedelta
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)
from urllib.parse import quote_plus, unquote_plus

import geojson
import orjson
from dateutil.parser import isoparse
from dateutil.tz import tzutc
from jsonpath_ng import Child, Fields, Root
from pydantic import Field
from pydantic.fields import FieldInfo
from requests.auth import AuthBase
from shapely.geometry.base import BaseGeometry
from typing_extensions import get_args

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    NOT_MAPPED,
    format_metadata,
    format_query_params,
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
)
from eodag.api.search_result import RawSearchResult
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.qssearch import PostJsonSearch, QueryStringSearch
from eodag.types import json_field_definition_to_python
from eodag.types.queryables import Queryables
from eodag.utils import (
    HTTP_REQ_TIMEOUT,
    deepcopy,
    dict_items_recursive_sort,
    get_geometry_from_various,
    is_range_in_range,
)
from eodag.utils.exceptions import ValidationError
from eodag.utils.requests import fetch_json

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.build_search_result")

# keywords from ECMWF keyword database + "dataset" (not part of database but exists)
# database: https://confluence.ecmwf.int/display/UDOC/Keywords+in+MARS+and+Dissemination+requests
ECMWF_KEYWORDS = [
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
]

# additional keywords from copernicus services
COP_DS_KEYWORDS = [
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
]


def keywords_to_mdt(
    keywords: List[str], prefix: Optional[str] = None
) -> Dict[str, Any]:
    """
    Make metadata mapping dict from a list of keywords

    prefix:keyword:
        - keyword
        - $."prefix:keyword"

    >>> keywords_to_mdt(["month", "year"])
    {'month': ['month', '$."month"'], 'year': ['year', '$."year"']}
    >>> keywords_to_mdt(["month", "year"], "ecmwf")
    {'ecmwf:month': ['month', '$."ecmwf:month"'], 'ecmwf:year': ['year', '$."ecmwf:year"']}

    :param keywords: List of keywords to be converted
    :param prefix: prefix to be added to the parameter in the mapping
    :return: metadata mapping dict
    """
    mdt: Dict[str, Any] = {}
    for keyword in keywords:
        key = f"{prefix}:{keyword}" if prefix else keyword
        mdt[key] = [keyword, f'$."{key}"']
    return mdt


def strip_quotes(value: Any) -> Any:
    """Strip superfluous quotes from elements (added by mapping converter to_geojson).

    >>> strip_quotes("'abc'")
    'abc'
    >>> strip_quotes(["'abc'", '"def'])
    ['abc', 'def']

    :param value: value from which quotes should be removed (should be either str or list)
    :return: value without quotes
    :raises: NotImplementedError
    """
    if isinstance(value, (list, tuple)):
        return [strip_quotes(v) for v in value]
    elif isinstance(value, dict):
        raise NotImplementedError("Dict value is not supported.")
    else:
        return str(value).strip("'\"")


def _update_properties_from_element(
    prop: Dict[str, Any], element: Dict[str, Any], values: List[str]
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
    return "ecmwf:" + v if v in ECMWF_KEYWORDS + COP_DS_KEYWORDS else v


class ECMWFSearch(PostJsonSearch):
    """ECMWF search plugin.

    This plugin builds a :class:`~eodag.api.search_result.SearchResult` containing a single product
    using given query parameters as product properties.

    The available configuration parameters inherits from parent classes, with some particular parameters
    for this plugin.

    :param provider: An eodag providers configuration dictionary
    :param config: Search plugin configuration:

        * :attr:`~eodag.config.PluginConfig.remove_from_query` (``List[str]``): List of parameters
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
        # cache fetching method
        self.fetch_data = functools.lru_cache()(self._fetch_data)

        config.metadata_mapping = {
            **keywords_to_mdt(ECMWF_KEYWORDS + COP_DS_KEYWORDS, "ecmwf"),
            **config.metadata_mapping,
        }

        super().__init__(provider, config)

        self.config.__dict__.setdefault("api_endpoint", "")

        # needed by QueryStringSearch.build_query_string / format_free_text_search
        self.config.__dict__.setdefault("free_text_search_operations", {})
        # needed for compatibility
        self.config.pagination.setdefault("next_page_query_obj", "{{}}")

        # parse jsonpath on init: product type specific metadata-mapping
        for product_type in self.config.products.keys():
            if "metadata_mapping" in self.config.products[product_type].keys():
                self.config.products[product_type][
                    "metadata_mapping"
                ] = mtd_cfg_as_conversion_and_querypath(
                    self.config.products[product_type]["metadata_mapping"]
                )
                # Complete and ready to use product type specific metadata-mapping
                product_type_metadata_mapping = deepcopy(self.config.metadata_mapping)

                # update config using provider product type definition metadata_mapping
                # from another product
                other_product_for_mapping = cast(
                    str,
                    self.config.products[product_type].get(
                        "metadata_mapping_from_product", ""
                    ),
                )
                if other_product_for_mapping:
                    other_product_type_def_params = self.get_product_type_def_params(
                        other_product_for_mapping,
                    )
                    product_type_metadata_mapping.update(
                        other_product_type_def_params.get("metadata_mapping", {})
                    )
                # from current product
                product_type_metadata_mapping.update(
                    self.config.products[product_type]["metadata_mapping"]
                )

                self.config.products[product_type][
                    "metadata_mapping"
                ] = product_type_metadata_mapping

    def do_search(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
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
    ) -> Tuple[List[EOProduct], Optional[int]]:
        """Build ready-to-download SearchResult

        :param prep: :class:`~eodag.plugins.search.PreparedSearch` object containing information needed for the search
        :param kwargs: keyword arguments to be used in the search
        :returns: list of products and number of products (optional)
        """
        product_type = prep.product_type
        if not product_type:
            product_type = kwargs.get("productType", None)
        self._preprocess_search_params(kwargs, product_type)
        result, num_items = super().query(prep, **kwargs)
        if prep.count and not num_items:
            num_items = 1

        return result, num_items

    def clear(self) -> None:
        """Clear search context"""
        super().clear()

    def build_query_string(
        self, product_type: str, **kwargs: Any
    ) -> Tuple[Dict[str, Any], str]:
        """Build The query string using the search parameters

        :param product_type: product type id
        :param kwargs: keyword arguments to be used in the query string
        :return: formatted query params and encode query string
        """
        # parse kwargs as properties as they might be needed to build the query
        parsed_properties = properties_from_json(
            kwargs,
            self.config.metadata_mapping,
        )
        available_properties = {
            # We strip values of superfluous quotes (added by mapping converter to_geojson).
            k: strip_quotes(v)
            for k, v in parsed_properties.items()
            if v not in [NOT_AVAILABLE, NOT_MAPPED]
        }

        # build and return the query
        return super().build_query_string(
            product_type=product_type, **available_properties
        )

    def _preprocess_search_params(
        self, params: Dict[str, Any], product_type: Optional[str]
    ) -> None:
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
                (
                    params["startTimeFromAscendingNode"],
                    params["completionTimeFromAscendingNode"],
                ) = _dc_qp["date"].split("/to/")
            elif "/" in _dc_qp.get("date", ""):
                (
                    params["startTimeFromAscendingNode"],
                    params["completionTimeFromAscendingNode"],
                ) = _dc_qp["date"].split("/")
            elif _dc_qp.get("date", None):
                params["startTimeFromAscendingNode"] = params[
                    "completionTimeFromAscendingNode"
                ] = _dc_qp["date"]

            if "/" in _dc_qp.get("area", ""):
                params["geometry"] = _dc_qp["area"].split("/")

        non_none_params = {k: v for k, v in params.items() if v}

        # productType
        dataset = params.get("ecmwf:dataset", None)
        params["productType"] = non_none_params.get("productType", dataset)

        # dates
        # check if default dates have to be added
        if getattr(self.config, "dates_required", False):
            self._check_date_params(params, product_type)

        # adapt end date if it is midnight
        if "completionTimeFromAscendingNode" in params:
            end_date_excluded = getattr(self.config, "end_date_excluded", True)
            is_datetime = True
            try:
                end_date = datetime.strptime(
                    params["completionTimeFromAscendingNode"], "%Y-%m-%dT%H:%M:%SZ"
                )
                end_date = end_date.replace(tzinfo=tzutc())
            except ValueError:
                try:
                    end_date = datetime.strptime(
                        params["completionTimeFromAscendingNode"],
                        "%Y-%m-%dT%H:%M:%S.%fZ",
                    )
                    end_date = end_date.replace(tzinfo=tzutc())
                except ValueError:
                    end_date = isoparse(params["completionTimeFromAscendingNode"])
                    is_datetime = False
            start_date = isoparse(params["startTimeFromAscendingNode"])
            if (
                not end_date_excluded
                and is_datetime
                and end_date > start_date
                and end_date
                == end_date.replace(hour=0, minute=0, second=0, microsecond=0)
            ):
                end_date += timedelta(days=-1)
                params["completionTimeFromAscendingNode"] = end_date.isoformat()

        # geometry
        if "geometry" in params:
            params["geometry"] = get_geometry_from_various(geometry=params["geometry"])

    def discover_queryables(
        self, **kwargs: Any
    ) -> Optional[Dict[str, Annotated[Any, FieldInfo]]]:
        """Fetch queryables list from provider using its constraints file

        :param kwargs: additional filters for queryables (`productType` and other search
                       arguments)
        :returns: fetched queryable parameters dict
        """
        product_type = kwargs.pop("productType")
        product_type_config = self.config.products.get(product_type, {})
        provider_product_type = (
            product_type_config.get("ecmwf:dataset", None)
            or product_type_config["productType"]
        )
        if "start" in kwargs:
            kwargs["startTimeFromAscendingNode"] = kwargs.pop("start")
        if "end" in kwargs:
            kwargs["completionTimeFromAscendingNode"] = kwargs.pop("end")

        # extract default datetime
        processed_kwargs = deepcopy(kwargs)
        self._preprocess_search_params(processed_kwargs, product_type)

        constraints_url = format_metadata(
            getattr(self.config, "discover_queryables", {}).get("constraints_url", ""),
            **kwargs,
        )
        constraints: List[Dict[str, Any]] = self.fetch_data(constraints_url)

        form_url = format_metadata(
            getattr(self.config, "discover_queryables", {}).get("form_url", ""),
            **kwargs,
        )
        form = self.fetch_data(form_url)

        formated_kwargs = self.format_as_provider_keyword(
            product_type, processed_kwargs
        )
        # we re-apply kwargs input to consider override of year, month, day and time.
        for key in kwargs:
            if key.startswith("ecmwf:"):
                formated_kwargs[key.replace("ecmwf:", "")] = kwargs[key]
            elif key in (
                "startTimeFromAscendingNode",
                "completionTimeFromAscendingNode",
                "geom",
            ):
                formated_kwargs[key] = kwargs[key]
            else:
                raise ValidationError(
                    f"{key} is not a queryable parameter for {self.provider}"
                )

        # we use non empty kwargs as default to integrate user inputs
        # it is needed because pydantic json schema does not represent "value"
        # but only "default"
        non_empty_formated: Dict[str, Any] = {
            k: v
            for k, v in formated_kwargs.items()
            if v and (not isinstance(v, list) or all(v))
        }
        non_empty_kwargs: Dict[str, Any] = {
            k: v
            for k, v in processed_kwargs.items()
            if v and (not isinstance(v, list) or all(v))
        }

        required_keywords: Set[str] = set()

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
                required_keywords = set(constraints[0].keys())
                for constraint in constraints[1:]:
                    required_keywords.intersection_update(constraint.keys())
        else:
            values_url = getattr(self.config, "available_values_url", "")
            if not values_url:
                return self.queryables_from_metadata_mapping(product_type)
            if "{" in values_url:
                values_url = values_url.format(productType=provider_product_type)
            data = self.fetch_data(values_url)
            available_values = data["constraints"]
            required_keywords = data.get("required", [])

        # To check if all keywords are queryable parameters, we check if they are in the
        # available values or the product type config (available values calculated from the
        # constraints might not include all queryables)
        for keyword in kwargs:
            if (
                keyword
                not in available_values.keys()
                | product_type_config.keys()
                | {
                    "startTimeFromAscendingNode",
                    "completionTimeFromAscendingNode",
                    "geom",
                }
                and keyword.replace("ecmwf:", "") not in available_values
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
                available_values, list(required_keywords), non_empty_kwargs
            )

        # ecmwf:date is replaced by start and end.
        # start and end filters are supported whenever combinations of "year", "month", "day" filters exist
        if (
            queryables.pop("ecmwf:date", None)
            or "ecmwf:year" in queryables
            or "ecmwf:hyear" in queryables
        ):
            queryables.update(
                {
                    "start": Queryables.get_with_default(
                        "start", non_empty_kwargs.get("startTimeFromAscendingNode")
                    ),
                    "end": Queryables.get_with_default(
                        "end",
                        non_empty_kwargs.get("completionTimeFromAscendingNode"),
                    ),
                }
            )

        # area is geom in EODAG.
        if queryables.pop("area", None):
            queryables["geom"] = Annotated[
                Union[str, Dict[str, float], BaseGeometry],
                Field(
                    None,
                    description="Read EODAG documentation for all supported geometry format.",
                ),
            ]

        return queryables

    def available_values_from_constraints(
        self,
        constraints: list[Dict[str, Any]],
        input_keywords: Dict[str, Any],
        form_keywords: List[str],
    ) -> Dict[str, List[str]]:
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
        filtered_constraints: List[Dict[str, Any]]

        parsed_keywords: List[str] = []
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
            filter_v = values if isinstance(values, (list, tuple)) else [values]

            # We convert every single value to a list of string
            # We strip values of superfluous quotes (added by mapping converter to_geojson).
            # ECMWF accept values with /to/. We need to split it to an array
            # ECMWF accept values in format val1/val2. We need to split it to an array
            sep = re.compile(r"/to/|/")
            filter_v = [i for v in filter_v for i in sep.split(strip_quotes(v))]

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
                    if any(is_range_in_range(x, values[0]) for x in entry[keyword]):
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
                keyword = f"ecmwf:{keyword}"

                all_keywords_str = ""
                if len(parsed_keywords) > 1:
                    keywords = [
                        f"ecmwf:{k}={pk}"
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

        available_values: Dict[str, Any] = {k: set() for k in ordered_keywords}

        # we aggregate the constraint entries left
        for entry in constraints:
            for key, value in entry.items():
                available_values[key].update(value)

        return {k: list(v) for k, v in available_values.items()}

    def queryables_by_form(
        self,
        form: List[Dict[str, Any]],
        available_values: Dict[str, List[str]],
        defaults: Dict[str, Any],
    ) -> Dict[str, Annotated[Any, FieldInfo]]:
        """
        Generate Annotated field definitions from form entries and available values
        Used by Copernicus services like cop_cds, cop_ads, cop_ewds.

        :param form: data fetched from the form endpoint of the provider
        :param available_values: available values for each parameter
        :param defaults: default values for the parameters
        :return: dict of annotated queryables
        """
        queryables: Dict[str, Annotated[Any, FieldInfo]] = {}

        required_list: List[str] = []
        for element in form:
            name: str = element["name"]

            # those are not parameter elements.
            if name in ("area_group", "global", "warning", "licences"):
                continue
            if "type" not in element or element["type"] == "FreeEditionWidget":
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

                if d := details.get("default"):
                    default = default or (d[0] if fields else d)

            if name == "area" and isinstance(default, dict):
                default = list(default.values())

            if default:
                # We strip values of superfluous quotes (addded by mapping converter to_geojson).
                default = strip_quotes(default)

            # sometimes form returns default as array instead of string
            if default and prop["type"] == "string" and isinstance(default, list):
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
        available_values: Dict[str, List[str]],
        required_keywords: List[str],
        defaults: Dict[str, Any],
    ) -> Dict[str, Annotated[Any, FieldInfo]]:
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
        required = [ecmwf_format(k) for k in required_keywords]

        queryables: Dict[str, Annotated[Any, FieldInfo]] = {}
        for name, values in available_values.items():
            # Rename keywords from form with metadata mapping.
            # Needed to map constraints like "xxxx" to eodag parameter "ecmwf:xxxx"
            key = ecmwf_format(name)

            default = defaults.get(key)

            queryables[key] = Annotated[
                get_args(
                    json_field_definition_to_python(
                        {"type": "string", "title": name, "enum": values},
                        default_value=strip_quotes(default) if default else None,
                        required=bool(key in required),
                    )
                )
            ]

        return queryables

    def format_as_provider_keyword(
        self, product_type: str, properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return provider equivalent keyword names from EODAG keywords.

        :param product_type: product type id
        :param properties: dict of properties to be formatted
        :return: dict of formatted properties
        """
        parsed_properties = properties_from_json(
            properties,
            self.config.metadata_mapping,
        )
        available_properties = {
            k: v
            for k, v in parsed_properties.items()
            if v not in [NOT_AVAILABLE, NOT_MAPPED]
        }
        return format_query_params(product_type, self.config, available_properties)

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
        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
        return fetch_json(url, auth=auth, timeout=timeout)

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> List[EOProduct]:
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
            # update result with query parameters without pagination (or search-only params)
            if isinstance(
                self.config.pagination["next_page_query_obj"], str
            ) and hasattr(results, "query_params_unpaginated"):
                unpaginated_query_params = results.query_params_unpaginated
            elif isinstance(self.config.pagination["next_page_query_obj"], str):
                next_page_query_obj = orjson.loads(
                    self.config.pagination["next_page_query_obj"].format()
                )
                unpaginated_query_params = {
                    k: v
                    for k, v in results.query_params.items()
                    if (k, v) not in next_page_query_obj.items()
                }
            else:
                unpaginated_query_params = self.query_params
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

        # remove unwanted query params
        for param in getattr(self.config, "remove_from_query", []):
            sorted_unpaginated_query_params.pop(param, None)

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

        if not product_type:
            product_type = parsed_properties.get("productType", None)

        # build product id
        id_prefix = (product_type or self.provider).upper()
        if (
            "startTimeFromAscendingNode" in parsed_properties
            and parsed_properties["startTimeFromAscendingNode"] != "Not Available"
            and "completionTimeFromAscendingNode" in parsed_properties
            and parsed_properties["completionTimeFromAscendingNode"] != "Not Available"
        ):
            product_id = "%s_%s_%s_%s" % (
                id_prefix,
                parsed_properties["startTimeFromAscendingNode"]
                .split("T")[0]
                .replace("-", ""),
                parsed_properties["completionTimeFromAscendingNode"]
                .split("T")[0]
                .replace("-", ""),
                query_hash,
            )
        elif (
            "startTimeFromAscendingNode" in parsed_properties
            and parsed_properties["startTimeFromAscendingNode"] != "Not Available"
        ):
            product_id = "%s_%s_%s" % (
                id_prefix,
                parsed_properties["startTimeFromAscendingNode"]
                .split("T")[0]
                .replace("-", ""),
                query_hash,
            )
        else:
            product_id = f"{id_prefix}_{query_hash}"

        parsed_properties["id"] = parsed_properties["title"] = product_id

        # update downloadLink and orderLink
        parsed_properties["_dc_qs"] = quote_plus(qs)
        if parsed_properties["downloadLink"] != "Not Available":
            parsed_properties["downloadLink"] += f"?{qs}"

        # parse metadata needing downloadLink
        dl_path = Fields("downloadLink")
        dl_path_from_root = Child(Root(), dl_path)
        for param, mapping in self.config.metadata_mapping.items():
            if dl_path in mapping or dl_path_from_root in mapping:
                parsed_properties.update(
                    properties_from_json(parsed_properties, {param: mapping})
                )

        # use product_type_config as default properties
        parsed_properties = dict(
            getattr(self.config, "product_type_config", {}),
            **parsed_properties,
        )

        product = EOProduct(
            provider=self.provider,
            productType=product_type,
            properties=parsed_properties,
        )

        return [
            product,
        ]

    def count_hits(
        self, count_url: Optional[str] = None, result_type: Optional[str] = None
    ) -> int:
        """Count method that will always return 1.

        :param count_url: not used, only here because this method overwrites count_hits from the parent class
        :param result_type: not used, only here because this method overwrites count_hits from the parent class
        :return: always 1
        """
        return 1


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
    ) -> Tuple[List[str], int]:
        """Wraps PostJsonSearch.collect_search_urls to force product count to 1

        :param prep: :class:`~eodag.plugins.search.PreparedSearch` object containing information for the search
        :param kwargs: keyword arguments used in the search
        :return: list of search url and number of results
        """
        urls, _ = super().collect_search_urls(prep, **kwargs)
        return urls, 1

    def do_search(
        self, prep: PreparedSearch = PreparedSearch(items_per_page=None), **kwargs: Any
    ) -> List[Dict[str, Any]]:
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
        self, product_type: str, **kwargs: Any
    ) -> Tuple[Dict[str, Any], str]:
        """Build The query string using the search parameters

        :param product_type: product type id
        :param kwargs: keyword arguments to be used in the query string
        :return: formatted query params and encode query string
        """
        return QueryStringSearch.build_query_string(
            self, product_type=product_type, **kwargs
        )


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
    ) -> List[EOProduct]:
        """Build :class:`~eodag.api.product._product.EOProduct` from provider result

        :param results: Raw provider result as single dict in list
        :param kwargs: Search arguments
        :returns: list of single :class:`~eodag.api.product._product.EOProduct`
        """

        # formating of orderLink requires access to the productType value.
        results.data = [
            {**result, **results.product_type_def_params} for result in results
        ]

        normalized = QueryStringSearch.normalize_results(self, results, **kwargs)

        if not normalized:
            return normalized

        query_params_encoded = quote_plus(orjson.dumps(results.query_params))
        for product in normalized:
            properties = {**product.properties, **results.query_params}
            properties["_dc_qs"] = query_params_encoded
            product.properties = {ecmwf_format(k): v for k, v in properties.items()}

        return normalized

    def do_search(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        """Should perform the actual search request.

        :param args: arguments to be used in the search
        :param kwargs: keyword arguments to be used in the search
        :return: list containing the results from the provider in json format
        """
        return QueryStringSearch.do_search(self, *args, **kwargs)

    def build_query_string(
        self, product_type: str, **kwargs: Any
    ) -> Tuple[Dict[str, Any], str]:
        """Build The query string using the search parameters

        :param product_type: product type id
        :param kwargs: keyword arguments to be used in the query string
        :return: formatted query params and encode query string
        """
        # Reorder kwargs to make sure year/month/day/time if set overwrite default datetime.
        # strip_quotes to remove duplicated quotes like "'1_1'" produced by convertors like to_geojson.
        priority_keys = [
            "startTimeFromAscendingNode",
            "completionTimeFromAscendingNode",
        ]
        ordered_kwargs = {k: kwargs[k] for k in priority_keys if k in kwargs}
        ordered_kwargs.update({k: strip_quotes(v) for k, v in kwargs.items()})

        return QueryStringSearch.build_query_string(
            self, product_type=product_type, **ordered_kwargs
        )
