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
from copy import deepcopy as copy_deepcopy
from unittest import mock

from eodag.config import load_default_config
from eodag.plugins.search import PreparedSearch
from eodag.utils.exceptions import ValidationError
from tests.units.search_plugins.base import BaseSearchPluginTest


class TestSearchPluginWekeoSearch(BaseSearchPluginTest):
    def setUp(self):
        super(TestSearchPluginWekeoSearch, self).setUp()
        # One of the providers that has a WekeoSearch Search plugin
        provider = "wekeo_main"
        self.wekeomain_search_plugin = self.get_search_plugin(self.collection, provider)
        self.wekeomain_auth_plugin = self.get_auth_plugin(self.wekeomain_search_plugin)

    def test_plugins_search_wekeosearch_init_wekeomain(self):
        """Check that the WekeoSearch plugin is initialized correctly for wekeo_main provider"""

        default_config = load_default_config()["wekeo_main"]
        # "eodag:order_link" in S1_SAR_GRD but not in provider conf or S1_SAR_SLC conf
        self.assertNotIn(
            "order_link", default_config.search.assets_mapping["download_link"]
        )
        self.assertIn(
            "order_link",
            default_config.products["S1_SAR_GRD"]["assets_mapping"]["download_link"],
        )
        self.assertNotIn("assets_mapping", default_config.products["S1_SAR_SLC"])

        # metadata_mapping_from_product: from S1_SAR_GRD to S1_SAR_SLC
        self.assertEqual(
            default_config.products["S1_SAR_SLC"]["metadata_mapping_from_product"],
            "S1_SAR_GRD",
        )

        # check initialized plugin configuration
        self.assertDictEqual(
            self.wekeomain_search_plugin.config.products["S1_SAR_GRD"][
                "metadata_mapping"
            ],
            self.wekeomain_search_plugin.config.products["S1_SAR_SLC"][
                "metadata_mapping"
            ],
        )

        # S3_SRA_BS has both metadata_mapping_from_product and metadata_mapping
        # "metadata_mapping" must override "metadata_mapping_from_product"
        self.assertIn(
            "order_link",
            default_config.products["S3_EFR"]["assets_mapping"]["download_link"],
        )
        self.assertEqual(
            default_config.products["S3_SRA_BS"]["metadata_mapping_from_product"],
            "S3_EFR",
        )

        # Cumputed mapping
        assets_mapping1 = self.wekeomain_search_plugin.get_assets_mapping("S3_SRA_BS")
        assets_mapping2 = self.wekeomain_search_plugin.get_assets_mapping("S3_EFR")
        self.assertEqual(
            assets_mapping1.get("download_link", {}).get("order_link"),
            assets_mapping2.get("download_link", {}).get("order_link"),
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.build_query_string", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.PostJsonSearch.build_query_string", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.WekeoSearch._request",
        autospec=True,
    )
    def test_plugins_search_wekeosearch_search_wekeomain(
        self,
        mock__request,
        mock_build_qs_postjsonsearch,
        mock_build_qs_stacsearch,
        mock_normalize_results,
    ):
        """A query with a WekeoSearch provider (here wekeo_main) must use build_query_string() of PostJsonSearch"""  # noqa
        mock_build_qs_postjsonsearch.return_value = (
            mock_build_qs_stacsearch.return_value
        ) = (
            {
                "dataset_id": "EO:ESA:DAT:SENTINEL-2",
                "startDate": "2020-08-08",
                "completionDate": "2020-08-16",
                "bbox": [137.772897, 13.134202, 153.749135, 23.885986],
                "processing:level": "S2MSI1C",
            },
            mock.ANY,
        )

        self.wekeomain_search_plugin.query(
            prep=PreparedSearch(
                page=1,
                limit=2,
                auth_plugin=self.wekeomain_auth_plugin,
            ),
            **self.search_criteria_s2_msi_l1c,
        )

        mock__request.assert_called()
        mock_build_qs_postjsonsearch.assert_called()
        mock_build_qs_stacsearch.assert_not_called()

    def test_plugins_search_wekeosearch_search_wekeomain_ko(self):
        """A query with a parameter which is not queryable must
        raise an error if the provider does not allow it"""  # noqa
        # with raised error parameter set to True in the global config of the provider
        provider_search_plugin_config = copy_deepcopy(
            self.wekeomain_search_plugin.config
        )
        self.wekeomain_search_plugin.config.discover_metadata = {
            "raise_mtd_discovery_error": True
        }

        with self.assertRaises(ValidationError) as context:
            self.wekeomain_search_plugin.query(
                prep=PreparedSearch(
                    page=1,
                    limit=2,
                    auth_plugin=self.wekeomain_auth_plugin,
                ),
                **{**self.search_criteria_s2_msi_l1c, **{"foo": "bar"}},
            )
        self.assertEqual(
            "Search parameters which are not queryable are disallowed for this collection on this provider: "
            f"please remove 'foo' from your search parameters. Collection: "
            f"{self.search_criteria_s2_msi_l1c['collection']} / provider : {self.wekeomain_search_plugin.provider}",
            context.exception.message,
        )

        # with raised error parameter set to True in the config of the collection of the provider

        # first, update this parameter to False in the global config
        # to show that it is going to be taken over by this new config
        self.wekeomain_search_plugin.config.discover_metadata[
            "raise_mtd_discovery_error"
        ] = False

        self.wekeomain_search_plugin.config.products[
            self.search_criteria_s2_msi_l1c["collection"]
        ]["discover_metadata"] = {"raise_mtd_discovery_error": True}

        with self.assertRaises(ValidationError) as context:
            self.wekeomain_search_plugin.query(
                prep=PreparedSearch(
                    page=1,
                    limit=2,
                    auth_plugin=self.wekeomain_auth_plugin,
                ),
                **{**self.search_criteria_s2_msi_l1c, **{"foo": "bar"}},
            )
        self.assertEqual(
            "Search parameters which are not queryable are disallowed for this collection on this provider: "
            f"please remove 'foo' from your search parameters. Collection: "
            f"{self.search_criteria_s2_msi_l1c['collection']} / provider : {self.wekeomain_search_plugin.provider}",
            context.exception.message,
        )

        # restore the original config
        self.wekeomain_search_plugin.config = provider_search_plugin_config

    @mock.patch(
        "eodag.plugins.search.qssearch.PostJsonSearch.discover_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.discover_queryables", autospec=True
    )
    def test_plugins_search_postjsonsearch_discover_queryables(
        self,
        mock_stacsearch_discover_queryables,
        mock_postjsonsearch_discover_queryables,
    ):
        """Queryables discovery with a PostJsonSearchWithStacQueryables (here wekeo_main) must use discover_queryables() of StacSearch"""  # noqa
        self.wekeomain_search_plugin.discover_queryables(collection=self.collection)
        mock_stacsearch_discover_queryables.assert_called()
        mock_postjsonsearch_discover_queryables.assert_not_called()
