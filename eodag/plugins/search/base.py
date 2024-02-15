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

from pydantic.fields import Field, FieldInfo
from typing_extensions import Annotated

from eodag.api.product.metadata_mapping import (
    DEFAULT_METADATA_MAPPING,
    mtd_cfg_as_conversion_and_querypath,
)
from eodag.plugins.base import PluginTopic
from eodag.types.search_args import SortByList
from eodag.utils import (
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_PAGE,
    GENERIC_PRODUCT_TYPE,
    Annotated,
    format_dict_items,
)
from eodag.utils.exceptions import ValidationError

if TYPE_CHECKING:
    from eodag.api.product import EOProduct
    from eodag.config import PluginConfig

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
        self, **kwargs: Any
    ) -> Optional[Dict[str, Annotated[Any, FieldInfo]]]:
        """Fetch queryables list from provider using `discover_queryables` conf

        :param kwargs: additional filters for queryables (`productType` and other search
                       arguments)
        :type kwargs: Any
        :returns: fetched queryable parameters dict
        :rtype: Optional[Dict[str, Annotated[Any, FieldInfo]]]
        """
        return None

    def get_defaults_as_queryables(
        self, product_type: str
    ) -> Dict[str, Annotated[Any, FieldInfo]]:
        """
        Return given product type defaut settings as queryables

        :param product_type: given product type
        :type product_type: str
        :returns: queryable parameters dict
        :rtype: Dict[str, Annotated[Any, FieldInfo]]
        """
        defaults = self.config.products.get(product_type, {})
        queryables = {}
        for parameter, value in defaults.items():
            queryables[parameter] = Annotated[type(value), Field(default=value)]
        return queryables

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

    def get_sort_by_arg(self, kwargs: Dict[str, Any]) -> Optional[SortByList]:
        """Extract the "sortBy" argument from the kwargs or the provider default sort configuration

        :param kwargs: Search arguments
        :type kwargs: Dict[str, Any]
        :returns: The "sortBy" argument from the kwargs or the provider default sort configuration
        :rtype: :class:`~eodag.types.search_args.SortByList`
        """
        # remove "sortBy" from search args if exists because it is not part of metadata mapping,
        # it will complete the query string or body once metadata mapping will be done
        sort_by_arg_tmp = kwargs.pop("sortBy", None)
        sort_by_arg = sort_by_arg_tmp or getattr(self.config, "sort", {}).get(
            "sort_by_default", None
        )
        if not sort_by_arg_tmp and sort_by_arg:
            logger.info(
                f"{self.provider} is configured with default sorting by '{sort_by_arg[0][0]}' "
                f"in {'ascending' if sort_by_arg[0][1] == 'ASC' else 'descending'} order"
            )
        return sort_by_arg

    def transform_sort_by_arg_for_search_request(
        self, sort_by_arg: SortByList
    ) -> Union[str, Dict[str, List[Dict[str, str]]]]:
        """Build the sorting part of the query string or body by transforming
        the "sortBy" argument into a provider-specific string or dictionnary

        :param sort_by_arg: the "sortBy" argument in EODAG format
        :type sort_by_arg: :class:`~eodag.types.search_args.SortByList`
        :returns: The "sortBy" argument in provider-specific format
        :rtype: Union[str, Dict[str, List[Dict[str, str]]]]
        """
        if not hasattr(self.config, "sort"):
            raise ValidationError(
                "{} does not support sorting feature".format(self.provider)
            )
        # remove duplicates
        sort_by_arg = list(set(sort_by_arg))
        sort_by_params: Union[str, Dict[str, List[Dict[str, str]]]]
        if self.config.sort.get("sort_url_tpl"):
            sort_by_provider_keyword = None
            sort_by_params = ""
        else:
            sort_by_provider_keyword = list(self.config.sort["sort_body_tpl"].keys())[0]
            sort_by_params = {sort_by_provider_keyword: []}
        sort_by_params_tmp: List[Dict[str, str]] = []
        sort_by_param: Dict[str, str]
        for one_sort_by_param in sort_by_arg:
            eodag_sort_param = one_sort_by_param[0]
            try:
                provider_sort_param = self.config.sort["sort_param_mapping"][
                    eodag_sort_param
                ]
            except KeyError:
                params = set(self.config.sort["sort_param_mapping"].keys())
                params.add(eodag_sort_param)
                raise ValidationError(
                    "'{}' parameter is not sortable with {}. "
                    "Here is the list of sortable parameter(s) with {}: {}".format(
                        eodag_sort_param,
                        self.provider,
                        self.provider,
                        ", ".join(
                            k for k in self.config.sort["sort_param_mapping"].keys()
                        ),
                    ),
                    params,
                )
            eodag_sort_order = one_sort_by_param[1]
            # TODO: remove this code block when search args model validation is embeded
            # Remove leading and trailing whitespace(s) if exist
            eodag_sort_order = eodag_sort_order.strip().upper()
            if eodag_sort_order[:3] != "ASC" and eodag_sort_order[:3] != "DES":
                raise ValidationError(
                    "Sorting order is invalid: it must be set to 'ASC' (ASCENDING) or "
                    f"'DESC' (DESCENDING), got '{eodag_sort_order}' with '{eodag_sort_param}' instead"
                )
            eodag_sort_order = eodag_sort_order[:3]

            provider_sort_order = (
                self.config.sort["sort_order_mapping"]["ascending"]
                if eodag_sort_order == "ASC"
                else self.config.sort["sort_order_mapping"]["descending"]
            )
            sort_by_param = {
                "field": provider_sort_param,
                "direction": provider_sort_order,
            }
            for sort_by_param_tmp in sort_by_params_tmp:
                # since duplicated tuples or dictionnaries have been removed, if two sorting parameters are equal,
                # then their sorting order is different and there is a contradiction that would raise an error
                if sort_by_param["field"] == sort_by_param_tmp["field"]:
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
            if isinstance(sort_by_params, str):
                sort_by_params += self.config.sort["sort_url_tpl"].format(
                    sort_param=sort_by_param["field"],
                    sort_order=sort_by_param["direction"],
                )
            else:
                assert sort_by_provider_keyword is not None
                sort_by_params[sort_by_provider_keyword].append(sort_by_param)
        return sort_by_params
