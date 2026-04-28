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
from typing import TYPE_CHECKING, Any

import requests

from eodag.api.product import EOProduct
from eodag.api.search_result import RawSearchResult
from eodag.utils import HTTP_REQ_TIMEOUT, USER_AGENT, string_to_jsonpath
from eodag.utils.exceptions import TimeOutError

from ..preparesearch import PreparedSearch
from .querystringsearch import QueryStringSearch

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.qssearch.odatav4search")


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
                          # 'sensingStartDate:[{start_datetime}Z TO *]'
                  - <op2>    # e.g:
                      # 'sensingStopDate:[* TO {end_datetime}Z]'
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
        metadata_path = metadata_pre_mapping.get("metadata_path")
        metadata_path_id = metadata_pre_mapping.get("metadata_path_id")
        metadata_path_value = metadata_pre_mapping.get("metadata_path_value")
        if metadata_path and metadata_path_id and metadata_path_value:
            self.config.metadata_pre_mapping["metadata_path"] = string_to_jsonpath(
                metadata_path
            )

    def do_search(
        self, prep: PreparedSearch = PreparedSearch(), **kwargs: Any
    ) -> RawSearchResult:
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
                except requests.RequestException as e:
                    if (
                        e.response
                        and e.response.status_code
                        and e.response.status_code == 429
                    ):
                        logger.error(
                            f"Too many requests on provider {self.provider}, please check your quota!"
                        )
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
            raw_search_results = RawSearchResult(final_result)
            raw_search_results.search_params = kwargs
            raw_search_results.query_params = (
                prep.query_params if hasattr(prep, "query_params") else {}
            )
            raw_search_results.collection_def_params = (
                prep.collection_def_params
                if hasattr(prep, "collection_def_params")
                else {}
            )
            return raw_search_results
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
        metadata_path = metadata_pre_mapping.get("metadata_path")
        metadata_path_id = metadata_pre_mapping.get("metadata_path_id")
        metadata_path_value = metadata_pre_mapping.get("metadata_path_value")

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


__all__ = ["ODataV4Search"]
