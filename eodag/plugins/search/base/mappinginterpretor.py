# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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
from typing import TYPE_CHECKING, Callable

from jsonpath_ng import JSONPath
from jsonpath_ng.jsonpath import Child as JSONChild

from eodag.api.product.metadata_mapping import NOT_AVAILABLE, format_metadata
from eodag.utils import string_to_jsonpath

if TYPE_CHECKING:
    from typing import Any, Optional

logger = logging.getLogger("eodag.search.base")


class MappingInterpretor:
    """Class to process configuration mapping"""

    @staticmethod
    def metadata_mapping_compute(
        metadata_mapping_data: Optional[dict] = None,
        properties: Optional[dict] = None,
        provider_item: Optional[dict] = None,
    ):
        """Mapping from configuration with product properties and provider_item"""
        # patch json_path without {...} to tag it as interpretable
        metadata_mapping_data = MappingInterpretor.update_json_path_as_interpretable(
            metadata_mapping_data
        )

        # all interpretable in {...}
        return MappingInterpretor.replace_interpretable(
            metadata_mapping_data,
            MappingInterpretor.metadata_substitution,
            properties=properties,
            provider_item=provider_item,
        )  # typing: ignore[arg-type]

    @staticmethod
    def update_json_path_as_interpretable(value: Any):
        """Transform in crawled structure raw value '$.[...]' into '{$.[...]}'"""
        if isinstance(value, str) and str != "":
            if value.startswith("$."):
                value = "{" + value + "}"
        elif isinstance(value, dict):
            for key in value:
                value[key] = MappingInterpretor.update_json_path_as_interpretable(
                    value[key]
                )
        elif isinstance(value, list):
            for i in range(0, len(value)):
                value[i] = MappingInterpretor.update_json_path_as_interpretable(
                    value[i]
                )
        return value

    @staticmethod
    def metadata_substitution(
        value: str,
        properties: Optional[dict[str, Any]] = None,
        provider_item: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Mapping rules
        replace field {value#filter} by property if possible
        replace field {$.jsonpath#filter} by provider_item value if possible
        """

        # Properties substitution "{field}" matching with "properties" key
        if isinstance(value, str) and properties is not None:
            # Extract filters
            filters = value.strip("{}").split("#")
            # Parameters subtitution
            field_name = filters.pop(0)
            if field_name in properties:
                value = properties[field_name]
                # apply filters
                for filter in filters:
                    scheme = "{fieldname#" + filter + "}"
                    try:
                        value = format_metadata(scheme, fieldname=value)
                    except Exception as e:
                        logger.warning(
                            "Error during properties substitution template '{}': {}".format(
                                value, str(e)
                            )
                        )

        # Provider item substitution "{$.jsonpath}" matching with "provider_item" json path resolve
        if isinstance(value, str) and provider_item is not None:
            # Extract filters
            filters = value.strip("{}").split("#")
            # Parameters subtitution
            field_name = filters.pop(0)
            if field_name.startswith("$."):
                # Is a josn path ?
                json_path = string_to_jsonpath(field_name)
                if isinstance(json_path, JSONPath) or isinstance(json_path, JSONChild):
                    match = json_path.find(provider_item)
                    if len(match) == 1:
                        value = match[0].value
                    else:
                        value = NOT_AVAILABLE
                # Apply filters
                for filter in filters:
                    scheme = "{fieldname#" + filter + "}"
                    try:
                        value = format_metadata(scheme, fieldname=value)
                    except Exception as e:
                        logger.warning(
                            "Error during provider_item substitution template {}: {}".format(
                                value, str(e)
                            )
                        )

        return value

    @staticmethod
    def replace_interpretable(value: Any, on_interpretable: Callable, *args, **kwargs):
        """Helper used to parse mapping parameters

        It extract sub element {...} from value, and call "on_interpretable"
        to substitute this sub part and replace it in value
        If value is not a string, ll try crawl by recursion to scan all data structure

        in_interpretable is called chen a sub element {...} is found to substitute it.
        args and kwargs are pass through on_interpretable function
        """

        if isinstance(value, str) and len(value) > 0:
            # Extract level 1 layer {}
            level = 0
            start = 0
            end = 0
            i = 0
            while i < len(value):
                char = value[i]
                if char == "{":
                    level += 1
                    if level == 1:
                        start = i
                if char == "}":
                    level -= 1
                    if level == 0:
                        end = i + 1
                        segment = value[start:end]
                        if len(segment) >= 2 and segment[1:-1].find("{") >= 0:
                            # Has sublevels ?
                            result = (
                                "{"
                                + MappingInterpretor.replace_interpretable(
                                    segment[1:-1], on_interpretable, *args, **kwargs
                                )
                                + "}"
                            )
                        else:
                            # Direct interpretable substitution
                            result = on_interpretable(segment, *args, **kwargs)
                        if result != segment:
                            value = value[0:start] + str(result) + value[end:]
                            # Data moved, cursor is invalid
                            i = -1
                i += 1
        elif isinstance(value, list):
            # Crawl by recursion
            for i in range(0, len(value)):
                value[i] = MappingInterpretor.replace_interpretable(
                    value[i], on_interpretable, *args, **kwargs
                )
        elif isinstance(value, dict):
            # Crawl by recursion
            for key in value:
                value[key] = MappingInterpretor.replace_interpretable(
                    value[key], on_interpretable, *args, **kwargs
                )

        return value
