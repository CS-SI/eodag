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

import json
import os
import unittest

from eodag.utils.exceptions import ValidationError
from tests import TEST_RESOURCES_PATH, mock
from tests.context import (
    SearchResult,
    eodag_api,
    filter_products,
    format_product_types,
    get_arguments_query_paths,
    get_criterias_from_metadata_mapping,
    get_date,
    get_datetime,
    get_detailled_collections_list,
    get_home_page_content,
    get_int,
    get_metadata_query_paths,
    get_pagination_info,
    get_product_types,
    get_stac_catalogs,
    get_stac_collection_by_id,
    get_stac_collections,
    get_stac_conformance,
    get_stac_extension_oseo,
    get_stac_item_by_id,
    get_templates_path,
    search_products,
)


class TestStacUtils(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        eodag_api.set_preferred_provider("peps")

    def test_download_stac_item_by_id(self):
        pass  # TODO

    def test_filter_products_unknown_cruncher_raise_error(self):
        """filter_products must raise a ValidationError if an unknown cruncher is given"""
        with self.assertRaises(ValidationError) as context:
            filter_products(self.products, {"filter": "unknown_cruncher"})
        self.assertTrue("unknown filter name" in str(context.exception))

    def test_filter_products_missing_additional_parameters_raise_error(self):
        """filter_products must raise a ValidationError if additional parameters are required by the cruncher"""
        with self.assertRaises(ValidationError) as context:
            filter_products(self.products, {"filter": "latestByName"})
        self.assertTrue("additional parameters required" in str(context.exception))

    def test_filter_products_filter_misuse_raise_error(self):
        """filter_products must raise a ValidationError if the cruncher is not used correctly"""
        with self.assertRaises(ValidationError):
            filter_products(
                self.products,
                {"filter": "latestByName", "name_pattern": "MisconfiguredError"},
            )

    def test_filter_products(self):
        """filter_products returns a SearchResult corresponding to the filter"""
        products_empty_filter = filter_products(self.products, {})
        products_filtered = filter_products(
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
        product_types = eodag_api.list_product_types(fetch_providers=False)
        self.assertEqual(
            format_product_types(product_types), "* *__S2_MSI_L1C__*: test"
        )

    def test_get_arguments_query_paths(self):
        """get_arguments_query_paths must extract the query paths and their values from a request arguments"""
        arguments = {
            "another": "example",
            "query": {"eo:cloud_cover": {"lte": "10"}, "foo": {"eq": "bar"}},
        }
        arguments_query_path = get_arguments_query_paths(arguments)
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
        criterias = get_criterias_from_metadata_mapping(metadata_mapping, arguments)
        self.assertEqual(criterias, {"cloudCover": "10", "foo": "bar"})

    def test_get_date(self):
        """Date validation function must correctly validate dates"""
        get_date("2018-01-01")
        get_date("2018-01-01T")
        get_date("2018-01-01T00:00")
        get_date("2018-01-01T00:00:00")
        get_date("2018-01-01T00:00:00Z")
        get_date("20180101")

        self.assertRaises(ValidationError, get_date, "foo")
        self.assertRaises(ValidationError, get_date, "foo2018-01-01")

        self.assertIsNone(get_date(None))

    def test_get_datetime(self):
        """get_datetime must extract start and end datetime from datetime request args"""
        start = "2021-01-01T00:00:00"
        end = "2021-01-28T00:00:00"

        dtstart, dtend = get_datetime({"datetime": f"{start}/{end}"})
        self.assertEqual(dtstart, start)
        self.assertEqual(dtend, end)

        dtstart, dtend = get_datetime({"datetime": start})
        self.assertEqual(dtstart, start)
        self.assertIsNone(dtend)

        dtstart, dtend = get_datetime({"dtstart": start, "dtend": end})
        self.assertEqual(dtstart, start)
        self.assertEqual(dtend, end)

    @mock.patch(
        "eodag.rest.utils.eodag_api.list_product_types",
        autospec=True,
        return_value=[{"ID": "S2_MSI_L1C"}],
    )
    def test_detailled_collections_list(self, list_pt):
        """get_detailled_collections_list returned list is non-empty"""
        self.assertTrue(get_detailled_collections_list())
        self.assertTrue(list_pt.called)

    def test_get_geometry(self):
        pass  # TODO

    def test_home_page_content(self):
        """get_home_page_content runs without any error"""
        get_home_page_content("http://127.0.0.1/")

    def test_get_int(self):
        """get_int must raise a ValidationError for strings that cannot be interpreted as integers"""
        get_int("1")
        with self.assertRaises(ValidationError):
            get_int("a")

    def test_get_metadata_query_paths(self):
        """get_metadata_query_paths returns query paths from metadata_mapping and their corresponding names"""
        metadata_mapping = {
            "cloudCover": [
                '{{"query":{{"eo:cloud_cover":{{"lte":"{cloudCover}"}}}}}}',
                '$.properties."eo:cloud_cover"',
            ]
        }
        metadata_query_paths = get_metadata_query_paths(metadata_mapping)
        self.assertEqual(
            metadata_query_paths, {"query.eo:cloud_cover.lte": "cloudCover"}
        )

    def test_get_pagination_info(self):
        """get_pagination_info must raise a ValidationError if wrong values are given"""
        get_pagination_info({})
        with self.assertRaises(ValidationError):
            get_pagination_info({"page": "-1"})
        with self.assertRaises(ValidationError):
            get_pagination_info({"limit": "-1"})

    def test_get_product_types(self):
        """get_product_types use"""
        self.assertTrue(get_product_types())
        self.assertTrue(get_product_types(filters={"sensorType": "OPTICAL"}))

    def test_get_stac_catalogs(self):
        """get_stac_catalogs runs without any error"""
        get_stac_catalogs(url="")

    def test_get_stac_collection_by_id(self):
        """get_stac_collection_by_id runs without any error"""
        get_stac_collection_by_id(url="", root="", collection_id="S2_MSI_L1C")

    def test_get_stac_collections(self):
        """get_stac_collections runs without any error"""
        get_stac_collections(url="", root="", arguments={})

    def test_get_stac_conformance(self):
        """get_stac_conformance runs without any error"""
        get_stac_conformance()

    def test_get_stac_extension_oseo(self):
        """get_stac_extension_oseo runs without any error"""
        get_stac_extension_oseo(url="")

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
            get_stac_item_by_id(url="", item_id="foo", catalogs=["S2_MSI_L1C"])
        )
        mock_do_search.return_value = []
        self.assertIsNone(
            get_stac_item_by_id(url="", item_id="", catalogs=["S3_MSI_L1C"])
        )

    def test_get_templates_path(self):
        """get_templates_path returns an existing dir path"""
        self.assertTrue(os.path.isdir(get_templates_path()))

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
    def test_search_products(self, mock_do_search):
        """search_products runs without any error"""
        search_products("S2_MSI_L1C", {})
        search_products("S2_MSI_L1C", {"unserialized": "true"})

    def test_search_stac_items(self):
        pass  # TODO
