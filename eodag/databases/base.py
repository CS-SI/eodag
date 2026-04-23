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
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional, Union

import shapely

from eodag.utils import get_geometry_from_various
from eodag.utils.dates import get_datetime

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from eodag.api.collection import CollectionsDict
    from eodag.config import ProviderConfig


# ---------------------------------------------------------------------------
# Shared CQL2 metadata (backend-agnostic).
# ---------------------------------------------------------------------------

#: Mapping of CQL2 property names to physical column names of the ``collections``
#: table. Properties not present here are translated to a JSON-extract expression
#: by the backend-specific CQL2 translator.
BASE_COLLECTION_TABLE_COLUMNS: dict[str, str] = {
    "key": "key",
    "id": "id",
    "internal_id": "internal_id",
    "datetime": "datetime",
    "end_datetime": "end_datetime",
    "geometry": "geometry",
    "content": "content",
    "federation:backends": "federation_backends",
}

SUPPORTED_CONFORMANCE_CLASSES: tuple[str, ...] = (
    "http://www.opengis.net/spec/cql2/1.0/conf/basic-cql2",
    "http://www.opengis.net/spec/cql2/1.0/conf/advanced-comparison-operators",
    "http://www.opengis.net/spec/cql2/1.0/conf/case-insensitive-comparison",
    "http://www.opengis.net/spec/cql2/1.0/conf/accent-insensitive-comparison",
    "http://www.opengis.net/spec/cql2/1.0/conf/basic-spatial-functions",
    "http://www.opengis.net/spec/cql2/1.0/conf/basic-spatial-functions-plus",
    "http://www.opengis.net/spec/cql2/1.0/conf/spatial-functions",
    "http://www.opengis.net/spec/cql2/1.0/conf/temporal-functions",
    "http://www.opengis.net/spec/cql2/1.0/conf/array-functions",
    "http://www.opengis.net/spec/cql2/1.0/conf/property-property",
    "http://www.opengis.net/spec/cql2/1.0/conf/arithmetic",
)

UNSUPPORTED_CONFORMANCE_CLASSES: tuple[str, ...] = (
    "http://www.opengis.net/spec/cql2/1.0/conf/functions",
)

SUPPORTED_OPS: set[str] = {
    "=", "<>", "!=", "<", "<=", ">", ">=",
    "and", "or", "not",
    "like", "between", "in", "isnull",
    "s_intersects", "s_equals", "s_disjoint", "s_within",
    "s_contains", "s_overlaps", "s_touches", "s_crosses",
    "t_after", "t_before", "t_contains", "t_disjoint",
    "t_during", "t_equals", "t_finishedby", "t_finishes",
    "t_intersects", "t_meets", "t_metby", "t_overlappedby",
    "t_overlaps", "t_startedby", "t_starts",
    "a_containedby", "a_contains", "a_equals", "a_overlaps",
    "casei", "accenti",
    "+", "-", "*", "/", "%", "^", "div",
}  # fmt: skip


def extract_ops(node: Any, out: set[str]) -> None:
    """Walk the CQL2 JSON to find all operators used."""
    if isinstance(node, dict):
        op = node.get("op")
        if isinstance(op, str):
            out.add(op.lower())
        for value in node.values():
            extract_ops(value, out)
    elif isinstance(node, list):
        for item in node:
            extract_ops(item, out)


def extract_properties(node: Any, out: set[str]) -> None:
    """Walk the CQL2 JSON to find all property names used."""
    if isinstance(node, dict):
        if "property" in node and isinstance(node["property"], str):
            out.add(node["property"])
        for value in node.values():
            extract_properties(value, out)
    elif isinstance(node, list):
        for item in node:
            extract_properties(item, out)


def validate_supported_ops(cql2_json: dict[str, Any]) -> None:
    """Validate that all operators in the CQL2 JSON are supported."""
    ops: set[str] = set()
    extract_ops(cql2_json, ops)
    unsupported_ops = sorted(op for op in ops if op not in SUPPORTED_OPS)
    if unsupported_ops:
        raise NotImplementedError(
            "Unsupported CQL2 operators: "
            f"{', '.join(unsupported_ops)}. "
            "Unsupported conformance classes include: "
            f"{', '.join(UNSUPPORTED_CONFORMANCE_CLASSES)}"
        )


# ---------------------------------------------------------------------------
# Shared sortby helpers.
# ---------------------------------------------------------------------------

COLLECTIONS_SORTABLES: dict[str, str] = {
    "id": "c.id",
    "datetime": "c.datetime",
    "end_datetime": "c.end_datetime",
}

_VALID_DIRECTIONS: set[str] = {"asc", "desc"}


def stac_sortby_to_order_by(sortby: list[dict[str, str]]) -> list[str]:
    """Convert a STAC ``sortby`` list to SQL ORDER BY clauses.

    :param sortby: e.g. ``[{"field": "datetime", "direction": "desc"}]``
    :returns: list of SQL order expressions, e.g. ``["c.datetime DESC"]``
    :raises ValueError: on unknown field or invalid direction
    """
    clauses: list[str] = []
    for item in sortby:
        field = item.get("field", "")
        direction = item.get("direction", "asc").lower()

        if field not in COLLECTIONS_SORTABLES:
            raise ValueError(
                f"Unsupported sortby field: {field}. "
                f"Allowed fields: {', '.join(sorted(COLLECTIONS_SORTABLES))}"
            )
        if direction not in _VALID_DIRECTIONS:
            raise ValueError(
                f"Invalid sortby direction: {direction}. "
                f"Allowed values: {', '.join(sorted(_VALID_DIRECTIONS))}"
            )

        clauses.append(f"{COLLECTIONS_SORTABLES[field]} {direction.upper()}")

    return clauses


def stac_search_to_where(
    cql2_json_to_sql: Callable[[dict[str, Any]], str],
    geometry: Optional[Union[str, dict[str, float], BaseGeometry]] = None,
    datetime: Optional[str] = None,
    ids: Optional[list[str]] = None,
    federation_backends: Optional[list[str]] = None,
    cql2_json: Optional[dict[str, Any]] = None,
) -> str:
    """Build the WHERE clause for a collections search query.

    The actual SQL syntax is delegated to ``cql2_json_to_sql`` so the same logic
    can serve any backend.
    """
    cql2_conditions: list[dict[str, Any]] = []

    if cql2_json:
        cql2_conditions.append(cql2_json)

    if ids:
        cql2_conditions.append(
            {
                "op": "or",
                "args": [
                    {"op": "in", "args": [{"property": "id"}, ids]},
                    {"op": "in", "args": [{"property": "internal_id"}, ids]},
                ],
            }
        )

    if federation_backends:
        cql2_conditions.append(
            {
                "op": "a_overlaps",
                "args": [
                    {"property": "federation:backends"},
                    federation_backends,
                ],
            }
        )

    if geometry:
        geom = get_geometry_from_various(geometry=geometry)
        if geom is not None:
            cql2_conditions.append(
                {
                    "op": "s_intersects",
                    "args": [
                        {"property": "geometry"},
                        shapely.geometry.mapping(geom),
                    ],
                }
            )

    if datetime:
        start_date_str, end_date_str = get_datetime({"datetime": datetime})
        if end_date_str:
            cql2_conditions.append(
                {
                    "op": "<=",
                    "args": [
                        {"property": "datetime"},
                        {"timestamp": end_date_str},
                    ],
                }
            )
        if start_date_str:
            cql2_conditions.append(
                {
                    "op": ">=",
                    "args": [
                        {"property": "end_datetime"},
                        {"timestamp": start_date_str},
                    ],
                }
            )

    if not cql2_conditions:
        return "True"
    combined = (
        cql2_conditions[0]
        if len(cql2_conditions) == 1
        else {"op": "and", "args": cql2_conditions}
    )
    return cql2_json_to_sql(combined)


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
    def collections_search(
        self,
        geometry: Optional[Union[str, dict[str, float], BaseGeometry]] = None,
        datetime: Optional[str] = None,
        limit: Optional[int] = None,
        q: Optional[str] = None,
        ids: Optional[list[str]] = None,
        federation_backends: Optional[list[str]] = None,
        cql2_text: Optional[str] = None,
        cql2_json: Optional[dict[str, Any]] = None,
        sortby: Optional[list[dict[str, str]]] = None,
        with_fbs_only: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        """Search collections matching the given parameters.

        :param sortby: STAC sort extension objects, e.g.
            ``[{"field": "datetime", "direction": "desc"}]``.
            Allowed fields: ``id``, ``datetime``, ``end_datetime``.
        :returns: A tuple of (returned collections as dictionaries, total number matched).
        """
        pass

    @abstractmethod
    def get_federation_backends(
        self,
        names: Optional[set[str]] = None,
        enabled: Optional[bool] = None,
        fetchable: Optional[bool] = None,
        collection: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> dict[str, dict[str, Any]]:
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
