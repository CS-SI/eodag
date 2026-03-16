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
from unittest import mock

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import OFFLINE_STATUS, ONLINE_STATUS
from tests.units.search_plugins.base import BaseSearchPluginTest


class TestSearchPluginGeodesSearch(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginGeodesSearch, self).setUp()
        self.provider = "geodes"
        self.search_plugin = self.get_search_plugin(provider=self.provider)

    def test_plugins_search_geodes_plugin_class(self):
        """The geodes provider must use the GeodesSearch plugin"""
        from eodag.plugins.search import GeodesSearch

        self.assertIsInstance(self.search_plugin, GeodesSearch)

    def _build_product(
        self, identifier, checksum, endpoint_url="https://geodes.example/data"
    ):
        download_link = f"https://geodes.example/data/{identifier}/file_{checksum}.tif"
        product = EOProduct(
            self.provider,
            {
                "id": identifier,
                "geometry": "POINT (0 0)",
                "geodes:endpoint_url": endpoint_url,
            },
        )
        product.assets.update({"download_link": {"href": download_link}})
        return product

    @mock.patch(
        "eodag.plugins.search.qssearch.geodessearch.GeodesSearch._request",
        autospec=True,
    )
    def test_plugins_search_geodes_get_availability(self, mock__request):
        """_get_availability must POST to the fastavailability endpoint with the
        download_link and endpoint_url for each product"""
        mock_response = mock.Mock()
        mock_response.json.return_value = {"products": []}
        mock__request.return_value = mock_response

        p1 = self._build_product("PROD1", "abc")
        p2 = self._build_product("PROD2", "def")

        result = self.search_plugin._get_availability([p1, p2])

        self.assertEqual(result, {"products": []})
        self.assertEqual(mock__request.call_count, 1)
        prep = mock__request.call_args.args[1]
        # url must be derived from api_endpoint (replacing api/stac/search by fastavailability)
        self.assertEqual(
            prep.url,
            self.search_plugin.config.api_endpoint.replace(
                "api/stac/search", "fastavailability"
            ),
        )
        self.assertEqual(
            prep.query_params,
            {
                "availability": [
                    {
                        "href": p1.assets.get("download_link", {}).get("href"),
                        "endpointURL": "https://geodes.example/data",
                    },
                    {
                        "href": p2.assets.get("download_link", {}).get("href"),
                        "endpointURL": "https://geodes.example/data",
                    },
                ]
            },
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.geodessearch.GeodesSearch._request",
        autospec=True,
    )
    def test_plugins_search_geodes_get_availability_skips_missing_fields(
        self, mock__request
    ):
        """Products without eodag:download_link or geodes:endpoint_url must be skipped
        in the availability request body"""
        mock_response = mock.Mock()
        mock_response.json.return_value = {"products": []}
        mock__request.return_value = mock_response

        p_ok = self._build_product("PROD1", "abc")
        p_no_url = EOProduct(
            self.provider,
            {
                "id": "PROD2",
                "geometry": "POINT (0 0)",
                "eodag:download_link": "https://geodes.example/data/PROD2/file.tif",
            },
        )
        p_no_link = EOProduct(
            self.provider,
            {
                "id": "PROD3",
                "geometry": "POINT (0 0)",
                "geodes:endpoint_url": "https://geodes.example/data",
            },
        )

        self.search_plugin._get_availability([p_ok, p_no_url, p_no_link])

        prep = mock__request.call_args.args[1]
        self.assertEqual(len(prep.query_params["availability"]), 1)
        self.assertEqual(
            prep.query_params["availability"][0]["href"],
            p_ok.assets.get("download_link", {}).get("href"),
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.geodessearch.GeodesSearch._get_availability",
        autospec=True,
    )
    def test_plugins_search_geodes_set_availability_online(self, mock_get_availability):
        """_set_availability must set order:status to ONLINE when asset is available"""
        product = self._build_product("PROD1", "abc")
        mock_get_availability.return_value = {
            "products": [
                {
                    "id": "PROD1",
                    "files": [{"checksum": "abc", "available": True}],
                }
            ]
        }

        self.search_plugin._set_availability([product])

        self.assertEqual(
            product.assets.get("download_link", {}).get("order:status"), ONLINE_STATUS
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.geodessearch.GeodesSearch._get_availability",
        autospec=True,
    )
    def test_plugins_search_geodes_set_availability_offline(
        self, mock_get_availability
    ):
        """_set_availability must set order:status to OFFLINE when asset is not available"""
        product = self._build_product("PROD1", "abc")
        mock_get_availability.return_value = {
            "products": [
                {
                    "id": "PROD1",
                    "files": [{"checksum": "abc", "available": False}],
                }
            ]
        }

        self.search_plugin._set_availability([product])
        self.assertEqual(
            product.assets.get("download_link", {}).get("order:status"), OFFLINE_STATUS
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.geodessearch.GeodesSearch._get_availability",
        autospec=True,
    )
    def test_plugins_search_geodes_set_availability_no_match(
        self, mock_get_availability
    ):
        """When no matching product/asset is found in the availability response,
        order:status must be left unchanged and a warning must be logged"""
        product = self._build_product("PROD1", "abc")
        product.properties["order:status"] = "untouched"
        # no matching id in response
        mock_get_availability.return_value = {"products": []}

        with self.assertLogs(
            "eodag.search.qssearch.geodes", level="WARNING"
        ) as log_ctx:
            self.search_plugin._set_availability([product])

        self.assertEqual(product.properties["order:status"], "untouched")
        self.assertTrue(
            any("Could not update availability" in m for m in log_ctx.output)
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.geodessearch.GeodesSearch._get_availability",
        autospec=True,
    )
    def test_plugins_search_geodes_set_availability_ambiguous_asset(
        self, mock_get_availability
    ):
        """Products whose checksum matches more than one file must be skipped"""
        product = self._build_product("PROD1", "abc")
        product.properties["order:status"] = "untouched"
        mock_get_availability.return_value = {
            "products": [
                {
                    "id": "PROD1",
                    "files": [
                        {"checksum": "abc", "available": True},
                        {"checksum": "abc", "available": False},
                    ],
                }
            ]
        }

        with self.assertLogs("eodag.search.qssearch.geodes", level="WARNING"):
            self.search_plugin._set_availability([product])

        self.assertEqual(product.properties["order:status"], "untouched")

    @mock.patch(
        "eodag.plugins.search.qssearch.geodessearch.GeodesSearch._set_availability",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.normalize_results", autospec=True
    )
    def test_plugins_search_geodes_normalize_results_calls_set_availability(
        self, mock_super_normalize, mock_set_availability
    ):
        """normalize_results must delegate to StacSearch.normalize_results and
        then call _set_availability with the resulting products"""
        product = self._build_product("PROD1", "abc")
        mock_super_normalize.return_value = [product]

        results = self.search_plugin.normalize_results([{}])

        self.assertEqual(results, [product])
        mock_set_availability.assert_called_once_with(self.search_plugin, [product])
