import json
import sqlite3
from pathlib import Path
from typing import Any

from model import init_database, load_spatialite, update_collections

CollectionDict = dict[str, Any]


def load_collections_from_file(file_path: Path) -> list[CollectionDict]:
    """Load STAC collections from JSON file.

    Supported JSON shapes:
    - list[dict]
    - {"collections": list[dict]}
    - dict (single collection)
    """
    with file_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        collections = payload
    elif isinstance(payload, dict) and isinstance(payload.get("collections"), list):
        collections = payload["collections"]
    elif isinstance(payload, dict):
        collections = [payload]
    else:
        raise ValueError(f"Unsupported JSON format in {file_path}")

    if not collections:
        raise ValueError(f"No collections found in {file_path}")

    return collections


def run_example_queries(cur: sqlite3.Cursor) -> None:
    """Run a couple of read queries after insert/update."""
    print("\n--- Query Examples ---")

    cur.execute("SELECT COUNT(*) FROM collections;")
    print("Total collections:", cur.fetchone()[0])

    cur.execute(
        """
        SELECT
            key,
            id AS collection_id,
            datetime,
            end_datetime,
            AsGeoJSON(geometry) AS geometry_geojson
        FROM collections
        ORDER BY key
        LIMIT 3;
        """
    )
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    records = [dict(zip(columns, row)) for row in rows]

    for record in records:
        if record.get("geometry_geojson"):
            record["geometry_geojson"] = json.loads(record["geometry_geojson"])

    print(json.dumps(records, indent=2, ensure_ascii=False))


def main() -> None:
    """Initialize database and load collections from collections.json."""
    base_path = Path(__file__).parent
    db_path = base_path / "test_sqlite.db"
    collections_path = base_path / "collections.json"

    conn = sqlite3.connect(str(db_path))
    try:
        load_spatialite(conn)
        init_database(conn)
        print(f"SpatiaLite database initialized at {db_path}")

        collections = load_collections_from_file(collections_path)

        update_collections(conn, collections, upsert=True)
        print(
            f"{len(collections)} STAC collection(s) inserted/updated from {collections_path}"
        )

        run_example_queries(conn.cursor())
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
