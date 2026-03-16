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
from importlib.resources import files as res_files
from unittest import mock

from lxml import html
from pydantic import ValidationError as PydanticValidationError
from requests.exceptions import RequestException

from eodag import EODataAccessGateway
from eodag import __version__ as eodag_version
from eodag.api.collection import Collection, CollectionsList
from eodag.api.provider import ProviderConfig
from eodag.api.search_result import SearchResult
from eodag.config import load_default_config
from eodag.types import model_fields_to_annotated
from eodag.types.queryables import CommonQueryables, Queryables, QueryablesDict
from eodag.utils.exceptions import RequestError, UnsupportedProvider, ValidationError
from tests.units.core.base import TestCoreBase
from tests.utils import SUPPORTED_COLLECTIONS, SUPPORTED_PROVIDERS, TEST_RESOURCES_PATH


class TestCore(TestCoreBase):
    def setUp(self):
        super().setUp()
        self.dag = EODataAccessGateway()
        self.conf_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
        # mock os.environ to empty env
        self.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        self.mock_os_environ.start()

    def tearDown(self):
        super().tearDown()
        # stop os.environ
        self.mock_os_environ.stop()

    def test_supported_providers_in_unit_test(self):
        """Every provider must be referenced in the core unittest SUPPORTED_PROVIDERS class attribute"""
        for provider in self.dag.providers.names:
            self.assertIn(provider, SUPPORTED_PROVIDERS)

    def test_supported_collections_in_unit_test(self):
        """Every collection must be referenced in the core unit test SUPPORTED_COLLECTIONS class attribute"""
        for collection in self.dag.list_collections(fetch_providers=False):
            assert (
                collection.id in SUPPORTED_COLLECTIONS.keys()
                or collection._id in SUPPORTED_COLLECTIONS.keys()
            )

    def test_list_collections_ok(self):
        """Core api must correctly return the list of supported collections"""
        collections = self.dag.list_collections(fetch_providers=False)
        self.assertIsInstance(collections, CollectionsList)
        for collection in collections:
            self.assertIsInstance(collection, Collection)
        # There should be no repeated collection in the output
        self.assertEqual(len(collections), len(set(col.id for col in collections)))
        # add alias for collection - should still work
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
        collections = self.dag.list_collections(fetch_providers=False)
        for collection in collections:
            self.assertIsInstance(collection, Collection)
        # There should be no repeated collection in the output
        self.assertEqual(len(collections), len(set(col.id for col in collections)))
        # use alias as id
        self.assertIn("S2_MSI_ALIAS", [col.id for col in collections])

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

    def test_list_collections_for_provider_ok(self):
        """Core api must correctly return the list of supported collections for a given provider"""
        for provider in SUPPORTED_PROVIDERS:
            try:
                collections = self.dag.list_collections(
                    provider=provider, fetch_providers=False
                )
                self.assertIsInstance(collections, CollectionsList)
                for collection in collections:
                    self.assertIsInstance(collection, Collection)
                    if collection.id in SUPPORTED_COLLECTIONS:
                        self.assertIn(
                            provider,
                            SUPPORTED_COLLECTIONS[collection.id],
                            f"missing in supported providers for {collection.id}",
                        )
                    else:
                        self.assertIn(
                            provider,
                            SUPPORTED_COLLECTIONS[collection._id],
                            f"missing in supported providers for {collection._id}",
                        )
            except UnsupportedProvider:
                pass

    def test_list_collections_for_unsupported_provider(self):
        """Core api must raise UnsupportedProvider error for list_collections with unsupported provider"""
        unsupported_provider = "a"
        try:
            _ = self.dag.list_collections(unsupported_provider)
            self.fail("Expect UnsupportedProvider error")
        except UnsupportedProvider:
            pass
        except Exception as e:
            self.fail(e)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    def test_list_collections_fetch_providers(self, mock_fetch_collections_list):
        """Core api must fetch providers for new collections if option is passed to list_collections"""
        self.dag.list_collections(fetch_providers=False)
        assert not mock_fetch_collections_list.called

        try:
            self.dag.list_collections(provider="cop_dataspace", fetch_providers=True)
            mock_fetch_collections_list.assert_called_once_with(
                self.dag, provider="cop_dataspace"
            )
        except UnsupportedProvider:
            pass

    def test_guess_collection_with_filter(self):
        """Testing the search terms"""

        with open(
            os.path.join(TEST_RESOURCES_PATH, "ext_collections_free_text_search.json")
        ) as f:
            ext_collections_conf = json.load(f)
        self.dag.update_collections_list(ext_collections_conf)

        # Search any filter contains filter value
        filter = "ABSTRACTFOO"
        collections_ids = [col.id for col in self.dag.guess_collection(filter)]
        self.assertListEqual(collections_ids, ["foo"])
        # Search the exact phrase. Search is case insensitive
        filter = '"THIS IS FOO. fooandbar"'
        collections_ids = [col.id for col in self.dag.guess_collection(filter)]
        self.assertListEqual(collections_ids, ["foo"])

        # Free text search: match in the keywords
        filter = "LECTUS_BAR_KEY"
        collections_ids = [col.id for col in self.dag.guess_collection(filter)]
        self.assertListEqual(collections_ids, ["bar"])

        # Free text search: match the phrase in title
        filter = '"FOOBAR COLLECTION"'
        collections_ids = [col.id for col in self.dag.guess_collection(filter)]
        self.assertListEqual(collections_ids, ["foobar_alias"])

        # Free text search: Using OR term match
        filter = "FOOBAR OR BAR"
        collections_ids = [col.id for col in self.dag.guess_collection(filter)]
        self.assertListEqual(sorted(collections_ids), ["bar", "foobar_alias"])

        # Free text search: using OR term match with additional filter UNION
        filter = "FOOBAR OR BAR"
        collections_ids = [
            col.id for col in self.dag.guess_collection(filter, title="FOO")
        ]
        self.assertListEqual(sorted(collections_ids), ["bar", "foo", "foobar_alias"])

        # Free text search: Using AND term match
        filter = "suspendisse AND FOO"
        collections_ids = [col.id for col in self.dag.guess_collection(filter)]
        self.assertListEqual(collections_ids, ["foo"])

        # Free text search: Parentheses can be used to group terms
        filter = "(FOOBAR OR BAR) AND titleFOOBAR"
        collections_ids = [col.id for col in self.dag.guess_collection(filter)]
        self.assertListEqual(collections_ids, ["foobar_alias"])

        # Free text search: multiple terms joined with param search (INTERSECT)
        filter = "FOOBAR OR BAR"
        collections_ids = [
            col.id
            for col in self.dag.guess_collection(
                filter, intersect=True, title="titleFOO*"
            )
        ]
        self.assertListEqual(collections_ids, ["foobar_alias"])

    def test_guess_collection_with_mission_dates(self):
        """Testing the datetime interval"""

        with open(
            os.path.join(TEST_RESOURCES_PATH, "ext_collections_free_text_search.json")
        ) as f:
            ext_collections_conf = json.load(f)
        self.dag.update_collections_list(ext_collections_conf)

        collections_ids = [
            col.id
            for col in self.dag.guess_collection(
                title="TEST DATES",
                start_date="2013-02-01",
                end_date="2013-02-05",
            )
        ]
        self.assertListEqual(collections_ids, ["interval_end"])
        collections_ids = [
            col.id
            for col in self.dag.guess_collection(
                title="TEST DATES",
                start_date="2013-02-01",
                end_date="2013-02-15",
            )
        ]
        self.assertListEqual(
            sorted(collections_ids),
            ["interval_end", "interval_start", "interval_start_end"],
        )
        collections_ids = [
            col.id
            for col in self.dag.guess_collection(
                title="TEST DATES", start_date="2013-02-01"
            )
        ]
        self.assertListEqual(
            sorted(collections_ids),
            ["interval_end", "interval_start", "interval_start_end"],
        )
        collections_ids = [
            col.id
            for col in self.dag.guess_collection(
                title="TEST DATES", end_date="2013-02-20"
            )
        ]
        self.assertListEqual(
            sorted(collections_ids),
            ["interval_end", "interval_start", "interval_start_end"],
        )

    def test_update_collections_list(self):
        """Core api.update_collections_list must update eodag collections list"""
        with open(os.path.join(TEST_RESOURCES_PATH, "ext_collections.json")) as f:
            ext_collections_conf = json.load(f)

        self.assertNotIn("foo", self.dag._providers["earth_search"].collections_config)
        self.assertNotIn("bar", self.dag._providers["earth_search"].collections_config)
        self.assertNotIn("foo", self.dag.collections_config)
        self.assertNotIn("bar", self.dag.collections_config)

        self.dag.update_collections_list(ext_collections_conf)

        self.assertIn("foo", self.dag._providers["earth_search"].collections_config)
        self.assertIn("bar", self.dag._providers["earth_search"].collections_config)
        self.assertEqual(self.dag.collections_config["foo"].license, "WTFPL")
        self.assertEqual(self.dag.collections_config["bar"].title, "Bar collection")

    def test_update_collections_list_unknown_provider(self):
        """Core api.update_collections_list on unkwnown provider must not crash and not update conf"""
        with open(os.path.join(TEST_RESOURCES_PATH, "ext_collections.json")) as f:
            ext_collections_conf = json.load(f)
        self.dag._providers.pop("earth_search")

        self.dag.update_collections_list(ext_collections_conf)
        self.assertNotIn("earth_search", self.dag._providers)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.discover_collections",
        autospec=True,
    )
    def test_update_collections_list_with_api_plugin(
        self, mock_plugin_discover_collections
    ):
        """Core api.update_collections_list with the api plugin must update eodag collections list"""
        with open(os.path.join(TEST_RESOURCES_PATH, "ext_collections.json")) as f:
            ext_collections_conf = json.load(f)

        # we keep the existing ext-conf to use it for a provider with an api plugin
        ext_collections_conf["ecmwf"] = ext_collections_conf.pop("earth_search")

        self.assertNotIn("foo", self.dag._providers["ecmwf"].collections_config)
        self.assertNotIn("bar", self.dag._providers["ecmwf"].collections_config)
        self.assertNotIn("foo", self.dag.collections_config)
        self.assertNotIn("bar", self.dag.collections_config)

        # update existing provider conf and check that update_collections_list() is launched for it
        self.dag.update_providers_config(
            """
            ecmwf:
                api:
                    discover_collections:
                        fetch_url: 'http://new-endpoint'
                    need_auth: False
            """
        )

        self.dag.update_collections_list(ext_collections_conf)

        self.assertIn("foo", self.dag._providers["ecmwf"].collections_config)
        self.assertIn("bar", self.dag._providers["ecmwf"].collections_config)
        self.assertEqual(self.dag.collections_config["foo"].license, "WTFPL")
        self.assertEqual(self.dag.collections_config["bar"].title, "Bar collection")

    def test_update_collections_list_without_plugin(self):
        """Core api.update_collections_list without search and api plugin do nothing"""
        with open(os.path.join(TEST_RESOURCES_PATH, "ext_collections.json")) as f:
            ext_collections_conf = json.load(f)

        self.assertNotIn("foo", self.dag._providers["earth_search"].collections_config)
        self.assertNotIn("bar", self.dag._providers["earth_search"].collections_config)
        self.assertNotIn("foo", self.dag.collections_config)
        self.assertNotIn("bar", self.dag.collections_config)

        delattr(self.dag._providers["earth_search"].config, "search")

        self.dag.update_collections_list(ext_collections_conf)

        self.assertNotIn("foo", self.dag._providers["earth_search"].collections_config)
        self.assertNotIn("bar", self.dag._providers["earth_search"].collections_config)
        self.assertNotIn("foo", self.dag.collections_config)
        self.assertNotIn("bar", self.dag.collections_config)

    def test_update_collections_list_errors_handling(self):
        """Core api.update_collections_list must skip a collection with a log if its id is not a string and
        must log a summary for a provider if an attribute (except id) of at least one of its collection has
        bad formatted attributed even if collection validation is disabled"""
        provider = "earth_search"
        try:
            # ensure validation is disabled for collections
            os.environ["EODAG_VALIDATE_COLLECTIONS"] = "False"

            # case when an argument of the collection (except id) is wrong

            with open(os.path.join(TEST_RESOURCES_PATH, "ext_collections.json")) as f:
                ext_collections_conf = json.load(f)

            # update the external conf with wrong attributes
            ext_collections_conf[provider]["providers_config"].update(
                {
                    "foo": {
                        "collection": "foo",
                        "metadata_mapping": {"cloudCover": "$.null"},
                    }
                }
            )

            ext_collections_conf[provider]["collections_config"].update(
                {"foo": {"processing:level": 100}}
            )

            # remove a collection useless for this test from the external conf
            del ext_collections_conf[provider]["providers_config"]["bar"]
            del ext_collections_conf[provider]["collections_config"]["bar"]

            # log a message to tell that bad attributes have been skipped on collections of the provider
            with self.assertLogs(level="DEBUG") as cm:
                self.dag.update_collections_list(ext_collections_conf)

            self.assertEqual(
                len(ext_collections_conf[provider]["collections_config"]), 1
            )

            self.assertIn(
                f"bad formatted attributes skipped for 1 collection(s) on {provider}",
                str(cm.output),
            )

            # check that the collection has been added to the config
            self.assertIn("foo", self.dag._providers["earth_search"].collections_config)

            # remove the wrong collection from the external conf
            del ext_collections_conf[provider]["providers_config"]["foo"]
            del ext_collections_conf[provider]["collections_config"]["foo"]

            # case when id is not a string case

            with open(os.path.join(TEST_RESOURCES_PATH, "ext_collections.json")) as f:
                ext_collections_conf = json.load(f)

            # update the external conf with an id which is not a string
            ext_collections_conf[provider]["providers_config"].update(
                {
                    100: {
                        "collection": 100,
                        "metadata_mapping": {"cloudCover": "$.null"},
                    }
                }
            )

            ext_collections_conf[provider]["collections_config"].update(
                {
                    100: {
                        "title": "Foo collection",
                    }
                }
            )

            # log a message to tell that the collection has been skipped
            with self.assertLogs(level="DEBUG") as cm:
                self.dag.update_collections_list(ext_collections_conf)

            self.assertIn(
                f"Collection 100 has been pruned on provider {provider} "
                "because its id was incorrectly parsed for eodag",
                str(cm.output),
            )

            # check that the collection has not been added to the config
            self.assertNotIn(
                100, self.dag._providers["earth_search"].collections_config
            )

            # remove the wrong collection from the external conf
            del ext_collections_conf[provider]["providers_config"][100]
            del ext_collections_conf[provider]["collections_config"][100]

        finally:
            # remove the environment variable
            os.environ.pop("EODAG_VALIDATE_COLLECTIONS", None)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.discover_collections",
        autospec=True,
        return_value={
            "providers_config": {"foo": {"_collection": "foo"}},
            "collections_config": {"foo": {"title": "Foo collection"}},
        },
    )
    def test_discover_collections(self, mock_plugin_discover_collections):
        """Core api must fetch providers for collections"""
        ext_collections_conf = self.dag.discover_collections(provider="earth_search")
        self.assertEqual(
            ext_collections_conf["earth_search"]["providers_config"]["foo"][
                "_collection"
            ],
            "foo",
        )
        self.assertEqual(
            ext_collections_conf["earth_search"]["collections_config"]["foo"]["title"],
            "Foo collection",
        )

    @mock.patch(
        "eodag.plugins.apis.ecmwf.EcmwfApi.discover_collections",
        autospec=True,
        return_value={
            "providers_config": {"foo": {"_collection": "foo"}},
            "collections_config": {"foo": {"title": "Foo collection"}},
        },
    )
    def test_discover_collections_with_api_plugin(
        self, mock_plugin_discover_collections
    ):
        """Core api must fetch providers with api plugin for collections"""
        self.dag.update_providers_config(
            """
            ecmwf:
                api:
                    discover_collections:
                        fetch_url: 'http://new-endpoint'
                    need_auth: False
            """
        )
        ext_collections_conf = self.dag.discover_collections(provider="ecmwf")
        self.assertEqual(
            ext_collections_conf["ecmwf"]["providers_config"]["foo"]["_collection"],
            "foo",
        )
        self.assertEqual(
            ext_collections_conf["ecmwf"]["collections_config"]["foo"]["title"],
            "Foo collection",
        )

    def test_discover_collections_without_plugin(self):
        """Core api must not fetch providers without search and api plugins"""
        delattr(self.dag._providers["earth_search"].config, "search")
        ext_collections_conf = self.dag.discover_collections(provider="earth_search")
        self.assertEqual(
            ext_collections_conf,
            None,
        )

    @mock.patch("eodag.api.core.get_ext_collections_conf", autospec=True)
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.discover_collections", autospec=True
    )
    def test_fetch_collections_list(
        self, mock_discover_collections, mock_get_ext_collections_conf
    ):
        """Core api must fetch collections list and update if needed"""
        # check that no provider has already been fetched
        for provider in self.dag._providers.values():
            self.assertFalse(provider.collections_fetched)

        # check that by default get_ext_collections_conf() is called without args
        self.dag.fetch_collections_list()
        mock_get_ext_collections_conf.assert_called_with()

        # check that with an empty/mocked ext-conf, no provider has been fetched
        for provider in self.dag._providers.values():
            self.assertFalse(provider.collections_fetched)

        # check that EODAG_EXT_COLLECTIONS_CFG_FILE env var will be used as get_ext_collections_conf() arg
        os.environ["EODAG_EXT_COLLECTIONS_CFG_FILE"] = "some/file"
        self.dag.fetch_collections_list()
        mock_get_ext_collections_conf.assert_called_with("some/file")
        os.environ.pop("EODAG_EXT_COLLECTIONS_CFG_FILE")

        # check that with a non-empty ext-conf, a provider will be marked as fetched, and eodag conf updated
        mock_get_ext_collections_conf.return_value = {
            "earth_search": {
                "providers_config": {"foo": {"_collection": "foo"}},
                "collections_config": {"foo": {"title": "Foo collection"}},
            }
        }
        # add an empty ext-conf for other providers to prevent them to be fetched
        for provider in self.dag._providers.values():
            if provider != "earth_search" and provider.fetchable:
                mock_get_ext_collections_conf.return_value[provider] = {}

        self.dag.fetch_collections_list()
        self.assertTrue(self.dag._providers["earth_search"].collections_fetched)
        self.assertEqual(
            self.dag._providers["earth_search"].collections_config["foo"],
            {"_collection": "foo"},
        )
        self.assertEqual(
            self.dag.collections_config.data["foo"],
            Collection.create_with_dag(self.dag, id="foo", title="Foo collection"),
        )

        # update existing provider conf and check that discover_collections() is launched for it
        self.assertEqual(mock_discover_collections.call_count, 0)
        self.dag.update_providers_config(
            """
            earth_search:
                search:
                    discover_collections:
                        fetch_url: 'http://new-endpoint'
            """
        )
        self.dag.fetch_collections_list()
        mock_discover_collections.assert_called_once_with(
            self.dag, provider="earth_search"
        )

        # add new provider conf and check that discover_collections() is launched for it
        self.assertEqual(mock_discover_collections.call_count, 1)
        self.dag.update_providers_config(
            """
            foo_provider:
                search:
                    type: StacSearch
                    api_endpoint: https://foo.bar/search
                products:
                    GENERIC_COLLECTION:
                        _collection: '{collection}'
            """
        )
        self.dag.fetch_collections_list()
        mock_discover_collections.assert_called_with(self.dag, provider="foo_provider")
        # discover_collections() should have been called 2 more times
        # (once per dynamically configured provider)
        self.assertEqual(mock_discover_collections.call_count, 3)

        # now check that if provider is specified, only this one is fetched
        mock_discover_collections.reset_mock()
        self.dag.fetch_collections_list(provider="foo_provider")
        mock_discover_collections.assert_called_once_with(
            self.dag, provider="foo_provider"
        )

    @mock.patch("eodag.api.core.get_ext_collections_conf", autospec=True)
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.discover_collections", autospec=True
    )
    def test_fetch_collections_list_without_ext_conf(
        self, mock_discover_collections, mock_get_ext_collections_conf
    ):
        """Core api must not fetch collections list and must discover collections without ext-conf"""
        # check that no provider has already been fetched
        for provider in self.dag._providers.values():
            self.assertFalse(provider.collections_fetched)

        # check that without an ext-conf, discover_collections() is launched for it
        mock_get_ext_collections_conf.return_value = {}
        self.dag.fetch_collections_list()
        self.assertEqual(mock_discover_collections.call_count, 1)

        # check that without an ext-conf, no provider has been fetched
        for provider in self.dag._providers.values():
            self.assertFalse(provider.collections_fetched)

    @mock.patch("eodag.api.core.get_ext_collections_conf", autospec=True)
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.discover_collections", autospec=True
    )
    def test_fetch_collections_list_updated_system_conf(
        self, mock_discover_collections, mock_get_ext_collections_conf
    ):
        """fetch_collections_list must launch collections discovery for new system-wide providers"""
        # add a new system-wide provider not listed in ext-conf
        new_default_conf = load_default_config()
        new_default_conf["new_provider"] = new_default_conf["earth_search"].with_name(
            "new_provider"
        )

        with mock.patch(
            "eodag.api.core.load_default_config",
            return_value=new_default_conf,
            autospec=True,
        ):
            self.dag = EODataAccessGateway()

            mock_get_ext_collections_conf.return_value = {}

            # disabled collections discovery
            os.environ["EODAG_EXT_COLLECTIONS_CFG_FILE"] = ""
            self.dag.fetch_collections_list()
            mock_discover_collections.assert_not_called()
            os.environ.pop("EODAG_EXT_COLLECTIONS_CFG_FILE")

            # add an empty ext-conf for other providers to prevent them to be fetched
            for provider in self.dag._providers.values():
                if provider != "new_provider" and provider.fetchable:
                    mock_get_ext_collections_conf.return_value[provider] = {}

            self.dag.fetch_collections_list()
            mock_discover_collections.assert_called_once_with(
                self.dag, provider="new_provider"
            )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.discover_collections", autospec=True
    )
    def test_fetch_collections_list_disabled(self, mock_discover_collections):
        """fetch_collections_list must not launch collections discovery if disabled"""

        # disable collections discovery
        os.environ["EODAG_EXT_COLLECTIONS_CFG_FILE"] = ""

        # default settings
        self.dag.fetch_collections_list()
        mock_discover_collections.assert_not_called()

        # only user-defined providers must be fetched
        self.dag.update_providers_config(
            """
            earth_search:
                search:
                    discover_collections:
                        fetch_url: 'http://new-endpoint'
            foo_provider:
                search:
                    type: StacSearch
                    api_endpoint: https://foo.bar/search
                products:
                    GENERIC_COLLECTION:
                        _collection: '{collection}'
            """
        )
        self.dag.fetch_collections_list()
        self.assertEqual(mock_discover_collections.call_count, 2)

    def test_core_object_set_default_locations_config(self):
        """The core object must set the default locations config on instantiation"""
        default_shpfile = os.path.join(
            self.conf_dir, "shp", "ne_110m_admin_0_map_units.shp"
        )
        self.assertIsInstance(self.dag.locations_config, list)
        self.assertEqual(
            self.dag.locations_config,
            [dict(attr="ADM0_A3_US", name="country", path=default_shpfile)],
        )

    def test_core_object_locations_file_not_found(self):
        """The core object must set the locations to an empty list when the file is not found"""
        dag = EODataAccessGateway(locations_conf_path="no_locations.yml")
        self.assertEqual(dag.locations_config, [])

    def test_prune_providers_list(self):
        """Providers needing auth for search but without credentials must be pruned on init"""
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
        )
        try:
            # Default conf: no auth needed for search
            dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
            assert not getattr(dag._providers["sara"].search_config, "need_auth", False)

            # auth needed for search without credentials
            os.environ["EODAG__SARA__SEARCH__NEED_AUTH"] = "true"
            dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
            assert "sara" not in dag.providers.names

            # auth needed for search with credentials
            os.environ["EODAG__SARA__SEARCH__NEED_AUTH"] = "true"
            os.environ["EODAG__SARA__AUTH__CREDENTIALS__USERNAME"] = "foo"
            dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
            assert "sara" in dag.providers.names
            assert getattr(dag._providers["sara"].search_config, "need_auth", False)

        # Teardown
        finally:
            os.environ.pop("EODAG__SARA__SEARCH__NEED_AUTH", None)
            os.environ.pop("EODAG__SARA__AUTH__CREDENTIALS__USERNAME", None)

    @mock.patch("eodag.plugins.manager.importlib_metadata.entry_points", autospec=True)
    def test_prune_providers_list_skipped_plugin(self, mock_iter_ep):
        """Providers needing skipped plugin must be pruned on init"""
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
        )

        def skip_qssearch(group):
            ep = mock.MagicMock()
            if group == "eodag.plugins.search":
                ep.name = "QueryStringSearch"
                ep.load = mock.MagicMock(side_effect=ModuleNotFoundError())
            return [ep]

        mock_iter_ep.side_effect = skip_qssearch

        dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
        self.assertNotIn("sara", dag.providers.names)
        self.assertEqual(dag._plugins_manager.skipped_plugins, ["QueryStringSearch"])
        dag._plugins_manager.skipped_plugins = []

    def test_prune_providers_list_for_search_without_auth(self):
        """Providers needing auth for search but without auth plugin must be pruned on init"""
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
        )
        try:
            # auth needed for search with need_auth but without auth plugin
            os.environ["EODAG__SARA__SEARCH__NEED_AUTH"] = "true"
            os.environ["EODAG__SARA__AUTH__CREDENTIALS__USERNAME"] = "foo"
            dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
            delattr(dag._providers["sara"].config, "auth")
            assert "sara" in dag.providers.names
            assert getattr(dag._providers["sara"].search_config, "need_auth", False)
            assert not hasattr(dag._providers["sara"].config, "auth")

            with self.assertLogs(level="INFO") as cm:
                dag._prune_providers_list()
                self.assertNotIn("sara", dag._providers)
                self.assertIn(
                    "sara: provider needing auth for search has been pruned because no auth plugin could be found",
                    str(cm.output),
                )

        # Teardown
        finally:
            os.environ.pop("EODAG__SARA__SEARCH__NEED_AUTH", None)
            os.environ.pop("EODAG__SARA__AUTH__CREDENTIALS__USERNAME", None)

    def test_prune_providers_list_without_api_or_search_plugin(self):
        """Providers without api or search plugin must be pruned on init"""
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
        )
        dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
        delattr(dag._providers["sara"].config, "search")
        assert "sara" in dag.providers.names
        assert not hasattr(dag._providers["sara"].config, "api")
        assert not hasattr(dag._providers["sara"].config, "search")

        assert "sara" in dag.providers.names

        with self.assertLogs(level="INFO") as cm:
            dag._prune_providers_list()
            self.assertNotIn("sara", dag._providers)
            self.assertIn(
                "sara: provider has been pruned because no api or search plugin could be found",
                str(cm.output),
            )

    def test_get_version(self):
        """Test if the version we get is the current one"""
        version_str = self.dag.get_version()
        self.assertEqual(eodag_version, version_str)

    def test_set_preferred_provider(self):
        """set_preferred_provider must set the preferred provider with increasing priority"""

        self.assertEqual(self.dag.get_preferred_provider(), ("usgs", 0))

        self.assertRaises(
            UnsupportedProvider, self.dag.set_preferred_provider, "unknown"
        )

        self.dag.set_preferred_provider("creodias")
        self.assertEqual(self.dag.get_preferred_provider(), ("creodias", 1))

        self.dag.set_preferred_provider("cop_dataspace")
        self.assertEqual(self.dag.get_preferred_provider(), ("cop_dataspace", 2))

        self.dag.set_preferred_provider("creodias")
        self.assertEqual(self.dag.get_preferred_provider(), ("creodias", 3))

        # check that the providers are correctly ordered by priority and name in "providers" property
        self.assertListEqual(["usgs", "aws_eos"], list(self.dag._providers.keys())[:2])
        self.assertListEqual(
            ["creodias", "cop_dataspace"], list(self.dag.providers.keys())[:2]
        )

    def test_update_providers_config(self):
        """update_providers_config must update providers configuration"""

        new_config = """
            my_new_provider:
                search:
                    type: StacSearch
                    api_endpoint: https://api.my_new_provider/search
                products:
                    GENERIC_COLLECTION:
                        _collection: '{collection}'
            """
        # add new provider
        self.dag.update_providers_config(new_config)
        self.assertIsInstance(
            self.dag._providers["my_new_provider"].config, ProviderConfig
        )

        self.assertEqual(self.dag._providers["my_new_provider"].config.priority, 0)

        # run a 2nd time: check that it does not raise an error
        self.dag.update_providers_config(new_config)

    @mock.patch(
        "eodag.utils.requests.requests.sessions.Session.get",
        autospec=True,
        side_effect=RequestException,
    )
    @mock.patch(
        "eodag.plugins.manager.PluginManager.get_auth_plugin",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.discover_queryables",
        autospec=True,
        return_value={},
    )
    def test_list_queryables(
        self,
        mock_stacsearch_discover_queryables: mock.Mock,
        mock_fetch_collections_list: mock.Mock,
        mock_auth_plugin: mock.Mock,
        mock_requests_get: mock.Mock,
    ) -> None:
        """list_queryables must return queryables list adapted to provider and collection"""

        with self.assertRaises(UnsupportedProvider):
            self.dag.list_queryables(provider="not_supported_provider")

        with self.assertRaises(RequestError):
            self.dag.list_queryables(collection="not_supported_collection")

        # No provider & no collection
        queryables_none_none = self.dag.list_queryables()
        expected_result = model_fields_to_annotated(CommonQueryables.model_fields)
        self.assertEqual(len(queryables_none_none), len(expected_result))
        for key, queryable in queryables_none_none.items():
            # compare obj.__repr__
            self.assertEqual(str(expected_result[key]), str(queryable))
        self.assertTrue(queryables_none_none.additional_properties)

        # Only provider
        # when only a provider is specified, return the union of the queryables for all collections
        queryables_cop_dataspace_none = self.dag.list_queryables(
            provider="cop_dataspace"
        )
        queryables_fields = Queryables.from_stac_models().model_fields
        expected_longer_result = model_fields_to_annotated(queryables_fields)
        self.assertGreater(
            len(queryables_cop_dataspace_none), len(queryables_none_none)
        )
        self.assertLess(len(queryables_cop_dataspace_none), len(expected_longer_result))
        for key, queryable in queryables_cop_dataspace_none.items():
            # compare obj.__repr__
            self.assertEqual(str(expected_longer_result[key]), str(queryable))
        self.assertTrue(queryables_cop_dataspace_none.additional_properties)

        # provider & collection
        queryables_cop_dataspace_s1grd = self.dag.list_queryables(
            provider="cop_dataspace", collection="S1_SAR_GRD"
        )
        self.assertGreater(
            len(queryables_cop_dataspace_s1grd), len(queryables_none_none)
        )
        self.assertLess(
            len(queryables_cop_dataspace_s1grd), len(expected_longer_result)
        )
        for key, queryable in queryables_cop_dataspace_s1grd.items():
            if key == "collection":
                self.assertEqual("S1_SAR_GRD", queryable.__metadata__[0].get_default())
            else:
                # compare obj.__repr__
                self.assertEqual(str(expected_longer_result[key]), str(queryable))
        self.assertTrue(queryables_cop_dataspace_s1grd.additional_properties)

        # provider & collection alias
        # result should be the same if alias is used
        products = self.dag.collections_config
        # add an alias to the collection
        products.update(
            {
                "S1_SAR_GRD": Collection.create_with_dag(
                    self.dag,
                    alias="S1_SG",
                    **products["S1_SAR_GRD"].model_dump(exclude={"alias"}),
                )
            }
        )
        queryables_cop_dataspace_s1grd_alias = self.dag.list_queryables(
            provider="cop_dataspace", collection="S1_SG"
        )
        self.assertEqual(
            len(queryables_cop_dataspace_s1grd),
            len(queryables_cop_dataspace_s1grd_alias),
        )
        self.assertEqual(
            "S1_SG",
            queryables_cop_dataspace_s1grd_alias["collection"]
            .__metadata__[0]
            .get_default(),
        )
        # restore the original collection instance in the config
        products.update(
            {
                "S1_SAR_GRD": Collection.create_with_dag(
                    self.dag,
                    id="S1_SAR_GRD",
                    **products["S1_SAR_GRD"].model_dump(exclude={"id", "alias"}),
                )
            }
        )

        # Only collection
        # when a collection is specified but not the provider, the union of the queryables of all providers
        # having the collection in its config is returned
        queryables_none_s1grd = self.dag.list_queryables(collection="S1_SAR_GRD")
        self.assertGreaterEqual(len(queryables_none_s1grd), len(queryables_none_none))
        self.assertGreaterEqual(
            len(queryables_none_s1grd), len(queryables_cop_dataspace_none)
        )
        self.assertGreaterEqual(
            len(queryables_none_s1grd), len(queryables_cop_dataspace_s1grd)
        )
        self.assertLess(len(queryables_none_s1grd), len(expected_longer_result))
        for key, queryable in queryables_cop_dataspace_s1grd.items():
            if key == "collection":
                self.assertEqual("S1_SAR_GRD", queryable.__metadata__[0].get_default())
            else:
                # compare obj.__repr__
                self.assertEqual(str(expected_longer_result[key]), str(queryable))
            # queryables for provider cop_dataspace are in queryables for all providers
            self.assertEqual(str(queryable), str(queryables_none_s1grd[key]))
        self.assertTrue(queryables_none_s1grd.additional_properties)

        # model_validate should validate input parameters using the queryables result
        queryables_validated = (
            queryables_cop_dataspace_s1grd.get_model().model_validate(
                {"collection": "S1_SAR_GRD", "gsd": 10}
            )
        )
        self.assertIn("gsd", queryables_validated.__dict__)
        with self.assertRaises(PydanticValidationError):
            queryables_cop_dataspace_s1grd.get_model().model_validate(
                {"collection": "S1_SAR_GRD", "gsd": -1}
            )

    @mock.patch(
        "eodag.plugins.search.base.Search.list_queryables",
        autospec=True,
    )
    def test_alias_in_list_queryables(self, mock_list_queryables: mock.Mock):
        """queryables alias must be resolved in list_queryables"""
        self.dag.list_queryables(
            provider="cop_dataspace",
            collection="S2_MSI_L1C",
            start="2025-01-01",
            end="2025-01-31",
            geom=[-10, 35, 10, 45],
        )
        search_plugin = next(
            self.dag._plugins_manager.get_search_plugins(provider="cop_dataspace")
        )
        mock_list_queryables.assert_called_with(
            search_plugin,
            dict(
                collection="S2_MSI_L1C",
                start_datetime="2025-01-01",
                end_datetime="2025-01-31",
                geometry=[-10, 35, 10, 45],
            ),
            [
                col.id
                for col in self.dag.list_collections(
                    "cop_dataspace", fetch_providers=False
                )
            ],
            {
                "S2_MSI_L1C": {
                    **self.dag.collections_config["S2_MSI_L1C"].model_dump(
                        mode="json", exclude={"id"}
                    ),
                    "collection": "S2_MSI_L1C",
                }
            },
            "S2_MSI_L1C",
            "S2_MSI_L1C",
        )

    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch.discover_queryables",
        autospec=True,
    )
    def test_additional_properties_in_list_queryables(
        self, mock_discover_queryables: mock.Mock
    ):
        """additional_properties in queryables must be adapted to provider's configuration"""
        # Check if discover_metadata.auto_discovery is False
        self.assertFalse(
            self.dag._providers["cop_marine"].search_config.discover_metadata[
                "auto_discovery"
            ]
        )
        cop_marine_queryables = self.dag.list_queryables(provider="cop_marine")
        self.assertFalse(cop_marine_queryables.additional_properties)

        item_cop_marine_queryables = self.dag.list_queryables(
            collection="MO_INSITU_GLO_PHY_TS_OA_NRT_013_002", provider="cop_marine"
        )
        self.assertFalse(item_cop_marine_queryables.additional_properties)

        # Check if discover_metadata.auto_discovery is True
        self.assertTrue(
            self.dag._providers["sara"].search_config.discover_metadata[
                "auto_discovery"
            ]
        )
        sara_queryables = self.dag.list_queryables(provider="sara")
        self.assertTrue(sara_queryables.additional_properties)

        item_sara_queryables = self.dag.list_queryables(
            collection="S2_MSI_L1C", provider="sara"
        )
        self.assertTrue(item_sara_queryables.additional_properties)

        # additional_properties set to False for EcmwfSearch plugin
        cop_cds_queryables = self.dag.list_queryables(provider="cop_cds")
        self.assertFalse(cop_cds_queryables.additional_properties)

    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch.discover_queryables",
        autospec=True,
    )
    def test_list_queryables_with_constraints(
        self, mock_discover_queryables: mock.Mock
    ):
        plugin = next(
            self.dag._plugins_manager.get_search_plugins(
                provider="cop_cds", collection="ERA5_SL"
            )
        )
        # default values should be added to params
        self.dag.list_queryables(provider="cop_cds", collection="ERA5_SL")
        defaults = {
            "collection": "ERA5_SL",
            "dataset": "reanalysis-era5-single-levels",
        }
        mock_discover_queryables.assert_called_once_with(plugin, **defaults)
        mock_discover_queryables.reset_mock()
        # default values + additional param
        res = self.dag.list_queryables(
            provider="cop_cds", **{"collection": "ERA5_SL", "month": "02"}
        )
        params = {
            "collection": "ERA5_SL",
            "dataset": "reanalysis-era5-single-levels",
            "month": "02",
        }
        mock_discover_queryables.assert_called_once_with(plugin, **params)
        self.assertFalse(res.additional_properties)
        mock_discover_queryables.reset_mock()

        # unset default values
        self.dag.list_queryables(
            provider="cop_cds", **{"collection": "ERA5_SL", "data_format": ""}
        )
        defaults = {
            "collection": "ERA5_SL",
            "dataset": "reanalysis-era5-single-levels",
            "data_format": "",
        }
        mock_discover_queryables.assert_called_once_with(plugin, **defaults)

    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.list_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch.list_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.build_search_result.WekeoECMWFSearch.list_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.manager.PluginManager.get_auth_plugin",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    def test_list_queryables_priority_sorted(
        self,
        mock_fetch_collections_list: mock.Mock,
        get_auth_plugin: mock.Mock,
        mock_wekeo_list_queryables: mock.Mock,
        mock_ecmwf_list_queryables: mock.Mock,
        mock_dedl_list_queryables: mock.Mock,
    ):
        mock_wekeo_list_queryables.return_value = QueryablesDict(
            additional_properties=False,
            additional_information="Mocked WEkEO queryables",
            property1="value_from_wekeo",
        )

        mock_ecmwf_list_queryables.return_value = QueryablesDict(
            additional_properties=False,
            additional_information="Mocked ECMWF queryables for cop_cds",
            property1="value_cds1",
            property2="value_cds2",
        )

        mock_dedl_list_queryables.return_value = QueryablesDict(
            additional_properties=False,
            additional_information="Mocked STAC queryables for dedl",
            property1="value_dedl1",
            property2="value_dedl2",
            property3="value_dedl3",
        )

        self.dag.set_preferred_provider("wekeo_ecmwf")

        queryables = self.dag.list_queryables(collection="ERA5_SL")

        self.assertEqual(queryables["property1"], "value_from_wekeo")
        self.assertEqual(queryables["property2"], "value_cds2")
        self.assertEqual(queryables["property3"], "value_dedl3")

        self.dag.set_preferred_provider("cop_cds")

        queryables = self.dag.list_queryables(collection="ERA5_SL")

        self.assertEqual(queryables["property1"], "value_cds1")
        self.assertEqual(queryables["property2"], "value_cds2")
        self.assertEqual(queryables["property3"], "value_dedl3")

        self.dag.set_preferred_provider("dedl")

        queryables = self.dag.list_queryables(collection="ERA5_SL")

        self.assertEqual(queryables["property1"], "value_dedl1")
        self.assertEqual(queryables["property2"], "value_dedl2")
        self.assertEqual(queryables["property3"], "value_dedl3")

    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.list_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch.list_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.build_search_result.WekeoECMWFSearch.list_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.manager.PluginManager.get_auth_plugin",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_collections_list", autospec=True
    )
    def test_list_queryables_additional(
        self,
        mock_fetch_collections_list: mock.Mock,
        get_auth_plugin: mock.Mock,
        mock_wekeo_list_queryables: mock.Mock,
        mock_ecmwf_list_queryables: mock.Mock,
        mock_dedl_list_queryables: mock.Mock,
    ):
        mock_wekeo_list_queryables.return_value = QueryablesDict(
            additional_properties=False,
            additional_information="Mocked WEkEO queryables",
        )

        mock_ecmwf_list_queryables.return_value = QueryablesDict(
            additional_properties=False,
            additional_information="Mocked ECMWF queryables for cop_cds",
        )

        mock_dedl_list_queryables.return_value = QueryablesDict(
            additional_properties=False,
            additional_information="Mocked STAC queryables for dedl",
        )

        queryables = self.dag.list_queryables(collection="ERA5_SL")

        self.assertEqual(
            queryables.additional_information,
            (
                "cop_cds: Mocked ECMWF queryables for cop_cds"
                " | wekeo_ecmwf: Mocked WEkEO queryables"
                " | dedl: Mocked STAC queryables for dedl"
            ),
        )
        self.assertEqual(queryables.additional_properties, False)

        mock_dedl_list_queryables.return_value = QueryablesDict(
            additional_properties=True,
            additional_information="Mocked STAC queryables for dedl",
        )
        queryables = self.dag.list_queryables(collection="ERA5_SL")

        self.assertEqual(queryables.additional_properties, True)

    @mock.patch(
        "eodag.plugins.manager.PluginManager.get_auth_plugin",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch._fetch_data",
        autospec=True,
    )
    def test_list_queryables_dynamic_discover_queryables(
        self,
        mock__fetch_data: mock.Mock,
        mock_auth_plugin: mock.Mock,
    ):
        """ECMWFSearch must dynamically get the discover queryables configuration"""
        provider = "wekeo_ecmwf"
        # get the original cop_* provider for each wekeo_ecmwf product
        original_cop_providers = {
            pt: next(p for p in providers if p.startswith("cop_"))
            for pt, providers in SUPPORTED_COLLECTIONS.items()
            if provider in providers
        }
        copernicus_urls = {
            "cop_ads": "ads.atmosphere.copernicus.eu",
            "cop_cds": "cds.climate.copernicus.eu",
            "cop_ewds": "ewds.climate.copernicus.eu",
        }
        for product, original_provider in original_cop_providers.items():
            self.dag.list_queryables(provider=provider, collection=product)
            self.assertEqual(mock__fetch_data.call_count, 2)
            constraints_url = mock__fetch_data.call_args_list[0][0][1]
            form_url = mock__fetch_data.call_args_list[1][0][1]
            # check if URLs in queryables_config are the copernicus ones
            original_url = copernicus_urls[original_provider]
            self.assertIn(original_url, constraints_url)
            self.assertIn(original_url, form_url)
            mock__fetch_data.reset_mock()

    def test_queryables_repr(self):
        """The HTML representation of queryables must be correct"""
        queryables = self.dag.list_queryables(
            provider="cop_dataspace", collection="S1_SAR_GRD"
        )
        self.assertIsInstance(queryables, QueryablesDict)
        queryables_repr = html.fromstring(queryables._repr_html_())
        self.assertIn("QueryablesDict", queryables_repr.xpath("//thead/tr/td")[0].text)
        spans = queryables_repr.xpath("//tbody/tr/td/details/summary/span")
        id_present = False
        for i, span in enumerate(spans):
            if "'id'" in span.text:
                id_present = True
                self.assertIn("str", spans[i + 1].text)
                break
        self.assertTrue(id_present)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.oidcauthorizationcodeflowauth.requests.sessions.Session.request",
        autospec=True,
    )
    def test_available_sortables(self, mock_auth_session_request):
        """available_sortables must return available sortable(s) and its (their)
        maximum number dict for providers which support the sorting feature"""
        self.maxDiff = None
        expected_result = {
            "aws_eos": None,
            "cop_ads": None,
            "cop_cds": None,
            "cop_dataspace": {
                "sortables": [
                    "start_datetime",
                    "end_datetime",
                    "published",
                    "updated",
                ],
                "max_sort_params": 1,
            },
            "cop_dataspace_s3": {
                "sortables": [
                    "start_datetime",
                    "end_datetime",
                    "published",
                    "updated",
                ],
                "max_sort_params": 1,
            },
            "cop_ewds": None,
            "cop_ghsl": None,
            "creodias": {
                "sortables": [
                    "start_datetime",
                    "end_datetime",
                    "published",
                    "updated",
                ],
                "max_sort_params": 1,
            },
            "creodias_s3": {
                "sortables": [
                    "start_datetime",
                    "end_datetime",
                    "published",
                    "updated",
                ],
                "max_sort_params": 1,
            },
            "dedl": {
                "max_sort_params": None,
                "sortables": [
                    "id",
                    "start_datetime",
                    "created",
                    "updated",
                    "platform",
                    "gsd",
                    "eo:cloud_cover",
                ],
            },
            "dedt_lumi": None,
            "dedt_mn5": None,
            "earth_search": {
                "sortables": [
                    "id",
                    "start_datetime",
                    "created",
                    "updated",
                    "platform",
                    "gsd",
                    "eo:cloud_cover",
                ],
                "max_sort_params": None,
            },
            "earth_search_gcs": {
                "sortables": [
                    "id",
                    "start_datetime",
                    "created",
                    "updated",
                    "platform",
                    "gsd",
                    "eo:cloud_cover",
                ],
                "max_sort_params": None,
            },
            "ecmwf": None,
            "eocat": {"max_sort_params": None, "sortables": []},
            "eumetsat_ds": {
                "sortables": [
                    "start_datetime",
                    "published",
                ],
                "max_sort_params": 1,
            },
            "cop_marine": None,
            "fedeo_ceda": {"max_sort_params": None, "sortables": []},
            "geodes": {
                "max_sort_params": None,
                "sortables": [
                    "id",
                    "start_datetime",
                    "end_datetime",
                    "platform",
                    "eo:cloud_cover",
                ],
            },
            "geodes_s3": {
                "max_sort_params": None,
                "sortables": [
                    "id",
                    "start_datetime",
                    "end_datetime",
                    "platform",
                    "eo:cloud_cover",
                ],
            },
            "hydroweb_next": {
                "sortables": [
                    "id",
                    "start_datetime",
                    "end_datetime",
                    "version",
                    "processing:level",
                ],
                "max_sort_params": None,
            },
            "meteoblue": None,
            "planetary_computer": {
                "sortables": [
                    "id",
                    "start_datetime",
                    "platform",
                ],
                "max_sort_params": None,
            },
            "sara": {
                "sortables": [
                    "start_datetime",
                    "end_datetime",
                    "sar:instrument_mode",
                ],
                "max_sort_params": 1,
            },
            "usgs": None,
            "usgs_satapi_aws": {"max_sort_params": None, "sortables": []},
            "wekeo_cmems": None,
            "wekeo_ecmwf": None,
            "wekeo_main": None,
        }
        sortables = self.dag.available_sortables()
        self.assertListEqual(
            sorted(list(sortables.keys())), sorted(list(expected_result.keys()))
        )
        for provider, sortable in sortables.items():
            if sortable is None:
                self.assertIsNone(expected_result[provider])
            else:
                self.assertDictEqual(
                    sortable,
                    expected_result[provider],
                    f"Expected sortables differ for provider {provider}",
                )

        # check if sortables are set to None when the provider does not support the sorting feature
        self.assertFalse(hasattr(self.dag._providers["aws_eos"].search_config, "sort"))
        self.assertIsNone(sortables["aws_eos"])

        # check if sortable parameter(s) and its (their) maximum number of a provider are set
        # to their value when the provider supports the sorting feature and has a maximum number of sortables
        self.assertTrue(hasattr(self.dag._providers["creodias"].search_config, "sort"))
        self.assertTrue(
            self.dag._providers["creodias"].search_config.sort.get("max_sort_params")
        )
        if sortables["creodias"]:
            self.assertIsNotNone(sortables["creodias"]["max_sort_params"])

        # check if sortable parameter(s) of a provider is set to its value and its (their) maximum number is set
        # to None when the provider supports the sorting feature and does not have a maximum number of sortables
        self.assertTrue(
            hasattr(self.dag._providers["planetary_computer"].search_config, "sort")
        )
        self.assertFalse(
            self.dag._providers["planetary_computer"].search_config.sort.get(
                "max_sort_params"
            )
        )
        if sortables["planetary_computer"]:
            self.assertIsNone(sortables["planetary_computer"]["max_sort_params"])

    @mock.patch(
        "eodag.plugins.manager.PluginManager.get_auth_plugin",
        autospec=True,
    )
    @mock.patch("eodag.plugins.search.base.Search.validate", autospec=True)
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.query",
        autospec=True,
        return_value=([], 0),
    )
    def test_search_validate(
        self,
        mock_query: mock.Mock,
        mock_validate: mock.Mock,
        mock_auth_plugin: mock.Mock,
    ) -> None:
        """Search filter must be validated if requested"""
        filter = {
            "provider": "cop_dataspace",
            "collection": "S1_SAR_GRD",
            "lorem": "ipsum",
        }
        # Validation by default
        self.dag.search(**filter)
        mock_validate.assert_called_once()
        args, kwargs = mock_validate.call_args
        # Some other default keyword may be added to the kwargs (e.g. geometry)
        self.assertEqual("S1_SAR_GRD", args[1].get("collection"))
        self.assertEqual("ipsum", args[1].get("lorem"))
        mock_validate.reset_mock()

        self.dag.search(validate=True, **filter)
        mock_validate.assert_called_once()
        mock_validate.reset_mock()

        # Don't validate request
        self.dag.search(validate=False, **filter)
        mock_validate.assert_not_called()
        mock_validate.reset_mock()

    @mock.patch(
        "eodag.plugins.manager.PluginManager.get_auth_plugin",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.query",
        autospec=True,
        return_value=SearchResult([]),
    )
    def test_search_validate_invalid_filter(
        self,
        mock_query: mock.Mock,
        mock_auth_plugin: mock.Mock,
    ) -> None:
        """Search must fail if validation is enabled and the filter is not valid"""
        filter = {
            "provider": "cop_dataspace",
            "collection": "S1_SAR_GRD",
            "sat:absolute_orbit": "dolorem",
        }
        # Validation by default: fails cause orbitNumber
        with self.assertRaises(ValidationError):
            self.dag.search(raise_errors=True, **filter)

        with self.assertRaises(ValidationError):
            self.dag.search(validate=True, raise_errors=True, **filter)

        # No validation, no exception
        self.dag.search(validate=False, raise_errors=True, **filter)
