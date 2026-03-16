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
from typing import Any, Optional
from urllib.error import URLError
from urllib.parse import quote_plus, unquote, unquote_plus

import geojson
import orjson
import requests
import yaml
from requests import Response
from requests.auth import AuthBase
from typing_extensions import TypedDict

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    format_query_params,
    mtd_cfg_as_conversion_and_querypath,
)
from eodag.api.search_result import RawSearchResult, SearchResult
from eodag.types.search_args import SortByList
from eodag.utils import (
    DEFAULT_PAGE,
    DEFAULT_SEARCH_TIMEOUT,
    GENERIC_COLLECTION,
    USER_AGENT,
    deepcopy,
    update_nested_dict,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    QuotaExceededError,
    RequestError,
    TimeOutError,
    ValidationError,
)

from ..preparesearch import PreparedSearch
from .querystringsearch import QueryStringSearch

logger = logging.getLogger("eodag.search.qssearch.postjsonsearch")


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
        * :attr:`~eodag.config.PluginConfig.Pagination.max_limit` (``int``): The maximum number of items
          per page that the provider can handle; default: ``50``

    """

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> SearchResult:
        """Perform a search on an OpenSearch-like interface"""
        collection = kwargs.get("collection", "")
        count = prep.count
        raise_errors = getattr(prep, "raise_errors", False)
        number_matched = kwargs.pop("number_matched", None)
        sort_by_arg: Optional[SortByList] = self.get_sort_by_arg(kwargs)
        _, sort_by_qp = (
            ("", {}) if sort_by_arg is None else self.build_sort_by(sort_by_arg)
        )
        provider_collection = self.map_collection(collection)
        _dc_qs = kwargs.pop("_dc_qs", None)
        if _dc_qs is not None:
            qs = unquote_plus(unquote_plus(_dc_qs))
            qp = geojson.loads(qs)

            # provider collection specific conf
            prep.collection_def_params = self.get_collection_def_params(
                collection, format_variables=kwargs
            )
        else:
            keywords = {
                k: v
                for k, v in kwargs.items()
                if k not in ("auth", "collection") and v is not None
            }

            if provider_collection and provider_collection != GENERIC_COLLECTION:
                keywords["_collection"] = provider_collection
            elif collection:
                keywords["_collection"] = collection

            # provider collection specific conf
            prep.collection_def_params = self.get_collection_def_params(
                collection, format_variables=kwargs
            )

            # Add to the query, the queryable parameters set in the provider collection definition
            collection_metadata_mapping = {
                **getattr(self.config, "metadata_mapping", {}),
                **prep.collection_def_params.get("metadata_mapping", {}),
            }
            keywords.update(
                {
                    k: v
                    for k, v in prep.collection_def_params.items()
                    if k not in keywords.keys()
                    and k in collection_metadata_mapping.keys()
                    and isinstance(collection_metadata_mapping[k], list)
                }
            )

            qp, _ = self.build_query_string(collection, keywords)

        # Force sort qp list parameters
        for key in qp:
            if isinstance(qp[key], list):
                qp[key].sort()

        for query_param, query_value in qp.items():
            if (
                query_param
                in self.config.products.get(collection, {}).get(
                    "specific_qssearch", {"parameters": []}
                )["parameters"]
            ):
                # config backup
                plugin_config_backup = yaml.dump(self.config)

                self.config.api_endpoint = query_value
                self.config.products[collection][
                    "metadata_mapping"
                ] = mtd_cfg_as_conversion_and_querypath(
                    self.config.products[collection]["specific_qssearch"][
                        "metadata_mapping"
                    ]
                )
                self.config.results_entry = self.config.products[collection][
                    "specific_qssearch"
                ]["results_entry"]
                self.config._collection = self.config.products[collection][
                    "specific_qssearch"
                ].get("_collection")
                self.config.merge_responses = self.config.products[collection][
                    "specific_qssearch"
                ].get("merge_responses")

                def count_hits(self, *x, **y):
                    return 1

                def _request(self, *x, **y):
                    return super(PostJsonSearch, self)._request(*x, **y)

                try:
                    eo_products = super(PostJsonSearch, self).query(prep, **kwargs)
                except Exception:
                    raise
                finally:
                    # restore config
                    self.config = yaml.load(
                        plugin_config_backup, self.config.yaml_loader
                    )

                return eo_products

        # If we were not able to build query params but have queryable search criteria,
        # this means the provider does not support the search criteria given. If so,
        # stop searching right away
        collection_metadata_mapping = dict(
            self.config.metadata_mapping,
            **prep.collection_def_params.get("metadata_mapping", {}),
        )
        if not qp and any(
            k
            for k in keywords.keys()
            if isinstance(collection_metadata_mapping.get(k), list)
        ):
            result = SearchResult([])
            if prep.count:
                result.number_matched = 0
            return result
        prep.query_params = dict(qp, **sort_by_qp)
        prep.search_urls, total_items = self.collect_search_urls(prep, **kwargs)
        if not count and getattr(prep, "need_count", False):
            # do not try to extract total_items from search results if count is False
            del prep.total_items_nb
            del prep.need_count

        provider_results = self.do_search(prep, **kwargs)
        if count and total_items is None and hasattr(prep, "total_items_nb"):
            total_items = prep.total_items_nb
        if not count and "number_matched" in kwargs and number_matched:
            total_items = number_matched

        eo_products_normalize = self.normalize_results(provider_results, **kwargs)
        formated_result = SearchResult(
            eo_products_normalize,
            total_items,
            search_params=provider_results.search_params,
            next_page_token=getattr(provider_results, "next_page_token", None),
            next_page_token_key=getattr(provider_results, "next_page_token_key", None),
            raise_errors=raise_errors,
        )
        return formated_result

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> list[EOProduct]:
        """Build EOProducts from provider results"""
        normalized = super().normalize_results(results, **kwargs)

        # @TODO to rework with download_link asset
        for product in normalized:
            if "eodag:download_link" in product.properties:
                decoded_link = unquote(product.properties["eodag:download_link"])
                if decoded_link[0] == "{":  # not a url but a dict
                    default_values = deepcopy(
                        self.config.products.get(product.collection, {})  # type: ignore
                    )
                    default_values.pop("metadata_mapping", None)
                    searched_values = orjson.loads(decoded_link)
                    _dc_qs = orjson.dumps(
                        format_query_params(
                            product.collection,  # type: ignore
                            self.config,
                            {**default_values, **searched_values},
                        )
                    )
                    product.properties["_dc_qs"] = quote_plus(_dc_qs)

            # workaround to add collection to wekeo cmems order links
            if (
                "eodag:order_link" in product.properties
                and "collection" in product.properties["eodag:order_link"]
                and "order" not in product.properties["eodag:order_link"]
            ):
                product.properties["eodag:order_link"] = product.properties[
                    "eodag:order_link"
                ].replace("collection", product.collection)
        return normalized

    def collect_search_urls(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> tuple[list[str], Optional[int]]:
        """Adds pagination to query parameters, and auth to url"""
        token = getattr(prep, "next_page_token", None)
        limit = prep.limit
        count = prep.count
        urls: list[str] = []
        total_results = 0 if count else None
        next_page_token_key = prep.next_page_token_key or self.config.pagination.get(
            "next_page_token_key"
        )

        if "count_endpoint" not in self.config.pagination:
            # if count_endpoint is not set, total_results should be extracted from search result
            total_results = None
            prep.need_count = True
            prep.total_items_nb = None

        if prep.auth_plugin is not None and hasattr(prep.auth_plugin, "config"):
            auth_conf_dict = getattr(prep.auth_plugin.config, "credentials", {})
        else:
            auth_conf_dict = {}
        for _collection in self.get_provider_collections(prep, **kwargs) or (None,):
            try:
                search_endpoint: str = self.config.api_endpoint.rstrip("/").format(
                    **dict(_collection=_collection, **auth_conf_dict)
                )
            except KeyError as e:
                provider = prep.auth_plugin.provider if prep.auth_plugin else ""
                raise MisconfiguredError(
                    "Missing %s in %s configuration" % (",".join(e.args), provider)
                )
            # numeric page token
            if (
                next_page_token_key == "page" or next_page_token_key == "skip"
            ) and limit is not None:
                if token is None and next_page_token_key == "skip":
                    # first page & next_page_token_key == skip
                    token = max(
                        0, self.config.pagination.get("start_page", DEFAULT_PAGE) - 1
                    )
                elif token is None:
                    # first page & next_page_token_key == page
                    token = self.config.pagination.get("start_page", DEFAULT_PAGE)
                else:
                    # next pages
                    token = int(token)
                if count:
                    count_endpoint = self.config.pagination.get(
                        "count_endpoint", ""
                    ).format(**dict(_collection=_collection, **auth_conf_dict))
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
            # parse next page url if needed
            if "next_page_url_tpl" in self.config.pagination:
                search_endpoint = self.config.pagination["next_page_url_tpl"].format(
                    url=search_endpoint,
                    limit=limit,
                    next_page_token=token,
                )

            # parse next page body / query-obj if needed
            if "next_page_query_obj" in self.config.pagination and isinstance(
                self.config.pagination["next_page_query_obj"], str
            ):
                if next_page_token_key is None or token is None:
                    next_page_token_kwargs = {
                        "next_page_token": -1,
                        "next_page_token_key": NOT_AVAILABLE,
                    }
                else:
                    next_page_token_kwargs = {
                        "next_page_token": token,
                        "next_page_token_key": next_page_token_key,
                    }
                next_page_token_kwargs["next_page_token_key"] = (
                    next_page_token_key or NOT_AVAILABLE
                )
                next_page_token_kwargs["next_page_token"] = (
                    token if token is not None else -1
                )

                # next_page_query_obj needs to be parsed
                next_page_query_obj_str = self.config.pagination[
                    "next_page_query_obj"
                ].format(limit=limit, **next_page_token_kwargs)
                next_page_query_obj = orjson.loads(next_page_query_obj_str)
                # remove NOT_AVAILABLE entries
                next_page_query_obj.pop(NOT_AVAILABLE, None)
                if (
                    next_page_token_key
                    and next_page_query_obj.get(next_page_token_key) == "-1"
                ):
                    next_page_query_obj.pop(next_page_token_key, None)
                # update prep query_params with pagination info
                update_nested_dict(prep.query_params, next_page_query_obj)

            if token is not None:
                prep.next_page_token = token

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
            if response.status_code and response.status_code == 429:
                raise QuotaExceededError(
                    f"Too many requests on provider {self.provider}, please check your quota!"
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


__all__ = ["PostJsonSearch"]
