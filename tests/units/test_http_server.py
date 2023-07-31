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
import socket
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import geojson
from fastapi.testclient import TestClient
from shapely.geometry import box

from tests import mock
from tests.context import (
    DEFAULT_ITEMS_PER_PAGE,
    AuthenticationError,
    SearchResult,
    parse_header,
)


# AF_UNIX socket not supported on windows yet, see https://github.com/python/cpython/issues/77589
@unittest.skipIf(
    not hasattr(socket, "AF_UNIX"), "AF_UNIX socket not supported on this OS (windows)"
)
class RequestTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(RequestTestCase, cls).setUpClass()

        cls.tested_product_type = "S2_MSI_L1C"

        # Mock home and eodag conf directory to tmp dir
        cls.tmp_home_dir = TemporaryDirectory()
        cls.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=cls.tmp_home_dir.name
        )
        cls.expanduser_mock.start()

        # import after having mocked home_dir because it launches http server (and EODataAccessGateway)
        # reload eodag.rest.utils to prevent eodag_api cache conflicts
        import eodag.rest.utils

        importlib.reload(eodag.rest.utils)
        from eodag.rest import server as eodag_http_server

        cls.eodag_http_server = eodag_http_server

        # mock os.environ to empty env
        cls.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        cls.mock_os_environ.start()

        # disable product types fetch
        os.environ["EODAG_EXT_PRODUCT_TYPES_CFG_FILE"] = ""

    @classmethod
    def tearDownClass(cls):
        super(RequestTestCase, cls).tearDownClass()
        # stop os.environ
        cls.mock_os_environ.stop()

        # stop Mock and remove tmp config dir
        cls.expanduser_mock.stop()
        cls.tmp_home_dir.cleanup()

    def setUp(self):
        self.app = TestClient(self.eodag_http_server.app)

    def test_route(self):
        self._request_valid("/")

    def test_forward(self):
        response = self.app.get("/", follow_redirects=True)
        self.assertEqual(200, response.status_code)
        resp_json = json.loads(response.content.decode("utf-8"))
        self.assertEqual(resp_json["links"][0]["href"], "http://testserver")

        response = self.app.get(
            "/", follow_redirects=True, headers={"Forwarded": "host=foo;proto=https"}
        )
        self.assertEqual(200, response.status_code)
        resp_json = json.loads(response.content.decode("utf-8"))
        self.assertEqual(resp_json["links"][0]["href"], "https://foo")

        response = self.app.get(
            "/",
            follow_redirects=True,
            headers={"X-Forwarded-Host": "bar", "X-Forwarded-Proto": "httpz"},
        )
        self.assertEqual(200, response.status_code)
        resp_json = json.loads(response.content.decode("utf-8"))
        self.assertEqual(resp_json["links"][0]["href"], "httpz://bar")

    @mock.patch(
        "eodag.rest.utils.eodag_api.search",
        autospec=True,
        return_value=(
            SearchResult.from_geojson(
                {
                    "features": [
                        {
                            "properties": {
                                "snowCover": None,
                                "resolution": None,
                                "completionTimeFromAscendingNode": "2018-02-16T00:12:14"
                                ".035Z",
                                "keyword": {},
                                "productType": "OCN",
                                "downloadLink": (
                                    "https://peps.cnes.fr/resto/collections/S1/"
                                    "578f1768-e66e-5b86-9363-b19f8931cc7b/download"
                                ),
                                "eodag_provider": "peps",
                                "eodag_product_type": "S1_SAR_OCN",
                                "platformSerialIdentifier": "S1A",
                                "cloudCover": 0,
                                "title": "S1A_WV_OCN__2SSV_20180215T235323_"
                                "20180216T001213_020624_023501_0FD3",
                                "orbitNumber": 20624,
                                "instrument": "SAR-C SAR",
                                "abstract": None,
                                "eodag_search_intersection": {
                                    "coordinates": [
                                        [
                                            [89.590721, 2.614019],
                                            [89.771805, 2.575546],
                                            [89.809341, 2.756323],
                                            [89.628258, 2.794767],
                                            [89.590721, 2.614019],
                                        ]
                                    ],
                                    "type": "Polygon",
                                },
                                "organisationName": None,
                                "startTimeFromAscendingNode": "2018-02-15T23:53:22"
                                ".871Z",
                                "platform": None,
                                "sensorType": None,
                                "processingLevel": None,
                                "orbitType": None,
                                "topicCategory": None,
                                "orbitDirection": None,
                                "parentIdentifier": None,
                                "sensorMode": None,
                                "quicklook": None,
                            },
                            "id": "578f1768-e66e-5b86-9363-b19f8931cc7b",
                            "type": "Feature",
                            "geometry": {
                                "coordinates": [
                                    [
                                        [89.590721, 2.614019],
                                        [89.771805, 2.575546],
                                        [89.809341, 2.756323],
                                        [89.628258, 2.794767],
                                        [89.590721, 2.614019],
                                    ]
                                ],
                                "type": "Polygon",
                            },
                        },
                        {
                            "properties": {
                                "snowCover": None,
                                "resolution": None,
                                "completionTimeFromAscendingNode": "2018-02-17T00:12:14"
                                ".035Z",
                                "keyword": {},
                                "productType": "OCN",
                                "downloadLink": (
                                    "https://peps.cnes.fr/resto/collections/S1/"
                                    "578f1768-e66e-5b86-9363-b19f8931cc7c/download"
                                ),
                                "eodag_provider": "peps",
                                "eodag_product_type": "S1_SAR_OCN",
                                "platformSerialIdentifier": "S1A",
                                "cloudCover": 0,
                                "title": "S1A_WV_OCN__2SSV_20180216T235323_"
                                "20180217T001213_020624_023501_0FD3",
                                "orbitNumber": 20624,
                                "instrument": "SAR-C SAR",
                                "abstract": None,
                                "eodag_search_intersection": {
                                    "coordinates": [
                                        [
                                            [89.590721, 2.614019],
                                            [89.771805, 2.575546],
                                            [89.809341, 2.756323],
                                            [89.628258, 2.794767],
                                            [89.590721, 2.614019],
                                        ]
                                    ],
                                    "type": "Polygon",
                                },
                                "organisationName": None,
                                "startTimeFromAscendingNode": "2018-02-16T23:53:22"
                                ".871Z",
                                "platform": None,
                                "sensorType": None,
                                "processingLevel": None,
                                "orbitType": None,
                                "topicCategory": None,
                                "orbitDirection": None,
                                "parentIdentifier": None,
                                "sensorMode": None,
                                "quicklook": None,
                            },
                            "id": "578f1768-e66e-5b86-9363-b19f8931cc7c",
                            "type": "Feature",
                            "geometry": {
                                "coordinates": [
                                    [
                                        [89.590721, 2.614019],
                                        [89.771805, 2.575546],
                                        [89.809341, 2.756323],
                                        [89.628258, 2.794767],
                                        [89.590721, 2.614019],
                                    ]
                                ],
                                "type": "Polygon",
                            },
                        },
                    ],
                    "type": "FeatureCollection",
                }
            ),
            2,
        ),
    )
    def _request_valid_raw(
        self,
        url,
        mock_search,
        expected_search_kwargs=None,
        protocol="GET",
        post_data=None,
    ):
        if protocol == "GET":
            response = self.app.get(url, follow_redirects=True)
        else:
            response = self.app.post(
                url,
                data=json.dumps(post_data),
                follow_redirects=True,
            )

        if expected_search_kwargs is not None:
            mock_search.assert_called_once_with(**expected_search_kwargs)

        self.assertEqual(200, response.status_code, response.text)

        return response

    def _request_valid(
        self,
        url,
        expected_search_kwargs=None,
        protocol="GET",
        post_data=None,
    ):
        response = self._request_valid_raw(
            url,
            expected_search_kwargs=expected_search_kwargs,
            protocol=protocol,
            post_data=post_data,
        )

        # Assert response format is GeoJSON
        return geojson.loads(response.content.decode("utf-8"))

    def _request_not_valid(self, url):
        response = self.app.get(url, follow_redirects=True)
        response_content = json.loads(response.content.decode("utf-8"))

        self.assertEqual(400, response.status_code)
        self.assertIn("description", response_content)
        self.assertIn("invalid", response_content["description"])

    def _request_not_found(self, url):
        response = self.app.get(url, follow_redirects=True)
        response_content = json.loads(response.content.decode("utf-8"))

        self.assertEqual(404, response.status_code)
        self.assertIn("description", response_content)
        self.assertIn("not found", response_content["description"])

    def test_request_params(self):
        self._request_not_valid(f"search?collections={self.tested_product_type}&bbox=1")
        self._request_not_valid(
            f"search?collections={self.tested_product_type}&bbox=0,43,1"
        )
        self._request_not_valid(
            f"search?collections={self.tested_product_type}&bbox=0,,1"
        )
        self._request_not_valid(
            f"search?collections={self.tested_product_type}&bbox=a,43,1,44"
        )

        self._request_valid(
            f"search?collections={self.tested_product_type}",
            expected_search_kwargs=dict(
                productType=self.tested_product_type,
                page=1,
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                raise_errors=True,
            ),
        )
        self._request_valid(
            f"search?collections={self.tested_product_type}&bbox=0,43,1,44",
            expected_search_kwargs=dict(
                productType=self.tested_product_type,
                page=1,
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                raise_errors=True,
                geom=box(0, 43, 1, 44, ccw=False),
            ),
        )

    def test_not_found(self):
        """A request to eodag server with a not supported product type must return a 404 HTTP error code"""
        self._request_not_found("search?collections=ZZZ&bbox=0,43,1,44")

    @mock.patch(
        "eodag.rest.utils.eodag_api.search",
        autospec=True,
        side_effect=AuthenticationError("you are no authorized"),
    )
    def test_auth_error(self, mock_search):
        """A request to eodag server raising a Authentication error must return a 401 HTTP error code"""
        response = self.app.get(
            f"search?collections={self.tested_product_type}", follow_redirects=True
        )
        response_content = json.loads(response.content.decode("utf-8"))

        self.assertEqual(401, response.status_code)
        self.assertIn("description", response_content)
        self.assertIn("AuthenticationError", response_content["description"])
        self.assertIn("you are no authorized", response_content["description"])

    def test_filter(self):
        """latestIntersect filter should only keep the latest products once search area is fully covered"""
        result1 = self._request_valid(
            f"search?collections={self.tested_product_type}&bbox=89.65,2.65,89.7,2.7",
            expected_search_kwargs=dict(
                productType=self.tested_product_type,
                page=1,
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                raise_errors=True,
                geom=box(89.65, 2.65, 89.7, 2.7, ccw=False),
            ),
        )
        self.assertEqual(len(result1.features), 2)
        result2 = self._request_valid(
            f"search?collections={self.tested_product_type}&bbox=89.65,2.65,89.7,2.7&filter=latestIntersect",
            expected_search_kwargs=dict(
                productType=self.tested_product_type,
                page=1,
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                raise_errors=True,
                geom=box(89.65, 2.65, 89.7, 2.7, ccw=False),
            ),
        )
        # only one product is returned with filter=latestIntersect
        self.assertEqual(len(result2.features), 1)

    def test_date_search(self):
        """Search through eodag server /search endpoint using dates filering should return a valid response"""
        self._request_valid(
            f"search?collections={self.tested_product_type}&bbox=0,43,1,44&datetime=2018-01-20/2018-01-25",
            expected_search_kwargs=dict(
                productType=self.tested_product_type,
                page=1,
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                raise_errors=True,
                start="2018-01-20T00:00:00",
                end="2018-01-25T00:00:00",
                geom=box(0, 43, 1, 44, ccw=False),
            ),
        )

    def test_date_search_from_items(self):
        """Search through eodag server collection/items endpoint using dates filering should return a valid response"""
        self._request_valid(
            f"collections/{self.tested_product_type}/items?bbox=0,43,1,44",
            expected_search_kwargs=dict(
                productType=self.tested_product_type,
                page=1,
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                raise_errors=True,
                geom=box(0, 43, 1, 44, ccw=False),
            ),
        )
        self._request_valid(
            f"collections/{self.tested_product_type}/items?bbox=0,43,1,44&datetime=2018-01-20/2018-01-25",
            expected_search_kwargs=dict(
                productType=self.tested_product_type,
                page=1,
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                raise_errors=True,
                start="2018-01-20T00:00:00",
                end="2018-01-25T00:00:00",
                geom=box(0, 43, 1, 44, ccw=False),
            ),
        )

    def test_date_search_from_catalog_items(self):
        """Search through eodag server catalog/items endpoint using dates filering should return a valid response"""
        results = self._request_valid(
            f"catalogs/{self.tested_product_type}/year/2018/month/01/items?bbox=0,43,1,44",
            expected_search_kwargs=dict(
                productType=self.tested_product_type,
                page=1,
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                raise_errors=True,
                start="2018-01-01T00:00:00",
                end="2018-02-01T00:00:00",
                geom=box(0, 43, 1, 44, ccw=False),
            ),
        )
        self.assertEqual(len(results.features), 2)

        results = self._request_valid(
            f"catalogs/{self.tested_product_type}/year/2018/month/01/items"
            "?bbox=0,43,1,44&datetime=2018-01-20/2018-01-25",
            expected_search_kwargs=dict(
                productType=self.tested_product_type,
                page=1,
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                raise_errors=True,
                start="2018-01-20T00:00:00",
                end="2018-01-25T00:00:00",
                geom=box(0, 43, 1, 44, ccw=False),
            ),
        )
        self.assertEqual(len(results.features), 2)

        results = self._request_valid(
            f"catalogs/{self.tested_product_type}/year/2018/month/01/items"
            "?bbox=0,43,1,44&datetime=2018-01-20/2019-01-01",
            expected_search_kwargs=dict(
                productType=self.tested_product_type,
                page=1,
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                raise_errors=True,
                start="2018-01-20T00:00:00",
                end="2018-02-01T00:00:00",
                geom=box(0, 43, 1, 44, ccw=False),
            ),
        )
        self.assertEqual(len(results.features), 2)

        results = self._request_valid(
            f"catalogs/{self.tested_product_type}/year/2018/month/01/items"
            "?bbox=0,43,1,44&datetime=2019-01-01/2019-01-31",
        )
        self.assertEqual(len(results.features), 0)

    def test_catalog_browse(self):
        """Browsing catalogs through eodag server should return a valid response"""
        result = self._request_valid(
            f"catalogs/{self.tested_product_type}/year/2018/month/01/day"
        )
        self.assertListEqual(
            [str(i) for i in range(1, 32)],
            [it["title"] for it in result.get("links", []) if it["rel"] == "child"],
        )

    def test_search_item_id_from_catalog(self):
        """Search by id through eodag server /catalog endpoint should return a valid response"""
        self._request_valid(
            f"catalogs/{self.tested_product_type}/items/foo",
            expected_search_kwargs={
                "id": "foo",
                "productType": self.tested_product_type,
            },
        )

    def test_search_item_id_from_collection(self):
        """Search by id through eodag server /collection endpoint should return a valid response"""
        self._request_valid(
            f"collections/{self.tested_product_type}/items/foo",
            expected_search_kwargs={
                "id": "foo",
                "productType": self.tested_product_type,
            },
        )

    def test_collection(self):
        """Requesting a collection through eodag server should return a valid response"""
        result = self._request_valid(f"collections/{self.tested_product_type}")
        self.assertEqual(result["id"], self.tested_product_type)
        for link in result["links"]:
            self.assertIn(link["rel"], ["self", "root", "items"])

    def test_cloud_cover_post_search(self):
        """POST search with cloudCover filtering through eodag server should return a valid response"""
        self._request_valid(
            "search",
            protocol="POST",
            post_data={
                "collections": [self.tested_product_type],
                "bbox": [0, 43, 1, 44],
                "query": {"eo:cloud_cover": {"lte": 10}},
            },
            expected_search_kwargs=dict(
                productType=self.tested_product_type,
                page=1,
                items_per_page=DEFAULT_ITEMS_PER_PAGE,
                raise_errors=True,
                cloudCover=10,
                geom=box(0, 43, 1, 44, ccw=False),
            ),
        )

    def test_ids_post_search(self):
        """POST search with ids filtering through eodag server should return a valid response"""
        self._request_valid(
            "search",
            protocol="POST",
            post_data={
                "collections": [self.tested_product_type],
                "ids": ["foo", "bar"],
            },
        )

    def test_search_response_contains_pagination_info(self):
        """Responses to valid search requests must return a geojson with pagination info in properties"""
        response = self._request_valid(f"search?collections={self.tested_product_type}")
        self.assertIn("numberMatched", response)
        self.assertIn("numberReturned", response)
        self.assertIn("context", response)
        self.assertEqual(1, response["context"]["page"])
        self.assertEqual(DEFAULT_ITEMS_PER_PAGE, response["context"]["limit"])
        self.assertIn("matched", response["context"])
        self.assertIn("returned", response["context"])

    def test_search_provider_in_downloadlink(self):
        """Search through eodag server and check that specified provider appears in downloadLink"""
        # with provider (get)
        response = self._request_valid(
            f"search?collections={self.tested_product_type}&provider=onda"
        )
        response_items = [f for f in response["features"]]
        self.assertTrue(
            all(
                [
                    i["assets"]["downloadLink"]["href"].endswith(
                        "download?provider=onda"
                    )
                    for i in response_items
                ]
            )
        )
        # with provider (post)
        response = self._request_valid(
            "search",
            protocol="POST",
            post_data={"collections": [self.tested_product_type], "provider": "onda"},
        )
        response_items = [f for f in response["features"]]
        self.assertTrue(
            all(
                [
                    i["assets"]["downloadLink"]["href"].endswith(
                        "download?provider=onda"
                    )
                    for i in response_items
                ]
            )
        )
        # without provider
        response = self._request_valid(f"search?collections={self.tested_product_type}")
        response_items = [f for f in response["features"]]
        self.assertTrue(
            all(
                [
                    i["assets"]["downloadLink"]["href"].endswith("download")
                    for i in response_items
                ]
            )
        )

    @mock.patch(
        "eodag.rest.utils.eodag_api.guess_product_type", autospec=True, return_value=[]
    )
    @mock.patch(
        "eodag.rest.utils.eodag_api.list_product_types",
        autospec=True,
        return_value=[{"ID": "S2_MSI_L1C"}, {"ID": "S2_MSI_L2A"}],
    )
    def test_list_product_types_ok(self, list_pt, guess_pt):
        """A simple request for product types with(out) a provider must succeed"""
        for url in ("/collections",):
            r = self.app.get(url)
            self.assertTrue(guess_pt.called)
            self.assertTrue(list_pt.called)
            self.assertEqual(200, r.status_code)
            self.assertListEqual(
                ["S2_MSI_L1C", "S2_MSI_L2A"],
                [
                    it["title"]
                    for it in json.loads(r.content.decode("utf-8")).get("links", [])
                    if it["rel"] == "child"
                ],
            )

        guess_pt.return_value = ["S2_MSI_L1C"]
        url = "/collections?instrument=MSI"
        r = self.app.get(url)
        self.assertTrue(guess_pt.called)
        self.assertTrue(list_pt.called)
        self.assertEqual(200, r.status_code)
        self.assertListEqual(
            ["S2_MSI_L1C"],
            [
                it["title"]
                for it in json.loads(r.content.decode("utf-8")).get("links", [])
                if it["rel"] == "child"
            ],
        )

    @mock.patch(
        "eodag.rest.utils.eodag_api.list_product_types",
        autospec=True,
        return_value=[{"ID": "S2_MSI_L1C"}, {"ID": "S2_MSI_L2A"}],
    )
    def test_list_product_types_nok(self, list_pt):
        """A request for product types with a not supported filter must return all product types"""
        url = "/collections?platform=gibberish"
        r = self.app.get(url)
        self.assertTrue(list_pt.called)
        self.assertEqual(200, r.status_code)
        self.assertListEqual(
            ["S2_MSI_L1C", "S2_MSI_L2A"],
            [
                it["title"]
                for it in json.loads(r.content.decode("utf-8")).get("links", [])
                if it["rel"] == "child"
            ],
        )

    @mock.patch(
        "eodag.plugins.authentication.generic.GenericAuth.authenticate",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.download.http.HTTPDownload._stream_download_dict",
        autospec=True,
    )
    def test_download_item_from_catalog(self, mock_download, mock_auth):
        """Download through eodag server catalog should return a valid response"""

        expected_file = "somewhere.zip"

        mock_download.return_value = dict(
            content=(i for i in range(0)),
            headers={
                "content-disposition": f"attachment; filename={expected_file}",
            },
        )

        response = self._request_valid_raw(
            f"catalogs/{self.tested_product_type}/items/foo/download"
        )
        mock_download.assert_called_once()

        header_content_disposition = parse_header(
            response.headers["content-disposition"]
        )
        response_filename = header_content_disposition.get_param("filename", None)
        self.assertEqual(response_filename, expected_file)

    @mock.patch(
        "eodag.plugins.apis.cds.CdsApi.authenticate",
        autospec=True,
    )
    @mock.patch(
        "eodag.rest.utils.eodag_api.download",
        autospec=True,
    )
    def test_download_item_from_collection_api_plugin(self, mock_download, mock_auth):
        """Download through eodag server catalog should return a valid response"""
        # download should be performed locally then deleted if streaming is not available
        tmp_dl_dir = TemporaryDirectory()
        expected_file = f"{tmp_dl_dir.name}.tar"
        Path(expected_file).touch()
        mock_download.return_value = expected_file

        # use an external python API provider for this test and reset downloader
        self._request_valid_raw.patchings[0].kwargs["return_value"][0][
            0
        ].provider = "cop_cds"
        self._request_valid_raw.patchings[0].kwargs["return_value"][0][
            0
        ].downloader = None

        self._request_valid_raw(
            "collections/some-collection/items/foo/download?provider=cop_cds"
        )
        mock_download.assert_called_once()
        # downloaded file should have been immediatly deleted from the server
        assert not os.path.exists(
            expected_file
        ), f"File {expected_file} should have been deleted"

    def test_conformance(self):
        """Request to /conformance should return a valid response"""
        self._request_valid("conformance")

    def test_service_desc(self):
        """Request to service_desc should return a valid response"""
        service_desc = self._request_valid("api")
        self.assertIn("openapi", service_desc.keys())
        self.assertIn("eodag", service_desc["info"]["title"].lower())
        self.assertGreater(len(service_desc["paths"].keys()), 0)
        # test a 2nd call (ending slash must be ignored)
        self._request_valid("api/")

    def test_service_doc(self):
        """Request to service_doc should return a valid response"""
        response = self.app.get("api.html", follow_redirects=True)
        self.assertEqual(200, response.status_code)

    def test_stac_extension_oseo(self):
        """Request to oseo extension should return a valid response"""
        response = self._request_valid("/extensions/oseo/json-schema/schema.json")
        self.assertEqual(response["title"], "OpenSearch for Earth Observation")
        self.assertEqual(response["allOf"][0]["$ref"], "#/definitions/oseo")
