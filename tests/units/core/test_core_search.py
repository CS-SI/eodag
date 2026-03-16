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
import copy
import json
import os
from datetime import datetime, timezone
from typing import Any
from unittest import mock

from shapely.geometry import Polygon

from eodag import EODataAccessGateway
from eodag.api.collection import Collection
from eodag.api.core import DEFAULT_LIMIT, DEFAULT_MAX_LIMIT
from eodag.api.product import EOProduct
from eodag.api.search_result import SearchResult
from eodag.utils.exceptions import (
    NoMatchingCollection,
    PluginImplementationError,
    RequestError,
)
from tests.units.core.base import TestCoreBase
from tests.utils import TEST_RESOURCES_PATH


class TestCoreSearch(TestCoreBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Mock OIDC auth requests.get to prevent socket calls during auth plugin init
        cls.oidc_mock = mock.patch(
            "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.get",
            autospec=True,
        )
        cls.oidc_mock.start()
        cls.dag = EODataAccessGateway()
        # Get a SearchResult obj with 2 S2_MSI_L1C cop_dataspace products
        search_results_file = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_cop_dataspace.geojson"
        )
        with open(search_results_file, encoding="utf-8") as f:
            search_results_geojson = json.load(f)
        cls.search_results = SearchResult.from_dict(search_results_geojson)
        cls.search_results_size = len(cls.search_results)
        # Change the id of these products, to emulate different products
        search_results_data_2 = copy.deepcopy(cls.search_results.data)
        search_results_data_2[0].properties["id"] = "a"
        search_results_data_2[1].properties["id"] = "b"
        cls.search_results_2 = SearchResult(search_results_data_2)
        cls.search_results_size_2 = len(cls.search_results_2)

    @classmethod
    def tearDownClass(cls):
        cls.oidc_mock.stop()
        super().tearDownClass()

    def test_guess_collection_with_kwargs(self):
        """guess_collection must return the products matching the given kwargs"""
        ext_collections_conf = {
            "earth_search": {
                "providers_config": {
                    "foobar": {
                        "collection": "foobar",
                        "metadata_mapping": {"cloudCover": "$.null"},
                    }
                },
                "collections_config": {
                    "foobar": {
                        "alias": "foobar_alias",
                    }
                },
            }
        }
        self.dag.update_collections_list(ext_collections_conf)

        kwargs = dict(
            instruments="MSI",
            constellation="SENTINEL2",
            platform="S2A",
        )
        actual = self.dag.guess_collection(**kwargs)
        expected = [
            "S2_MSI_L1C",
            "S2_MSI_L2A",
            "S2_MSI_L2A_COG",
            "S2_MSI_L2A_MAJA",
            "S2_MSI_L2B_MAJA_SNOW",
            "S2_MSI_L2B_MAJA_WATER",
            "CLMS_HRVPP_ST",
            "CLMS_HRVPP_ST_LAEA",
            "CLMS_HRVPP_VPP",
            "CLMS_HRVPP_VPP_LAEA",
            "EEA_HRL_TCF",
        ]
        self.assertListEqual([col.id for col in actual], expected)

        # with collection specified

        # unkwown collection and alias
        actual = self.dag.guess_collection(collection="foo")
        self.assertListEqual([actual[0].id], ["foo"])

        # known collection which does not have an alias
        actual = self.dag.guess_collection(collection="S2_MSI_L1C")
        self.assertListEqual([actual[0].id], ["S2_MSI_L1C"])

        # known collection which has an alias
        actual = self.dag.guess_collection(collection="foobar")
        self.assertListEqual([actual[0].id], ["foobar_alias"])

        # known alias
        actual = self.dag.guess_collection(collection="foobar_alias")
        self.assertListEqual([actual[0].id], ["foobar_alias"])

        # with dates
        self.assertEqual(
            self.dag.collections_config["S2_MSI_L1C"].extent.temporal.interval[0][0],
            datetime(2015, 6, 23, 0, 0, tzinfo=timezone.utc),
        )
        self.assertNotIn(
            "S2_MSI_L1C",
            [col.id for col in self.dag.guess_collection(end_date="2015-06-01")],
        )
        self.assertIn(
            "S2_MSI_L1C",
            [col.id for col in self.dag.guess_collection(end_date="2015-07-01")],
        )

        # with individual filters
        actual = self.dag.guess_collection(
            constellation="SENTINEL1", processing_level="L2", intersect=True
        )
        self.assertListEqual([col.id for col in actual], ["S1_SAR_OCN"])
        # without intersect, the most appropriate collection must be at first position
        actual = self.dag.guess_collection(
            constellation="SENTINEL1", processing_level="L2"
        )
        self.assertGreater(len(actual), 1)
        self.assertEqual(actual[0].id, "S1_SAR_OCN")

    def test_guess_collection_without_kwargs(self):
        """guess_collection must raise an exception when no kwargs are provided"""
        with self.assertRaises(NoMatchingCollection):
            self.dag.guess_collection()

    def test_guess_collection_has_no_limit(self):
        """guess_collection must run a whoosh search without any limit"""
        # Filter that should give more than 10 products referenced in the catalog.
        opt_prods = [
            c
            for c in self.dag.list_collections(fetch_providers=False)
            if c.eodag_sensor_type == "OPTICAL"
        ]
        if len(opt_prods) <= 10:
            self.skipTest("This test requires that more than 10 products are 'OPTICAL'")
        guesses = self.dag.guess_collection(
            sensor_type="OPTICAL",
        )
        self.assertGreater(len(guesses), 10)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.sessions.Session.request",
        autospec=True,
    )
    def test_prepare_search_no_parameters(
        self, mock_auth_session_request, mock_fetch_collections_list
    ):
        """_prepare_search must create some kwargs even when no parameter has been provided"""
        _, prepared_search = self.dag._prepare_search()
        expected = {
            "geometry": None,
            "collection": None,
        }
        expected = set(["geometry", "collection"])
        self.assertSetEqual(expected, set(prepared_search))

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.sessions.Session.request",
        autospec=True,
    )
    def test_prepare_search_dates(
        self, mock_auth_session_request, mock_fetch_collections_list
    ):
        """_prepare_search must handle start & end dates"""
        # with start and end parameters
        base = {
            "start": "2020-01-01",
            "end": "2020-02-01",
        }
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(prepared_search["start_datetime"], base["start"])
        self.assertEqual(prepared_search["end_datetime"], base["end"])
        # with datetime
        base = {"datetime": "2021-01-01T00:00:00Z/2021-01-02T00:00:00Z"}
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(prepared_search["start_datetime"], "2021-01-01T00:00:00")
        self.assertEqual(prepared_search["end_datetime"], "2021-01-02T00:00:00")
        # with both, start/end overwrites datetime
        base = {
            "start": "2020-01-01",
            "end": "2020-02-01",
            "datetime": "2021-01-01T00:00:00Z/2021-01-02T00:00:00Z",
        }
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(prepared_search["start_datetime"], base["start"])
        self.assertEqual(prepared_search["end_datetime"], base["end"])
        # with sort by datetime
        base = {
            "datetime": "2021-01-01T00:00:00Z/2021-01-02T00:00:00Z",
            "sort_by": [("datetime", "DESC")],
        }
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertListEqual([("start_datetime", "DESC")], prepared_search["sort_by"])

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.sessions.Session.request",
        autospec=True,
    )
    def test_prepare_search_geom(
        self, mock_auth_session_request, mock_fetch_collections_list
    ):
        """_prepare_search must handle geom, box and bbox"""
        # The default way to provide a geom is through the 'geom' argument.
        base = {"geom": (0, 50, 2, 52)}
        # "geom": "POLYGON ((1 43, 1 44, 2 44, 2 43, 1 43))"
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        # 'box' and 'bbox' are supported for backwards compatibility,
        # The priority is geom > bbox > box
        base = {"box": (0, 50, 2, 52)}
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        base = {"bbox": (0, 50, 2, 52)}
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        base = {
            "geom": "POLYGON ((1 43, 1 44, 2 44, 2 43, 1 43))",
            "bbox": (0, 50, 2, 52),
            "box": (0, 50, 1, 51),
        }
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        self.assertNotIn("bbox", prepared_search)
        self.assertNotIn("bbox", prepared_search)
        self.assertIsInstance(prepared_search["geometry"], Polygon)
        base = {
            "intersects": {
                "type": "Polygon",
                "coordinates": [[[6, 53], [6, 73], [37, 73], [37, 53], [6, 53]]],
            }
        }
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        self.assertNotIn("intersects", prepared_search)
        self.assertIsInstance(prepared_search["geometry"], Polygon)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.sessions.Session.request",
        autospec=True,
    )
    def test_prepare_search_locations(
        self, mock_auth_session_request, mock_fetch_collections_list
    ):
        """_prepare_search must handle a location search"""
        # When locations where introduced they could be passed
        # as regular kwargs. The new and recommended way to provide
        # them is through the 'locations' parameter.
        base = {"locations": {"country": "FRA"}}
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)

        # TODO: Remove this when support for locations kwarg is dropped.
        base = {"country": "FRA"}
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        self.assertNotIn("country", prepared_search)

    def test_prepare_search_collection_provided(self):
        """_prepare_search must handle when a collection is given"""
        base = {"collection": "S2_MSI_L1C"}
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(prepared_search["collection"], base["collection"])

    def test_prepare_search_collection_guess_it(self):
        """_prepare_search must guess a collection when required to"""
        # Uses guess_collection to find the product matching
        # the best the given params.
        base = dict(
            instruments="MSI",
            constellation="SENTINEL2",
            platform="S2A",
        )
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(prepared_search["collection"], "S2_MSI_L1C")

    def test_prepare_search_remove_guess_kwargs(self):
        """_prepare_search must remove the guess kwargs"""
        # Uses guess_collection to find the product matching
        # the best the given params.
        base = dict(
            instruments="MSI",
            constellation="SENTINEL2",
            platform="S2A",
        )
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(len(base.keys() & prepared_search.keys()), 0)

    def test_prepare_search_with_id(self):
        """_prepare_search must handle a search by id"""
        base = {"id": "dummy-id", "provider": "creodias"}
        _, prepared_search = self.dag._prepare_search(**base)
        expected = {"id": "dummy-id"}
        self.assertDictEqual(expected, prepared_search)

    def test_prepare_search_preserve_additional_kwargs(self):
        """_prepare_search must preserve additional kwargs"""
        base = {
            "collection": "S2_MSI_L1C",
            "eo:cloud_cover": 10,
        }
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(prepared_search["collection"], base["collection"])
        self.assertEqual(prepared_search["eo:cloud_cover"], base["eo:cloud_cover"])

    def test_prepare_search_search_plugin_has_known_product_properties(self):
        """_prepare_search must attach the product properties to the search plugin"""
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("cop_dataspace")
            base = {"collection": "S2_MSI_L1C"}
            search_plugins, _ = self.dag._prepare_search(**base)
            # Just check that the title has been set correctly. There are more (e.g.
            # description, platform, etc.) but this is sufficient to check that the
            # collection_config dict has been created and populated.
            self.assertEqual(
                search_plugins[0].config.collection_config["title"],
                "SENTINEL2 Level-1C",
            )
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    def test_prepare_search_search_plugin_has_generic_product_properties(
        self, mock_fetch_collections_list
    ):
        """_prepare_search must be able to attach the generic product properties to the search plugin"""
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("cop_dataspace")
            base = {"collection": "product_unknown_to_eodag"}
            search_plugins, _ = self.dag._prepare_search(**base)
            # collection_config is still created if the product is not known to eodag
            # however it contains no data.
            self.assertIsNone(
                search_plugins[0].config.collection_config["title"],
            )
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

    def test_prepare_search_cop_dataspace_plugins_product_available(self):
        """_prepare_search must return the search plugins when collection is defined"""
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("cop_dataspace")
            base = {"collection": "S2_MSI_L1C"}
            search_plugins, _ = self.dag._prepare_search(**base)
            self.assertEqual(search_plugins[0].provider, "cop_dataspace")
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

    def test_prepare_search_cop_dataspace_plugins_product_available_with_alias(self):
        """_prepare_search must return the search plugins when collection is defined and alias is used"""
        products = self.dag.collections_config
        products.update(
            {
                "S2_MSI_L1C": Collection.create_with_dag(
                    self.dag,
                    alias="S2_MSI_ALIAS",
                    **products["S2_MSI_L1C"].model_dump(exclude={"alias"}),
                )
            }
        )
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("cop_dataspace")
            base = {"collection": "S2_MSI_ALIAS"}
            search_plugins, _ = self.dag._prepare_search(**base)
            self.assertEqual(search_plugins[0].provider, "cop_dataspace")
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

        # restore the original collection instance in the config
        products.update(
            {
                "S2_MSI_L1C": Collection.create_with_dag(
                    self.dag,
                    id="S2_MSI_L1C",
                    **products["S2_MSI_L1C"].model_dump(exclude={"id", "alias"}),
                )
            }
        )

    def test_prepare_search_no_plugins_when_search_by_id(self):
        """_prepare_search must not return the search and auth plugins for a search by id"""
        base = {"id": "some_id", "provider": "some_provider"}
        search_plugins, prepared_search = self.dag._prepare_search(**base)
        self.assertListEqual(search_plugins, [])
        self.assertNotIn("auth", prepared_search)

    def test_prepare_search_cop_dataspace_plugins_product_not_available(self):
        """_prepare_search can use another search plugin than the preferred one"""
        # Document a special behaviour whereby the search and auth plugins don't
        # correspond to the preferred one. This occurs whenever the searched product
        # isn't available for the preferred provider but is made available by another
        # one. In that case the first provider on the list that makes it available is used.
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("cop_cds")
            base = {"collection": "S2_MSI_L1C"}
            search_plugins, _ = self.dag._prepare_search(**base)
            self.assertNotEqual(search_plugins[0].provider, "cop_cds")
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    def test_prepare_search_unknown_collection(self, mock_fetch_collections_list):
        """_prepare_search must fetch collections if collection is unknown"""
        self.dag._prepare_search(collection="foo")
        mock_fetch_collections_list.assert_called_once_with(self.dag)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway._do_search",
        autospec=True,
        return_value=(SearchResult([mock.Mock()], 1)),
    )
    @mock.patch("eodag.plugins.manager.PluginManager.get_auth_plugin", autospec=True)
    @mock.patch(
        "eodag.plugins.manager.PluginManager.get_search_plugins",
        autospec=True,
        return_value=[mock.Mock()],
    )
    def test_search_by_id(
        self, mock_get_search_plugins, mock_get_auth_plugin, mock__do_search
    ):
        """_search_by_id must filter search plugins using given kwargs, clear plugin and perform search"""
        # max_limit plugin conf
        mock_config = mock.Mock()
        type(mock_config).pagination = mock.PropertyMock(
            return_value={"max_limit": 100}
        )
        type(mock_get_search_plugins.return_value[0]).config = mock.PropertyMock(
            return_value=mock_config
        )
        type(
            mock_get_search_plugins.return_value[0]
        ).next_page_query_obj = mock.PropertyMock(return_value={})
        # mocked search result id
        type(mock__do_search.return_value[0]).properties = mock.PropertyMock(
            return_value={"id": "foo"}
        )

        found = self.dag._search_by_id(uid="foo", collection="bar", provider="baz")

        from eodag.utils.logging import get_logging_verbose

        _ = get_logging_verbose()
        # get_search_plugins
        mock_get_search_plugins.assert_called_once_with(
            self.dag._plugins_manager, collection="bar", provider="baz"
        )

        # search plugin clear
        mock_get_search_plugins.return_value[0].clear.assert_called_once()

        # _do_search returns 1 product
        mock__do_search.assert_called_once_with(
            self.dag,
            mock_get_search_plugins.return_value[0],
            id="foo",
            collection="bar",
            raise_errors=True,
            page=1,
            limit=100,
        )
        self.assertEqual(found, mock__do_search.return_value)

        mock__do_search.reset_mock()
        # return None if more than 1 product is found
        mock__do_search.return_value = SearchResult([mock.Mock(), mock.Mock()], 2)
        type(mock__do_search.return_value[0]).properties = mock.PropertyMock(
            return_value={"id": "foo"}
        )
        type(mock__do_search.return_value[1]).properties = mock.PropertyMock(
            return_value={"id": "foo"}
        )
        with self.assertLogs(level="INFO") as cm:
            found = self.dag._search_by_id(uid="foo", collection="bar", provider="baz")
            self.assertEqual(found, SearchResult([], 0))
            self.assertIn("Several products found for this id", str(cm.output))

        mock__do_search.reset_mock()
        # return 1 result if more than 1 product is found but only 1 has the matching id
        mock__do_search.return_value = SearchResult([mock.Mock(), mock.Mock()], 2)
        type(mock__do_search.return_value[0]).properties = mock.PropertyMock(
            return_value={"id": "foo"}
        )
        type(mock__do_search.return_value[1]).properties = mock.PropertyMock(
            return_value={"id": "foooooo"}
        )
        found = self.dag._search_by_id(uid="foo", collection="bar", provider="baz")
        self.assertEqual(found.number_matched, 1)
        self.assertEqual(len(found), 1)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_do_search_support_itemsperpage_higher_than_maximum(self, search_plugin):
        """_do_search must support itemsperpage higher than maximum"""
        search_plugin.provider = "cop_dataspace"
        search_plugin.query.return_value = SearchResult(
            self.search_results.data,  # a list must be returned by .query
            self.search_results_size,
        )

        class DummyConfig:
            pagination = {"max_limit": 1}

        search_plugin.config = DummyConfig()
        with self.assertLogs(level="WARNING") as cm:
            sr = self.dag._do_search(
                count=True,
                search_plugin=search_plugin,
                limit=2,
            )
            self.assertIsInstance(sr, SearchResult)
            self.assertEqual(len(sr), self.search_results_size)
            self.assertEqual(sr.number_matched, self.search_results_size)
            self.assertIn(
                "Try to lower the value of 'limit'",
                str(cm.output),
            )

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_do_search_params_alias(self, search_plugin):
        """_do_search must get params alias and remove provider prefix"""
        search_plugin.provider = "cop_dataspace"

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        search_args = dict(
            foo="bar",
            baz=None,
            eo_cloud_cover=10,
            **{"eo:snow_cover": 20},
            cop_dataspace_custom_1=30,
            **{"cop_dataspace:custom_2": 40},
            **{"ecmwf:variable": "aaa"},
            **{"ecmwf_format": "grib"},
        )

        shared: dict[str, Any] = {"kwargs": {}}

        def fake_query(*args, **kwargs) -> SearchResult:
            shared["kwargs"] = kwargs
            return SearchResult([])

        search_plugin.query = fake_query

        self.dag._do_search(search_plugin=search_plugin, **search_args)
        self.assertEqual(shared["kwargs"].get("foo"), "bar")
        self.assertEqual(shared["kwargs"].get("eo:cloud_cover"), 10)
        self.assertEqual(shared["kwargs"].get("eo:snow_cover"), 20)
        self.assertEqual(shared["kwargs"].get("custom_1"), 30)
        self.assertEqual(shared["kwargs"].get("custom_2"), 40)
        self.assertEqual(shared["kwargs"].get("ecmwf:variable"), "aaa")
        self.assertEqual(shared["kwargs"].get("ecmwf:format"), "grib")

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_do_search_counts(self, search_plugin):
        """_do_search must create a count query if specified"""
        search_plugin.provider = "cop_dataspace"
        search_plugin.query.return_value = SearchResult(
            self.search_results.data,  # a list must be returned by .query
            self.search_results_size,
        )

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        sr = self.dag._do_search(search_plugin=search_plugin, count=True)
        self.assertIsInstance(sr, SearchResult)
        self.assertEqual(len(sr), self.search_results_size)
        self.assertEqual(sr.number_matched, self.search_results_size)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_do_search_without_count(self, search_plugin):
        """_do_search must be able to create a query without a count"""
        search_plugin.provider = "cop_dataspace"
        search_plugin.query.return_value = SearchResult(
            self.search_results.data,
            None,  # .query must return None if count is False
        )

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        sr = self.dag._do_search(search_plugin=search_plugin, count=False)
        self.assertEqual(sr.number_matched, None)
        self.assertEqual(len(sr), self.search_results_size)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_do_search_paginated_handle_no_count_returned(self, search_plugin):
        """_do_search must return None as count if provider does not return the count"""
        search_plugin.provider = "cop_dataspace"
        search_plugin.query.return_value = SearchResult(self.search_results.data, None)

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        page = 4
        sr = self.dag._do_search(
            count=True,
            search_plugin=search_plugin,
            page=page,
            limit=2,
        )
        self.assertEqual(len(sr), self.search_results_size)
        self.assertIsNone(sr.number_matched)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_do_search_paginated_handle_null_count(self, search_plugin):
        """_do_search must return provider response even if provider returns a null count"""
        search_plugin.provider = "cop_dataspace"
        search_plugin.query.return_value = ([], 0)

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        shared: dict[str, Any] = {"kwargs": {}}

        def fake_query(*args, **kwargs) -> SearchResult:
            shared["kwargs"] = kwargs
            result = SearchResult([])
            result.number_matched = 0
            return result

        search_plugin.query = fake_query

        page = 4
        limit = 10
        sr = self.dag._do_search(
            count=True,
            search_plugin=search_plugin,
            page=page,
            limit=limit,
        )

        self.assertEqual(len(sr), 0)
        self.assertEqual(sr.number_matched, 0)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_do_search_pagination_disabled_less_products(self, search_plugin):
        """_do_search must handle pagination disabled when less products than limit are returned"""
        search_plugin.provider = "cop_dataspace"
        search_plugin.query.return_value = SearchResult(
            [EOProduct("cop_dataspace", {"id": "_"})], next_page_token=2
        )

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        sr = self.dag._do_search(
            count=True,
            search_plugin=search_plugin,
            limit=5,
        )
        # search returns less products than limit
        self.assertEqual(len(sr), 1)
        self.assertIsNone(sr.next_page_token)

        with self.assertRaises(StopIteration):
            next(sr.next_page())

    def test_do_search_does_not_raise_by_default(self):
        """_do_search must not raise any error by default"""

        # provider attribute required internally by __do_search for logging purposes.
        class DummyConfig:
            pagination = {}

        class DummySearchPlugin:
            provider = "cop_dataspace"
            config = DummyConfig()

            def query(*args, **kwargs):
                result = SearchResult([])
                result.number_matched = 0
                return result

        sr = self.dag._do_search(
            search_plugin=DummySearchPlugin(), count=True, validate=False
        )
        self.assertIsInstance(sr, SearchResult)
        self.assertEqual(len(sr), 0)
        self.assertEqual(sr.number_matched, 0)

    def test_do_search_can_raise_errors(self):
        """_do_search must not raise errors if raise_errors=True"""

        class DummySearchPlugin:
            provider = "cop_dataspace"

        # AttributeError raised when .query is tried to be accessed on the dummy plugin.
        with self.assertRaises(AttributeError):
            self.dag._do_search(
                search_plugin=DummySearchPlugin(), raise_errors=True, validate=False
            )

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_do_search_query_products_must_be_a_list(self, search_plugin):
        """_do_search expects that each search plugin returns a list of products."""
        search_plugin.provider = "cop_dataspace"

        # create an "invalid" SearchResult object

        class FakeSearchResult:
            def __init__(self):
                self.data = "not-a-list"  # not a list, will trigger the error
                self.number_matched = 1

        # mock query to return the invalid SearchResult
        search_plugin.query.return_value = FakeSearchResult()

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        with self.assertRaises(PluginImplementationError):
            self.dag._do_search(search_plugin=search_plugin, raise_errors=True)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_do_search_register_downloader_if_search_intersection(self, search_plugin):
        """_do_search must register each product's downloader if search_intersection is not None"""
        search_plugin.provider = "cop_dataspace"
        search_plugin.query.return_value = (
            self.search_results.data,
            self.search_results_size,
        )

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        def fake_query(*args, **kwargs) -> SearchResult:
            return SearchResult([])

        search_plugin.query = fake_query

        sr = self.dag._do_search(search_plugin=search_plugin)
        for product in sr:
            self.assertIsNotNone(product.downloader)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_do_search_doest_not_register_downloader_if_no_search_intersection(
        self, search_plugin
    ):
        """_do_search must not register downloaders if search_intersection is None"""

        class DummyProduct(EOProduct):
            seach_intersecion = None

            def __init__(self):
                self.downloader = None
                super().__init__(provider="cop_dataspace", properties={})

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        search_plugin.provider = "cop_dataspace"

        def fake_query(*args, **kwargs) -> SearchResult:
            products: list[EOProduct] = [DummyProduct(), DummyProduct()]
            results = SearchResult(products)
            results.number_matched = 2
            return results

        search_plugin.query = fake_query

        sr = self.dag._do_search(search_plugin=search_plugin)
        for product in sr:
            self.assertIsNone(product.downloader)

    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_search_iter_page_returns_iterator(self, search_plugin, prepare_seach):
        """search_iter_page must return an iterator"""
        search_plugin.provider = "cop_dataspace"
        # create first and second SearchResult with next_page_token
        first_page = SearchResult(
            products=self.search_results.data, number_matched=None
        )
        first_page.next_page_token = "token_for_page_2"

        second_page = SearchResult(
            products=self.search_results_2.data, number_matched=None
        )
        second_page.next_page_token = None  # last page
        search_plugin.query.side_effect = [first_page, second_page]

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        prepare_seach.return_value = ([search_plugin], {})
        page_iterator = self.dag.search_iter_page_plugin(
            limit=2, search_plugin=search_plugin
        )
        first_result_page = next(page_iterator)
        self.assertIsInstance(first_result_page, SearchResult)
        self.assertEqual(len(first_result_page.data), self.search_results_size)
        second_result_page = next(page_iterator)
        self.assertIsInstance(second_result_page, SearchResult)
        self.assertEqual(len(second_result_page.data), self.search_results_size_2)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    @mock.patch("eodag.api.core.EODataAccessGateway._do_search", autospec=True)
    def test_search_iter_page_count(self, mock_do_seach, mock_fetch_collections_list):
        """search_iter_page must return an iterator"""
        first_page = copy.copy(self.search_results)
        first_page.next_page_token = "token_for_page_2"
        first_page.next_page_token_key = "next_key"
        second_page = self.search_results_2
        mock_do_seach.side_effect = [
            first_page,
            second_page,
        ]

        # no count by default
        page_iterator = self.dag.search_iter_page(collection="S2_MSI_L1C")
        next(page_iterator)
        mock_do_seach.assert_called_once_with(
            mock.ANY,
            mock.ANY,
            collection="S2_MSI_L1C",
            geometry=None,
            raise_errors=True,
            page=1,
            limit=DEFAULT_LIMIT,
        )

        # count only on 1st page if specified
        mock_do_seach.reset_mock()
        first_page = copy.copy(self.search_results)
        first_page.next_page_token = "token_for_page_2"
        first_page.next_page_token_key = "next_key"
        second_page = self.search_results_2
        mock_do_seach.side_effect = [
            first_page,
            second_page,
        ]
        page_iterator = self.dag.search_iter_page(
            collection="S2_MSI_L1C", count=True, limit=2
        )
        next(page_iterator)
        mock_do_seach.assert_called_once_with(
            mock.ANY,
            mock.ANY,
            collection="S2_MSI_L1C",
            geometry=None,
            count=True,
            raise_errors=True,
            page=1,
            limit=2,
        )
        # 2nd page: no count
        next(page_iterator)
        self.assertEqual(mock_do_seach.call_count, 2)
        mock_do_seach.assert_called_with(
            mock.ANY,
            mock.ANY,
            collection="S2_MSI_L1C",
            geometry=None,
            count=False,
            raise_errors=True,
            next_page_token="token_for_page_2",
            next_page_token_key="next_key",
            limit=2,
            number_matched=1,
            validate=False,
        )

    @mock.patch("eodag.api.core.EODataAccessGateway.search_iter_page_plugin")
    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search")
    def test_search_iter_page_requesterror_retry(
        self, mock_prepare_search, mock_search_plugin
    ):
        """Simulate a search with two plugins. The first one fails, the second one succeeds."""
        plugin1 = mock.Mock(provider="provider1")
        plugin2 = mock.Mock(provider="provider2")

        mock_prepare_search.return_value = (
            [plugin1, plugin2],
            {"collection": "S2_MSI_L1C"},
        )
        mock_search_plugin.side_effect = [RequestError("fail"), iter([1, 2, 3])]

        page_iterator = self.dag.search_iter_page(limit=2, collection="S2_MSI_L1C")
        results = list(page_iterator)
        self.assertEqual(results, [1, 2, 3])

        self.assertEqual(mock_search_plugin.call_count, 2)

    @mock.patch("eodag.api.core.EODataAccessGateway.search_iter_page_plugin")
    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search")
    def test_search_iter_page_requesterror_all_fail(
        self, mock_prepare_search, mock_search_plugin
    ):
        """Simulate a search with two plugins that both fail."""
        plugin1 = mock.Mock(provider="provider1")
        plugin2 = mock.Mock(provider="provider2")

        mock_prepare_search.return_value = (
            [plugin1, plugin2],
            {"collection": "S2_MSI_L1C"},
        )
        mock_search_plugin.side_effect = [RequestError("fail1"), RequestError("fail2")]

        with self.assertRaises(RequestError):
            list(self.dag.search_iter_page(limit=2, collection="S2_MSI_L1C"))

    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_search_iter_page_exhaust_get_all_pages_and_quit_early(
        self, search_plugin, prepare_seach
    ):
        """search_iter_page must stop as soon as less than limit products were retrieved"""
        search_plugin.provider = "cop_dataspace"
        # create first and second SearchResult with next_page_token
        first_page = SearchResult(
            products=self.search_results.data, number_matched=None
        )
        first_page.next_page_token = "token_for_page_2"

        second_page = SearchResult(
            products=[self.search_results_2.data[0]], number_matched=None
        )
        second_page.next_page_token = None  # last page
        search_plugin.query.side_effect = [first_page, second_page]

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        prepare_seach.return_value = ([search_plugin], {})
        page_iterator = self.dag.search_iter_page_plugin(
            limit=2, search_plugin=search_plugin
        )
        all_page_results = list(page_iterator)
        self.assertEqual(len(all_page_results), 2)
        self.assertIsInstance(all_page_results[0], SearchResult)

    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_search_iter_page_exhaust_get_all_pages_no_products_last_page(
        self, search_plugin, prepare_seach
    ):
        """search_iter_page must stop if the page doesn't return any product"""
        search_plugin.provider = "cop_dataspace"
        # create 3 SearchResult with next_page_token
        first_page = SearchResult(
            products=self.search_results.data, number_matched=None
        )
        first_page.next_page_token = "token_for_page_2"
        first_page.search_params = {"limit": 2}

        second_page = SearchResult(
            products=self.search_results_2.data, number_matched=None
        )
        second_page.next_page_token = "token_for_page_3"  # last page
        second_page.search_params = {"limit": 2}

        third_page = SearchResult(products=[], number_matched=None)
        search_plugin.query.side_effect = [first_page, second_page, third_page]

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        prepare_seach.return_value = ([search_plugin], {})
        page_iterator = self.dag.search_iter_page_plugin(
            limit=2, search_plugin=search_plugin
        )
        all_page_results = list(page_iterator)
        self.assertEqual(len(all_page_results), 2)
        self.assertIsInstance(all_page_results[0], SearchResult)

    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_search_iter_page_does_not_handle_query_errors(
        self, search_plugin, prepare_seach
    ):
        """search_iter_page must propagate errors"""
        search_plugin.provider = "cop_dataspace"
        search_plugin.query.side_effect = AttributeError()
        page_iterator = self.dag.search_iter_page_plugin(search_plugin=search_plugin)
        with self.assertRaises(AttributeError):
            next(page_iterator)

    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_finally_breaks_when_same_product_as_previous(
        self, search_plugin, prepare_seach
    ):
        """search_iter_page must stop if the next page appears to have the same products"""

        class DummyConfig:
            pagination = {"next_page_url_tpl": "tpl"}

        search_plugin.config = DummyConfig()
        search_plugin.provider = "cop_dataspace"
        search_plugin.next_page_url = "page2"
        search_plugin.next_page_query_obj = None
        search_plugin.next_page_merge = False

        same_product = mock.Mock()
        same_product.properties = {"id": "123"}
        same_product.provider = "cop_dataspace"

        result_page1 = mock.Mock()
        result_page1.number_matched = 10
        result_page1.__getitem__ = lambda self, i: [same_product, mock.Mock()][i]
        result_page1.__iter__ = lambda self: iter([same_product, mock.Mock()])
        result_page1.__len__ = lambda self: 2

        result_page2 = mock.Mock()
        result_page2.number_matched = 10
        result_page2.__getitem__ = lambda self, i: [same_product, mock.Mock()][i]
        result_page2.__iter__ = lambda self: iter([same_product, mock.Mock()])
        result_page2.__len__ = lambda self: 2

        prepare_seach.return_value = ([search_plugin], {})

        with mock.patch.object(
            self.dag,
            "_do_search",
            side_effect=[
                SearchResult(result_page1, 2, next_page_token="token_for_page_2"),
                SearchResult(result_page2, 2),
            ],
        ):
            with self.assertLogs(level="WARNING") as cm_logs:
                page_iterator = self.dag.search_iter_page_plugin(
                    limit=2, search_plugin=search_plugin
                )

                first_page = next(page_iterator)
                self.assertEqual(len(first_page), 2)

                with self.assertRaises(StopIteration):
                    next(page_iterator)

        self.assertIn(
            "stop iterating since the next page appears to have the same products",
            "".join(cm_logs.output),
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    def test_search_iter_page_must_reset_next_attrs_if_next_mechanism(
        self, normalize_results, _request
    ):
        """search_iter_page must reset the search plugin if the next mechanism is used"""
        # More specifically: next_page_url must be None and
        # config.pagination["next_page_url_tpl"] must be equal to its original value.
        _request.return_value.json.return_value = {
            "features": [],
            "links": [{"rel": "next", "href": "url/to/next/page"}],
        }

        p1 = EOProduct("dummy", dict(geometry="POINT (0 0)", id="1"))
        p1.search_intersection = None
        p2 = EOProduct("dummy", dict(geometry="POINT (0 0)", id="2"))
        p2.search_intersection = None
        normalize_results.side_effect = [[p1], [p2]]
        dag = EODataAccessGateway()
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_url_tpl: 'dummy_next_page_url_tpl'
                    next_page_url_key_path: '$.links[?(@.rel="next")].href'
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    _collection: '{collection}'
        """
        dag.update_providers_config(dummy_provider_config)
        dag.set_preferred_provider("dummy_provider")

        search_plugin = next(
            dag._plugins_manager.get_search_plugins(collection="S2_MSI_L1C")
        )
        self.assertIsNone(search_plugin.next_page_url)
        self.assertEqual(
            search_plugin.config.pagination["next_page_url_tpl"],
            "dummy_next_page_url_tpl",
        )

    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    def test_search_sort_by(
        self,
        mock_normalize_results,
        mock_qssearch__request,
        mock_postjsonsearch__request,
    ):
        """search must sort results by sorting parameter(s) in their sorting order
        from the "sort_by" argument or by default sorting parameter if exists"""
        mock_qssearch__request.return_value.json.return_value = {
            "properties": {"totalResults": 2},
            "features": [],
            "links": [{"rel": "next", "href": "url/to/next/page"}],
        }
        mock_postjsonsearch__request.return_value.json.return_value = {
            "meta": {"found": 2},
            "features": [],
            "links": [{"rel": "next", "href": "url/to/next/page"}],
        }

        p1 = EOProduct(
            "dummy", dict(geometry="POINT (0 0)", id="1", eodagSortParam="1")
        )
        p1.search_intersection = None
        p2 = EOProduct(
            "dummy", dict(geometry="POINT (0 0)", id="2", eodagSortParam="2")
        )
        p2.search_intersection = None
        mock_normalize_results.return_value = [p2, p1]

        dag = EODataAccessGateway()

        # with a GET mode search
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_url_tpl: '{url}?{search}'
                    total_items_nb_key_path: '$.properties.totalResults'
                sort:
                    sort_by_tpl: '&sortParam={sort_param}&sortOrder={sort_order}'
                    sort_param_mapping:
                        eodagSortParam: providerSortParam
                    sort_order_mapping:
                        ascending: asc
                        descending: desc
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    _collection: '{collection}'
        """
        dag.update_providers_config(dummy_provider_config)

        dag.search(
            provider="dummy_provider",
            collection="S2_MSI_L1C",
            sort_by=[("eodagSortParam", "DESC")],
        )

        # a provider-specific string has been created to sort by
        self.assertIn(
            "sortParam=providerSortParam&sortOrder=desc",
            mock_qssearch__request.call_args[0][1].url,
        )

        # with a POST mode search
        dummy_provider_config = """
        other_dummy_provider:
            search:
                type: PostJsonSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_query_obj: '{{"limit":{limit},"page":{next_page_token}}}'
                    total_items_nb_key_path: '$.meta.found'
                sort:
                    sort_by_tpl: '{{"sort_by": [ {{"field": "{sort_param}", "direction": "{sort_order}" }} ] }}'
                    sort_param_mapping:
                        eodagSortParam: providerSortParam
                    sort_order_mapping:
                        ascending: asc
                        descending: desc
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    _collection: '{collection}'
        """
        dag.update_providers_config(dummy_provider_config)
        dag.search(
            provider="other_dummy_provider",
            collection="S2_MSI_L1C",
            sort_by=[("eodagSortParam", "DESC")],
        )

        # a provider-specific dictionary has been created to sort by
        self.assertIn(
            "sort_by", mock_postjsonsearch__request.call_args[0][1].query_params.keys()
        )
        self.assertEqual(
            [{"field": "providerSortParam", "direction": "desc"}],
            mock_postjsonsearch__request.call_args[0][1].query_params["sort_by"],
        )

        # TODO: sort by default sorting parameter and sorting order

    def test_search_sort_by_raise_errors(self):
        """search used with "sort_by" argument must raise errors if the argument is incorrect or if the provider does
        not support a maximum number of sorting parameter, one sorting parameter or the sorting feature
        """
        dag = EODataAccessGateway()
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_url_tpl: '{url}?{search}{sort_by}&maxRecords={limit}&page={page}&exactCount=1'
                    total_items_nb_key_path: '$.properties.totalResults'
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    _collection: '{collection}'
        """
        dag.update_providers_config(dummy_provider_config)
        # raise an error with a provider which does not support sorting feature
        with self.assertLogs(level="ERROR") as cm_logs:
            dag.search(
                provider="dummy_provider",
                collection="S2_MSI_L1C",
                sort_by=[("eodagSortParam", "ASC")],
            )
            self.assertIn(
                "dummy_provider does not support sorting feature", str(cm_logs.output)
            )

        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_url_tpl: '{url}?{search}{sort_by}&maxRecords={limit}&page={page}&exactCount=1'
                    total_items_nb_key_path: '$.properties.totalResults'
                sort:
                    sort_by_tpl: '&sortParam={sort_param}&sortOrder={sort_order}'
                    sort_param_mapping:
                        eodagSortParam: providerSortParam
                    sort_order_mapping:
                        ascending: asc
                        descending: desc
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    _collection: '{collection}'
        """
        dag.update_providers_config(dummy_provider_config)
        # raise an error with a parameter not sortable with a provider
        with self.assertLogs(level="ERROR") as cm_logs:
            dag.search(
                provider="dummy_provider",
                collection="S2_MSI_L1C",
                sort_by=[("otherEodagSortParam", "ASC")],
            )
            self.assertIn(
                "\\'otherEodagSortParam\\' parameter is not sortable with dummy_provider. "
                "Here is the list of sortable parameter(s) with dummy_provider: eodagSortParam",
                str(cm_logs.output),
            )

        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_url_tpl: '{url}?{search}{sort_by}&maxRecords={limit}&page={page}&exactCount=1'
                    total_items_nb_key_path: '$.properties.totalResults'
                sort:
                    sort_by_tpl: '&sortParam={sort_param}&sortOrder={sort_order}'
                    sort_param_mapping:
                        eodagSortParam: providerSortParam
                        otherEodagSortParam: otherProviderSortParam
                    sort_order_mapping:
                        ascending: asc
                        descending: desc
                    max_sort_params: 1
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    _collection: '{collection}'
        """
        dag.update_providers_config(dummy_provider_config)
        # raise an error with more sorting parameters than supported by the provider
        with self.assertLogs(level="ERROR") as cm_logs:
            dag.search(
                provider="dummy_provider",
                collection="S2_MSI_L1C",
                sort_by=[("eodagSortParam", "ASC"), ("otherEodagSortParam", "ASC")],
            )
            self.assertIn(
                "Search results can be sorted by only 1 parameter(s) with dummy_provider",
                str(cm_logs.output),
            )

    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_search_all_must_collect_them_all(self, search_plugin, prepare_seach):
        """search_all must return all the products available"""
        search_plugin.provider = "cop_dataspace"
        first_page = SearchResult(self.search_results.data, None)
        first_page.next_page_token = "token_for_page_2"
        second_page = SearchResult([self.search_results_2.data[0]], None)
        search_plugin.query.side_effect = [
            first_page,
            second_page,
        ]

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        # Infinite generator here because passing directly the dict to
        # prepare_search.return_value (or side_effect) didn't work. One function
        # would do a dict.pop("search_plugin") that would remove the item from the
        # mocked return value. Later calls would then break
        def yield_search_plugin():
            while True:
                yield ([search_plugin], {})

        prepare_seach.side_effect = yield_search_plugin()
        all_results = self.dag.search_all(limit=2)
        self.assertIsInstance(all_results, SearchResult)
        self.assertEqual(len(all_results), 3)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway._do_search",
        autospec=True,
        return_value=(SearchResult([mock.Mock()], 1)),
    )
    def test_search_all_use_max_limit(self, mock__do_search):
        """search_all must use the configured parameter max_limit if available"""
        dag = EODataAccessGateway()
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    max_limit: 2
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    _collection: '{collection}'
        """
        mock__do_search.side_effect = [SearchResult([self.search_results.data[0]], 1)]
        dag.update_providers_config(dummy_provider_config)
        dag.set_preferred_provider("dummy_provider")
        dag.search_all(collection="S2_MSI_L1C")

        first_call_kwargs = mock__do_search.call_args_list[0][1]
        self.assertEqual(first_call_kwargs["limit"], 2)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway._do_search",
        autospec=True,
        return_value=(SearchResult([mock.Mock()], 1)),
    )
    def test_search_all_use_default_value(self, mock__do_search):
        """search_all must use the DEFAULT_MAX_LIMIT if the provider's one wasn't configured"""
        dag = EODataAccessGateway()
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    _collection: '{collection}'
        """
        mock__do_search.side_effect = [SearchResult([self.search_results.data[0]], 1)]
        dag.update_providers_config(dummy_provider_config)
        dag.set_preferred_provider("dummy_provider")
        dag.search_all(collection="S2_MSI_L1C")

        self.assertEqual(
            mock__do_search.call_args_list[0].kwargs["limit"],
            DEFAULT_MAX_LIMIT,
        )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway._do_search",
        autospec=True,
    )
    def test_search_all_user_limit(self, mock__do_search):
        """search_all must use the value of limit provided by the user"""
        dag = EODataAccessGateway()
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    _collection: '{collection}'
        """
        mock__do_search.side_effect = [SearchResult([self.search_results.data[0]], 1)]
        dag.update_providers_config(dummy_provider_config)
        dag.set_preferred_provider("dummy_provider")
        dag.search_all(collection="S2_MSI_L1C", limit=7)

        self.assertEqual(mock__do_search.call_args_list[0].kwargs["limit"], 7)

    @mock.patch(
        "eodag.plugins.manager.PluginManager.get_auth",
        autospec=True,
    )
    def test_search_all_request_error(self, mock_get_auth):
        """search_all must stop iteration and move to next provider when error occurs"""

        collection = "S2_MSI_L1C"
        dag = EODataAccessGateway()

        def fake_request(*args, **kwargs):
            raise RequestError()

        for plugin in dag._plugins_manager.get_search_plugins(collection=collection):
            plugin.discover_queryables = mock.MagicMock()
            plugin.query = mock.MagicMock()
            plugin.query.side_effect = fake_request

        try:
            results = dag.search_all(collection="S2_MSI_L1C")
            self.assertEqual(len(results), 0)
        except RequestError:
            pass

        for plugin in dag._plugins_manager.get_search_plugins(collection=collection):
            self.assertEqual(
                plugin.query.call_count,
                1,
                "Expected to be called once, {} call count = {}".format(
                    plugin, plugin.query.call_count
                ),
            )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway._do_search",
        autospec=True,
        return_value=(SearchResult([mock.Mock()], 1)),
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    def test_search_all_unknown_collection(
        self, mock_fetch_collections_list, mock__do_search
    ):
        """search_all must fetch collections if collection is unknown"""
        self.dag.search_all(collection="foo")
        mock_fetch_collections_list.assert_called_with(self.dag)
        mock__do_search.assert_called_once()

    def test_fetch_external_collection_with_auth(self):
        """test _fetch_external_collection when the plugin needs authentication"""
        provider = "cop_dataspace"
        collection = "S2_MSI_L1C"

        plugin = mock.Mock()
        plugin.config = mock.Mock()
        plugin.config.discover_collections = {"fetch_url": "http://fake-fetch-url"}
        plugin.config.need_auth = True
        plugin.config.api_endpoint = "http://fake-api"
        plugin.provider = provider

        plugin.discover_collections = mock.Mock(return_value={"product1": {}})

        dag = EODataAccessGateway()
        dag._plugins_manager = mock.Mock()
        dag._plugins_manager.get_search_plugins.return_value = iter([plugin])
        auth_mock = mock.Mock()
        dag._plugins_manager.get_auth.return_value = auth_mock
        dag.update_collections_list = mock.Mock()
        dag._fetch_external_collection(provider, collection)

        dag._plugins_manager.get_auth.assert_called_once_with(
            plugin.provider, plugin.config.api_endpoint, plugin.config
        )
        plugin.discover_collections.assert_called_once_with(
            collection=collection, auth=auth_mock
        )
        dag.update_collections_list.assert_called_once_with(
            {provider: {"product1": {}}}
        )

    def test_core_crunch(self):
        """Test crunch method with multiple crunchers"""
        results = mock.Mock()
        results_after_first = mock.Mock()
        results_after_second = mock.Mock()

        results.crunch.return_value = results_after_first
        results_after_first.crunch.return_value = results_after_second

        dag = EODataAccessGateway()
        cruncher_1 = mock.Mock()
        cruncher_2 = mock.Mock()
        dag._plugins_manager = mock.Mock()
        dag._plugins_manager.get_crunch_plugin.side_effect = [cruncher_1, cruncher_2]

        kwargs = {
            "cruncher1": {"arg1": 1},
            "cruncher2": {"arg2": 2},
            "search_criteria": {"filter": "value"},
        }

        final_result = dag.crunch(results, **kwargs)

        dag._plugins_manager.get_crunch_plugin.assert_has_calls(
            [
                mock.call("cruncher1", **{"arg1": 1}),
                mock.call("cruncher2", **{"arg2": 2}),
            ]
        )

        results.crunch.assert_called_once_with(cruncher_1, **{"filter": "value"})
        results_after_first.crunch.assert_called_once_with(
            cruncher_2, **{"filter": "value"}
        )

        self.assertEqual(final_result, results_after_second)

    def test_get_cruncher(self):
        """Test get_cruncher method"""
        dag = EODataAccessGateway()
        dag._plugins_manager = mock.Mock()

        expected_crunch = mock.Mock()
        dag._plugins_manager.get_crunch_plugin.return_value = expected_crunch
        crunch = dag.get_cruncher(
            "my_cruncher",
            option1="value1",
            option2="value2",
            **{"option-with-dash": "dash_value"},
        )
        expected_conf = {
            "name": "my_cruncher",
            "option1": "value1",
            "option2": "value2",
            "option_with_dash": "dash_value",
        }
        dag._plugins_manager.get_crunch_plugin.assert_called_once_with(
            "my_cruncher", **expected_conf
        )
        self.assertEqual(crunch, expected_crunch)
