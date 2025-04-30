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
import socket
from copy import copy as copy_copy
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Optional,
    Sequence,
    TypedDict,
    cast,
    get_args,
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

import concurrent.futures
import geojson
import orjson
import requests
import yaml
from jsonpath_ng import JSONPath
from lxml import etree
from pydantic import create_model
from pydantic.fields import FieldInfo
from requests import Response
from requests.adapters import HTTPAdapter
from requests.auth import AuthBase
from urllib3 import Retry

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
from eodag.types.queryables import Queryables
from eodag.types.search_args import SortByList
from eodag.utils import (
    DEFAULT_SEARCH_TIMEOUT,
    GENERIC_PRODUCT_TYPE,
    HTTP_REQ_TIMEOUT,
    REQ_RETRY_BACKOFF_FACTOR,
    REQ_RETRY_STATUS_FORCELIST,
    REQ_RETRY_TOTAL,
    USER_AGENT,
    _deprecated,
    copy_deepcopy,
    deepcopy,
    dict_items_recursive_apply,
    format_dict_items,
    get_ssl_context,
    quote,
    string_to_jsonpath,
    update_nested_dict,
    urlencode,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    PluginImplementationError,
    RequestError,
    TimeOutError,
    ValidationError,
)

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.qssearch")


class QueryStringSearch(Search):
    """A plugin that helps implementing any kind of search protocol that relies on
    query strings (e.g: opensearch). Most of the other search plugins inherit from this plugin.

    :param provider: provider name
    :param config: Search plugin configuration:

        * :attr:`~eodag.config.PluginConfig.result_type` (``str``): One of ``json`` or ``xml``, depending on the
          representation of the provider's search results. The default is ``json``.
        * :attr:`~eodag.config.PluginConfig.results_entry` (``str``) (**mandatory**): The name of the key in the
          provider search result that gives access to the result entries
        * :attr:`~eodag.config.PluginConfig.api_endpoint` (``str``) (**mandatory**): The endpoint of the provider's
          search interface
        * :attr:`~eodag.config.PluginConfig.need_auth` (``bool``): if authentication is needed for the search request;
          default: ``False``
        * :attr:`~eodag.config.PluginConfig.auth_error_code` (``int``): which error code is returned in case of an
          authentication error; only used if ``need_auth=true``
        * :attr:`~eodag.config.PluginConfig.ssl_verify` (``bool``): if the ssl certificates should be verified in
          requests; default: ``True``
        * :attr:`~eodag.config.PluginConfig.asset_key_from_href` (``bool``): guess assets keys using their ``href``. Use
          their original key if ``False``; default: ``True``
        * :attr:`~eodag.config.PluginConfig.dont_quote` (``list[str]``): characters that should not be quoted in the
          url params
        * :attr:`~eodag.config.PluginConfig.timeout` (``int``): time to wait until request timeout in seconds;
          default: ``5``
        * :attr:`~eodag.config.PluginConfig.retry_total` (``int``): :class:`urllib3.util.Retry` ``total`` parameter,
          total number of retries to allow; default: ``3``
        * :attr:`~eodag.config.PluginConfig.retry_backoff_factor` (``int``): :class:`urllib3.util.Retry`
          ``backoff_factor`` parameter, backoff factor to apply between attempts after the second try; default: ``2``
        * :attr:`~eodag.config.PluginConfig.retry_status_forcelist` (``list[int]``): :class:`urllib3.util.Retry`
          ``status_forcelist`` parameter, list of integer HTTP status codes that we should force a retry on; default:
          ``[401, 429, 500, 502, 503, 504]``
        * :attr:`~eodag.config.PluginConfig.literal_search_params` (``dict[str, str]``): A mapping of (search_param =>
          search_value) pairs giving search parameters to be passed as is in the search url query string. This is useful
          for example in situations where the user wants to add a fixed search query parameter exactly
          as it is done on the provider interface.
        * :attr:`~eodag.config.PluginConfig.pagination` (:class:`~eodag.config.PluginConfig.Pagination`)
          (**mandatory**): The configuration of how the pagination is done on the provider. It is a tree with the
          following nodes:

          * :attr:`~eodag.config.PluginConfig.Pagination.next_page_url_tpl` (``str``) (**mandatory**): The template for
            pagination requests. This is a simple Python format string which will be resolved using the following
            keywords: ``url`` (the base url of the search endpoint), ``search`` (the query string corresponding
            to the search request), ``items_per_page`` (the number of items to return per page),
            ``skip`` (the number of items to skip) or ``skip_base_1`` (the number of items to skip,
            starting from 1) and ``page`` (which page to return).
          * :attr:`~eodag.config.PluginConfig.Pagination.total_items_nb_key_path` (``str``):  An XPath or JsonPath
            leading to the total number of results satisfying a request. This is used for providers which provides the
            total results metadata along with the result of the query and don't have an endpoint for querying
            the number of items satisfying a request, or for providers for which the count endpoint
            returns a json or xml document
          * :attr:`~eodag.config.PluginConfig.Pagination.count_endpoint` (``str``): The endpoint for counting the number
            of items satisfying a request
          * :attr:`~eodag.config.PluginConfig.Pagination.count_tpl` (``str``): template for the count parameter that
            should be added to the search request
          * :attr:`~eodag.config.PluginConfig.Pagination.next_page_url_key_path` (``str``): A JsonPath expression used
            to retrieve the URL of the next page in the response of the current page.
          * :attr:`~eodag.config.PluginConfig.Pagination.max_items_per_page` (``int``): The maximum number of items per
            page that the provider can handle; default: ``50``
          * :attr:`~eodag.config.PluginConfig.Pagination.start_page` (``int``): number of the first page; default: ``1``

        * :attr:`~eodag.config.PluginConfig.discover_product_types`
          (:class:`~eodag.config.PluginConfig.DiscoverProductTypes`): configuration for product type discovery based on
          information from the provider; It contains the keys:

          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.fetch_url` (``str``) (**mandatory**): url from which
            the product types can be fetched
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.max_connections` (``int``): Maximum number of
            connections for concurrent HTTP requests
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.result_type` (``str``): type of the provider result;
            currently only ``json`` is supported (other types could be used in an extension of this plugin)
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.results_entry` (``str``) (**mandatory**): json path
            to the list of product types
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.generic_product_type_id` (``str``): mapping for the
            product type id
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.generic_product_type_parsable_metadata`
            (``dict[str, str]``): mapping for product type metadata (e.g. ``abstract``, ``licence``) which can be parsed
            from the provider result
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.generic_product_type_parsable_properties`
            (``dict[str, str]``): mapping for product type properties which can be parsed from the result and are not
            product type metadata
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.generic_product_type_unparsable_properties`
            (``dict[str, str]``): mapping for product type properties which cannot be parsed from the result and are not
            product type metadata
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.single_collection_fetch_url` (``str``): url to fetch
            data for a single collection; used if product type metadata is not available from the endpoint given in
            :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.fetch_url`
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.single_collection_fetch_qs` (``str``): query string
            to be added to the :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.fetch_url` to filter for a
            collection
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.single_product_type_parsable_metadata`
            (``dict[str, str]``): mapping for product type metadata returned by the endpoint given in
            :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.single_collection_fetch_url`.

        * :attr:`~eodag.config.PluginConfig.sort` (:class:`~eodag.config.PluginConfig.Sort`): configuration for sorting
          the results. It contains the keys:

          * :attr:`~eodag.config.PluginConfig.Sort.sort_by_default` (``list[Tuple(str, Literal["ASC", "DESC"])]``):
            parameter and sort order by which the result will be sorted by default (if the user does not enter a
            ``sort_by`` parameter); if not given the result will use the default sorting of the provider; Attention:
            for some providers sorting might cause a timeout if no filters are used. In that case no default
            sort parameters should be given. The format is::

                  sort_by_default:
                      - !!python/tuple [<param>, <sort order> (ASC or DESC)]

          * :attr:`~eodag.config.PluginConfig.Sort.sort_by_tpl` (``str``): template for the sort parameter that is added
            to the request; It contains the parameters `sort_param` and `sort_order` which will be replaced by user
            input or default value. If the parameters are added as query params to a GET request, the string
            should start with ``&``, otherwise it should be a valid json string surrounded by ``{{ }}``.
          * :attr:`~eodag.config.PluginConfig.Sort.sort_param_mapping` (``Dict [str, str]``): mapping for the parameters
            available for sorting
          * :attr:`~eodag.config.PluginConfig.Sort.sort_order_mapping`
            (``dict[Literal["ascending", "descending"], str]``): mapping for the sort order
          * :attr:`~eodag.config.PluginConfig.Sort.max_sort_params` (``int``): maximum number of sort parameters
            supported by the provider; used to validate the user input to avoid failed requests or unexpected behaviour
            (not all parameters are used in the request)

        * :attr:`~eodag.config.PluginConfig.metadata_mapping` (``dict[str, Any]``): The search plugins of this kind can
          detect when a metadata mapping is "query-able", and get the semantics of how to format the query string
          parameter that enables to make a query on the corresponding metadata. To make a metadata query-able,
          just configure it in the metadata mapping to be a list of 2 items, the first one being the
          specification of the query string search formatting. The later is a string following the
          specification of Python string formatting, with a special behaviour added to it. For example,
          an entry in the metadata mapping of this kind::

                completionTimeFromAscendingNode:
                    - 'f=acquisition.endViewingDate:lte:{completionTimeFromAscendingNode#timestamp}'
                    - '$.properties.acquisition.endViewingDate'

          means that the search url will have a query string parameter named ``f`` with a value of
          ``acquisition.endViewingDate:lte:1543922280.0`` if the search was done with the value
          of ``completionTimeFromAscendingNode`` being ``2018-12-04T12:18:00``. What happened is that
          ``{completionTimeFromAscendingNode#timestamp}`` was replaced with the timestamp of the value
          of ``completionTimeFromAscendingNode``. This example shows all there is to know about the
          semantics of the query string formatting introduced by this plugin: any eodag search parameter
          can be referenced in the query string with an additional optional conversion function that
          is separated from it by a ``#`` (see :func:`~eodag.api.product.metadata_mapping.format_metadata` for further
          details on the available converters). Note that for the values in the
          :attr:`~eodag.config.PluginConfig.free_text_search_operations` configuration parameter follow the same rule.
          If the metadata_mapping is not a list but only a string, this means that the parameters is not queryable but
          it is included in the result obtained from the provider. The string indicates how the provider result should
          be mapped to the eodag parameter.
        * :attr:`~eodag.config.PluginConfig.discover_metadata` (:class:`~eodag.config.PluginConfig.DiscoverMetadata`):
          configuration for the auto-discovery of queryable parameters as well as parameters returned by the provider
          which are not in the metadata mapping. It has the attributes:

          * :attr:`~eodag.config.PluginConfig.DiscoverMetadata.auto_discovery` (``bool``): if the automatic discovery of
            metadata is activated; default: ``False``; if false, the other parameters are not used;
          * :attr:`~eodag.config.PluginConfig.DiscoverMetadata.metadata_pattern` (``str``): regex string a parameter in
            the result should match so that is used
          * :attr:`~eodag.config.PluginConfig.DiscoverMetadata.search_param` (``Union [str, dict[str, Any]]``): format
            to add a query param given by the user and not in the metadata mapping to the requests, 'metadata' will be
            replaced by the search param; can be a string or a dict containing
            :attr:`~eodag.config.PluginConfig.free_text_search_operations`
            (see :class:`~eodag.plugins.search.qssearch.ODataV4Search`)
          * :attr:`~eodag.config.PluginConfig.DiscoverMetadata.metadata_path` (``str``): path where the queryable
            properties can be found in the provider result

        * :attr:`~eodag.config.PluginConfig.discover_queryables`
          (:class:`~eodag.config.PluginConfig.DiscoverQueryables`): configuration to fetch the queryables from a
          provider queryables endpoint; It has the following keys:

          * :attr:`~eodag.config.PluginConfig.DiscoverQueryables.fetch_url` (``str``): url to fetch the queryables valid
            for all product types
          * :attr:`~eodag.config.PluginConfig.DiscoverQueryables.product_type_fetch_url` (``str``): url to fetch the
            queryables for a specific product type
          * :attr:`~eodag.config.PluginConfig.DiscoverQueryables.result_type` (``str``): type of the result (currently
            only ``json`` is used)
          * :attr:`~eodag.config.PluginConfig.DiscoverQueryables.results_entry` (``str``): json path to retrieve the
            queryables from the provider result

        * :attr:`~eodag.config.PluginConfig.constraints_file_url` (``str``): url to fetch the constraints for a specific
          product type, can be an http url or a path to a file; the constraints are used to build queryables
        * :attr:`~eodag.config.PluginConfig.constraints_entry` (``str``): key in the json result where the constraints
          can be found; if not given, it is assumed that the constraints are on top level of the result, i.e.
          the result is an array of constraints
    """

    extract_properties: dict[str, Callable[..., dict[str, Any]]] = {
        "xml": properties_from_xml,
        "json": properties_from_json,
    }

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(QueryStringSearch, self).__init__(provider, config)
        self.config.__dict__.setdefault("result_type", "json")
        self.config.__dict__.setdefault("results_entry", "features")
        self.config.__dict__.setdefault("pagination", {})
        self.config.__dict__.setdefault("free_text_search_operations", {})
        self.search_urls: list[str] = []
        self.query_params: dict[str, str] = dict()
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

    def discover_product_types(self, **kwargs: Any) -> Optional[dict[str, Any]]:
        """Fetch product types list from provider using `discover_product_types` conf

        :returns: configuration dict containing fetched product types information
        """
        unpaginated_fetch_url = self.config.discover_product_types.get("fetch_url")
        if not unpaginated_fetch_url:
            return None

        # product types pagination
        next_page_url_tpl = self.config.discover_product_types.get("next_page_url_tpl")
        page = self.config.discover_product_types.get("start_page", 1)

        if not next_page_url_tpl:
            # no pagination
            return self.discover_product_types_per_page(**kwargs)

        conf_update_dict: dict[str, Any] = {
            "providers_config": {},
            "product_types_config": {},
        }

        while True:
            fetch_url = next_page_url_tpl.format(url=unpaginated_fetch_url, page=page)

            conf_update_dict_per_page = self.discover_product_types_per_page(
                fetch_url=fetch_url, **kwargs
            )

            if (
                not conf_update_dict_per_page
                or not conf_update_dict_per_page.get("providers_config")
                or conf_update_dict_per_page.items() <= conf_update_dict.items()
            ):
                # conf_update_dict_per_page is empty or a subset on existing conf
                break
            else:
                conf_update_dict["providers_config"].update(
                    conf_update_dict_per_page["providers_config"]
                )
                conf_update_dict["product_types_config"].update(
                    conf_update_dict_per_page["product_types_config"]
                )

            page += 1

        return conf_update_dict

    def discover_product_types_per_page(
        self, **kwargs: Any
    ) -> Optional[dict[str, Any]]:
        """Fetch product types list from provider using `discover_product_types` conf
        using paginated ``kwargs["fetch_url"]``

        :returns: configuration dict containing fetched product types information
        """
        try:
            prep = PreparedSearch()

            # url from discover_product_types() or conf
            fetch_url: Optional[str] = kwargs.get("fetch_url")
            if fetch_url is None:
                if fetch_url := self.config.discover_product_types.get("fetch_url"):
                    fetch_url = fetch_url.format(**self.config.__dict__)
                else:
                    return None
            prep.url = fetch_url

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
                "Skipping error while fetching product types for {} {} instance:"
            ).format(self.provider, self.__class__.__name__)

            # Query using appropriate method
            fetch_method = self.config.discover_product_types.get("fetch_method", "GET")
            fetch_body = self.config.discover_product_types.get("fetch_body", {})
            if fetch_method == "POST" and isinstance(self, PostJsonSearch):
                prep.query_params = fetch_body
                response = self._request(prep)
            else:
                response = QueryStringSearch._request(self, prep)
        except (RequestError, KeyError, AttributeError):
            return None
        else:
            try:
                conf_update_dict: dict[str, Any] = {
                    "providers_config": {},
                    "product_types_config": {},
                }
                if self.config.discover_product_types["result_type"] == "json":
                    resp_as_json = response.json()
                    # extract results from response json
                    results_entry = self.config.discover_product_types["results_entry"]
                    if not isinstance(results_entry, JSONPath):
                        logger.warning(
                            f"Could not parse {self.provider} discover_product_types.results_entry"
                            f" as JSONPath: {results_entry}"
                        )
                        return None
                    result = [match.value for match in results_entry.find(resp_as_json)]
                    if result and isinstance(result[0], list):
                        result = result[0]

                    def conf_update_from_product_type_result(
                        product_type_result: dict[str, Any],
                    ) -> None:
                        """Update ``conf_update_dict`` using given product type json response"""
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
                                if kf
                                in conf_update_dict["product_types_config"][
                                    generic_product_type_id
                                ]
                                and conf_update_dict["product_types_config"][
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

                    # runs concurrent requests and aggregate results in conf_update_dict
                    max_connections = self.config.discover_product_types.get(
                        "max_connections"
                    )
                    with concurrent.futures.ThreadPoolExecutor(
                        max_workers=max_connections
                    ) as executor:
                        futures = (
                            executor.submit(conf_update_from_product_type_result, r)
                            for r in result
                        )
                        [f.result() for f in concurrent.futures.as_completed(futures)]

            except KeyError as e:
                logger.warning(
                    "Incomplete %s discover_product_types configuration: %s",
                    self.provider,
                    e,
                )
                return None
            except requests.RequestException as e:
                logger.debug(
                    "Could not parse discovered product types response from "
                    f"{self.provider}, {type(e).__name__}: {e.args}"
                )
                return None
        conf_update_dict["product_types_config"] = dict_items_recursive_apply(
            conf_update_dict["product_types_config"],
            lambda k, v: v if v != NOT_AVAILABLE else None,
        )
        return conf_update_dict

    def _get_product_type_metadata_from_single_collection_endpoint(
        self, product_type: str
    ) -> dict[str, Any]:
        """
        retrieves additional product type information from an endpoint returning data for a single collection
        :param product_type: product type
        :return: product types and their metadata
        """
        single_collection_url = self.config.discover_product_types[
            "single_collection_fetch_url"
        ].format(productType=product_type)
        resp = QueryStringSearch._request(
            self,
            PreparedSearch(
                url=single_collection_url,
                info_message=f"Fetching data for product type: {product_type}",
                exception_message="Skipping error while fetching product types for "
                "{} {} instance:".format(self.provider, self.__class__.__name__),
            ),
        )
        product_data = resp.json()
        return properties_from_json(
            product_data,
            self.config.discover_product_types["single_product_type_parsable_metadata"],
        )

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> tuple[list[EOProduct], Optional[int]]:
        """Perform a search on an OpenSearch-like interface

        :param prep: Object collecting needed information for search.
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
            self.get_product_type_def_params(product_type, format_variables=kwargs)
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

        qp, qs = self.build_query_string(product_type, keywords)

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
    def update_metadata_mapping(self, metadata_mapping: dict[str, Any]) -> None:
        """Update plugin metadata_mapping with input metadata_mapping configuration"""
        if self.config.metadata_mapping:
            self.config.metadata_mapping.update(metadata_mapping)

    def build_query_string(
        self, product_type: str, query_dict: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Build The query string using the search parameters"""
        logger.debug("Building the query string that will be used for search")
        query_params = format_query_params(product_type, self.config, query_dict)

        # Build the final query string, in one go without quoting it
        # (some providers do not operate well with urlencoded and quoted query strings)
        def quote_via(x: Any, *_args: Any, **_kwargs: Any) -> str:
            return x

        return (
            query_params,
            urlencode(query_params, doseq=True, quote_via=quote_via),
        )

    def collect_search_urls(
        self,
        prep: PreparedSearch = PreparedSearch(page=None, items_per_page=None),
        **kwargs: Any,
    ) -> tuple[list[str], Optional[int]]:
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

        for collection in self.get_collections(prep, **kwargs) or (None,):
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
                if "next_page_url_tpl" not in self.config.pagination:
                    raise MisconfiguredError(
                        f"next_page_url_tpl is missing in {self.provider} search.pagination configuration"
                    )
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
        return list(dict.fromkeys(urls)), total_results

    def do_search(
        self, prep: PreparedSearch = PreparedSearch(items_per_page=None), **kwargs: Any
    ) -> list[Any]:
        """Perform the actual search request.

        If there is a specified number of items per page, return the results as soon
        as this number is reached

        :param prep: Object collecting needed information for search.
        """
        items_per_page = prep.items_per_page
        total_items_nb = 0
        if getattr(prep, "need_count", False):
            # extract total_items_nb from search results
            if self.config.result_type == "json":
                total_items_nb_key_path_parsed = self.config.pagination[
                    "total_items_nb_key_path"
                ]

        results: list[Any] = []
        for search_url in prep.search_urls:
            single_search_prep = copy_copy(prep)
            single_search_prep.url = search_url
            single_search_prep.info_message = "Sending search request: {}".format(
                search_url
            )
            single_search_prep.exception_message = (
                f"Skipping error while searching for {self.provider}"
                f" {self.__class__.__name__} instance"
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
                    if isinstance(results_xpath, Sequence)
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
                            if isinstance(total_nb_results_xpath, Sequence)
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
                    found_paths = path_parsed.find(resp_as_json)
                    if found_paths and not isinstance(found_paths, int):
                        self.next_page_url = found_paths[0].value
                        logger.debug(
                            "Next page URL collected and set for the next search",
                        )
                    else:
                        logger.debug("Next page URL could not be collected")
                if next_page_query_obj_key_path:
                    path_parsed = next_page_query_obj_key_path
                    found_paths = path_parsed.find(resp_as_json)
                    if found_paths and not isinstance(found_paths, int):
                        self.next_page_query_obj = found_paths[0].value
                        logger.debug(
                            "Next page Query-object collected and set for the next search",
                        )
                    else:
                        logger.debug("Next page Query-object could not be collected")
                if next_page_merge_key_path:
                    path_parsed = next_page_merge_key_path
                    found_paths = path_parsed.find(resp_as_json)
                    if found_paths and not isinstance(found_paths, int):
                        self.next_page_merge = found_paths[0].value
                        logger.debug(
                            "Next page merge collected and set for the next search",
                        )
                    else:
                        logger.debug("Next page merge could not be collected")

                results_entry = string_to_jsonpath(
                    self.config.results_entry, force=True
                )
                found_entry_paths = results_entry.find(resp_as_json)
                if found_entry_paths and not isinstance(found_entry_paths, int):
                    result = found_entry_paths[0].value
                else:
                    result = []
                if not isinstance(result, list):
                    result = [result]

                if getattr(prep, "need_count", False):
                    # extract total_items_nb from search results
                    found_total_items_nb_paths = total_items_nb_key_path_parsed.find(
                        resp_as_json
                    )
                    if found_total_items_nb_paths and not isinstance(
                        found_total_items_nb_paths, int
                    ):
                        _total_items_nb = found_total_items_nb_paths[0].value
                        if getattr(self.config, "merge_responses", False):
                            total_items_nb = _total_items_nb or 0
                        else:
                            total_items_nb += _total_items_nb or 0
                    else:
                        logger.debug(
                            "Could not extract total_items_nb from search results"
                        )
            if (
                getattr(self.config, "merge_responses", False)
                and self.config.result_type == "json"
            ):
                json_result = cast(list[dict[str, Any]], result)
                results = (
                    [dict(r, **json_result[i]) for i, r in enumerate(results)]
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
    ) -> list[EOProduct]:
        """Build EOProducts from provider results"""
        normalize_remaining_count = len(results)
        logger.debug(
            "Adapting %s plugin results to eodag product representation"
            % normalize_remaining_count
        )
        products: list[EOProduct] = []
        asset_key_from_href = getattr(self.config, "asset_key_from_href", True)
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
            # move assets from properties to product's attr, normalize keys & roles
            for key, asset in product.properties.pop("assets", {}).items():
                norm_key, asset["roles"] = product.driver.guess_asset_key_and_roles(
                    asset.get("href", "") if asset_key_from_href else key,
                    product,
                )
                if norm_key:
                    product.assets[norm_key] = asset
            # sort assets
            product.assets.data = dict(sorted(product.assets.data.items()))
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
                if not isinstance(path_parsed, JSONPath):
                    raise PluginImplementationError(
                        "total_items_nb_key_path must be parsed to JSONPath on plugin init"
                    )
                found_paths = path_parsed.find(count_results)
                if found_paths and not isinstance(found_paths, int):
                    total_results = found_paths[0].value
                else:
                    raise MisconfiguredError(
                        "Could not get results count from response using total_items_nb_key_path"
                    )
            else:  # interpret the result as a raw int
                total_results = int(count_results)
        return total_results

    def get_collections(self, prep: PreparedSearch, **kwargs: Any) -> tuple[str, ...]:
        """Get the collection to which the product belongs"""
        # See https://earth.esa.int/web/sentinel/missions/sentinel-2/news/-
        # /asset_publisher/Ac0d/content/change-of
        # -format-for-new-sentinel-2-level-1c-products-starting-on-6-december
        product_type: Optional[str] = kwargs.get("productType")
        collection: Optional[str] = None
        if product_type is None and (
            not hasattr(prep, "product_type_def_params")
            or not prep.product_type_def_params
        ):
            collections: set[str] = set()
            collection = getattr(self.config, "collection", None)
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

        collection = getattr(self.config, "collection", None)
        if collection is None:
            collection = (
                prep.product_type_def_params.get("collection", None) or product_type
            )

        if collection is None:
            return ()
        elif not isinstance(collection, list):
            return (collection,)
        else:
            return tuple(collection)

    def _request(
        self,
        prep: PreparedSearch,
    ) -> Response:
        url = prep.url
        if url is None:
            raise ValidationError("Cannot request empty URL")
        info_message = prep.info_message
        exception_message = prep.exception_message
        try:
            timeout = getattr(self.config, "timeout", DEFAULT_SEARCH_TIMEOUT)
            ssl_verify = getattr(self.config, "ssl_verify", True)

            retry_total = getattr(self.config, "retry_total", REQ_RETRY_TOTAL)
            retry_backoff_factor = getattr(
                self.config, "retry_backoff_factor", REQ_RETRY_BACKOFF_FACTOR
            )
            retry_status_forcelist = getattr(
                self.config, "retry_status_forcelist", REQ_RETRY_STATUS_FORCELIST
            )

            ssl_ctx = get_ssl_context(ssl_verify)
            # auth if needed
            kwargs: dict[str, Any] = {}
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

                session = requests.Session()
                retries = Retry(
                    total=retry_total,
                    backoff_factor=retry_backoff_factor,
                    status_forcelist=retry_status_forcelist,
                )
                session.mount(url, HTTPAdapter(max_retries=retries))

                response = session.get(
                    url,
                    timeout=timeout,
                    headers=USER_AGENT,
                    verify=ssl_verify,
                    **kwargs,
                )
                response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=timeout) from exc
        except socket.timeout:
            err = requests.exceptions.Timeout(request=requests.Request(url=url))
            raise TimeOutError(err, timeout=timeout)
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
            raise RequestError.from_error(err, exception_message) from err
        return response


class ODataV4Search(QueryStringSearch):
    """A specialisation of a :class:`~eodag.plugins.search.qssearch.QueryStringSearch` that does a two step search to
    retrieve all products metadata. All configuration parameters of
    :class:`~eodag.plugins.search.qssearch.QueryStringSearch` are also available for this plugin. In addition, the
    following parameters can be configured:

    :param provider: provider name
    :param config: Search plugin configuration:

      * :attr:`~eodag.config.PluginConfig.per_product_metadata_query` (``bool``): should be set to true if the metadata
        is not given in the search result and a two step search has to be performed; default: false
      * :attr:`~eodag.config.PluginConfig.metadata_pre_mapping` (:class:`~eodag.config.PluginConfig.MetadataPreMapping`)
        : a dictionary which can be used to simplify further metadata extraction. For example, going from
        ``$.Metadata[?(@.id="foo")].value`` to ``$.Metadata.foo.value``. It has the keys:

        * :attr:`~eodag.config.PluginConfig.MetadataPreMapping.metadata_path` (``str``): json path of the metadata entry
        * :attr:`~eodag.config.PluginConfig.MetadataPreMapping.metadata_path_id` (``str``): key to get the metadata id
        * :attr:`~eodag.config.PluginConfig.MetadataPreMapping.metadata_path_value` (``str``): key to get the metadata
          value

      * :attr:`~eodag.config.PluginConfig.free_text_search_operations`: (optional) A tree structure of the form::

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
        ``(<op1> <opname> <op2>)``, then the operations will be joined together using
        the union string and finally if the number of operations is greater than 1,
        they will be wrapped as specified by the wrapper config key.

    """

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
    ) -> list[Any]:
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
                        "Skipping error while searching for %s %s instance",
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

    def get_metadata_search_url(self, entity: dict[str, Any]) -> str:
        """Build the metadata link for the given entity"""
        return "{}({})/Metadata".format(
            self.config.api_endpoint.rstrip("/"), entity["id"]
        )

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> list[EOProduct]:
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
    """A specialisation of a :class:`~eodag.plugins.search.qssearch.QueryStringSearch` that uses POST method

    All configuration parameters available for :class:`~eodag.plugins.search.qssearch.QueryStringSearch`
    are also available for PostJsonSearch. The mappings given in metadata_mapping are used to construct
    a (json) body for the POST request that is sent to the provider. Due to the fact that we sent a POST request and
    not a get request, the pagination configuration will look slightly different. It has the
    following parameters:

    :param provider: provider name
    :param config: Search plugin configuration:

        * :attr:`~eodag.config.PluginConfig.Pagination.next_page_query_obj` (``str``): The additional parameters
          needed to add pagination information to the search request. These parameters won't be
          included in result. This must be a json dict formatted like ``{{"foo":"bar"}}`` because
          it will be passed to a :meth:`str.format` method before being loaded as json.
        * :attr:`~eodag.config.PluginConfig.Pagination.total_items_nb_key_path` (``str``):  An XPath or JsonPath
          leading to the total number of results satisfying a request. This is used for providers
          which provides the total results metadata along with the result of the query and don't
          have an endpoint for querying the number of items satisfying a request, or for providers
          for which the count endpoint returns a json or xml document
        * :attr:`~eodag.config.PluginConfig.Pagination.max_items_per_page` (``int``): The maximum number of items
          per page that the provider can handle; default: ``50``

    """

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> tuple[list[EOProduct], Optional[int]]:
        """Perform a search on an OpenSearch-like interface"""
        product_type = kwargs.get("productType", "")
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
                product_type, format_variables=kwargs
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
                product_type, format_variables=kwargs
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

            qp, _ = self.build_query_string(product_type, keywords)

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

                def count_hits(self, *x, **y):
                    return 1

                def _request(self, *x, **y):
                    return super(PostJsonSearch, self)._request(*x, **y)

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
    ) -> list[EOProduct]:
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
    ) -> tuple[list[str], Optional[int]]:
        """Adds pagination to query parameters, and auth to url"""
        page = prep.page
        items_per_page = prep.items_per_page
        count = prep.count
        urls: list[str] = []
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
        for collection in self.get_collections(prep, **kwargs) or (None,):
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
                            total_results = (
                                (_total_results or 0)
                                if total_results is None
                                else total_results + (_total_results or 0)
                            )
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
        return list(dict.fromkeys(urls)), total_results

    def _request(
        self,
        prep: PreparedSearch,
    ) -> Response:
        url = prep.url
        if url is None:
            raise ValidationError("Cannot request empty URL")
        info_message = prep.info_message
        exception_message = prep.exception_message
        timeout = getattr(self.config, "timeout", DEFAULT_SEARCH_TIMEOUT)
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
            if (
                hasattr(self, "next_page_query_obj")
                and self.next_page_query_obj is not None
            ):
                prep.query_params = self.next_page_query_obj
            if info_message:
                logger.info(info_message)
            try:
                logger.debug("Query parameters: %s" % geojson.dumps(prep.query_params))
            except TypeError:
                logger.debug("Query parameters: %s" % prep.query_params)
            try:
                logger.debug("Query kwargs: %s" % geojson.dumps(kwargs))
            except TypeError:
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
            response = locals().get("response", Response())
            # check if error is identified as auth_error in provider conf
            auth_errors = getattr(self.config, "auth_error_code", [None])
            if not isinstance(auth_errors, list):
                auth_errors = [auth_errors]
            if response.status_code and response.status_code in auth_errors:
                raise AuthenticationError(
                    f"Please check your credentials for {self.provider}.",
                    f"HTTP Error {response.status_code} returned.",
                    response.text.strip(),
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
            logger.debug(response.content or str(err))
            raise RequestError.from_error(err, exception_message) from err
        return response


class StacSearch(PostJsonSearch):
    """A specialisation of :class:`~eodag.plugins.search.qssearch.PostJsonSearch` that uses generic
    STAC configuration, it therefore has the same configuration parameters (those inherited
    from :class:`~eodag.plugins.search.qssearch.QueryStringSearch`).
    For providers using ``StacSearch`` default values are defined for most of the parameters
    (see ``stac_provider.yml``). If some parameters are different for a specific provider, they
    have to be overwritten. If certain functionalities are not available, their configuration
    parameters have to be overwritten with ``null``. E.g. if there is no queryables endpoint,
    the :attr:`~eodag.config.PluginConfig.DiscoverQueryables.fetch_url` and
    :attr:`~eodag.config.PluginConfig.DiscoverQueryables.product_type_fetch_url` in the
    :attr:`~eodag.config.PluginConfig.discover_queryables` config have to be set to ``null``.
    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        # backup results_entry overwritten by init
        results_entry = config.results_entry

        super(StacSearch, self).__init__(provider, config)

        # restore results_entry overwritten by init
        self.config.results_entry = results_entry

    def build_query_string(
        self, product_type: str, query_dict: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Build The query string using the search parameters"""
        logger.debug("Building the query string that will be used for search")

        # handle opened time intervals
        if any(
            q in query_dict
            for q in ("startTimeFromAscendingNode", "completionTimeFromAscendingNode")
        ):
            query_dict.setdefault("startTimeFromAscendingNode", "..")
            query_dict.setdefault("completionTimeFromAscendingNode", "..")

        query_params = format_query_params(product_type, self.config, query_dict)

        # Build the final query string, in one go without quoting it
        # (some providers do not operate well with urlencoded and quoted query strings)
        def quote_via(x: Any, *_args: Any, **_kwargs: Any) -> str:
            return x

        return (
            query_params,
            urlencode(query_params, doseq=True, quote_via=quote_via),
        )

    def discover_queryables(
        self, **kwargs: Any
    ) -> Optional[dict[str, Annotated[Any, FieldInfo]]]:
        """Fetch queryables list from provider using `discover_queryables` conf

        :param kwargs: additional filters for queryables (`productType` and other search
                       arguments)
        :returns: fetched queryable parameters dict
        """
        if (
            not self.config.discover_queryables["fetch_url"]
            and not self.config.discover_queryables["product_type_fetch_url"]
        ):
            raise NotImplementedError()

        product_type = kwargs.get("productType", None)
        provider_product_type = (
            self.config.products.get(product_type, {}).get("productType", product_type)
            if product_type
            else None
        )
        if (
            provider_product_type
            and not self.config.discover_queryables["product_type_fetch_url"]
        ):
            raise NotImplementedError(
                f"Cannot fetch queryables for a specific product type with {self.provider}"
            )
        if (
            not provider_product_type
            and not self.config.discover_queryables["fetch_url"]
        ):
            raise ValidationError(
                f"Cannot fetch global queryables for {self.provider}. A product type must be specified"
            )

        try:
            unparsed_fetch_url = (
                self.config.discover_queryables["product_type_fetch_url"]
                if provider_product_type
                else self.config.discover_queryables["fetch_url"]
            )
            if unparsed_fetch_url is None:
                raise PluginImplementationError(
                    f"Cannot fetch queryables for {self.provider}: missing url"
                )

            fetch_url = unparsed_fetch_url.format(
                provider_product_type=provider_product_type,
                **self.config.__dict__,
            )
            auth = (
                self.auth
                if hasattr(self, "auth") and isinstance(self.auth, AuthBase)
                else None
            )
            response = QueryStringSearch._request(
                self,
                PreparedSearch(
                    url=fetch_url,
                    auth=auth,
                    info_message="Fetching queryables: {}".format(fetch_url),
                    exception_message="Skipping error while fetching queryables for "
                    "{} {} instance:".format(self.provider, self.__class__.__name__),
                ),
            )
        except (KeyError, AttributeError) as e:
            raise PluginImplementationError(
                "failure in queryables discovery: %s", e
            ) from e
        except RequestError as e:
            raise RequestError("failure in queryables discovery: %s", e) from e
        else:
            json_queryables = dict()
            try:
                resp_as_json = response.json()

                # extract results from response json
                results_entry = self.config.discover_queryables["results_entry"]
                if not isinstance(results_entry, JSONPath):
                    raise MisconfiguredError(
                        f"Could not parse {self.provider} discover_queryables.results_entry"
                        f" as JSONPath: {results_entry}"
                    )
                json_queryables = [
                    match.value for match in results_entry.find(resp_as_json)
                ][0]

            except KeyError as e:
                raise MisconfiguredError(
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
            field_definitions: dict[str, Any] = dict()
            STAC_TO_EODAG_QUERYABLES = {
                "start_datetime": "start",
                "end_datetime": "end",
                "datetime": None,
                "bbox": "geom",
            }
            for json_param, json_mtd in json_queryables.items():
                param = STAC_TO_EODAG_QUERYABLES.get(
                    json_param,
                    get_queryable_from_provider(
                        json_param, self.get_metadata_mapping(product_type)
                    )
                    or json_param,
                )
                if param is None:
                    continue

                default = kwargs.get(param, json_mtd.get("default"))
                annotated_def = json_field_definition_to_python(
                    json_mtd, default_value=default
                )
                field_definitions[param] = get_args(annotated_def)

            python_queryables = create_model("m", **field_definitions).model_fields
            geom_queryable = python_queryables.pop("geometry", None)
            if geom_queryable:
                python_queryables["geom"] = geom_queryable

            queryables_dict = model_fields_to_annotated(python_queryables)

            # append "datetime" as "start" & "end" if needed
            if "datetime" in json_queryables:
                eodag_queryables = copy_deepcopy(
                    model_fields_to_annotated(Queryables.model_fields)
                )
                queryables_dict.setdefault("start", eodag_queryables["start"])
                queryables_dict.setdefault("end", eodag_queryables["end"])

            return queryables_dict


class PostJsonSearchWithStacQueryables(StacSearch, PostJsonSearch):
    """A specialisation of a :class:`~eodag.plugins.search.qssearch.PostJsonSearch` that uses
    generic STAC configuration for queryables (inherited from :class:`~eodag.plugins.search.qssearch.StacSearch`).
    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        PostJsonSearch.__init__(self, provider, config)

    def build_query_string(
        self, product_type: str, query_dict: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Build The query string using the search parameters"""
        return PostJsonSearch.build_query_string(self, product_type, query_dict)
