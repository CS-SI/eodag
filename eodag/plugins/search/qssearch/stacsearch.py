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
from typing import TYPE_CHECKING, Annotated, Any, Optional, get_args
from urllib.parse import urlencode

from jsonpath_ng import JSONPath
from pydantic import ConfigDict, Field, create_model
from pydantic.fields import FieldInfo
from requests.auth import AuthBase

from eodag.api.product.metadata_mapping import (
    format_query_params,
    get_queryable_from_provider,
)
from eodag.types import json_field_definition_to_python, model_fields_to_annotated
from eodag.types.queryables import Queryables
from eodag.utils import STAC_SEARCH_PLUGINS, copy_deepcopy
from eodag.utils.exceptions import (
    MisconfiguredError,
    PluginImplementationError,
    RequestError,
    ValidationError,
)

from ..preparesearch import PreparedSearch
from .postjsonsearch import PostJsonSearch
from .querystringsearch import QueryStringSearch

if TYPE_CHECKING:
    from eodag.config import PluginConfig

logger = logging.getLogger("eodag.search.qssearch.stacsearch")


class StacSearch(PostJsonSearch):
    """A specialisation of :class:`~eodag.plugins.search.qssearch.PostJsonSearch` that uses generic
    STAC configuration.

    It therefore has the same configuration parameters (those inherited
    from :class:`~eodag.plugins.search.qssearch.QueryStringSearch`).

    For providers using ``StacSearch`` default values are defined for most of the parameters
    (see ``stac_provider.yml``). If some parameters are different for a specific provider, they
    have to be overwritten. If certain functionalities are not available, their configuration
    parameters have to be overwritten with ``null``. E.g. if there is no queryables endpoint,
    the :attr:`~eodag.config.PluginConfig.DiscoverQueryables.fetch_url` and
    :attr:`~eodag.config.PluginConfig.DiscoverQueryables.collection_fetch_url` in the
    :attr:`~eodag.config.PluginConfig.discover_queryables` config have to be set to ``null``.

    Plugins inheriting from ``StacSearch`` have to be referenced in :const:`~eodag.utils.STAC_SEARCH_PLUGINS`
    to be correctly initialized with the expected STAC configuration and features.
    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        try:
            # backup results_entry overwritten by init
            results_entry = config.results_entry
        except AttributeError:
            plugin_name = self.__class__.__name__
            if plugin_name not in STAC_SEARCH_PLUGINS:
                raise MisconfiguredError(
                    "Missing results_entry in %s configuration. If %s is expected to be used as "
                    "a STAC plugin, it must be referenced in STAC_SEARCH_PLUGINS."
                    % (provider, plugin_name)
                )
            else:
                raise

        super(StacSearch, self).__init__(provider, config)

        # restore results_entry overwritten by init
        self.config.results_entry = results_entry

    def build_query_string(
        self, collection: str, query_dict: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        """Build The query string using the search parameters"""
        logger.debug("Building the query string that will be used for search")

        # handle opened time intervals
        if any(q in query_dict for q in ("start_datetime", "end_datetime")):
            query_dict.setdefault("start_datetime", "..")
            query_dict.setdefault("end_datetime", "..")

        error_context = f"Collection: {collection} / provider : {self.provider}"
        query_params = format_query_params(
            collection, self.config, query_dict, error_context
        )

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

        :param kwargs: additional filters for queryables (`collection` and other search
                       arguments)
        :returns: fetched queryable parameters dict
        """
        if (
            not self.config.discover_queryables["fetch_url"]
            and not self.config.discover_queryables["collection_fetch_url"]
        ):
            raise NotImplementedError()

        collection = kwargs.get("collection")
        provider_collection = (
            self.config.products.get(collection, {}).get("_collection", collection)
            if collection
            else None
        )
        if (
            provider_collection
            and not self.config.discover_queryables["collection_fetch_url"]
        ):
            raise NotImplementedError(
                f"Cannot fetch queryables for a specific collection with {self.provider}"
            )
        if not provider_collection and not self.config.discover_queryables["fetch_url"]:
            raise ValidationError(
                f"Cannot fetch global queryables for {self.provider}. A collection must be specified"
            )

        try:
            unparsed_fetch_url = (
                self.config.discover_queryables["collection_fetch_url"]
                if provider_collection
                else self.config.discover_queryables["fetch_url"]
            )
            if unparsed_fetch_url is None:
                raise PluginImplementationError(
                    f"Cannot fetch queryables for {self.provider}: missing url"
                )

            fetch_url = unparsed_fetch_url.format(
                provider_collection=provider_collection,
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
                    "No queryable found for %s on %s", collection, self.provider
                )
                return None
            # convert json results to pydantic model fields
            field_definitions: dict[str, Any] = dict()
            StacQueryables = Queryables.from_stac_models()
            for json_param, json_mtd in json_queryables.items():
                param = get_queryable_from_provider(
                    json_param, self.get_metadata_mapping(collection)
                ) or StacQueryables.get_queryable_from_alias(json_param)
                # do not expose internal parameters, neither datetime
                if param == "datetime" or param.startswith("_"):
                    continue

                # convert provider json field definition to python
                default = kwargs.get(param, json_mtd.get("default"))
                annotated_def = json_field_definition_to_python(
                    json_mtd, default_value=default
                )
                field_definition = get_args(annotated_def)

                if param in StacQueryables.model_fields:
                    # update provider queryable using eodag queryable definition
                    eodag_queryable = StacQueryables.get_with_default(param, default)
                    eodag_queryable_args = get_args(eodag_queryable)
                    if len(field_definition) == 2 and len(eodag_queryable_args) == 2:
                        (
                            provider_queryable_type,
                            provider_queryable_fieldinfo,
                        ) = field_definition
                        (
                            eodag_queryable_type,
                            eodag_queryable_fieldinfo,
                        ) = eodag_queryable_args
                        if ".Literal[" not in str(provider_queryable_type):
                            # use eodag queryable type if provider one has no constraints
                            field_definition = eodag_queryable_type, field_definition[1]

                        # merge provider and eodag queryables FieldInfo metadata
                        merged_metadata = (
                            field_definition[1].metadata
                            + eodag_queryable_fieldinfo.metadata
                        )
                        # build merged attributes: use provider value if set, otherwise fall back to eodag value
                        merged_attrs = {
                            attr_k: (
                                attr_v or getattr(eodag_queryable_fieldinfo, attr_k)
                            )
                            for attr_k, attr_v in provider_queryable_fieldinfo.asdict()
                            .get("attributes", {})
                            .items()
                        }
                        # rebuild using Field()
                        merged_fieldinfo = Field(**merged_attrs)
                        merged_fieldinfo.metadata = merged_metadata
                        field_definition = field_definition[0], merged_fieldinfo

                field_definitions[param] = field_definition

            python_queryables = create_model(
                "m",
                __config__=ConfigDict(arbitrary_types_allowed=True),
                **field_definitions,
            ).model_fields

            queryables_dict = model_fields_to_annotated(python_queryables)

            # append "datetime" as "start" & "end" if needed
            if "datetime" in json_queryables:
                eodag_queryables = copy_deepcopy(
                    model_fields_to_annotated(StacQueryables.model_fields)
                )
                queryables_dict.setdefault("start", eodag_queryables["start"])
                queryables_dict.setdefault("end", eodag_queryables["end"])

            return queryables_dict


__all__ = ["StacSearch"]
