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
import threading
import unicodedata
from collections import defaultdict
from collections.abc import Callable
from sqlite3 import Connection
from typing import TYPE_CHECKING, Any, Optional, Union, cast

import cql2
import orjson
import shapely
from shapely.geometry import shape

from eodag.api.collection import Collection, CollectionsDict
from eodag.api.product.metadata_mapping import NOT_AVAILABLE
from eodag.databases.base import Database
from eodag.databases.sqlite_cql2 import cql2_json_to_sql
from eodag.databases.sqlite_fts import stac_q_to_fts5
from eodag.utils import (
    GENERIC_COLLECTION,
    PLUGINS_TOPIC_KEYS,
    get_geometry_from_various,
)
from eodag.utils.dates import get_datetime
from eodag.utils.env import is_env_var_true

if TYPE_CHECKING:
    from collections.abc import Iterable
    from sqlite3 import Cursor, _Parameters

    from shapely.geometry.base import BaseGeometry

    from eodag.config import ProviderConfig

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
_JSON_STORE = "jsonb" if _HAS_JSONB else "json"
_JSON_EXTRACT = "jsonb_extract" if _HAS_JSONB else "json_extract"
_CONTENT_TYPE = "JSONB" if _HAS_JSONB else "TEXT"
_JSON_VALID_CHECK = "json_valid(content, 4)" if _HAS_JSONB else "json_valid(content)"
_JSON_GROUP_ARRAY = "jsonb_group_array" if _HAS_JSONB else "json_group_array"


class SQLiteDatabase(Database):
    """Class representing a SQLite database."""

    _con: Connection

    def __init__(self, db_path: str) -> None:
        """Initialize database by creating a connection and preparing the database."""
        self._lock = threading.RLock()
        self._con = sqlite3.connect(
            database=db_path,
            detect_types=sqlite3.PARSE_COLNAMES,
            check_same_thread=False,
        )
        self._con.row_factory = sqlite3.Row

        sqlite3.register_adapter(Collection, _adapt_collection)
        sqlite3.register_converter("collection_dict", _convert_collection)

        sqlite3.register_adapter(dict, _adapt_dict)
        # set the key "dict" to convert SQLite bytes values to a dictionary
        sqlite3.register_converter("dict", _convert_dict)

        register_custom_functions(self._con)

        with self._lock, self._con:
            create_collections_table(self._con)
            create_collections_federation_backends_table(self._con)
            create_federation_backends_table(self._con)

    def close(self) -> None:
        """Close the connection to the database."""
        with self._lock:
            if self._con:
                self._con.close()

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

        with self._lock:
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

    def delete_collections_federation_backends(self, collection_ids: list[str]) -> None:
        """Remove collection entries from the collections_federation_backends table.

        :param collection_ids: Collection IDs to remove.
        """
        if not collection_ids:
            return
        with self._lock:
            placeholders = ", ".join("?" * len(collection_ids))
            self._execute(
                f"DELETE FROM collections_federation_backends WHERE collection_id IN ({placeholders})",
                tuple(collection_ids),
            )
            self._con.commit()

    def upsert_collections(self, collections: CollectionsDict) -> None:
        """Add or update collections in the database"""

        def _get_id(c):
            if isinstance(c, Collection):
                return c.id
            else:
                return c.get("id")

        with self._lock:
            upserted_coll_nb = self._executemany(
                f"""
                INSERT INTO collections (content) VALUES ({_JSON_STORE}(?))
                ON CONFLICT(id) DO UPDATE SET content = excluded.content
                ON CONFLICT(internal_id) DO UPDATE SET content=excluded.content;
                """,
                [
                    (c,)
                    for c in collections.values()
                    if _get_id(c) not in (GENERIC_COLLECTION, "GENERIC_PRODUCT_TYPE")
                ],
            ).rowcount

            self._con.commit()

            if upserted_coll_nb > 0:
                msg = f"{upserted_coll_nb} collection(s) have been updated or added to the database"
                logger.debug(msg)

    def _upsert_federation_backends(
        self,
        fb_configs: list[
            tuple[str, dict[str, dict[str, Any]], int, dict[str, Any], bool]
        ],
    ) -> None:
        """
        Add or update federation backend configs (providers) in the database.
        Each config must contain: name, plugins_config, priority, metadata, enabled.
        """
        if not fb_configs:
            return
        self._executemany(
            f"""
            INSERT INTO federation_backends (name, plugins_config, priority, metadata, enabled)
            VALUES (?, {_JSON_STORE}(?), ?, {_JSON_STORE}(?), ?)
            ON CONFLICT(name) DO UPDATE SET
                plugins_config = excluded.plugins_config,
                priority = excluded.priority,
                metadata = excluded.metadata,
                enabled = excluded.enabled
            """,
            fb_configs,
        )
        logger.debug("Upserted %d federation backend(s)", len(fb_configs))

    def _upsert_collections_federation_backends(
        self, coll_fb_configs: list[tuple[str, str, dict[str, Any]]]
    ) -> None:
        """
        Upsert collection-specific federation backend configs.
        """
        if not coll_fb_configs:
            return

        self._executemany(
            f"""
            INSERT INTO collections_federation_backends
                (collection_id, federation_backend_name, plugins_config)
            VALUES (?, ?, {_JSON_STORE}(?))
            ON CONFLICT(collection_id, federation_backend_name) DO UPDATE SET
                plugins_config = excluded.plugins_config
            """,
            coll_fb_configs,
        )

        logger.debug("Upserted %d collection-provider config(s)", len(coll_fb_configs))

    def _refresh_collections_denorm(self, changed_fbs: list[str]) -> None:
        """
        Refresh the denormalized ``federation_backends`` and ``priority`` column
        on affected collections.
        """
        if not changed_fbs:
            return
        provider_qmarks = ", ".join(["?"] * len(changed_fbs))

        self._execute(
            """
            CREATE TEMP TABLE IF NOT EXISTS tmp_affected (
                collection_id TEXT PRIMARY KEY
            ) WITHOUT ROWID;
            """
        )
        self._execute(
            f"""
            CREATE TEMP TABLE IF NOT EXISTS tmp_agg (
                collection_id TEXT PRIMARY KEY,
                federation_backends {_CONTENT_TYPE} NOT NULL,
                priority INTEGER NOT NULL
            ) WITHOUT ROWID;
            """
        )
        self._execute("DELETE FROM tmp_affected;")
        self._execute("DELETE FROM tmp_agg;")

        self._execute(
            f"""
            INSERT INTO tmp_affected(collection_id)
            SELECT DISTINCT cfb.collection_id
            FROM collections_federation_backends cfb
            WHERE cfb.federation_backend_name IN ({provider_qmarks});
            """,
            tuple(changed_fbs),
        )
        self._execute(
            f"""
           INSERT INTO tmp_agg(collection_id, federation_backends, priority)
            SELECT
                cfb.collection_id,
                COALESCE(
                    {_JSON_GROUP_ARRAY}(fb.name),
                    json('[]')
                ) AS federation_backends,
                COALESCE(MAX(fb.priority), 0) AS priority
            FROM tmp_affected a
            JOIN collections_federation_backends cfb
                ON cfb.collection_id = a.collection_id
            JOIN (
                SELECT name, priority
                FROM federation_backends
                WHERE enabled = 1
                ORDER BY priority DESC
            ) fb
                ON fb.name = cfb.federation_backend_name
            GROUP BY cfb.collection_id;
            """
        )
        self._execute(
            f"""
            UPDATE collections
            SET
                federation_backends = COALESCE(
                    (SELECT federation_backends
                    FROM tmp_agg
                    WHERE tmp_agg.collection_id = collections.internal_id),
                    {_JSON_STORE}('[]')
                ),
                priority = COALESCE(
                    (SELECT priority
                    FROM tmp_agg
                    WHERE tmp_agg.collection_id = collections.internal_id),
                    0
                )
            WHERE internal_id IN (SELECT collection_id FROM tmp_affected);
            """
        )

    def upsert_fb_configs(self, configs: list[ProviderConfig]) -> None:
        """Add or update federation backend configs (providers) in the database."""
        with self._lock:
            federation_backend_configs = []
            coll_fb_configs = []
            changed_fbs = set()
            known_collections = {
                coll["id"] for coll in self.collections_search(with_fbs_only=False)[0]
            } | {GENERIC_COLLECTION, "GENERIC_PRODUCT_TYPE"}
            strict_mode = is_env_var_true("EODAG_STRICT_COLLECTIONS")
            collections_to_add = []

            def strip_credentials(plugin_conf: dict[str, Any]) -> dict[str, Any]:
                return {k: v for k, v in plugin_conf.items() if k != "credentials"}

            for config in configs:
                exclude_keys = set(PLUGINS_TOPIC_KEYS) | {
                    "name",
                    "priority",
                    "enabled",
                    "products",
                }
                metadata = {
                    k: v for k, v in config.__dict__.items() if k not in exclude_keys
                }

                plugins_config = {}
                for k in PLUGINS_TOPIC_KEYS:
                    if val := getattr(config, k, None):
                        plugins_config[k] = strip_credentials(val.__dict__)

                federation_backend_configs.append(
                    (
                        config.name,
                        plugins_config,
                        getattr(config, "priority", 0),
                        metadata,
                        config.enabled,
                    )
                )

                topics_cfg: dict[str, dict[str, Any]] = {}
                products_cfg = getattr(config, "products", {})
                if getattr(config, "api", None):
                    topics_cfg["api"] = products_cfg
                else:
                    topics_cfg["search"] = products_cfg
                    if products_download_cfg := getattr(
                        getattr(config, "download", None), "products", None
                    ):
                        topics_cfg["download"] = products_download_cfg
                # check
                tmp: dict[str, dict[str, Any]] = defaultdict(
                    lambda: {topic: None for topic in topics_cfg}
                )

                for topic, products_cfg in topics_cfg.items():
                    for coll_id, cfg in products_cfg.items():
                        # add collections config only if collections are known or in collections permissive mode
                        if strict_mode and coll_id not in known_collections:
                            continue
                        # add empty collections to DB for unknown collections in collections permissive mode
                        # it allows to synchronize collections to federation backends
                        if coll_id not in known_collections:
                            collections_to_add.append(
                                Collection(
                                    id=coll_id, title=coll_id, description=NOT_AVAILABLE
                                )
                            )

                        tmp[coll_id][topic] = cfg

                for coll_id, cfg in tmp.items():
                    coll_fb_configs.append((coll_id, config.name, cfg))

                changed_fbs.add(config.name)

            with self._con:
                # Add new collections to DB first to enable to set their column
                # "federation_backends" during federation backends config update
                if collections_to_add:
                    self.upsert_collections(CollectionsDict(collections_to_add))
                    logger.debug(
                        "Collections permissive mode, %s added",
                        ", ".join(c.id for c in collections_to_add),
                    )
                self._upsert_federation_backends(federation_backend_configs)
                self._upsert_collections_federation_backends(coll_fb_configs)
                self._refresh_collections_denorm(sorted(changed_fbs))

    def set_priority(self, name: str, priority: int) -> None:
        """
        Set the priority of a federation backend.
        """
        with self._lock, self._con:
            self._execute(
                "UPDATE federation_backends SET priority = ? WHERE name = ?",
                (priority, name),
            )
            self._refresh_collections_denorm([name])

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
        with self._lock:
            if cql2_text and cql2_json:
                raise ValueError("Cannot provide both cql2_text and cql2_json")

            if cql2_text:
                cql2_json = cql2.parse_text(cql2_text).to_json()

            where = _stac_search_to_where(
                geometry, datetime, ids, federation_backends, cql2_json
            )

            from_clause = "FROM collections c"
            where_parts = (
                [where] + ["c.federation_backends IS NOT NULL"]
                if with_fbs_only
                else [where]
            )
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
                    select_score = (
                        ", bm25(collections_fts, 30.0, 3.0, 1.0) AS rank_score"
                    )
                    order_terms = ["rank_score ASC"]

            if sortby:
                order_terms = _stac_sortby_to_order_by(sortby)

            order_terms.extend(["c.priority DESC", "c.id ASC"])
            order_by = " ORDER BY " + ", ".join(order_terms)

            full_where = " AND ".join(where_parts)

            # Total matches (before limit)
            count_row = self._execute(
                f"SELECT COUNT(*) {from_clause} WHERE {full_where}",
                tuple(params) or None,
            ).fetchone()
            number_matched = cast(int, count_row[0]) if count_row else 0

            sql = (
                f'SELECT json(c.content) AS "c.content [collection_dict]", '
                f'json(c.federation_backends) as "c.federation_backends [dict]", '
                f'json(c.federation) as "c.federation [dict]"{select_score} '
                f"{from_clause} WHERE {full_where}{order_by}"
            )
            if limit is not None:
                sql += f" LIMIT {limit}"

            collections_list = []
            for row in self._execute(sql, tuple(params) or None).fetchall():
                coll = row["c.content"]
                coll["federation:backends"] = row["c.federation_backends"]
                coll["federation"] = row["c.federation"]
                collections_list.append(coll)

            return collections_list, number_matched

    def get_federation_backends(
        self,
        names: Optional[set[str]] = None,
        enabled: Optional[bool] = None,
        fetchable: Optional[bool] = None,
        collection: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Return federation backends according to filters.
        Results are sorted by priority DESC then name ASC.
        """
        with self._lock:
            sql = (
                "SELECT fb.name, fb.priority, fb.enabled, "
                'json(fb.metadata) AS "metadata [dict]" '
                "FROM federation_backends fb"
            )
            where_clauses = []
            params: dict[str, Any] = {}

            if collection:
                sql += (
                    " INNER JOIN collections_federation_backends cfb "
                    "ON fb.name = cfb.federation_backend_name AND cfb.collection_id = :collection"
                )
                params["collection"] = collection

            if enabled is not None:
                where_clauses.append(f"{'NOT ' if not enabled else ''}fb.enabled")

            if fetchable is not None:
                where_clauses.append(
                    f"{'NOT ' if not fetchable else ''}{_JSON_EXTRACT}(fb.metadata, '$.fetchable')"
                )

            if names:
                placeholders = ",".join(f":{name}" for name in names)
                where_clauses.append(f"fb.name IN ({placeholders})")
                for name in names:
                    params[name] = name

            if where_clauses:
                sql += " WHERE " + " AND ".join(where_clauses)

            sql += " ORDER BY fb.priority DESC, fb.name ASC"
            if limit is not None:
                sql += f" LIMIT {limit}"

            rows = self._execute(sql, params).fetchall()

            return {
                row["name"]: {
                    "priority": row["priority"],
                    "enabled": bool(row["enabled"]),
                    "metadata": row["metadata"] or {},
                }
                for row in rows
            }

    def get_fb_config(
        self,
        name: str,
        collections: set[str] | None = None,
    ) -> dict[str, Any]:
        """Get the federation backend config for a given provider and optional collection filter."""
        with self._lock:
            collections = collections or set()

            if collections:
                placeholders = ", ".join("?" for _ in collections)
                cfb_filter_sql = f"cfb.collection_id IN ({placeholders})"
                cfb_params = tuple(collections)
            else:
                cfb_filter_sql = "0"
                cfb_params = ()

            sql = f"""
                SELECT
                    json(fb.plugins_config) AS "provider_plugins_config [dict]",
                    fb.priority             AS provider_priority,
                    json(fb.metadata)       AS "provider_metadata [dict]",
                    fb.enabled              AS provider_enabled,

                    c.collection_id         AS collection_id,
                    json(c.plugins_config)  AS "collection_plugins_config [dict]"
                FROM federation_backends fb
                LEFT JOIN (
                    SELECT
                        cfb.collection_id,
                        cfb.plugins_config
                    FROM collections_federation_backends cfb
                    WHERE cfb.federation_backend_name = ?
                    AND {cfb_filter_sql}
                ) AS c
                ON 1 = 1
                WHERE fb.name = ?
            """
            params = (name, *cfb_params, name)

            rows = self._execute(sql, params).fetchall()
            if not rows or not rows[0]["provider_plugins_config"]:
                msg = f"Provider '{name}' not found"
                raise KeyError(msg)
            base: dict[str, Any] = (
                rows[0]["provider_plugins_config"]
                | (rows[0]["provider_metadata"] or {})
                | {
                    "priority": rows[0]["provider_priority"],
                    "enabled": bool(rows[0]["provider_enabled"]),
                    "name": name,
                }
            )
            base.setdefault("products", {})
            if isinstance(base.get("download"), dict):
                base["download"].setdefault("products", {})

            for r in rows:
                cid = r["collection_id"]
                if not cid:
                    continue
                blob = r["collection_plugins_config"] or {}
                base["products"][cid] = blob.get("search", {}) or blob.get("api", {})
                if isinstance(base.get("download"), dict):
                    base["download"]["products"][cid] = blob.get("download", {})

            return base


def _adapt_collection(collection: Collection) -> str:
    """An adapter to automatically convert from a ``Collection`` instance
    to an SQLite-compatible type (here a string) when injected to queries"""
    data = collection.model_dump(mode="json")
    data["_id"] = collection._id
    # remove "federation:backends" from the stored content as it is computed in a separate column
    del data["federation:backends"]
    del data["federation"]
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
    data_bytes = orjson.dumps(data)
    return data_bytes if _HAS_JSONB else data_bytes.decode()


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
            federation_backends {_CONTENT_TYPE},
            federation {_CONTENT_TYPE},
            priority INTEGER
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


def create_federation_backends_table(con: sqlite3.Connection) -> None:
    """Create the federation backends table in the database."""
    cur = con.cursor()

    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS federation_backends (
            key PRIMARY KEY,
            name TEXT UNIQUE,
            plugins_config {_CONTENT_TYPE} NOT NULL,
            priority INTEGER NOT NULL,
            metadata {_CONTENT_TYPE},
            enabled BOOLEAN NOT NULL
        );
        """,
    )


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
        CREATE INDEX IF NOT EXISTS idx_cfb_backend_collection
        ON collections_federation_backends (federation_backend_name, collection_id);
        """
    )


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
                "args": [{"property": "federation:backends"}, federation_backends],
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
