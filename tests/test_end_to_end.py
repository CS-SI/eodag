# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
from __future__ import unicode_literals

import glob
import multiprocessing
import os
import unittest

from tests import TEST_RESOURCES_PATH, TESTS_DOWNLOAD_PATH
from tests.context import EODataAccessGateway


class TestEODagEndToEnd(unittest.TestCase):
    """Make real case tests. This assume the existence of a user conf file in resources folder named user_conf.yml"""  # noqa

    @classmethod
    def setUpClass(cls):

        # use tests/resources/user_conf.yml if exists else default file ~/.config/eodag/eodag.yml
        tests_user_conf = os.path.join(TEST_RESOURCES_PATH, "user_conf.yml")
        if os.path.isfile(tests_user_conf):
            cls.eodag = EODataAccessGateway(
                user_conf_file_path=os.path.join(TEST_RESOURCES_PATH, "user_conf.yml")
            )
        else:
            cls.eodag = EODataAccessGateway()

        # create TESTS_DOWNLOAD_PATH is not exists
        if not os.path.exists(TESTS_DOWNLOAD_PATH):
            os.makedirs(TESTS_DOWNLOAD_PATH)

        # Ensure that we will be able to make search requests on only one provider, by
        # setting partial to False by
        # default for all the supported product types of all the providers
        for provider, conf in cls.eodag.providers_config.items():
            for product_type, pt_conf in conf.products.items():
                pt_conf["partial"] = False
            # Change download directory to TESTS_DOWNLOAD_PATH for tests
            if hasattr(conf, "download") and hasattr(conf.download, "outputs_prefix"):
                conf.download.outputs_prefix = TESTS_DOWNLOAD_PATH
            elif hasattr(conf, "api") and hasattr(conf.api, "outputs_prefix"):
                conf.api.outputs_prefix = TESTS_DOWNLOAD_PATH
            else:
                # no outputs_prefix found for provider
                pass
            # Force all providers implementing RestoSearch and defining how to retrieve
            # products by specifying the
            # location scheme to use https, enabling actual downloading of the product
            if (
                getattr(getattr(conf, "search", {}), "product_location_scheme", "https")
                == "file"
            ):
                conf.search.product_location_scheme = "https"
            # Disable extraction
            try:  # Case HTTPDownload plugin
                conf.download.extract = False
            except (KeyError, AttributeError):  # case api plugin
                conf.api.extract = False

    def setUp(self):
        self.downloaded_file_path = ""

    def tearDown(self):
        try:
            os.remove(self.downloaded_file_path)
        except OSError:
            pass

    def execute_search(self, provider, product_type, start, end, bbox):
        """Search products on provider:

        - First set the preferred provider as the one given in parameter
        - Then do the search
        - Then ensure that at least the first result originates from the provider
        - Return one product to be downloaded
        """
        search_criteria = {
            "startTimeFromAscendingNode": start,
            "completionTimeFromAscendingNode": end,
            "geometry": {
                "lonmin": bbox[0],
                "latmin": bbox[1],
                "lonmax": bbox[2],
                "latmax": bbox[3],
            },
        }
        self.eodag.set_preferred_provider(provider)
        results, _ = self.eodag.search(productType=product_type, **search_criteria)
        one_product = results[0]
        self.assertEqual(one_product.provider, provider)
        return one_product

    def execute_download(self, product, expected_filename):
        """Download the product in a child process, avoiding to perform the entire
        download, then do some checks and delete the downloaded result from the
        filesystem.
        """

        dl_process = multiprocessing.Process(
            target=self.eodag.download, args=(product,)
        )
        dl_process.start()
        try:
            # It is assumed that after 5 seconds, we should have already get at least 1
            # Megabytes of data from provider
            # Consider changing this to fit a lower internet bandwidth
            dl_process.join(timeout=5)
            # added this timeout loop, to handle long download start times
            max_wait_time = 120
            while (
                dl_process.is_alive()
                and not glob.glob("%s/[!quicklooks]*" % TESTS_DOWNLOAD_PATH)
                and max_wait_time > 0
            ):
                dl_process.join(timeout=5)
                max_wait_time -= 5
            if dl_process.is_alive():  # The process has timed out
                dl_process.terminate()
        except KeyboardInterrupt:
            while dl_process.is_alive():
                dl_process.terminate()

        self.assertIn(
            expected_filename, os.listdir(product.downloader.config.outputs_prefix)
        )
        self.downloaded_file_path = os.path.join(
            product.downloader.config.outputs_prefix, expected_filename
        )
        # The partially downloaded file should be greater or equal to 1 MB
        self.assertGreaterEqual(os.stat(self.downloaded_file_path).st_size, 2 ** 20)

    def test_end_to_end_search_download_usgs(self):
        product = self.execute_search(
            "usgs", "L8_OLI_TIRS_C1L1", "2017-03-01", "2017-03-15", (50, 50, 50.3, 50.3)
        )
        expected_filename = "{}.tar.bz".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_airbus(self):
        product = self.execute_search(
            "sobloo",
            "S2_MSI_L1C",
            "2018-05-01",
            "2018-06-01",
            (
                0.2563590566012408,
                43.19555008715042,
                2.379835675499976,
                43.907759172380565,
            ),
        )
        expected_filename = "{}.zip".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    @unittest.skip(
        "Download of S2_MSI_L1C Products on peps provider before 2016/12/05 is known "
        "to be asynchronous and this feature is not present in eodag at the moment"
    )
    def test_end_to_end_search_download_peps_before_20161205(self):
        product = self.execute_search(
            "peps",
            "S2_MSI_L1C",
            "2016-06-05",
            "2016-06-16",
            (137.772897, -37.134202, 153.749135, 73.885986),
        )
        expected_filename = "{}.zip".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_peps_after_20161205(self):
        product = self.execute_search(
            "peps",
            "S2_MSI_L1C",
            "2019-11-08",
            "2019-11-16",
            (137.772897, 13.134202, 153.749135, 23.885986),
        )
        expected_filename = "{}.zip".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_get_quicklook_peps(self):
        product = self.execute_search(
            "peps", "S2_MSI_L1C", "2019-03-01", "2019-03-15", (50, 50, 50.3, 50.3)
        )
        quicklook_file_path = product.get_quicklook(filename="peps_quicklook")
        # TearDown will remove quicklook_file_path on end
        self.downloaded_file_path = quicklook_file_path

        self.assertNotEqual(quicklook_file_path, "")
        self.assertEqual(os.path.basename(quicklook_file_path), "peps_quicklook")
        self.assertEqual(
            os.path.dirname(quicklook_file_path),
            os.path.join(product.downloader.config.outputs_prefix, "quicklooks"),
        )
        self.assertGreaterEqual(os.stat(quicklook_file_path).st_size, 2 ** 5)
