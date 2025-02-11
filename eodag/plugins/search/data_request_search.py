# -*- coding: utf-8 -*-
# Copyright 2023, CS GROUP - France, https://www.csgroup.eu/
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
import time
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional, cast

import requests

from eodag import EOProduct
from eodag.api.product.metadata_mapping import (
    format_query_params,
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
)
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.base import Search
from eodag.utils import (
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_MISSION_START_DATE,
    DEFAULT_PAGE,
    DEFAULT_SEARCH_TIMEOUT,
    GENERIC_PRODUCT_TYPE,
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    deepcopy,
    string_to_jsonpath,
)
from eodag.utils.exceptions import (
    NotAvailableError,
    RequestError,
    TimeOutError,
    ValidationError,
)

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.data_request_search")


class DataRequestSearch(Search):
    """
    Plugin to execute search requests composed of several steps:

    #. do a data request which defines which data shall be searched
    #. check the status of the request job
    #. if finished - fetch the result of the job

    :param provider: provider name
    :param config: Search plugin configuration:

        * :attr:`~eodag.config.PluginConfig.api_endpoint` (``str``) (**mandatory**): The endpoint of the
          provider's search interface
        * :attr:`~eodag.config.PluginConfig.results_entry` (``str``) (**mandatory**): The name of
          the key in the provider search result that gives access to the result entries
        * :attr:`~eodag.config.PluginConfig.data_request_url` (``str``) (**mandatory**): url
          to which the data request shall be sent
        * :attr:`~eodag.config.PluginConfig.status_url` (``str``) (**mandatory**): url to fetch
          the status of the data request
        * :attr:`~eodag.config.PluginConfig.result_url` (``str``) (**mandatory**): url to fetch
          the search result when the data request is done
        * :attr:`~eodag.config.PluginConfig.need_auth` (``bool``): if authentication is needed for
          the search request; default: ``False``
        * :attr:`~eodag.config.PluginConfig.auth_error_code` (``int``): which error code is returned in case of an
          authentication error; only used if ``need_auth=true``
        * :attr:`~eodag.config.PluginConfig.ssl_verify` (``bool``): if the ssl certificates should be
          verified in requests; default: ``True``
        * :attr:`~eodag.config.PluginConfig.timeout` (``int``): time to wait until request timeout in seconds;
          default: ``5``
        * :attr:`~eodag.config.PluginConfig.dates_required` (``bool``): if date parameters are mandatory
          in the request; default: ``True``
        * :attr:`~eodag.config.PluginConfig.pagination` (:class:`~eodag.config.PluginConfig.Pagination`)
          (**mandatory**): The configuration of how the pagination is done on the provider. It is a tree with the
          following nodes:

          * :attr:`~eodag.config.PluginConfig.Pagination.total_items_nb_key_path` (``str``):  An XPath or JsonPath
            leading to the total number of results satisfying a request. This is used for providers which provides the
            total results metadata along with the result of the query and don't have an endpoint for querying
            the number of items satisfying a request, or for providers for which the count endpoint
            returns a json or xml document
          * :attr:`~eodag.config.PluginConfig.Pagination.max_items_per_page` (``int``): The maximum
            number of items per page that the provider can handle; default: ``50``
          * :attr:`~eodag.config.PluginConfig.Pagination.start_page` (``int``): number of the
            first page; default: ``1``

        * :attr:`~eodag.config.PluginConfig.discover_product_types`
          (:class:`~eodag.config.PluginConfig.DiscoverProductTypes`): configuration for product type discovery based on
          information from the provider; It contains the keys:

          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.fetch_url` (``str``) (**mandatory**): url from which
            the product types can be fetched
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
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.single_collection_fetch_url` (``str``): url to fetch
            data for a single collection; used if product type metadata is not available from the endpoint given in
            :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.fetch_url`
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.single_collection_fetch_qs` (``str``): query string
            to be added to the :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.fetch_url` to filter for a
            collection
          * :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.single_product_type_parsable_metadata`
            (``dict[str, str]``): mapping for product type metadata returned by the endpoint given in
            :attr:`~eodag.config.PluginConfig.DiscoverProductTypes.single_collection_fetch_url`.

        * :attr:`~eodag.config.PluginConfig.constraints_file_url` (``str``): url to fetch the constraints for a specific
          product type, can be an http url or a path to a file; the constraints are used to build queryables
        * :attr:`~eodag.config.PluginConfig.constraints_entry` (``str``): key in the json result where the constraints
          can be found; if not given, it is assumed that the constraints are on top level of the result, i.e.
          the result is an array of constraints
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

    """

    data_request_id: Optional[str]

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(DataRequestSearch, self).__init__(provider, config)
        self.config.__dict__.setdefault("result_type", "json")
        self.config.__dict__.setdefault("results_entry", "content")
        self.config.__dict__.setdefault("pagination", {})
        self.config.__dict__.setdefault("free_text_search_operations", {})
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
                other_product_for_mapping = self.config.products[product_type].get(
                    "metadata_mapping_from_product", ""
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

        if (
            self.config.result_type == "json"
            and "next_page_url_key_path" in self.config.pagination
        ):
            self.config.pagination["next_page_url_key_path"] = string_to_jsonpath(
                self.config.pagination.get("next_page_url_key_path", None)
            )
        self.download_info: dict[str, Any] = {}
        self.data_request_id = None

    def discover_product_types(self, **kwargs: Any) -> Optional[dict[str, Any]]:
        """Fetch product types is disabled for `DataRequestSearch`

        :returns: empty dict
        """
        return None

    def clear(self) -> None:
        """Clear search context"""
        super().clear()
        self.data_request_id = None

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> tuple[list[EOProduct], Optional[int]]:
        """
        performs the search for a provider where several steps are required to fetch the data
        """
        if kwargs.get("sort_by"):
            raise ValidationError(f"{self.provider} does not support sorting feature")

        product_type = kwargs.get("productType", None)

        if product_type is None:
            raise ValidationError("Required productType is missing")

        # replace "product_type" to "providerProductType" in search args if exists
        # for compatibility with DataRequestSearch method
        if kwargs.get("product_type"):
            kwargs["providerProductType"] = kwargs.pop("product_type", None)
        provider_product_type = cast(str, self._map_product_type(product_type or ""))
        keywords = {k: v for k, v in kwargs.items() if k != "auth" and v is not None}

        if provider_product_type and provider_product_type != GENERIC_PRODUCT_TYPE:
            keywords["productType"] = provider_product_type
        else:
            keywords["productType"] = product_type

        # provider product type specific conf
        self.product_type_def_params = self.get_product_type_def_params(
            product_type, format_variables=kwargs
        )

        # update config using provider product type definition metadata_mapping
        # from another product
        other_product_for_mapping = self.product_type_def_params.get(
            "metadata_mapping_from_product", ""
        )
        if other_product_for_mapping:
            other_product_type_def_params = self.get_product_type_def_params(
                other_product_for_mapping, format_variables=kwargs
            )
            self.config.metadata_mapping.update(
                other_product_type_def_params.get("metadata_mapping", {})
            )
        # from current product
        self.config.metadata_mapping.update(
            self.product_type_def_params.get("metadata_mapping", {})
        )

        # if product_type_def_params is set, remove product_type as it may conflict with this conf
        if self.product_type_def_params:
            keywords.pop("productType", None)
        keywords.update(
            {
                k: v
                for k, v in self.product_type_def_params.items()
                if k not in keywords.keys()
                and k in self.config.metadata_mapping.keys()
                and isinstance(self.config.metadata_mapping[k], list)
            }
        )

        # update dates if needed
        if getattr(self.config, "dates_required", True) and "id" not in keywords:
            if not keywords.get("startTimeFromAscendingNode", None):
                keywords["startTimeFromAscendingNode"] = getattr(
                    self.config, "product_type_config", {}
                ).get("missionStartDate", DEFAULT_MISSION_START_DATE)
            if not keywords.get("completionTimeFromAscendingNode", None):
                keywords["completionTimeFromAscendingNode"] = getattr(
                    self.config, "product_type_config", {}
                ).get("missionEndDate", datetime.now(timezone.utc).isoformat())

        # ask for data_request_id if not set (it must exist when iterating over pages)
        if not self.data_request_id:
            data_request_id = self._create_data_request(
                provider_product_type, product_type, **keywords
            )
            self.data_request_id = data_request_id
            request_finished = False
        else:
            data_request_id = self.data_request_id
            request_finished = True

        # loop to check search job status
        search_timeout = int(getattr(self.config, "timeout", DEFAULT_SEARCH_TIMEOUT))
        logger.info(
            f"checking status of request job {data_request_id} (timeout={search_timeout}s)"
        )
        check_beginning = datetime.now()
        while not request_finished:
            request_finished = self._check_request_status(data_request_id)
            if not request_finished and datetime.now() >= check_beginning + timedelta(
                seconds=search_timeout
            ):
                self._cancel_request(data_request_id)
                raise NotAvailableError(
                    f"Timeout reached when checking search job status for {self.provider}"
                )
            elif not request_finished:
                time.sleep(1)

        logger.info("search job for product_type %s finished", provider_product_type)
        result = self._get_result_data(
            data_request_id,
            kwargs.get("items_per_page", DEFAULT_ITEMS_PER_PAGE),
            kwargs.get("page", DEFAULT_PAGE),
        )
        # if exists, add the geometry from search args in the content of the response for each product
        if keywords.get("geometry"):
            for product_content in result["content"]:
                if product_content["extraInformation"] is None:
                    product_content["extraInformation"] = {
                        "footprint": keywords["geometry"]
                    }
                elif not product_content["extraInformation"].get("footprint"):
                    product_content["extraInformation"]["footprint"] = keywords[
                        "geometry"
                    ]
        logger.info("result retrieved from search job")
        if self._check_uses_custom_filters(product_type):
            result = self._apply_additional_filters(
                result, self.config.products[product_type]["custom_filters"]
            )
        return self._convert_result_data(
            result, data_request_id, product_type or "", **kwargs
        )

    def _create_data_request(
        self, product_type: str, eodag_product_type: str, **kwargs: Any
    ) -> str:
        headers = getattr(self.auth, "headers", USER_AGENT)
        ssl_verify = getattr(self.config.ssl_verify, "ssl_verify", True)
        try:
            url = self.config.data_request_url
            request_body = format_query_params(eodag_product_type, self.config, kwargs)
            logger.debug(
                f"Sending search job request to {url} with {str(request_body)}"
            )
            request_job = requests.post(
                url,
                json=request_body,
                headers=headers,
                timeout=HTTP_REQ_TIMEOUT,
                verify=ssl_verify,
            )
            request_job.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
        except requests.RequestException as e:
            raise RequestError.from_error(
                e, f"search job for product_type {product_type} could not be created"
            ) from e
        else:
            logger.info("search job for product_type %s created", product_type)
            return request_job.json()["jobId"]

    def _cancel_request(self, data_request_id: str) -> None:
        logger.info("deleting request job %s", data_request_id)
        delete_url = f"{self.config.data_request_url}/{data_request_id}"
        headers = getattr(self.auth, "headers", USER_AGENT)
        try:
            delete_resp = requests.delete(
                delete_url, headers=headers, timeout=HTTP_REQ_TIMEOUT
            )
            delete_resp.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
        except requests.RequestException as e:
            raise RequestError.from_error(e, "_cancel_request failed") from e

    def _check_request_status(self, data_request_id: str) -> bool:
        logger.debug("checking status of request job %s", data_request_id)
        status_url = self.config.status_url + data_request_id
        headers = getattr(self.auth, "headers", USER_AGENT)
        ssl_verify = getattr(self.config, "ssl_verify", True)

        try:
            status_resp = requests.get(
                status_url,
                headers=headers,
                timeout=HTTP_REQ_TIMEOUT,
                verify=ssl_verify,
            )
            status_resp.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
        except requests.RequestException as e:
            raise RequestError.from_error(e, "_check_request_status failed") from e
        else:
            status_data = status_resp.json()
            if "status_code" in status_data and status_data["status_code"] in [
                403,
                404,
            ]:
                logger.error(f"_check_request_status failed: {status_data}")
                error = RequestError("authentication token expired during request")
                error.status_code = status_data["status_code"]
                raise error
            if status_data["status"] == "failed":
                logger.error(f"_check_request_status failed: {status_data}")
                raise RequestError(
                    f"data request job has failed, message: {status_data['message']}"
                )
            return status_data["status"] == "completed"

    def _get_result_data(
        self, data_request_id: str, items_per_page: int, page: int
    ) -> dict[str, Any]:
        page = page - 1 + self.config.pagination.get("start_page", 1)
        url = self.config.result_url.format(
            jobId=data_request_id, items_per_page=items_per_page, page=page
        )
        ssl_verify = getattr(self.config, "ssl_verify", True)
        headers = getattr(self.auth, "headers", USER_AGENT)
        try:
            return requests.get(
                url, headers=headers, timeout=HTTP_REQ_TIMEOUT, verify=ssl_verify
            ).json()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=HTTP_REQ_TIMEOUT) from exc
        except requests.RequestException:
            logger.error(f"Result could not be retrieved for {url}")
        return {}

    def _convert_result_data(
        self,
        result_data: dict[str, Any],
        data_request_id: str,
        product_type: str,
        **kwargs: Any,
    ) -> tuple[list[EOProduct], int]:
        """Build EOProducts from provider results"""
        results_entry = self.config.results_entry
        results = result_data[results_entry]
        logger.debug(
            "Adapting %s plugin results to eodag product representation" % len(results)
        )
        products: list[EOProduct] = []
        for result in results:
            product = EOProduct(
                self.provider,
                properties_from_json(
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
        # postprocess filtering needed when provider does not natively offer filtering by id
        if "id" in kwargs:
            products = [
                p for p in products if product.properties["id"] == kwargs["id"]
            ] or products
        total_items_nb_key_path = string_to_jsonpath(
            self.config.pagination["total_items_nb_key_path"]
        )
        found_total_items_nb_paths = total_items_nb_key_path.find(results)
        if found_total_items_nb_paths and not isinstance(
            found_total_items_nb_paths, int
        ):
            total_items_nb = found_total_items_nb_paths[0].value
        else:
            total_items_nb = 0
        for p in products:
            # add the request id to the order link property (required to create data order)
            p.properties["orderLink"] = p.properties["orderLink"].replace(
                "requestJobId", str(data_request_id)
            )
            if self.config.products[product_type].get("storeDownloadUrl", False):
                # store download information to retrieve it later in case search by id
                # is not possible
                self.download_info[p.properties["id"]] = {
                    "requestJobId": data_request_id,
                    "orderLink": p.properties["orderLink"],
                    "downloadLink": p.properties["downloadLink"],
                    "provider": self.provider,
                }
        return products, total_items_nb

    def _check_uses_custom_filters(self, product_type: str) -> bool:
        if (
            product_type in self.config.products
            and "custom_filters" in self.config.products[product_type]
        ):
            return True
        return False

    def _apply_additional_filters(
        self, result: dict[str, Any], custom_filters: dict[str, str]
    ) -> dict[str, Any]:
        filtered_result = []
        results_entry = self.config.results_entry
        results = result[results_entry]
        path = string_to_jsonpath(custom_filters["filter_attribute"])
        indexes = custom_filters["indexes"].split("-")
        for record in results:
            found_paths = path.find(record)
            if not found_paths or isinstance(found_paths, int):
                continue
            filter_param = found_paths[0].value
            filter_value = filter_param[int(indexes[0]) : int(indexes[1])]
            filter_clause = "'" + filter_value + "' " + custom_filters["filter_clause"]
            if eval(filter_clause):
                filtered_result.append(record)
        result[results_entry] = filtered_result
        return result

    def _map_product_type(self, product_type: Optional[str]) -> Optional[str]:
        """Map the eodag product type to the provider product type"""
        if product_type is None:
            return None
        logger.debug("Mapping eodag product type to provider product type")
        return self.config.products.get(product_type, {}).get(
            "productType", GENERIC_PRODUCT_TYPE
        )
