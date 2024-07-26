import unittest
from unittest import mock

from pydantic import ValidationError

from eodag.rest.types import eodag_search, stac_search


class TestStacSearch(unittest.TestCase):
    def test_sortby(self):
        # Test with valid field and direction
        sort_by = stac_search.SortBy(field="test", direction="asc")
        self.assertEqual(sort_by.field, "test")
        self.assertEqual(sort_by.direction, "asc")

        # Test with invalid direction
        with self.assertRaises(ValidationError) as context:
            stac_search.SortBy(field="test", direction="invalid")
        self.assertTrue("Input should be 'asc' or 'desc'" in str(context.exception))

        # Test with empty field
        with self.assertRaises(ValidationError) as context:
            stac_search.SortBy(field="", direction="asc")

    def test_sortby2list(self):
        # Test with no input
        self.assertEqual(stac_search.sortby2list(None), None)

        # Test with valid input
        sortby_list = stac_search.sortby2list("test,+test2,-test3")
        self.assertEqual(len(sortby_list), 3)
        self.assertEqual(sortby_list[0].field, "test")
        self.assertEqual(sortby_list[0].direction, "asc")
        self.assertEqual(sortby_list[1].field, "test2")
        self.assertEqual(sortby_list[1].direction, "asc")
        self.assertEqual(sortby_list[2].field, "test3")
        self.assertEqual(sortby_list[2].direction, "desc")


class TestSearchPostRequest(unittest.TestCase):
    def test_limit(self):
        # Test with positive integer
        try:
            stac_search.SearchPostRequest.model_validate({"limit": 10})
        except ValidationError:
            self.fail("SearchPostRequest raised ValidationError unexpectedly!")

        # Test with non-positive integer
        with self.assertRaises(ValidationError):
            stac_search.SearchPostRequest.model_validate({"limit": -10})

    def test_page(self):
        # Test with positive integer
        try:
            stac_search.SearchPostRequest.model_validate({"page": 10})
        except ValidationError:
            self.fail("SearchPostRequest raised ValidationError unexpectedly!")

        # Test with non-positive integer
        with self.assertRaises(ValidationError):
            stac_search.SearchPostRequest.model_validate({"page": -10})

    def test_check_filter_lang(self):
        # Test with filter and without filter-lang
        values = {"filter": {"test": "value"}}
        search_args = stac_search.SearchPostRequest.model_validate(values).model_dump(
            exclude_none=True
        )
        self.assertEqual(
            search_args, {"filter_lang": "cql2-json", "filter": {"test": "value"}}
        )

        # Test with filter-lang and without filter
        values = {"filter-lang": "cql2-json"}
        with self.assertRaises(ValidationError):
            stac_search.SearchPostRequest.model_validate(values)

        # Test with incorrect filter-lang
        values = {"filter": {"test": "value"}, "filter-lang": "incorrect"}
        with self.assertRaises(ValidationError):
            stac_search.SearchPostRequest.model_validate(values)

        # Test with correct filter and filter-lang
        values = {"filter": {"test": "value"}, "filter-lang": "cql2-json"}
        try:
            stac_search.SearchPostRequest.model_validate(values)
        except ValidationError:
            self.fail("SearchPostRequest raised ValidationError unexpectedly!")

    def test_str_to_str_list(self):
        # Test with string
        values = {"ids": "id1,id2", "collections": "col1,col2"}
        req = stac_search.SearchPostRequest.model_validate(values)
        self.assertEqual(req.ids, ["id1", "id2"])
        self.assertEqual(req.collections, ["col1", "col2"])

        # Test with list of strings
        values = {"ids": ["id1", "id2"], "collections": ["col1", "col2"]}
        req = stac_search.SearchPostRequest.model_validate(values)
        self.assertEqual(req.ids, ["id1", "id2"])
        self.assertEqual(req.collections, ["col1", "col2"])

    def test_validate_spatial(self):
        # Test with both bbox and intersects
        values = {
            "bbox": [-180, -90, 180, 90],
            "intersects": {"type": "Point", "coordinates": [0, 0]},
        }
        with self.assertRaises(ValidationError):
            stac_search.SearchPostRequest.model_validate(values)

        # Test with incorrect geometry
        values = {"intersects": {"type": "Incorrect", "coordinates": [0, 0]}}
        with self.assertRaises(ValidationError):
            stac_search.SearchPostRequest.model_validate(values)

        # Test with correct geometry
        values = {"intersects": {"type": "Point", "coordinates": [0, 0]}}
        try:
            stac_search.SearchPostRequest.model_validate(values)
        except ValidationError:
            self.fail("SearchPostRequest raised ValidationError unexpectedly!")

    def test_validate_bbox(self):
        # Test with incorrect bbox
        values = {"bbox": [180, -90, -180, 90]}
        with self.assertRaises(ValidationError):
            stac_search.SearchPostRequest.model_validate(values)

        # Test with correct bbox
        values = {"bbox": [-180, -90, 180, 90]}
        try:
            stac_search.SearchPostRequest.model_validate(values)
        except ValidationError:
            self.fail("SearchPostRequest raised ValidationError unexpectedly!")

    def test_validate_datetime(self):
        # Test with single datetime
        values = {"datetime": "2023-12-18T19:56:32Z"}
        try:
            stac_search.SearchPostRequest.model_validate(values)
        except ValidationError:
            self.fail("SearchPostRequest raised ValidationError unexpectedly!")

        # Test with datetime interval
        values = {"datetime": "2023-12-18T19:56:32Z/2023-12-19T19:56:32Z"}
        try:
            stac_search.SearchPostRequest.model_validate(values)
        except ValidationError:
            self.fail("SearchPostRequest raised ValidationError unexpectedly!")

        # Test with open datetime interval
        values = {"datetime": "../2023-12-19T19:56:32Z"}
        try:
            stac_search.SearchPostRequest.model_validate(values)
        except ValidationError:
            self.fail("SearchPostRequest raised ValidationError unexpectedly!")

        # Test with both ends of range open
        values = {"datetime": "../.."}
        with self.assertRaises(ValidationError):
            stac_search.SearchPostRequest.model_validate(values)

        # Test with invalid datetime range
        values = {"datetime": "2023-12-19T19:56:32Z/2023-12-18T19:56:32Z"}
        with self.assertRaises(ValidationError):
            stac_search.SearchPostRequest.model_validate(values)

        # Test with invalid datetime
        values = {"datetime": "invalid"}
        with self.assertRaises(ValidationError):
            stac_search.SearchPostRequest.model_validate(values)


class TestEODAGSearch(unittest.TestCase):
    def test_remove_custom_extensions(self):
        values = {"unk:test1": "value", "oseo:test2": "value", "collections": ["value"]}
        self.assertEqual(
            eodag_search.EODAGSearch.model_validate(values).model_dump(
                exclude_none=True
            ),
            {
                "test1": "value",
                "test2": "value",
                "productType": "value",
                "items_per_page": 20,
                "page": 1,
                "raise_errors": False,
            },
        )

    def test_remove_keys(self):
        values = {
            "datetime": "2023-12-18T16:41:35Z",
            "collections": ["value"],
            "bbox": "value",
            "intersects": {"type": "Point", "coordinates": [1, 1]},
            "raise_errors": False,
        }
        self.assertEqual(
            eodag_search.EODAGSearch.model_validate(values).model_dump(
                exclude_none=True
            ),
            {
                "productType": "value",
                "items_per_page": 20,
                "page": 1,
                "raise_errors": False,
            },
        )

    def test_assemble_geom(self):
        values = {
            "geometry": {"type": "Point", "coordinates": [1, 1]},
            "collections": ["value"],
        }
        self.assertEqual(
            eodag_search.EODAGSearch.model_validate(values).model_dump(
                exclude_none=True
            ),
            {
                "geom": {"type": "Point", "coordinates": [1, 1]},
                "productType": "value",
                "items_per_page": 20,
                "page": 1,
                "raise_errors": False,
            },
        )

    def test_convert_collections_to_product_type(self):
        # Test with one collection in collections
        values = {"collections": ["test_collections"], "test": "value"}
        self.assertEqual(
            eodag_search.EODAGSearch.model_validate(values).model_dump(
                exclude_none=True
            ),
            {
                "test": "value",
                "productType": "test_collections",
                "items_per_page": 20,
                "page": 1,
                "raise_errors": False,
            },
        )

        # Test with one collection in collection
        values = {"collections": ["test_collection"], "test": "value"}
        self.assertEqual(
            eodag_search.EODAGSearch.model_validate(values).model_dump(
                exclude_none=True
            ),
            {
                "test": "value",
                "productType": "test_collection",
                "items_per_page": 20,
                "page": 1,
                "raise_errors": False,
            },
        )

        # Test with more than one collection in collections
        values = {"collections": ["value1", "value2"], "test": "value"}
        with self.assertRaises(ValidationError) as context:
            eodag_search.EODAGSearch.model_validate(values)
        self.assertTrue(
            "Only one collection is supported per search" in str(context.exception)
        )

    def test_convert_query_to_dict(self):
        # Test with valid query
        values = {
            "query": {"properties.test": {"eq": "value"}},
            "collections": ["test_collection"],
        }
        self.assertEqual(
            eodag_search.EODAGSearch.model_validate(values).model_dump(
                exclude_none=True
            ),
            {
                "test": "value",
                "productType": "test_collection",
                "items_per_page": 20,
                "page": 1,
                "raise_errors": False,
            },
        )

        # Test with invalid query syntax
        values = {"query": {"invalid": "invalid"}, "collections": ["test_collection"]}
        with self.assertRaises(ValidationError) as context:
            eodag_search.EODAGSearch.model_validate(values)
        self.assertTrue(
            "Exactly 1 operator must be specified per property"
            in str(context.exception)
        )

        # Test with multiple operators for a property
        values = {
            "query": {"properties.test": {"eq": "value", "lte": "value"}},
            "collections": ["test_collection"],
        }
        with self.assertRaises(ValidationError) as context:
            eodag_search.EODAGSearch.model_validate(values)
        self.assertTrue(
            "Exactly 1 operator must be specified per property"
            in str(context.exception)
        )

        # Test with unsupported operator
        values = {
            "query": {"properties.test": {"neq": "value"}},
            "collections": ["test_collection"],
        }
        with self.assertRaises(ValidationError) as context:
            eodag_search.EODAGSearch.model_validate(values)
        self.assertTrue(
            'operator "neq" is not supported for property "test"'
            in str(context.exception)
        )

        # Test with "lte" operator for a non-cloud_cover property
        values = {
            "query": {"properties.test": {"lte": "value"}},
            "collections": ["test_collection"],
        }
        with self.assertRaises(ValidationError) as context:
            eodag_search.EODAGSearch.model_validate(values)
        self.assertTrue(
            'operator "lte" is not supported for property "test"'
            in str(context.exception)
        )

    @mock.patch("eodag.rest.types.eodag_search.EodagEvaluator")
    @mock.patch("eodag.rest.types.eodag_search.parse_json")
    @mock.patch("eodag.rest.types.eodag_search.is_dict_str_any")
    def test_parse_cql(
        self, mock_is_dict_str_any, mock_parse_json, mock_EodagEvaluator
    ):
        # Set up the mock objects
        mock_parse_json.return_value = "parsed_filter"
        mock_EodagEvaluator.return_value.evaluate.return_value = {
            "parsed_result": "parsed_value"
        }
        mock_is_dict_str_any.return_value = True

        # Test with no filter
        values = {"test": "value"}
        expected_result = {"test": "value"}
        self.assertEqual(eodag_search.EODAGSearch.parse_cql(values), expected_result)

        # Test with valid filter
        values = {"filter": "filter", "test": "value"}
        expected_result = {"test": "value", "parsed_result": "parsed_value"}
        self.assertEqual(eodag_search.EODAGSearch.parse_cql(values), expected_result)

        # Test with invalid filter
        values = {"filter": "filter", "test": "value"}
        mock_is_dict_str_any.return_value = False
        with self.assertRaises(ValueError) as context:
            eodag_search.EODAGSearch.parse_cql(values)
        self.assertTrue(
            "The parsed filter is not a proper dictionary" in str(context.exception)
        )

    def test_join_instruments(self):
        # Test with string
        self.assertEqual(
            eodag_search.EODAGSearch.model_validate(
                {"instruments": "value", "collections": ["test_collection"]}
            ).model_dump(exclude_none=True),
            {
                "instrument": "value",
                "productType": "test_collection",
                "items_per_page": 20,
                "page": 1,
                "raise_errors": False,
            },
        )

        # Test with list of strings
        self.assertEqual(
            eodag_search.EODAGSearch.model_validate(
                {
                    "instruments": ["value1", "value2"],
                    "collections": ["test_collection"],
                }
            ).model_dump(exclude_none=True),
            {
                "instrument": "value1,value2",
                "productType": "test_collection",
                "items_per_page": 20,
                "page": 1,
                "raise_errors": False,
            },
        )

    def test_convert_stac_to_eodag_sortby(self):
        values = {
            "sort_by": [{"field": "test", "direction": "desc"}],
            "collections": ["test_collection"],
        }
        self.assertEqual(
            eodag_search.EODAGSearch.model_validate(values).model_dump(
                exclude_none=True
            ),
            {
                "sort_by": [("test", "desc")],
                "productType": "test_collection",
                "items_per_page": 20,
                "page": 1,
                "raise_errors": False,
            },
        )

    def test_verify_producttype_is_present(self):
        # Test with no collections and no collection
        with self.assertRaises(ValidationError) as context:
            eodag_search.EODAGSearch.model_validate({})
        self.assertTrue("A collection is required" in str(context.exception))

        # test with neither collections nor collection but isCatalog
        self.assertEqual(
            eodag_search.EODAGSearch.model_validate(
                {}, context={"isCatalog": True}
            ).model_dump(exclude_none=True),
            {
                "items_per_page": 20,
                "page": 1,
                "raise_errors": False,
            },
        )

    def test_cleanup_dates(self):
        # Test with date ending with "+00:00"
        self.assertEqual(
            eodag_search.EODAGSearch.model_validate(
                {
                    "start": "2023-12-18T16:41:35+00:00",
                    "end": "2023-12-19T16:41:35+00:00",
                    "collections": ["test_collection"],
                }
            ).model_dump(exclude_none=True),
            {
                "start": "2023-12-18T16:41:35Z",
                "end": "2023-12-19T16:41:35Z",
                "productType": "test_collection",
                "items_per_page": 20,
                "page": 1,
                "raise_errors": False,
            },
        )

        # Test with date not ending with "+00:00"
        self.assertEqual(
            eodag_search.EODAGSearch.model_validate(
                {
                    "start": "2023-12-20T16:41:35",
                    "end": "2023-12-21T16:41:35",
                    "collections": ["test_collection"],
                }
            ).model_dump(exclude_none=True),
            {
                "start": "2023-12-20T16:41:35",
                "end": "2023-12-21T16:41:35",
                "productType": "test_collection",
                "items_per_page": 20,
                "page": 1,
                "raise_errors": False,
            },
        )

    def test_alias_to_property(self):
        # Test with valid aliases
        self.assertEqual(
            eodag_search.EODAGSearch.to_eodag("collections"), "productType"
        )
        self.assertEqual(
            eodag_search.EODAGSearch.to_eodag("start_datetime"),
            "startTimeFromAscendingNode",
        )
        self.assertEqual(
            eodag_search.EODAGSearch.to_eodag("platform"),
            "platformSerialIdentifier",
        )

        # Test with invalid alias
        self.assertEqual(
            eodag_search.EODAGSearch.to_eodag("invalid_alias"), "invalid_alias"
        )

        # Test with empty string
        self.assertEqual(eodag_search.EODAGSearch.to_eodag(""), "")

        # Test with alias that has no corresponding property
        self.assertEqual(eodag_search.EODAGSearch.to_eodag("provider"), "provider")
