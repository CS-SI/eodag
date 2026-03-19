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

import logging
import sqlite3
import unicodedata
from collections.abc import Callable
from sqlite3 import Connection
from typing import TYPE_CHECKING, Any, Optional, Union, cast

import cql2
import orjson
import shapely
from shapely.geometry import shape

from eodag.api.collection import Collection, CollectionsDict
from eodag.databases.base import Database
from eodag.databases.sqlite_cql2 import cql2_json_to_sql
from eodag.databases.sqlite_fts import stac_q_to_fts5
from eodag.utils import get_geometry_from_various
from eodag.utils.dates import get_datetime

if TYPE_CHECKING:
    from collections.abc import Iterable
    from sqlite3 import Cursor, _Parameters

    from shapely.geometry.base import BaseGeometry

    from eodag.config import CollectionProviderConfig, FederationBackendConfig

logger = logging.getLogger("eodag.databases.sqlite_database")

# Runtime JSONB support detection (jsonb introduced in SQLite 3.45.0)
_SQLITE_VERSION = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
_HAS_JSONB = _SQLITE_VERSION >= (3, 45, 0)

if not _HAS_JSONB:
    logger.info(
        "SQLite %s does not support JSONB; falling back to text JSON (slower).",
        sqlite3.sqlite_version,
    )

# Conditional SQL fragments
_JSON_STORE = "jsonb(?)" if _HAS_JSONB else "json(?)"
_JSON_EXTRACT = "jsonb_extract" if _HAS_JSONB else "json_extract"
_CONTENT_TYPE = "JSONB" if _HAS_JSONB else "TEXT"
_JSON_VALID_CHECK = "json_valid(content, 4)" if _HAS_JSONB else "json_valid(content)"

# SQLite has a compile-time variable limit (often 999).
# Keep headroom when building batched parameterised queries.
_SQLITE_VAR_CHUNK = 500


def _chunks(seq: list[str], size: int) -> Iterable[list[str]]:
    """Yield successive *size*-length slices from *seq*."""
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


class SQLiteDatabase(Database):
    """Class representing a SQLite database."""

    _con: Connection

    def __init__(self, db_path: str) -> None:
        """Initialize database by creating a connection and preparing the database."""
        self._con = sqlite3.connect(
            database=db_path,
            detect_types=sqlite3.PARSE_COLNAMES,
            check_same_thread=True,
        )
        self._con.row_factory = sqlite3.Row

        # register adapters and converters
        sqlite3.register_adapter(Collection, _adapt_collection)
        # set the key "collection_dict" to convert SQLite bytes values to a dictionary
        sqlite3.register_converter("collection_dict", _convert_collection)

        sqlite3.register_adapter(dict, _adapt_dict)
        # set the key "dict" to convert SQLite bytes values to a dictionary
        sqlite3.register_converter("dict", _convert_dict)

        register_custom_functions(self._con)

        create_collections_table(self._con)
        create_collections_federation_backends_table(self._con)
        create_federation_backends_table(self._con)

    def close(self) -> None:
        """Close the connection to the database."""
        if self._con:
            self._con.close()
            self._con = None

    def _execute(self, sql: str, parameters: Optional[_Parameters] = None) -> Cursor:
        """
        Return the cursor from a SQLite query ``execute()`` and rollback the connection if the query failed

        :param sql: A single SQL statement
        :param parameters: Python values to bind to placeholders in ``sql``

        :raises: :class:`~sqlite3.DatabaseError`
        """
        try:
            if parameters is None:
                return self._con.execute(sql)
            else:
                return self._con.execute(sql, parameters)
        except sqlite3.DatabaseError as e:
            # rollback manually as connection parameter "isolation_level" is set to "DEFERRED"
            self._con.rollback()
            raise e

    def _executemany(self, sql: str, parameters: Iterable[_Parameters]) -> Cursor:
        """
        Return the cursor from a SQLite query ``execute_all()`` and rollback the connection if the query failed

        :param sql: A single SQL statement
        :param parameters: Python values to bind to placeholders in ``sql``

        :raises: :class:`~sqlite3.DatabaseError`
        """
        try:
            return self._con.executemany(sql, parameters)
        except sqlite3.DatabaseError as e:
            # rollback manually as connection parameter "isolation_level" is set to "DEFERRED"
            self._con.rollback()
            raise e

    def delete_collections(self, collection_ids: list[str]) -> None:
        """Remove collections and their federation backend configs from the database.

        Matches against both ``id`` and ``internal_id`` columns to handle aliases.
        """
        if not collection_ids:
            raise ValueError("collection_ids cannot be empty")

        placeholders = ", ".join("?" * len(collection_ids))
        params = tuple(collection_ids)
        match_clause = f"id IN ({placeholders}) OR internal_id IN ({placeholders})"
        # Delete federation backend configs using internal_id lookup
        # (collections_federation_backends.collection_id
        # stores the internal id, not the alias)
        self._execute(
            f"DELETE FROM collections_federation_backends WHERE collection IN "
            f"(SELECT internal_id FROM collections WHERE {match_clause})",
            params + params,
        )
        self._execute(
            f"DELETE FROM collections WHERE {match_clause}",
            params + params,
        )
        self._con.commit()

    def upsert_collections(self, collections: CollectionsDict) -> None:
        """Add or update collections in the database"""

        upserted_coll_nb = self._executemany(
            f"""
            INSERT INTO collections (content) VALUES ({_JSON_STORE})
            ON CONFLICT(internal_id) DO UPDATE SET content=excluded.content;
            """,
            [(c,) for c in collections.values()],
        ).rowcount

        self._con.commit()

        if upserted_coll_nb > 0:
            msg = f"{upserted_coll_nb} collection(s) have been updated or added to the database"
            logger.debug(msg)

    def upsert_federation_backends(
        self, fb_configs: list[FederationBackendConfig]
    ) -> None:
        """
        Add or update collection specific api or search and download
        plugins config for federation backends in the database
        """
        if not fb_configs:
            return

        cur = self._executemany(
            f"""
            INSERT INTO federation_backends (id, plugins_config, priority, metadata, enabled)
            VALUES (?, {_JSON_STORE}, ?, {_JSON_STORE}, ?)
            ON CONFLICT(id) DO UPDATE SET
                plugins_config = excluded.plugins_config,
                priority       = excluded.priority,
                metadata       = excluded.metadata,
                enabled        = excluded.enabled
            """,
            (
                (fb.name, fb.plugins_config, fb.priority, fb.metadata, fb.enabled)
                for fb in fb_configs
            ),
        )
        self._con.commit()

        if cur.rowcount > 0:
            logger.debug(
                "%s federation backend configuration(s) have been updated or added "
                "to the database",
                cur.rowcount,
            )

    def upsert_collections_federation_backends(
        self, coll_fb_configs: list[CollectionProviderConfig]
    ) -> None:
        """
        Upsert collection-specific federation backend configs, then refresh
        the denormalized ``federation_backends`` column on affected collections.
        """
        if not coll_fb_configs:
            return

        rows = [(cfg.id, cfg.provider, cfg.plugins_config) for cfg in coll_fb_configs]
        affected_ids = sorted({cid for cid, _, _ in rows})

        with self._con:
            self._executemany(
                f"""
                INSERT INTO collections_federation_backends
                    (collection_id, federation_backend_name, plugins_config)
                VALUES (?, ?, {_JSON_STORE})
                ON CONFLICT(collection_id, federation_backend_name) DO UPDATE SET
                    plugins_config = excluded.plugins_config
                """,
                rows,
            )

            for batch in _chunks(affected_ids, _SQLITE_VAR_CHUNK):
                values_clause = ", ".join(["(?)"] * len(batch))
                self._execute(
                    f"""
                    WITH affected(cid) AS (VALUES {values_clause})
                    UPDATE collections
                    SET federation_backends = (
                        SELECT COALESCE(json_group_array(fb_name), json('[]'))
                        FROM (
                            SELECT federation_backend_name AS fb_name
                            FROM collections_federation_backends
                            WHERE collection_id = collections.internal_id
                            ORDER BY federation_backend_name
                        )
                    )
                    WHERE internal_id IN (SELECT cid FROM affected)
                    """,
                    tuple(batch),
                )

        logger.debug(
            "Upserted %d collection-provider config(s); "
            "refreshed federation_backends for %d collection(s)",
            len(rows),
            len(affected_ids),
        )

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
    ) -> tuple[list[dict[str, Any]], int]:
        """Search collections matching the given parameters.

        :param sortby: STAC sort extension objects, e.g.
            ``[{"field": "datetime", "direction": "desc"}]``.
            Allowed fields: ``id``, ``datetime``, ``end_datetime``.
        :returns: A tuple of (returned collections as dictionaries, total number matched).
        """
        if cql2_text and cql2_json:
            raise ValueError("Cannot provide both cql2_text and cql2_json")

        if cql2_text:
            cql2_json = cql2.parse_text(cql2_text).to_json()

        where = _stac_search_to_where(
            geometry, datetime, ids, federation_backends, cql2_json
        )

        from_clause = "FROM collections c"
        where_parts = [where]
        params: list[Any] = []
        order_terms: list[str] = []
        select_score = ""

        if q:
            fts_expr = stac_q_to_fts5(q)
            if fts_expr:
                from_clause += " JOIN collections_fts cf ON cf.rowid = c.key"
                where_parts.append("collections_fts MATCH ?")
                params.append(fts_expr)

                # Weighted relevance: title > description > keywords
                select_score = ", bm25(collections_fts, 10.0, 3.0, 1.0) AS rank_score"
                order_terms = ["rank_score ASC"]

        if sortby:
            order_terms = _stac_sortby_to_order_by(sortby)

        order_terms.append("c.id ASC")
        order_by = " ORDER BY " + ", ".join(order_terms)

        full_where = " AND ".join(where_parts)

        # Total matches (before limit)
        count_row = self._execute(
            f"SELECT COUNT(*) {from_clause} WHERE {full_where}",
            tuple(params) or None,
        ).fetchone()
        number_matched = cast(int, count_row[0]) if count_row else 0

        sql = (
            f'SELECT json(c.content) AS "c.content [collection_dict]"{select_score} '
            f"{from_clause} WHERE {full_where}{order_by}"
        )
        if limit is not None:
            sql += f" LIMIT {limit}"

        collections_list: list[dict[str, Any]] = [
            row["c.content"]
            for row in self._execute(sql, tuple(params) or None).fetchall()
        ]

        return collections_list, number_matched

    def get_collections(self, federation_backend_name: str) -> list[str]:
        """
        Get the list of collections of the given federation backend from the database
        """
        sql = "SELECT collection_id FROM collections_federation_backends WHERE federation_backend_name = ?;"

        collections: list[str] = [
            row["collection_id"]
            for row in self._execute(sql, (federation_backend_name,)).fetchall()
        ]

        return collections

    def get_federation_backends(
        self, federation_backend_ids: Optional[list[str]] = None
    ) -> dict[str, dict[str, Any]]:
        """
        Get federation backends from the database
        """
        where: str = ""
        params: list[str] = []

        if federation_backend_ids:
            fb_placeholders = ", ".join("?" * len(federation_backend_ids))
            where = f" WHERE id IN ({fb_placeholders})"
            params = federation_backend_ids

        sql = (
            'SELECT id, json(plugins_config) AS "plugins_config [dict]", '
            'priority, json(metadata) AS "metadata [dict]", enabled '
            f"FROM federation_backends{where};"
        )

        fb_configs: dict[str, dict[str, dict[str, Any]]] = {}
        for row in self._execute(sql, tuple(params) or None).fetchall():
            fb_id = row["id"]
            fb_configs[fb_id] = {
                "plugins_config": row["plugins_config"],
                "priority": row["priority"],
                "metadata": row["metadata"],
                "enabled": row["enabled"],
            }

        return fb_configs

    def get_collection_federation_backends(
        self, collection: str, federation_backend_ids: Optional[list[str]] = None
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """
        Get collection specific api or search and download
        plugins config for federation backends from the database
        """
        where_parts: list[str] = ["collection_id = ?"]
        params: list[str] = [collection]

        if federation_backend_ids:
            fb_placeholders = ", ".join("?" * len(federation_backend_ids))
            where_parts.append(f"federation_backend_name IN ({fb_placeholders})")
            params.extend(federation_backend_ids)

        full_where = " AND ".join(where_parts)

        sql = (
            'SELECT federation_backend_name, json(plugins_config) AS "plugins_config [dict]" '
            f"FROM collections_federation_backends WHERE {full_where}"
        )

        coll_fb_configs: dict[str, dict[str, dict[str, Any]]] = {}
        for row in self._execute(sql, tuple(params)).fetchall():
            fb_id = row["federation_backend_name"]
            coll_fb_configs[fb_id] = row["plugins_config"]

        return coll_fb_configs


def _adapt_collection(collection: Collection) -> str:
    """An adapter to automatically convert from a ``Collection`` instance
    to an SQLite-compatible type (here a string) when injected to queries"""
    data = collection.model_dump(mode="json")
    data["_id"] = collection._id
    return orjson.dumps(data).decode()


def _convert_collection(coll_bytes: bytes) -> dict[str, Any]:
    """A converter to convert from SQLite bytes values of a collection json string to a
    dictionary of this collection when called in queries by its key wrapped in square brackets.
    Its key is set during its registration.

    Remaps ``_id`` (internal id) back to ``id`` so that
    ``Collection(**data)`` reconstructs correctly via ``model_post_init``
    and ``set_id_from_alias``.
    """
    data = orjson.loads(coll_bytes)
    if "_id" in data:
        data["id"] = data.pop("_id")
    return data


def _adapt_dict(data: dict[str, Any]) -> str:
    """An adapter to automatically convert from a dictionary to an
    SQLite-compatible type (here a string) when injected to queries"""
    return orjson.dumps(data).decode()


def _convert_dict(dict_bytes: bytes) -> dict[str, Any]:
    """A converter to convert from SQLite bytes values of a json string to
    a dictionary when called in queries by its key wrapped in square brackets.
    Its key is set during its registration.
    """
    return orjson.loads(dict_bytes)


def _strip_accents(text: str | None) -> str | None:
    """Remove diacritical marks for accent-insensitive comparison (CQL2 accenti)."""
    if text is None:
        return None
    return "".join(
        c
        for c in unicodedata.normalize("NFD", str(text))
        if unicodedata.category(c) != "Mn"
    )


def _st_makeenvelope(xmin: float, ymin: float, xmax: float, ymax: float) -> str:
    """Convert bounding-box coordinates to a GeoJSON Polygon string."""
    return orjson.dumps(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [xmin, ymin],
                    [xmax, ymin],
                    [xmax, ymax],
                    [xmin, ymax],
                    [xmin, ymin],
                ]
            ],
        }
    ).decode()


def _make_spatial_func(
    method_name: str,
) -> Callable[[str | None, str | None], int | None]:
    """Create a spatial predicate function for SQLite registration."""

    def func(g1_json: str | None, g2_json: str | None) -> int | None:
        if g1_json is None or g2_json is None:
            return None
        g1 = shape(orjson.loads(g1_json))
        g2 = shape(orjson.loads(g2_json))
        return int(getattr(g1, method_name)(g2))

    return func


def register_custom_functions(con: sqlite3.Connection) -> None:
    """Register custom SQL functions needed for CQL2 evaluation in SQLite.

    This includes spatial predicates (via Shapely), array comparisons,
    accent-insensitive helpers, bounding-box conversion, and integer division.
    """
    # GeoJSON passthrough – cql2 emits st_geomfromgeojson('...')
    con.create_function("st_geomfromgeojson", 1, lambda x: x)

    # Bounding-box literal – cql2 emits st_makeenvelope(xmin, ymin, xmax, ymax)
    con.create_function("st_makeenvelope", 4, _st_makeenvelope)

    # Accent-insensitive comparison – cql2 emits strip_accents(x)
    con.create_function("strip_accents", 1, _strip_accents)

    # Spatial predicates
    for sql_name, shapely_method in [
        ("st_intersects", "intersects"),
        ("st_equals", "equals"),
        ("st_disjoint", "disjoint"),
        ("st_within", "within"),
        ("st_contains", "contains"),
        ("st_overlaps", "overlaps"),
        ("st_touches", "touches"),
        ("st_crosses", "crosses"),
    ]:
        con.create_function(sql_name, 2, _make_spatial_func(shapely_method))

    # Integer division – cql2 emits div(a, b)
    con.create_function(
        "div", 2, lambda a, b: None if a is None or b is None or b == 0 else a // b
    )


def create_collections_table(con: sqlite3.Connection) -> None:
    """Create the core collections table and FTS5 index for STAC payload and metadata."""
    cur = con.cursor()
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS collections (
            key INTEGER PRIMARY KEY,
            content {_CONTENT_TYPE} NOT NULL CHECK ({_JSON_VALID_CHECK}),
            id TEXT GENERATED ALWAYS AS ({_JSON_EXTRACT}(content, '$.id')) STORED UNIQUE,
            internal_id TEXT GENERATED ALWAYS AS ({_JSON_EXTRACT}(content, '$._id')) STORED UNIQUE,
            datetime TEXT GENERATED ALWAYS AS (
                COALESCE({_JSON_EXTRACT}(content, '$.extent.temporal.interval[0][0]'), '-infinity')
            ) STORED
                CHECK (
                    datetime IN ('-infinity', 'infinity')
                    OR datetime(datetime) IS NOT NULL
                ),
            end_datetime TEXT GENERATED ALWAYS AS (
                COALESCE({_JSON_EXTRACT}(content, '$.extent.temporal.interval[0][1]'), 'infinity')
            ) STORED
                CHECK (
                    end_datetime IN ('-infinity', 'infinity')
                    OR datetime(end_datetime) IS NOT NULL
                ),
            geometry TEXT GENERATED ALWAYS AS (
                CASE WHEN json_type(content, '$.extent.spatial.bbox[0]') = 'array' THEN
                    json_object(
                        'type', 'Polygon',
                        'coordinates', json_array(json_array(
                            json_array(
                                CAST({_JSON_EXTRACT}(content, '$.extent.spatial.bbox[0][0]') AS REAL),
                                CAST({_JSON_EXTRACT}(content, '$.extent.spatial.bbox[0][1]') AS REAL)
                            ),
                            json_array(
                                CAST({_JSON_EXTRACT}(content, '$.extent.spatial.bbox[0][2]') AS REAL),
                                CAST({_JSON_EXTRACT}(content, '$.extent.spatial.bbox[0][1]') AS REAL)
                            ),
                            json_array(
                                CAST({_JSON_EXTRACT}(content, '$.extent.spatial.bbox[0][2]') AS REAL),
                                CAST({_JSON_EXTRACT}(content, '$.extent.spatial.bbox[0][3]') AS REAL)
                            ),
                            json_array(
                                CAST({_JSON_EXTRACT}(content, '$.extent.spatial.bbox[0][0]') AS REAL),
                                CAST({_JSON_EXTRACT}(content, '$.extent.spatial.bbox[0][3]') AS REAL)
                            ),
                            json_array(
                                CAST({_JSON_EXTRACT}(content, '$.extent.spatial.bbox[0][0]') AS REAL),
                                CAST({_JSON_EXTRACT}(content, '$.extent.spatial.bbox[0][1]') AS REAL)
                            )
                        ))
                    )
                END
            ) STORED,
            federation_backends TEXT
        );
        """
    )

    # R-tree spatial index on collection bounding boxes
    cur.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS collections_rtree USING rtree(
            id,
            minx, maxx,
            miny, maxy
        );
        """
    )

    # Triggers to keep R-tree in sync with collections table
    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS collections_rtree_ai AFTER INSERT ON collections
        WHEN json_type(NEW.content, '$.extent.spatial.bbox[0]') = 'array'
        BEGIN
            INSERT INTO collections_rtree (id, minx, maxx, miny, maxy) VALUES (
                NEW.key,
                CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][0]') AS REAL),
                CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][2]') AS REAL),
                CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][1]') AS REAL),
                CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][3]') AS REAL)
            );
        END;
        """
    )
    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS collections_rtree_ad AFTER DELETE ON collections
        BEGIN
            DELETE FROM collections_rtree WHERE id = OLD.key;
        END;
        """
    )
    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS collections_rtree_au AFTER UPDATE OF content ON collections
        BEGIN
            DELETE FROM collections_rtree WHERE id = OLD.key;
            INSERT INTO collections_rtree (id, minx, maxx, miny, maxy)
            SELECT
                NEW.key,
                CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][0]') AS REAL),
                CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][2]') AS REAL),
                CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][1]') AS REAL),
                CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][3]') AS REAL)
            WHERE json_type(NEW.content, '$.extent.spatial.bbox[0]') = 'array';
        END;
        """
    )

    # B-tree indexes on temporal columns for range queries
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_collections_datetime ON collections (datetime);"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_collections_end_datetime ON collections (end_datetime);"
    )

    # FTS5 virtual table for full-text search on title, description, keywords
    cur.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS collections_fts USING fts5(
            title,
            description,
            keywords,
            content='',
            tokenize='unicode61 remove_diacritics 2'
        );
        """
    )

    # Helper: FTS extraction values for a given row reference (NEW/OLD/bare column)
    def _fts_vals(ref: str) -> str:
        sep = "." if ref in ("NEW", "OLD") else ""
        r = f"{ref}{sep}" if ref else ""
        return f"""
                {r}key,
                COALESCE(json_extract({r}content, '$.title'), ''),
                COALESCE(json_extract({r}content, '$.description'), ''),
                COALESCE((
                    SELECT group_concat(value, ' ')
                    FROM json_each({r}content, '$.keywords')
                ), '')"""

    # Triggers to keep FTS index in sync with collections table
    cur.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS collections_ai AFTER INSERT ON collections BEGIN
            INSERT INTO collections_fts(rowid, title, description, keywords)
            VALUES ({_fts_vals("NEW")});
        END;
    """
    )
    cur.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS collections_ad AFTER DELETE ON collections BEGIN
            INSERT INTO collections_fts(collections_fts, rowid, title, description, keywords)
            VALUES ('delete', {_fts_vals("OLD")});
        END;
    """
    )
    cur.execute(
        f"""
        CREATE TRIGGER IF NOT EXISTS collections_au AFTER UPDATE OF content ON collections BEGIN
            INSERT INTO collections_fts(collections_fts, rowid, title, description, keywords)
            VALUES ('delete', {_fts_vals("OLD")});
            INSERT INTO collections_fts(rowid, title, description, keywords)
            VALUES ({_fts_vals("NEW")});
        END;
    """
    )

    con.commit()


def create_collections_federation_backends_table(con: sqlite3.Connection) -> None:
    """Create the federation backends collections configuration table in the database."""
    cur = con.cursor()
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS collections_federation_backends (
            collection_id TEXT,
            federation_backend_name TEXT,
            plugins_config {_CONTENT_TYPE} NOT NULL,
            PRIMARY KEY (collection_id, federation_backend_name)
        );
        """,
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_cfb_backend_name
        ON collections_federation_backends (federation_backend_name);
        """
    )
    con.commit()


def _stac_search_to_where(
    geometry: Optional[Union[str, dict[str, float], BaseGeometry]] = None,
    datetime: Optional[str] = None,
    ids: Optional[list[str]] = None,
    federation_backends: Optional[list[str]] = None,
    cql2_json: Optional[dict[str, Any]] = None,
) -> str:
    """Build the WHERE clause for the collections search query based on the provided parameters."""

    cql2_conditions: list[dict[str, Any]] = []

    if cql2_json:
        cql2_conditions.append(cql2_json)

    if ids:
        cql2_conditions.append(
            {
                "op": "or",
                "args": [
                    {
                        "op": "in",
                        "args": [{"property": "id"}, ids],
                    },
                    {
                        "op": "in",
                        "args": [{"property": "internal_id"}, ids],
                    },
                ],
            }
        )

    if federation_backends:
        cql2_conditions.append(
            {
                "op": "a_overlaps",
                "args": [{"property": "federation_backends"}, federation_backends],
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
                    "args": [{"property": "datetime"}, {"timestamp": end_date_str}],
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

    # Merge all conditions into one CQL2 AND filter
    where_clause = "True"
    if cql2_conditions:
        combined = (
            cql2_conditions[0]
            if len(cql2_conditions) == 1
            else {"op": "and", "args": cql2_conditions}
        )
        where_clause = cql2_json_to_sql(combined)
    return where_clause


COLLECTIONS_SORTABLES: dict[str, str] = {
    "id": "c.id",
    "datetime": "c.datetime",
    "end_datetime": "c.end_datetime",
}

_VALID_DIRECTIONS = {"asc", "desc"}


def _stac_sortby_to_order_by(sortby: list[dict[str, str]]) -> list[str]:
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


def create_federation_backends_table(con: sqlite3.Connection) -> None:
    """Create the federation backends table in the database."""
    cur = con.cursor()

    # Into config goes
    # search:
    #     xxx
    # download:
    #     xxx
    # api:
    #     xxx
    # auth:
    #     xxx
    # search_auth:
    #     xxx

    # Into metadata goes
    # description
    # url
    # last_fetch

    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS federation_backends (
            key PRIMARY KEY,
            id TEXT UNIQUE,
            plugins_config {_CONTENT_TYPE} NOT NULL,
            priority INTEGER NOT NULL,
            metadata {_CONTENT_TYPE},
            enabled BOOLEAN NOT NULL DEFAULT TRUE
        );
        """,
    )
    con.commit()
