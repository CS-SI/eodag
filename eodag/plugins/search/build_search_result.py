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

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, cast
from urllib.parse import quote_plus, unquote_plus

import geojson
import orjson
from dateutil.parser import isoparse
from jsonpath_ng import Child, Fields, Root
from pydantic import create_model
from pydantic.fields import FieldInfo
from typing_extensions import get_args

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    NOT_MAPPED,
    get_queryable_from_provider,
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
)
from eodag.plugins.search.base import Search
from eodag.plugins.search.qssearch import PostJsonSearch
from eodag.rest.stac import DEFAULT_MISSION_START_DATE
from eodag.types import json_field_definition_to_python, model_fields_to_annotated
from eodag.types.queryables import CommonQueryables
from eodag.utils import (
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_PAGE,
    Annotated,
    deepcopy,
    dict_items_recursive_sort,
    get_geometry_from_various,
)
from eodag.utils.constraints import (
    fetch_constraints,
    get_constraint_queryables_with_additional_params,
)
from eodag.utils.exceptions import ValidationError

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.build_search_result")


class BuildPostSearchResult(PostJsonSearch):
    """BuildPostSearchResult search plugin.

    This plugin, which inherits from :class:`~eodag.plugins.search.qssearch.PostJsonSearch`,
    performs a POST request and uses its result to build a single :class:`~eodag.api.search_result.SearchResult`
    object.

    The available configuration parameters inherits from parent classes, with particularly
    for this plugin:

        - **api_endpoint**: (mandatory) The endpoint of the provider's search interface

        - **pagination**: The configuration of how the pagination is done
          on the provider. It is a tree with the following nodes:

          - *next_page_query_obj*: (optional) The additional parameters needed to perform
            search. These paramaters won't be included in result. This must be a json dict
            formatted like `{{"foo":"bar"}}` because it will be passed to a `.format()`
            method before being loaded as json.

    :param provider: An eodag providers configuration dictionary
    :type provider: dict
    :param config: Path to the user configuration file
    :type config: str
    """

    def count_hits(
        self, count_url: Optional[str] = None, result_type: Optional[str] = None
    ) -> int:
        """Count method that will always return 1."""
        return 1

    def collect_search_urls(
        self,
        page: Optional[int] = None,
        items_per_page: Optional[int] = None,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[str], int]:
        """Wraps PostJsonSearch.collect_search_urls to force product count to 1"""
        urls, _ = super(BuildPostSearchResult, self).collect_search_urls(
            page=page, items_per_page=items_per_page, count=count, **kwargs
        )
        return urls, 1

    def do_search(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        """Perform the actual search request, and return result in a single element."""
        search_url = self.search_urls[0]
        response = self._request(
            search_url,
            info_message=f"Sending search request: {search_url}",
            exception_message=f"Skipping error while searching for {self.provider} "
            f"{self.__class__.__name__} instance:",
        )
        return [response.json()]

    def normalize_results(
        self, results: List[Dict[str, Any]], **kwargs: Any
    ) -> List[EOProduct]:
        """Build :class:`~eodag.api.product._product.EOProduct` from provider result

        :param results: Raw provider result as single dict in list
        :type results: list
        :param kwargs: Search arguments
        :type kwargs: Union[int, str, bool, dict, list]
        :returns: list of single :class:`~eodag.api.product._product.EOProduct`
        :rtype: list
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
            ) and hasattr(self, "query_params_unpaginated"):
                unpaginated_query_params = self.query_params_unpaginated
            elif isinstance(self.config.pagination["next_page_query_obj"], str):
                next_page_query_obj = orjson.loads(
                    self.config.pagination["next_page_query_obj"].format()
                )
                unpaginated_query_params = {
                    k: v[0] if (isinstance(v, list) and len(v) == 1) else v
                    for k, v in self.query_params.items()
                    if (k, v) not in next_page_query_obj.items()
                }
            else:
                unpaginated_query_params = self.query_params

            # query hash, will be used to build a product id
            sorted_unpaginated_query_params = dict_items_recursive_sort(
                unpaginated_query_params
            )

        # use all available query_params to parse properties
        result = dict(result, **sorted_unpaginated_query_params)

        # remove unwanted query params
        for param in getattr(self.config, "remove_from_query", []):
            sorted_unpaginated_query_params.pop(param, None)

        qs = geojson.dumps(sorted_unpaginated_query_params)

        query_hash = hashlib.sha1(str(qs).encode("UTF-8")).hexdigest()

        # update result with product_type_def_params and search args if not None (and not auth)
        kwargs.pop("auth", None)
        result.update(self.product_type_def_params)
        result = dict(result, **{k: v for k, v in kwargs.items() if v is not None})

        # parse porperties
        parsed_properties = properties_from_json(
            result,
            self.config.metadata_mapping,
            discovery_config=getattr(self.config, "discover_metadata", {}),
        )

        if not product_type:
            product_type = parsed_properties.get("productType", None)

        # build product id
        id_prefix = (product_type or self.provider).upper()
        product_id = "%s_%s_%s" % (
            id_prefix,
            parsed_properties["startTimeFromAscendingNode"]
            .split("T")[0]
            .replace("-", ""),
            query_hash,
        )
        parsed_properties["id"] = parsed_properties["title"] = product_id

        # update downloadLink and orderLink
        parsed_properties["_dc_qs"] = quote_plus(qs)
        parsed_properties["downloadLink"] += f"?{qs}"
        if "orderLink" in parsed_properties:
            parsed_properties["orderLink"] += f"?{qs}"

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


class BuildSearchResult(BuildPostSearchResult):
    """BuildSearchResult search plugin.

    This plugin builds a single :class:`~eodag.api.search_result.SearchResult` object
    using given query parameters as product properties.

    The available configuration parameters inherits from parent classes, with particularly
    for this plugin:

        - **end_date_excluded**: Set to `False` if provider does not include end date to
          search

        - **remove_from_query**: List of parameters used to parse metadata but that must
          not be included to the query

        - **constraints_file_url**: url of the constraint file used to build queryables

    :param provider: An eodag providers configuration dictionary
    :type provider: dict
    :param config: Path to the user configuration file
    :type config: str
    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        # init self.config.metadata_mapping using Search Base plugin
        Search.__init__(self, provider, config)

        self.config.__dict__.setdefault("api_endpoint", "")

        # needed by QueryStringSearch.build_query_string / format_free_text_search
        self.config.__dict__.setdefault("free_text_search_operations", {})
        # needed for compatibility
        self.config.__dict__.setdefault("pagination", {"next_page_query_obj": "{{}}"})

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
        """Should perform the actual search request."""
        return [{}]

    def query(
        self,
        product_type: Optional[str] = None,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        page: int = DEFAULT_PAGE,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[EOProduct], Optional[int]]:
        """Build ready-to-download SearchResult"""

        self._preprocess_search_params(kwargs)

        return BuildPostSearchResult.query(
            self, items_per_page=items_per_page, page=page, count=count, **kwargs
        )

    def clear(self) -> None:
        """Clear search context"""
        pass

    def build_query_string(
        self, product_type: str, **kwargs: Any
    ) -> Tuple[Dict[str, Any], str]:
        """Build The query string using the search parameters"""
        # parse kwargs as properties as they might be needed to build the query
        parsed_properties = properties_from_json(
            kwargs,
            self.config.metadata_mapping,
        )
        available_properties = {
            k: v
            for k, v in parsed_properties.items()
            if v not in [NOT_AVAILABLE, NOT_MAPPED]
        }

        # build and return the query
        return BuildPostSearchResult.build_query_string(
            self, product_type=product_type, **available_properties
        )

    def get_product_type_cfg(self, key: str, default: Any = None) -> Any:
        """
        Get the value of a configuration option specific to the current product type.

        This method retrieves the value of a configuration option from the
        `_product_type_config` attribute. If the option is not found, the provided
        default value is returned.

        :param key: The configuration option key.
        :type key: str
        :param default: The default value to be returned if the option is not found (default is None).
        :type default: Any

        :return: The value of the specified configuration option or the default value.
        :rtype: Any
        """
        product_type_cfg = getattr(self.config, "product_type_config", {})
        non_none_cfg = {k: v for k, v in product_type_cfg.items() if v}

        return non_none_cfg.get(key, default)

    def _preprocess_search_params(self, params: Dict[str, Any]) -> None:
        """Preprocess search parameters before making a request to the CDS API.

        This method is responsible for checking and updating the provided search parameters
        to ensure that required parameters like 'productType', 'startTimeFromAscendingNode',
        'completionTimeFromAscendingNode', and 'geometry' are properly set. If not specified
        in the input parameters, default values or values from the configuration are used.

        :param params: Search parameters to be preprocessed.
        :type params: dict
        """
        _dc_qs = params.get("_dc_qs", None)
        if _dc_qs is not None:
            # if available, update search params using datacube query-string
            _dc_qp = geojson.loads(unquote_plus(unquote_plus(_dc_qs)))
            if "/" in _dc_qp.get("date", ""):
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
        dataset = params.get("dataset", None)
        params["productType"] = non_none_params.get("productType", dataset)

        # dates
        mission_start_dt = datetime.fromisoformat(
            self.get_product_type_cfg(
                "missionStartDate", DEFAULT_MISSION_START_DATE
            ).replace(
                "Z", "+00:00"
            )  # before 3.11
        )

        default_end_from_cfg = self.config.products.get(params["productType"], {}).get(
            "_default_end_date", None
        )
        default_end_str = (
            default_end_from_cfg
            or (
                datetime.now(timezone.utc)
                if params.get("startTimeFromAscendingNode")
                else mission_start_dt + timedelta(days=1)
            ).isoformat()
        )

        params["startTimeFromAscendingNode"] = non_none_params.get(
            "startTimeFromAscendingNode", mission_start_dt.isoformat()
        )
        params["completionTimeFromAscendingNode"] = non_none_params.get(
            "completionTimeFromAscendingNode", default_end_str
        )

        # temporary _date parameter mixing start & end
        end_date_excluded = getattr(self.config, "end_date_excluded", True)
        end_date = isoparse(params["completionTimeFromAscendingNode"])
        if not end_date_excluded and end_date == end_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        ):
            end_date += timedelta(days=-1)
            params["completionTimeFromAscendingNode"] = end_date.isoformat()

        # geometry
        if "geometry" in params:
            params["geometry"] = get_geometry_from_various(geometry=params["geometry"])

    def discover_queryables(
        self, **kwargs: Any
    ) -> Optional[Dict[str, Annotated[Any, FieldInfo]]]:
        """Fetch queryables list from provider using `discover_queryables` conf

        :param kwargs: additional filters for queryables (`productType` and other search
                       arguments)
        :type kwargs: Any
        :returns: fetched queryable parameters dict
        :rtype: Optional[Dict[str, Annotated[Any, FieldInfo]]]
        """
        constraints_file_url = getattr(self.config, "constraints_file_url", "")
        if not constraints_file_url:
            return {}
        product_type = kwargs.pop("productType", None)
        if not product_type:
            return {}

        provider_product_type = self.config.products.get(product_type, {}).get(
            "dataset", None
        )
        user_provider_product_type = kwargs.pop("dataset", None)
        if (
            user_provider_product_type
            and user_provider_product_type != provider_product_type
        ):
            raise ValidationError(
                f"Cannot change dataset from {provider_product_type} to {user_provider_product_type}"
            )

        # defaults
        default_queryables = self._get_defaults_as_queryables(product_type)
        # remove dataset from queryables
        default_queryables.pop("dataset", None)

        non_empty_kwargs = {k: v for k, v in kwargs.items() if v}

        if "{" in constraints_file_url:
            constraints_file_url = constraints_file_url.format(
                dataset=provider_product_type
            )
        constraints = fetch_constraints(constraints_file_url, self)
        if not constraints:
            return default_queryables

        constraint_params: Dict[str, Dict[str, Set[Any]]] = {}
        if len(kwargs) == 0:
            # get values from constraints without additional filters
            for constraint in constraints:
                for key in constraint.keys():
                    if key in constraint_params:
                        constraint_params[key]["enum"].update(constraint[key])
                    else:
                        constraint_params[key] = {}
                        constraint_params[key]["enum"] = set(constraint[key])
        else:
            # get values from constraints with additional filters
            constraints_input_params = {k: v for k, v in non_empty_kwargs.items()}
            constraint_params = get_constraint_queryables_with_additional_params(
                constraints, constraints_input_params, self, product_type
            )
            # query params that are not in constraints but might be default queryables
            if len(constraint_params) == 1 and "not_available" in constraint_params:
                not_queryables = set()
                for constraint_param in constraint_params["not_available"]["enum"]:
                    param = CommonQueryables.get_queryable_from_alias(constraint_param)
                    if param in dict(
                        CommonQueryables.model_fields, **default_queryables
                    ):
                        non_empty_kwargs.pop(constraint_param)
                    else:
                        not_queryables.add(constraint_param)
                if not_queryables:
                    raise ValidationError(
                        f"parameter(s) {str(not_queryables)} not queryable"
                    )
                else:
                    # get constraints again without common queryables
                    constraint_params = (
                        get_constraint_queryables_with_additional_params(
                            constraints, non_empty_kwargs, self, product_type
                        )
                    )

        field_definitions = dict()
        for json_param, json_mtd in constraint_params.items():
            param = (
                get_queryable_from_provider(json_param, self.config.metadata_mapping)
                or json_param
            )
            default = kwargs.get(param, None)
            annotated_def = json_field_definition_to_python(
                json_mtd, default_value=default, required=True
            )
            field_definitions[param] = get_args(annotated_def)

        python_queryables = create_model("m", **field_definitions).model_fields
        return dict(default_queryables, **model_fields_to_annotated(python_queryables))
