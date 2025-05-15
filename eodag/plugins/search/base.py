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
from typing import TYPE_CHECKING, Annotated, get_args

import orjson
from pydantic.fields import Field, FieldInfo

from eodag.api.product.metadata_mapping import (
    DEFAULT_METADATA_MAPPING,
    NOT_MAPPED,
    mtd_cfg_as_conversion_and_querypath,
)
from eodag.plugins.base import PluginTopic
from eodag.plugins.search import PreparedSearch
from eodag.types import model_fields_to_annotated
from eodag.types.queryables import Queryables, QueryablesDict
from eodag.types.search_args import SortByList
from eodag.utils import (
    GENERIC_PRODUCT_TYPE,
    copy_deepcopy,
    deepcopy,
    format_dict_items,
    update_nested_dict,
)
from eodag.utils.exceptions import ValidationError

if TYPE_CHECKING:
    from typing import Any, Optional, Union

    from requests.auth import AuthBase

    from eodag.api.product import EOProduct
    from eodag.config import PluginConfig
    from eodag.types import S3SessionKwargs

logger = logging.getLogger("eodag.search.base")


class Search(PluginTopic):
    """Base Search Plugin.

    :param provider: An EODAG provider name
    :param config: An EODAG plugin configuration
    """

    auth: Union[AuthBase, S3SessionKwargs]
    next_page_url: Optional[str]
    next_page_query_obj: Optional[dict[str, Any]]
    total_items_nb: int
    need_count: bool
    _request: Any  # needed by deprecated load_stac_items

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(Search, self).__init__(provider, config)
        # Prepare the metadata mapping
        # Do a shallow copy, the structure is flat enough for this to be sufficient
        metas: dict[str, Any] = DEFAULT_METADATA_MAPPING.copy()
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
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> tuple[list[EOProduct], Optional[int]]:
        """Implementation of how the products must be searched goes here.

        This method must return a tuple with (1) a list of :class:`~eodag.api.product._product.EOProduct` instances
        which will be processed by a :class:`~eodag.plugins.download.base.Download` plugin (2) and the total number of
        products matching the search criteria. If ``prep.count`` is False, the second element returned must be ``None``.
        """
        raise NotImplementedError("A Search plugin must implement a method named query")

    def discover_product_types(self, **kwargs: Any) -> Optional[dict[str, Any]]:
        """Fetch product types list from provider using `discover_product_types` conf"""
        return None

    def discover_queryables(
        self, **kwargs: Any
    ) -> Optional[dict[str, Annotated[Any, FieldInfo]]]:
        """Fetch queryables list from provider using :attr:`~eodag.config.PluginConfig.discover_queryables` conf

        :param kwargs: additional filters for queryables (``productType`` and other search
                       arguments)
        :returns: fetched queryable parameters dict
        """
        raise NotImplementedError(
            f"discover_queryables is not implemeted for plugin {self.__class__.__name__}"
        )

    def _get_defaults_as_queryables(
        self, product_type: str
    ) -> dict[str, Annotated[Any, FieldInfo]]:
        """
        Return given product type default settings as queryables

        :param product_type: given product type
        :returns: queryable parameters dict
        """
        defaults = deepcopy(self.config.products.get(product_type, {}))
        defaults.pop("metadata_mapping", None)

        queryables: dict[str, Annotated[Any, FieldInfo]] = {}
        for parameter, value in defaults.items():
            queryables[parameter] = Annotated[type(value), Field(default=value)]
        return queryables

    def map_product_type(
        self, product_type: Optional[str], **kwargs: Any
    ) -> Optional[str]:
        """Get the provider product type from eodag product type

        :param product_type: eodag product type
        :returns: provider product type
        """
        if product_type is None:
            return None
        logger.debug("Mapping eodag product type to provider product type")
        return self.config.products.get(product_type, {}).get(
            "productType", GENERIC_PRODUCT_TYPE
        )

    def get_product_type_def_params(
        self, product_type: str, format_variables: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Get the provider product type definition parameters and specific settings

        :param product_type: the desired product type
        :returns: The product type definition parameters
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
                    self.config.products[GENERIC_PRODUCT_TYPE],
                    **(format_variables or {}),
                ).items()
                if v
            }
        else:
            return {}

    def get_product_type_cfg_value(self, key: str, default: Any = None) -> Any:
        """
        Get the value of a configuration option specific to the current product type.

        This method retrieves the value of a configuration option from the
        ``product_type_config`` attribute. If the option is not found, the provided
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

    def get_metadata_mapping(
        self, product_type: Optional[str] = None
    ) -> dict[str, Union[str, list[str]]]:
        """Get the plugin metadata mapping configuration (product type specific if exists)

        :param product_type: the desired product type
        :returns: The product type specific metadata-mapping
        """
        if product_type:
            return self.config.products.get(product_type, {}).get(
                "metadata_mapping", self.config.metadata_mapping
            )
        return self.config.metadata_mapping

    def get_sort_by_arg(self, kwargs: dict[str, Any]) -> Optional[SortByList]:
        """Extract the ``sort_by`` argument from the kwargs or the provider default sort configuration

        :param kwargs: Search arguments
        :returns: The ``sort_by`` argument from the kwargs or the provider default sort configuration
        """
        # remove "sort_by" from search args if exists because it is not part of metadata mapping,
        # it will complete the query string or body once metadata mapping will be done
        sort_by_arg_tmp = kwargs.pop("sort_by", None)
        sort_by_arg = sort_by_arg_tmp or getattr(self.config, "sort", {}).get(
            "sort_by_default", None
        )
        if not sort_by_arg_tmp and sort_by_arg:
            logger.info(
                f"{self.provider} is configured with default sorting by '{sort_by_arg[0][0]}' "
                f"in {'ascending' if sort_by_arg[0][1] == 'ASC' else 'descending'} order"
            )
        return sort_by_arg

    def build_sort_by(
        self, sort_by_arg: SortByList
    ) -> tuple[str, dict[str, list[dict[str, str]]]]:
        """Build the sorting part of the query string or body by transforming
        the ``sort_by`` argument into a provider-specific string or dictionary

        :param sort_by_arg: the ``sort_by`` argument in EODAG format
        :returns: The ``sort_by`` argument in provider-specific format
        """
        if not hasattr(self.config, "sort"):
            raise ValidationError(f"{self.provider} does not support sorting feature")
        # TODO: remove this code block when search args model validation is embeded
        # remove duplicates
        sort_by_arg = list(dict.fromkeys(sort_by_arg))

        sort_by_qs: str = ""
        sort_by_qp: dict[str, Any] = {}

        provider_sort_by_tuples_used: list[tuple[str, str]] = []
        for eodag_sort_by_tuple in sort_by_arg:
            eodag_sort_param = eodag_sort_by_tuple[0]
            provider_sort_param = self.config.sort["sort_param_mapping"].get(
                eodag_sort_param, None
            )
            if not provider_sort_param:
                joined_eodag_params_to_map = ", ".join(
                    k for k in self.config.sort["sort_param_mapping"].keys()
                )
                params = set(self.config.sort["sort_param_mapping"].keys())
                params.add(eodag_sort_param)
                raise ValidationError(
                    f"'{eodag_sort_param}' parameter is not sortable with {self.provider}. "
                    f"Here is the list of sortable parameter(s) with {self.provider}: {joined_eodag_params_to_map}",
                    params,
                )
            eodag_sort_order = eodag_sort_by_tuple[1]
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
            provider_sort_by_tuple: tuple[str, str] = (
                provider_sort_param,
                provider_sort_order,
            )
            # TODO: remove this code block when search args model validation is embeded
            for provider_sort_by_tuple_used in provider_sort_by_tuples_used:
                # since duplicated tuples or dictionnaries have been removed, if two sorting parameters are equal,
                # then their sorting order is different and there is a contradiction that would raise an error
                if provider_sort_by_tuple[0] == provider_sort_by_tuple_used[0]:
                    raise ValidationError(
                        f"'{eodag_sort_param}' parameter is called several times to sort results with different "
                        "sorting orders. Please set it to only one ('ASC' (ASCENDING) or 'DESC' (DESCENDING))",
                        set([eodag_sort_param]),
                    )
            provider_sort_by_tuples_used.append(provider_sort_by_tuple)

            # TODO: move this code block to the top of this method when search args model validation is embeded
            # check if the limit number of sorting parameter(s) is respected with this sorting parameter
            if (
                self.config.sort.get("max_sort_params", None)
                and len(provider_sort_by_tuples_used)
                > self.config.sort["max_sort_params"]
            ):
                raise ValidationError(
                    f"Search results can be sorted by only {self.config.sort['max_sort_params']} "
                    f"parameter(s) with {self.provider}"
                )

            parsed_sort_by_tpl: str = self.config.sort["sort_by_tpl"].format(
                sort_param=provider_sort_by_tuple[0],
                sort_order=provider_sort_by_tuple[1],
            )
            try:
                parsed_sort_by_tpl_dict: dict[str, Any] = orjson.loads(
                    parsed_sort_by_tpl
                )
                sort_by_qp = update_nested_dict(
                    sort_by_qp, parsed_sort_by_tpl_dict, extend_list_values=True
                )
            except orjson.JSONDecodeError:
                sort_by_qs += parsed_sort_by_tpl
        return (sort_by_qs, sort_by_qp)

    def _get_product_type_queryables(
        self, product_type: Optional[str], alias: Optional[str], filters: dict[str, Any]
    ) -> QueryablesDict:
        default_values: dict[str, Any] = deepcopy(
            getattr(self.config, "products", {}).get(product_type, {})
        )
        default_values.pop("metadata_mapping", None)
        try:
            filters["productType"] = product_type
            queryables = self.discover_queryables(**{**default_values, **filters}) or {}
        except NotImplementedError as e:
            if str(e):
                logger.debug(str(e))
            queryables = self.queryables_from_metadata_mapping(product_type, alias)

        return QueryablesDict(**queryables)

    def list_queryables(
        self,
        filters: dict[str, Any],
        available_product_types: list[Any],
        product_type_configs: dict[str, dict[str, Any]],
        product_type: Optional[str] = None,
        alias: Optional[str] = None,
    ) -> QueryablesDict:
        """
        Get queryables

        :param filters: Additional filters for queryables.
        :param available_product_types: list of available product types
        :param product_type_configs: dict containing the product type information for all used product types
        :param product_type: (optional) The product type.
        :param alias: (optional) alias of the product type

        :return: A dictionary containing the queryable properties, associating parameters to their
                annotated type.
        """
        additional_info = (
            "Please select a product type to get the possible values of the parameters!"
            if not product_type
            else ""
        )
        discover_metadata = getattr(self.config, "discover_metadata", {})
        auto_discovery = discover_metadata.get("auto_discovery", False)

        if product_type or getattr(self.config, "discover_queryables", {}).get(
            "fetch_url", ""
        ):
            if product_type:
                self.config.product_type_config = product_type_configs[product_type]
            queryables = self._get_product_type_queryables(product_type, alias, filters)
            queryables.additional_information = additional_info
            queryables.additional_properties = auto_discovery

            return queryables
        else:
            all_queryables: dict[str, Any] = {}
            for pt in available_product_types:
                self.config.product_type_config = product_type_configs[pt]
                pt_queryables = self._get_product_type_queryables(pt, None, filters)
                all_queryables.update(pt_queryables)
            # reset defaults because they may vary between product types
            for k, v in all_queryables.items():
                v.__metadata__[0].default = getattr(
                    Queryables.model_fields.get(k, Field(None)), "default", None
                )
            return QueryablesDict(
                additional_properties=auto_discovery,
                additional_information=additional_info,
                **all_queryables,
            )

    def queryables_from_metadata_mapping(
        self, product_type: Optional[str] = None, alias: Optional[str] = None
    ) -> dict[str, Annotated[Any, FieldInfo]]:
        """
        Extract queryable parameters from product type metadata mapping.
        :param product_type: product type id (optional)
        :param alias: (optional) alias of the product type
        :returns: dict of annotated queryables
        """
        metadata_mapping: dict[str, Any] = deepcopy(
            self.get_metadata_mapping(product_type)
        )

        queryables: dict[str, Annotated[Any, FieldInfo]] = {}

        for param in list(metadata_mapping.keys()):
            if NOT_MAPPED in metadata_mapping[param] or not isinstance(
                metadata_mapping[param], list
            ):
                del metadata_mapping[param]

        eodag_queryables = copy_deepcopy(
            model_fields_to_annotated(Queryables.model_fields)
        )
        # add default value for product type
        if alias:
            eodag_queryables.pop("productType")
            eodag_queryables["productType"] = Annotated[str, Field(default=alias)]
        for k, v in eodag_queryables.items():
            eodag_queryable_field_info = (
                get_args(v)[1] if len(get_args(v)) > 1 else None
            )
            if not isinstance(eodag_queryable_field_info, FieldInfo):
                continue
            if eodag_queryable_field_info.is_required() or (
                (eodag_queryable_field_info.alias or k) in metadata_mapping
            ):
                queryables[k] = v
        return queryables
