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
import os
from unittest import mock
from unittest.mock import ANY

import responses
from shapely.geometry import shape
from usgs.api import USGSAuthExpiredError

from eodag.api.product import EOProduct
from eodag.plugins.search import PreparedSearch
from eodag.utils import USER_AGENT, get_geometry_from_various
from eodag.utils.exceptions import AuthenticationError, NotAvailableError
from tests.units.apis_plugins.base import BaseApisPluginTest


class TestApisPluginUsgsApi(BaseApisPluginTest):

    SCENE_SEARCH_RETURN = {
        "data": {
            "results": [
                {
                    "browse": [
                        {
                            "browsePath": "https://path/to/quicklook.jpg",
                            "thumbnailPath": "https://path/to/thumbnail.jpg",
                        },
                        {},
                        {},
                    ],
                    "cloudCover": "77.46",
                    "entityId": "LC81780382020041LGN00",
                    "displayId": "LC08_L1GT_178038_20200210_20200224_01_T2",
                    "spatialBounds": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [28.03905, 30.68073],
                                [28.03905, 32.79057],
                                [30.46294, 32.79057],
                                [30.46294, 30.68073],
                                [28.03905, 30.68073],
                            ]
                        ],
                    },
                    "temporalCoverage": {
                        "endDate": "2020-02-10 00:00:00",
                        "startDate": "2020-02-10 00:00:00",
                    },
                    "publishDate": "2020-02-10 08:24:46",
                },
            ],
            "recordsReturned": 5,
            "totalHits": 139,
            "startingNumber": 6,
            "nextRecord": 11,
        }
    }

    DOWNLOAD_OPTION_RETURN = {
        "data": [
            {
                "id": "5e83d0b8e7f6734c",
                "entityId": "LC81780382020041LGN00",
                "available": True,
                "filesize": 9186067,
                "productName": "LandsatLook Natural Color Image",
                "downloadSystem": "dds",
            },
            {
                "entityId": "LC81780382020041LGN00",
                "available": False,
                "downloadSystem": "wms",
            },
        ]
    }

    def setUp(self):
        super().setUp()
        self.provider = "usgs"
        self.api_plugin = self.get_search_plugin(provider=self.provider)

    def tearDown(self):
        super().tearDown()

    @mock.patch("usgs.api.login", autospec=True)
    @mock.patch("usgs.api.logout", autospec=True)
    def _test_plugins_apis_usgs_authenticate(self, mock_api_logout, mock_api_login):
        """UsgsApi.authenticate must return try to login"""
        # no credential
        try:
            self.api_plugin.authenticate()
            self.fail('Can`t authenticate without username/password in credentials"')
        except AuthenticationError:
            pass
        mock_api_login.assert_not_called()
        mock_api_logout.assert_not_called()
        mock_api_login.reset_mock()

        # with credentials
        self.api_plugin.config.credentials = {
            "username": "foo",
            "password": "bar",
        }
        self.api_plugin.authenticate()
        mock_api_login.assert_called_once_with("foo", "bar", save=False)
        mock_api_logout.assert_not_called()
        mock_api_login.reset_mock()

        # with USGSAuthExpiredError
        mock_api_login.side_effect = [USGSAuthExpiredError(), None]
        try:
            self.api_plugin.authenticate()
        except AuthenticationError:
            pass
        mock_api_login.reset_mock()
        mock_api_logout.reset_mock()

    @mock.patch("usgs.api.login", autospec=True)
    @mock.patch("usgs.api.logout", autospec=True)
    @mock.patch(
        "usgs.api.scene_search", autospec=True, return_value=SCENE_SEARCH_RETURN
    )
    @mock.patch(
        "usgs.api.download_options", autospec=True, return_value=DOWNLOAD_OPTION_RETURN
    )
    def _test_plugins_apis_usgs_query(
        self,
        mock_api_download_options,
        mock_api_scene_search,
        mock_api_logout,
        mock_api_login,
    ):
        # with credentials
        self.api_plugin.config.credentials = {
            "username": "foo",
            "password": "bar",
        }
        """UsgsApi.query must search using usgs api"""
        search_kwargs = {
            "collection": "LANDSAT_C2L1",
            "start_datetime": "2020-02-01",
            "end_datetime": "2020-02-10",
            "geometry": get_geometry_from_various(geometry=[10, 20, 30, 40]),
            "prep": PreparedSearch(
                limit=5,
            ),
        }
        search_kwargs["prep"].next_page_token = "6"
        search_results = self.api_plugin.query(**search_kwargs)
        mock_api_scene_search.assert_called_once_with(
            "landsat_ot_c2_l1",
            start_date="2020-02-01",
            end_date="2020-02-10",
            ll={"longitude": 10.0, "latitude": 20.0},
            ur={"longitude": 30.0, "latitude": 40.0},
            max_results=5,
            starting_number=6,
            api_key=ANY,
        )
        self.assertEqual(search_results.data[0].provider, "usgs")
        self.assertEqual(search_results.data[0].collection, "LANDSAT_C2L1")
        self.assertEqual(
            search_results.data[0].geometry,
            shape(
                mock_api_scene_search.return_value["data"]["results"][0][
                    "spatialBounds"
                ]
            ),
        )
        self.assertEqual(
            search_results.data[0].properties["id"],
            mock_api_scene_search.return_value["data"]["results"][0]["displayId"],
        )
        self.assertEqual(
            search_results.data[0].properties["eo:cloud_cover"],
            float(
                mock_api_scene_search.return_value["data"]["results"][0]["cloudCover"]
            ),
        )
        self.assertEqual(
            search_results.number_matched,
            mock_api_scene_search.return_value["data"]["totalHits"],
        )

    @mock.patch("usgs.api.login", autospec=True)
    @mock.patch("usgs.api.logout", autospec=True)
    @mock.patch(
        "usgs.api.scene_search",
        autospec=True,
        return_value=SCENE_SEARCH_RETURN,
    )
    @mock.patch(
        "usgs.api.download_options",
        autospec=True,
        return_value=DOWNLOAD_OPTION_RETURN,
    )
    @mock.patch(
        "usgs.api.dataset_filters",
        autospec=True,
        return_value={
            "data": [
                {"id": "foo_id", "searchSql": "DONT_USE_THIS !"},
                {"id": "bar_id", "searchSql": "USE_THIS_ID !"},
            ]
        },
    )
    def _test_plugins_apis_usgs_query_by_id(
        self,
        mock_dataset_filters,
        mock_api_download_options,
        mock_api_scene_search,
        mock_api_logout,
        mock_api_login,
    ):
        """UsgsApi.query by id must search using usgs api"""
        self.api_plugin.config.credentials = {
            "username": "foo",
            "password": "bar",
        }
        search_kwargs = {
            "collection": "LANDSAT_C2L1",
            "id": "SOME_PRODUCT_ID",
            "prep": PreparedSearch(
                limit=500,
            ),
        }
        search_kwargs["prep"].next_page_token = "1"
        search_results = self.api_plugin.query(**search_kwargs)
        mock_api_scene_search.assert_called_once_with(
            "landsat_ot_c2_l1",
            where={"filter_id": "bar_id", "value": "SOME_PRODUCT_ID"},
            start_date=None,
            end_date=None,
            ll=None,
            ur=None,
            max_results=500,
            starting_number=1,
            api_key=ANY,
        )
        self.assertEqual(search_results.data[0].provider, "usgs")
        self.assertEqual(search_results.data[0].collection, "LANDSAT_C2L1")
        self.assertEqual(len(search_results.data), 1)

    @mock.patch("usgs.api.login", autospec=True)
    @mock.patch("usgs.api.logout", autospec=True)
    @mock.patch("usgs.api.download_request", autospec=True)
    @responses.activate
    def test_plugins_apis_usgs_download(
        self,
        mock_api_download_request,
        mock_api_logout,
        mock_api_login,
    ):
        """UsgsApi.download must donwload using usgs api"""
        self.api_plugin.config.credentials = {
            "username": "foo",
            "password": "bar",
        }

        product = EOProduct(
            "cop_dataspace",
            dict(
                geometry="POINT (0 0)",
                title="dummy_product",
                id="dummy",
                collection="L8_OLI_TIRS_C1L1",
                **{
                    "usgs:entityId": "dummyEntityId",
                    "usgs:productId": "dummyProductId",
                },
            ),
        )
        product.assets.update(
            {
                "download_link": {
                    "title": "download_link",
                    "href": "http://somewhere",
                    "type": "application/octet-stream",
                }
            }
        )
        product.properties["id"] = "someproduct"

        responses.add(
            responses.GET,
            "http://somewhere",
            status=200,
            content_type="application/octet-stream",
            body=b"something",
            auto_calculate_content_length=True,
        )

        with self.assertRaises(NotAvailableError):
            self.api_plugin.download(
                product.assets.get("download_link"),
                output_dir=self.tmp_home_dir.name,
                no_cache=True,
            )

        product.assets["download_link"].update(
            {
                "title": "download_link",
                "href": "http://somewhere",
                "type": "application/octet-stream",
                "usgs:entityId": "some-id",
                "usgs:productId": "some-id",
            }
        )

        # download 1 available product
        mock_api_download_request.return_value = {
            "data": {"preparingDownloads": [{"url": "http://somewhere"}]}
        }

        path = self.api_plugin.download(
            product.assets.get("download_link"),
            output_dir=self.tmp_home_dir.name,
            no_cache=True,
        )

        self.assertEqual(len(responses.calls), 1)
        self.assertIn(
            list(USER_AGENT.items())[0], responses.calls[0].request.headers.items()
        )
        responses.calls.reset()

        self.assertEqual(
            path,
            os.path.join(self.tmp_home_dir.name, "dummy_product", "download_link"),
        )
        self.assertTrue(os.path.isfile(path))

        # check file extension
        # tar
        os.remove(path)
        asset = product.assets.get("download_link")

        with mock.patch("tarfile.is_tarfile", return_value=True, autospec=True):
            path = self.api_plugin.download(
                asset,
                output_dir=self.tmp_home_dir.name,
                output_extension=".tar.gz",
                extract=False,
            )
            self.assertEqual(
                path,
                os.path.join(
                    self.tmp_home_dir.name, "dummy_product", "download_link.tar.gz"
                ),
            )

        # zip
        os.remove(path)
        product.collection = "S2_MSI_L1C"
        with mock.patch("zipfile.is_zipfile", return_value=True, autospec=True):
            path = self.api_plugin.download(
                asset,
                output_dir=self.tmp_home_dir.name,
                output_extension=".zip",
                extract=False,
            )
            self.assertEqual(
                path,
                os.path.join(
                    self.tmp_home_dir.name, "dummy_product", "download_link.zip"
                ),
            )
