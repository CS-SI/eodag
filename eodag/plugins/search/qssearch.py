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

import logging
import re
from collections.abc import Iterable
from copy import copy as copy_copy
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    TypedDict,
    cast,
)
from urllib.error import URLError
from urllib.parse import (
    parse_qsl,
    quote_plus,
    unquote,
    unquote_plus,
    urlparse,
    urlunparse,
)
from urllib.request import Request, urlopen

import geojson
import orjson
import requests
import yaml
from lxml import etree
from pydantic import create_model
from pydantic.fields import FieldInfo
from requests import Response
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    format_query_params,
    get_queryable_from_provider,
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
    properties_from_xml,
)
from eodag.api.search_result import RawSearchResult
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.base import Search
from eodag.types import json_field_definition_to_python, model_fields_to_annotated
from eodag.types.queryables import CommonQueryables
from eodag.types.search_args import SortByList
from eodag.utils import (
    GENERIC_PRODUCT_TYPE,
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    Annotated,
    _deprecated,
    deepcopy,
    dict_items_recursive_apply,
    format_dict_items,
    get_args,
    get_ssl_context,
    quote,
    string_to_jsonpath,
    update_nested_dict,
    urlencode,
)
from eodag.utils.constraints import (
    fetch_constraints,
    get_constraint_queryables_with_additional_params,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    RequestError,
    TimeOutError,
    ValidationError,
)

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.qssearch")


class QueryStringSearch(Search):
    """A plugin that helps implementing any kind of search protocol that relies on
    query strings (e.g: opensearch).

    The available configuration parameters for this kind of plugin are:

        - **result_type**: (optional) One of "json" or "xml", depending on the
          representation of the provider's search results. The default is "json"

        - **results_entry**: (mandatory) The name of the key in the provider search
          result that gives access to the result entries

        - **api_endpoint**: (mandatory) The endpoint of the provider's search interface

        - **literal_search_params**: (optional) A mapping of (search_param =>
          search_value) pairs giving search parameters to be passed as is in the search
          url query string. This is useful for example in situations where the user wants
          to pass-in a search query as it is done on the provider interface. In such a case,
          the user can put in his configuration file the query he needs to pass to the provider.

        - **pagination**: (mandatory) The configuration of how the pagination is done
          on the provider. It is a tree with the following nodes:

          - *next_page_url_tpl*: The template for pagination requests. This is a simple
            Python format string which will be resolved using the following keywords:
            ``url`` (the base url of the search endpoint), ``search`` (the query string
            corresponding to the search request), ``items_per_page`` (the number of
            items to return per page), ``skip`` (the number of items to skip) or
            ``skip_base_1`` (the number of items to skip, starting from 1) and
            ``page`` (which page to return).

          - *total_items_nb_key_path*: (optional) An XPath or JsonPath leading to the
            total number of results satisfying a request. This is used for providers
            which provides the total results metadata along with the result of the
            query and don't have an endpoint for querying the number of items
            satisfying a request, or for providers for which the count endpoint returns
            a json or xml document

          - *count_endpoint*: (optional) The endpoint for counting the number of items
            satisfying a request

          - *next_page_url_key_path*: (optional) A JSONPATH expression used to retrieve
            the URL of the next page in the response of the current page.

        - **free_text_search_operations**: (optional) A tree structure of the form::

            # noqa: E800
            <search-param>:     # e.g: $search
                union: # how to join the operations below (e.g: ' AND ' -->
                       # '(op1 AND op2) AND (op3 OR op4)')
                wrapper: # a pattern for how each operation will be wrapped
                         # (e.g: '({})' --> '(op1 AND op2)')
                operations:     # The operations to build
                  <opname>:     # e.g: AND
                    - <op1>    # e.g:
                               # 'sensingStartDate:[{startTimeFromAscendingNode}Z TO *]'
                    - <op2>    # e.g:
                        # 'sensingStopDate:[* TO {completionTimeFromAscendingNode}Z]'
                    ...
                  ...
            ...

          With the structure above, each operation will become a string of the form:
          '(<op1> <opname> <op2>)', then the operations will be joined together using
          the union string and finally if the number of operations is greater than 1,
          they will be wrapped as specified by the wrapper config key.

    The search plugins of this kind can detect when a metadata mapping is "query-able",
    and get the semantics of how to format the query string parameter that enables to
    make a query on the corresponding metadata. To make a metadata query-able, just
    configure it in the metadata mapping to be a list of 2 items, the first one being
    the specification of the query string search formatting. The later is a string
    following the specification of Python string formatting, with a special behaviour
    added to it. For example, an entry in the metadata mapping of this kind::

        completionTimeFromAscendingNode:
            - 'f=acquisition.endViewingDate:lte:{completionTimeFromAscendingNode#timestamp}'
            - '$.properties.acquisition.endViewingDate'

    means that the search url will have a query string parameter named *"f"* with a
    value of *"acquisition.endViewingDate:lte:1543922280.0"* if the search was done
    with the value of ``completionTimeFromAscendingNode`` being
    ``2018-12-04T12:18:00``. What happened is that
    ``{completionTimeFromAscendingNode#timestamp}`` was replaced with the timestamp
    of the value of ``completionTimeFromAscendingNode``. This example shows all there
    is to know about the semantics of the query string formatting introduced by this
    plugin: any eodag search parameter can be referenced in the query string
    with an additional optional conversion function that is separated from it by a
    ``#`` (see :func:`~eodag.utils.format_metadata` for further details on the
    available converters). Note that for the values in the
    ``free_text_search_operations`` configuration parameter follow the same rule.

    :param provider: An eodag providers configuration dictionary
    :type provider: dict
    :param config: Path to the user configuration file
    :type config: str
    """

    extract_properties = {"xml": properties_from_xml, "json": properties_from_json}

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(QueryStringSearch, self).__init__(provider, config)
        self.config.__dict__.setdefault("result_type", "json")
        self.config.__dict__.setdefault("results_entry", "features")
        self.config.__dict__.setdefault("pagination", {})
        self.config.__dict__.setdefault("free_text_search_operations", {})
        self.search_urls: List[str] = []
        self.query_params: Dict[str, str] = dict()
        self.query_string = ""
        self.next_page_url = None
        self.next_page_query_obj = None
        self.next_page_merge = None
        # parse jsonpath on init: pagination
        if (
            self.config.result_type == "json"
            and "total_items_nb_key_path" in self.config.pagination
        ):
            self.config.pagination["total_items_nb_key_path"] = string_to_jsonpath(
                self.config.pagination["total_items_nb_key_path"]
            )
        if (
            self.config.result_type == "json"
            and "next_page_url_key_path" in self.config.pagination
        ):
            self.config.pagination["next_page_url_key_path"] = string_to_jsonpath(
                self.config.pagination.get("next_page_url_key_path", None)
            )
        if (
            self.config.result_type == "json"
            and "next_page_query_obj_key_path" in self.config.pagination
        ):
            self.config.pagination["next_page_query_obj_key_path"] = string_to_jsonpath(
                self.config.pagination.get("next_page_query_obj_key_path", None)
            )
        if (
            self.config.result_type == "json"
            and "next_page_merge_key_path" in self.config.pagination
        ):
            self.config.pagination["next_page_merge_key_path"] = string_to_jsonpath(
                self.config.pagination.get("next_page_merge_key_path", None)
            )

        # parse jsonpath on init: product types discovery
        if (
            getattr(self.config, "discover_product_types", {}).get(
                "results_entry", None
            )
            and getattr(self.config, "discover_product_types", {}).get(
                "result_type", None
            )
            == "json"
        ):
            self.config.discover_product_types["results_entry"] = string_to_jsonpath(
                self.config.discover_product_types["results_entry"], force=True
            )
            self.config.discover_product_types[
                "generic_product_type_id"
            ] = mtd_cfg_as_conversion_and_querypath(
                {"foo": self.config.discover_product_types["generic_product_type_id"]}
            )[
                "foo"
            ]
            self.config.discover_product_types[
                "generic_product_type_parsable_properties"
            ] = mtd_cfg_as_conversion_and_querypath(
                self.config.discover_product_types[
                    "generic_product_type_parsable_properties"
                ]
            )
            self.config.discover_product_types[
                "generic_product_type_parsable_metadata"
            ] = mtd_cfg_as_conversion_and_querypath(
                self.config.discover_product_types[
                    "generic_product_type_parsable_metadata"
                ]
            )
            if (
                "single_product_type_parsable_metadata"
                in self.config.discover_product_types
            ):
                self.config.discover_product_types[
                    "single_product_type_parsable_metadata"
                ] = mtd_cfg_as_conversion_and_querypath(
                    self.config.discover_product_types[
                        "single_product_type_parsable_metadata"
                    ]
                )

        # parse jsonpath on init: queryables discovery
        if (
            getattr(self.config, "discover_queryables", {}).get("results_entry", None)
            and getattr(self.config, "discover_queryables", {}).get("result_type", None)
            == "json"
        ):
            self.config.discover_queryables["results_entry"] = string_to_jsonpath(
                self.config.discover_queryables["results_entry"], force=True
            )

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
                    other_product_type_mtd_mapping = (
                        mtd_cfg_as_conversion_and_querypath(
                            other_product_type_def_params.get("metadata_mapping", {})
                        )
                    )
                    # updated mapping at the end
                    for metadata, mapping in other_product_type_mtd_mapping.items():
                        product_type_metadata_mapping.pop(metadata, None)
                        product_type_metadata_mapping[metadata] = mapping

                # from current product, updated mapping at the end
                for metadata, mapping in self.config.products[product_type][
                    "metadata_mapping"
                ].items():
                    product_type_metadata_mapping.pop(metadata, None)
                    product_type_metadata_mapping[metadata] = mapping

                self.config.products[product_type][
                    "metadata_mapping"
                ] = product_type_metadata_mapping

    def clear(self) -> None:
        """Clear search context"""
        super().clear()
        self.search_urls.clear()
        self.query_params.clear()
        self.query_string = ""
        self.next_page_url = None
        self.next_page_query_obj = None
        self.next_page_merge = None

    def discover_product_types(self, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """Fetch product types list from provider using `discover_product_types` conf

        :returns: configuration dict containing fetched product types information
        :rtype: (optional) dict
        """
        try:
            prep = PreparedSearch()

            prep.url = cast(
                str,
                self.config.discover_product_types["fetch_url"].format(
                    **self.config.__dict__
                ),
            )

            # get auth if available
            if "auth" in kwargs:
                prep.auth = kwargs.pop("auth")

            # try updating fetch_url qs using productType
            fetch_qs_dict = {}
            if "single_collection_fetch_qs" in self.config.discover_product_types:
                try:
                    fetch_qs = self.config.discover_product_types[
                        "single_collection_fetch_qs"
                    ].format(**kwargs)
                    fetch_qs_dict = dict(parse_qsl(fetch_qs))
                except KeyError:
                    pass
            if fetch_qs_dict:
                url_parse = urlparse(prep.url)
                query = url_parse.query
                url_dict = dict(parse_qsl(query))
                url_dict.update(fetch_qs_dict)
                url_new_query = urlencode(url_dict)
                url_parse = url_parse._replace(query=url_new_query)
                prep.url = urlunparse(url_parse)

            prep.info_message = "Fetching product types: {}".format(prep.url)
            prep.exception_message = (
                "Skipping error while fetching product types for " "{} {} instance:"
            ).format(self.provider, self.__class__.__name__)

            response = QueryStringSearch._request(self, prep)
        except (RequestError, KeyError, AttributeError):
            return None
        else:
            try:
                conf_update_dict: Dict[str, Any] = {
                    "providers_config": {},
                    "product_types_config": {},
                }
                if self.config.discover_product_types["result_type"] == "json":
                    resp_as_json = response.json()
                    # extract results from response json
                    result = [
                        match.value
                        for match in self.config.discover_product_types[
                            "results_entry"
                        ].find(resp_as_json)
                    ]
                    if result and isinstance(result[0], list):
                        result = result[0]

                    for product_type_result in result:
                        # providers_config extraction
                        extracted_mapping = properties_from_json(
                            product_type_result,
                            dict(
                                self.config.discover_product_types[
                                    "generic_product_type_parsable_properties"
                                ],
                                **{
                                    "generic_product_type_id": self.config.discover_product_types[
                                        "generic_product_type_id"
                                    ]
                                },
                            ),
                        )
                        generic_product_type_id = extracted_mapping.pop(
                            "generic_product_type_id"
                        )
                        conf_update_dict["providers_config"][
                            generic_product_type_id
                        ] = dict(
                            extracted_mapping,
                            **self.config.discover_product_types.get(
                                "generic_product_type_unparsable_properties", {}
                            ),
                        )
                        # product_types_config extraction
                        conf_update_dict["product_types_config"][
                            generic_product_type_id
                        ] = properties_from_json(
                            product_type_result,
                            self.config.discover_product_types[
                                "generic_product_type_parsable_metadata"
                            ],
                        )

                        if (
                            "single_product_type_parsable_metadata"
                            in self.config.discover_product_types
                        ):
                            collection_data = self._get_product_type_metadata_from_single_collection_endpoint(
                                generic_product_type_id
                            )
                            conf_update_dict["product_types_config"][
                                generic_product_type_id
                            ].update(collection_data)

                        # update keywords
                        keywords_fields = [
                            "instrument",
                            "platform",
                            "platformSerialIdentifier",
                            "processingLevel",
                            "keywords",
                        ]
                        keywords_values_str = ",".join(
                            [generic_product_type_id]
                            + [
                                str(
                                    conf_update_dict["product_types_config"][
                                        generic_product_type_id
                                    ][kf]
                                )
                                for kf in keywords_fields
                                if conf_update_dict["product_types_config"][
                                    generic_product_type_id
                                ][kf]
                                != NOT_AVAILABLE
                            ]
                        )
                        # cleanup str list from unwanted characters
                        keywords_values_str = (
                            keywords_values_str.replace(", ", ",")
                            .replace(" ", "-")
                            .replace("_", "-")
                            .lower()
                        )
                        keywords_values_str = re.sub(
                            r"[\[\]'\"]", "", keywords_values_str
                        )
                        # sorted list of unique lowercase keywords
                        keywords_values_str = ",".join(
                            sorted(set(keywords_values_str.split(",")))
                        )
                        conf_update_dict["product_types_config"][
                            generic_product_type_id
                        ]["keywords"] = keywords_values_str
            except KeyError as e:
                logger.warning(
                    "Incomplete %s discover_product_types configuration: %s",
                    self.provider,
                    e,
                )
                return None
        conf_update_dict["product_types_config"] = dict_items_recursive_apply(
            conf_update_dict["product_types_config"],
            lambda k, v: v if v != NOT_AVAILABLE else None,
        )
        return conf_update_dict

    def _get_product_type_metadata_from_single_collection_endpoint(
        self, product_type: str
    ) -> Dict[str, Any]:
        """
        retrieves additional product type information from an endpoint returning data for a single collection
        :param product_type: product type
        :type product_type: str
        :return: product types and their metadata
        :rtype: Dict[str, Any]
        """
        single_collection_url = self.config.discover_product_types[
            "single_collection_fetch_url"
        ].format(productType=product_type)
        resp = QueryStringSearch._request(
            self,
            PreparedSearch(
                url=single_collection_url,
                info_message="Fetching data for product type product type: {}".format(
                    product_type
                ),
                exception_message="Skipping error while fetching product types for "
                "{} {} instance:".format(self.provider, self.__class__.__name__),
            ),
        )
        product_data = resp.json()
        return properties_from_json(
            product_data,
            self.config.discover_product_types["single_product_type_parsable_metadata"],
        )

    def discover_queryables(
        self, **kwargs: Any
    ) -> Optional[Dict[str, Annotated[Any, FieldInfo]]]:
        """Fetch queryables list from provider using its constraints file

        :param kwargs: additional filters for queryables (`productType` and other search
                       arguments)
        :type kwargs: Any
        :returns: fetched queryable parameters dict
        :rtype: Optional[Dict[str, Annotated[Any, FieldInfo]]]
        """
        product_type = kwargs.pop("productType", None)
        if not product_type:
            return {}
        constraints_file_url = getattr(self.config, "constraints_file_url", "")
        if not constraints_file_url:
            return {}

        constraints_file_dataset_key = getattr(
            self.config, "constraints_file_dataset_key", "dataset"
        )
        provider_product_type = self.config.products.get(product_type, {}).get(
            constraints_file_dataset_key, None
        )

        # defaults
        default_queryables = self._get_defaults_as_queryables(product_type)
        # remove unwanted queryables
        for param in getattr(self.config, "remove_from_queryables", []):
            default_queryables.pop(param, None)

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
                        constraint_params[key] = {"enum": set(constraint[key])}
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
                get_queryable_from_provider(
                    json_param, self.get_metadata_mapping(product_type)
                )
                or json_param
            )
            default = kwargs.get(param, None) or self.config.products.get(
                product_type, {}
            ).get(param, None)
            annotated_def = json_field_definition_to_python(
                json_mtd, default_value=default, required=True
            )
            field_definitions[param] = get_args(annotated_def)

        python_queryables = create_model("m", **field_definitions).model_fields
        return dict(default_queryables, **model_fields_to_annotated(python_queryables))

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> Tuple[List[EOProduct], Optional[int]]:
        """Perform a search on an OpenSearch-like interface

        :param prep: Object collecting needed information for search.
        :type prep: :class:`~eodag.plugins.search.PreparedSearch`
        """
        count = prep.count
        product_type = kwargs.get("productType", prep.product_type)
        if product_type == GENERIC_PRODUCT_TYPE:
            logger.warning(
                "GENERIC_PRODUCT_TYPE is not a real product_type and should only be used internally as a template"
            )
            return ([], 0) if prep.count else ([], None)

        sort_by_arg: Optional[SortByList] = self.get_sort_by_arg(kwargs)
        prep.sort_by_qs, _ = (
            ("", {}) if sort_by_arg is None else self.build_sort_by(sort_by_arg)
        )

        provider_product_type = self.map_product_type(product_type)
        keywords = {k: v for k, v in kwargs.items() if k != "auth" and v is not None}
        keywords["productType"] = (
            provider_product_type
            if (provider_product_type and provider_product_type != GENERIC_PRODUCT_TYPE)
            else product_type
        )

        # provider product type specific conf
        prep.product_type_def_params = (
            self.get_product_type_def_params(product_type, **kwargs)
            if product_type is not None
            else {}
        )

        # if product_type_def_params is set, remove product_type as it may conflict with this conf
        if prep.product_type_def_params:
            keywords.pop("productType", None)

        if self.config.metadata_mapping:
            product_type_metadata_mapping = dict(
                self.config.metadata_mapping,
                **prep.product_type_def_params.get("metadata_mapping", {}),
            )
            keywords.update(
                {
                    k: v
                    for k, v in prep.product_type_def_params.items()
                    if k not in keywords.keys()
                    and k in product_type_metadata_mapping.keys()
                    and isinstance(product_type_metadata_mapping[k], list)
                }
            )

        if product_type is None:
            raise ValidationError("Required productType is missing")

        qp, qs = self.build_query_string(product_type, **keywords)

        prep.query_params = qp
        prep.query_string = qs
        prep.search_urls, total_items = self.collect_search_urls(
            prep,
            **kwargs,
        )
        if not count and hasattr(prep, "total_items_nb"):
            # do not try to extract total_items from search results if count is False
            del prep.total_items_nb
            del prep.need_count

        provider_results = self.do_search(prep, **kwargs)
        if count and total_items is None and hasattr(prep, "total_items_nb"):
            total_items = prep.total_items_nb

        raw_search_result = RawSearchResult(provider_results)
        raw_search_result.query_params = prep.query_params
        raw_search_result.product_type_def_params = prep.product_type_def_params

        eo_products = self.normalize_results(raw_search_result, **kwargs)
        return eo_products, total_items

    @_deprecated(
        reason="Simply run `self.config.metadata_mapping.update(metadata_mapping)` instead",
        version="2.10.0",
    )
    def update_metadata_mapping(self, metadata_mapping: Dict[str, Any]) -> None:
        """Update plugin metadata_mapping with input metadata_mapping configuration"""
        if self.config.metadata_mapping:
            self.config.metadata_mapping.update(metadata_mapping)

    def build_query_string(
        self, product_type: str, **kwargs: Any
    ) -> Tuple[Dict[str, Any], str]:
        """Build The query string using the search parameters"""
        logger.debug("Building the query string that will be used for search")
        query_params = format_query_params(product_type, self.config, kwargs)

        # Build the final query string, in one go without quoting it
        # (some providers do not operate well with urlencoded and quoted query strings)
        quote_via: Callable[[Any, str, str, str], str] = lambda x, *_args, **_kwargs: x
        return (
            query_params,
            urlencode(query_params, doseq=True, quote_via=quote_via),
        )

    def collect_search_urls(
        self,
        prep: PreparedSearch = PreparedSearch(page=None, items_per_page=None),
        **kwargs: Any,
    ) -> Tuple[List[str], Optional[int]]:
        """Build paginated urls"""
        page = prep.page
        items_per_page = prep.items_per_page
        count = prep.count

        urls = []
        total_results = 0 if count else None

        # use only sort_by parameters for search, not for count
        #  and remove potential leading '&'
        qs_with_sort = (prep.query_string + getattr(prep, "sort_by_qs", "")).strip("&")
        # append count template if needed
        if count:
            qs_with_sort += self.config.pagination.get("count_tpl", "")

        if "count_endpoint" not in self.config.pagination:
            # if count_endpoint is not set, total_results should be extracted from search result
            total_results = None
            prep.need_count = True
            prep.total_items_nb = None

        for collection in self.get_collections(prep, **kwargs):
            # skip empty collection if one is required in api_endpoint
            if "{collection}" in self.config.api_endpoint and not collection:
                continue
            search_endpoint = self.config.api_endpoint.rstrip("/").format(
                collection=collection
            )
            if page is not None and items_per_page is not None:
                page = page - 1 + self.config.pagination.get("start_page", 1)
                if count:
                    count_endpoint = self.config.pagination.get(
                        "count_endpoint", ""
                    ).format(collection=collection)
                    if count_endpoint:
                        count_url = "{}?{}".format(count_endpoint, prep.query_string)
                        _total_results = (
                            self.count_hits(
                                count_url, result_type=self.config.result_type
                            )
                            or 0
                        )
                        if getattr(self.config, "merge_responses", False):
                            total_results = _total_results
                        else:
                            total_results = (
                                0 if total_results is None else total_results
                            )
                            total_results += _total_results or 0
                next_url = self.config.pagination["next_page_url_tpl"].format(
                    url=search_endpoint,
                    search=qs_with_sort,
                    items_per_page=items_per_page,
                    page=page,
                    skip=(page - 1) * items_per_page,
                    skip_base_1=(page - 1) * items_per_page + 1,
                )
            else:
                next_url = "{}?{}".format(search_endpoint, qs_with_sort)
            urls.append(next_url)
        return urls, total_results

    def do_search(
        self, prep: PreparedSearch = PreparedSearch(items_per_page=None), **kwargs: Any
    ) -> List[Any]:
        """Perform the actual search request.

        If there is a specified number of items per page, return the results as soon
        as this number is reached

        :param prep: Object collecting needed information for search.
        :type prep: :class:`~eodag.plugins.search.PreparedSearch`
        """
        items_per_page = prep.items_per_page
        total_items_nb = 0
        if getattr(prep, "need_count", False):
            # extract total_items_nb from search results
            if self.config.result_type == "json":
                total_items_nb_key_path_parsed = self.config.pagination[
                    "total_items_nb_key_path"
                ]

        results: List[Any] = []
        for search_url in prep.search_urls:
            single_search_prep = copy_copy(prep)
            single_search_prep.url = search_url
            single_search_prep.info_message = "Sending search request: {}".format(
                search_url
            )
            single_search_prep.exception_message = (
                "Skipping error while searching for {} {} "
                "instance:".format(self.provider, self.__class__.__name__)
            )
            response = self._request(single_search_prep)
            next_page_url_key_path = self.config.pagination.get(
                "next_page_url_key_path", None
            )
            next_page_query_obj_key_path = self.config.pagination.get(
                "next_page_query_obj_key_path", None
            )
            next_page_merge_key_path = self.config.pagination.get(
                "next_page_merge_key_path", None
            )
            if self.config.result_type == "xml":
                root_node = etree.fromstring(response.content)
                namespaces = {k or "ns": v for k, v in root_node.nsmap.items()}
                results_xpath = root_node.xpath(
                    self.config.results_entry or "//ns:entry", namespaces=namespaces
                )
                result = (
                    [etree.tostring(element_or_tree=entry) for entry in results_xpath]
                    if isinstance(results_xpath, Iterable)
                    else []
                )

                if next_page_url_key_path or next_page_query_obj_key_path:
                    raise NotImplementedError(
                        "Setting the next page url from an XML response has not "
                        "been implemented yet"
                    )
                if getattr(prep, "need_count", False):
                    # extract total_items_nb from search results
                    try:
                        total_nb_results_xpath = root_node.xpath(
                            str(self.config.pagination["total_items_nb_key_path"]),
                            namespaces={
                                k or "ns": v for k, v in root_node.nsmap.items()
                            },
                        )
                        total_nb_results = (
                            total_nb_results_xpath
                            if isinstance(total_nb_results_xpath, Iterable)
                            else []
                        )[0]
                        _total_items_nb = int(total_nb_results)

                        if getattr(self.config, "merge_responses", False):
                            total_items_nb = _total_items_nb or 0
                        else:
                            total_items_nb += _total_items_nb or 0
                    except IndexError:
                        logger.debug(
                            "Could not extract total_items_nb from search results"
                        )
            else:
                resp_as_json = response.json()
                if next_page_url_key_path:
                    path_parsed = next_page_url_key_path
                    try:
                        self.next_page_url = path_parsed.find(resp_as_json)[0].value
                        logger.debug(
                            "Next page URL collected and set for the next search",
                        )
                    except IndexError:
                        logger.debug("Next page URL could not be collected")
                if next_page_query_obj_key_path:
                    path_parsed = next_page_query_obj_key_path
                    try:
                        self.next_page_query_obj = path_parsed.find(resp_as_json)[
                            0
                        ].value
                        logger.debug(
                            "Next page Query-object collected and set for the next search",
                        )
                    except IndexError:
                        logger.debug("Next page Query-object could not be collected")
                if next_page_merge_key_path:
                    path_parsed = next_page_merge_key_path
                    try:
                        self.next_page_merge = path_parsed.find(resp_as_json)[0].value
                        logger.debug(
                            "Next page merge collected and set for the next search",
                        )
                    except IndexError:
                        logger.debug("Next page merge could not be collected")

                results_entry = string_to_jsonpath(
                    self.config.results_entry, force=True
                )
                try:
                    result = results_entry.find(resp_as_json)[0].value
                except Exception:
                    result = []
                if not isinstance(result, list):
                    result = [result]

                if getattr(prep, "need_count", False):
                    # extract total_items_nb from search results
                    try:
                        _total_items_nb = total_items_nb_key_path_parsed.find(
                            resp_as_json
                        )[0].value
                        if getattr(self.config, "merge_responses", False):
                            total_items_nb = _total_items_nb or 0
                        else:
                            total_items_nb += _total_items_nb or 0
                    except IndexError:
                        logger.debug(
                            "Could not extract total_items_nb from search results"
                        )
            if getattr(self.config, "merge_responses", False):
                results = (
                    [dict(r, **result[i]) for i, r in enumerate(results)]
                    if results
                    else result
                )
            else:
                results.extend(result)
            if getattr(prep, "need_count", False):
                prep.total_items_nb = total_items_nb
                del prep.need_count
            # remove prep.total_items_nb if value could not be extracted from response
            if (
                hasattr(prep, "total_items_nb")
                and not prep.total_items_nb
                and len(results) > 0
            ):
                del prep.total_items_nb
            if items_per_page is not None and len(results) == items_per_page:
                return results
        return results

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> List[EOProduct]:
        """Build EOProducts from provider results"""
        normalize_remaining_count = len(results)
        logger.debug(
            "Adapting %s plugin results to eodag product representation"
            % normalize_remaining_count
        )
        products: List[EOProduct] = []
        for result in results:
            product = EOProduct(
                self.provider,
                QueryStringSearch.extract_properties[self.config.result_type](
                    result,
                    self.get_metadata_mapping(kwargs.get("productType")),
                    discovery_config=getattr(self.config, "discover_metadata", {}),
                ),
                **kwargs,
            )
            # use product_type_config as default properties
            product.properties = dict(
                getattr(self.config, "product_type_config", {}), **product.properties
            )
            # move assets from properties to product's attr
            product.assets.update(product.properties.pop("assets", {}))
            products.append(product)
        return products

    def count_hits(self, count_url: str, result_type: Optional[str] = "json") -> int:
        """Count the number of results satisfying some criteria"""
        # Handle a very annoying special case :'(
        url = count_url.replace("$format=json&", "")
        response = self._request(
            PreparedSearch(
                url=url,
                info_message="Sending count request: {}".format(url),
                exception_message="Skipping error while counting results for {} {} "
                "instance:".format(self.provider, self.__class__.__name__),
            )
        )
        if result_type == "xml":
            root_node = etree.fromstring(response.content)
            total_nb_results = root_node.xpath(
                self.config.pagination["total_items_nb_key_path"],
                namespaces={k or "ns": v for k, v in root_node.nsmap.items()},
            )[0]
            total_results = int(total_nb_results)
        else:
            count_results = response.json()
            if isinstance(count_results, dict):
                path_parsed = self.config.pagination["total_items_nb_key_path"]
                total_results = path_parsed.find(count_results)[0].value
            else:  # interpret the result as a raw int
                total_results = int(count_results)
        return total_results

    def get_collections(
        self, prep: PreparedSearch, **kwargs: Any
    ) -> Tuple[Set[Dict[str, Any]], ...]:
        """Get the collection to which the product belongs"""
        # See https://earth.esa.int/web/sentinel/missions/sentinel-2/news/-
        # /asset_publisher/Ac0d/content/change-of
        # -format-for-new-sentinel-2-level-1c-products-starting-on-6-december
        product_type: Optional[str] = kwargs.get("productType")
        if product_type is None and (
            not hasattr(prep, "product_type_def_params")
            or not prep.product_type_def_params
        ):
            collections: Set[Dict[str, Any]] = set()
            collection: Optional[str] = getattr(self.config, "collection", None)
            if collection is None:
                try:
                    for product_type, product_config in self.config.products.items():
                        if product_type != GENERIC_PRODUCT_TYPE:
                            collections.add(product_config["collection"])
                        else:
                            collections.add(
                                format_dict_items(product_config, **kwargs).get(
                                    "collection", ""
                                )
                            )
                except KeyError:
                    collections.add("")
            else:
                collections.add(collection)
            return tuple(collections)

        collection: Optional[str] = getattr(self.config, "collection", None)
        if collection is None:
            collection = (
                prep.product_type_def_params.get("collection", None) or product_type
            )
        return (collection,) if not isinstance(collection, list) else tuple(collection)

    def _request(
        self,
        prep: PreparedSearch,
    ) -> Response:
        url = prep.url
        info_message = prep.info_message
        exception_message = prep.exception_message
        try:
            timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
            ssl_verify = getattr(self.config, "ssl_verify", True)

            ssl_ctx = get_ssl_context(ssl_verify)
            # auth if needed
            kwargs: Dict[str, Any] = {}
            if (
                getattr(self.config, "need_auth", False)
                and hasattr(prep, "auth")
                and callable(prep.auth)
            ):
                kwargs["auth"] = prep.auth
            # requests auto quote url params, without any option to prevent it
            # use urllib instead of requests if req must be sent unquoted

            if hasattr(self.config, "dont_quote"):
                # keep unquoted desired params
                base_url, params = url.split("?") if "?" in url else (url, "")
                qry = quote(params)
                for keep_unquoted in self.config.dont_quote:
                    qry = qry.replace(quote(keep_unquoted), keep_unquoted)

                # prepare req for Response building
                req = requests.Request(
                    method="GET", url=base_url, headers=USER_AGENT, **kwargs
                )
                req_prep = req.prepare()
                req_prep.url = base_url + "?" + qry
                # send urllib req
                if info_message:
                    logger.info(info_message.replace(url, req_prep.url))
                urllib_req = Request(req_prep.url, headers=USER_AGENT)
                urllib_response = urlopen(urllib_req, timeout=timeout, context=ssl_ctx)
                # build Response
                adapter = HTTPAdapter()
                response = cast(
                    Response, adapter.build_response(req_prep, urllib_response)
                )
            else:
                if info_message:
                    logger.info(info_message)
                response = requests.get(
                    url,
                    timeout=timeout,
                    headers=USER_AGENT,
                    verify=ssl_verify,
                    **kwargs,
                )
                response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=timeout) from exc
        except (requests.RequestException, URLError) as err:
            err_msg = err.readlines() if hasattr(err, "readlines") else ""
            if exception_message:
                logger.exception("%s %s" % (exception_message, err_msg))
            else:
                logger.exception(
                    "Skipping error while requesting: %s (provider:%s, plugin:%s): %s",
                    url,
                    self.provider,
                    self.__class__.__name__,
                    err_msg,
                )
            raise RequestError(str(err))
        return response


class ODataV4Search(QueryStringSearch):
    """A specialisation of a QueryStringSearch that does a two step search to retrieve
    all products metadata"""

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(ODataV4Search, self).__init__(provider, config)

        # parse jsonpath on init
        metadata_pre_mapping = getattr(self.config, "metadata_pre_mapping", {})
        metadata_path = metadata_pre_mapping.get("metadata_path", None)
        metadata_path_id = metadata_pre_mapping.get("metadata_path_id", None)
        metadata_path_value = metadata_pre_mapping.get("metadata_path_value", None)
        if metadata_path and metadata_path_id and metadata_path_value:
            self.config.metadata_pre_mapping["metadata_path"] = string_to_jsonpath(
                metadata_path
            )

    def do_search(
        self, prep: PreparedSearch = PreparedSearch(), **kwargs: Any
    ) -> List[Any]:
        """A two step search can be performed if the metadata are not given into the search result"""

        if getattr(self.config, "per_product_metadata_query", False):
            final_result = []
            ssl_verify = getattr(self.config, "ssl_verify", True)
            # Query the products entity set for basic metadata about the product
            for entity in super(ODataV4Search, self).do_search(prep, **kwargs):
                metadata_url = self.get_metadata_search_url(entity)
                try:
                    logger.debug("Sending metadata request: %s", metadata_url)
                    response = requests.get(
                        metadata_url,
                        headers=USER_AGENT,
                        timeout=HTTP_REQ_TIMEOUT,
                        verify=ssl_verify,
                    )
                    response.raise_for_status()
                except requests.exceptions.Timeout as exc:
                    raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
                except requests.RequestException:
                    logger.exception(
                        "Skipping error while searching for %s %s instance:",
                        self.provider,
                        self.__class__.__name__,
                    )
                else:
                    entity.update(
                        {item["id"]: item["value"] for item in response.json()["value"]}
                    )
                    final_result.append(entity)
            return final_result
        else:
            return super(ODataV4Search, self).do_search(prep, **kwargs)

    def get_metadata_search_url(self, entity: Dict[str, Any]) -> str:
        """Build the metadata link for the given entity"""
        return "{}({})/Metadata".format(
            self.config.api_endpoint.rstrip("/"), entity["id"]
        )

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> List[EOProduct]:
        """Build EOProducts from provider results

        If configured, a metadata pre-mapping can be applied to simplify further metadata extraction.
        For example, going from '$.Metadata[?(@.id="foo")].value' to '$.Metadata.foo.value'
        """
        metadata_pre_mapping = getattr(self.config, "metadata_pre_mapping", {})
        metadata_path = metadata_pre_mapping.get("metadata_path", None)
        metadata_path_id = metadata_pre_mapping.get("metadata_path_id", None)
        metadata_path_value = metadata_pre_mapping.get("metadata_path_value", None)

        if metadata_path and metadata_path_id and metadata_path_value:
            # metadata_path already parsed on init
            parsed_metadata_path = metadata_path
            for result in results:
                found_metadata = parsed_metadata_path.find(result)
                if found_metadata:
                    metadata_update = {}
                    for metadata_dict in found_metadata[0].value:
                        metada_id = metadata_dict[metadata_path_id]
                        metada_value = metadata_dict[metadata_path_value]
                        metadata_update[metada_id] = metada_value
                    parsed_metadata_path.update(result, metadata_update)

        # once metadata pre-mapping applied execute QueryStringSearch.normalize_results
        products = super(ODataV4Search, self).normalize_results(results, **kwargs)

        return products


class PostJsonSearch(QueryStringSearch):
    """A specialisation of a QueryStringSearch that uses POST method"""

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> Tuple[List[EOProduct], Optional[int]]:
        """Perform a search on an OpenSearch-like interface"""
        product_type = kwargs.get("productType", None)
        count = prep.count
        # remove "product_type" from search args if exists for compatibility with QueryStringSearch methods
        kwargs.pop("product_type", None)
        sort_by_arg: Optional[SortByList] = self.get_sort_by_arg(kwargs)
        _, sort_by_qp = (
            ("", {}) if sort_by_arg is None else self.build_sort_by(sort_by_arg)
        )
        provider_product_type = self.map_product_type(product_type)
        _dc_qs = kwargs.pop("_dc_qs", None)
        if _dc_qs is not None:
            qs = unquote_plus(unquote_plus(_dc_qs))
            qp = geojson.loads(qs)

            # provider product type specific conf
            prep.product_type_def_params = self.get_product_type_def_params(
                product_type, **kwargs
            )
        else:
            keywords = {
                k: v for k, v in kwargs.items() if k != "auth" and v is not None
            }

            if provider_product_type and provider_product_type != GENERIC_PRODUCT_TYPE:
                keywords["productType"] = provider_product_type
            elif product_type:
                keywords["productType"] = product_type

            # provider product type specific conf
            prep.product_type_def_params = self.get_product_type_def_params(
                product_type, **kwargs
            )

            # Add to the query, the queryable parameters set in the provider product type definition
            keywords.update(
                {
                    k: v
                    for k, v in prep.product_type_def_params.items()
                    if k not in keywords.keys()
                    and k in self.config.metadata_mapping.keys()
                    and isinstance(self.config.metadata_mapping[k], list)
                }
            )

            qp, _ = self.build_query_string(product_type, **keywords)

        for query_param, query_value in qp.items():
            if (
                query_param
                in self.config.products.get(product_type, {}).get(
                    "specific_qssearch", {"parameters": []}
                )["parameters"]
            ):
                # config backup
                plugin_config_backup = yaml.dump(self.config)

                self.config.api_endpoint = query_value
                self.config.products[product_type][
                    "metadata_mapping"
                ] = mtd_cfg_as_conversion_and_querypath(
                    self.config.products[product_type]["specific_qssearch"][
                        "metadata_mapping"
                    ]
                )
                self.config.results_entry = self.config.products[product_type][
                    "specific_qssearch"
                ]["results_entry"]
                self.config.collection = self.config.products[product_type][
                    "specific_qssearch"
                ].get("collection", None)
                self.config.merge_responses = self.config.products[product_type][
                    "specific_qssearch"
                ].get("merge_responses", None)

                self.count_hits = lambda *x, **y: 1
                self._request = super(PostJsonSearch, self)._request

                try:
                    eo_products, total_items = super(PostJsonSearch, self).query(
                        prep, **kwargs
                    )
                except Exception:
                    raise
                finally:
                    # restore config
                    self.config = yaml.load(
                        plugin_config_backup, self.config.yaml_loader
                    )

                return eo_products, total_items

        # If we were not able to build query params but have queryable search criteria,
        # this means the provider does not support the search criteria given. If so,
        # stop searching right away
        product_type_metadata_mapping = dict(
            self.config.metadata_mapping,
            **prep.product_type_def_params.get("metadata_mapping", {}),
        )
        if not qp and any(
            k
            for k in keywords.keys()
            if isinstance(product_type_metadata_mapping.get(k, []), list)
        ):
            return ([], 0) if prep.count else ([], None)
        prep.query_params = dict(qp, **sort_by_qp)
        prep.search_urls, total_items = self.collect_search_urls(prep, **kwargs)
        if not count and getattr(prep, "need_count", False):
            # do not try to extract total_items from search results if count is False
            del prep.total_items_nb
            del prep.need_count
        provider_results = self.do_search(prep, **kwargs)
        if count and total_items is None and hasattr(prep, "total_items_nb"):
            total_items = prep.total_items_nb

        raw_search_result = RawSearchResult(provider_results)
        raw_search_result.query_params = prep.query_params
        raw_search_result.product_type_def_params = prep.product_type_def_params

        eo_products = self.normalize_results(raw_search_result, **kwargs)
        return eo_products, total_items

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> List[EOProduct]:
        """Build EOProducts from provider results"""
        normalized = super().normalize_results(results, **kwargs)
        for product in normalized:
            if "downloadLink" in product.properties:
                decoded_link = unquote(product.properties["downloadLink"])
                if decoded_link[0] == "{":  # not a url but a dict
                    default_values = deepcopy(
                        self.config.products.get(product.product_type, {})
                    )
                    default_values.pop("metadata_mapping", None)
                    searched_values = orjson.loads(decoded_link)
                    _dc_qs = orjson.dumps(
                        format_query_params(
                            product.product_type,
                            self.config,
                            {**default_values, **searched_values},
                        )
                    )
                    product.properties["_dc_qs"] = quote_plus(_dc_qs)

            # workaround to add product type to wekeo cmems order links
            if (
                "orderLink" in product.properties
                and "productType" in product.properties["orderLink"]
            ):
                product.properties["orderLink"] = product.properties[
                    "orderLink"
                ].replace("productType", product.product_type)
        return normalized

    def collect_search_urls(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> Tuple[List[str], Optional[int]]:
        """Adds pagination to query parameters, and auth to url"""
        page = prep.page
        items_per_page = prep.items_per_page
        count = prep.count
        urls: List[str] = []
        total_results = 0 if count else None

        if "count_endpoint" not in self.config.pagination:
            # if count_endpoint is not set, total_results should be extracted from search result
            total_results = None
            prep.need_count = True
            prep.total_items_nb = None

        if prep.auth_plugin is not None and hasattr(prep.auth_plugin, "config"):
            auth_conf_dict = getattr(prep.auth_plugin.config, "credentials", {})
        else:
            auth_conf_dict = {}
        for collection in self.get_collections(prep, **kwargs):
            try:
                search_endpoint: str = self.config.api_endpoint.rstrip("/").format(
                    **dict(collection=collection, **auth_conf_dict)
                )
            except KeyError as e:
                provider = prep.auth_plugin.provider if prep.auth_plugin else ""
                raise MisconfiguredError(
                    "Missing %s in %s configuration" % (",".join(e.args), provider)
                )
            if page is not None and items_per_page is not None:
                page = page - 1 + self.config.pagination.get("start_page", 1)
                if count:
                    count_endpoint = self.config.pagination.get(
                        "count_endpoint", ""
                    ).format(**dict(collection=collection, **auth_conf_dict))
                    if count_endpoint:
                        _total_results = self.count_hits(
                            count_endpoint, result_type=self.config.result_type
                        )
                        if getattr(self.config, "merge_responses", False):
                            total_results = _total_results or 0
                        else:
                            total_results += _total_results or 0
                if "next_page_query_obj" in self.config.pagination and isinstance(
                    self.config.pagination["next_page_query_obj"], str
                ):
                    # next_page_query_obj needs to be parsed
                    next_page_query_obj = self.config.pagination[
                        "next_page_query_obj"
                    ].format(
                        items_per_page=items_per_page,
                        page=page,
                        skip=(page - 1) * items_per_page,
                        skip_base_1=(page - 1) * items_per_page + 1,
                    )
                    update_nested_dict(
                        prep.query_params, orjson.loads(next_page_query_obj)
                    )

            urls.append(search_endpoint)
        return urls, total_results

    def _request(
        self,
        prep: PreparedSearch,
    ) -> Response:
        url = prep.url
        info_message = prep.info_message
        exception_message = prep.exception_message
        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
        ssl_verify = getattr(self.config, "ssl_verify", True)
        try:
            # auth if needed
            RequestsKwargs = TypedDict(
                "RequestsKwargs", {"auth": AuthBase}, total=False
            )
            kwargs: RequestsKwargs = {}
            if (
                getattr(self.config, "need_auth", False)
                and hasattr(prep, "auth")
                and callable(prep.auth)
            ):
                kwargs["auth"] = prep.auth

            # perform the request using the next page arguments if they are defined
            if getattr(self, "next_page_query_obj", None):
                prep.query_params = self.next_page_query_obj
            if info_message:
                logger.info(info_message)
            logger.debug("Query parameters: %s" % prep.query_params)
            logger.debug("Query kwargs: %s" % kwargs)
            response = requests.post(
                url,
                json=prep.query_params,
                headers=USER_AGENT,
                timeout=timeout,
                verify=ssl_verify,
                **kwargs,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=timeout) from exc
        except (requests.RequestException, URLError) as err:
            # check if error is identified as auth_error in provider conf
            auth_errors = getattr(self.config, "auth_error_code", [None])
            if not isinstance(auth_errors, list):
                auth_errors = [auth_errors]
            if (
                hasattr(err.response, "status_code")
                and err.response.status_code in auth_errors
            ):
                raise AuthenticationError(
                    "HTTP Error {} returned:\n{}\nPlease check your credentials for {}".format(
                        err.response.status_code,
                        err.response.text.strip(),
                        self.provider,
                    )
                )
            if exception_message:
                logger.exception(exception_message)
            else:
                logger.exception(
                    "Skipping error while requesting: %s (provider:%s, plugin:%s):",
                    url,
                    self.provider,
                    self.__class__.__name__,
                )
            if "response" in locals():
                logger.debug(response.content)
            error_text = str(err)
            if getattr(err, "response", None) is not None:
                error_text = err.response.text
            raise RequestError(error_text) from err
        return response


class StacSearch(PostJsonSearch):
    """A specialisation of a QueryStringSearch that uses generic STAC configuration"""

    def __init__(self, provider: str, config: PluginConfig) -> None:
        # backup results_entry overwritten by init
        results_entry = config.results_entry

        super(StacSearch, self).__init__(provider, config)

        # restore results_entry overwritten by init
        self.config.results_entry = results_entry

    def build_query_string(
        self, product_type: str, **kwargs: Any
    ) -> Tuple[Dict[str, Any], str]:
        """Build The query string using the search parameters"""
        logger.debug("Building the query string that will be used for search")

        # handle opened time intervals
        if any(
            k in kwargs
            for k in ("startTimeFromAscendingNode", "completionTimeFromAscendingNode")
        ):
            kwargs.setdefault("startTimeFromAscendingNode", "..")
            kwargs.setdefault("completionTimeFromAscendingNode", "..")

        query_params = format_query_params(product_type, self.config, kwargs)

        # Build the final query string, in one go without quoting it
        # (some providers do not operate well with urlencoded and quoted query strings)
        quote_via: Callable[[Any, str, str, str], str] = lambda x, *_args, **_kwargs: x
        return (
            query_params,
            urlencode(query_params, doseq=True, quote_via=quote_via),
        )

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
        product_type = kwargs.get("productType", None)
        provider_product_type = (
            self.config.products.get(product_type, {}).get("productType", product_type)
            if product_type
            else None
        )

        try:
            unparsed_fetch_url = (
                self.config.discover_queryables["product_type_fetch_url"]
                if provider_product_type
                else self.config.discover_queryables["fetch_url"]
            )

            fetch_url = unparsed_fetch_url.format(
                provider_product_type=provider_product_type, **self.config.__dict__
            )
            response = QueryStringSearch._request(
                self,
                PreparedSearch(
                    url=fetch_url,
                    info_message="Fetching queryables: {}".format(fetch_url),
                    exception_message="Skipping error while fetching queryables for "
                    "{} {} instance:".format(self.provider, self.__class__.__name__),
                ),
            )
        except (RequestError, KeyError, AttributeError):
            return None
        else:
            json_queryables = dict()
            try:
                resp_as_json = response.json()

                # extract results from response json
                json_queryables = [
                    match.value
                    for match in self.config.discover_queryables["results_entry"].find(
                        resp_as_json
                    )
                ][0]

            except KeyError as e:
                logger.warning(
                    "Incomplete %s discover_queryables configuration: %s",
                    self.provider,
                    e,
                )
            except IndexError:
                logger.info(
                    "No queryable found for %s on %s", product_type, self.provider
                )
                return None

            # convert json results to pydantic model fields
            field_definitions: Dict[str, Any] = dict()
            for json_param, json_mtd in json_queryables.items():
                param = (
                    get_queryable_from_provider(
                        json_param, self.get_metadata_mapping(product_type)
                    )
                    or json_param
                )

                default = kwargs.get(param, None)
                annotated_def = json_field_definition_to_python(
                    json_mtd, default_value=default
                )
                field_definitions[param] = get_args(annotated_def)

            python_queryables = create_model("m", **field_definitions).model_fields

        return model_fields_to_annotated(python_queryables)
