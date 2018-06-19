# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import multiprocessing
import os
import unittest

from tests import TEST_RESOURCES_PATH
from tests.context import SatImagesAPI


class TestEODagEndToEnd(unittest.TestCase):
    """Make real case tests. This assume the existence of a user conf file in resources folder named user_conf.yml"""

    @classmethod
    def setUpClass(cls):
        cls.eodag = SatImagesAPI(user_conf_file_path=os.path.join(TEST_RESOURCES_PATH, 'user_conf.yml'))
        # Ensure that we will be able to make search requests on only one provider, by setting partial to False by
        # default for all the supported product types of all the providers
        for provider, conf in cls.eodag.providers_config.items():
            for product_type, pt_conf in conf['products'].items():
                pt_conf['partial'] = False
            # Force all providers implementing RestoSearch and defining how to retrieve products by specifying the
            # location scheme to use https, enabling actual downloading of the product
            if conf.get('search', {}).get('product_location_scheme', 'https') == 'file':
                conf['search']['product_location_scheme'] = 'https'
            # Disable extraction
            try:  # Case HTTPDownload plugin
                conf['download']['extract'] = False
            except KeyError:  # case api plugin
                conf['api']['extract'] = False

    def setUp(self):
        self.downloaded_file_path = ''

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
            'startTimeFromAscendingNode': start,
            'completionTimeFromAscendingNode': end,
            'geometry': {'lonmin': bbox[0], 'latmin': bbox[1], 'lonmax': bbox[2], 'latmax': bbox[3]}
        }
        self.eodag.set_preferred_provider(provider)
        results = self.eodag.search(product_type, **search_criteria)
        one_product = results[0]
        self.assertEqual(one_product.provider, provider)
        return one_product

    def execute_download(self, product, expected_filename):
        """Download the product in a child process, avoiding to perform the entire download, then do some checks and
        delete the downloaded result from the filesystem.
        """
        dl_process = multiprocessing.Process(target=self.eodag.download, args=(product,))
        dl_process.start()
        try:
            # It is assumed that after 5 seconds, we should have already get at least 1 Megabytes of data from provider
            # Consider changing this to fit a lower internet bandwidth
            dl_process.join(timeout=5)
            if dl_process.is_alive():  # The process has timed out
                dl_process.terminate()
        except KeyboardInterrupt:
            while dl_process.is_alive():
                dl_process.terminate()
        self.assertIn(expected_filename, os.listdir(self.eodag.user_config['outputs_prefix']))
        self.downloaded_file_path = os.path.join(self.eodag.user_config['outputs_prefix'], expected_filename)
        # The partially downloaded file should be greater or equal to 1 MB
        self.assertGreaterEqual(os.stat(self.downloaded_file_path).st_size, 2 ** 20)

    def test_end_to_end_search_download_airbus(self):
        product = self.execute_search(
            'airbus-ds',
            'S2_MSI_L1C',
            '2018-05-01',
            '2018-06-01',
            (0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565)
        )
        expected_filename = '{}.zip'.format(product.properties['title'])
        self.execute_download(product, expected_filename)
