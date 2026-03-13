from __future__ import annotations

import re
from typing import Any

import cql2
import orjson

BASE_COLUMNS = {"key", "id", "datetime", "end_datetime", "geometry", "content"}

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
    """Walk the CQL2 JSON to find all property names used, so we can rewrite them to json_extract."""
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
        if prop in BASE_COLUMNS:
            continue

        prop_expr = f"json_extract(content, '$.{prop}')"
        quoted = f'"{prop}"'
        result = result.replace(quoted, prop_expr)

        # Also handle bare identifiers with word boundaries (to avoid partial matches)
        result = re.sub(rf"\b{re.escape(prop)}\b", prop_expr, result)

    return result


def _sqlite_compat(sql: str) -> str:
    """Apply SQLite-specific rewrites to the SQL emitted by cql2."""
    result = sql

    # cql2 emits Postgres CAST('...' AS TIMESTAMP WITH TIME ZONE); strip for SQLite.
    result = re.sub(
        r"CAST\('([^']+)'\s+AS\s+TIMESTAMP\s+WITH\s+TIME\s+ZONE\)",
        r"'\1'",
        result,
        flags=re.IGNORECASE,
    )

    # cql2 emits Postgres form: x = SOME(ARRAY['a', 'b'])
    result = re.sub(
        r"([^\s\(][^=]*?)\s*=\s*SOME\s*\(\s*ARRAY\[(.*?)\]\s*\)",
        r"\1 IN (\2)",
        result,
        flags=re.IGNORECASE,
    )

    # cql2 emits Postgres array operators (@>, <@, @@, = ARRAY[...]).
    # Rewrite to custom SQLite functions that compare JSON arrays.
    # Process @@ before @> to avoid partial matches.
    for pg_op, func_name in [
        ("@@", "a_overlaps"),
        ("@>", "a_contains"),
        ("<@", "a_containedby"),
    ]:
        result = re.sub(
            rf"(.+?)\s*{re.escape(pg_op)}\s*ARRAY\[(.*?)\]",
            rf"{func_name}(\1, json_array(\2))",
            result,
        )

    # a_equals: prop = ARRAY[...] → a_equals(prop, json_array(...))
    result = re.sub(
        r"(.+?)\s*=\s*ARRAY\[(.*?)\]",
        r"a_equals(\1, json_array(\2))",
        result,
    )

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
