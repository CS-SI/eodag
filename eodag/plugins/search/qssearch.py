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
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple, cast
from urllib.error import URLError
from urllib.request import Request, urlopen

import orjson
import requests
import yaml
from lxml import etree
from pydantic import create_model
from pydantic.fields import FieldInfo
from requests import Response
from requests.adapters import HTTPAdapter

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    format_query_params,
    get_queryable_from_provider,
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
    properties_from_xml,
)
from eodag.plugins.search.base import Search
from eodag.types import json_field_definition_to_python, model_fields_to_annotated_tuple
from eodag.utils import (
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_PAGE,
    GENERIC_PRODUCT_TYPE,
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    Annotated,
    _deprecated,
    deepcopy,
    dict_items_recursive_apply,
    format_dict_items,
    quote,
    string_to_jsonpath,
    update_nested_dict,
    urlencode,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    RequestError,
    TimeOutError,
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

    DEFAULT_ITEMS_PER_PAGE = 10
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

    def discover_product_types(self) -> Optional[Dict[str, Any]]:
        """Fetch product types list from provider using `discover_product_types` conf

        :returns: configuration dict containing fetched product types information
        :rtype: (optional) dict
        """
        try:
            fetch_url = cast(
                str,
                self.config.discover_product_types["fetch_url"].format(
                    **self.config.__dict__
                ),
            )
            response = QueryStringSearch._request(
                self,
                fetch_url,
                info_message="Fetching product types: {}".format(fetch_url),
                exception_message="Skipping error while fetching product types for "
                "{} {} instance:".format(self.provider, self.__class__.__name__),
            )
        except (RequestError, KeyError, AttributeError):
            return None
        else:
            try:
                conf_update_dict = {
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

    def query(
        self,
        product_type: Optional[str] = None,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        page: int = DEFAULT_PAGE,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[EOProduct], Optional[int]]:
        """Perform a search on an OpenSearch-like interface

        :param items_per_page: (optional) The number of results that must appear in one
                               single page
        :type items_per_page: int
        :param page: (optional) The page number to return
        :type page: int
        :param count: (optional) To trigger a count request
        :type count: bool
        """
        product_type = kwargs.get("productType", None)
        if product_type == GENERIC_PRODUCT_TYPE:
            logger.warning(
                "GENERIC_PRODUCT_TYPE is not a real product_type and should only be used internally as a template"
            )
            return [], 0
        # remove "product_type" from search args if exists for compatibility with QueryStringSearch methods
        kwargs.pop("product_type", None)

        provider_product_type = self.map_product_type(product_type)
        keywords = {k: v for k, v in kwargs.items() if k != "auth" and v is not None}
        keywords["productType"] = (
            provider_product_type
            if (provider_product_type and provider_product_type != GENERIC_PRODUCT_TYPE)
            else product_type
        )

        # provider product type specific conf
        self.product_type_def_params = (
            self.get_product_type_def_params(product_type, **kwargs)
            if product_type is not None
            else {}
        )

        # if product_type_def_params is set, remove product_type as it may conflict with this conf
        if self.product_type_def_params:
            keywords.pop("productType", None)

        if self.config.metadata_mapping:
            product_type_metadata_mapping = dict(
                self.config.metadata_mapping,
                **self.product_type_def_params.get("metadata_mapping", {}),
            )
            keywords.update(
                {
                    k: v
                    for k, v in self.product_type_def_params.items()
                    if k not in keywords.keys()
                    and k in product_type_metadata_mapping.keys()
                    and isinstance(product_type_metadata_mapping[k], list)
                }
            )

        qp, qs = self.build_query_string(product_type, **keywords)

        self.query_params = qp
        self.query_string = qs
        self.search_urls, total_items = self.collect_search_urls(
            page=page, items_per_page=items_per_page, count=count, **kwargs
        )
        if not count and hasattr(self, "total_items_nb"):
            # do not try to extract total_items from search results if count is False
            del self.total_items_nb
            del self.need_count

        provider_results = self.do_search(items_per_page=items_per_page, **kwargs)
        if count and total_items is None and hasattr(self, "total_items_nb"):
            total_items = self.total_items_nb
        eo_products = self.normalize_results(provider_results, **kwargs)
        total_items = len(eo_products) if total_items == 0 else total_items
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
        query_params = format_query_params(product_type, self.config, **kwargs)

        # Build the final query string, in one go without quoting it
        # (some providers do not operate well with urlencoded and quoted query strings)
        quote_via: Callable[[Any], str] = lambda x, *_args, **_kwargs: x
        return (
            query_params,
            urlencode(query_params, doseq=True, quote_via=quote_via),
        )

    def collect_search_urls(
        self,
        page: Optional[int] = None,
        items_per_page: Optional[int] = None,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[str], Optional[int]]:
        """Build paginated urls"""
        urls = []
        total_results = 0 if count else None

        if "count_endpoint" not in self.config.pagination:
            # if count_endpoint is not set, total_results should be extracted from search result
            total_results = None
            self.need_count = True
            self.total_items_nb = None

        for collection in self.get_collections(**kwargs):
            # skip empty collection if one is required in api_endpoint
            if "{collection}" in self.config.api_endpoint and not collection:
                continue
            search_endpoint = self.config.api_endpoint.rstrip("/").format(
                collection=collection
            )
            if page is not None and items_per_page is not None:
                if count:
                    count_endpoint = self.config.pagination.get(
                        "count_endpoint", ""
                    ).format(collection=collection)
                    if count_endpoint:
                        count_url = "{}?{}".format(count_endpoint, self.query_string)
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
                    search=self.query_string,
                    items_per_page=items_per_page,
                    page=page,
                    skip=(page - 1) * items_per_page,
                    skip_base_1=(page - 1) * items_per_page + 1,
                )
            else:
                next_url = "{}?{}".format(search_endpoint, self.query_string)
            urls.append(next_url)
        return urls, total_results

    def do_search(
        self, items_per_page: Optional[int] = None, **kwargs: Any
    ) -> List[Any]:
        """Perform the actual search request.

        If there is a specified number of items per page, return the results as soon
        as this number is reached

        :param items_per_page: (optional) The number of items to return for one page
        :type items_per_page: int
        """
        total_items_nb = 0
        if getattr(self, "need_count", False):
            # extract total_items_nb from search results
            if self.config.result_type == "json":
                total_items_nb_key_path_parsed = self.config.pagination[
                    "total_items_nb_key_path"
                ]

        results: List[Any] = []
        for search_url in self.search_urls:
            response = self._request(
                search_url,
                info_message="Sending search request: {}".format(search_url),
                exception_message="Skipping error while searching for {} {} "
                "instance:".format(self.provider, self.__class__.__name__),
            )
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
                if getattr(self, "need_count", False):
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

                if getattr(self, "need_count", False):
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
            if getattr(self, "need_count", False):
                self.total_items_nb = total_items_nb
                del self.need_count
            if items_per_page is not None and len(results) == items_per_page:
                return results
        return results

    def normalize_results(
        self, results: List[Dict[str, Any]], **kwargs: Any
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
            products.append(product)
        return products

    def count_hits(self, count_url: str, result_type: Optional[str] = "json") -> int:
        """Count the number of results satisfying some criteria"""
        # Handle a very annoying special case :'(
        url = count_url.replace("$format=json&", "")
        response = self._request(
            url,
            info_message="Sending count request: {}".format(url),
            exception_message="Skipping error while counting results for {} {} "
            "instance:".format(self.provider, self.__class__.__name__),
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

    def get_collections(self, **kwargs: Any) -> Tuple[Set[Dict[str, Any]], ...]:
        """Get the collection to which the product belongs"""
        # See https://earth.esa.int/web/sentinel/missions/sentinel-2/news/-
        # /asset_publisher/Ac0d/content/change-of
        # -format-for-new-sentinel-2-level-1c-products-starting-on-6-december
        product_type: Optional[str] = kwargs.get("productType")
        if product_type is None and not self.product_type_def_params:
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
                self.product_type_def_params.get("collection", None) or product_type
            )
        return (collection,) if not isinstance(collection, list) else tuple(collection)

    def _request(
        self,
        url: str,
        info_message: Optional[str] = None,
        exception_message: Optional[str] = None,
    ) -> Response:
        try:
            timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
            # auth if needed
            kwargs: Dict[str, Any] = {}
            if (
                getattr(self.config, "need_auth", False)
                and hasattr(self, "auth")
                and callable(self.auth)
            ):
                kwargs["auth"] = self.auth
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
                prep = req.prepare()
                prep.url = base_url + "?" + qry
                # send urllib req
                if info_message:
                    logger.info(info_message.replace(url, prep.url))
                urllib_req = Request(prep.url, headers=USER_AGENT)
                urllib_response = urlopen(urllib_req, timeout=timeout)
                # build Response
                adapter = HTTPAdapter()
                response = cast(Response, adapter.build_response(prep, urllib_response))
            else:
                if info_message:
                    logger.info(info_message)
                response = requests.get(
                    url, timeout=timeout, headers=USER_AGENT, **kwargs
                )
                response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(str(exc))
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


class AwsSearch(QueryStringSearch):
    """A specialisation of RestoSearch that modifies the way the EOProducts are built
    from the search results"""

    def normalize_results(
        self, results: List[Dict[str, Any]], **kwargs: Any
    ) -> List[EOProduct]:
        """Transform metadata from provider representation to eodag representation"""
        normalized: List[EOProduct] = []
        logger.debug("Adapting plugin results to eodag product representation")
        for result in results:
            ref = result["properties"]["title"].split("_")[5]
            year = result["properties"]["completionDate"][0:4]
            month = str(int(result["properties"]["completionDate"][5:7]))
            day = str(int(result["properties"]["completionDate"][8:10]))

            properties = QueryStringSearch.extract_properties[self.config.result_type](
                result, self.get_metadata_mapping(kwargs.get("productType"))
            )

            properties["downloadLink"] = (
                "s3://tiles/{ref[1]}{ref[2]}/{ref[3]}/{ref[4]}{ref[5]}/{year}/"
                "{month}/{day}/0/"
            ).format(**locals())
            normalized.append(EOProduct(self.provider, properties, **kwargs))
        return normalized


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

    def do_search(self, *args: Any, **kwargs: Any) -> List[Any]:
        """A two step search can be performed if the metadata are not given into the search result"""

        if getattr(self.config, "per_product_metadata_query", False):
            final_result = []
            # Query the products entity set for basic metadata about the product
            for entity in super(ODataV4Search, self).do_search(*args, **kwargs):
                metadata_url = self.get_metadata_search_url(entity)
                try:
                    logger.debug("Sending metadata request: %s", metadata_url)
                    response = requests.get(
                        metadata_url, headers=USER_AGENT, timeout=HTTP_REQ_TIMEOUT
                    )
                    response.raise_for_status()
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
            return super(ODataV4Search, self).do_search(*args, **kwargs)

    def get_metadata_search_url(self, entity: Dict[str, Any]) -> str:
        """Build the metadata link for the given entity"""
        return "{}({})/Metadata".format(
            self.config.api_endpoint.rstrip("/"), entity["id"]
        )

    def normalize_results(
        self, results: List[Dict[str, Any]], **kwargs: Any
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
        product_type: Optional[str] = None,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        page: int = DEFAULT_PAGE,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[EOProduct], Optional[int]]:
        """Perform a search on an OpenSearch-like interface"""
        product_type = kwargs.get("productType", None)
        # remove "product_type" from search args if exists for compatibility with QueryStringSearch methods
        kwargs.pop("product_type", None)
        provider_product_type = self.map_product_type(product_type)
        keywords = {k: v for k, v in kwargs.items() if k != "auth" and v is not None}

        if provider_product_type and provider_product_type != GENERIC_PRODUCT_TYPE:
            keywords["productType"] = provider_product_type
        elif product_type:
            keywords["productType"] = product_type

        # provider product type specific conf
        self.product_type_def_params = self.get_product_type_def_params(
            product_type, **kwargs
        )

        # Add to the query, the queryable parameters set in the provider product type definition
        keywords.update(
            {
                k: v
                for k, v in self.product_type_def_params.items()
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
                        items_per_page=items_per_page, page=page, **kwargs
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
            **self.product_type_def_params.get("metadata_mapping", {}),
        )
        if not qp and any(
            k
            for k in keywords.keys()
            if isinstance(product_type_metadata_mapping.get(k, []), list)
        ):
            return [], 0
        self.query_params = qp
        self.search_urls, total_items = self.collect_search_urls(
            page=page, items_per_page=items_per_page, count=count, **kwargs
        )
        if not count and getattr(self, "need_count", False):
            # do not try to extract total_items from search results if count is False
            del self.total_items_nb
            del self.need_count
        provider_results = self.do_search(items_per_page=items_per_page, **kwargs)
        if count and total_items is None and hasattr(self, "total_items_nb"):
            total_items = self.total_items_nb
        eo_products = self.normalize_results(provider_results, **kwargs)
        total_items = len(eo_products) if total_items == 0 else total_items
        return eo_products, total_items

    def collect_search_urls(
        self,
        page: Optional[int] = None,
        items_per_page: Optional[int] = None,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[str], Optional[int]]:
        """Adds pagination to query parameters, and auth to url"""
        urls: List[str] = []
        total_results = 0 if count else None

        if "count_endpoint" not in self.config.pagination:
            # if count_endpoint is not set, total_results should be extracted from search result
            total_results = None
            self.need_count = True
            self.total_items_nb = None

        if "auth" in kwargs and hasattr(kwargs["auth"], "config"):
            auth_conf_dict = getattr(kwargs["auth"].config, "credentials", {})
        else:
            auth_conf_dict = {}
        for collection in self.get_collections(**kwargs):
            try:
                search_endpoint: str = self.config.api_endpoint.rstrip("/").format(
                    **dict(collection=collection, **auth_conf_dict)
                )
            except KeyError as e:
                raise MisconfiguredError(
                    "Missing %s in %s configuration"
                    % (",".join(e.args), kwargs["auth"].provider)
                )
            if page is not None and items_per_page is not None:
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
                if isinstance(self.config.pagination["next_page_query_obj"], str):
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
                        self.query_params, orjson.loads(next_page_query_obj)
                    )

            urls.append(search_endpoint)
        return urls, total_results

    def _request(
        self,
        url: str,
        info_message: Optional[str] = None,
        exception_message: Optional[str] = None,
    ) -> Response:
        try:
            # auth if needed
            kwargs = {}
            if (
                getattr(self.config, "need_auth", False)
                and hasattr(self, "auth")
                and callable(self.auth)
            ):
                kwargs["auth"] = self.auth

            # perform the request using the next page arguments if they are defined
            if getattr(self, "next_page_query_obj", None):
                self.query_params = self.next_page_query_obj
            if info_message:
                logger.info(info_message)
            logger.debug("Query parameters: %s" % self.query_params)
            response = requests.post(
                url,
                json=self.query_params,
                headers=USER_AGENT,
                timeout=getattr(self.config, "timeout", HTTP_REQ_TIMEOUT),
                **kwargs,
            )
            response.raise_for_status()
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
            raise RequestError(str(err))
        return response


class StacSearch(PostJsonSearch):
    """A specialisation of a QueryStringSearch that uses generic STAC configuration"""

    def __init__(self, provider: str, config: PluginConfig) -> None:
        # backup results_entry overwritten by init
        results_entry = config.results_entry

        super(StacSearch, self).__init__(provider, config)

        # restore results_entry overwritten by init
        self.config.results_entry = results_entry

    def normalize_results(
        self, results: List[Dict[str, Any]], **kwargs: Any
    ) -> List[EOProduct]:
        """Build EOProducts from provider results"""

        products = super(StacSearch, self).normalize_results(results, **kwargs)

        # move assets from properties to product's attr
        for product in products:
            product.assets.update(product.properties.pop("assets", {}))

        return products

    def discover_queryables(
        self, product_type: Optional[str] = None
    ) -> Optional[Dict[str, Tuple[Annotated[Any, FieldInfo], Any]]]:
        """Fetch queryables list from provider using `discover_queryables` conf

        :param product_type: (optional) product type
        :type product_type: str
        :returns: fetched queryable parameters dict
        :rtype: dict
        """
        provider_product_type = self.config.products.get(product_type, {}).get(
            "productType", product_type
        )

        python_queryables: Dict[str, FieldInfo] = dict()

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
                fetch_url,
                info_message="Fetching queryables: {}".format(fetch_url),
                exception_message="Skipping error while fetching queryables for "
                "{} {} instance:".format(self.provider, self.__class__.__name__),
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
            field_definitions = dict()
            for json_param, json_mtd in json_queryables.items():
                param = (
                    get_queryable_from_provider(
                        json_param, self.config.metadata_mapping
                    )
                    or json_param
                )
                field_definitions[param] = json_field_definition_to_python(json_mtd)

            python_queryables = create_model("m", **field_definitions).model_fields

        return model_fields_to_annotated_tuple(python_queryables)
