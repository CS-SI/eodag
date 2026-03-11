import json
import re
import sqlite3
from typing import Any

import cql2

JsonObject = dict[str, Any]

BASE_COLUMNS = {"key", "id", "datetime", "end_datetime", "geometry", "content"}

SUPPORTED_CONFORMANCE_CLASSES = (
    "http://www.opengis.net/spec/cql2/1.0/conf/basic-cql2",
    "http://www.opengis.net/spec/cql2/1.0/conf/advanced-comparison-operators",
    "http://www.opengis.net/spec/cql2/1.0/conf/case-insensitive-comparison",
    "http://www.opengis.net/spec/cql2/1.0/conf/accent-insensitive-comparison",
    "http://www.opengis.net/spec/cql2/1.0/conf/basic-spatial-functions",
    "http://www.opengis.net/spec/cql2/1.0/conf/basic-spatial-functions-plus",
)

UNSUPPORTED_CONFORMANCE_CLASSES = (
    "http://www.opengis.net/spec/cql2/1.0/conf/spatial-functions",
    "http://www.opengis.net/spec/cql2/1.0/conf/temporal-functions",
    "http://www.opengis.net/spec/cql2/1.0/conf/array-functions",
    "http://www.opengis.net/spec/cql2/1.0/conf/property-property",
    "http://www.opengis.net/spec/cql2/1.0/conf/functions",
    "http://www.opengis.net/spec/cql2/1.0/conf/arithmetic",
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
    "ilike",
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


def _validate_supported_ops(cql2_json: JsonObject) -> None:
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
    if isinstance(node, dict):
        if "property" in node and isinstance(node["property"], str):
            out.add(node["property"])
        for value in node.values():
            _extract_properties(value, out)
    elif isinstance(node, list):
        for item in node:
            _extract_properties(item, out)


def _replace_properties(sql: str, properties: set[str]) -> str:
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
    result = sql

    # cql2 emits PostGIS-like function names; rewrite for SpatiaLite.
    result = re.sub(r"\bst_intersects\s*\(", "Intersects(", result, flags=re.IGNORECASE)
    result = re.sub(r"\bst_equals\s*\(", "Equals(", result, flags=re.IGNORECASE)
    result = re.sub(r"\bst_disjoint\s*\(", "Disjoint(", result, flags=re.IGNORECASE)
    result = re.sub(r"\bst_within\s*\(", "Within(", result, flags=re.IGNORECASE)
    result = re.sub(r"\bst_contains\s*\(", "Contains(", result, flags=re.IGNORECASE)
    result = re.sub(r"\bst_overlaps\s*\(", "Overlaps(", result, flags=re.IGNORECASE)
    result = re.sub(r"\bst_touches\s*\(", "Touches(", result, flags=re.IGNORECASE)
    result = re.sub(r"\bst_crosses\s*\(", "Crosses(", result, flags=re.IGNORECASE)

    result = re.sub(
        r"\bst_geomfromgeojson\s*\(",
        "GeomFromGeoJSON(",
        result,
        flags=re.IGNORECASE,
    )

    # cql2 emits ilike(id, 'x%') as a function call.
    result = re.sub(
        r'"?ilike"?\s*\(\s*([^,]+?)\s*,\s*([^\)]+?)\s*\)',
        r"LOWER(\1) LIKE LOWER(\2)",
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

    return result


def cql2_json_to_sql(cql2_json: JsonObject) -> str:
    """Validate CQL2 JSON and return SQLite-compatible WHERE SQL."""

    _validate_supported_ops(cql2_json)

    # First, parse the CQL2 JSON to ensure it's valid and to get the raw SQL.
    expr = cql2.parse_json(json.dumps(cql2_json))

    raw_sql = expr.to_sql()

    # Walk the CQL2 JSON to find all property names used, so we can rewrite them to json_extract.
    properties: set[str] = set()
    _extract_properties(cql2_json, properties)
    where_sql = _replace_properties(raw_sql, properties)

    # Finally, apply any SQLite-specific rewrites.
    where_sql = _sqlite_compat(where_sql)

    return where_sql


def execute_cql2_json(
    conn: sqlite3.Connection,
    cql2_json: JsonObject,
    limit: int | None = 100,
) -> tuple[list[dict[str, Any]], str]:
    """Execute a CQL2 JSON filter against collections and return rows + SQL."""
    where_sql = cql2_json_to_sql(cql2_json)

    sql = (
        "SELECT key, id, datetime, end_datetime, AsGeoJSON(geometry) AS geometry_geojson "
        "FROM collections "
        f"WHERE {where_sql} "
        "ORDER BY key"
    )
    if limit is not None:
        sql += f" LIMIT {int(limit)}"

    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()

    columns = [desc[0] for desc in cur.description]
    records = [dict(zip(columns, row)) for row in rows]
    for record in records:
        if record.get("geometry_geojson"):
            record["geometry_geojson"] = json.loads(record["geometry_geojson"])

    return records, sql
