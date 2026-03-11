import json
import sqlite3
from typing import Any

type CollectionDict = dict[str, Any]


def load_spatialite(connection: sqlite3.Connection) -> None:
    """Load SpatiaLite extension with common Linux library names."""
    candidates = [
        "mod_spatialite",
        "libspatialite",
        "/usr/lib/x86_64-linux-gnu/mod_spatialite.so",
    ]

    connection.enable_load_extension(True)
    for candidate in candidates:
        try:
            connection.load_extension(candidate)
            return
        except sqlite3.OperationalError:
            continue
    raise RuntimeError(
        "Could not load SpatiaLite extension. Install mod_spatialite/libspatialite first."
    )


def create_collections_table(cur: sqlite3.Cursor) -> None:
    """Create the core collections table for STAC payload and metadata."""
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS collections (
            key INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL CHECK (json_valid(content)),
            id TEXT GENERATED ALWAYS AS (json_extract(content, '$.id')) STORED UNIQUE,
            datetime TEXT GENERATED ALWAYS AS (
                COALESCE(json_extract(content, '$.extent.temporal.interval[0][0]'), '-infinity')
            ) STORED
                CHECK (
                    datetime IN ('-infinity', 'infinity')
                    OR datetime(datetime) IS NOT NULL
                ),
            end_datetime TEXT GENERATED ALWAYS AS (
                COALESCE(json_extract(content, '$.extent.temporal.interval[0][1]'), 'infinity')
            ) STORED
                CHECK (
                    end_datetime IN ('-infinity', 'infinity')
                    OR datetime(end_datetime) IS NOT NULL
                )
        );
        """
    )


def create_bbox_to_geometry_triggers(cur: sqlite3.Cursor) -> None:
    """Create triggers that derive geometry from content.extent.spatial.bbox[0]."""
    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS tr_collections_geom_after_insert
        AFTER INSERT ON collections
        FOR EACH ROW
        WHEN json_type(NEW.content, '$.extent.spatial.bbox[0]') = 'array'
        BEGIN
            UPDATE collections
            SET geometry = CastToMulti(
                BuildMbr(
                    CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][0]') AS REAL),
                    CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][1]') AS REAL),
                    CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][2]') AS REAL),
                    CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][3]') AS REAL),
                    4326
                )
            )
            WHERE key = NEW.key;
        END;
        """
    )

    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS tr_collections_geom_after_update_content
        AFTER UPDATE OF content ON collections
        FOR EACH ROW
        WHEN json_type(NEW.content, '$.extent.spatial.bbox[0]') = 'array'
        BEGIN
            UPDATE collections
            SET geometry = CastToMulti(
                BuildMbr(
                    CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][0]') AS REAL),
                    CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][1]') AS REAL),
                    CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][2]') AS REAL),
                    CAST(json_extract(NEW.content, '$.extent.spatial.bbox[0][3]') AS REAL),
                    4326
                )
            )
            WHERE key = NEW.key;
        END;
        """
    )

    cur.execute(
        """
        CREATE TRIGGER IF NOT EXISTS tr_collections_geom_clear_when_no_bbox
        AFTER UPDATE OF content ON collections
        FOR EACH ROW
        WHEN json_type(NEW.content, '$.extent.spatial.bbox[0]') IS NULL
        BEGIN
            UPDATE collections
            SET geometry = NULL
            WHERE key = NEW.key;
        END;
        """
    )


def init_spatial_metadata(cur: sqlite3.Cursor) -> None:
    """Initialize SpatiaLite metadata tables once."""
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='spatial_ref_sys';"
    )
    if cur.fetchone() is None:
        cur.execute("SELECT InitSpatialMetadata(1);")


def ensure_geometry_column(cur: sqlite3.Cursor) -> None:
    """Add and validate the SpatiaLite geometry column registration."""
    cur.execute("PRAGMA table_info(collections);")
    existing_columns = {row[1] for row in cur.fetchall()}

    cur.execute(
        """
        SELECT 1
        FROM geometry_columns
        WHERE f_table_name = 'collections' AND f_geometry_column = 'geometry'
        LIMIT 1;
        """
    )
    geometry_is_registered = cur.fetchone() is not None

    if "geometry" in existing_columns and not geometry_is_registered:
        raise RuntimeError(
            "Column 'geometry' already exists but is not registered as a SpatiaLite geometry column. "
            "Use a fresh DB or migrate the table."
        )

    if "geometry" not in existing_columns:
        cur.execute(
            "SELECT AddGeometryColumn('collections', 'geometry', 4326, 'MULTIPOLYGON', 'XY');"
        )


def ensure_geometry_spatial_index(cur: sqlite3.Cursor) -> None:
    """Create the geometry spatial index once."""
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='idx_collections_geometry';"
    )
    if cur.fetchone() is None:
        cur.execute("SELECT CreateSpatialIndex('collections', 'geometry');")


def init_database(connection: sqlite3.Connection) -> None:
    """Run complete schema and spatial initialization."""
    cur = connection.cursor()
    init_spatial_metadata(cur)
    create_collections_table(cur)
    ensure_geometry_column(cur)
    ensure_geometry_spatial_index(cur)
    create_bbox_to_geometry_triggers(cur)
    connection.commit()


def update_collections(
    conn: sqlite3.Connection,
    collections: list[CollectionDict],
    upsert: bool = False,
) -> None:
    """
    Update multiple STAC collection rows;

    Args:
        conn: sqlite3.Connection object.
        collections: List of dictionaries, each representing a STAC collection.
        upsert: If True, update content on id conflict instead of raising.
    """
    rows = [(json.dumps(c),) for c in collections]
    on_conflict = "ON CONFLICT(id) DO UPDATE SET content = excluded.content" if upsert else ""
    cur = conn.cursor()
    cur.executemany(
        f"""
        INSERT INTO collections (content)
        VALUES (?)
        {on_conflict}
        """,
        rows,
    )
    conn.commit()
