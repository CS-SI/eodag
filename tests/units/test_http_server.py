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
from __future__ import annotations

import importlib
import json
import os
import socket
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Optional, Union
from unittest.mock import Mock, call
from urllib.parse import quote_plus

import geojson
import httpx
import responses
from fastapi.testclient import TestClient

from eodag.config import PluginConfig
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.download.base import Download
from eodag.rest.config import Settings
from eodag.rest.types.queryables import StacQueryables
from eodag.utils import USER_AGENT, MockResponse
from eodag.utils.exceptions import RequestError
from tests import mock, temporary_environment
from tests.context import (
    DEFAULT_SEARCH_TIMEOUT,
    OFFLINE_STATUS,
    ONLINE_STATUS,
    TEST_RESOURCES_PATH,
    NotAvailableError,
    SearchResult,
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

        # mock os.environ to empty env
        cls.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        cls.mock_os_environ.start()

        # disable product types fetch
        os.environ["EODAG_EXT_PRODUCT_TYPES_CFG_FILE"] = ""

        # load fake credentials to prevent providers needing auth for search to be pruned
        os.environ["EODAG_CFG_FILE"] = os.path.join(
            TEST_RESOURCES_PATH, "wrong_credentials_conf.yml"
        )

        # import after having mocked home_dir because it launches http server (and EODataAccessGateway)
        # reload eodag.rest.core to prevent eodag_api cache conflicts
        import eodag.rest.core

        importlib.reload(eodag.rest.core)
        from eodag.rest import server as eodag_http_server

        cls.eodag_http_server = eodag_http_server

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

    def test_forward(self):
        response = self.app.get("/", follow_redirects=True)
        self.assertEqual(200, response.status_code)
        resp_json = json.loads(response.content.decode("utf-8"))
        self.assertEqual(resp_json["links"][0]["href"], "http://testserver/")

        response = self.app.get(
            "/", follow_redirects=True, headers={"Forwarded": "host=foo;proto=https"}
        )
        self.assertEqual(200, response.status_code)
        resp_json = json.loads(response.content.decode("utf-8"))
        self.assertEqual(resp_json["links"][0]["href"], "https://foo/")

        response = self.app.get(
            "/",
            follow_redirects=True,
            headers={"X-Forwarded-Host": "bar", "X-Forwarded-Proto": "httpz"},
        )
        self.assertEqual(200, response.status_code)
        resp_json = json.loads(response.content.decode("utf-8"))
        self.assertEqual(resp_json["links"][0]["href"], "httpz://bar/")

    def test_liveness_probe(self):
        response = self.app.get("/_mgmt/ping")
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.json()["success"])

    def mock_search_result(self):
        """generate eodag_api.search mock results"""
        search_result = SearchResult.from_geojson(
            {
                "features": [
                    {
                        "properties": {
                            "snowCover": None,
                            "resolution": None,
                            "completionTimeFromAscendingNode": "2018-02-16T00:12:14.035Z",
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
                            "startTimeFromAscendingNode": "2018-02-15T23:53:22.871Z",
                            "platform": None,
                            "sensorType": None,
                            "processingLevel": None,
                            "orbitType": None,
                            "topicCategory": None,
                            "orbitDirection": None,
                            "parentIdentifier": None,
                            "sensorMode": None,
                            "quicklook": None,
                            "storageStatus": ONLINE_STATUS,
                            "providerProperty": "foo",
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
                            "completionTimeFromAscendingNode": "2018-02-17T00:12:14.035Z",
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
                            "startTimeFromAscendingNode": "2018-02-16T23:53:22.871Z",
                            "platform": None,
                            "sensorType": None,
                            "processingLevel": None,
                            "orbitType": None,
                            "topicCategory": None,
                            "orbitDirection": None,
                            "parentIdentifier": None,
                            "sensorMode": None,
                            "quicklook": None,
                            "storageStatus": OFFLINE_STATUS,
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
        )
        config = PluginConfig()
        config.priority = 0
        for p in search_result:
            p.downloader = Download("peps", config)
            p.downloader_auth = Authentication("peps", config)
        search_result.number_matched = len(search_result)
        return search_result

    @mock.patch("eodag.rest.core.eodag_api.search", autospec=True)
    def _request_valid_raw(
        self,
        url: str,
        mock_search: Mock,
        expected_search_kwargs: Union[
            list[dict[str, Any]], dict[str, Any], None
        ] = None,
        method: str = "GET",
        post_data: Optional[Any] = None,
        search_call_count: Optional[int] = None,
        search_result: Optional[SearchResult] = None,
        expected_status_code: int = 200,
    ) -> httpx.Response:
        if search_result:
            mock_search.return_value = search_result
        else:
            mock_search.return_value = self.mock_search_result()
        response = self.app.request(
            method,
            url,
            json=post_data,
            follow_redirects=True,
            headers={"Content-Type": "application/json"} if method == "POST" else {},
        )

        if search_call_count is not None:
            self.assertEqual(mock_search.call_count, search_call_count)

        if (
            expected_search_kwargs is not None
            and search_call_count is not None
            and search_call_count > 1
        ):
            self.assertIsInstance(
                expected_search_kwargs,
                list,
                "expected_search_kwargs must be a list if search_call_count > 1",
            )
            for single_search_kwargs in expected_search_kwargs:
                mock_search.assert_any_call(**single_search_kwargs)
        elif expected_search_kwargs is not None:
            mock_search.assert_called_once_with(**expected_search_kwargs)

        self.assertEqual(expected_status_code, response.status_code, response.text)

        return response

    def _request_valid(
        self,
        url: str,
        expected_search_kwargs: Union[
            list[dict[str, Any]], dict[str, Any], None
        ] = None,
        method: str = "GET",
        post_data: Optional[Any] = None,
        search_call_count: Optional[int] = None,
        check_links: bool = True,
        search_result: Optional[SearchResult] = None,
    ) -> Any:
        response = self._request_valid_raw(
            url,
            expected_search_kwargs=expected_search_kwargs,
            method=method,
            post_data=post_data,
            search_call_count=search_call_count,
            search_result=search_result,
        )

        # Assert response format is GeoJSON
        result = geojson.loads(response.content.decode("utf-8"))

        if check_links:
            self.assert_links_valid(result)

        return result

    def assert_links_valid(self, element: Any):
        """Checks that element links are valid"""
        self.assertIsInstance(element, dict)
        self.assertIn("links", element, f"links not found in {str(element)}")
        self.assertIsInstance(element["links"], list)
        links = element["links"]

        known_rel = [
            "self",
            "root",
            "parent",
            "child",
            "items",
            "service-desc",
            "service-doc",
            "conformance",
            "search",
            "data",
            "collection",
        ]
        required_links_rel = ["self", "root"]

        for link in links:
            # known relations
            self.assertIn(link["rel"], known_rel)
            # must start with app base-url
            assert link["href"].startswith(str(self.app.base_url))
            # HEAD must be valid
            self._request_valid_raw(link["href"], method="HEAD")
            # GET must be valid
            self._request_valid_raw(link["href"])

            if link["rel"] in required_links_rel:
                required_links_rel.remove(link["rel"])

        # required relations
        self.assertEqual(
            len(required_links_rel),
            0,
            f"missing {required_links_rel} relation(s) in {links}",
        )

    def _request_not_valid(
        self, url: str, method: str = "GET", post_data: Optional[Any] = None
    ) -> None:
        response = self.app.request(
            method,
            url,
            json=post_data,
            follow_redirects=True,
            headers={"Content-Type": "application/json"} if method == "POST" else {},
        )
        response_content = json.loads(response.content.decode("utf-8"))

        self.assertEqual(400, response.status_code)
        self.assertIn("description", response_content)

    def _request_not_found(self, url: str):
        response = self.app.get(url, follow_redirects=True)
        response_content = json.loads(response.content.decode("utf-8"))

        self.assertEqual(404, response.status_code)
        self.assertIn("description", response_content)
        self.assertIn("NotAvailableError", response_content["description"])

    def _request_accepted(self, url: str):
        response = self.app.get(url, follow_redirects=True)
        response_content = json.loads(response.content.decode("utf-8"))
        self.assertEqual(202, response.status_code)
        self.assertIn("description", response_content)
        self.assertIn("location", response_content)
        return response_content

    @mock.patch(
        "eodag.plugins.authentication.base.Authentication.authenticate",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.download.base.Download._stream_download_dict",
        autospec=True,
    )
    @mock.patch(
        "eodag.rest.core.eodag_api.download",
        autospec=True,
    )
    def test_download_item_from_collection_no_stream(
        self, mock_download: Mock, mock_stream_download: Mock, mock_auth: Mock
    ):
        """Download through eodag server catalog should return a valid response"""
        # download should be performed locally then deleted if streaming is not available
        tmp_dl_dir = TemporaryDirectory()
        expected_file = f"{tmp_dl_dir.name}.tar"
        Path(expected_file).touch()
        mock_download.return_value = expected_file
        mock_stream_download.side_effect = NotImplementedError()

        self._request_valid_raw(
            f"collections/{self.tested_product_type}/items/foo/download?provider=peps"
        )
        mock_download.assert_called_once()
        # downloaded file should have been immediatly deleted from the server
        assert not os.path.exists(
            expected_file
        ), f"File {expected_file} should have been deleted"

    @mock.patch(
        "eodag.plugins.authentication.base.Authentication.authenticate",
        autospec=True,
    )
    @mock.patch(
        "eodag.rest.core._order_and_update",
        autospec=True,
        side_effect=NotAvailableError(),
    )
    def test_download_item_orderable(
        self,
        mock_order_and_update: Mock,
        mock_auth: Mock,
    ):
        """Download orderable item through eodag server should order the item"""

        qs = '{"foo": "bar"}'
        self.app.request(
            "GET",
            f"collections/foo/items/FOO_ORDERABLE_13245/download?provider=cop_cds&_dc_qs={quote_plus(qs)}",
            json=None,
            follow_redirects=True,
            headers={},
        )

        mock_order_and_update.assert_called_once()
        self.assertEqual(
            mock_order_and_update.call_args[0][0].properties["qs"]["foo"], "bar"
        )

    @mock.patch(
        "eodag.plugins.authentication.base.Authentication.authenticate",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.download.base.Download._stream_download_dict",
        autospec=True,
    )
    def test_error_handler_supports_request_exception_with_status_code_none(
        self, mock_stream_download: Mock, mock_auth: Mock
    ):
        """
        A RequestError with a status code set to None (the default value) should not
        crash the server. This test ensures that it doesn't crash the server and that a
        500 status code is returned to the user.
        """
        # Make _stream_download_dict reaise an exception object with a status_code
        # attribute set to None
        exception = RequestError()
        exception.status_code = None
        mock_stream_download.side_effect = exception

        response = self._request_valid_raw(
            f"collections/{self.tested_product_type}/items/foo/download?provider=peps",
            expected_status_code=500,
        )
        self.assertIn("RequestError", response.text)

    def test_root(self):
        """Request to / should return a valid response"""
        resp_json = self._request_valid("", check_links=False)
        self.assertEqual(resp_json["id"], "eodag-stac-api")
        self.assertEqual(resp_json["title"], "eodag-stac-api")
        self.assertEqual(resp_json["description"], "STAC API provided by EODAG")

        # customize root info
        try:
            Settings.from_environment.cache_clear()
            with temporary_environment(
                EODAG_STAC_API_LANDING_ID="foo-id",
                EODAG_STAC_API_TITLE="foo title",
                EODAG_STAC_API_DESCRIPTION="foo description",
            ):
                resp_json = self._request_valid("", check_links=False)
                self.assertEqual(resp_json["id"], "foo-id")
                self.assertEqual(resp_json["title"], "foo title")
                self.assertEqual(resp_json["description"], "foo description")
        finally:
            Settings.from_environment.cache_clear()

    def test_conformance(self):
        """Request to /conformance should return a valid response"""
        self._request_valid("conformance", check_links=False)

    def test_service_doc(self):
        """Request to service_doc should return a valid response"""
        response = self.app.get("api.html", follow_redirects=True)
        self.assertEqual(200, response.status_code)

    def test_stac_extension_oseo(self):
        """Request to oseo extension should return a valid response"""
        response = self._request_valid(
            "/extensions/oseo/json-schema/schema.json", check_links=False
        )
        self.assertEqual(response["title"], "OpenSearch for Earth Observation")
        self.assertEqual(response["allOf"][0]["$ref"], "#/definitions/oseo")

    def test_queryables(self):
        """Request to /queryables without parameter should return a valid response."""
        stac_common_queryables = list(StacQueryables.default_properties.keys())

        # neither provider nor product type are specified
        res_no_product_type_no_provider = self._request_valid(
            "queryables", check_links=False
        )

        # the response is in StacQueryables class format
        self.assertListEqual(
            list(res_no_product_type_no_provider.keys()),
            [
                "$schema",
                "$id",
                "type",
                "title",
                "description",
                "properties",
                "additionalProperties",
            ],
        )
        self.assertTrue(res_no_product_type_no_provider["additionalProperties"])

        # properties from stac common queryables are added and are the only ones of the response
        self.assertListEqual(
            list(res_no_product_type_no_provider["properties"].keys()),
            stac_common_queryables,
        )

    @mock.patch("eodag.plugins.search.qssearch.requests.Session.get", autospec=True)
    def test_queryables_with_provider(self, mock_requests_get: Mock):
        """Request to /queryables with a valid provider as parameter should return a valid response."""
        queryables_path = os.path.join(
            TEST_RESOURCES_PATH, "stac/provider_queryables.json"
        )
        with open(queryables_path) as f:
            provider_queryables = json.load(f)
        mock_requests_get.return_value = MockResponse(
            provider_queryables, status_code=200
        )

        stac_common_queryables = list(StacQueryables.default_properties.keys())
        provider_stac_queryables_from_queryables_file = [
            "id",
            "gsd",
            "title",
            "s3:gsd",
            "datetime",
            "geometry",
            "platform",
            "processing:level",
            "s1:processing_level",
            "landsat:processing_level",
        ]

        # provider is specified without product type
        res_no_product_type_with_provider = self._request_valid(
            "queryables?provider=planetary_computer", check_links=False
        )

        mock_requests_get.assert_called_once_with(
            mock.ANY,
            url="https://planetarycomputer.microsoft.com/api/stac/v1/search/../queryables",
            timeout=DEFAULT_SEARCH_TIMEOUT,
            headers=USER_AGENT,
            verify=True,
        )

        # the response is in StacQueryables class format
        self.assertListEqual(
            list(res_no_product_type_with_provider.keys()),
            [
                "$schema",
                "$id",
                "type",
                "title",
                "description",
                "properties",
                "additionalProperties",
            ],
        )
        self.assertTrue(res_no_product_type_with_provider["additionalProperties"])

        # properties from stac common queryables are added
        for p in stac_common_queryables:
            self.assertIn(
                p, list(res_no_product_type_with_provider["properties"].keys())
            )

        # properties from provider queryables are added (here the ones of planetary_computer)
        for provider_stac_queryable in provider_stac_queryables_from_queryables_file:
            self.assertIn(
                provider_stac_queryable, res_no_product_type_with_provider["properties"]
            )

    def test_queryables_with_provider_error(self):
        """Request to /queryables with a wrong provider as parameter should return a UnsupportedProvider error."""
        response = self.app.get(
            "queryables?provider=not_supported_provider", follow_redirects=True
        )
        response_content = json.loads(response.content.decode("utf-8"))

        self.assertIn("description", response_content)
        self.assertIn("UnsupportedProvider", response_content["description"])

        self.assertEqual(404, response.status_code)

    @mock.patch("eodag.plugins.manager.PluginManager.get_auth_plugin", autospec=True)
    def test_product_type_queryables(self, mock_requests_session_post):
        """Request to /collections/{collection_id}/queryables should return a valid response."""

        @responses.activate(registry=responses.registries.OrderedRegistry)
        def run():
            queryables_path = os.path.join(
                TEST_RESOURCES_PATH, "stac/product_type_queryables.json"
            )
            with open(queryables_path) as f:
                provider_queryables = json.load(f)
            constraints_path = os.path.join(TEST_RESOURCES_PATH, "constraints.json")
            with open(constraints_path) as f:
                constraints = json.load(f)
            wekeo_main_constraints = {"constraints": constraints}

            planetary_computer_queryables_url = (
                "https://planetarycomputer.microsoft.com/api/stac/v1/collections/"
                "sentinel-1-grd/queryables"
            )
            dedl_queryables_url = (
                "https://hda.data.destination-earth.eu/stac/collections/"
                "EO.ESA.DAT.SENTINEL-1.L1_GRD/queryables"
            )
            wekeo_main_constraints_url = (
                "https://gateway.prod.wekeo2.eu/hda-broker/api/v1/dataaccess/queryable/"
                "EO:ESA:DAT:SENTINEL-1"
            )

            responses.add(
                responses.GET,
                planetary_computer_queryables_url,
                status=200,
                json=provider_queryables,
            )
            responses.add(
                responses.GET,
                wekeo_main_constraints_url,
                status=200,
                json=wekeo_main_constraints,
            )
            responses.add(
                responses.GET,
                dedl_queryables_url,
                status=200,
                json=provider_queryables,
            )

            # no provider is specified with the product type (3 providers get a queryables or constraints file
            # among available providers for S1_SAR_GRD for the moment): queryables intersection returned
            res_product_type_no_provider = self._request_valid(
                "collections/S1_SAR_GRD/queryables",
                check_links=False,
            )
            self.assertEqual(len(responses.calls), 3)

            # check the mock call on planetary_computer
            self.assertEqual(
                planetary_computer_queryables_url, responses.calls[0].request.url
            )
            self.assertIn(
                ("timeout", DEFAULT_SEARCH_TIMEOUT),
                responses.calls[0].request.req_kwargs.items(),
            )
            self.assertIn(
                list(USER_AGENT.items())[0], responses.calls[0].request.headers.items()
            )
            self.assertIn(
                ("verify", True), responses.calls[0].request.req_kwargs.items()
            )
            # check the mock call on wekeo_main
            self.assertEqual(wekeo_main_constraints_url, responses.calls[1].request.url)
            self.assertIn(
                ("timeout", 60), responses.calls[1].request.req_kwargs.items()
            )
            self.assertIn(
                list(USER_AGENT.items())[0], responses.calls[1].request.headers.items()
            )
            self.assertIn(
                ("verify", True), responses.calls[1].request.req_kwargs.items()
            )

            # the response is in StacQueryables class format
            self.assertListEqual(
                list(res_product_type_no_provider.keys()),
                [
                    "$schema",
                    "$id",
                    "type",
                    "title",
                    "description",
                    "properties",
                    "additionalProperties",
                ],
            )
            self.assertTrue(res_product_type_no_provider["additionalProperties"])

            res_list = list(res_product_type_no_provider["properties"].keys())
            expected = [
                "platform",
                "datetime",
                "start_datetime",
                "end_datetime",
                "geometry",
                "bbox",
                "constellation",
                "instruments",
                "gsd",
                "eo:cloud_cover",
                "eo:snow_cover",
                "processing:level",
                "sat:orbit_state",
                "sat:absolute_orbit",
                "sar:instrument_mode",
            ]
            for value in expected:
                self.assertIn(value, res_list)

            # stac format processing:level is in result
            pl_s1_sar_grd_planetary_computer_queryable = "s1:processing_level"
            pl_s1_sar_grd_wekeo_main_queryable = "processingLevel"
            stac_pl_property = "processing:level"
            self.assertIn(
                pl_s1_sar_grd_planetary_computer_queryable,
                provider_queryables["properties"],
            )
            for constraint in wekeo_main_constraints["constraints"]:
                self.assertNotIn(pl_s1_sar_grd_wekeo_main_queryable, constraint)
            self.assertIn(stac_pl_property, res_product_type_no_provider["properties"])

        run()

    def test_product_type_queryables_error(self):
        """Request to /collections/{collection_id}/queryables with a wrong collection_id
        should return a UnsupportedProductType error."""
        response = self.app.get(
            "collections/not_supported_product_type/queryables", follow_redirects=True
        )
        response_content = json.loads(response.content.decode("utf-8"))

        self.assertIn("description", response_content)
        self.assertIn("UnsupportedProductType", response_content["description"])

        self.assertEqual(404, response.status_code)

    @mock.patch("eodag.plugins.search.qssearch.requests.Session.get", autospec=True)
    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch.discover_queryables",
        autospec=True,
    )
    def test_product_type_queryables_with_provider(
        self, mock_discover_queryables_ecmwf, mock_requests_get
    ):
        """Request a collection-specific list of queryables for a given provider
        using a queryables file should return a valid response."""
        queryables_path = os.path.join(
            TEST_RESOURCES_PATH, "stac/product_type_queryables.json"
        )
        with open(queryables_path) as f:
            provider_queryables = json.load(f)
        mock_requests_get.return_value = MockResponse(
            provider_queryables, status_code=200
        )

        planetary_computer_queryables_url = (
            "https://planetarycomputer.microsoft.com/api/stac/v1/search/../collections/"
            "sentinel-1-grd/queryables"
        )

        stac_common_queryables = list(StacQueryables.default_properties.keys())
        # when product type is given, "collection" item is not used
        stac_common_queryables.remove("collection")
        provider_stac_queryables_from_queryables_file = [
            "id",
            "datetime",
            "geometry",
            "platform",
            "processing:level",
        ]

        # provider and product type are specified
        res_product_type_with_provider = self._request_valid(
            "collections/S1_SAR_GRD/queryables?provider=planetary_computer",
            check_links=False,
        )

        mock_requests_get.assert_called_once_with(
            mock.ANY,
            url=planetary_computer_queryables_url,
            timeout=DEFAULT_SEARCH_TIMEOUT,
            headers=USER_AGENT,
            verify=True,
        )

        # the response is in StacQueryables class format
        self.assertListEqual(
            list(res_product_type_with_provider.keys()),
            [
                "$schema",
                "$id",
                "type",
                "title",
                "description",
                "properties",
                "additionalProperties",
            ],
        )
        self.assertTrue(res_product_type_with_provider["additionalProperties"])

        # properties from stac common queryables are added
        for p in stac_common_queryables:
            self.assertIn(p, list(res_product_type_with_provider["properties"].keys()))

        # properties from provider product type queryables are added
        # (here the ones of S1_SAR_GRD for planetary_computer)
        for provider_stac_queryable in provider_stac_queryables_from_queryables_file:
            self.assertIn(
                provider_stac_queryable, res_product_type_with_provider["properties"]
            )

        # properties may be updated with info from provider queryables if
        # info exist (here an example with platformSerialIdentifier)
        stac_psi_property = "platform"
        self.assertEqual(
            "string", provider_queryables["properties"][stac_psi_property]["type"]
        )
        self.assertIn(
            "string",
            res_product_type_with_provider["properties"][stac_psi_property]["type"],
        )

        # provider + product type with constraints -> additionalProperties = False
        mock_discover_queryables_ecmwf.return_value = {}
        res_product_type_with_provider = self._request_valid(
            "collections/ERA5_SL/queryables?provider=cop_cds",
            check_links=False,
        )
        self.assertFalse(res_product_type_with_provider["additionalProperties"])

    def test_stac_queryables_type(self):
        res = self._request_valid(
            "collections/S2_MSI_L2A/queryables?provider=creodias",
            check_links=False,
        )
        self.assertIn("eo:cloud_cover", res["properties"])
        cloud_cover = res["properties"]["eo:cloud_cover"]
        self.assertIn("type", cloud_cover)
        self.assertEqual("integer", cloud_cover["type"])
        self.assertIn("exclusiveMinimum", cloud_cover)
        self.assertEqual(0, cloud_cover["exclusiveMinimum"])
        self.assertIn("exclusiveMaximum", cloud_cover)
        self.assertEqual(100, cloud_cover["exclusiveMaximum"])
        self.assertIn("processing:level", res["properties"])
        processing_level = res["properties"]["processing:level"]
        self.assertEqual("string", processing_level["type"])
        self.assertNotIn(
            "min", processing_level
        )  # none values are left out in serialization

    @mock.patch("eodag.utils.requests.requests.sessions.Session.get", autospec=True)
    def test_product_type_queryables_from_constraints(self, mock_requests_get: Mock):
        """Request a collection-specific list of queryables for a given provider
        using a constraints file should return a valid response."""
        constraints_path = os.path.join(TEST_RESOURCES_PATH, "constraints.json")
        with open(constraints_path) as f:
            constraints = json.load(f)
        for const in constraints:
            const["variable"].append("10m_u_component_of_wind")

        form_path = os.path.join(TEST_RESOURCES_PATH, "form.json")
        with open(form_path) as f:
            form = json.load(f)
        mock_requests_get.return_value.json.side_effect = [constraints, form]

        provider_queryables_from_constraints_file = [
            "year",
            "month",
            "day",
            "time",
            "variable",
            "leadtime_hour",
            "type",
            "product_type",
        ]
        # queryables properties not shared by all constraints must be removed
        not_shared_properties = ["leadtime_hour", "type"]
        provider_queryables_from_constraints_file = [
            f"ecmwf:{properties}"
            for properties in provider_queryables_from_constraints_file
            if properties not in not_shared_properties
        ]
        default_provider_stac_properties = ["ecmwf:product_type", "ecmwf:data_format"]

        res = self._request_valid(
            "collections/ERA5_SL/queryables?provider=cop_cds",
            check_links=False,
        )

        mock_requests_get.assert_has_calls(
            [
                call(
                    mock.ANY,
                    "https://cds.climate.copernicus.eu/api/catalogue/v1/collections/"
                    "reanalysis-era5-single-levels/constraints.json",
                    headers=USER_AGENT,
                    auth=mock.ANY,
                    timeout=30,
                ),
                call().raise_for_status(),
                call().json(),
                call(
                    mock.ANY,
                    "https://cds.climate.copernicus.eu/api/catalogue/v1/collections/"
                    "reanalysis-era5-single-levels/form.json",
                    headers=USER_AGENT,
                    auth=mock.ANY,
                    timeout=30,
                ),
                call().raise_for_status(),
                call().json(),
            ]
        )

        # the response is in StacQueryables class format
        self.assertListEqual(
            list(res.keys()),
            [
                "$schema",
                "$id",
                "type",
                "title",
                "description",
                "properties",
                "required",
                "additionalProperties",
            ],
        )
        self.assertFalse(res["additionalProperties"])

        # properties from provider product type queryables and default properties are added
        # (here the ones of ERA5_SL for cop_cds)
        for provider_stac_queryable in list(
            set(
                provider_queryables_from_constraints_file
                + default_provider_stac_properties
            )
        ):
            self.assertIn(provider_stac_queryable, res["properties"])

    @mock.patch("eodag.rest.core.eodag_api.list_product_types", autospec=True)
    @mock.patch("eodag.rest.core.eodag_api.guess_product_type", autospec=True)
    def test_collection_free_text_search(self, guess_pt: Mock, list_pt: Mock):
        """Test STAC Collection free-text search"""

        url = "/collections?q=TERM1,TERM2"
        r = self.app.get(url)
        list_pt.assert_called_once_with(provider=None, fetch_providers=False)
        guess_pt.assert_called_once_with(
            free_text="TERM1,TERM2",
            platformSerialIdentifier=None,
            instrument=None,
            platform=None,
            missionStartDate=None,
            missionEndDate=None,
            productType=None,
        )
        self.assertEqual(200, r.status_code)
