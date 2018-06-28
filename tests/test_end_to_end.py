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
        from eodag.utils.logging import setup_logging
        setup_logging(verbose=3)
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

    def test_end_to_end_search_download_eocloud(self):
        product = self.execute_search(
            'eocloud',
            'S2_MSI_L1C',
            '2018-02-01',
            '2018-02-16',
            (9.1113159, 2.701635, 14.100952, 5.588651)
        )
        expected_filename = '{}.zip'.format(product.properties['title'])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_usgs(self):
        product = self.execute_search(
            'USGS',
            'L8_LC8',
            '2017-03-01',
            '2017-03-15',
            (50, 50, 50.3, 50.3)
        )
        expected_filename = '{}.tar.bz'.format(product.properties['title'])
        self.execute_download(product, expected_filename)

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

    @unittest.skip('Download of S2_MSI_L1C Products on peps provider before 2016/12/05 is known to be asynchronous and '
                   'this feature is not present in eodag at the moment')
    def test_end_to_end_search_download_peps_before_20161205(self):
        product = self.execute_search(
            'peps',
            'S2_MSI_L1C',
            '2016-06-05',
            '2016-06-16',
            (137.772897, -37.134202, 153.749135, 73.885986)
        )
        expected_filename = '{}.zip'.format(product.properties['title'])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_peps_after_20161205(self):
        product = self.execute_search(
            'peps',
            'S2_MSI_L1C',
            '2018-06-05',
            '2018-06-16',
            (137.772897, -37.134202, 153.749135, 73.885986)
        )
        expected_filename = '{}.zip'.format(product.properties['title'])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_scihub(self):
        product = self.execute_search(
            'scihub',
            'S2_MSI_L1C',
            '2018-02-01',
            '2018-02-16',
            (-161.187910, 64.821439, -159.177830, 65.809122)
        )
        # Scihub api manage incomplete downloads by adding '.incomplete' to a file that hasn't been fully downloaded yet
        expected_filename = '{}.zip.incomplete'.format(product.properties['title'])
        self.execute_download(product, expected_filename)

    def test_get_quiclook_peps(self):
        product = self.execute_search('peps', 'S2_MSI_L1C', '2014-03-01', '2017-03-15', (50, 50, 50.3, 50.3))
        product.get_quicklook('peps_quicklook')

        expected_filename = os.path.join(self.eodag.user_config['outputs_prefix'], 'quicklooks', 'peps_quicklook')
        self.assertIn('peps_quicklook', os.listdir(os.path.join(self.eodag.user_config['outputs_prefix'],
                                                                'quicklooks')))
        self.assertGreaterEqual(os.stat(expected_filename).st_size, 2 ** 5)

    def test_get_quiclook_scihub(self):
        product = self.execute_search('scihub', 'S2_MSI_L1C', '2014-03-01', '2017-03-15', (50, 50, 50.3, 50.3))
        product.get_quicklook('scihub_quicklook')

        expected_filename = os.path.join(self.eodag.user_config['outputs_prefix'], 'quicklooks', 'scihub_quicklook')
        self.assertIn('scihub_quicklook', os.listdir(os.path.join(self.eodag.user_config['outputs_prefix'],
                                                                  'quicklooks')))
        self.assertGreaterEqual(os.stat(expected_filename).st_size, 2 ** 5)

    def test_get_quicklook_theia(self):
        product = self.execute_search('theia', 'S2_REFLECTANCE', '2018-06-15', '2018-06-29', (-1, 45, 1, 47))
        product.get_quicklook('theia_quicklook')

        expected_filename = os.path.join(self.eodag.user_config['outputs_prefix'], 'quicklooks', 'theia_quicklook')
        self.assertIn('theia_quicklook', os.listdir(os.path.join(self.eodag.user_config['outputs_prefix'],
                                                                 'quicklooks')))
        self.assertGreaterEqual(os.stat(expected_filename).st_size, 2 ** 5)

    def test_get_quicklook_theia_landsat(self):
        product = self.execute_search('theia-landsat', 'LS_REFLECTANCE', '2017-03-15', '2017-04-15', (-2, 41, 0, 43))
        product.get_quicklook('theia_landsat_quicklook')

        expected_filename = os.path.join(self.eodag.user_config['outputs_prefix'], 'quicklooks',
                                         'theia_landsat_quicklook')
        self.assertIn('theia_landsat_quicklook', os.listdir(os.path.join(self.eodag.user_config['outputs_prefix'],
                                                                         'quicklooks')))
        self.assertGreaterEqual(os.stat(expected_filename).st_size, 2 ** 5)

    @unittest.expectedFailure
    def test_get_quicklook_eocloud(self):
        product = self.execute_search('eocloud', 'S2_MSI_L1C', '2014-03-01', '2017-03-15', (50, 50, 50.3, 50.3))
        product.get_quicklook('theia_landsat_quicklook')

        expected_filename = os.path.join(self.eodag.user_config['outputs_prefix'], 'quicklooks',
                                         'theia_landsat_quicklook')
        self.assertIn('theia_landsat_quicklook', os.listdir(os.path.join(self.eodag.user_config['outputs_prefix'],
                                                                         'quicklooks')))
        self.assertGreaterEqual(os.stat(expected_filename).st_size, 2 ** 5)

    @unittest.expectedFailure
    def test_get_quicklook_aibus_ds(self):
        product = self.execute_search('airbus-ds', 'S3_SRA_A_BS', '2014-03-01', '2017-03-15', (50, 50, 50.3, 50.3))
        product.get_quicklook('airbus_ds_quicklook')

        expected_filename = os.path.join(self.eodag.user_config['outputs_prefix'], 'quicklooks',
                                         'airbus_ds_quicklook')
        self.assertIn('airbus_ds_quicklook', os.listdir(os.path.join(self.eodag.user_config['outputs_prefix'],
                                                                     'quicklooks')))
        self.assertGreaterEqual(os.stat(expected_filename).st_size, 2 ** 5)


