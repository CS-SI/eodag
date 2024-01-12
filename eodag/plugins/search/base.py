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
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

from typing_extensions import Annotated

from eodag.api.product.metadata_mapping import (
    DEFAULT_METADATA_MAPPING,
    mtd_cfg_as_conversion_and_querypath,
)
from eodag.plugins.base import PluginTopic
from eodag.utils import (
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_PAGE,
    GENERIC_PRODUCT_TYPE,
    format_dict_items,
)
from eodag.utils.exceptions import ValidationError

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from eodag.api.product import EOProduct
    from eodag.config import PluginConfig
    from eodag.utils import Annotated

logger = logging.getLogger("eodag.search.base")


class Search(PluginTopic):
    """Base Search Plugin.

    :param provider: An EODAG provider name
    :type provider: str
    :param config: An EODAG plugin configuration
    :type config: :class:`~eodag.config.PluginConfig`
    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(Search, self).__init__(provider, config)
        # Prepare the metadata mapping
        # Do a shallow copy, the structure is flat enough for this to be sufficient
        metas = DEFAULT_METADATA_MAPPING.copy()
        # Update the defaults with the mapping value. This will add any new key
        # added by the provider mapping that is not in the default metadata
        if self.config.metadata_mapping:
            metas.update(self.config.metadata_mapping)
        self.config.metadata_mapping = mtd_cfg_as_conversion_and_querypath(
            metas,
            self.config.metadata_mapping,
            result_type=getattr(self.config, "result_type", "json"),
        )

    def clear(self) -> None:
        """Method used to clear a search context between two searches."""
        pass

    def query(
        self,
        product_type: Optional[str] = None,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        page: int = DEFAULT_PAGE,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[EOProduct], Optional[int]]:
        """Implementation of how the products must be searched goes here.

        This method must return a tuple with (1) a list of EOProduct instances (see eodag.api.product module)
        which will be processed by a Download plugin (2) and the total number of products matching
        the search criteria. If ``count`` is False, the second element returned must be ``None``.
        """
        raise NotImplementedError("A Search plugin must implement a method named query")

    def discover_product_types(self) -> Optional[Dict[str, Any]]:
        """Fetch product types list from provider using `discover_product_types` conf"""
        return None

    def discover_queryables(
        self, product_type: Optional[str] = None
    ) -> Optional[Dict[str, Tuple[Annotated[Any, FieldInfo], Any]]]:
        """Fetch queryables list from provider using `discover_queryables` conf"""
        return None

    def map_product_type(
        self, product_type: Optional[str], **kwargs: Any
    ) -> Optional[str]:
        """Get the provider product type from eodag product type

        :param product_type: eodag product type
        :type product_type: str
        :returns: provider product type
        :rtype: str
        """
        if product_type is None:
            return None
        logger.debug("Mapping eodag product type to provider product type")
        return self.config.products.get(product_type, {}).get(
            "productType", GENERIC_PRODUCT_TYPE
        )

    def get_product_type_def_params(
        self, product_type: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Get the provider product type definition parameters and specific settings

        :param product_type: the desired product type
        :type product_type: str
        :returns: The product type definition parameters
        :rtype: dict
        """
        if product_type in self.config.products.keys():
            logger.debug(
                "Getting provider product type definition parameters for %s",
                product_type,
            )
            return self.config.products[product_type]
        elif GENERIC_PRODUCT_TYPE in self.config.products.keys():
            logger.debug(
                "Getting generic provider product type definition parameters for %s",
                product_type,
            )
            return {
                k: v
                for k, v in format_dict_items(
                    self.config.products[GENERIC_PRODUCT_TYPE], **kwargs
                ).items()
                if v
            }
        else:
            return {}

    def get_metadata_mapping(
        self, product_type: Optional[str] = None
    ) -> Dict[str, str]:
        """Get the plugin metadata mapping configuration (product type specific if exists)

        :param product_type: the desired product type
        :type product_type: str
        :returns: The product type specific metadata-mapping
        :rtype: dict
        """
        return self.config.products.get(product_type, {}).get(
            "metadata_mapping", self.config.metadata_mapping
        )

    def transform_sort_by_params_for_search_request(self) -> None:
        """Build the sorting part of the query string or body by transforming
        the "sortBy" parameter into a provider-specific string or dictionnary"""
        if not hasattr(self.config, "sort"):
            raise ValidationError(
                "{} does not support sorting feature".format(self.provider)
            )
        # remove duplicates
        self.sort_by_params = list(set(self.sort_by_params))
        sort_by_params: Union[str, Dict[str, List[Dict[str, str]]]]
        if self.config.sort.get("sort_url_tpl"):
            sort_by_params = ""
        else:
            sort_by_keyword_in_search_body = list(
                self.config.sort["sort_body_tpl"].keys()
            )[0]
            sort_by_params = {sort_by_keyword_in_search_body: []}
        sort_by_params_tmp = []
        for sort_by_param_arg in self.sort_by_params:
            # Remove leading and trailing whitespace(s) if exist
            eodag_sort_param = sort_by_param_arg[0]
            try:
                provider_sort_param = self.config.sort["sort_by_mapping"][
                    eodag_sort_param
                ]
            except KeyError:
                params = set(self.config.sort["sort_by_mapping"].keys())
                params.add(eodag_sort_param)
                raise ValidationError(
                    "'{}' parameter is not sortable with {}. "
                    "Here is the list of sortable parameter(s) with {}: {}".format(
                        eodag_sort_param,
                        self.provider,
                        self.provider,
                        ", ".join(
                            k for k in self.config.sort["sort_by_mapping"].keys()
                        ),
                    ),
                    params,
                )
            sort_order = sort_by_param_arg[1]
            sort_by_param: Union[Tuple[str, str], Dict[str, str]]
            if sort_order == "ASC" and self.config.sort.get("sort_url_tpl"):
                sort_by_param = (provider_sort_param, "asc")
            elif sort_order == "ASC":
                sort_by_param = {"field": provider_sort_param, "direction": "asc"}
            elif sort_order == "DES" and self.config.sort.get("sort_url_tpl"):
                sort_by_param = (provider_sort_param, "desc")
            else:
                sort_by_param = {"field": provider_sort_param, "direction": "desc"}
            for sort_by_param_tmp in sort_by_params_tmp:
                # since duplicated tuples or dictionnaries have been removed, if two sorting parameters are equal,
                # then their sorting order is different and there is a contradiction that would raise an error
                if (
                    self.config.sort.get("sort_url_tpl")
                    and sort_by_param[0] == sort_by_param_tmp[0]
                    or self.config.sort.get("sort_body_tpl")
                    and sort_by_param["field"] == sort_by_param_tmp["field"]
                ):
                    raise ValidationError(
                        "'{}' parameter is called several times to sort results with different sorting orders. "
                        "Please set it to only one ('ASC' (ASCENDING) or 'DESC' (DESCENDING))".format(
                            eodag_sort_param
                        ),
                        set([eodag_sort_param]),
                    )
            sort_by_params_tmp.append(sort_by_param)
            # check if the limit number of sorting parameter(s) is respected with this sorting parameter
            if (
                self.config.sort.get("max_sort_params", None)
                and len(sort_by_params_tmp) > self.config.sort["max_sort_params"]
            ):
                raise ValidationError(
                    "Search results can be sorted by only "
                    "{} parameter(s) with {}".format(
                        self.config.sort["max_sort_params"], self.provider
                    )
                )
            if self.config.sort.get("sort_url_tpl"):
                sort_by_params += self.config.sort["sort_url_tpl"].format(
                    sort_param=sort_by_param[0], sort_order=sort_by_param[1]
                )
            else:
                sort_by_params[sort_by_keyword_in_search_body].append(sort_by_param)
        self.sort_by_params = sort_by_params
        return None
