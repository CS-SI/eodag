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
from sqlite3 import Connection
from typing import TYPE_CHECKING, Any, Optional, Union, cast

import orjson
from shapely import Geometry, wkt

from eodag.api.collection import Collection, CollectionsDict
from eodag.databases.base import Database
from eodag.databases.sqlite_functions import register_sqlite_functions
from eodag.utils import get_geometry_from_various
from eodag.utils.dates import get_datetime
from eodag.utils.exceptions import NoMatchingCollection

if TYPE_CHECKING:
    from collections.abc import Iterable
    from sqlite3 import Cursor, _Parameters

    from shapely.geometry.base import BaseGeometry

    from eodag.api.core import EODataAccessGateway
    from eodag.api.provider import ProviderConfig

logger = logging.getLogger("eodag.databases.sqlite_database")


class SQLiteDatabase(Database):
    """Class representing a SQLite database."""

    con: Connection
    _dag: Optional[EODataAccessGateway] = None

    def __init__(self, db_path: Optional[str] = None) -> None:
        """Initialize database by creating a connection and preparing the database."""
        self.type = "sqlite"
        if db_path is None:
            db_path = os.path.join(
                os.path.expanduser("~"), ".config", "eodag", "eodag.db"
            )
        self.con = self._get_connection(db_path)
        self.prepare_database()

    @classmethod
    def create_with_dag(
        cls, dag: EODataAccessGateway, db_path: Optional[str] = None, **kwargs
    ) -> SQLiteDatabase:
        """Create a SQLiteDatabase with a EODataAccessGateway instance.

        :param dag: The gateway instance to use to create collections with it
        :param kwargs: The database attributes
        """
        instance = cls(db_path, **kwargs)
        instance._dag = dag
        return instance

    def _ensure_dag(self) -> EODataAccessGateway:
        """Ensure that a dag is present in the instance before some operations"""
        if self._dag is None:
            raise RuntimeError(
                "SQLiteDatabase instance needs EODataAccessGateway to perform this operation. "
                "Create with: SQLiteDatabase.create_with_dag(dag)"
            )
        return self._dag

    def _adapt_collection(self, collection: Collection) -> str:
        """An adapter to automatically convert from a ``Collection``
        instance to an SQLite-compatible type when injected to queries"""
        return collection.model_dump_json()

    def _convert_collection(self, coll_bytes: bytes) -> Collection:
        """A converter to convert from SQLite values to the ``Collection`` instance
        when called in queries by its key wrapped in square brackets.
        Its key is set during its registration.
        """
        dag = self._ensure_dag()
        coll_dict = orjson.loads(coll_bytes)
        coll_obj = Collection.create_with_dag(dag, **coll_dict)
        return coll_obj

    def prepare_database(self) -> None:
        """Do what is required (or better) to do before sending queries to the database:

        * register adapters and converters to make processes before and after queries easier
        * register custom SQLite functions
        * create tables if do not exist
        """
        # register the adapter and converter
        sqlite3.register_adapter(Collection, self._adapt_collection)
        # set the key "collection" to convert SQLite values to a ``Collection`` instance
        sqlite3.register_converter("collection", self._convert_collection)

        # register custom SQLite functions
        register_sqlite_functions(self.con)

        self._create_col_table()
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

    def _execute(
        self, con: Connection, sql: str, parameters: Optional[_Parameters] = None
    ) -> Cursor:
        """
        Return the cursor from a SQLite query ``execute()`` and rollback the connection if the query failed

        :param con: The connection to the database
        :param sql: A single SQL statement
        :param parameters: Python values to bind to placeholders in ``sql``

        :raises: :class:`~sqlite3.DatabaseError`
        """
        try:
            if parameters is None:
                return con.execute(sql)
            else:
                return con.execute(sql, parameters)
        except sqlite3.DatabaseError as e:
            # rollback manually as connection parameter "isolation_level" is set to "DEFERRED"
            con.rollback()
            raise e

    def _executemany(
        self, con: Connection, sql: str, parameters: Iterable[_Parameters]
    ) -> Cursor:
        """
        Return the cursor from a SQLite query ``execute_all()`` and rollback the connection if the query failed

        :param con: The connection to the database
        :param sql: A single SQL statement
        :param parameters: Python values to bind to placeholders in ``sql``

        :raises: :class:`~sqlite3.DatabaseError`
        """
        try:
            return con.executemany(sql, parameters)
        except sqlite3.DatabaseError as e:
            # rollback manually as connection parameter "isolation_level" is set to "DEFERRED"
            con.rollback()
            raise e

    def _create_col_table(self) -> None:
        """Create the collections table in the database."""
        self._execute(
            self.con,
            """
            CREATE TABLE IF NOT EXISTS collections (
                id TEXT PRIMARY KEY,
                collection BLOB NOT NULL
            );
            """,
        )

    def _create_col_config_table(self) -> None:
        """Create the collections configuration table in the database."""
        self._execute(
            self.con,
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

    def get_collection(self, collection_name: str) -> Optional[Collection]:
        """Retrieve a collection from the database."""
        collection_row = self._execute(
            self.con,
            'SELECT json(collection) AS "collection [collection]" FROM collections WHERE id = ?;',
            (collection_name,),
        ).fetchone()

        if collection_row is None:
            return None
        return collection_row["collection"]

    def get_collection_from_alias(self, alias_or_id: str) -> Collection:
        """Retrieve a collection from the database by either its id or alias.

        :param alias_or_id: Alias of the collection. If an existing id is given, this
                            method will directly return the collection of given value.
        :returns: The collection having  Internal name of the collection.
        """
        collection_rows = self._execute(
            self.con,
            'SELECT json(collection) AS "collection [collection]" FROM collections '
            "WHERE jsonb_extract(collection, '$.id') = ?;",
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

    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection from the database."""
        deleted_coll_nb = self._execute(
            self.con,
            """
            DELETE FROM collections
            WHERE id = ?;
            """,
            (collection_name,),
        ).rowcount

        self._execute(
            self.con,
            """
            DELETE FROM providers_config
            WHERE collection = ?;
            """,
            (collection_name,),
        )

        self.con.commit()

        if deleted_coll_nb > 0:
            msg = f"{deleted_coll_nb} collection(s) have been deleted from the database"
            logger.debug(msg)

    def rename_collection(self, old_name: str, new_name: str) -> None:
        """Rename a collection in the database."""
        # TODO: maybe change id attribute in column "collection",
        # and in that case it is not needed to update providers_config
        renamed_coll_nb = self._execute(
            self.con,
            """
            UPDATE collections
            SET id = ?
            WHERE id = ?;
            """,
            (new_name, old_name),
        ).rowcount

        self._execute(
            self.con,
            """
            UPDATE providers_config
            SET collection = ?
            WHERE collection = ?;
            """,
            (new_name, old_name),
        )

        self.con.commit()

        if renamed_coll_nb > 0:
            msg = f"{renamed_coll_nb} collection(s) have been renamed in the database"
            logger.debug(msg)

    def update(self, collection_conf: dict[str, Any]) -> None:
        """Update a collection in the database."""
        raise NotImplementedError

    def insert_collection(self, collection: Collection) -> None:
        """Insert a collection in the database."""
        raise NotImplementedError

    def upsert_collections(self, collections: CollectionsDict) -> None:
        """Add or update collections in the database"""
        collection_tuples_list: list[tuple[str, Collection]] = []
        for id, coll in collections.items():
            collection_tuples_list.append((id, coll))

        upserted_coll_nb = self._executemany(
            self.con,
            """
            INSERT INTO collections (id, collection) VALUES (?, jsonb(?))
            ON CONFLICT(id) DO UPDATE SET collection=excluded.collection;
            """,
            collection_tuples_list,
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
                    self.con,
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

    def search_collections(
        self,
        geometry: Optional[Union[str, dict[str, float], BaseGeometry]] = None,
        datetime: Optional[str] = None,
        limit: Optional[int] = 10,
        q: Optional[list[str]] = None,  # Free-Text Search
        query: Optional[str] = None,  # STACQL
        filter_: Optional[dict[str, Any]] = None,  # cql2
        count: bool = False,
    ) -> tuple[CollectionsDict, Optional[int]]:
        """
        :returns: Collections matching all the given parameters.
        """
        where_conditions_list = []
        parameters: dict[str, Any] = {}

        # TODO: create q_to_dict
        q_dict = {}  # q_to_dict(q) if q else {}

        if collection := q_dict.get("id"):
            try:
                self.get_collection_from_alias(collection)
            except NoMatchingCollection:
                return (CollectionsDict([]), 0 if count else None)

            parameters.update({"id": collection})
            where_conditions_list.append("id = :id")

        if "provider" in q_dict or "federation:backends" in q_dict:
            provider = q_dict.get("provider", q_dict.get["federation:backends"])
            provider = provider[0] if isinstance(provider, list) else provider
            if provider is not None:
                parameters.update({"provider": provider})
                where_conditions_list.append(
                    "jsonb_extract(collection, '$.id') IN "
                    "("
                    "   SELECT collection FROM providers_config "
                    "   WHERE provider = :provider"
                    ");",
                )

        if geometry:
            geom = cast(Geometry, get_geometry_from_various(geometry=geometry))
            geom_wkt = wkt.dumps(geom, rounding_precision=4)
            if geom is not None:
                parameters.update({"geom": geom_wkt})
                where_conditions_list.append(
                    "check_collection_geom_intersection(json(collection), :geom)"
                )

        if datetime:
            start_date_str, end_date_str = get_datetime({"datetime": datetime})
            parameters.update(
                {"start_date_str": start_date_str, "end_date_str": end_date_str}
            )
            where_conditions_list.append(
                "check_collection_interval_intersection(json(collection), :start_date_str, :end_date_str)"
            )

        where_conditions_intersection = (
            " AND ".join(where_conditions_list) if where_conditions_list else "True"
        )

        # execute
        sql = (
            'SELECT json(collection) AS "collection [collection]" FROM collections '
            f"WHERE {where_conditions_intersection};"
        )

        collection_rows = self._execute(self.con, sql, parameters).fetchall()

        if not collection_rows:
            if collection:
                msg = (
                    f"Collection {collection} exists but does not match other criteria"
                )
                logger.info(msg)

            return (CollectionsDict([]), 0 if count else None)

        collections_list: list[Collection] = [
            coll_row["collection"] for coll_row in collection_rows
        ]

        number_matched: Optional[int] = None
        if count:
            sql = (
                "SELECT COUNT(collection) FROM collections "
                f"WHERE {where_conditions_intersection};"
            )
            number_matched_row = self._execute(self.con, sql).fetchone()

            number_matched = 0 if number_matched_row is None else number_matched_row[0]

        return CollectionsDict(collections_list), number_matched
