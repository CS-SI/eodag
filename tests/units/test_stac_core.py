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

from eodag.rest.types.stac_search import SearchPostRequest
from eodag.utils.exceptions import ValidationError
from tests import TEST_RESOURCES_PATH, mock
from tests.context import SearchResult
from tests.utils import mock_request


class TestStacCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestStacCore, cls).setUpClass()

        # Mock home and eodag conf directory to tmp dir
        cls.tmp_home_dir = TemporaryDirectory()
        cls.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=cls.tmp_home_dir.name
        )
        cls.expanduser_mock.start()

        # import after having mocked home_dir because it launches http server (and EODataAccessGateway)
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
        super(TestStacCore, cls).tearDownClass()
        # stop Mock and remove tmp config dir
        cls.expanduser_mock.stop()
        cls.tmp_home_dir.cleanup()
        # stop os.environ
        cls.mock_os_environ.stop()

    def test_crunch_products_unknown_cruncher_raise_error(self):
        """crunch_products must raise a ValidationError if an unknown cruncher is given"""
        with self.assertRaises(ValidationError) as context:
            self.rest_core.crunch_products(self.products, "unknown_cruncher")
        self.assertTrue("Unknown crunch name" in str(context.exception))

    def test_crunch_products_missing_additional_parameters_raise_error(self):
        """crunch_products must raise a ValidationError if additional parameters are required by the cruncher"""
        with self.assertRaises(ValidationError) as context:
            self.rest_core.crunch_products(self.products, "filterLatestByName")
        self.assertTrue("require additional parameters" in str(context.exception))

    def test_crunch_products_filter_misuse_raise_error(self):
        """crunch_products must raise a ValidationError if the cruncher is not used correctly"""
        with self.assertRaises(ValidationError):
            self.rest_core.crunch_products(
                self.products,
                "filterLatestByName",
                **{"name_pattern": "MisconfiguredError"},
            )

    def test_crunch_products(self):
        """crunch_products returns a SearchResult corresponding to the filter"""
        products_filtered = self.rest_core.crunch_products(
            self.products,
            "filterLatestByName",
            **{"name_pattern": r"S2[AB]_MSIL1C_20(?P<tileid>\d{6}).*T21NY.*"},
        )
        self.assertNotEqual(self.products, products_filtered)

    @mock.patch(
        "eodag.rest.core.eodag_api.list_product_types",
        autospec=True,
        return_value=[{"ID": "S2_MSI_L1C", "abstract": "test"}],
    )
    def test_format_product_types(self, list_pt):
        """format_product_types must return a string representation of the product types"""
        product_types = self.rest_core.eodag_api.list_product_types(
            fetch_providers=False
        )
        with pytest.warns(
            DeprecationWarning,
            match="Call to deprecated function/method format_product_types",
        ):
            self.assertEqual(
                self.rest_core.format_product_types(product_types),
                "* *__S2_MSI_L1C__*: test",
            )

    @mock.patch(
        "eodag.rest.core.eodag_api.list_product_types",
        autospec=True,
        return_value=[{"ID": "S2_MSI_L1C"}],
    )
    def test_detailled_collections_list(self, list_pt):
        """get_detailled_collections_list returned list is non-empty"""
        self.assertTrue(self.rest_core.get_detailled_collections_list())
        self.assertTrue(list_pt.called)

    def test_get_geometry(self):
        pass  # TODO

    def test_home_page_content(self):
        """get_home_page_content runs without any error"""
        with pytest.warns(
            DeprecationWarning,
            match="Call to deprecated function/method get_home_page_content",
        ):
            self.rest_core.get_home_page_content("http://127.0.0.1/")

    def test_get_product_types(self):
        """get_product_types use"""
        self.assertTrue(self.rest_core.get_product_types())
        self.assertTrue(
            self.rest_core.get_product_types(filters={"sensorType": "OPTICAL"})
        )

    def test_get_stac_catalogs(self):
        """get_stac_catalogs runs without any error"""
        self.rest_core.get_stac_catalogs(url="")

    def test_get_stac_collection_by_id(self):
        """get_stac_collection_by_id runs without any error"""
        r = self.rest_core.get_stac_collection_by_id(
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
        self.rest_core.get_stac_collections(url="", root="", arguments={})

    def test_get_stac_conformance(self):
        """get_stac_conformance runs without any error"""
        self.rest_core.get_stac_conformance()

    def test_get_stac_extension_oseo(self):
        """get_stac_extension_oseo runs without any error"""
        self.rest_core.get_stac_extension_oseo(url="")

    def test_search_bbox(self):
        pass  # TODO

    def test_search_product_by_id(self):
        pass  # TODO

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
        self.rest_core.eodag_api.set_preferred_provider("peps")

        response = self.rest_core.search_stac_items(
            request=mock_request("http://foo/search"),
            search_request=SearchPostRequest.model_validate(
                {"collections": "S2_MSI_L2A", "provider": "earth_search"}
            ),
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
        for k, v in self.earth_search_resp_search_json["features"][0]["assets"].items():
            self.assertIn(k, response["features"][0]["assets"].keys())
            self.assertEqual(
                response["features"][0]["assets"][k]["href"],
                f"http://foo/collections/S2_MSI_L2A/items/{product_id}/download/{k}?provider=earth_search",
            )
        # preferred provider should not be changed
        self.assertEqual("peps", self.rest_core.eodag_api.get_preferred_provider()[0])

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request",
        autospec=True,
    )
    def test_search_stac_items_with_non_stac_providers(self, mock__request):
        """search_stac_items runs without any error with non-stac providers"""
        # mock the QueryStringSearch request with the S2_MSI_L1C peps response search dictionary
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = self.peps_resp_search_json

        response = self.rest_core.search_stac_items(
            request=mock_request("http://foo/search"),
            search_request=SearchPostRequest.model_validate({"provider": "peps"}),
            catalogs=["S2_MSI_L1C"],
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

        response = self.rest_core.search_stac_items(
            request=mock_request("http://foo/search?collections=S2_MSI_L1C"),
            search_request=SearchPostRequest.model_validate(
                {"collections": ["S2_MSI_L1C"]}
            ),
        )

        mock__request.assert_called()

        next_link = [link for link in response["links"] if link["rel"] == "next"][0]

        self.assertEqual(
            next_link,
            {
                "method": "GET",
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

        response = self.rest_core.search_stac_items(
            request=mock_request(
                url="http://foo/search",
                method="POST",
                body={"collections": ["S2_MSI_L1C"], "page": "2"},
            ),
            search_request=SearchPostRequest.model_validate(
                {"collections": ["S2_MSI_L1C"], "page": "2"}
            ),
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

    def test_get_templates_path(self):
        """get_templates_path returns an existing dir path"""
        with pytest.warns(
            DeprecationWarning,
            match="Call to deprecated function/method get_templates_path",
        ):
            self.assertTrue(os.path.isdir(self.rest_core.get_templates_path()))
