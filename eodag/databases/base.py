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

from typing import TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from eodag.api.collection import CollectionsDict
    from eodag.api.provider import ProviderConfig

DEFAULT_COLLECTIONS_PER_PAGE = 10

class Database:
    """Base for classes representing a database.

    A Database object is used to store information about :class:`~eodag.api.collection.Collection` objects.
    """

    type: str

    def _create_col_table(self) -> None:
        """Create the collections table in the database."""
        raise NotImplementedError

    def _create_col_config_table(self) -> None:
        """Create the collections configuration table in the database."""
        raise NotImplementedError

    def get_collection(self, collection_name: str) -> Optional[dict[str, Any]]:
        """Retrieve a collection from the database."""
        raise NotImplementedError

    def get_collection_from_alias(self, alias_or_id: str) -> dict[str, Any]:
        """Retrieve a collection from the database by either its id or alias.

        :param alias_or_id: Alias of the collection. If an existing id is given, this
                            method will directly return the collection of given value.
        :returns: The collection having  Internal name of the collection.
        """
        raise NotImplementedError

    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection from the database."""
        raise NotImplementedError

    def rename_collection(self, old_name: str, new_name: str) -> None:
        """Rename a collection in the database."""
        raise NotImplementedError

    def upsert_collections(self, collections: CollectionsDict) -> None:
        """Add or update collections in the database"""
        raise NotImplementedError

    def upsert_providers_config(self, providers_config: list[ProviderConfig]) -> None:
        """Add or update providers configurations in the database"""
        raise NotImplementedError

    def collections_search(
        self,
        geometry: Optional[Union[str, dict[str, float], BaseGeometry]] = None,
        datetime: Optional[str] = None,
        limit: int = DEFAULT_COLLECTIONS_PER_PAGE,
        q: Optional[list[str]] = None,
        cql2_text: Optional[str] = None,
        cql2_json: Optional[dict[str, Any]] = None,
        sortby: Optional[list[dict[str, str]]] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        :returns: A tuple of (returned collections as dictionaries, total number matched).
        """
        raise NotImplementedError
