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

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from eodag.api.collection import CollectionsDict
    from eodag.config import ProviderConfig


class Database(ABC):
    """Base for classes representing a database.

    A Database object is used to store information about :class:`~eodag.api.collection.Collection` objects.
    """

    def __del__(self):
        """Close the database connection when the object is deleted."""
        self.close()

    def __enter__(self) -> Database:
        """Enter the runtime context related to this object."""
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Exit the runtime context related to this object."""
        self.close()

    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""
        ...

    @abstractmethod
    def delete_collections(self, collection_ids: list[str]) -> None:
        """Delete collections from the database by their IDs or aliases."""
        pass

    @abstractmethod
    def upsert_collections(self, collections: CollectionsDict) -> None:
        """Add or update collections in the database"""
        pass

    @abstractmethod
    def upsert_fb_configs(self, configs: list[ProviderConfig]) -> None:
        """Add or update provider configurations in the database"""
        pass

    @abstractmethod
    def get_federation_backends(
        self,
        collection: Optional[str] = None,
        enabled: Optional[bool] = None,
        limit: Optional[int] = None,
        names: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Get federation backends from the database
        """
        pass

    @abstractmethod
    def get_fb_config(
        self,
        name: str,
        collections: set[str] | None = None,
    ) -> dict[str, Any]:
        """
        Get the configuration for a specific federation backend and collection from the database.
        """
        pass

    @abstractmethod
    def set_priority(self, name: str, priority: int) -> None:
        """
        Set the priority of a federation backend.
        """
        pass
