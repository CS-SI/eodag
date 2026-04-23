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

from eodag.databases.base import (
    BASE_COLLECTION_TABLE_COLUMNS,
    extract_properties,
    validate_supported_ops,
)


def _replace_properties(sql: str, properties: set[str]) -> str:
    """Rewrite property references in the SQL to json_extract(content, '$.property')."""
    result = sql
    for prop in sorted(properties, key=len, reverse=True):
        if value := BASE_COLLECTION_TABLE_COLUMNS.get(prop):
            prop_expr = value
            quoted = f'"{value}"'
        else:
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

# Spatial function patterns for R-tree pre-filtering.
# Excludes st_disjoint (bbox overlap doesn't imply geometry non-disjointness).
_RE_SPATIAL_GEOJSON = re.compile(
    r"(st_(?!disjoint)\w+)\(geometry,\s*st_geomfromgeojson\('([^']*)'\)\)",
    re.IGNORECASE,
)
_RE_SPATIAL_ENVELOPE = re.compile(
    r"(st_(?!disjoint)\w+)\(geometry,\s*st_makeenvelope\(([^)]*)\)\)",
    re.IGNORECASE,
)


def _geojson_bounds(geojson_str: str) -> tuple[float, float, float, float] | None:
    """Extract (minx, miny, maxx, maxy) from a GeoJSON literal string."""
    try:
        geojson = orjson.loads(geojson_str)
    except Exception:
        return None
    bbox = geojson.get("bbox")
    if bbox and len(bbox) >= 4:
        return (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
    coords = geojson.get("coordinates")
    if coords is None:
        return None
    points: list[tuple[float, float]] = []

    def _flatten(item: Any) -> None:
        if isinstance(item, list) and item and isinstance(item[0], (int, float)):
            points.append((float(item[0]), float(item[1])))
        elif isinstance(item, list):
            for sub in item:
                _flatten(sub)

    _flatten(coords)
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))  # minx, miny, maxx, maxy


def _rtree_filter(minx: float, miny: float, maxx: float, maxy: float) -> str:
    """Build an R-tree sub-query filter for bbox intersection."""
    return (
        f"key IN (SELECT id FROM collections_rtree WHERE "
        f"minx <= {maxx} AND maxx >= {minx} AND miny <= {maxy} AND maxy >= {miny})"
    )


def _sqlite_compat(sql: str) -> str:
    """Apply SQLite-specific rewrites to the SQL emitted by cql2."""
    # TODO: check to refactor
    # TODO: also verify probably no need of JSONB special operators
    result = sql

    # cql2 emits Postgres CAST('...' AS TIMESTAMP WITH TIME ZONE); strip for SQLite.
    result = _RE_CAST_TIMESTAMP.sub(r"'\1'", result)

    # cql2 emits Postgres form: x = SOME(ARRAY['a', 'b'])
    result = _RE_SOME_ARRAY.sub(r"\1 IN (\2)", result)

    # ---- Array operators ----------------------------------------------------
    # Guard must look for REAL operators (after html.unescape above).
    if any(tok in result for tok in ("@>", "<@", "@@", "&&", "ARRAY[")):
        # IMPORTANT: LHS can be:
        # - a function call: json_extract(...)
        # - an identifier: federation_backends
        # - a qualified identifier: c.federation_backends
        # - a quoted identifier: "federation:backends"
        #
        # So we widen the LHS expression matcher here to include "...." identifiers.
        _LHS = r"(?:" r'"[^"]+"' r"|(?:\w+\.)?\w+" r"|\w+\([^)]*\)" r")"

        _SCALAR_STR = (
            r"'(?:[^']|'')*'"  # SQL single-quoted literal (handles doubled quotes)
        )

        # One regex per operator; RHS supports ARRAY[...] or scalar.
        _RE_OP_MIXED = {
            "@@": re.compile(rf"({_LHS})\s*@@\s*(?:ARRAY\[([^\]]*)\]|({_SCALAR_STR}))"),
            "@>": re.compile(rf"({_LHS})\s*@>\s*(?:ARRAY\[([^\]]*)\]|({_SCALAR_STR}))"),
            "<@": re.compile(rf"({_LHS})\s*<@\s*(?:ARRAY\[([^\]]*)\]|({_SCALAR_STR}))"),
        }

        def _sub_overlaps(m: re.Match[str]) -> str:
            lhs, rhs_arr, rhs_scalar = m.group(1), m.group(2), m.group(3)
            if rhs_scalar is not None:
                # A @@ 'x'  ->  x ∈ A
                return f"EXISTS (SELECT 1 FROM json_each({lhs}) je WHERE je.value = {rhs_scalar})"
            # A @@ ARRAY[...]  ->  A ∩ B ≠ ∅
            return f"EXISTS (SELECT 1 FROM json_each({lhs}) je WHERE je.value IN ({rhs_arr}))"

        def _sub_contains(m: re.Match[str]) -> str:
            lhs, rhs_arr, rhs_scalar = m.group(1), m.group(2), m.group(3)
            if rhs_scalar is not None:
                # A @> 'x'  ->  x ∈ A
                return f"EXISTS (SELECT 1 FROM json_each({lhs}) je WHERE je.value = {rhs_scalar})"
            # A @> ARRAY[...]  ->  every element of B is in A
            return (
                f"NOT EXISTS (SELECT 1 FROM json_each(json_array({rhs_arr})) je "
                f"WHERE je.value NOT IN (SELECT je2.value FROM json_each({lhs}) je2))"
            )

        def _sub_containedby(m: re.Match[str]) -> str:
            lhs, rhs_arr, rhs_scalar = m.group(1), m.group(2), m.group(3)
            if rhs_scalar is not None:
                # A <@ 'x'  ->  A ⊆ {x} (all elements equal x)
                return (
                    f"({lhs} IS NOT NULL AND "
                    f"NOT EXISTS (SELECT 1 FROM json_each({lhs}) je WHERE je.value <> {rhs_scalar}))"
                )
            # A <@ ARRAY[...]  ->  every element of A is in B
            return (
                f"({lhs} IS NOT NULL AND "
                f"NOT EXISTS (SELECT 1 FROM json_each({lhs}) je WHERE je.value NOT IN ({rhs_arr})))"
            )

        result = _RE_OP_MIXED["@@"].sub(_sub_overlaps, result)
        result = _RE_OP_MIXED["@>"].sub(_sub_contains, result)
        result = _RE_OP_MIXED["<@"].sub(_sub_containedby, result)

        # Keep your a_equals rewrite as-is, but only if ARRAY[...] is present.
        if "ARRAY[" in result:
            result = _RE_ARRAY_EQUALS.sub(
                r"(\1 IS NOT NULL"
                r" AND NOT EXISTS (SELECT 1 FROM json_each(json_array(\2)) je"
                r" WHERE je.value NOT IN (SELECT je2.value FROM json_each(\1) je2))"
                r" AND NOT EXISTS (SELECT 1 FROM json_each(\1) je"
                r" WHERE je.value NOT IN (\2)))",
                result,
            )

    # ---- Spatial R-tree pre-filter -----------------------------------------
    def _inject_rtree_geojson(match: re.Match[str]) -> str:
        bounds = _geojson_bounds(match.group(2))
        if bounds is None:
            return match.group(0)
        return f"({_rtree_filter(*bounds)} AND {match.group(0)})"

    def _inject_rtree_envelope(match: re.Match[str]) -> str:
        parts = [p.strip() for p in match.group(2).split(",")]
        if len(parts) != 4:
            return match.group(0)
        minx, miny, maxx, maxy = parts
        return (
            f"(key IN (SELECT id FROM collections_rtree WHERE "
            f"minx <= {maxx} AND maxx >= {minx} AND miny <= {maxy} AND maxy >= {miny}) "
            f"AND {match.group(0)})"
        )

    result = _RE_SPATIAL_GEOJSON.sub(_inject_rtree_geojson, result)
    result = _RE_SPATIAL_ENVELOPE.sub(_inject_rtree_envelope, result)

    return result


def cql2_json_to_sql(cql2_json: dict[str, Any]) -> str:
    """Validate CQL2 JSON and return SQLite-compatible WHERE SQL."""

    validate_supported_ops(cql2_json)

    # First, parse the CQL2 JSON to ensure it's valid and to get the raw SQL.
    expr = cql2.parse_json(orjson.dumps(cql2_json).decode())

    raw_sql = expr.to_sql()

    # Walk the CQL2 JSON to find all property names used, so we can rewrite them to json_extract.
    properties: set[str] = set()
    extract_properties(cql2_json, properties)
    where_sql = _replace_properties(raw_sql, properties)

    # Finally, apply any SQLite-specific rewrites.
    where_sql = _sqlite_compat(where_sql)

    return where_sql
