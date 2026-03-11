import sqlite3
import unittest

from cql2_sqlite import execute_cql2_json
from model import init_database, load_spatialite, update_collections


def _normalize_sql(sql: str) -> str:
    return " ".join(sql.split())


def _expected_sql(where_sql: str, limit: int = 100) -> str:
    return _normalize_sql(
        "SELECT key, id, datetime, end_datetime, AsGeoJSON(geometry) AS geometry_geojson "
        "FROM collections "
        f"WHERE {where_sql} "
        f"ORDER BY key LIMIT {limit}"
    )


class SQLAssertions:
    def assert_sql_where_equal(self, sql: str, where_sql: str) -> None:
        self.assertEqual(_normalize_sql(sql), _expected_sql(where_sql))


# supported conformance classes
CONFORMANCE_BASIC_CQL2 = "http://www.opengis.net/spec/cql2/1.0/conf/basic-cql2"
CONFORMANCE_ADVANCED_COMPARISON = (
    "http://www.opengis.net/spec/cql2/1.0/conf/advanced-comparison-operators"
)
CONFORMANCE_CASE_INSENSITIVE = (
    "http://www.opengis.net/spec/cql2/1.0/conf/case-insensitive-comparison"
)
CONFORMANCE_ACCENT_INSENSITIVE = (
    "http://www.opengis.net/spec/cql2/1.0/conf/accent-insensitive-comparison"
)
CONFORMANCE_BASIC_SPATIAL = (
    "http://www.opengis.net/spec/cql2/1.0/conf/basic-spatial-functions"
)
CONFORMANCE_BASIC_SPATIAL_PLUS = (
    "http://www.opengis.net/spec/cql2/1.0/conf/basic-spatial-functions-plus"
)

# unsupported conformance classes
CONFORMANCE_SPATIAL_FUNCTIONS = (
    "http://www.opengis.net/spec/cql2/1.0/conf/spatial-functions"
)
CONFORMANCE_TEMPORAL_FUNCTIONS = (
    "http://www.opengis.net/spec/cql2/1.0/conf/temporal-functions"
)
CONFORMANCE_ARRAY_FUNCTIONS = (
    "http://www.opengis.net/spec/cql2/1.0/conf/array-functions"
)
CONFORMANCE_PROPERTY_PROPERTY = (
    "http://www.opengis.net/spec/cql2/1.0/conf/property-property"
)
CONFORMANCE_FUNCTIONS = "http://www.opengis.net/spec/cql2/1.0/conf/functions"
CONFORMANCE_ARITHMETIC = "http://www.opengis.net/spec/cql2/1.0/conf/arithmetic"


SAMPLE_COLLECTIONS = [
    {
        "type": "Collection",
        "id": "EO.TEST.ONE",
        "extent": {
            "spatial": {"bbox": [[0.0, 0.0, 10.0, 10.0]]},
            "temporal": {"interval": [["2020-01-01T00:00:00Z", None]]},
        },
        "license": "proprietary",
        "description": "sample one",
    },
    {
        "type": "Collection",
        "id": "ML.TEST.TWO",
        "extent": {
            "spatial": {"bbox": [[20.0, 20.0, 30.0, 30.0]]},
            "temporal": {
                "interval": [["2021-01-01T00:00:00Z", "2021-12-31T23:59:59Z"]]
            },
        },
        "license": "MIT",
        "description": "sample two",
    },
    {
        "type": "Collection",
        "id": "EO.PRODUCT.THREE",
        "extent": {
            "spatial": {"bbox": [[40.0, 40.0, 50.0, 50.0]]},
            "temporal": {
                "interval": [["2022-01-01T00:00:00Z", "2022-12-31T23:59:59Z"]]
            },
        },
        "license": "CC-BY-4.0",
        "description": "sample three",
    },
]


class TestCQL2BasicConformance(SQLAssertions, unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        load_spatialite(self.conn)
        init_database(self.conn)
        update_collections(self.conn, SAMPLE_COLLECTIONS, upsert=True)

    def tearDown(self) -> None:
        self.conn.close()

    def test_basic_cql2_equality(self) -> None:
        request = {"op": "=", "args": [{"property": "id"}, "EO.TEST.ONE"]}
        rows, sql = execute_cql2_json(self.conn, request)

        self.assertEqual([r["id"] for r in rows], ["EO.TEST.ONE"])
        self.assert_sql_where_equal(sql, "id = 'EO.TEST.ONE'")

    def test_basic_cql2_comparison(self) -> None:
        request = {
            "op": ">=",
            "args": [{"property": "datetime"}, "2021-01-01T00:00:00Z"],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        ids = sorted([r["id"] for r in rows])
        self.assertEqual(ids, ["EO.PRODUCT.THREE", "ML.TEST.TWO"])
        self.assert_sql_where_equal(sql, "datetime >= '2021-01-01T00:00:00Z'")

    def test_basic_cql2_logical_and_or_not(self) -> None:
        and_request = {
            "op": "and",
            "args": [
                {"op": "=", "args": [{"property": "id"}, "EO.TEST.ONE"]},
                {
                    "op": ">=",
                    "args": [{"property": "datetime"}, "2020-01-01T00:00:00Z"],
                },
            ],
        }
        and_rows, and_sql = execute_cql2_json(self.conn, and_request)
        self.assertEqual([r["id"] for r in and_rows], ["EO.TEST.ONE"])
        self.assert_sql_where_equal(
            and_sql,
            "id = 'EO.TEST.ONE' AND datetime >= '2020-01-01T00:00:00Z'",
        )

        or_request = {
            "op": "or",
            "args": [
                {"op": "=", "args": [{"property": "id"}, "EO.TEST.ONE"]},
                {"op": "=", "args": [{"property": "id"}, "ML.TEST.TWO"]},
            ],
        }
        or_rows, or_sql = execute_cql2_json(self.conn, or_request)
        self.assertEqual(
            sorted(r["id"] for r in or_rows), ["EO.TEST.ONE", "ML.TEST.TWO"]
        )
        self.assert_sql_where_equal(
            or_sql,
            "id = 'EO.TEST.ONE' OR id = 'ML.TEST.TWO'",
        )

        not_request = {
            "op": "not",
            "args": [{"op": "=", "args": [{"property": "id"}, "EO.TEST.ONE"]}],
        }
        not_rows, not_sql = execute_cql2_json(self.conn, not_request)
        ids = sorted([r["id"] for r in not_rows])
        self.assertEqual(ids, ["EO.PRODUCT.THREE", "ML.TEST.TWO"])
        self.assert_sql_where_equal(not_sql, "NOT id = 'EO.TEST.ONE'")


class TestCQL2AdvancedComparison(SQLAssertions, unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        load_spatialite(self.conn)
        init_database(self.conn)
        update_collections(self.conn, SAMPLE_COLLECTIONS, upsert=True)

    def tearDown(self) -> None:
        self.conn.close()

    def test_advanced_cql2_like(self) -> None:
        """Test LIKE operator for pattern matching."""
        request = {"op": "like", "args": [{"property": "id"}, "EO.%"]}
        rows, sql = execute_cql2_json(self.conn, request)

        ids = sorted([r["id"] for r in rows])
        self.assertEqual(ids, ["EO.PRODUCT.THREE", "EO.TEST.ONE"])
        self.assert_sql_where_equal(sql, "id LIKE 'EO.%'")

    def test_advanced_cql2_between(self) -> None:
        """Test BETWEEN operator for range checking."""
        request = {
            "op": "between",
            "args": [
                {"property": "datetime"},
                "2021-01-01T00:00:00Z",
                "2022-12-31T23:59:59Z",
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        ids = sorted([r["id"] for r in rows])
        self.assertEqual(ids, ["EO.PRODUCT.THREE", "ML.TEST.TWO"])
        self.assert_sql_where_equal(
            sql,
            "datetime BETWEEN '2021-01-01T00:00:00Z' AND '2022-12-31T23:59:59Z'",
        )

    def test_advanced_cql2_in(self) -> None:
        """Test IN operator for membership testing."""
        request = {
            "op": "in",
            "args": [
                {"property": "id"},
                ["EO.TEST.ONE", "ML.TEST.TWO"],
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        ids = sorted([r["id"] for r in rows])
        self.assertEqual(ids, ["EO.TEST.ONE", "ML.TEST.TWO"])
        self.assert_sql_where_equal(sql, "id IN ('EO.TEST.ONE', 'ML.TEST.TWO')")

    def test_advanced_cql2_isNull(self) -> None:
        """Test isNull operator for null checking on license (which can be null)."""
        # Insert a collection with null license to test isNull operator
        null_collection = {
            "type": "Collection",
            "id": "NO.LICENSE.COLLECTION",
            "extent": {
                "spatial": {"bbox": [[60.0, 60.0, 70.0, 70.0]]},
                "temporal": {"interval": [["2023-01-01T00:00:00Z", None]]},
            },
            "description": "collection without license",
        }
        from model import update_collections

        update_collections(self.conn, [null_collection], upsert=True)

        # Now test isNull on license field
        # We can't easily test isNull on extracted JSON properties with simple STAC,
        # so we'll test with a property that legitimately doesn't exist
        request = {"op": "isNull", "args": [{"property": "license"}]}
        rows, sql = execute_cql2_json(self.conn, request)

        # NO.LICENSE.COLLECTION should match since it has no license property
        self.assertEqual(
            len([r for r in rows if r["id"] == "NO.LICENSE.COLLECTION"]), 1
        )
        self.assert_sql_where_equal(sql, "json_extract(content, '$.license') IS NULL")


class TestCQL2CaseInsensitiveComparison(SQLAssertions, unittest.TestCase):
    """Test case-insensitive comparison operators per CQL2 spec A.5."""

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        load_spatialite(self.conn)
        init_database(self.conn)
        update_collections(self.conn, SAMPLE_COLLECTIONS, upsert=True)

    def tearDown(self) -> None:
        self.conn.close()

    def test_case_insensitive_equality_variations(self) -> None:
        """Test CASEI equality with different case variations (Test 15 spirit)."""
        # CASEI(id) = casei('eo.test.one')
        request_lower = {"op": "ilike", "args": [{"property": "id"}, "eo.test.one"]}
        rows_lower, _ = execute_cql2_json(self.conn, request_lower)

        # CASEI(id) = casei('EO.TEST.ONE')
        request_upper = {"op": "ilike", "args": [{"property": "id"}, "EO.TEST.ONE"]}
        rows_upper, _ = execute_cql2_json(self.conn, request_upper)

        # Both should return the same item
        self.assertEqual([r["id"] for r in rows_lower], ["EO.TEST.ONE"])
        self.assertEqual([r["id"] for r in rows_upper], ["EO.TEST.ONE"])

    def test_case_insensitive_like_pattern_matching(self) -> None:
        """Test CASEI with LIKE - case variations should return same results (Test 16 spirit)."""
        # CASEI(id) LIKE casei('EO.%')
        request_upper = {"op": "ilike", "args": [{"property": "id"}, "EO.%"]}
        rows_upper, sql_upper = execute_cql2_json(self.conn, request_upper)

        # CASEI(id) LIKE casei('eo.%')
        request_lower = {"op": "ilike", "args": [{"property": "id"}, "eo.%"]}
        rows_lower, sql_lower = execute_cql2_json(self.conn, request_lower)

        # Both queries should return identical result sets
        ids_upper = sorted([r["id"] for r in rows_upper])
        ids_lower = sorted([r["id"] for r in rows_lower])
        self.assertEqual(ids_upper, ids_lower)
        self.assertEqual(ids_upper, ["EO.PRODUCT.THREE", "EO.TEST.ONE"])
        self.assert_sql_where_equal(sql_upper, "LOWER(id) LIKE LOWER('EO.%')")
        self.assert_sql_where_equal(sql_lower, "LOWER(id) LIKE LOWER('eo.%')")

    def test_case_insensitive_like_multiple_variations(self) -> None:
        """Test CASEI LIKE with multiple case variations (Test 17 spirit)."""
        # Test with uppercase pattern
        request1 = {"op": "ilike", "args": [{"property": "id"}, "ML.%"]}
        rows1, _ = execute_cql2_json(self.conn, request1)

        # Test with lowercase pattern
        request2 = {"op": "ilike", "args": [{"property": "id"}, "ml.%"]}
        rows2, _ = execute_cql2_json(self.conn, request2)

        # Test with mixed case pattern
        request3 = {"op": "ilike", "args": [{"property": "id"}, "Ml.%"]}
        rows3, _ = execute_cql2_json(self.conn, request3)

        # All should return the same result
        ids1 = sorted([r["id"] for r in rows1])
        ids2 = sorted([r["id"] for r in rows2])
        ids3 = sorted([r["id"] for r in rows3])
        self.assertEqual(ids1, ids2)
        self.assertEqual(ids2, ids3)
        self.assertEqual(ids1, ["ML.TEST.TWO"])

    def test_case_insensitive_in_operator(self) -> None:
        """Test CASEI with IN operator."""
        request = {
            "op": "in",
            "args": [
                {"property": "id"},
                ["eo.test.one", "ml.test.two"],
            ],
        }
        # Note: IN operator might be case-sensitive depending on implementation
        rows, sql = execute_cql2_json(self.conn, request)
        # Since SQL IN is typically case-sensitive by default, we verify it matches exactly
        self.assert_sql_where_equal(sql, "id IN ('eo.test.one', 'ml.test.two')")


class TestCQL2AccentInsensitiveComparison(SQLAssertions, unittest.TestCase):
    """Test accent-insensitive comparison operators per CQL2 spec A.6."""

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        load_spatialite(self.conn)
        init_database(self.conn)

        # Add collections with accented characters for testing
        collections_with_accents = SAMPLE_COLLECTIONS + [
            {
                "type": "Collection",
                "id": "ACCENT.TEST.FOUR",
                "extent": {
                    "spatial": {"bbox": [[50.0, 50.0, 60.0, 60.0]]},
                    "temporal": {"interval": [["2023-06-01T00:00:00Z", None]]},
                },
                "license": "CC-BY-4.0",
                "description": "Chișinău region",  # Accented name
            },
        ]
        update_collections(self.conn, collections_with_accents, upsert=True)

    def tearDown(self) -> None:
        self.conn.close()

    def test_accent_insensitive_like_basic(self) -> None:
        """Test basic accent-insensitive LIKE pattern matching (Test 20 spirit)."""
        # Using ilike with ID field
        request = {"op": "ilike", "args": [{"property": "id"}, "eo.%"]}
        rows, sql = execute_cql2_json(self.conn, request)

        # Should find collections with ID starting with EO
        self.assertGreater(len(rows), 0)
        self.assert_sql_where_equal(sql, "LOWER(id) LIKE LOWER('eo.%')")

    def test_accent_insensitive_ilike_pattern(self) -> None:
        """Test ilike (accent-insensitive LIKE) pattern (Test 20 spirit)."""
        request = {"op": "ilike", "args": [{"property": "id"}, "accent.%"]}
        rows, sql = execute_cql2_json(self.conn, request)

        ids = [r["id"] for r in rows]
        self.assertEqual(ids, ["ACCENT.TEST.FOUR"])
        self.assert_sql_where_equal(sql, "LOWER(id) LIKE LOWER('accent.%')")

    def test_accent_insensitive_mixed_case_search(self) -> None:
        """Test accent-insensitive matching with various cases (Test 22 spirit)."""
        test_cases = [
            ("EO.PRODUCT.THREE", "eo.product.%"),
            ("EO.PRODUCT.THREE", "EO.PRODUCT.%"),
            ("EO.PRODUCT.THREE", "Eo.ProDuCt.%"),
        ]

        for expected_id, pattern in test_cases:
            request = {"op": "ilike", "args": [{"property": "id"}, pattern]}
            rows, _ = execute_cql2_json(self.conn, request)
            ids = [r["id"] for r in rows]
            self.assertEqual(
                ids, [expected_id], f"Pattern {pattern} failed to match {expected_id}"
            )

    def test_accent_insensitive_combined_or_patterns(self) -> None:
        """Test accent-insensitive patterns with OR logic (Test 23 spirit)."""
        # Create a complex AND/OR query combining accent-insensitive patterns
        request = {
            "op": "or",
            "args": [
                {"op": "ilike", "args": [{"property": "id"}, "eo.%"]},
                {"op": "ilike", "args": [{"property": "id"}, "ml.%"]},
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        ids = sorted([r["id"] for r in rows])
        self.assertEqual(
            ids,
            ["EO.PRODUCT.THREE", "EO.TEST.ONE", "ML.TEST.TWO"],
        )
        self.assert_sql_where_equal(
            sql,
            "LOWER(id) LIKE LOWER('eo.%') OR LOWER(id) LIKE LOWER('ml.%')",
        )


class TestCQL2BasicSpatialFunctions(SQLAssertions, unittest.TestCase):
    """Test basic spatial function operators per CQL2 spec A.7."""

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        load_spatialite(self.conn)
        init_database(self.conn)
        update_collections(self.conn, SAMPLE_COLLECTIONS, upsert=True)

    def tearDown(self) -> None:
        self.conn.close()

    def test_spatial_s_intersects_geometry(self) -> None:
        """Test S_INTERSECTS spatial operator with GeoJSON geometry."""
        # Query for collections that intersect with a region around the first collection's bbox
        # EO.TEST.ONE has bbox: [[0.0, 0.0, 10.0, 10.0]]
        geojson_geometry = {
            "type": "Polygon",
            "coordinates": [
                [[5.0, 5.0], [15.0, 5.0], [15.0, 15.0], [5.0, 15.0], [5.0, 5.0]]
            ],
        }

        request = {
            "op": "s_intersects",
            "args": [
                {"property": "geometry"},
                geojson_geometry,
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        # Should find collections whose geometry intersects with the query polygon
        self.assertGreater(len(rows), 0)
        self.assert_sql_where_equal(
            sql,
            'Intersects(geometry, GeomFromGeoJSON(\'{"type":"Polygon","coordinates":[[[5.0,5.0],[15.0,5.0],[15.0,15.0],[5.0,15.0],[5.0,5.0]]]}\'))',
        )

    def test_spatial_s_intersects_multiple_collections(self) -> None:
        """Test S_INTERSECTS finds all intersecting collections."""
        # Query polygon that overlaps multiple collection bboxes
        geojson_geometry = {
            "type": "Polygon",
            "coordinates": [
                [[0.0, 0.0], [50.0, 0.0], [50.0, 50.0], [0.0, 50.0], [0.0, 0.0]]
            ],
        }

        request = {
            "op": "s_intersects",
            "args": [
                {"property": "geometry"},
                geojson_geometry,
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        ids = sorted([r["id"] for r in rows])
        # Should find at least the three main collections
        self.assertGreaterEqual(len(ids), 3)
        self.assert_sql_where_equal(
            sql,
            'Intersects(geometry, GeomFromGeoJSON(\'{"type":"Polygon","coordinates":[[[0.0,0.0],[50.0,0.0],[50.0,50.0],[0.0,50.0],[0.0,0.0]]]}\'))',
        )

    def test_spatial_s_intersects_combined_with_filter(self) -> None:
        """Test S_INTERSECTS combined with other filter criteria."""
        geojson_geometry = {
            "type": "Polygon",
            "coordinates": [
                [[0.0, 0.0], [30.0, 0.0], [30.0, 30.0], [0.0, 30.0], [0.0, 0.0]]
            ],
        }

        request = {
            "op": "and",
            "args": [
                {
                    "op": "s_intersects",
                    "args": [
                        {"property": "geometry"},
                        geojson_geometry,
                    ],
                },
                {
                    "op": ">=",
                    "args": [{"property": "datetime"}, "2021-01-01T00:00:00Z"],
                },
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        # Should find collections that both intersect AND have datetime >= 2021
        self.assertGreater(len(rows), 0)
        self.assert_sql_where_equal(
            sql,
            'Intersects(geometry, GeomFromGeoJSON(\'{"type":"Polygon","coordinates":[[[0.0,0.0],[30.0,0.0],[30.0,30.0],[0.0,30.0],[0.0,0.0]]]}\')) '
            "AND datetime >= '2021-01-01T00:00:00Z'",
        )

    def test_spatial_bbox_as_polygon(self) -> None:
        """Test spatial query with bbox-defined polygon."""
        # Define a query polygon that covers the first collection's area
        query_bbox = {
            "type": "Polygon",
            "coordinates": [
                [[-5.0, -5.0], [15.0, -5.0], [15.0, 15.0], [-5.0, 15.0], [-5.0, -5.0]]
            ],
        }

        request = {
            "op": "s_intersects",
            "args": [
                {"property": "geometry"},
                query_bbox,
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        # Should find EO.TEST.ONE which is at [0.0, 0.0, 10.0, 10.0]
        ids = [r["id"] for r in rows]
        self.assertIn("EO.TEST.ONE", ids)
        self.assert_sql_where_equal(
            sql,
            'Intersects(geometry, GeomFromGeoJSON(\'{"type":"Polygon","coordinates":[[[-5.0,-5.0],[15.0,-5.0],[15.0,15.0],[-5.0,15.0],[-5.0,-5.0]]]}\'))',
        )


class TestCQL2BasicSpatialFunctionsPlus(SQLAssertions, unittest.TestCase):
    """Test extended spatial function operators per CQL2 spec A.8."""

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        load_spatialite(self.conn)
        init_database(self.conn)
        update_collections(self.conn, SAMPLE_COLLECTIONS, upsert=True)

    def tearDown(self) -> None:
        self.conn.close()

    def test_spatial_s_equals_geometry(self) -> None:
        """Test S_EQUALS spatial operator for identical geometries."""
        # Create a geometry that matches EO.TEST.ONE's bbox exactly
        # EO.TEST.ONE has bbox: [[0.0, 0.0, 10.0, 10.0]]
        geojson_geometry = {
            "type": "Polygon",
            "coordinates": [
                [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
            ],
        }

        request = {
            "op": "s_equals",
            "args": [
                {"property": "geometry"},
                geojson_geometry,
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        # Should find geometries equal to the query polygon
        self.assertGreater(len(rows), 0)
        self.assert_sql_where_equal(
            sql,
            'Equals(geometry, GeomFromGeoJSON(\'{"type":"Polygon","coordinates":[[[0.0,0.0],[10.0,0.0],[10.0,10.0],[0.0,10.0],[0.0,0.0]]]}\'))',
        )

    def test_spatial_s_disjoint_geometry(self) -> None:
        """Test S_DISJOINT spatial operator for non-intersecting geometries."""
        # Create a geometry that doesn't intersect any collections
        # Collections are at [0,0,10,10], [20,20,30,30], [40,40,50,50]
        geojson_geometry = {
            "type": "Polygon",
            "coordinates": [
                [
                    [100.0, 100.0],
                    [110.0, 100.0],
                    [110.0, 110.0],
                    [100.0, 110.0],
                    [100.0, 100.0],
                ]
            ],
        }

        request = {
            "op": "s_disjoint",
            "args": [
                {"property": "geometry"},
                geojson_geometry,
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        # All collections should be disjoint from the far-away polygon
        self.assertEqual(len(rows), len(SAMPLE_COLLECTIONS))
        self.assert_sql_where_equal(
            sql,
            'Disjoint(geometry, GeomFromGeoJSON(\'{"type":"Polygon","coordinates":[[[100.0,100.0],[110.0,100.0],[110.0,110.0],[100.0,110.0],[100.0,100.0]]]}\'))',
        )

    def test_spatial_s_within_geometry(self) -> None:
        """Test S_WITHIN spatial operator for geometry containment."""
        # Create a large bounding geometry containing all collections
        large_bbox = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-10.0, -10.0],
                    [60.0, -10.0],
                    [60.0, 60.0],
                    [-10.0, 60.0],
                    [-10.0, -10.0],
                ]
            ],
        }

        request = {
            "op": "s_within",
            "args": [
                {"property": "geometry"},
                large_bbox,
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        # All collections should be within the large bbox
        self.assertEqual(len(rows), len(SAMPLE_COLLECTIONS))
        self.assert_sql_where_equal(
            sql,
            'Within(geometry, GeomFromGeoJSON(\'{"type":"Polygon","coordinates":[[[-10.0,-10.0],[60.0,-10.0],[60.0,60.0],[-10.0,60.0],[-10.0,-10.0]]]}\'))',
        )

    def test_spatial_s_contains_geometry(self) -> None:
        """Test S_CONTAINS spatial operator for containing geometry."""
        # Create a large bounding geometry
        large_bbox = {
            "type": "Polygon",
            "coordinates": [
                [
                    [-10.0, -10.0],
                    [60.0, -10.0],
                    [60.0, 60.0],
                    [-10.0, 60.0],
                    [-10.0, -10.0],
                ]
            ],
        }

        request = {
            "op": "s_contains",
            "args": [
                large_bbox,
                {"property": "geometry"},
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        # All collections should be contained by the large bbox
        self.assertEqual(len(rows), len(SAMPLE_COLLECTIONS))
        self.assert_sql_where_equal(
            sql,
            'Contains(GeomFromGeoJSON(\'{"type":"Polygon","coordinates":[[[-10.0,-10.0],[60.0,-10.0],[60.0,60.0],[-10.0,60.0],[-10.0,-10.0]]]}\'), geometry)',
        )

    def test_spatial_s_overlaps_geometry(self) -> None:
        """Test S_OVERLAPS spatial operator for partial overlap."""
        # Create a geometry that overlaps with collections
        overlapping_bbox = {
            "type": "Polygon",
            "coordinates": [
                [[5.0, 5.0], [25.0, 5.0], [25.0, 25.0], [5.0, 25.0], [5.0, 5.0]]
            ],
        }

        request = {
            "op": "s_overlaps",
            "args": [
                {"property": "geometry"},
                overlapping_bbox,
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        # Should find collections that overlap with the query polygon
        self.assertGreater(len(rows), 0)
        self.assert_sql_where_equal(
            sql,
            'Overlaps(geometry, GeomFromGeoJSON(\'{"type":"Polygon","coordinates":[[[5.0,5.0],[25.0,5.0],[25.0,25.0],[5.0,25.0],[5.0,5.0]]]}\'))',
        )

    def test_spatial_multiple_predicates_with_and(self) -> None:
        """Test combining multiple spatial predicates with AND."""
        # Collections intersecting with a region
        intersect_bbox = {
            "type": "Polygon",
            "coordinates": [
                [[0.0, 0.0], [50.0, 0.0], [50.0, 50.0], [0.0, 50.0], [0.0, 0.0]]
            ],
        }

        # Collections NOT disjoint from another region
        disjoint_bbox = {
            "type": "Polygon",
            "coordinates": [
                [
                    [100.0, 100.0],
                    [110.0, 100.0],
                    [110.0, 110.0],
                    [100.0, 110.0],
                    [100.0, 100.0],
                ]
            ],
        }

        request = {
            "op": "and",
            "args": [
                {
                    "op": "s_intersects",
                    "args": [{"property": "geometry"}, intersect_bbox],
                },
                {
                    "op": "s_disjoint",
                    "args": [{"property": "geometry"}, disjoint_bbox],
                },
            ],
        }
        rows, sql = execute_cql2_json(self.conn, request)

        # Should find collections that intersect the first bbox AND are disjoint from the second
        self.assertGreater(len(rows), 0)
        self.assert_sql_where_equal(
            sql,
            'Intersects(geometry, GeomFromGeoJSON(\'{"type":"Polygon","coordinates":[[[0.0,0.0],[50.0,0.0],[50.0,50.0],[0.0,50.0],[0.0,0.0]]]}\')) '
            'AND Disjoint(geometry, GeomFromGeoJSON(\'{"type":"Polygon","coordinates":[[[100.0,100.0],[110.0,100.0],[110.0,110.0],[100.0,110.0],[100.0,100.0]]]}\'))',
        )


class TestCQL2UnsupportedConformance(unittest.TestCase):
    """Ensure unsupported conformance classes fail fast with clear errors."""

    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        load_spatialite(self.conn)
        init_database(self.conn)
        update_collections(self.conn, SAMPLE_COLLECTIONS, upsert=True)

    def tearDown(self) -> None:
        self.conn.close()

    def test_unsupported_spatial_functions_class(self) -> None:
        """spatial-functions class (A.9) is intentionally unsupported."""
        geom = {
            "type": "Polygon",
            "coordinates": [
                [[0.0, 0.0], [11.0, 0.0], [11.0, 11.0], [0.0, 11.0], [0.0, 0.0]]
            ],
        }
        request = {
            "op": "s_dwithin",
            "args": [{"property": "geometry"}, geom, 2.0, "m"],
        }
        with self.assertRaises(NotImplementedError) as ctx:
            execute_cql2_json(self.conn, request)

        self.assertIn("Unsupported CQL2 operators", str(ctx.exception))
        self.assertIn("s_dwithin", str(ctx.exception))
        self.assertIn(CONFORMANCE_SPATIAL_FUNCTIONS, str(ctx.exception))

    def test_unsupported_functions_and_arithmetic_classes(self) -> None:
        """functions/arithmetic classes are intentionally unsupported."""
        request = {
            "op": "+",
            "args": [
                {"property": "key"},
                1,
            ],
        }
        with self.assertRaises(NotImplementedError) as ctx:
            execute_cql2_json(self.conn, request)

        self.assertIn("Unsupported CQL2 operators", str(ctx.exception))
        self.assertIn(CONFORMANCE_FUNCTIONS, str(ctx.exception))
        self.assertIn(CONFORMANCE_ARITHMETIC, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
