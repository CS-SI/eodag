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
from pydantic import ValidationError as PydanticValidationError
from pydantic.fields import Field, FieldInfo

from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    NOT_MAPPED,
    mtd_cfg_as_conversion_and_querypath,
)
from eodag.plugins.base import PluginTopic
from eodag.plugins.search import PreparedSearch
from eodag.types import model_fields_to_annotated
from eodag.types.queryables import Queryables, QueryablesDict
from eodag.types.search_args import SortByList
from eodag.utils import (
    GENERIC_COLLECTION,
    copy_deepcopy,
    deepcopy,
    format_dict_items,
    format_pydantic_error,
    get_collection_dates,
    string_to_jsonpath,
    update_nested_dict,
)
from eodag.utils.exceptions import ValidationError

if TYPE_CHECKING:
    from typing import Any, Optional, Union

    from mypy_boto3_s3 import S3ServiceResource
    from requests.auth import AuthBase

    from eodag.api.product import EOProduct
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.base")


class Search(PluginTopic):
    """Base Search Plugin.

    :param provider: An EODAG provider name
    :param config: An EODAG plugin configuration
    """

    auth: Union[AuthBase, S3ServiceResource]
    next_page_url: Optional[str]
    next_page_query_obj: Optional[dict[str, Any]]
    total_items_nb: int
    need_count: bool

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(Search, self).__init__(provider, config)
        # Prepare the metadata mapping
        # Do a shallow copy, the structure is flat enough for this to be sufficient
        metas: dict[str, Any] = {}
        # Update the defaults with the mapping value. This will add any new key
        # added by the provider mapping that is not in the default metadata
        if self.config.metadata_mapping:
            metas.update(self.config.metadata_mapping)
        self.config.metadata_mapping = mtd_cfg_as_conversion_and_querypath(
            metas,
            self.config.metadata_mapping,
            result_type=getattr(self.config, "result_type", "json"),
        )
        # set default metadata prefix for discover_metadata if not already set
        if hasattr(self.config, "discover_metadata"):
            self.config.discover_metadata.setdefault("metadata_prefix", provider)

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

    def discover_collections(self, **kwargs: Any) -> Optional[dict[str, Any]]:
        """Fetch collections list from provider using `discover_collections` conf"""
        return None

    def discover_queryables(
        self, **kwargs: Any
    ) -> Optional[dict[str, Annotated[Any, FieldInfo]]]:
        """Fetch queryables list from provider using :attr:`~eodag.config.PluginConfig.discover_queryables` conf

        :param kwargs: additional filters for queryables (``collection`` and other search
                       arguments)
        :returns: fetched queryable parameters dict
        """
        raise NotImplementedError(
            f"discover_queryables is not implemeted for plugin {self.__class__.__name__}"
        )

    def _get_defaults_as_queryables(
        self, collection: str
    ) -> dict[str, Annotated[Any, FieldInfo]]:
        """
        Return given collection default settings as queryables

        :param collection: given collection
        :returns: queryable parameters dict
        """
        defaults = deepcopy(self.config.products.get(collection, {}))
        defaults.pop("metadata_mapping", None)

        queryables: dict[str, Annotated[Any, FieldInfo]] = {}
        for parameter, value in defaults.items():
            queryables[parameter] = Annotated[type(value), Field(default=value)]
        return queryables

    def map_collection(self, collection: Optional[str], **kwargs: Any) -> Optional[str]:
        """Get the provider collection from eodag collection

        :param collection: eodag collection
        :returns: provider collection
        """
        if collection is None:
            return None
        logger.debug("Mapping eodag collection to provider collection")
        return self.config.products.get(collection, {}).get(
            "_collection", GENERIC_COLLECTION
        )

    def get_collection_def_params(
        self, collection: str, format_variables: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Get the provider collection definition parameters and specific settings

        :param collection: the desired collection
        :returns: The collection definition parameters
        """
        if collection in self.config.products.keys():
            return self.config.products[collection]
        elif GENERIC_COLLECTION in self.config.products.keys():
            logger.debug(
                "Getting generic provider collection definition parameters for %s",
                collection,
            )
            return {
                k: v
                for k, v in format_dict_items(
                    self.config.products[GENERIC_COLLECTION],
                    **(format_variables or {}),
                ).items()
                if v
            }
        else:
            return {}

    def get_collection_cfg_value(self, key: str, default: Any = None) -> Any:
        """
        Get the value of a configuration option specific to the current collection.

        This method retrieves the value of a configuration option from the
        ``collection_config`` attribute. If the option is not found, the provided
        default value is returned.

        :param key: The configuration option key.
        :type key: str
        :param default: The default value to be returned if the option is not found (default is None).
        :type default: Any

        :return: The value of the specified configuration option or the default value.
        :rtype: Any
        """
        collection_cfg = getattr(self.config, "collection_config", {})
        non_none_cfg = {k: v for k, v in collection_cfg.items() if v}

        return non_none_cfg.get(key, default)

    def get_collection_cfg_dates(
        self, start_default: Optional[str] = None, end_default: Optional[str] = None
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Get start and end dates from the collection configuration.

        Extracts dates from the extent.temporal.interval structure in the collection
        configuration, falling back to provided defaults if dates are not available.

        :param start_default: Default value to return for start date if not found in config
        :param end_default: Default value to return for end date if not found in config
        :returns: Tuple of (mission_start_date, mission_end_date) as ISO strings or defaults
        """
        collection_cfg = getattr(self.config, "collection_config", {})
        col_start, col_end = get_collection_dates(collection_cfg)

        return col_start or start_default, col_end or end_default

    def get_metadata_mapping(
        self, collection: Optional[str] = None
    ) -> dict[str, Union[str, list[str]]]:
        """Get the plugin metadata mapping configuration (collection specific if exists)

        :param collection: the desired collection
        :returns: The collection specific metadata-mapping
        """
        if collection:
            return self.config.products.get(collection, {}).get(
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
            "sort_by_default"
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
                eodag_sort_param
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
                    f"'DESC' (DESCENDING), got '{eodag_sort_order}' with '{eodag_sort_param}' instead",
                    {eodag_sort_param},
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
                        {eodag_sort_param},
                    )
            provider_sort_by_tuples_used.append(provider_sort_by_tuple)

            # TODO: move this code block to the top of this method when search args model validation is embeded
            # check if the limit number of sorting parameter(s) is respected with this sorting parameter
            if (
                self.config.sort.get("max_sort_params")
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

    def _get_collection_queryables(
        self, collection: Optional[str], alias: Optional[str], filters: dict[str, Any]
    ) -> QueryablesDict:
        default_values: dict[str, Any] = deepcopy(
            getattr(self.config, "products", {}).get(collection, {})
        )
        default_values.pop("metadata_mapping", None)
        try:
            filters["collection"] = collection
            queryables = self.discover_queryables(**{**default_values, **filters}) or {}
        except NotImplementedError as e:
            if str(e):
                logger.debug(str(e))
            queryables = self.queryables_from_metadata_mapping(collection, alias)

        return QueryablesDict(**queryables)

    def list_queryables(
        self,
        filters: dict[str, Any],
        available_collections: list[Any],
        collection_configs: dict[str, dict[str, Any]],
        collection: Optional[str] = None,
        alias: Optional[str] = None,
    ) -> QueryablesDict:
        """
        Get queryables

        :param filters: Additional filters for queryables.
        :param available_collections: list of available collections
        :param collection_configs: dict containing the collection information for all used collections
        :param collection: (optional) The collection.
        :param alias: (optional) alias of the collection

        :return: A dictionary containing the queryable properties, associating parameters to their
                annotated type.
        """
        additional_info = (
            "Please select a collection to get the possible values of the parameters!"
            if not collection
            else ""
        )
        discover_metadata = getattr(self.config, "discover_metadata", {})
        auto_discovery = discover_metadata.get("auto_discovery", False)

        if collection or getattr(self.config, "discover_queryables", {}).get(
            "fetch_url", ""
        ):
            if collection:
                self.config.collection_config = collection_configs[collection]
            queryables = self._get_collection_queryables(collection, alias, filters)
            queryables.additional_information = additional_info
            queryables.additional_properties = auto_discovery

            return queryables
        else:
            all_queryables: dict[str, Any] = {}
            for pt in available_collections:
                self.config.collection_config = collection_configs[pt]
                pt_queryables = self._get_collection_queryables(pt, None, filters)
                all_queryables.update(pt_queryables)
            # reset defaults because they may vary between collections
            for k, v in all_queryables.items():
                v.__metadata__[0].default = getattr(
                    Queryables.model_fields.get(k, Field(None)), "default", None
                )
            return QueryablesDict(
                additional_properties=auto_discovery,
                additional_information=additional_info,
                **all_queryables,
            )

    def validate(
        self,
        search_params: dict[str, Any],
        auth: Optional[Union[AuthBase, S3ServiceResource]],
    ) -> None:
        """Validate a search request.

        :param search_params: Arguments of the search request
        :param auth: Authentication object
        :raises: :class:`~eodag.utils.exceptions.ValidationError`
        """
        logger.debug("Validate request")
        # attach authentication if required
        if getattr(self.config, "need_auth", False) and auth:
            self.auth = auth
        try:
            product_type = search_params.get("productType")
            if not product_type:
                raise ValidationError("Field required: productType")
            self.list_queryables(
                filters=search_params,
                available_product_types=[product_type],
                product_type_configs={product_type: self.config.product_type_config},
                product_type=product_type,
                alias=product_type,
            ).get_model().model_validate(search_params)
        except PydanticValidationError as e:
            raise ValidationError(format_pydantic_error(e)) from e

    def queryables_from_metadata_mapping(
        self, collection: Optional[str] = None, alias: Optional[str] = None
    ) -> dict[str, Annotated[Any, FieldInfo]]:
        """
        Extract queryable parameters from collection metadata mapping.
        :param collection: collection id (optional)
        :param alias: (optional) alias of the collection
        :returns: dict of annotated queryables
        """
        metadata_mapping: dict[str, Any] = deepcopy(
            self.get_metadata_mapping(collection)
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
        queryables["collection"] = eodag_queryables.pop("collection")
        # add default value for collection
        if collection_or_alias := alias or collection:
            queryables["collection"] = Annotated[
                str, Field(default=collection_or_alias)
            ]

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

    def get_assets_from_mapping(self, provider_item: dict[str, Any]) -> dict[str, Any]:
        """
        Create assets based on the assets_mapping in the provider's config
        and an item returned by the provider

        :param provider_item: dict of item properties returned by the provider
        :returns: dict containing the asset metadata
        """
        assets_mapping = getattr(self.config, "assets_mapping", None)
        if not assets_mapping:
            return {}
        assets = {}
        for key, values in assets_mapping.items():
            asset_href = values.get("href")
            if not asset_href:
                logger.warning(
                    "asset mapping %s skipped because no href is available", key
                )
                continue
            json_url_path = string_to_jsonpath(asset_href)
            if isinstance(json_url_path, str):
                url_path = json_url_path
            else:
                url_match = json_url_path.find(provider_item)
                if len(url_match) == 1:
                    url_path = url_match[0].value
                else:
                    url_path = NOT_AVAILABLE
            assets[key] = deepcopy(values)
            assets[key]["href"] = url_path
        return assets
