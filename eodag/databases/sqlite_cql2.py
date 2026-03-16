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
"""CQL2 to SQLite SQL translator for EODAG's SQLite backend."""
from __future__ import annotations

import re
from typing import Any

import cql2
import orjson

BASE_COLLECTION_TABLE_COLUMNS = {
    "key",
    "id",
    "internal_id",
    "datetime",
    "end_datetime",
    "geometry",
    "content",
}

SUPPORTED_CONFORMANCE_CLASSES = (
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

UNSUPPORTED_CONFORMANCE_CLASSES = (
    "http://www.opengis.net/spec/cql2/1.0/conf/functions",
)

SUPPORTED_OPS = {
    "=",
    "<>",
    "!=",
    "<",
    "<=",
    ">",
    ">=",
    "and",
    "or",
    "not",
    "like",
    "between",
    "in",
    "isnull",
    "s_intersects",
    "s_equals",
    "s_disjoint",
    "s_within",
    "s_contains",
    "s_overlaps",
    "s_touches",
    "s_crosses",
    "t_after",
    "t_before",
    "t_contains",
    "t_disjoint",
    "t_during",
    "t_equals",
    "t_finishedby",
    "t_finishes",
    "t_intersects",
    "t_meets",
    "t_metby",
    "t_overlappedby",
    "t_overlaps",
    "t_startedby",
    "t_starts",
    "a_containedby",
    "a_contains",
    "a_equals",
    "a_overlaps",
    "casei",
    "accenti",
    "+",
    "-",
    "*",
    "/",
    "%",
    "^",
    "div",
}


def _extract_ops(node: Any, out: set[str]) -> None:
    """Walk the CQL2 JSON to find all operators used."""
    if isinstance(node, dict):
        op = node.get("op")
        if isinstance(op, str):
            out.add(op.lower())
        for value in node.values():
            _extract_ops(value, out)
    elif isinstance(node, list):
        for item in node:
            _extract_ops(item, out)


def _validate_supported_ops(cql2_json: dict[str, Any]) -> None:
    """Validate that all operators in the CQL2 JSON are supported."""
    ops: set[str] = set()
    _extract_ops(cql2_json, ops)
    unsupported_ops = sorted(op for op in ops if op not in SUPPORTED_OPS)
    if unsupported_ops:
        raise NotImplementedError(
            "Unsupported CQL2 operators: "
            f"{', '.join(unsupported_ops)}. "
            "Unsupported conformance classes include: "
            f"{', '.join(UNSUPPORTED_CONFORMANCE_CLASSES)}"
        )


def _extract_properties(node: Any, out: set[str]) -> None:
    """Walk the CQL2 JSON to find all property names used."""
    if isinstance(node, dict):
        if "property" in node and isinstance(node["property"], str):
            out.add(node["property"])
        for value in node.values():
            _extract_properties(value, out)
    elif isinstance(node, list):
        for item in node:
            _extract_properties(item, out)


def _replace_properties(sql: str, properties: set[str]) -> str:
    """Rewrite property references in the SQL to json_extract(content, '$.property')."""
    result = sql
    for prop in sorted(properties, key=len, reverse=True):
        if prop in BASE_COLLECTION_TABLE_COLUMNS:
            continue

        prop_expr = f"json_extract(content, '$.{prop}')"
        quoted = f'"{prop}"'

        if quoted in result:
            # CQL2 quotes properties that contain special characters (e.g. ':').
            # Replace the quoted form and skip the bare-identifier regex to avoid
            # double-wrapping the property inside the already-inserted json_extract.
            result = result.replace(quoted, prop_expr)
        else:
            # Handle bare identifiers with word boundaries (to avoid partial matches)
            result = re.sub(rf"\b{re.escape(prop)}\b", prop_expr, result)

    return result


# Pre-compiled patterns for _sqlite_compat.
# LHS of Postgres array operators is always a SQL identifier or a function call
# like json_extract(content, '$.prop'). We use (?:\w+\([^)]*\)|\w+) to match
# either form without backtracking across AND/OR boundaries.
_SQL_EXPR = r"(?:\w+\([^)]*\)|\w+)"

_RE_CAST_TIMESTAMP = re.compile(
    r"CAST\('([^']+)'\s+AS\s+TIMESTAMP\s+WITH\s+TIME\s+ZONE\)",
    re.IGNORECASE,
)
_RE_SOME_ARRAY = re.compile(
    r"(\S+)\s*=\s*SOME\s*\(\s*ARRAY\[([^\]]*)\]\s*\)",
    re.IGNORECASE,
)
_RE_ARRAY_OPS = {
    "@@": re.compile(rf"({_SQL_EXPR})\s*@@\s*ARRAY\[([^\]]*)\]"),
    "@>": re.compile(rf"({_SQL_EXPR})\s*@>\s*ARRAY\[([^\]]*)\]"),
    "<@": re.compile(rf"({_SQL_EXPR})\s*<@\s*ARRAY\[([^\]]*)\]"),
}
_RE_ARRAY_EQUALS = re.compile(rf"({_SQL_EXPR})\s*=\s*ARRAY\[([^\]]*)\]")


def _sqlite_compat(sql: str) -> str:
    """Apply SQLite-specific rewrites to the SQL emitted by cql2."""
    result = sql

    # cql2 emits Postgres CAST('...' AS TIMESTAMP WITH TIME ZONE); strip for SQLite.
    result = _RE_CAST_TIMESTAMP.sub(r"'\1'", result)

    # cql2 emits Postgres form: x = SOME(ARRAY['a', 'b'])
    result = _RE_SOME_ARRAY.sub(r"\1 IN (\2)", result)

    # cql2 emits Postgres array operators (@>, <@, @@, = ARRAY[...]).
    # Rewrite to custom SQLite functions that compare JSON arrays.
    # Skip entirely if no ARRAY[ remains after SOME rewriting (avoids catastrophic backtracking).
    if "ARRAY[" in result:
        for pg_op, (func_name, pattern) in {
            "@@": ("a_overlaps", _RE_ARRAY_OPS["@@"]),
            "@>": ("a_contains", _RE_ARRAY_OPS["@>"]),
            "<@": ("a_containedby", _RE_ARRAY_OPS["<@"]),
        }.items():
            result = pattern.sub(rf"{func_name}(\1, json_array(\2))", result)

        # a_equals: prop = ARRAY[...] → a_equals(prop, json_array(...))
        result = _RE_ARRAY_EQUALS.sub(r"a_equals(\1, json_array(\2))", result)

    return result


def cql2_json_to_sql(cql2_json: dict[str, Any]) -> str:
    """Validate CQL2 JSON and return SQLite-compatible WHERE SQL."""

    _validate_supported_ops(cql2_json)

    # First, parse the CQL2 JSON to ensure it's valid and to get the raw SQL.
    expr = cql2.parse_json(orjson.dumps(cql2_json).decode())

    raw_sql = expr.to_sql()

    # Walk the CQL2 JSON to find all property names used, so we can rewrite them to json_extract.
    properties: set[str] = set()
    _extract_properties(cql2_json, properties)
    where_sql = _replace_properties(raw_sql, properties)

    # Finally, apply any SQLite-specific rewrites.
    where_sql = _sqlite_compat(where_sql)

    return where_sql
