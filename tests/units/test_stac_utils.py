# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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

import importlib
import json
import os
import unittest
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus, unquote_plus

import orjson
import pytest
from pygeofilter import ast
from pygeofilter.values import Geometry

import eodag.rest.utils.rfc3339 as rfc3339
from eodag.rest.types.stac_search import SearchPostRequest
from eodag.rest.utils.cql_evaluate import EodagEvaluator
from eodag.utils.exceptions import ValidationError
from tests import TEST_RESOURCES_PATH, mock
from tests.context import SearchResult
from tests.utils import mock_request


class TestStacUtils(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestStacUtils, cls).setUpClass()

        # Mock home and eodag conf directory to tmp dir
        cls.tmp_home_dir = TemporaryDirectory()
        cls.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=cls.tmp_home_dir.name
        )
        cls.expanduser_mock.start()

        # import after having mocked home_dir because it launches http server (and EODataAccessGateway)
        import eodag.rest.utils as rest_utils

        importlib.reload(rest_utils)

        cls.rest_utils = rest_utils

        search_results_file = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_peps.geojson"
        )
        with open(search_results_file, encoding="utf-8") as f:
            search_results_geojson = json.load(f)
        cls.products = SearchResult.from_geojson(search_results_geojson)
        cls.arguments = {
            "query": {"eo:cloud_cover": {"lte": "10"}},
            "filter": "latestIntersect",
        }
        cls.criteria = {
            "productType": "S2_MSI_L1C",
            "page": 1,
            "items_per_page": 1,
            "raise_errors": True,
            "cloudCover": "10",
        }
        cls.empty_products = SearchResult([])
        cls.empty_arguments = {}
        cls.empty_criteria = {}

        # mock os.environ to empty env
        cls.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        cls.mock_os_environ.start()

        # disable product types fetch
        os.environ["EODAG_EXT_PRODUCT_TYPES_CFG_FILE"] = ""

        # create a dictionary obj of a S2_MSI_L1C peps response search
        peps_resp_search_file = os.path.join(
            TEST_RESOURCES_PATH, "provider_responses", "peps_search.json"
        )
        with open(peps_resp_search_file, encoding="utf-8") as f:
            cls.peps_resp_search_json = json.load(f)

        # create a dictionary obj of a S2_MSI_L2A earth_search response search
        earth_search_resp_search_file = os.path.join(
            TEST_RESOURCES_PATH, "provider_responses", "earth_search_search.json"
        )
        with open(earth_search_resp_search_file, encoding="utf-8") as f:
            cls.earth_search_resp_search_json = json.load(f)

    @classmethod
    def tearDownClass(cls):
        super(TestStacUtils, cls).tearDownClass()
        # stop Mock and remove tmp config dir
        cls.expanduser_mock.stop()
        cls.tmp_home_dir.cleanup()
        # stop os.environ
        cls.mock_os_environ.stop()

    def test_filter_products_unknown_cruncher_raise_error(self):
        """filter_products must raise a ValidationError if an unknown cruncher is given"""
        with self.assertRaises(ValidationError) as context:
            self.rest_utils.filter_products(
                self.products, {"filter": "unknown_cruncher"}
            )
        self.assertTrue("unknown filter name" in str(context.exception))

    def test_filter_products_missing_additional_parameters_raise_error(self):
        """filter_products must raise a ValidationError if additional parameters are required by the cruncher"""
        with self.assertRaises(ValidationError) as context:
            self.rest_utils.filter_products(self.products, {"filter": "latestByName"})
        self.assertTrue("additional parameters required" in str(context.exception))

    def test_filter_products_filter_misuse_raise_error(self):
        """filter_products must raise a ValidationError if the cruncher is not used correctly"""
        with self.assertRaises(ValidationError):
            self.rest_utils.filter_products(
                self.products,
                {"filter": "latestByName", "name_pattern": "MisconfiguredError"},
            )

    def test_filter_products(self):
        """filter_products returns a SearchResult corresponding to the filter"""
        products_empty_filter = self.rest_utils.filter_products(self.products, {})
        products_filtered = self.rest_utils.filter_products(
            self.products,
            {
                "filter": "latestByName",
                "name_pattern": r"S2[AB]_MSIL1C_20(?P<tileid>\d{6}).*T21NY.*",
            },
        )
        self.assertEqual(self.products, products_empty_filter)
        self.assertNotEqual(self.products, products_filtered)

    def test_get_arguments_query_paths(self):
        """get_arguments_query_paths must extract the query paths and their values from a request arguments"""
        arguments = {
            "another": "example",
            "query": {"eo:cloud_cover": {"lte": "10"}, "foo": {"eq": "bar"}},
        }
        arguments_query_path = self.rest_utils.get_arguments_query_paths(arguments)
        self.assertEqual(
            arguments_query_path,
            {"query.eo:cloud_cover.lte": "10", "query.foo.eq": "bar"},
        )

    def test_get_metadata_query_paths(self):
        """get_metadata_query_paths returns query paths from metadata_mapping and their corresponding names"""
        metadata_mapping = {
            "cloudCover": [
                '{{"query":{{"eo:cloud_cover":{{"lte":"{cloudCover}"}}}}}}',
                '$.properties."eo:cloud_cover"',
            ]
        }
        metadata_query_paths = self.rest_utils.get_metadata_query_paths(
            metadata_mapping
        )
        self.assertEqual(
            metadata_query_paths, {"query.eo:cloud_cover.lte": "cloudCover"}
        )

    def test_str2json(self):
        """str2json return a Python dict from a string dict representation"""
        json_dict = self.rest_utils.str2json(
            "collections", '{"collections": ["S1_SAR_GRD"]}'
        )
        self.assertEqual(json_dict, {"collections": ["S1_SAR_GRD"]})

        # key without value
        self.assertIsNone(self.rest_utils.str2json("key_without_value"))

        json_obj = {"key": "value with spaces"}
        json_str_quoted = quote_plus(orjson.dumps(json_obj).decode())
        json_str_unquoted = unquote_plus(json_str_quoted)
        self.assertEqual(
            self.rest_utils.str2json("key", json_str_quoted),
            orjson.loads(json_str_unquoted),
        )

        with pytest.raises(ValidationError) as exc_info:
            self.rest_utils.str2json("key", "invalid json")
            self.assertEqual("key: Incorrect JSON object", str(exc_info.value))

    def test_str2list(self):
        """str2list convert a str variable to a list variable"""
        self.assertIsNone(self.rest_utils.str2list(None))
        self.assertEqual(self.rest_utils.str2list(""), None)
        self.assertEqual(self.rest_utils.str2list("value"), ["value"])
        self.assertEqual(
            self.rest_utils.str2list("value1,value2,value3"),
            ["value1", "value2", "value3"],
        )

    def test_is_list_str(self):
        """is_list_str verifies whether the input variable is of type List[str]"""
        self.assertTrue(self.rest_utils.is_list_str(["value1", "value2", "value3"]))
        self.assertFalse(self.rest_utils.is_list_str(["value1", 2, "value3"]))
        self.assertFalse(self.rest_utils.is_list_str("not a list"))
        self.assertFalse(self.rest_utils.is_list_str(None))

    def test_is_dict_str_any(self):
        """is_dict_str_any verifies whether the input variable is of type Dict[str, Any]"""
        self.assertTrue(
            self.rest_utils.is_dict_str_any({"key1": "value1", "key2": "value2"})
        )
        self.assertTrue(
            self.rest_utils.is_dict_str_any({"key1": 123, "key2": [1, 2, 3]})
        )
        self.assertFalse(
            self.rest_utils.is_dict_str_any({123: "value1", "key2": "value2"})
        )
        self.assertFalse(self.rest_utils.is_dict_str_any("not a dict"))
        self.assertFalse(self.rest_utils.is_dict_str_any(None))

    def test_get_next_link_post(self):
        """Verify search next link for POST request"""
        mr = mock_request(url="http://foo/search", body={"page": 2}, method="POST")
        sr = SearchPostRequest.model_validate(mr.json.return_value)

        next_link, next_body = self.rest_utils.get_next_link(mr, sr)

        self.assertEqual(next_link, "http://foo/search")
        self.assertEqual(next_body, {"page": 3})

    def test_get_next_link_get(self):
        """Verify search next link for GET request"""
        mr = mock_request("http://foo/search")
        next_link, next_body = self.rest_utils.get_next_link(
            mr, SearchPostRequest.model_validate({})
        )

        self.assertEqual(next_link, "http://foo/search?page=2")
        self.assertIsNone(next_body)


class TestEodagCql2jsonEvaluator(unittest.TestCase):
    def setUp(self):
        self.evaluator = EodagEvaluator()

    def test_attribute(self):
        self.assertEqual(self.evaluator.attribute("test"), "test")
        self.assertEqual(
            self.evaluator.attribute(ast.Attribute("test")), ast.Attribute("test")
        )
        self.assertEqual(self.evaluator.attribute(123), 123)
        self.assertEqual(self.evaluator.attribute(123.456), 123.456)

    def test_spatial(self):
        geometry = Geometry({"type": "Point", "coordinates": [125.6, 10.1]})
        self.assertEqual(
            self.evaluator.spatial(geometry),
            {"type": "Point", "coordinates": [125.6, 10.1]},
        )

    def test_temporal(self):
        dt = datetime.now()
        self.assertEqual(self.evaluator.temporal(dt), dt.isoformat())

    def test_interval(self):
        result = self.evaluator.interval(None, "value1", "value2")
        self.assertEqual(result, ["value1", "value2"])

    def test_predicate(self):
        attribute = ast.Attribute("test")
        value = "value"
        self.assertEqual(
            self.evaluator.predicate(ast.Equal(attribute, value), attribute, value),
            {"test": "value"},
        )
        self.assertEqual(
            self.evaluator.predicate(
                ast.GeometryIntersects(attribute, value), attribute, value
            ),
            {"test": "value"},
        )
        self.assertEqual(
            self.evaluator.predicate(
                ast.LessEqual(attribute, datetime(2022, 1, 1)),
                attribute,
                datetime(2022, 1, 1),
            ),
            {"end_datetime": datetime(2022, 1, 1)},
        )
        self.assertEqual(
            self.evaluator.predicate(
                ast.GreaterEqual(attribute, datetime(2022, 1, 1)),
                attribute,
                datetime(2022, 1, 1),
            ),
            {"start_datetime": datetime(2022, 1, 1)},
        )
        self.assertEqual(
            self.evaluator.predicate(
                ast.TimeOverlaps(
                    attribute, [datetime(2022, 1, 1), datetime(2022, 12, 31)]
                ),
                attribute,
                [datetime(2022, 1, 1), datetime(2022, 12, 31)],
            ),
            {
                "start_datetime": datetime(2022, 1, 1),
                "end_datetime": datetime(2022, 12, 31),
            },
        )

    def test_contains(self):
        attribute = ast.Attribute("test")
        sub_nodes = ["value1", "value2"]
        self.assertEqual(
            self.evaluator.contains(
                ast.In(attribute, sub_nodes, False), attribute, "value1", "value2"
            ),
            {"test": ["value1", "value2"]},
        )

    def test_combination(self):
        self.assertEqual(
            self.evaluator.combination(None, {"key1": "value1"}, {"key2": "value2"}),
            {"key1": "value1", "key2": "value2"},
        )


class TestRfc3339(unittest.TestCase):
    def test_rfc3339_str_to_datetime(self):
        test_str = "2023-12-18T16:41:35Z"
        expected_result = datetime(2023, 12, 18, 16, 41, 35, tzinfo=timezone.utc)
        self.assertEqual(rfc3339.rfc3339_str_to_datetime(test_str), expected_result)

    def test_str_to_interval(self):
        test_str = "2023-12-18T16:41:35Z/2023-12-19T16:41:35Z"
        expected_result = (
            datetime(2023, 12, 18, 16, 41, 35, tzinfo=timezone.utc),
            datetime(2023, 12, 19, 16, 41, 35, tzinfo=timezone.utc),
        )
        self.assertEqual(rfc3339.str_to_interval(test_str), expected_result)

    def test_now_in_utc(self):
        now = rfc3339.now_in_utc()
        self.assertEqual(now.tzinfo, timezone.utc)

    def test_now_to_rfc3339_str(self):
        now = rfc3339.now_in_utc()
        now_str = rfc3339.now_to_rfc3339_str()
        now_from_str = datetime.fromisoformat(now_str.replace("Z", "+00:00"))
        time_diff = now - now_from_str
        self.assertTrue(abs(time_diff.total_seconds()) < 1)
