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
from tempfile import TemporaryDirectory

import pytest

from eodag.utils.exceptions import ValidationError
from tests import TEST_RESOURCES_PATH, mock
from tests.context import SearchResult


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
        cls.criterias = {
            "productType": "S2_MSI_L1C",
            "page": 1,
            "items_per_page": 1,
            "raise_errors": True,
            "cloudCover": "10",
        }
        cls.empty_products = SearchResult([])
        cls.empty_arguments = {}
        cls.empty_criterias = {}

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

    @mock.patch(
        "eodag.rest.utils.eodag_api.list_product_types",
        autospec=True,
        return_value=[{"ID": "S2_MSI_L1C", "abstract": "test"}],
    )
    def test_format_product_types(self, list_pt):
        """format_product_types must return a string representation of the product types"""
        product_types = self.rest_utils.eodag_api.list_product_types(
            fetch_providers=False
        )
        with pytest.warns(
            DeprecationWarning,
            match="Call to deprecated function/method format_product_types",
        ):
            self.assertEqual(
                self.rest_utils.format_product_types(product_types),
                "* *__S2_MSI_L1C__*: test",
            )

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

    def test_get_criterias_from_metadata_mapping(self):
        """get_criterias_from_metadata_mapping must extract search criterias
        from request arguments with metadata_mapping config"""
        metadata_mapping = {
            "doi": [
                '{{"query":{{"sci:doi":{{"eq":"{doi}"}}}}}}',
                '$.properties."sci:doi"',
            ],
            "platform": [
                '{{"query":{{"constellation":{{"eq":"{platform}"}}}}}}',
                "$.properties.constellation",
            ],
            "cloudCover": [
                '{{"query":{{"eo:cloud_cover":{{"lte":"{cloudCover}"}}}}}}',
                '$.properties."eo:cloud_cover"',
            ],
            "productVersion": [
                '{{"query":{{"version":{{"eq":"{productVersion}"}}}}}}',
                "$.properties.version",
            ],
            "id": ['{{"ids":["{id}"]}}', "$.id"],
            "downloadLink": "%(base_uri)s/collections/{productType}/items/{id}",
        }
        arguments = {
            "query": {"eo:cloud_cover": {"lte": "10"}, "foo": {"eq": "bar"}},
        }
        criterias = self.rest_utils.get_criterias_from_metadata_mapping(
            metadata_mapping, arguments
        )
        self.assertEqual(criterias, {"cloudCover": "10", "foo": "bar"})

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
        "eodag.rest.utils.eodag_api.list_product_types",
        autospec=True,
        return_value=[{"ID": "S2_MSI_L1C"}],
    )
    def test_detailled_collections_list(self, list_pt):
        """get_detailled_collections_list returned list is non-empty"""
        self.assertTrue(self.rest_utils.get_detailled_collections_list())
        self.assertTrue(list_pt.called)

    def test_get_geometry(self):
        pass  # TODO

    def test_home_page_content(self):
        """get_home_page_content runs without any error"""
        with pytest.warns(
            DeprecationWarning,
            match="Call to deprecated function/method get_home_page_content",
        ):
            self.rest_utils.get_home_page_content("http://127.0.0.1/")

    def test_get_int(self):
        """get_int must raise a ValidationError for strings that cannot be interpreted as integers"""
        self.rest_utils.get_int("1")
        with self.assertRaises(ValidationError):
            self.rest_utils.get_int("a")

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

    def test_get_pagination_info(self):
        """get_pagination_info must raise a ValidationError if wrong values are given"""
        self.rest_utils.get_pagination_info({})
        with self.assertRaises(ValidationError):
            self.rest_utils.get_pagination_info({"page": "-1"})
        with self.assertRaises(ValidationError):
            self.rest_utils.get_pagination_info({"limit": "-1"})

    def test_get_product_types(self):
        """get_product_types use"""
        self.assertTrue(self.rest_utils.get_product_types())
        self.assertTrue(
            self.rest_utils.get_product_types(filters={"sensorType": "OPTICAL"})
        )

    def test_get_stac_catalogs(self):
        """get_stac_catalogs runs without any error"""
        self.rest_utils.get_stac_catalogs(url="")

    def test_get_stac_collection_by_id(self):
        """get_stac_collection_by_id runs without any error"""
        r = self.rest_utils.get_stac_collection_by_id(
            url="", root="", collection_id="S2_MSI_L1C"
        )
        self.assertIsNotNone(r)
        self.assertEqual(8, len(r["providers"]))
        self.assertEqual(1, r["providers"][0]["priority"])
        self.assertEqual("peps", r["providers"][0]["name"])
        self.assertEqual(["host"], r["providers"][0]["roles"])
        self.assertEqual("https://peps.cnes.fr", r["providers"][0]["url"])
        self.assertTrue(
            r["providers"][0]["description"].startswith(
                'The PEPS platform, the French "mirror site"'
            )
        )

    def test_get_stac_collections(self):
        """get_stac_collections runs without any error"""
        self.rest_utils.get_stac_collections(url="", root="", arguments={})

    def test_get_stac_conformance(self):
        """get_stac_conformance runs without any error"""
        self.rest_utils.get_stac_conformance()

    def test_get_stac_extension_oseo(self):
        """get_stac_extension_oseo runs without any error"""
        self.rest_utils.get_stac_extension_oseo(url="")

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.do_search", autospec=True
    )
    def test_get_stac_item_by_id(self, mock_do_search):
        """get_stac_item_by_id returns None if no StacItem was found"""
        mock_do_search.return_value = [
            {
                "geometry": "POINT (0 0)",
                "properties": {"productIdentifier": "foo", "title": "foo"},
            }
        ]
        self.assertIsNotNone(
            self.rest_utils.get_stac_item_by_id(
                url="", item_id="foo", catalogs=["S2_MSI_L1C"]
            )
        )
        mock_do_search.return_value = []
        self.assertIsNone(
            self.rest_utils.get_stac_item_by_id(
                url="", item_id="", catalogs=["S3_MSI_L1C"]
            )
        )

    def test_get_templates_path(self):
        """get_templates_path returns an existing dir path"""
        with pytest.warns(
            DeprecationWarning,
            match="Call to deprecated function/method get_templates_path",
        ):
            self.assertTrue(os.path.isdir(self.rest_utils.get_templates_path()))

    def test_search_bbox(self):
        pass  # TODO

    def test_search_product_by_id(self):
        pass  # TODO

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.do_search",
        autospec=True,
        return_value=[
            {
                "geometry": "POINT (0 0)",
                "properties": {"productIdentifier": "foo", "title": "foo"},
            }
        ],
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.count_hits",
        autospec=True,
        return_value=1,
    )
    def test_search_products(self, mock_count_hits, mock_do_search):
        """search_products runs without any error"""
        self.rest_utils.search_products("S2_MSI_L1C", {})
        self.rest_utils.search_products("S2_MSI_L1C", {"unserialized": "true"})

        # STAC formatted
        self.rest_utils.search_products(
            "S2_MSI_L1C",
            {
                "intersects": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [0.25, 43.2],
                            [0.25, 43.9],
                            [2.8, 43.9],
                            [2.8, 43.2],
                            [0.25, 43.2],
                        ]
                    ],
                },
                "query": {"eo:cloud_cover": {"lte": 50}},
                "dtstart": "2020-02-01T00:00:00.000Z",
                "dtend": "2021-02-20T00:00:00.000Z",
                "product_type": "S2_MSI_L1C",
                "unserialized": "true",
            },
        )
        call_args, call_kwargs = mock_do_search.call_args
        # check if call_kwargs contains subset
        self.assertLessEqual(
            {
                "productType": "S2_MSI_L1C",
                "cloudCover": 50,
                "startTimeFromAscendingNode": "2020-02-01T00:00:00",
                "completionTimeFromAscendingNode": "2021-02-20T00:00:00",
            }.items(),
            call_kwargs.items(),
        )
        self.assertEqual(call_kwargs["geometry"].bounds, (0.25, 43.2, 2.8, 43.9))

    @mock.patch(
        "eodag.plugins.search.qssearch.PostJsonSearch._request",
        autospec=True,
    )
    def test_search_stac_items_with_stac_providers(self, mock__request):
        """search_stac_items runs without any error with stac providers"""
        # mock the PostJsonSearch request with the S2_MSI_L2A earth_search response search dictionary
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = (
            self.earth_search_resp_search_json
        )
        self.rest_utils.eodag_api.set_preferred_provider("peps")

        response = self.rest_utils.search_stac_items(
            url="http://foo/search",
            arguments={"collections": "S2_MSI_L2A"},
            root="http://foo",
            catalogs=[],
            provider="earth_search",
        )

        mock__request.assert_called()

        # check that default assets have been added to the response
        self.assertTrue(
            "downloadLink", "thumbnail" in response["features"][0]["assets"].keys()
        )
        # check that assets from the provider response search are reformatted in the response
        product_id = self.earth_search_resp_search_json["features"][0]["properties"][
            "sentinel:product_id"
        ]
        for (k, v) in self.earth_search_resp_search_json["features"][0][
            "assets"
        ].items():
            self.assertIn(k, response["features"][0]["assets"].keys())
            self.assertEqual(
                response["features"][0]["assets"][k]["href"],
                f"http://foo/collections/S2_MSI_L2A/items/{product_id}/download/{k}?provider=earth_search",
            )
        # preferred provider should not be changed
        self.assertEqual("peps", self.rest_utils.eodag_api.get_preferred_provider()[0])

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_search_stac_items_with_non_stac_providers(self, mock__request):
        """search_stac_items runs without any error with non-stac providers"""
        # mock the QueryStringSearch request with the S2_MSI_L1C peps response search dictionary
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = self.peps_resp_search_json

        response = self.rest_utils.search_stac_items(
            url="http://foo/search",
            arguments={},
            root="http://foo/",
            catalogs=["S2_MSI_L1C"],
            provider="peps",
        )

        mock__request.assert_called()

        # check that default assets have been added to the response
        self.assertTrue(
            "downloadLink", "thumbnail" in response["features"][0]["assets"].keys()
        )
        # check that no other asset have also been added to the response
        self.assertEqual(len(response["features"][0]["assets"]), 2)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_search_stac_items_get(self, mock__request):
        """search_stac_items runs with GET method"""
        # mock the QueryStringSearch request with the S2_MSI_L1C peps response search dictionary
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = self.peps_resp_search_json

        response = self.rest_utils.search_stac_items(
            url="http://foo/search",
            arguments={"collections": "S2_MSI_L1C"},
            root="http://foo/",
            method="GET",
        )

        mock__request.assert_called()

        next_link = [link for link in response["links"] if link["rel"] == "next"][0]

        self.assertEqual(
            next_link,
            {
                "method": "GET",
                "body": None,
                "rel": "next",
                "href": "http://foo/search?collections=S2_MSI_L1C&page=2",
                "title": "Next page",
                "type": "application/geo+json",
            },
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_search_stac_items_post(self, mock__request):
        """search_stac_items runs with GET method"""
        # mock the QueryStringSearch request with the S2_MSI_L1C peps response search dictionary
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = self.peps_resp_search_json

        response = self.rest_utils.search_stac_items(
            url="http://foo/search",
            arguments={"collections": ["S2_MSI_L1C"], "page": 2},
            root="http://foo/",
            method="POST",
        )

        mock__request.assert_called()

        next_link = [link for link in response["links"] if link["rel"] == "next"][0]

        self.assertEqual(
            next_link,
            {
                "method": "POST",
                "rel": "next",
                "href": "http://foo/search",
                "title": "Next page",
                "type": "application/geo+json",
                "body": {"collections": ["S2_MSI_L1C"], "page": 3},
            },
        )
