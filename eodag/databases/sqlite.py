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

import atexit
import logging
import os
import sqlite3
import unicodedata
from collections.abc import Callable
from sqlite3 import Connection
from typing import TYPE_CHECKING, Any, Optional, Union

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
from eodag.utils.exceptions import NoMatchingCollection

if TYPE_CHECKING:
    from collections.abc import Iterable
    from sqlite3 import Cursor, _Parameters

    from shapely.geometry.base import BaseGeometry

    from eodag.api.provider import ProviderConfig

logger = logging.getLogger("eodag.databases.sqlite_database")


class SQLiteDatabase(Database):
    """Class representing a SQLite database."""

    con: Connection

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize database by creating a connection and preparing the database."""
        self.type = "sqlite"
        if db_path is None:
            db_path = os.path.join(
                os.path.expanduser("~"), ".config", "eodag", "eodag.db"
            )
        self.con = self._get_connection(db_path)
        self.prepare_database()

    def _adapt_collection(self, collection: Collection) -> str:
        """An adapter to automatically convert from a ``Collection``
        instance to an SQLite-compatible type when injected to queries"""
        return collection.model_dump_json()

    def _convert_collection(self, coll_bytes: bytes) -> dict[str, Any]:
        """A converter to convert from SQLite bytes values of a collection to a dictionary
        of this collection when called in queries by its key wrapped in square brackets.
        Its key is set during its registration.
        """
        return orjson.loads(coll_bytes)

    def prepare_database(self) -> None:
        """Do what is required (or better) to do before sending queries to the database:

        * register adapters and converters to make processes before and after queries easier
        * register custom SQLite functions
        * create tables if do not exist
        """
        # register the adapter and converter
        sqlite3.register_adapter(Collection, self._adapt_collection)
        # set the key "collection_dict" to convert SQLite bytes values to a dictionary
        sqlite3.register_converter("collection_dict", self._convert_collection)

        # register custom SQLite functions
        register_custom_functions(self.con)

        create_collections_table(self.con)

        self._create_col_config_table()

    def _get_connection(self, db_path: str) -> Connection:
        """Get a connection to a database.

        :param db_path: Path to use to create a database or to connect to it

        :returns: The connection instance
        """
        # connect to the database
        # set parsing using column names for the adapter and converter
        con = sqlite3.connect(
            database=db_path,
            detect_types=sqlite3.PARSE_COLNAMES,
            check_same_thread=True,
        )
        con.row_factory = sqlite3.Row

        # ensure the connection is closed on exit
        atexit.register(self._close_connection)

        return con

    def _close_connection(self) -> None:
        """Close the connection to the database."""
        self.con.close()

    def _execute(self, sql: str, parameters: Optional[_Parameters] = None) -> Cursor:
        """
        Return the cursor from a SQLite query ``execute()`` and rollback the connection if the query failed

        :param sql: A single SQL statement
        :param parameters: Python values to bind to placeholders in ``sql``

        :raises: :class:`~sqlite3.DatabaseError`
        """
        try:
            if parameters is None:
                return self.con.execute(sql)
            else:
                return self.con.execute(sql, parameters)
        except sqlite3.DatabaseError as e:
            # rollback manually as connection parameter "isolation_level" is set to "DEFERRED"
            self.con.rollback()
            raise e

    def _executemany(self, sql: str, parameters: Iterable[_Parameters]) -> Cursor:
        """
        Return the cursor from a SQLite query ``execute_all()`` and rollback the connection if the query failed

        :param sql: A single SQL statement
        :param parameters: Python values to bind to placeholders in ``sql``

        :raises: :class:`~sqlite3.DatabaseError`
        """
        try:
            return self.con.executemany(sql, parameters)
        except sqlite3.DatabaseError as e:
            # rollback manually as connection parameter "isolation_level" is set to "DEFERRED"
            self.con.rollback()
            raise e

    def _create_col_config_table(self) -> None:
        """Create the collections configuration table in the database."""
        self._execute(
            """
            CREATE TABLE IF NOT EXISTS providers_config (
                provider TEXT,
                collection TEXT,
                config BLOB NOT NULL,
                priority INTEGER,
                PRIMARY KEY (provider, collection)
            );
            """,
        )

    def get_collection(self, collection_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a collection from the database."""
        row = self._execute(
            'SELECT json(content) AS "collection [collection_dict]" FROM collections WHERE id = ?',
            (collection_id,),
        ).fetchone()
        return row["collection"] if row else None

    def get_collection_from_alias(self, alias_or_id: str) -> dict[str, Any]:
        """Retrieve a collection from the database by either its id or alias.

        :param alias_or_id: Alias of the collection. If an existing id is given, this
                            method will directly return the collection of given value.
        :returns: A dictionary of the collection having ``alias_or_id`` as alias or id.
        """
        collection_rows = self._execute(
            'SELECT json(content) AS "collection [collection_dict]" FROM collections '
            "WHERE id = ?;",
            (alias_or_id,),
        ).fetchall()

        if len(collection_rows) > 1:
            coll_with_alias = ", ".join(
                [str(coll_row["collection"]) for coll_row in collection_rows]
            )
            msg = f"Too many matching collections for alias {alias_or_id}: {coll_with_alias}"
            raise NoMatchingCollection(msg)

        if len(collection_rows) == 0:
            if (coll := self.get_collection(alias_or_id)) is not None:
                return coll
            else:
                msg = f"Could not find collection from alias or id {alias_or_id}"
                raise NoMatchingCollection(msg)

        return collection_rows[0]["collection"]

    def delete_collection(self, collection_id: str) -> None:
        """Remove a collection and its provider configs from the database."""
        self._execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        self._execute(
            "DELETE FROM providers_config WHERE collection = ?", (collection_id,)
        )
        self.con.commit()

    def upsert_collections(self, collections: CollectionsDict) -> None:
        """Add or update collections in the database"""

        upserted_coll_nb = self._executemany(
            """
            INSERT INTO collections (content) VALUES (jsonb(?))
            ON CONFLICT(id) DO UPDATE SET content=excluded.content;
            """,
            [(c,) for c in collections.values()],
        ).rowcount

        self.con.commit()

        if upserted_coll_nb > 0:
            msg = f"{upserted_coll_nb} collection(s) have been updated or added to the database"
            logger.debug(msg)

    def upsert_providers_config(self, providers_config: list[ProviderConfig]) -> None:
        """Add or update providers configurations in the database"""
        for p_config in providers_config:
            for coll, coll_config in p_config.products.items():
                # TODO: better use executemany
                self._execute(
                    """
                    INSERT INTO providers_config (provider, collection, config, priority)
                        VALUES (?, ?, jsonb(?), ?)
                        ON CONFLICT(provider, collection) DO UPDATE SET
                            config=excluded.config,
                            priority=excluded.priority;
                    """,
                    (
                        p_config.name,
                        coll,
                        coll_config,
                        p_config.priority,
                    ),
                )
        self.con.commit()

        # free memory taken by "products" in providers config
        p_config.__dict__["products"] = {}
        pass

    def collections_search(
        self,
        geometry: Optional[Union[str, dict[str, float], BaseGeometry]] = None,
        datetime: Optional[str] = None,
        limit: Optional[int] = 10,
        q: Optional[list[str]] = None,
        cql2_text: Optional[str] = None,
        cql2_json: Optional[dict[str, Any]] = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Search collections matching the given parameters.

        :returns: A tuple of (returned collections as dictionaries, total number matched).
        """
        where = _stac_search_to_where(geometry, datetime, cql2_text, cql2_json)

        from_clause = "FROM collections c"
        where_parts = [where]
        params: list[Any] = []
        order_by = ""
        select_score = ""

        if q:
            fts_expr = stac_q_to_fts5(" ".join(q))
            if fts_expr:
                from_clause += " JOIN collections_fts cf ON cf.rowid = c.key"
                where_parts.append("collections_fts MATCH ?")
                params.append(fts_expr)

                # Weighted relevance: title > description > keywords
                select_score = ", bm25(collections_fts, 10.0, 3.0, 1.0) AS rank_score"
                order_by = " ORDER BY rank_score ASC, c.id ASC"

        full_where = " AND ".join(where_parts)

        # Total matches (before limit)
        count_row = self._execute(
            f"SELECT COUNT(*) {from_clause} WHERE {full_where}",
            tuple(params) or None,
        ).fetchone()
        number_matched = count_row[0] if count_row else 0

        sql = (
            f'SELECT json(c.content) AS "collection [collection_dict]"{select_score} '
            f"{from_clause} WHERE {full_where}{order_by}"
        )
        if limit is not None:
            sql += f" LIMIT {limit}"

        collections_list: list[Collection] = [
            row["collection"]
            for row in self._execute(sql, tuple(params) or None).fetchall()
        ]

        return CollectionsDict(collections_list), number_matched


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


def _make_array_func(
    predicate: Callable[[set[Any], set[Any]], bool],
) -> Callable[[str | None, str | None], int | None]:
    """Create an array comparison function for SQLite registration.

    Both arguments are JSON array strings.
    """

    def func(left_json: str | None, right_json: str | None) -> int | None:
        if left_json is None or right_json is None:
            return None
        left = set(orjson.loads(left_json))
        right = set(orjson.loads(right_json))
        return int(predicate(left, right))

    return func


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

    # Array predicates – rewritten from Postgres @>, <@, @@, = ARRAY[]
    for func_name, predicate in [
        ("a_contains", lambda a, b: b.issubset(a)),
        ("a_containedby", lambda a, b: a.issubset(b)),
        ("a_equals", lambda a, b: a == b),
        ("a_overlaps", lambda a, b: bool(a & b)),
    ]:
        con.create_function(func_name, 2, _make_array_func(predicate))

    # Integer division – cql2 emits div(a, b)
    con.create_function(
        "div", 2, lambda a, b: None if a is None or b is None or b == 0 else a // b
    )


def create_collections_table(con: sqlite3.Connection) -> None:
    """Create the core collections table and FTS5 index for STAC payload and metadata."""
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS collections (
            key INTEGER PRIMARY KEY,
            content JSONB NOT NULL CHECK (json_valid(content, 4)),
            id TEXT GENERATED ALWAYS AS (jsonb_extract(content, '$.id')) STORED UNIQUE,
            datetime TEXT GENERATED ALWAYS AS (
                COALESCE(jsonb_extract(content, '$.extent.temporal.interval[0][0]'), '-infinity')
            ) STORED
                CHECK (
                    datetime IN ('-infinity', 'infinity')
                    OR datetime(datetime) IS NOT NULL
                ),
            end_datetime TEXT GENERATED ALWAYS AS (
                COALESCE(jsonb_extract(content, '$.extent.temporal.interval[0][1]'), 'infinity')
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
                                CAST(jsonb_extract(content, '$.extent.spatial.bbox[0][0]') AS REAL),
                                CAST(jsonb_extract(content, '$.extent.spatial.bbox[0][1]') AS REAL)
                            ),
                            json_array(
                                CAST(jsonb_extract(content, '$.extent.spatial.bbox[0][2]') AS REAL),
                                CAST(jsonb_extract(content, '$.extent.spatial.bbox[0][1]') AS REAL)
                            ),
                            json_array(
                                CAST(jsonb_extract(content, '$.extent.spatial.bbox[0][2]') AS REAL),
                                CAST(jsonb_extract(content, '$.extent.spatial.bbox[0][3]') AS REAL)
                            ),
                            json_array(
                                CAST(jsonb_extract(content, '$.extent.spatial.bbox[0][0]') AS REAL),
                                CAST(jsonb_extract(content, '$.extent.spatial.bbox[0][3]') AS REAL)
                            ),
                            json_array(
                                CAST(jsonb_extract(content, '$.extent.spatial.bbox[0][0]') AS REAL),
                                CAST(jsonb_extract(content, '$.extent.spatial.bbox[0][1]') AS REAL)
                            )
                        ))
                    )
                END
            ) STORED
        );
        """
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


def _stac_search_to_where(
    geometry: Optional[Union[str, dict[str, float], BaseGeometry]] = None,
    datetime: Optional[str] = None,
    cql2_text: Optional[str] = None,
    cql2_json: Optional[dict[str, Any]] = None,
) -> str:
    """Build the WHERE clause for the collections search query based on the provided parameters."""
    if cql2_text and cql2_json:
        raise ValueError("Cannot provide both cql2_text and cql2_json")

    if cql2_text:
        cql2_json = cql2.parse_text(cql2_text).to_json()

    cql2_conditions: list[dict[str, Any]] = []

    if cql2_json:
        cql2_conditions.append(cql2_json)

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
