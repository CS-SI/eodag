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

from pygeofilter import ast
from pygeofilter.values import Geometry

import eodag.rest.utils.rfc3339 as rfc3339
from eodag.api.product.metadata_mapping import mtd_cfg_as_conversion_and_querypath
from eodag.config import load_stac_provider_config
from eodag.rest.stac import StacCollection
from eodag.rest.types.stac_search import SearchPostRequest
from eodag.rest.utils.cql_evaluate import EodagEvaluator
from eodag.utils import deepcopy
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

        import eodag.rest.core as rest_core

        importlib.reload(rest_core)

        cls.rest_core = rest_core

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

    def test_str2json(self):
        """str2json return a Python dict from a string dict representation"""
        json_dict = self.rest_utils.str2json(
            "collections", '{"collections": ["S1_SAR_GRD"]}'
        )
        self.assertEqual(json_dict, {"collections": ["S1_SAR_GRD"]})

    def test_str2list(self):
        """str2list convert a str variable to a list variable"""
        self.assertIsNone(self.rest_utils.str2list(None))
        self.assertEqual(self.rest_utils.str2list(""), None)
        self.assertEqual(self.rest_utils.str2list("value"), ["value"])
        self.assertEqual(
            self.rest_utils.str2list("value1,value2,value3"),
            ["value1", "value2", "value3"],
        )

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

    def test_flatten_list(self):
        """flatten_list convert list of list to single list"""
        self.assertEqual(
            self.rest_utils.flatten_list([1, 2, [3, 4, [5, 6], 7], 8]),
            [1, 2, 3, 4, 5, 6, 7, 8],
        )
        self.assertEqual(
            self.rest_utils.flatten_list(["a", ["b", ["c", "d"], "e"], "f"]),
            ["a", "b", "c", "d", "e", "f"],
        )
        self.assertEqual(self.rest_utils.flatten_list([1, 2, 3]), [1, 2, 3])
        self.assertEqual(self.rest_utils.flatten_list([]), [])
        self.assertEqual(
            self.rest_utils.flatten_list([1, [2, [3, [4, [5]]]]]), [1, 2, 3, 4, 5]
        )

    def test_list_to_str_list(self):
        """
        list_to_str_list convert a List[Any] to a List[str].
        It raises a TypeError if the convertion cannot be done
        """
        self.assertEqual(self.rest_utils.list_to_str_list([1, 2, 3]), ["1", "2", "3"])
        self.assertEqual(
            self.rest_utils.list_to_str_list(["a", "b", "c"]), ["a", "b", "c"]
        )
        self.assertEqual(
            self.rest_utils.list_to_str_list([1.1, 2.2, 3.3]), ["1.1", "2.2", "3.3"]
        )
        self.assertEqual(self.rest_utils.list_to_str_list([]), [])
        self.assertEqual(
            self.rest_utils.list_to_str_list([1, "2", 3.3, [4, 5]]),
            ["1", "2", "3.3", "[4, 5]"],
        )

    def test_get_next_link_post(self):
        """Verify search next link for POST request"""
        mr = mock_request(url="http://foo/search", body={"page": 2}, method="POST")
        sr = SearchPostRequest.model_validate(mr.json.return_value)

        next_link = self.rest_utils.get_next_link(mr, sr, 100, 20)

        self.assertEqual(
            next_link,
            {
                "rel": "next",
                "href": "http://foo/search",
                "title": "Next page",
                "method": "POST",
                "body": {"page": 3},
                "type": "application/geo+json",
            },
        )

    def test_get_next_link_get(self):
        """Verify search next link for GET request"""
        mr = mock_request("http://foo/search")
        next_link = self.rest_utils.get_next_link(
            mr, SearchPostRequest.model_validate({}), 100, 20
        )

        self.assertEqual(
            next_link,
            {
                "rel": "next",
                "href": "http://foo/search?page=2",
                "title": "Next page",
                "method": "GET",
                "type": "application/geo+json",
            },
        )

    def test_get_date(self):
        """Date validation function must correctly validate dates"""
        self.rest_utils.get_date("2018-01-01")
        self.rest_utils.get_date("2018-01-01T")
        self.rest_utils.get_date("2018-01-01T00:00")
        self.rest_utils.get_date("2018-01-01T00:00:00")
        self.rest_utils.get_date("2018-01-01T00:00:00Z")
        self.rest_utils.get_date("20180101")

        self.assertRaises(ValidationError, self.rest_utils.get_date, "foo")
        self.assertRaises(ValidationError, self.rest_utils.get_date, "foo2018-01-01")

        self.assertIsNone(self.rest_utils.get_date(None))

    def test_get_datetime(self):
        """get_datetime must extract start and end datetime from datetime request args"""
        start = "2021-01-01T00:00:00"
        end = "2021-01-28T00:00:00"

        dtstart, dtend = self.rest_utils.get_datetime({"datetime": f"{start}/{end}"})
        self.assertEqual(dtstart, start)
        self.assertEqual(dtend, end)

        dtstart, dtend = self.rest_utils.get_datetime({"datetime": f"../{end}"})
        self.assertEqual(dtstart, None)
        self.assertEqual(dtend, end)

        dtstart, dtend = self.rest_utils.get_datetime({"datetime": f"{start}/.."})
        self.assertEqual(dtstart, start)
        self.assertEqual(dtend, None)

        dtstart, dtend = self.rest_utils.get_datetime({"datetime": start})
        self.assertEqual(dtstart, start)
        self.assertEqual(dtstart, dtend)

        dtstart, dtend = self.rest_utils.get_datetime({"dtstart": start, "dtend": end})
        self.assertEqual(dtstart, start)
        self.assertEqual(dtend, end)

    @mock.patch(
        "eodag.rest.stac.get_ext_stac_collection",
        autospec=True,
        return_value=json.loads(
            """{
                "new_field":"New Value",
                "title":"A different title for Sentinel 2 MSI Level 1C",
                "summaries": {
                    "instruments": [
                        "MSI"
                    ],
                    "platform": [
                        "SENTINEL-2A",
                        "SENTINEL-2B"
                    ],
                    "constellation": [
                        "Sentinel-2"
                    ],
                    "processing:level": [
                        "L1C"
                    ]
                }
            }"""
        ),
    )
    def test_load_external_product_type_metadata(self, mock_get_ext_stac_collection):
        """Load the supported EODAG metadata from an external STAC collection"""
        product_type_conf = deepcopy(
            self.rest_core.eodag_api.product_types_config["S2_MSI_L1C"]
        )
        ext_stac_collection_path = "/path/to/external/stac/collections/S2_MSI_L1C.json"
        product_type_conf["stacCollection"] = ext_stac_collection_path
        stac_provider_config = load_stac_provider_config()
        parsable_metadata = stac_provider_config["search"]["discover_product_types"][
            "generic_product_type_parsable_metadata"
        ]
        parsable_metadata = mtd_cfg_as_conversion_and_querypath(parsable_metadata)
        enhanced_product_type = StacCollection._load_external_product_type_metadata(
            "S2_MSI_L1C",
            product_type_conf,
            parsable_metadata,
        )
        mock_get_ext_stac_collection.assert_called_with(ext_stac_collection_path)
        # Fields not supported by EODAG
        self.assertNotIn("new_field", enhanced_product_type)
        # Merge lists
        self.assertEqual(
            "S2A,S2B,SENTINEL-2A,SENTINEL-2B",
            enhanced_product_type["platformSerialIdentifier"],
        )
        # Don't override existings keys
        self.assertEqual("SENTINEL2 Level-1C", enhanced_product_type["title"])
        # The parameter passed `_load_external_product_type_metadata` is not modified
        del product_type_conf["stacCollection"]
        self.assertDictEqual(
            product_type_conf,
            self.rest_core.eodag_api.product_types_config["S2_MSI_L1C"],
        )

    def test_fetch_external_stac_collections(self):
        """Load external STAC collections"""
        external_json = """{
            "new_field":"New Value",
            "title":"A different title for Sentinel 2 MSI Level 1C",
            "keywords":["New Keyword"]
        }"""
        product_type_conf = self.rest_core.eodag_api.product_types_config["S2_MSI_L1C"]
        ext_stac_collection_path = "/path/to/external/stac/collections/S2_MSI_L1C.json"
        product_type_conf["stacCollection"] = ext_stac_collection_path

        with mock.patch(
            "eodag.rest.stac.get_ext_stac_collection", autospec=True
        ) as mock_stac_get_ext_stac_collection:
            mock_stac_get_ext_stac_collection.return_value = json.loads(external_json)

            # Check if the returned STAC collection contains updated data
            StacCollection.fetch_external_stac_collections(self.rest_core.eodag_api)
            stac_coll = self.rest_core.get_stac_collection_by_id(
                url="", root="", collection_id="S2_MSI_L1C"
            )
            mock_stac_get_ext_stac_collection.assert_called_with(
                ext_stac_collection_path
            )
            # New field
            self.assertIn("new_field", stac_coll)
            # Merge keywords
            self.assertListEqual(
                ["MSI", "SENTINEL2", "S2A,S2B", "L1", "OPTICAL", "New Keyword"],
                stac_coll["keywords"],
            )
            # Override existing fields
            self.assertEqual(
                "A different title for Sentinel 2 MSI Level 1C", stac_coll["title"]
            )
            # Restore previous state
            StacCollection.ext_stac_collections.clear()


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
        self.assertEqual(self.evaluator.temporal(dt), dt.strftime("%Y-%m-%dT%H:%M:%SZ"))

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
                ast.GeometryIntersects(ast.Attribute("geometry"), value),
                ast.Attribute("geometry"),
                value,
            ),
            {"geometry": "value"},
        )
        with self.assertRaises(ValueError) as context:
            self.evaluator.predicate(
                ast.GeometryIntersects(attribute, value),
                attribute,
                value,
            )
        self.assertTrue(
            'operator INTERSECTS is not supported for property "test"'
            in str(context.exception)
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
        self.assertEqual(
            self.evaluator.contains(
                ast.In(attribute, ["value1", "value2"], False),
                attribute,
                "value1",
                "value2",
            ),
            {"test": ["value1", "value2"]},
        )
        with self.assertRaises(ValueError) as context:
            self.evaluator.contains(
                ast.In(attribute, "value1", False), attribute, "value1"
            )
        self.assertTrue(
            'property "test" expects a value in list format with operator "in"'
            in str(context.exception)
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
