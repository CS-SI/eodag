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
"""SQLite database layer tests."""

from __future__ import annotations

import sqlite3
import unittest
from typing import Any

import orjson
import shapely.geometry

from eodag.databases.sqlite import (
    SQLiteDatabase,
    create_collections_table,
    register_custom_functions,
)
from eodag.databases.sqlite_cql2 import cql2_json_to_sql
from eodag.databases.sqlite_fts import stac_q_to_fts5


def _norm(sql: str) -> str:
    """Collapse whitespace for SQL comparison."""
    return " ".join(sql.split())


# ---------------------------------------------------------------------------
# Fixture - one unified set of collections
#
#   ONE   - full properties, open-ended temporal, tags=earth+observation
#   TWO   - full properties, closed temporal,     tags=ml+observation
#   THREE - full properties, closed temporal,     tags=earth, accented desc
#   FOUR  - no license / tags / count / score,    open-ended temporal
# ---------------------------------------------------------------------------

COLLECTIONS = [
    {
        "type": "Collection",
        "id": "ONE",
        "_id": "ONE",
        "title": "Optical satellite one",
        "extent": {
            "spatial": {"bbox": [[0.0, 0.0, 10.0, 10.0]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
        "license": "proprietary",
        "description": "sample one",
        "keywords": ["optical", "satellite"],
        "tags": ["earth", "observation"],
        "count": 10,
        "score": 3.5,
    },
    {
        "type": "Collection",
        "id": "TWO",
        "_id": "TWO",
        "title": "Radar satellite two",
        "extent": {
            "spatial": {"bbox": [[20.0, 20.0, 30.0, 30.0]]},
            "temporal": {
                "interval": [["2021-01-01T00:00:00Z", "2021-12-31T23:59:59Z"]]
            },
        },
        "license": "MIT",
        "description": "sample two",
        "keywords": ["radar", "satellite"],
        "tags": ["ml", "observation"],
        "count": 5,
        "score": 2.0,
    },
    {
        "type": "Collection",
        "id": "THREE",
        "_id": "THREE",
        "title": "Climate reanalysis three",
        "extent": {
            "spatial": {"bbox": [[40.0, 40.0, 50.0, 50.0]]},
            "temporal": {
                "interval": [["2022-01-01T00:00:00Z", "2022-12-31T23:59:59Z"]]
            },
        },
        "license": "CC-BY-4.0",
        "description": "Région de Chișinău",
        "keywords": ["climate", "reanalysis"],
        "tags": ["earth"],
        "count": 3,
        "score": 9.0,
    },
    {
        "type": "Collection",
        "id": "FOUR",
        "_id": "FOUR",
        "title": "Radar generation four",
        "extent": {
            "spatial": {"bbox": [[60.0, 60.0, 70.0, 70.0]]},
            "temporal": {"interval": [["2023-01-01T00:00:00Z", None]]},
        },
        "description": "no license field",
        "keywords": ["radar", "satellite"],
    },
]

ALL_IDS = {c["id"] for c in COLLECTIONS}


# ---------------------------------------------------------------------------
# CQL2 JSON builders (reduce repetition in test cases)
# ---------------------------------------------------------------------------


def _cmp(op: str, prop: str, val):
    """Property-literal comparison."""
    return {"op": op, "args": [{"property": prop}, val]}


def _casei_cmp(op: str, prop: str, val: str):
    """Case-insensitive comparison using casei()."""
    return {
        "op": op,
        "args": [
            {"op": "casei", "args": [{"property": prop}]},
            {"op": "casei", "args": [val]},
        ],
    }


def _accenti_cmp(op: str, prop: str, val: str):
    """Accent-insensitive comparison using accenti()."""
    return {
        "op": op,
        "args": [
            {"op": "accenti", "args": [{"property": prop}]},
            {"op": "accenti", "args": [val]},
        ],
    }


def _spatial(op: str, geom):
    """Spatial predicate: op(geometry, geom_literal)."""
    return {"op": op, "args": [{"property": "geometry"}, geom]}


def _prop_prop(op: str, left: str, right: str):
    """Property-property comparison."""
    return {"op": op, "args": [{"property": left}, {"property": right}]}


def _temporal(op: str, prop: str, val):
    """Temporal predicate.  *val* is a timestamp string or an interval dict."""
    if isinstance(val, str):
        literal = {"timestamp": val}
    elif isinstance(val, (list, tuple)):
        literal = {"interval": list(val)}
    else:
        literal = val
    return {"op": op, "args": [{"property": prop}, literal]}


def _array_op(op: str, prop: str, values: list):
    return {"op": op, "args": [{"property": prop}, values]}


def _arith(arith_op: str, prop: str, operand, cmp_op: str, value):
    """Arithmetic expression inside a comparison: (prop arith_op operand) cmp_op value."""
    return {
        "op": cmp_op,
        "args": [
            {"op": arith_op, "args": [{"property": prop}, operand]},
            value,
        ],
    }


def _make_coll_fb(provider: str, collection_id: str) -> tuple[str, str, dict]:
    """Create a (collection_id, fb_name, plugins_config) tuple for the
    private :meth:`SQLiteDatabase._upsert_collections_federation_backends`."""
    return (collection_id, provider, {"search": {"type": "StacSearch"}})


def _register_fb_and_collections(
    db: SQLiteDatabase, coll_fb_tuples: list[tuple[str, str, dict]]
) -> None:
    """Register federation backends + their per-collection configs and
    refresh the denormalized columns. Mirrors what :meth:`SQLiteDatabase.upsert_fb_configs`
    does internally, but works directly from the lightweight test tuples.
    """
    fb_names = sorted({fb_name for _, fb_name, _ in coll_fb_tuples})
    if not fb_names:
        return
    fb_configs: list[
        tuple[str, dict[str, dict[str, Any]], int, dict[str, Any], bool]
    ] = [(name, {"search": {"type": "StacSearch"}}, 0, {}, True) for name in fb_names]
    with db._con:
        db._upsert_federation_backends(fb_configs)
        db._upsert_collections_federation_backends(coll_fb_tuples)
        db._refresh_collections_denorm(fb_names)


class TestCQL2JsonToSql(unittest.TestCase):
    """Comprehensive CQL2 JSON → SQLite conformance tests.

    CQL2 tests are organized by conformance class as defined in OGC 21-065r2
    Annex A.

    * https://docs.ogc.org/is/21-065r2/21-065r2.html

    A single in-memory database is created once for the entire class,
    loaded with :data:`COLLECTIONS`.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.conn = sqlite3.connect(":memory:")
        register_custom_functions(cls.conn)
        create_collections_table(cls.conn)
        cls.conn.executemany(
            """
            INSERT INTO collections (content) VALUES (jsonb(?))
            ON CONFLICT(id) DO UPDATE SET content = excluded.content;
            """,
            [(orjson.dumps(c),) for c in COLLECTIONS],
        )
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.conn.close()

    # -- helpers ----------------------------------------------------------

    def assert_filter(
        self,
        cql2_json: dict[str, Any],
        expected_ids: list[str],
        expected_where: str | None = None,
    ) -> str:
        """Assert the WHERE clause and query results."""
        where_sql = cql2_json_to_sql(cql2_json)

        if expected_where is not None:
            self.assertEqual(_norm(where_sql), _norm(expected_where))

        rows = self.conn.execute(
            f"SELECT id FROM collections WHERE {where_sql} ORDER BY id"
        ).fetchall()
        self.assertSetEqual({r[0] for r in rows}, set(expected_ids))

        return where_sql

    # -- A.1 - Basic CQL2 (comparison, isNull, and/or/not) ---------------

    def test_a1_basic_comparison(self):
        """A.1 - All six comparison operators with property-literal."""
        cases = [
            ("eq", "=", "id", "ONE", ["ONE"], "id = 'ONE'"),
            ("neq", "<>", "id", "ONE", ["FOUR", "THREE", "TWO"], "id <> 'ONE'"),
            (
                "gte",
                ">=",
                "datetime",
                "2021-01-01T00:00:00Z",
                ["FOUR", "THREE", "TWO"],
                "datetime >= '2021-01-01T00:00:00Z'",
            ),
            (
                "lte",
                "<=",
                "datetime",
                "2021-01-01T00:00:00Z",
                ["ONE", "TWO"],
                "datetime <= '2021-01-01T00:00:00Z'",
            ),
            (
                "gt",
                ">",
                "datetime",
                "2021-01-01T00:00:00Z",
                ["FOUR", "THREE"],
                "datetime > '2021-01-01T00:00:00Z'",
            ),
            (
                "lt",
                "<",
                "datetime",
                "2021-01-01T00:00:00Z",
                ["ONE"],
                "datetime < '2021-01-01T00:00:00Z'",
            ),
        ]
        for name, op, prop, val, ids, where in cases:
            with self.subTest(name):
                self.assert_filter(_cmp(op, prop, val), ids, where)

    def test_a1_basic_is_null(self):
        """A.1 - isNull on a JSON property that may be absent."""
        self.assert_filter(
            {"op": "isNull", "args": [{"property": "license"}]},
            ["FOUR"],
            "json_extract(content, '$.license') IS NULL",
        )

    def test_a1_basic_logical(self):
        """A.1 - and, or, not."""
        cases = [
            (
                "and",
                {
                    "op": "and",
                    "args": [
                        _cmp("=", "id", "ONE"),
                        _cmp(">=", "datetime", "2020-01-01T00:00:00Z"),
                    ],
                },
                ["ONE"],
                "id = 'ONE' AND datetime >= '2020-01-01T00:00:00Z'",
            ),
            (
                "or",
                {
                    "op": "or",
                    "args": [
                        _cmp("=", "id", "ONE"),
                        _cmp("=", "id", "TWO"),
                    ],
                },
                ["ONE", "TWO"],
                "id = 'ONE' OR id = 'TWO'",
            ),
            (
                "not",
                {"op": "not", "args": [_cmp("=", "id", "ONE")]},
                ["FOUR", "THREE", "TWO"],
                "NOT id = 'ONE'",
            ),
        ]
        for name, cql2_json, ids, where in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids, where)

    # -- A.2 - Advanced Comparison (like, between, in) --------------------

    def test_a2_advanced_comparison(self):
        """A.2 - like, between, in operators."""
        cases = [
            (
                "like",
                {"op": "like", "args": [{"property": "id"}, "T%"]},
                ["THREE", "TWO"],
                "id LIKE 'T%'",
            ),
            (
                "between",
                {
                    "op": "between",
                    "args": [
                        {"property": "datetime"},
                        "2021-01-01T00:00:00Z",
                        "2022-12-31T23:59:59Z",
                    ],
                },
                ["THREE", "TWO"],
                "datetime BETWEEN '2021-01-01T00:00:00Z' AND '2022-12-31T23:59:59Z'",
            ),
            (
                "in",
                {"op": "in", "args": [{"property": "id"}, ["ONE", "TWO"]]},
                ["ONE", "TWO"],
                "id IN ('ONE', 'TWO')",
            ),
        ]
        for name, cql2_json, ids, where in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids, where)

    # -- A.5 - Case-insensitive Comparison (casei) ------------------------

    def test_a5_case_insensitive(self):
        """A.5 - casei() wrapping property and/or literal operands."""
        cases = [
            (
                "eq_lower",
                _casei_cmp("=", "id", "one"),
                ["ONE"],
                "lower(id) = lower('one')",
            ),
            (
                "eq_upper",
                _casei_cmp("=", "id", "ONE"),
                ["ONE"],
                "lower(id) = lower('ONE')",
            ),
            (
                "eq_mixed",
                _casei_cmp("=", "id", "One"),
                ["ONE"],
                "lower(id) = lower('One')",
            ),
            (
                "like_lower",
                _casei_cmp("like", "id", "t%"),
                ["THREE", "TWO"],
                "lower(id) LIKE lower('t%')",
            ),
            (
                "like_upper",
                _casei_cmp("like", "id", "T%"),
                ["THREE", "TWO"],
                "lower(id) LIKE lower('T%')",
            ),
        ]
        for name, cql2_json, ids, where in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids, where)

    # -- A.6 - Accent-insensitive Comparison (accenti) --------------------

    def test_a6_accent_insensitive(self):
        """A.6 - accenti() wrapping property and/or literal operands."""
        cases = [
            (
                "eq_no_accents",
                _accenti_cmp("=", "description", "Region de Chisinau"),
                ["THREE"],
                "strip_accents(json_extract(content, '$.description'))"
                " = strip_accents('Region de Chisinau')",
            ),
            (
                "eq_with_accents",
                _accenti_cmp("=", "description", "Région de Chișinău"),
                ["THREE"],
                "strip_accents(json_extract(content, '$.description'))"
                " = strip_accents('Région de Chișinău')",
            ),
            (
                "like_no_accents",
                _accenti_cmp("like", "description", "Region%"),
                ["THREE"],
                "strip_accents(json_extract(content, '$.description'))"
                " LIKE strip_accents('Region%')",
            ),
            (
                "like_with_accents",
                _accenti_cmp("like", "description", "Région%"),
                ["THREE"],
                "strip_accents(json_extract(content, '$.description'))"
                " LIKE strip_accents('Région%')",
            ),
        ]
        for name, cql2_json, ids, where in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids, where)

    # -- A.7 - Basic Spatial (s_intersects with point & bbox) -------------

    def test_a7_basic_spatial(self):
        """A.7 - s_intersects with Point and bbox literals."""
        cases = [
            (
                "point",
                _spatial("s_intersects", {"type": "Point", "coordinates": [5.0, 5.0]}),
                ["ONE"],
            ),
            (
                "bbox",
                _spatial("s_intersects", {"bbox": [5.0, 5.0, 25.0, 25.0]}),
                ["ONE", "TWO"],
            ),
        ]
        for name, cql2_json, ids in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids)

    # -- A.8/A.9 - Spatial Functions (full predicate set) -----------------

    def test_a8_a9_spatial_functions(self):
        """A.8/A.9 - Full spatial predicate set with arbitrary geometry types."""
        # fmt: off
        cases = [
            ("s_intersects",
             _spatial("s_intersects", {
                 "type": "Polygon",
                 "coordinates": [[[5, 5], [15, 5], [15, 15], [5, 15], [5, 5]]],
             }),
             ["ONE"]),

            ("s_equals",
             _spatial("s_equals", {
                 "type": "Polygon",
                 "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
             }),
             ["ONE"]),

            ("s_disjoint",
             _spatial("s_disjoint", {
                 "type": "Polygon",
                 "coordinates": [[[100, 100], [110, 100], [110, 110],
                                  [100, 110], [100, 100]]],
             }),
             ALL_IDS),

            ("s_within",
             _spatial("s_within", {
                 "type": "Polygon",
                 "coordinates": [[[-10, -10], [80, -10], [80, 80],
                                  [-10, 80], [-10, -10]]],
             }),
             ALL_IDS),

            ("s_contains",
             _spatial("s_contains", {
                 "type": "Point", "coordinates": [5.0, 5.0],
             }),
             ["ONE"]),

            ("s_overlaps",
             _spatial("s_overlaps", {
                 "type": "Polygon",
                 "coordinates": [[[5, 5], [25, 5], [25, 25], [5, 25], [5, 5]]],
             }),
             ["ONE", "TWO"]),

            ("s_touches",
             _spatial("s_touches", {
                 "type": "Polygon",
                 "coordinates": [[[10, 0], [20, 0], [20, 10], [10, 10], [10, 0]]],
             }),
             ["ONE"]),

            ("s_crosses",
             _spatial("s_crosses", {
                 "type": "LineString",
                 "coordinates": [[5.0, -5.0], [5.0, 15.0]],
             }),
             ["ONE"]),
        ]
        # fmt: on
        for name, cql2_json, ids in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids)

    # -- A.10 - Property-Property Comparisons -----------------------------

    def test_a10_property_property(self):
        """A.10 - Both sides of a comparison may be property references."""
        cases = [
            (
                "eq",
                _prop_prop("=", "datetime", "end_datetime"),
                [],
                "datetime = end_datetime",
            ),
            (
                "neq",
                _prop_prop("<>", "datetime", "end_datetime"),
                ALL_IDS,
                "datetime <> end_datetime",
            ),
            (
                "lt",
                _prop_prop("<", "datetime", "end_datetime"),
                ALL_IDS,
                "datetime < end_datetime",
            ),
            (
                "vs_json",
                _prop_prop("<>", "id", "license"),
                ["ONE", "THREE", "TWO"],
                "id <> json_extract(content, '$.license')",
            ),
        ]
        for name, cql2_json, ids, where in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids, where)

    # -- A.11 - Temporal Functions ----------------------------------------

    def test_a11_temporal_timestamp(self):
        """A.11 - All 15 temporal operators with a timestamp literal (instant vs instant)."""
        ts = "2021-01-01T00:00:00Z"
        # fmt: off
        cases = [
            ("t_after", _temporal("t_after", "datetime", ts), ["FOUR", "THREE"]),
            ("t_before", _temporal("t_before", "datetime", ts), ["ONE"]),
            ("t_equals", _temporal("t_equals", "datetime", ts), ["TWO"]),
            ("t_meets", _temporal("t_meets", "datetime", ts), ["TWO"]),
            ("t_metby", _temporal("t_metby", "datetime", ts), ["TWO"]),
            ("t_intersects", _temporal("t_intersects", "datetime", ts), ["TWO"]),
            ("t_disjoint", _temporal("t_disjoint", "datetime", ts), ["FOUR", "ONE", "THREE"]),
            ("t_contains", _temporal("t_contains", "datetime", ts), []),
            ("t_during", _temporal("t_during", "datetime", ts), []),
            ("t_finishedby", _temporal("t_finishedby", "datetime", ts), []),
            ("t_finishes", _temporal("t_finishes", "datetime", ts), []),
            ("t_overlappedby", _temporal("t_overlappedby", "datetime", ts), []),
            ("t_overlaps", _temporal("t_overlaps", "datetime", ts), []),
            ("t_startedby", _temporal("t_startedby", "datetime", ts), []),
            ("t_starts", _temporal("t_starts", "datetime", ts), []),
        ]
        # fmt: on
        for name, cql2_json, ids in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids)

    def test_a11_temporal_interval(self):
        """A.11 - All 15 temporal operators with an interval literal (instant vs interval)."""
        iv = ["2020-06-01T00:00:00Z", "2021-06-01T00:00:00Z"]
        # fmt: off
        cases = [
            ("t_after", _temporal("t_after", "datetime", iv), ["FOUR", "THREE"]),
            ("t_before", _temporal("t_before", "datetime", iv), ["ONE"]),
            ("t_during", _temporal("t_during", "datetime", iv), ["TWO"]),
            ("t_intersects", _temporal("t_intersects", "datetime", iv), ["TWO"]),
            ("t_disjoint", _temporal("t_disjoint", "datetime", iv), ["FOUR", "ONE", "THREE"]),
            ("t_overlaps", _temporal("t_overlaps", "datetime", iv), ["TWO"]),
            ("t_contains", _temporal("t_contains", "datetime", iv), []),
            ("t_equals", _temporal("t_equals", "datetime", iv), []),
            ("t_finishedby", _temporal("t_finishedby", "datetime", iv), []),
            ("t_finishes", _temporal("t_finishes", "datetime", iv), []),
            ("t_meets", _temporal("t_meets", "datetime", iv), []),
            ("t_metby", _temporal("t_metby", "datetime", iv), []),
            ("t_overlappedby", _temporal("t_overlappedby", "datetime", iv), []),
            ("t_startedby", _temporal("t_startedby", "datetime", iv), []),
            ("t_starts", _temporal("t_starts", "datetime", iv), []),
        ]
        # fmt: on
        for name, cql2_json, ids in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids)

    # -- A.12 - Array Functions -------------------------------------------

    def test_a12_array_functions(self):
        """A.12 - a_contains, a_containedby, a_equals, a_overlaps."""
        cases = [
            (
                "a_contains_both",
                _array_op("a_contains", "tags", ["earth", "observation"]),
                ["ONE"],
            ),
            (
                "a_contains_single",
                _array_op("a_contains", "tags", ["observation"]),
                ["ONE", "TWO"],
            ),
            (
                "a_containedby",
                _array_op("a_containedby", "tags", ["earth", "observation", "ml"]),
                ["ONE", "THREE", "TWO"],
            ),
            ("a_equals", _array_op("a_equals", "tags", ["earth"]), ["THREE"]),
            (
                "a_equals_two",
                _array_op("a_equals", "tags", ["earth", "observation"]),
                ["ONE"],
            ),
            ("a_overlaps_ml", _array_op("a_overlaps", "tags", ["ml"]), ["TWO"]),
            (
                "a_overlaps_earth",
                _array_op("a_overlaps", "tags", ["earth", "ml"]),
                ["ONE", "THREE", "TWO"],
            ),
        ]
        for name, cql2_json, ids in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids)

    # -- A.13 - Arithmetic ------------------------------------------------

    def test_a13_arithmetic(self):
        """A.13 - Arithmetic operators: +, -, *, /, %, ^, div."""
        cases = [
            ("+", _arith("+", "count", 1, "=", 6), ["TWO"]),
            ("-", _arith("-", "count", 2, "=", 3), ["TWO"]),
            ("*", _arith("*", "count", 2, ">", 15), ["ONE"]),
            ("/", _arith("/", "count", 2, "<", 3), ["THREE", "TWO"]),
            ("%", _arith("%", "count", 3, "=", 1), ["ONE"]),
            ("^", _arith("^", "score", 2, "=", 4), ["TWO"]),
            ("div", _arith("div", "count", 3, "=", 3), ["ONE"]),
        ]
        for name, cql2_json, ids in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids)

    # -- Unsupported conformance classes ----------------------------------

    def test_unsupported_operators(self):
        """Operators from unsupported classes must raise NotImplementedError."""
        with self.assertRaises(NotImplementedError) as ctx:
            cql2_json_to_sql(
                {
                    "op": "=",
                    "args": [{"op": "upper", "args": [{"property": "id"}]}, "X"],
                }
            )
        self.assertIn("Unsupported CQL2 operators", str(ctx.exception))


# ===========================================================================
# STAC ``q`` → FTS5 expression tests
# ===========================================================================

# ---------------------------------------------------------------------------
# FTS fixtures - real STAC collections inserted via create_collections_table
# triggers, exercising the actual title/description/keywords extraction.
# ---------------------------------------------------------------------------

FTS_COLLECTIONS = [
    {
        "type": "Collection",
        "id": "S2_L2A",
        "title": "Sentinel-2 Level-2A",
        "description": "Surface reflectance imagery over Europe",
        "keywords": ["optical", "satellite", "copernicus"],
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
    {
        "type": "Collection",
        "id": "S1_GRD",
        "title": "Sentinel-1 GRD",
        "description": "Ground range detected SAR imagery",
        "keywords": ["radar", "satellite", "copernicus"],
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
    {
        "type": "Collection",
        "id": "L8_C2",
        "title": "Landsat 8 Collection 2",
        "description": "Multispectral imagery from Landsat program",
        "keywords": ["optical", "satellite", "landsat"],
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
    {
        "type": "Collection",
        "id": "ERA5",
        "title": "ERA5 Reanalysis",
        "description": "Global climate reanalysis dataset",
        "keywords": ["climate", "reanalysis", "temperature"],
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
    {
        "type": "Collection",
        "id": "MODIS",
        "title": "MODIS Terra",
        "description": "Moderate resolution imaging from Terra satellite",
        "keywords": ["optical", "moderate", "resolution"],
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
]

FTS_ACCENT_COLLECTIONS = [
    {
        "type": "Collection",
        "id": "DONNEES",
        "title": "Données satellitaires",
        "description": "Résolution élevée",
        "keywords": ["données", "satellite"],
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
    {
        "type": "Collection",
        "id": "SATDATA",
        "title": "Satellite data",
        "description": "High resolution",
        "keywords": ["data", "satellite"],
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
]


def _make_fts_conn(collections: list[dict[str, Any]]) -> sqlite3.Connection:
    """Create an in-memory DB with collections table + FTS triggers, insert collections."""
    conn = sqlite3.connect(":memory:")
    register_custom_functions(conn)
    create_collections_table(conn)
    conn.executemany(
        "INSERT INTO collections (content) VALUES (jsonb(?))",
        [(orjson.dumps(c),) for c in collections],
    )
    conn.commit()
    return conn


class TestStacQToFts5(unittest.TestCase):
    """Comprehensive tests for :func:`stac_q_to_fts5`.

    FTS tests exercise the STAC ``q`` → FTS5 expression translation.

    * https://github.com/radiantearth/stac-api-spec/tree/main/fragments/free-text
    * https://www.sqlite.org/fts5.html

    Uses real collections inserted via ``create_collections_table`` triggers
    so the FTS index is populated exactly as in production.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.conn = _make_fts_conn(FTS_COLLECTIONS)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.conn.close()

    # -- helpers ----------------------------------------------------------

    def assert_fts(
        self,
        q: str,
        expected_ids: list[str],
        expected_expr: str | None = None,
    ) -> str:
        """Assert the FTS5 expression string and its query results."""
        expr = stac_q_to_fts5(q)

        if expected_expr is not None:
            self.assertEqual(_norm(expr), _norm(expected_expr))

        rows = self.conn.execute(
            "SELECT c.id FROM collections c"
            " JOIN collections_fts cf ON cf.rowid = c.key"
            " WHERE collections_fts MATCH ? ORDER BY c.id",
            (expr,),
        ).fetchall()
        self.assertEqual(sorted(r[0] for r in rows), sorted(expected_ids))

        return expr

    # -- expression + DB result tests (parametrized) ----------------------

    def test_fts_queries(self):
        """Parametrized: expression string **and** DB results."""
        cases = [
            # -- single terms
            (
                "single: satellite",
                "satellite",
                ["L8_C2", "MODIS", "S1_GRD", "S2_L2A"],
                '"satellite"',
            ),
            ("single: climate", "climate", ["ERA5"], '"climate"'),
            ("single: optical", "optical", ["L8_C2", "MODIS", "S2_L2A"], '"optical"'),
            ("single: nonexistent", "nonexistent", [], '"nonexistent"'),
            # -- implicit OR (STAC default)
            (
                "implicit OR: 2 terms",
                "climate radar",
                ["ERA5", "S1_GRD"],
                '("climate") OR ("radar")',
            ),
            (
                "implicit OR: 3 terms",
                "climate radar landsat",
                ["ERA5", "L8_C2", "S1_GRD"],
                '(("climate") OR ("radar")) OR ("landsat")',
            ),
            # -- explicit AND
            (
                "AND",
                "optical AND satellite",
                ["L8_C2", "MODIS", "S2_L2A"],
                '("optical") AND ("satellite")',
            ),
            ("AND no match", "climate AND optical", [], '("climate") AND ("optical")'),
            # -- explicit OR
            ("OR", "climate OR radar", ["ERA5", "S1_GRD"], '("climate") OR ("radar")'),
            # -- NOT treated as bare term
            ("NOT bare", "not", [], '"not"'),
            (
                "NOT between terms",
                "satellite NOT radar",
                ["L8_C2", "MODIS", "S1_GRD", "S2_L2A"],
                '(("satellite") OR ("NOT")) OR ("radar")',
            ),
            # -- quoted phrases
            (
                "phrase match",
                '"Surface reflectance"',
                ["S2_L2A"],
                '"Surface reflectance"',
            ),
            ("phrase no match", '"reflectance surface"', [], '"reflectance surface"'),
            (
                "phrase + term",
                '"SAR imagery" climate',
                ["ERA5", "S1_GRD"],
                '("SAR imagery") OR ("climate")',
            ),
            # -- parentheses / grouping
            (
                "(OR) AND",
                "(climate OR radar) AND satellite",
                ["S1_GRD"],
                '(("climate") OR ("radar")) AND ("satellite")',
            ),
            (
                "nested parens",
                "((optical AND satellite) OR climate)",
                ["ERA5", "L8_C2", "MODIS", "S2_L2A"],
                '(("optical") AND ("satellite")) OR ("climate")',
            ),
            # -- precedence: AND > OR
            (
                "AND before OR",
                "climate OR optical AND satellite",
                ["ERA5", "L8_C2", "MODIS", "S2_L2A"],
                '("climate") OR (("optical") AND ("satellite"))',
            ),
            (
                "parens override",
                "(climate OR optical) AND satellite",
                ["L8_C2", "MODIS", "S2_L2A"],
                '(("climate") OR ("optical")) AND ("satellite")',
            ),
            # -- complex
            (
                "complex",
                "optical AND (climate OR radar)",
                [],
                '("optical") AND (("climate") OR ("radar"))',
            ),
        ]
        for name, q, ids, expected_expr in cases:
            with self.subTest(name):
                self.assert_fts(q, ids, expected_expr)

    # -- expression-only tests (no DB needed) -----------------------------

    def test_expression_only(self):
        """Parametrized: expression string only (no DB execution)."""
        cases = [
            ("4 implicit OR", "a b c d", '((("a") OR ("b")) OR ("c")) OR ("d")'),
            ("AND chain", "a AND b AND c", '(("a") AND ("b")) AND ("c")'),
            (
                "mixed ops",
                "a AND b OR c AND d",
                '(("a") AND ("b")) OR (("c") AND ("d"))',
            ),
            ("case and", "optical and satellite", '("optical") AND ("satellite")'),
            ("case Or", "optical Or satellite", '("optical") OR ("satellite")'),
            ("internal quotes", 'foo"bar', '("foo") OR ("bar")'),
        ]
        for name, q, expected_expr in cases:
            with self.subTest(name):
                self.assertEqual(_norm(stac_q_to_fts5(q)), _norm(expected_expr))

    # -- unsupported operators (+, -) -------------------------------------

    def test_unsupported_operators(self):
        """Parametrized: +/- prefix operators raise ValueError."""
        cases = [
            ("plus", "+satellite"),
            ("minus", "-satellite"),
            ("mixed signs", "+optical -landsat"),
        ]
        for name, q in cases:
            with self.subTest(name):
                with self.assertRaises(ValueError) as ctx:
                    stac_q_to_fts5(q)
                self.assertIn("Unsupported operator", str(ctx.exception))

    # -- error handling ---------------------------------------------------

    def test_errors(self):
        """Parametrized: invalid input raises ValueError."""
        cases = [
            ("unbalanced open", "(optical AND satellite", "Unbalanced parentheses"),
            ("unbalanced close", "optical) AND satellite", "Unbalanced parentheses"),
        ]
        for name, q, msg in cases:
            with self.subTest(name):
                with self.assertRaises(ValueError) as ctx:
                    stac_q_to_fts5(q)
                self.assertIn(msg, str(ctx.exception))

    # -- empty input ------------------------------------------------------

    def test_empty_input(self):
        """Parametrized: empty / whitespace input returns empty string."""
        for q in ("", "   "):
            with self.subTest(q=repr(q)):
                self.assertEqual(stac_q_to_fts5(q), "")

    # -- BM25 ranking -----------------------------------------------------

    def test_ranking(self):
        """BM25 ranking: title > description > keywords (10, 3, 1)."""
        conn = _make_fts_conn(
            [
                {
                    "type": "Collection",
                    "id": "TITLE_HIT",
                    "title": "satellite overview",
                    "description": "general description",
                    "keywords": ["misc"],
                    "extent": {
                        "spatial": {"bbox": [[0, 0, 1, 1]]},
                        "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
                    },
                },
                {
                    "type": "Collection",
                    "id": "DESC_HIT",
                    "title": "overview",
                    "description": "satellite imagery description",
                    "keywords": ["misc"],
                    "extent": {
                        "spatial": {"bbox": [[0, 0, 1, 1]]},
                        "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
                    },
                },
                {
                    "type": "Collection",
                    "id": "KW_HIT",
                    "title": "overview",
                    "description": "general description",
                    "keywords": ["satellite", "misc"],
                    "extent": {
                        "spatial": {"bbox": [[0, 0, 1, 1]]},
                        "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
                    },
                },
            ]
        )
        fts = stac_q_to_fts5("satellite")
        rows = conn.execute(
            "SELECT c.id FROM collections c"
            " JOIN collections_fts cf ON cf.rowid = c.key"
            " WHERE collections_fts MATCH ?"
            " ORDER BY bm25(collections_fts, 10.0, 3.0, 1.0) ASC",
            (fts,),
        ).fetchall()
        # title hit first, then description, then keywords
        self.assertListEqual([r[0] for r in rows], ["TITLE_HIT", "DESC_HIT", "KW_HIT"])
        conn.close()

    # -- diacritics / accent handling -------------------------------------

    def test_diacritics(self):
        """Parametrized: remove_diacritics=2 matches accented/unaccented."""
        conn = _make_fts_conn(FTS_ACCENT_COLLECTIONS)
        cases = [
            ("unaccented→accented", "donnees", ["DONNEES"]),
            ("accented→accented", "données", ["DONNEES"]),
            ("accented→unaccented", "résolution", ["DONNEES", "SATDATA"]),
        ]
        for name, q, ids in cases:
            with self.subTest(name):
                fts = stac_q_to_fts5(q)
                rows = conn.execute(
                    "SELECT c.id FROM collections c"
                    " JOIN collections_fts cf ON cf.rowid = c.key"
                    " WHERE collections_fts MATCH ?",
                    (fts,),
                ).fetchall()
                self.assertEqual(sorted(r[0] for r in rows), sorted(ids))
        conn.close()


# ===========================================================================
# collections_search integration tests
# ===========================================================================


class TestCollectionsSearch(unittest.TestCase):
    """Integration tests for :meth:`SQLiteDatabase.collections_search`.

    Uses the shared :data:`COLLECTIONS` fixture.  Exercises sortby, geometry,
    datetime, limit, q, cql2, and their combinations.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.db = SQLiteDatabase(":memory:")
        cls.db._con.executemany(
            "INSERT INTO collections (content) VALUES (jsonb(?))",
            [(orjson.dumps(c),) for c in COLLECTIONS],
        )
        cls.db._con.commit()

        # Federation backends:
        #   ONE   -> ["backend_a", "backend_b"]
        #   TWO   -> ["backend_b"]
        #   THREE -> (none)
        #   FOUR  -> (none)
        _register_fb_and_collections(
            cls.db,
            [
                _make_coll_fb("backend_a", "ONE"),
                _make_coll_fb("backend_b", "ONE"),
                _make_coll_fb("backend_b", "TWO"),
            ],
        )

    def _ids(self, result: tuple[list[dict[str, Any]], int]) -> list[str]:
        """Extract ordered list of ids from collections_search result."""
        return [c["id"] for c in result[0]]

    def _matched(self, result: tuple[list[dict[str, Any]], int]) -> int:
        return result[1]

    def test_no_params(self):
        """Default (with_fbs_only=True) returns only collections that have at least one
        federation backend, ordered by id ASC.  with_fbs_only=False returns everything.
        """
        # Fixture: ONE & TWO have backends; THREE & FOUR do not.
        result = self.db.collections_search()
        self.assertListEqual(self._ids(result), ["ONE", "TWO"])
        self.assertEqual(self._matched(result), 2)

        result_all = self.db.collections_search(with_fbs_only=False)
        # Ordering: priority DESC (ONE/TWO have priority=0 from their backends;
        # THREE/FOUR have priority=NULL → sorted last), then id ASC within each tier.
        self.assertListEqual(self._ids(result_all), ["ONE", "TWO", "FOUR", "THREE"])
        self.assertEqual(self._matched(result_all), 4)

    def test_returns_dicts(self):
        """collections_search returns list of dicts with 'id' keys."""
        collections, _ = self.db.collections_search(limit=1)
        self.assertIsInstance(collections, list)
        self.assertIsInstance(collections[0], dict)
        self.assertIn("id", collections[0])

    def test_limit(self):
        """Limit caps the page size; total matched reflects the full result set.

        with_fbs_only=True (default) - only ONE & TWO visible (matched=2).
        with_fbs_only=False           - all four collections visible (matched=4).
        """
        cases = [
            # (name, limit, with_fbs_only, expected_page_len, expected_matched)
            ("limit=2 with_fbs_only=True", 2, True, 2, 2),
            ("limit=1 with_fbs_only=True", 1, True, 1, 2),
            ("limit=2 with_fbs_only=False", 2, False, 2, 4),
            ("limit=1 with_fbs_only=False", 1, False, 1, 4),
        ]
        for name, limit, with_fbs_only, expected_len, expected_matched in cases:
            with self.subTest(name):
                result = self.db.collections_search(
                    limit=limit, with_fbs_only=with_fbs_only
                )
                self.assertEqual(len(result[0]), expected_len)
                self.assertEqual(self._matched(result), expected_matched)

    def test_datetime(self):
        cases = [
            ("single instant", "2021-06-01T00:00:00Z", {"ONE", "TWO"}),
            (
                "closed range",
                "2021-06-01T00:00:00Z/2022-06-01T00:00:00Z",
                {"ONE", "THREE", "TWO"},
            ),
            ("open start", "../2020-06-01T00:00:00Z", {"ONE"}),
            ("open end", "2022-06-01T00:00:00Z/..", {"FOUR", "ONE", "THREE"}),
        ]
        for name, dt, expected_ids in cases:
            with self.subTest(name):
                result = self.db.collections_search(datetime=dt, with_fbs_only=False)
                self.assertSetEqual(set(self._ids(result)), expected_ids)

    def test_geometry(self):
        cases = [
            ("point in ONE", shapely.geometry.Point(5.0, 5.0), {"ONE"}),
            (
                "box ONE+TWO",
                shapely.geometry.box(5.0, 5.0, 25.0, 25.0),
                {"ONE", "TWO"},
            ),
            ("no match", shapely.geometry.Point(100.0, 100.0), set()),
        ]
        for name, geom, expected_ids in cases:
            with self.subTest(name):
                result = self.db.collections_search(geometry=geom)
                self.assertSetEqual(set(self._ids(result)), expected_ids)

    def test_sortby(self):
        all_cases = [
            (
                "id asc all",
                [{"field": "id", "direction": "asc"}],
                ["FOUR", "ONE", "THREE", "TWO"],
            ),
            (
                "id desc all",
                [{"field": "id", "direction": "desc"}],
                ["TWO", "THREE", "ONE", "FOUR"],
            ),
            (
                "datetime asc all",
                [{"field": "datetime", "direction": "asc"}],
                ["ONE", "TWO", "THREE", "FOUR"],
            ),
            (
                "datetime desc all",
                [{"field": "datetime", "direction": "desc"}],
                ["FOUR", "THREE", "TWO", "ONE"],
            ),
            (
                "end_datetime asc all",
                [{"field": "end_datetime", "direction": "asc"}],
                [
                    "TWO",
                    "THREE",
                    "ONE",
                    "FOUR",
                ],  # ONE (priority=0) before FOUR (NULL) in tie-break
            ),
        ]
        for name, sortby, expected_ids in all_cases:
            with self.subTest(name):
                result = self.db.collections_search(sortby=sortby, with_fbs_only=False)
                self.assertListEqual(self._ids(result), expected_ids)

    def test_sortby_errors(self):
        cases = [
            (
                "invalid field",
                [{"field": "title", "direction": "asc"}],
                "Unsupported sortby field",
            ),
            (
                "invalid direction",
                [{"field": "id", "direction": "sideways"}],
                "Invalid sortby direction",
            ),
            ("missing field", [{"direction": "asc"}], "Unsupported sortby field"),
        ]
        for name, sortby, msg in cases:
            with self.subTest(name):
                with self.assertRaises(ValueError) as ctx:
                    self.db.collections_search(sortby=sortby)
                self.assertIn(msg, str(ctx.exception))

    def test_q(self):
        cases = [
            ("radar", "radar", {}, {"FOUR", "TWO"}),
            ("no match", "nonexistent", {}, set()),
            (
                "satellite + datetime",
                "satellite",
                {"datetime": "../2021-06-01T00:00:00Z"},
                {"ONE", "TWO"},
            ),
        ]
        for name, q, kwargs, expected_ids in cases:
            with self.subTest(name):
                result = self.db.collections_search(q=q, with_fbs_only=False, **kwargs)
                self.assertSetEqual(set(self._ids(result)), expected_ids)

    def test_q_sortby_overrides_bm25(self):
        """Explicit sortby overrides BM25 ranking order."""
        result = self.db.collections_search(
            q="satellite",
            sortby=[{"field": "id", "direction": "desc"}],
            with_fbs_only=False,
        )
        # satellite in keywords: ONE, TWO, FOUR → sorted id desc
        self.assertListEqual(self._ids(result), ["TWO", "ONE", "FOUR"])

    def test_cql2(self):
        cases = [
            ("json match", {"cql2_json": _cmp("=", "id", "ONE")}, ["ONE"]),
            ("text match", {"cql2_text": "id = 'TWO'"}, ["TWO"]),
            (
                "json match no backend",
                {"cql2_json": _cmp("=", "id", "THREE")},
                ["THREE"],
            ),
            ("text match no backend", {"cql2_text": "id = 'THREE'"}, ["THREE"]),
        ]
        for name, kwargs, expected_ids in cases:
            with self.subTest(name):
                result = self.db.collections_search(with_fbs_only=False, **kwargs)
                self.assertListEqual(self._ids(result), expected_ids)

    def test_cql2_text_and_json_raises(self):
        with self.assertRaises(ValueError):
            self.db.collections_search(
                cql2_text="id = 'ONE'",
                cql2_json=_cmp("=", "id", "ONE"),
            )

    def test_all_combined(self):
        """Geometry + datetime + CQL2 + sortby + limit."""
        result = self.db.collections_search(
            geometry=shapely.geometry.box(-10, -10, 80, 80),  # covers all
            datetime="2021-06-01T00:00:00Z/2022-06-01T00:00:00Z",
            cql2_json=_cmp("<>", "id", "THREE"),
            sortby=[{"field": "datetime", "direction": "desc"}],
            limit=10,
        )
        # Spatial: all 4.  Temporal: ONE, TWO, THREE.  CQL2: not THREE → ONE, TWO.
        # Sorted datetime desc: TWO(2021), ONE(2020)
        self.assertListEqual(self._ids(result), ["TWO", "ONE"])
        self.assertEqual(self._matched(result), 2)

    def test_federation_backends(self):
        """Filter collections by federation_backends."""
        cases = [
            # (name, fb_filter, extra_kwargs, expected_ids, expected_matched)
            (
                "no filter - with_fbs_only=False returns all",
                None,
                {"with_fbs_only": False},
                ALL_IDS,
                4,
            ),
            ("single backend", ["backend_a"], {}, {"ONE"}, 1),
            ("shared backend", ["backend_b"], {}, {"ONE", "TWO"}, 2),
            (
                "multiple backends (union)",
                ["backend_a", "backend_b"],
                {},
                {"ONE", "TWO"},
                2,
            ),
            ("nonexistent backend", ["backend_z"], {}, set(), 0),
            (
                "with geometry",
                ["backend_a"],
                {"geometry": shapely.geometry.box(-5, -5, 15, 15)},
                {"ONE"},
                1,
            ),
            (
                "with datetime",
                ["backend_b"],
                {"datetime": "2021-01-01T00:00:00Z/.."},
                {"ONE", "TWO"},
                2,
            ),
        ]
        for name, fb, kwargs, expected_ids, expected_matched in cases:
            with self.subTest(name):
                result = self.db.collections_search(federation_backends=fb, **kwargs)
                self.assertSetEqual(set(self._ids(result)), expected_ids)
                self.assertEqual(self._matched(result), expected_matched)

    def test_federation_backends_denormalization_update(self):
        """Adding backends incrementally keeps the denormalized column in sync."""
        db = SQLiteDatabase(":memory:")
        db._con.executemany(
            "INSERT INTO collections (content) VALUES (jsonb(?))",
            [(orjson.dumps(c),) for c in COLLECTIONS[:1]],  # only ONE
        )
        db._con.commit()

        cases = [
            ("initially empty", [], ["backend_x"], 0),
            ("after adding backend_x", [("backend_x", "ONE")], ["backend_x"], 1),
            (
                "after adding backend_y, backend_x still matches",
                [("backend_y", "ONE")],
                ["backend_x"],
                1,
            ),
            ("backend_y also matches", [], ["backend_y"], 1),
            ("both together match", [], ["backend_x", "backend_y"], 1),
        ]
        for name, to_add, fb_filter, expected_matched in cases:
            with self.subTest(name):
                if to_add:
                    _register_fb_and_collections(
                        db, [_make_coll_fb(prov, coll) for prov, coll in to_add]
                    )
                result = db.collections_search(federation_backends=fb_filter)
                self.assertEqual(self._matched(result), expected_matched)

        db.close()


# TODO: add tests on all methods of SQLiteDatabase, not only on collections search.
