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
from unittest import mock

from eodag import EODataAccessGateway
from eodag.api.collection import Collection
from tests.units.core.base import TestCoreBase


class TestCoreProviderGroup(TestCoreBase):
    # create a group with a provider which has collection discovery mechanism
    # and the other one which has not it to test different cases
    dag: EODataAccessGateway
    group = ("creodias", "earth_search")
    group_name = "testgroup"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.dag = EODataAccessGateway()
        providers_configs = cls.dag._providers.configs
        for name in cls.group:
            if name in providers_configs:
                setattr(providers_configs[name], "group", cls.group_name)

    def test_available_providers_by_group(self) -> None:
        """
        The method available_providers returns only one entry for both grouped providers
        """
        providers = self.dag.providers.names

        # check that setting "by_group" argument to True removes names of grouped providers and add names of their group
        groups = []
        for provider in self.dag._providers.values():
            provider_group = getattr(provider.config, "group", None)
            if provider_group and provider_group not in groups:
                groups.append(provider_group)
                providers.append(provider_group)
            if provider_group:
                providers.remove(provider)  # type: ignore

        self.assertCountEqual(self.dag.providers.groups, providers)

    def test_list_collections(self) -> None:
        """
        List the collections for the provider group.
        EODAG return the merged list of collections from both providers of the group.
        """

        search_products: list = []
        for provider in self.group:
            search_products.extend(
                self.dag.list_collections(provider, fetch_providers=False)
            )

        merged_list = list({d.id: d for d in search_products}.values())

        self.assertCountEqual(
            self.dag.list_collections(self.group_name, fetch_providers=False),
            merged_list,
        )

    @mock.patch("eodag.api.core.get_ext_collections_conf", autospec=True)
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.discover_collections", autospec=True
    )
    def test_fetch_collections_list_grouped_providers(
        self, mock_discover_collections, mock_get_ext_collections_conf
    ):
        """Core api must fetch collections list and update if needed"""
        # store providers
        tmp_providers = copy.deepcopy(self.dag._providers)

        # check that no provider has already been fetched
        for provider in self.dag._providers.values():
            self.assertFalse(provider.collections_fetched)

        mock_get_ext_collections_conf.return_value = {
            provider: {
                "providers_config": {"foo": {"_collection": "foo"}},
                "collections_config": {"foo": {"title": "Foo collection"}},
            }
            for provider in self.group
        }

        for provider in self.dag._providers.values():
            # add an empty ext-conf for other providers to prevent them to be fetched
            if provider not in self.group and provider.fetchable:
                mock_get_ext_collections_conf.return_value[provider] = {}

            # update grouped providers conf and check that discover_collections() is launched for them
            if provider in self.group and provider.fetchable:
                provider_search_config_key = (
                    "search" if hasattr(provider.config, "search") else "api"
                )
                self.dag.update_providers_config(
                    f"""
                    {provider}:
                        {provider_search_config_key}:
                            discover_collections:
                                fetch_url: 'http://new-{provider}-endpoint'
                            """
                )

        self.dag.fetch_collections_list(provider=self.group_name)

        # discover_collections() should have been called one time per each provider of the group
        # which has collection discovery mechanism. dag configuration of these providers should have been updated
        for name in self.group:
            if self.dag._providers[name].fetchable:
                self.assertTrue(self.dag._providers[name].collections_fetched)
                self.assertEqual(
                    self.dag._providers[name].collections_config["foo"],
                    {"_collection": "foo"},
                )
                mock_discover_collections.assert_called_with(self.dag, provider=name)
            else:
                self.assertFalse(self.dag._providers[name].collections_fetched)
                self.assertNotIn(
                    "foo", list(self.dag._providers[name].collections_config.keys())
                )

        self.assertEqual(
            self.dag.collections_config.data["foo"],
            Collection.create_with_dag(self.dag, id="foo", title="Foo collection"),
        )

        # restore providers config
        self.dag._providers = tmp_providers

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.discover_collections",
        autospec=True,
        return_value={
            "providers_config": {"foo": {"collection": "foo"}},
            "collections_config": {"foo": {"title": "Foo collection"}},
        },
    )
    def test_discover_collections_grouped_providers(
        self, mock_plugin_discover_collections
    ):
        """Core api must fetch grouped providers for collections"""
        ext_collections_conf = self.dag.discover_collections(provider=self.group_name)

        self.assertIsNotNone(ext_collections_conf)

        # discover_collections() of providers search plugin should have been called one time per each provider
        # of the group which has collection discovery mechanism. Only config of these providers should have been
        # added in the external config
        mock_call_args_list = [
            mock_plugin_discover_collections.call_args_list[i].args[0]
            for i in range(len(mock_plugin_discover_collections.call_args_list))
        ]
        for provider in self.group:
            provider_search_plugin = next(
                self.dag._plugins_manager.get_search_plugins(provider=provider)
            )
            if self.dag._providers[provider].fetchable:
                self.assertIn(provider_search_plugin, mock_call_args_list)
                self.assertEqual(
                    ext_collections_conf[provider]["providers_config"]["foo"][
                        "collection"
                    ],
                    "foo",
                )
                self.assertEqual(
                    ext_collections_conf[provider]["collections_config"]["foo"][
                        "title"
                    ],
                    "Foo collection",
                )
            else:
                self.assertNotIn(provider_search_plugin, mock_call_args_list)
                self.assertNotIn(provider, list(ext_collections_conf.keys()))

    def test_get_search_plugins(
        self,
    ) -> None:
        """
        The method _plugins_manager.get_search_plugins is called with provider group
        It returns a list containing the 2 grouped plugins
        """
        plugin1 = list(
            self.dag._plugins_manager.get_search_plugins(provider=self.group[0])
        )
        plugin2 = list(
            self.dag._plugins_manager.get_search_plugins(provider=self.group[1])
        )

        group_plugins = list(
            self.dag._plugins_manager.get_search_plugins(provider=self.group_name)
        )

        self.assertCountEqual(group_plugins, [*plugin1, *plugin2])
