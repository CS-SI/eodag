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
"""Generic database base helper tests."""

from __future__ import annotations

import unittest
from typing import Any
from unittest import mock

from shapely.geometry import box

from eodag.api.collection import Collection, CollectionsDict
from eodag.databases.base import (
    Database,
    extract_ops,
    extract_properties,
    stac_search_to_where,
    stac_sortby_to_order_by,
    validate_supported_ops,
)
from eodag.databases.sqlite import SQLiteDatabase
from eodag.databases.sqlite_cql2 import cql2_json_to_sql
from tests.units.test_database_sqlite import (
    COLLECTIONS,
    _cmp,
    _make_coll_fb,
    _register_fb_and_collections,
)


def _collection_from_fixture(data: dict[str, Any]) -> Collection:
    """Build a Collection from fixture data without private _id input."""
    collection_data = {key: value for key, value in data.items() if key != "_id"}
    return Collection(**collection_data)


def _make_memory_db(collections: list[dict[str, Any]] | None = None) -> SQLiteDatabase:
    db = SQLiteDatabase(":memory:")
    if collections:
        db.upsert_collections(
            CollectionsDict([_collection_from_fixture(item) for item in collections])
        )
    return db


class _ConcreteDatabase(Database):
    """Concrete test double for Database context-manager methods."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def delete_collections(self, collection_ids: list[str]) -> None:
        pass

    def delete_collections_federation_backends(self, collection_ids: list[str]) -> None:
        pass

    def delete_federation_backends(self, names: list[str]) -> None:
        pass

    def upsert_collections(self, collections) -> None:
        pass

    def upsert_fb_configs(self, configs) -> None:
        pass

    def collections_search(
        self,
        geometry=None,
        datetime=None,
        limit=None,
        q=None,
        ids=None,
        federation_backends=None,
        cql2_text=None,
        cql2_json=None,
        sortby=None,
        with_fbs_only=True,
    ):
        return [], 0

    def get_federation_backends(
        self,
        names=None,
        collection=None,
        enabled=None,
        fetchable=None,
        limit=None,
    ):
        return {}

    def get_fb_config(self, name: str, collections: set[str] | None = None):
        return {}

    def restore_fbs(self) -> None:
        pass

    def set_priority(self, name: str, priority: int) -> None:
        pass


class TestDatabaseBaseMethods(unittest.TestCase):
    """Coverage for non-abstract helpers from eodag.databases.base."""

    def test_context_manager_closes_database(self) -> None:
        """Database context manager returns itself and closes on exit."""
        db = _ConcreteDatabase()

        with db as returned:
            self.assertIs(returned, db)
            self.assertFalse(db.closed)

        self.assertTrue(db.closed)

    def test_del_closes_database(self) -> None:
        """Database finalizer delegates to close."""
        db = _ConcreteDatabase()

        with mock.patch.object(db, "close") as close_mock:
            db.__del__()

        close_mock.assert_called_once_with()

    def test_extract_ops_nested(self) -> None:
        """extract_ops collects operators from nested CQL2 JSON."""
        cql2_json = {
            "op": "and",
            "args": [
                _cmp("=", "id", "ONE"),
                {
                    "op": "not",
                    "args": [
                        {
                            "op": "or",
                            "args": [
                                _cmp("like", "license", "MIT"),
                                {"op": "casei", "args": [{"property": "title"}]},
                            ],
                        }
                    ],
                },
            ],
        }

        ops: set[str] = set()
        extract_ops(cql2_json, ops)

        self.assertEqual(ops, {"and", "=", "not", "or", "like", "casei"})

    def test_extract_properties_nested(self) -> None:
        """extract_properties collects property names from nested CQL2 JSON."""
        cql2_json = {
            "op": "and",
            "args": [
                _cmp("=", "id", "ONE"),
                {
                    "op": "or",
                    "args": [
                        {"op": "isNull", "args": [{"property": "license"}]},
                        {
                            "op": "s_intersects",
                            "args": [
                                {"property": "geometry"},
                                {"type": "Point", "coordinates": [0, 0]},
                            ],
                        },
                    ],
                },
            ],
        }

        properties: set[str] = set()
        extract_properties(cql2_json, properties)

        self.assertEqual(properties, {"id", "license", "geometry"})

    def test_validate_supported_ops_accepts_supported_tree(self) -> None:
        """validate_supported_ops accepts known operators."""
        validate_supported_ops(
            {
                "op": "and",
                "args": [
                    _cmp("=", "id", "ONE"),
                    {"op": "a_overlaps", "args": [{"property": "tags"}, ["earth"]]},
                ],
            }
        )

    def test_validate_supported_ops_rejects_unsupported_tree(self) -> None:
        """validate_supported_ops rejects unknown operators."""
        with self.assertRaises(NotImplementedError) as ctx:
            validate_supported_ops(
                {
                    "op": "=",
                    "args": [
                        {"op": "upper", "args": [{"property": "id"}]},
                        "ONE",
                    ],
                }
            )

        self.assertIn("Unsupported CQL2 operators: upper", str(ctx.exception))

    def test_stac_sortby_to_order_by_valid(self) -> None:
        """stac_sortby_to_order_by converts allowed sort fields."""
        terms = stac_sortby_to_order_by(
            [
                {"field": "id", "direction": "asc"},
                {"field": "datetime", "direction": "desc"},
                {"field": "end_datetime"},
            ]
        )

        self.assertEqual(
            terms,
            ["c.id ASC", "c.datetime DESC", "c.end_datetime ASC"],
        )

    def test_stac_sortby_to_order_by_invalid(self) -> None:
        """stac_sortby_to_order_by rejects invalid fields and directions."""
        cases = [
            (
                [{"field": "title", "direction": "asc"}],
                "Unsupported sortby field",
            ),
            (
                [{"field": "id", "direction": "invalid"}],
                "Invalid sortby direction",
            ),
            (
                [{"direction": "asc"}],
                "Unsupported sortby field",
            ),
        ]

        for sortby, expected_message in cases:
            with self.subTest(sortby=sortby):
                with self.assertRaises(ValueError) as ctx:
                    stac_sortby_to_order_by(sortby)
                self.assertIn(expected_message, str(ctx.exception))

    def test_stac_search_to_where_no_filters(self) -> None:
        """stac_search_to_where returns a true predicate without filters."""
        self.assertEqual(
            stac_search_to_where(cql2_json_to_sql, None, None, None, None, None),
            "True",
        )

    def test_stac_search_to_where_ids_matches_id_and_internal_id(self) -> None:
        """stac_search_to_where filters by public and internal ids."""
        db = _make_memory_db(COLLECTIONS)
        try:
            where = stac_search_to_where(
                cql2_json_to_sql,
                ids=["ONE", "THREE"],
            )
            rows = db._execute(
                f"SELECT c.id FROM collections c WHERE {where} ORDER BY c.id"
            ).fetchall()

            self.assertEqual([r["id"] for r in rows], ["ONE", "THREE"])
        finally:
            db.close()

    def test_stac_search_to_where_datetime_instant(self) -> None:
        """stac_search_to_where filters collections matching an instant."""
        db = _make_memory_db(COLLECTIONS)
        try:
            where = stac_search_to_where(
                cql2_json_to_sql,
                datetime="2021-06-01T00:00:00Z",
            )
            rows = db._execute(
                f"SELECT c.id FROM collections c WHERE {where} ORDER BY c.id"
            ).fetchall()

            self.assertEqual([r["id"] for r in rows], ["ONE", "TWO"])
        finally:
            db.close()

    def test_stac_search_to_where_datetime_interval(self) -> None:
        """stac_search_to_where filters collections overlapping an interval."""
        db = _make_memory_db(COLLECTIONS)
        try:
            where = stac_search_to_where(
                cql2_json_to_sql,
                datetime="2021-06-01T00:00:00Z/2022-06-01T00:00:00Z",
            )
            rows = db._execute(
                f"SELECT c.id FROM collections c WHERE {where} ORDER BY c.id"
            ).fetchall()

            self.assertEqual([r["id"] for r in rows], ["ONE", "THREE", "TWO"])
        finally:
            db.close()

    def test_stac_search_to_where_geometry(self) -> None:
        """stac_search_to_where filters collections intersecting a geometry."""
        db = _make_memory_db(COLLECTIONS)
        try:
            where = stac_search_to_where(
                cql2_json_to_sql,
                geometry=box(5.0, 5.0, 25.0, 25.0),
            )
            rows = db._execute(
                f"SELECT c.id FROM collections c WHERE {where} ORDER BY c.id"
            ).fetchall()

            self.assertEqual([r["id"] for r in rows], ["ONE", "TWO"])
        finally:
            db.close()

    def test_stac_search_to_where_federation_backends(self) -> None:
        """stac_search_to_where filters collections by backend overlap."""
        db = _make_memory_db(COLLECTIONS)
        try:
            _register_fb_and_collections(
                db,
                [
                    _make_coll_fb("backend_a", "ONE"),
                    _make_coll_fb("backend_b", "ONE"),
                    _make_coll_fb("backend_b", "TWO"),
                ],
            )

            where = stac_search_to_where(
                cql2_json_to_sql,
                federation_backends=["backend_a"],
            )
            rows = db._execute(
                f"SELECT c.id FROM collections c WHERE {where} ORDER BY c.id"
            ).fetchall()

            self.assertEqual([r["id"] for r in rows], ["ONE"])
        finally:
            db.close()

    def test_stac_search_to_where_cql2_json(self) -> None:
        """stac_search_to_where includes caller-provided CQL2 JSON."""
        db = _make_memory_db(COLLECTIONS)
        try:
            where = stac_search_to_where(
                cql2_json_to_sql,
                cql2_json=_cmp("=", "id", "TWO"),
            )
            rows = db._execute(
                f"SELECT c.id FROM collections c WHERE {where} ORDER BY c.id"
            ).fetchall()

            self.assertEqual([r["id"] for r in rows], ["TWO"])
        finally:
            db.close()

    def test_stac_search_to_where_combined(self) -> None:
        """stac_search_to_where combines all supported filter families."""
        db = _make_memory_db(COLLECTIONS)
        try:
            _register_fb_and_collections(
                db,
                [
                    _make_coll_fb("backend_a", "ONE"),
                    _make_coll_fb("backend_b", "ONE"),
                    _make_coll_fb("backend_b", "TWO"),
                ],
            )

            where = stac_search_to_where(
                cql2_json_to_sql,
                geometry=box(-5.0, -5.0, 35.0, 35.0),
                datetime="2020-01-01T00:00:00Z/2021-12-31T23:59:59Z",
                ids=["ONE", "TWO", "THREE"],
                federation_backends=["backend_b"],
                cql2_json=_cmp("<>", "id", "THREE"),
            )
            rows = db._execute(
                f"SELECT c.id FROM collections c WHERE {where} ORDER BY c.id"
            ).fetchall()

            self.assertEqual([r["id"] for r in rows], ["ONE", "TWO"])
        finally:
            db.close()
