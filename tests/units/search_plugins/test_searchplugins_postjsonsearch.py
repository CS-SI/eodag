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
from unittest import mock

import requests
import responses

from eodag.api.product import EOProduct
from eodag.plugins.search import PreparedSearch
from eodag.utils import USER_AGENT
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    QuotaExceededError,
    RequestError,
)
from tests.units.search_plugins.base import BaseSearchPluginTest
from tests.units.search_plugins.mock_response import MockResponse


class TestSearchPluginPostJsonSearch(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginPostJsonSearch, self).setUp()
        # One of the providers that has a PostJsonSearch Search plugin
        provider = "aws_eos"
        self.awseos_search_plugin = self.get_search_plugin(self.collection, provider)
        self.awseos_auth_plugin = self.get_auth_plugin(self.awseos_search_plugin)
        self.awseos_auth_plugin.config.credentials = dict(apikey="dummyapikey")
        self.awseos_url = "https://gate.eos.com/api/lms/search/v2/sentinel2"

    def test_plugins_search_postjsonsearch_request_error(self):
        """A query with a PostJsonSearch must handle requests errors"""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            responses.add(
                responses.POST, self.awseos_url, status=500, body=b"test error message"
            )

            with self.assertLogs("eodag.search.qssearch", level="DEBUG") as cm:
                with self.assertRaises(RequestError):
                    products, estimate = self.awseos_search_plugin.query(
                        prep=PreparedSearch(
                            page=1,
                            limit=2,
                            auth_plugin=self.awseos_auth_plugin,
                        ),
                        raise_errors=True,
                        **self.search_criteria_s2_msi_l1c,
                    )
                self.assertIn("test error message", str(cm.output))

        run()

    def test_plugins_search_postjsonsearch_request_auth_error(self):
        """A query with a PostJsonSearch must handle auth errors"""

        @responses.activate(registry=responses.registries.FirstMatchRegistry)
        def run():
            responses.add(
                responses.POST, self.awseos_url, status=403, body=b"test error message"
            )

            with self.assertRaisesRegex(AuthenticationError, "test error message"):
                products, estimate = self.awseos_search_plugin.query(
                    prep=PreparedSearch(
                        page=1,
                        limit=2,
                        auth_plugin=self.awseos_auth_plugin,
                    ),
                    **self.search_criteria_s2_msi_l1c,
                )

        run()

    @mock.patch(
        "eodag.plugins.search.qssearch.postjsonsearch.requests.post", autospec=True
    )
    def test_plugins_search_postjsonsearch_search_quota_exceeded(self, mock__request):
        """A query with a PostJsonSearch must handle a 429 response returned by the provider"""

        class MockResponseRequestsException(MockResponse):
            def raise_for_status(self):
                if self.status_code != 200:
                    raise requests.RequestException()

        response = MockResponseRequestsException({}, status_code=429)
        mock__request.return_value = response
        with self.assertRaises(QuotaExceededError):
            self.awseos_search_plugin.query(collection="S2_MSI_L2A")

    @mock.patch(
        "eodag.plugins.search.qssearch.postjsonsearch.PostJsonSearch._request",
        autospec=True,
    )
    def test_plugins_search_postjsonsearch_count_and_search_awseos(self, mock__request):
        """A query with a PostJsonSearch (here aws_eos) must return tuple with a list of EOProduct and a number of available products"""  # noqa
        with open(self.provider_resp_dir / "awseos_search.json") as f:
            awseos_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = [
            awseos_resp_search,
        ]
        products = self.awseos_search_plugin.query(
            prep=PreparedSearch(
                page=1,
                limit=2,
                auth_plugin=self.awseos_auth_plugin,
            ),
            **self.search_criteria_s2_msi_l1c,
        )

        # Specific expected results
        awseos_products_count = 44
        number_of_products = 2

        self.assertEqual(mock__request.call_args_list[-1][0][1].url, self.awseos_url)

        self.assertEqual(products.number_matched, awseos_products_count)
        self.assertEqual(len(products.data), number_of_products)
        self.assertIsInstance(products.data[0], EOProduct)

    @mock.patch(
        "eodag.plugins.search.qssearch.postjsonsearch.PostJsonSearch._request",
        autospec=True,
    )
    def test_plugins_search_postjsonsearch_count_and_search_awseos_s2l2a(
        self, mock__request
    ):
        """A query with a PostJsonSearch (here aws_eos) must return a single EOProduct when search by id using specific_qssearch"""  # noqa

        mock_values = []
        with open(self.provider_resp_dir / "s2l2a_tileInfo.json") as f:
            mock_values.append(json.load(f))
        with open(self.provider_resp_dir / "s2l2a_productInfo.json") as f:
            mock_values.append(json.load(f))

        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.side_effect = mock_values

        try:
            products = self.awseos_search_plugin.query(
                prep=PreparedSearch(auth_plugin=self.awseos_auth_plugin, count=True),
                **{
                    "collection": "S2_MSI_L2A",
                    "id": "S2B_MSIL2A_20220101T000459_N0301_R130_T53DMB_20220101T012649",
                },
            )
        except MisconfiguredError:
            # @TODO: to fix
            # postJsonSearch does not apply metadata mapping filters on properties
            # eodag.utils.exceptions.MisconfiguredError: Missing id#s2msil2a_title_to_aws_productinfo
            #     in aws_eos configuration
            self.skipTest(reason="need fix")

        self.assertEqual(mock__request.call_count, 2)
        self.assertEqual(
            mock__request.call_args_list[0][0][1].url,
            "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/53/D/MB/2022/1/1/0/tileInfo.json",
        )
        self.assertEqual(
            mock__request.call_args_list[1][0][1].url,
            "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/53/D/MB/2022/1/1/0/productInfo.json",
        )

        self.assertEqual(len(products.data), 1)
        self.assertIsInstance(products.data[0], EOProduct)

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch.count_hits",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.postjsonsearch.PostJsonSearch._request",
        autospec=True,
    )
    def test_plugins_search_postjsonsearch_no_count_and_search_awseos(
        self, mock__request, mock_count_hits
    ):
        """A query with a PostJsonSearch (here aws_eos) without a count"""
        with open(self.provider_resp_dir / "awseos_search.json") as f:
            awseos_resp_search = json.load(f)
        mock__request.return_value = mock.Mock()
        mock__request.return_value.json.return_value = awseos_resp_search
        products = self.awseos_search_plugin.query(
            prep=PreparedSearch(
                count=False,
                page=1,
                limit=2,
                auth_plugin=self.awseos_auth_plugin,
            ),
            **self.search_criteria_s2_msi_l1c,
        )

        # Specific expected results
        number_of_products = 2

        mock_count_hits.assert_not_called()
        self.assertEqual(mock__request.call_args_list[0][0][1].url, self.awseos_url)

        self.assertIsNone(products.number_matched)
        self.assertEqual(len(products.data), number_of_products)
        self.assertIsInstance(products.data[0], EOProduct)
        # products count should not have been extracted from search results
        self.assertIsNone(
            getattr(mock__request.call_args_list[0][0][1], "total_items_nb", None)
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.requests.post", autospec=True
    )
    def test_plugins_search_postjsonsearch_search_cloudcover_awseos(
        self, mock_requests_post, mock_normalize_results
    ):
        """A query with a PostJsonSearch (here aws_eos) must only use cloudCover filtering for non-radar collections"""  # noqa

        self.awseos_search_plugin.query(
            prep=PreparedSearch(auth_plugin=self.awseos_auth_plugin),
            collection="S2_MSI_L1C",
            **{"eo:cloud_cover": 50},
        )
        mock_requests_post.assert_called()
        self.assertIn("cloudCoverage", str(mock_requests_post.call_args_list[-1][1]))
        mock_requests_post.reset_mock()

        self.awseos_search_plugin.query(
            prep=PreparedSearch(auth_plugin=self.awseos_auth_plugin),
            collection="S1_SAR_GRD",
            **{"eo:cloud_cover": 50},
        )
        mock_requests_post.assert_called()
        self.assertNotIn(
            "cloudCoverPercentage", str(mock_requests_post.call_args_list[-1][1])
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.postjsonsearch.PostJsonSearch._request",
        autospec=True,
    )
    def test_plugins_search_postjsonsearch_distinct_collection_mtd_mapping(
        self, mock__request
    ):
        """The metadata mapping for PostJsonSearch should not mix specific collections metadata-mapping"""
        geojson_geometry = self.search_criteria_s2_msi_l1c["geometry"].__geo_interface__
        mock__request.return_value = mock.Mock()
        result = {
            "meta": {"page": 1, "found": 1, "limit": 2},
            "results": [
                {
                    "id": "foo",
                    "dataGeometry": geojson_geometry,
                },
            ],
        }
        mock__request.return_value.json.side_effect = [result, result]

        # update metadata_mapping only for S1_SAR_GRD
        self.awseos_search_plugin.config.products["S1_SAR_GRD"]["metadata_mapping"][
            "bar"
        ] = (
            None,
            "baz",
        )
        products = self.awseos_search_plugin.query(
            prep=PreparedSearch(auth_plugin=self.awseos_auth_plugin),
            collection="S1_SAR_GRD",
        )
        self.assertIn("bar", products.data[0].properties)
        self.assertEqual(products.data[0].properties["bar"], "baz")

        # search with another collection
        self.assertNotIn(
            "bar",
            self.awseos_search_plugin.config.products["S2_MSI_L1C"]["metadata_mapping"],
        )
        products = self.awseos_search_plugin.query(
            prep=PreparedSearch(auth_plugin=self.awseos_auth_plugin),
            collection="S2_MSI_L1C",
        )
        self.assertNotIn("bar", products.data[0].properties)

    @mock.patch(
        "eodag.plugins.search.qssearch.querystringsearch.requests.post", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.postjsonsearch.PostJsonSearch.normalize_results",
        autospec=True,
    )
    def test_plugins_search_postjsonsearch_default_dates(
        self, mock_normalize, mock_request
    ):
        provider = "wekeo_ecmwf"
        search_plugins = self.plugins_manager.get_search_plugins(provider=provider)
        search_plugin = next(search_plugins)
        mock_request.return_value = MockResponse({"features": []}, 200)
        # year, month, day, time given -> don't use default dates
        search_plugin.query(
            prep=PreparedSearch(),
            collection="ERA5_SL",
            **{
                "ecmwf:year": "2020",
                "ecmwf:month": ["02"],
                "ecmwf:day": ["20", "21"],
                "ecmwf:time": ["01:00"],
            },
        )
        mock_request.assert_called_with(
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/search",
            json={
                "year": "2020",
                "month": ["02"],
                "day": ["20", "21"],
                "time": ["01:00"],
                "dataset_id": "EO:ECMWF:DAT:REANALYSIS_ERA5_SINGLE_LEVELS",
                "itemsPerPage": 20,
                "startIndex": 0,
            },
            headers=USER_AGENT,
            timeout=60,
            verify=True,
        )
        # start date given and converted to year, month, day, time
        search_plugin.query(
            prep=PreparedSearch(),
            collection="ERA5_SL",
            start_datetime="2021-02-01T03:00:00Z",
        )
        mock_request.assert_called_with(
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/search",
            json={
                "year": ["2021"],
                "month": ["02"],
                "day": ["01"],
                "time": ["03:00"],
                "dataset_id": "EO:ECMWF:DAT:REANALYSIS_ERA5_SINGLE_LEVELS",
                "itemsPerPage": 20,
                "startIndex": 0,
            },
            headers=USER_AGENT,
            timeout=60,
            verify=True,
        )
        # no date info given -> default dates (extent.temporal.interval.0.0) which are
        # then converted to year, month, day, time
        col_conf = {
            "id": "ERA5_SL",
            "description": "ERA5 abstract",
            "instruments": [],
            "constellation": "ERA5",
            "platform": "ERA5",
            "processing:level": None,
            "keywords": [
                "ECMWF",
                "Reanalysis",
                "ERA5",
                "CDS",
                "Atmospheric",
                "land",
                "sea",
                "hourly",
                "single",
                "levels",
            ],
            "eodag:sensor_type": "ATMOSPHERIC",
            "license": "other",
            "title": "ERA5 hourly data on single levels from 1940 to present",
            "extent": {
                "spatial": {"bbox": [[-180.0, -90.0, 180.0, 90.0]]},
                "temporal": {"interval": [["1940-01-01T00:00:00Z", None]]},
            },
            "_id": "ERA5_SL",
        }
        search_plugin.config.collection_config = dict(
            col_conf,
            **{"_collection": "ERA5_SL"},
        )
        search_plugin.query(collection="ERA5_SL", prep=PreparedSearch())
        mock_request.assert_called_with(
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/search",
            json={
                "dataset_id": "EO:ECMWF:DAT:REANALYSIS_ERA5_SINGLE_LEVELS",
                "itemsPerPage": 20,
                "startIndex": 0,
            },
            headers=USER_AGENT,
            timeout=60,
            verify=True,
        )
        # collection with dates are query params -> use extent.temporal.interval.0.0 and today
        col_conf = {
            "id": "CAMS_EAC4",
            "description": "CAMS_EAC4 abstract",
            "instruments": [],
            "constellation": "CAMS",
            "platform": "CAMS",
            "processing:level": None,
            "keywords": [
                "Copernicus",
                "ADS",
                "CAMS",
                "Atmosphere",
                "Atmospheric",
                "EWMCF",
                "EAC4",
            ],
            "eodag:sensor_type": "ATMOSPHERIC",
            "license": "other",
            "title": "CAMS global reanalysis (EAC4)",
            "extent": {
                "spatial": {"bbox": [[-180.0, -90.0, 180.0, 90.0]]},
                "temporal": {"interval": [["2003-01-01T00:00:00Z", None]]},
            },
            "_id": "CAMS_EAC4",
        }
        search_plugin.config.collection_config = dict(
            col_conf,
            **{"_collection": "CAMS_EAC4"},
        )
        search_plugin.query(collection="CAMS_EAC4", prep=PreparedSearch())
        mock_request.assert_called_with(
            "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/search",
            json={
                "dataset_id": "EO:ECMWF:DAT:CAMS_GLOBAL_REANALYSIS_EAC4",
                "itemsPerPage": 20,
                "startIndex": 0,
            },
            headers=USER_AGENT,
            timeout=60,
            verify=True,
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.postjsonsearch.PostJsonSearch._request",
        autospec=True,
    )
    def test_plugins_search_postjsonsearch_query_params_wekeo(self, mock__request):
        """A query with PostJsonSearch (here wekeo) must generate query params corresponding to the
        search criteria"""
        provider = "wekeo_ecmwf"
        collection = "GRIDDED_GLACIERS_MASS_CHANGE"
        search_plugin = self.get_search_plugin(collection, provider)
        auth_plugin = self.get_auth_plugin(search_plugin)

        mock__request.return_value = mock.Mock()

        def _test_query_params(search_criteria, raw_result, expected_query_params):
            mock__request.reset_mock()
            mock__request.return_value.json.side_effect = [raw_result]
            search_plugin.query(
                prep=PreparedSearch(
                    page=1,
                    limit=10,
                    auth_plugin=auth_plugin,
                ),
                **search_criteria,
            )
            self.assertDictEqual(
                mock__request.call_args_list[0].args[1].query_params,
                expected_query_params,
            )

        raw_result = {
            "properties": {"itemsPerPage": 1, "startIndex": 0, "totalResults": 1},
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "startdate": "1975-01-01T00:00:00Z",
                        "enddate": "2024-09-30T00:00:00Z",
                    },
                    "id": "derived-gridded-glacier-mass-change-576f8a153a25a83d9d3a5cfb03c4a759",
                }
            ],
        }

        # Test #1: using the datetime
        search_criteria = {
            "collection": collection,
            "start_datetime": "1980-01-01",
            "end_datetime": "1981-12-31",
            "ecmwf:variable": "glacier_mass_change",
            "ecmwf:data_format": "zip",
            "ecmwf:product_version": "wgms_fog_2022_09",
        }
        expected_query_params = {
            "dataset_id": "EO:ECMWF:DAT:DERIVED_GRIDDED_GLACIER_MASS_CHANGE",
            "hydrological_year": ["1980_81"],
            "variable": "glacier_mass_change",
            "data_format": "zip",
            "product_version": "wgms_fog_2022_09",
            "itemsPerPage": 10,
            "startIndex": 0,
        }
        _test_query_params(search_criteria, raw_result, expected_query_params)

        # Test #2: using parameter hydrological_year (single value)
        search_criteria = {
            "collection": collection,
            "ecmwf:variable": "glacier_mass_change",
            "ecmwf:data_format": "zip",
            "ecmwf:product_version": "wgms_fog_2022_09",
            "ecmwf:hydrological_year": ["2020_21"],
        }
        expected_query_params = {
            "dataset_id": "EO:ECMWF:DAT:DERIVED_GRIDDED_GLACIER_MASS_CHANGE",
            "hydrological_year": ["2020_21"],
            "variable": "glacier_mass_change",
            "data_format": "zip",
            "product_version": "wgms_fog_2022_09",
            "itemsPerPage": 10,
            "startIndex": 0,
        }
        _test_query_params(search_criteria, raw_result, expected_query_params)

        # Test #3: using parameter hydrological_year (multiple values)
        search_criteria = {
            "collection": collection,
            "ecmwf:variable": "glacier_mass_change",
            "ecmwf:data_format": "zip",
            "ecmwf:product_version": "wgms_fog_2022_09",
            "ecmwf:hydrological_year": ["1990_91", "2020_21"],
        }
        expected_query_params = {
            "dataset_id": "EO:ECMWF:DAT:DERIVED_GRIDDED_GLACIER_MASS_CHANGE",
            "hydrological_year": ["1990_91", "2020_21"],
            "variable": "glacier_mass_change",
            "data_format": "zip",
            "product_version": "wgms_fog_2022_09",
            "itemsPerPage": 10,
            "startIndex": 0,
        }
        _test_query_params(search_criteria, raw_result, expected_query_params)
