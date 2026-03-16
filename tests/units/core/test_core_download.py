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

from eodag import EODataAccessGateway
from eodag.api.product import EOProduct
from eodag.api.search_result import SearchResult
from tests.units.core.base import TestCoreBase


class TestCoreDownload(TestCoreBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dag = EODataAccessGateway()

    def test_download_all(self):
        """download_all must create its own ThreadPoolExecutor if no executor is provided"""

        download_plugin = self.dag._plugins_manager.get_download_plugin("cop_dataspace")

        def download_all(
            search_result,
            downloaded_callback,
            progress_callback,
            wait,
            timeout,
            **kwargs,
        ) -> list[str]:
            return ["localpath1", "localpath2"]

        download_plugin.download_all = download_all

        search_result = SearchResult(
            [
                EOProduct(
                    "cop_dataspace",
                    dict(
                        geometry="POINT (0 0)",
                        id="dummy_product_a",
                        title="dummy_product_a",
                    ),
                ),
                EOProduct(
                    "cop_dataspace",
                    dict(
                        geometry="POINT (0 0)",
                        id="dummy_product_b",
                        title="dummy_product_b",
                    ),
                ),
            ]
        )
        results = self.dag.download_all(search_result, wait=-1, timeout=-1)
        self.assertEqual(results, ["localpath1", "localpath2"])
