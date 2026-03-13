"""CQL2 JSON → SQLite conformance tests.

Tests are organized by CQL2 conformance class as defined in OGC 21-065r2
Annex A.  Parametrized via ``subTest`` to minimize boilerplate.

The unit under test is :func:`eodag.databases.sqlite_cql2.cql2_json_to_sql`.
Each test verifies both the generated WHERE clause (string) **and** that
executing it against a real in-memory SQLite database returns the expected rows.

References
----------
* https://docs.ogc.org/is/21-065r2/21-065r2.html
* https://docs.ogc.org/is/21-065r2/21-065r2.html#ats
"""

from __future__ import annotations

import sqlite3
import unittest
from typing import Any

import orjson

from eodag.databases.sqlite import create_collections_table, register_custom_functions
from eodag.databases.sqlite_cql2 import cql2_json_to_sql

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _norm(sql: str) -> str:
    """Collapse whitespace for SQL comparison."""
    return " ".join(sql.split())


def _insert_collections(
    conn: sqlite3.Connection, collections: list[dict[str, Any]]
) -> None:
    """Insert (or upsert) collection dicts into the collections table."""
    conn.executemany(
        """
        INSERT INTO collections (content) VALUES (jsonb(?))
        ON CONFLICT(id) DO UPDATE SET content = excluded.content;
        """,
        [(orjson.dumps(c),) for c in collections],
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_COLLECTIONS = [
    {
        "type": "Collection",
        "id": "TEST_ONE",
        "extent": {
            "spatial": {"bbox": [[0.0, 0.0, 10.0, 10.0]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
        "license": "proprietary",
        "description": "sample one",
    },
    {
        "type": "Collection",
        "id": "TEST_TWO",
        "extent": {
            "spatial": {"bbox": [[20.0, 20.0, 30.0, 30.0]]},
            "temporal": {
                "interval": [["2021-01-01T00:00:00Z", "2021-12-31T23:59:59Z"]]
            },
        },
        "license": "MIT",
        "description": "sample two",
    },
    {
        "type": "Collection",
        "id": "TEST_THREE",
        "extent": {
            "spatial": {"bbox": [[40.0, 40.0, 50.0, 50.0]]},
            "temporal": {
                "interval": [["2022-01-01T00:00:00Z", "2022-12-31T23:59:59Z"]]
            },
        },
        "license": "CC-BY-4.0",
        "description": "sample three",
    },
]

ALL_IDS = sorted(c["id"] for c in SAMPLE_COLLECTIONS)

# Collection with accented description (used by TestAccentInsensitive)
ACCENT_COLLECTION = {
    "type": "Collection",
    "id": "TEST_ACCENT",
    "extent": {
        "spatial": {"bbox": [[50.0, 50.0, 60.0, 60.0]]},
        "temporal": {"interval": [["2023-06-01T00:00:00Z", None]]},
    },
    "license": "CC-BY-4.0",
    "description": "Région de Chișinău",
}

# Collection without license (used by isNull tests)
NO_LICENSE_COLLECTION = {
    "type": "Collection",
    "id": "TEST_NOLICENSE",
    "extent": {
        "spatial": {"bbox": [[60.0, 60.0, 70.0, 70.0]]},
        "temporal": {"interval": [["2023-01-01T00:00:00Z", None]]},
    },
    "description": "no license field",
}


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


# ---------------------------------------------------------------------------
# Base test class
# ---------------------------------------------------------------------------


class CQL2TestBase(unittest.TestCase):
    """Shared setUp / tearDown / assertion helpers."""

    collections: list[dict[str, Any]] = SAMPLE_COLLECTIONS

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        register_custom_functions(self.conn)
        create_collections_table(self.conn)
        _insert_collections(self.conn, self.collections)

    def tearDown(self) -> None:
        self.conn.close()

    def assert_filter(
        self,
        cql2_json: dict[str, Any],
        expected_ids: list[str],
        expected_where: str | None = None,
    ) -> str:
        """Call *cql2_json_to_sql*, assert the WHERE clause and query results."""
        where_sql = cql2_json_to_sql(cql2_json)

        if expected_where is not None:
            self.assertEqual(_norm(where_sql), _norm(expected_where))

        rows = self.conn.execute(
            f"SELECT id FROM collections WHERE {where_sql} ORDER BY id"
        ).fetchall()
        self.assertEqual(sorted(r[0] for r in rows), sorted(expected_ids))

        return where_sql


# ===================================================================
# A.1 – Basic CQL2  (conf/basic-cql2)
# ===================================================================


class TestBasicCQL2(CQL2TestBase):
    """Comparison operators (=, <>, <, <=, >, >=), isNull, and/or/not.

    Only property-literal comparisons are required.
    """

    def test_comparison_operators(self):
        """A.1 – All six comparison operators with property-literal."""
        cases = [
            ("eq", "=", "id", "TEST_ONE", ["TEST_ONE"], "id = 'TEST_ONE'"),
            (
                "neq",
                "<>",
                "id",
                "TEST_ONE",
                ["TEST_THREE", "TEST_TWO"],
                "id <> 'TEST_ONE'",
            ),
            (
                "gte",
                ">=",
                "datetime",
                "2021-01-01T00:00:00Z",
                ["TEST_THREE", "TEST_TWO"],
                "datetime >= '2021-01-01T00:00:00Z'",
            ),
            (
                "lte",
                "<=",
                "datetime",
                "2021-01-01T00:00:00Z",
                ["TEST_ONE", "TEST_TWO"],
                "datetime <= '2021-01-01T00:00:00Z'",
            ),
            (
                "gt",
                ">",
                "datetime",
                "2021-01-01T00:00:00Z",
                ["TEST_THREE"],
                "datetime > '2021-01-01T00:00:00Z'",
            ),
            (
                "lt",
                "<",
                "datetime",
                "2021-01-01T00:00:00Z",
                ["TEST_ONE"],
                "datetime < '2021-01-01T00:00:00Z'",
            ),
        ]
        for name, op, prop, val, ids, where in cases:
            with self.subTest(name):
                self.assert_filter(_cmp(op, prop, val), ids, where)

    def test_is_null(self):
        """A.1 – isNull on a JSON property that may be absent."""
        _insert_collections(self.conn, [NO_LICENSE_COLLECTION])
        self.assert_filter(
            {"op": "isNull", "args": [{"property": "license"}]},
            ["TEST_NOLICENSE"],
            "json_extract(content, '$.license') IS NULL",
        )

    def test_logical_operators(self):
        """A.1 – and, or, not."""
        cases = [
            (
                "and",
                {
                    "op": "and",
                    "args": [
                        _cmp("=", "id", "TEST_ONE"),
                        _cmp(">=", "datetime", "2020-01-01T00:00:00Z"),
                    ],
                },
                ["TEST_ONE"],
                "id = 'TEST_ONE' AND datetime >= '2020-01-01T00:00:00Z'",
            ),
            (
                "or",
                {
                    "op": "or",
                    "args": [
                        _cmp("=", "id", "TEST_ONE"),
                        _cmp("=", "id", "TEST_TWO"),
                    ],
                },
                ["TEST_ONE", "TEST_TWO"],
                "id = 'TEST_ONE' OR id = 'TEST_TWO'",
            ),
            (
                "not",
                {
                    "op": "not",
                    "args": [_cmp("=", "id", "TEST_ONE")],
                },
                ["TEST_THREE", "TEST_TWO"],
                "NOT id = 'TEST_ONE'",
            ),
        ]
        for name, cql2_json, ids, where in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids, where)


# ===================================================================
# A.2 – Advanced Comparison Operators
# ===================================================================


class TestAdvancedComparison(CQL2TestBase):
    """Operators: like, between, in."""

    def test_advanced_operators(self):
        cases = [
            (
                "like",
                {"op": "like", "args": [{"property": "id"}, "TEST_T%"]},
                ["TEST_THREE", "TEST_TWO"],
                "id LIKE 'TEST_T%'",
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
                ["TEST_THREE", "TEST_TWO"],
                "datetime BETWEEN '2021-01-01T00:00:00Z' AND '2022-12-31T23:59:59Z'",
            ),
            (
                "in",
                {
                    "op": "in",
                    "args": [
                        {"property": "id"},
                        ["TEST_ONE", "TEST_TWO"],
                    ],
                },
                ["TEST_ONE", "TEST_TWO"],
                "id IN ('TEST_ONE', 'TEST_TWO')",
            ),
        ]
        for name, cql2_json, ids, where in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids, where)


# ===================================================================
# A.5 – Case-insensitive Comparison
# ===================================================================


class TestCaseInsensitive(CQL2TestBase):
    """Function: casei() wrapping property and/or literal operands."""

    def test_casei(self):
        """Different case variations must yield identical results."""
        cases = [
            (
                "eq_lower",
                _casei_cmp("=", "id", "test_one"),
                ["TEST_ONE"],
                "lower(id) = lower('test_one')",
            ),
            (
                "eq_upper",
                _casei_cmp("=", "id", "TEST_ONE"),
                ["TEST_ONE"],
                "lower(id) = lower('TEST_ONE')",
            ),
            (
                "eq_mixed",
                _casei_cmp("=", "id", "Test_One"),
                ["TEST_ONE"],
                "lower(id) = lower('Test_One')",
            ),
            (
                "like_lower",
                _casei_cmp("like", "id", "test_t%"),
                ["TEST_THREE", "TEST_TWO"],
                "lower(id) LIKE lower('test_t%')",
            ),
            (
                "like_upper",
                _casei_cmp("like", "id", "TEST_T%"),
                ["TEST_THREE", "TEST_TWO"],
                "lower(id) LIKE lower('TEST_T%')",
            ),
        ]
        for name, cql2_json, ids, where in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids, where)


# ===================================================================
# A.6 – Accent-insensitive Comparison
# ===================================================================


class TestAccentInsensitive(CQL2TestBase):
    """Function: accenti() wrapping property and/or literal operands."""

    collections = SAMPLE_COLLECTIONS + [ACCENT_COLLECTION]

    def test_accenti(self):
        """Accented and unaccented forms must match."""
        cases = [
            (
                "eq_no_accents",
                _accenti_cmp("=", "description", "Region de Chisinau"),
                ["TEST_ACCENT"],
                "strip_accents(json_extract(content, '$.description'))"
                " = strip_accents('Region de Chisinau')",
            ),
            (
                "eq_with_accents",
                _accenti_cmp("=", "description", "Région de Chișinău"),
                ["TEST_ACCENT"],
                "strip_accents(json_extract(content, '$.description'))"
                " = strip_accents('Région de Chișinău')",
            ),
            (
                "like_no_accents",
                _accenti_cmp("like", "description", "Region%"),
                ["TEST_ACCENT"],
                "strip_accents(json_extract(content, '$.description'))"
                " LIKE strip_accents('Region%')",
            ),
            (
                "like_with_accents",
                _accenti_cmp("like", "description", "Région%"),
                ["TEST_ACCENT"],
                "strip_accents(json_extract(content, '$.description'))"
                " LIKE strip_accents('Région%')",
            ),
        ]
        for name, cql2_json, ids, where in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids, where)


# ===================================================================
# A.7 – Basic Spatial Functions  (s_intersects with points & bboxes)
# ===================================================================


class TestBasicSpatial(CQL2TestBase):
    """s_intersects only, restricted to Point and bbox literals."""

    def test_s_intersects(self):
        cases = [
            (
                "point",
                _spatial("s_intersects", {"type": "Point", "coordinates": [5.0, 5.0]}),
                ["TEST_ONE"],
            ),
            (
                "bbox",
                _spatial("s_intersects", {"bbox": [5.0, 5.0, 25.0, 25.0]}),
                ["TEST_ONE", "TEST_TWO"],
            ),
        ]
        for name, cql2_json, ids in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids)


# ===================================================================
# A.8 / A.9 – Extended Spatial Literals & Spatial Functions
# ===================================================================


class TestSpatialFunctions(CQL2TestBase):
    """Full spatial predicate set with arbitrary geometry types.

    Covers basic-spatial-functions-plus (A.8) and spatial-functions (A.9).
    """

    def test_spatial_predicates(self):
        # fmt: off
        cases = [
            # s_intersects with Polygon
            ("s_intersects",
             _spatial("s_intersects", {
                 "type": "Polygon",
                 "coordinates": [[[5, 5], [15, 5], [15, 15], [5, 15], [5, 5]]],
             }),
             ["TEST_ONE"]),

            # s_equals – polygon matching TEST_ONE bbox exactly
            ("s_equals",
             _spatial("s_equals", {
                 "type": "Polygon",
                 "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
             }),
             ["TEST_ONE"]),

            # s_disjoint – far-away polygon => all collections
            ("s_disjoint",
             _spatial("s_disjoint", {
                 "type": "Polygon",
                 "coordinates": [[[100, 100], [110, 100], [110, 110],
                                  [100, 110], [100, 100]]],
             }),
             ALL_IDS),

            # s_within – large bbox containing everything
            ("s_within",
             _spatial("s_within", {
                 "type": "Polygon",
                 "coordinates": [[[-10, -10], [60, -10], [60, 60],
                                  [-10, 60], [-10, -10]]],
             }),
             ALL_IDS),

            # s_contains – collection bbox containing a point
            ("s_contains",
             _spatial("s_contains", {
                 "type": "Point", "coordinates": [5.0, 5.0],
             }),
             ["TEST_ONE"]),

            # s_overlaps – partial overlap with two collections
            ("s_overlaps",
             _spatial("s_overlaps", {
                 "type": "Polygon",
                 "coordinates": [[[5, 5], [25, 5], [25, 25], [5, 25], [5, 5]]],
             }),
             ["TEST_ONE", "TEST_TWO"]),

            # s_touches – adjacent polygon sharing edge with TEST_ONE
            ("s_touches",
             _spatial("s_touches", {
                 "type": "Polygon",
                 "coordinates": [[[10, 0], [20, 0], [20, 10], [10, 10], [10, 0]]],
             }),
             ["TEST_ONE"]),

            # s_crosses – line crossing through TEST_ONE
            ("s_crosses",
             _spatial("s_crosses", {
                 "type": "LineString",
                 "coordinates": [[5.0, -5.0], [5.0, 15.0]],
             }),
             ["TEST_ONE"]),
        ]
        # fmt: on
        for name, cql2_json, ids in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids)


# ===================================================================
# A.10 – Property-Property Comparisons
# ===================================================================


class TestPropertyProperty(CQL2TestBase):
    """Both sides of a comparison may be property references."""

    def test_property_comparisons(self):
        cases = [
            (
                "base_eq",
                _prop_prop("=", "datetime", "end_datetime"),
                [],
                "datetime = end_datetime",
            ),
            (
                "base_neq",
                _prop_prop("<>", "datetime", "end_datetime"),
                ALL_IDS,
                "datetime <> end_datetime",
            ),
            (
                "base_lt",
                _prop_prop("<", "datetime", "end_datetime"),
                ALL_IDS,
                "datetime < end_datetime",
            ),
            (
                "base_vs_json",
                _prop_prop("<>", "id", "license"),
                ALL_IDS,
                "id <> json_extract(content, '$.license')",
            ),
        ]
        for name, cql2_json, ids, where in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids, where)


# ===================================================================
# A.11 – Temporal Functions
# ===================================================================


class TestTemporalFunctions(CQL2TestBase):
    """All 15 temporal comparison operators per CQL2 spec (Allen interval algebra).

    Collections:
      - TEST_ONE:   datetime = 2020-01-01
      - TEST_TWO:   datetime = 2021-01-01
      - TEST_THREE: datetime = 2022-01-01

    Many Allen relations are trivially empty when comparing an instant property
    against an instant or a short interval – that is expected.
    """

    def test_temporal_with_timestamp(self):
        """All 15 operators with a timestamp literal (instant vs instant)."""
        ts = "2021-01-01T00:00:00Z"
        # fmt: off
        cases = [
            # Meaningful results
            ("t_after", _temporal("t_after", "datetime", ts),
             ["TEST_THREE"]),
            ("t_before", _temporal("t_before", "datetime", ts),
             ["TEST_ONE"]),
            ("t_equals", _temporal("t_equals", "datetime", ts),
             ["TEST_TWO"]),
            ("t_meets", _temporal("t_meets", "datetime", ts),
             ["TEST_TWO"]),
            ("t_metby", _temporal("t_metby", "datetime", ts),
             ["TEST_TWO"]),
            ("t_intersects", _temporal("t_intersects", "datetime", ts),
             ["TEST_TWO"]),
            ("t_disjoint", _temporal("t_disjoint", "datetime", ts),
             ["TEST_ONE", "TEST_THREE"]),
            # Always empty for instant-vs-instant (contradictory conditions)
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

    def test_temporal_with_interval(self):
        """All 15 operators with an interval literal (instant vs interval)."""
        iv = ["2020-06-01T00:00:00Z", "2021-06-01T00:00:00Z"]
        # fmt: off
        cases = [
            # Meaningful results
            ("t_after", _temporal("t_after", "datetime", iv),
             ["TEST_THREE"]),
            ("t_before", _temporal("t_before", "datetime", iv),
             ["TEST_ONE"]),
            ("t_during", _temporal("t_during", "datetime", iv),
             ["TEST_TWO"]),
            ("t_intersects", _temporal("t_intersects", "datetime", iv),
             ["TEST_TWO"]),
            ("t_disjoint", _temporal("t_disjoint", "datetime", iv),
             ["TEST_ONE", "TEST_THREE"]),
            ("t_overlaps", _temporal("t_overlaps", "datetime", iv),
             ["TEST_TWO"]),
            # Empty (instant can't contain/equal/start/finish an interval, etc.)
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


# ===================================================================
# A.12 – Array Functions
# ===================================================================


ARRAY_COLLECTIONS = [
    {
        "type": "Collection",
        "id": "TAG_AB",
        "tags": ["earth", "observation"],
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
    {
        "type": "Collection",
        "id": "TAG_BC",
        "tags": ["ml", "observation"],
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
    {
        "type": "Collection",
        "id": "TAG_A",
        "tags": ["earth"],
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
]


def _array_op(op: str, prop: str, values: list):
    return {"op": op, "args": [{"property": prop}, values]}


class TestArrayFunctions(CQL2TestBase):
    """Array comparison operators: a_contains, a_containedby, a_equals, a_overlaps."""

    collections = ARRAY_COLLECTIONS

    def test_array_operators(self):
        cases = [
            # a_contains: tags ⊇ literal
            (
                "a_contains_both",
                _array_op("a_contains", "tags", ["earth", "observation"]),
                ["TAG_AB"],
            ),
            (
                "a_contains_single",
                _array_op("a_contains", "tags", ["observation"]),
                ["TAG_AB", "TAG_BC"],
            ),
            # a_containedby: tags ⊆ literal
            (
                "a_containedby",
                _array_op("a_containedby", "tags", ["earth", "observation", "ml"]),
                ["TAG_A", "TAG_AB", "TAG_BC"],
            ),
            # a_equals: tags = literal (as sets)
            ("a_equals", _array_op("a_equals", "tags", ["earth"]), ["TAG_A"]),
            (
                "a_equals_two",
                _array_op("a_equals", "tags", ["earth", "observation"]),
                ["TAG_AB"],
            ),
            # a_overlaps: tags ∩ literal ≠ ∅
            ("a_overlaps_ml", _array_op("a_overlaps", "tags", ["ml"]), ["TAG_BC"]),
            (
                "a_overlaps_earth",
                _array_op("a_overlaps", "tags", ["earth", "ml"]),
                ["TAG_A", "TAG_AB", "TAG_BC"],
            ),
        ]
        for name, cql2_json, ids in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, ids)


# ===================================================================
# A.13 – Arithmetic  (conf/arithmetic)
# ===================================================================


ARITHMETIC_COLLECTIONS = [
    {
        "type": "Collection",
        "id": "NUM_A",
        "count": 10,
        "score": 3.5,
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
    {
        "type": "Collection",
        "id": "NUM_B",
        "count": 5,
        "score": 2.0,
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
    {
        "type": "Collection",
        "id": "NUM_C",
        "count": 3,
        "score": 9.0,
        "extent": {
            "spatial": {"bbox": [[0, 0, 1, 1]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
    },
]


def _arith(arith_op: str, prop: str, operand, cmp_op: str, value):
    """Arithmetic expression inside a comparison: (prop arith_op operand) cmp_op value."""
    return {
        "op": cmp_op,
        "args": [
            {"op": arith_op, "args": [{"property": prop}, operand]},
            value,
        ],
    }


class TestArithmetic(CQL2TestBase):
    """Arithmetic operators: +, -, *, /, %, ^, div."""

    collections = ARITHMETIC_COLLECTIONS

    def test_arithmetic_operators(self):
        cases = [
            # count + 1 = 6  → NUM_B (5+1=6)
            ("+", _arith("+", "count", 1, "=", 6), ["NUM_B"]),
            # count - 2 = 3  → NUM_B (5-2=3)
            ("-", _arith("-", "count", 2, "=", 3), ["NUM_B"]),
            # count * 2 > 15 → NUM_A (10*2=20)
            ("*", _arith("*", "count", 2, ">", 15), ["NUM_A"]),
            # count / 2 < 3  → NUM_B (5/2=2.5), NUM_C (3/2=1.5)
            ("/", _arith("/", "count", 2, "<", 3), ["NUM_B", "NUM_C"]),
            # count % 3 = 1  → NUM_A (10%3=1)
            ("%", _arith("%", "count", 3, "=", 1), ["NUM_A"]),
            # score ^ 2 = 4  → NUM_B (2.0^2=4.0)
            ("^", _arith("^", "score", 2, "=", 4), ["NUM_B"]),
            # div(count, 3) = 3 → NUM_A (10//3=3)
            ("div", _arith("div", "count", 3, "=", 3), ["NUM_A"]),
        ]
        for name, cql2_json, expected_ids in cases:
            with self.subTest(name):
                self.assert_filter(cql2_json, expected_ids)


# ===================================================================
# Unsupported conformance classes
# ===================================================================


class TestUnsupported(CQL2TestBase):
    """Operators from unsupported classes must raise NotImplementedError."""

    def test_unsupported_operators(self):
        cases = [
            # 'functions' conformance class – custom function call
            (
                "functions",
                {
                    "op": "=",
                    "args": [{"op": "upper", "args": [{"property": "id"}]}, "X"],
                },
            ),
        ]
        for name, cql2_json in cases:
            with self.subTest(name):
                with self.assertRaises(NotImplementedError) as ctx:
                    cql2_json_to_sql(cql2_json)
                self.assertIn("Unsupported CQL2 operators", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
