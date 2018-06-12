# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

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

    def execute(self, provider, product_type, start, end, bbox):
        """Execute the test on one provider.

        - First set the preferred provider as the one given in parameter
        - Then do a search
        - Then ensure that at least the first result originates from the provider
        - Download the first result
        - Delete the downloaded result from the filesystem
        """
        search_criteria = {
            'startTimeFromAscendingNode': start,
            'completionTimeFromAscendingNode': end,
        }
        search_criteria['geometry'] = {'lonmin': bbox[0], 'latmin': bbox[1], 'lonmax': bbox[2], 'latmax': bbox[3]}
        self.eodag.set_preferred_provider(provider)
        results = self.eodag.search(product_type, **search_criteria)
        one_product = results[0]
        self.assertEqual(one_product.provider, provider)
        path = self.eodag.download(one_product)
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isfile(path))
        os.unlink(path)

    def test_end_to_end_search_download_eocloud(self):
        self.execute(
            'eocloud',
            'S2_MSI_L1C',
            '2018-02-01',
            '2018-02-16',
            (9.1113159, 2.701635, 14.100952, 5.588651))

    def test_end_to_end_search_download_usgs(self):
        self.execute(
            'USGS',
            'L8_LC8',
            '2017-03-01',
            '2017-03-15',
            (50, 50, 50.3, 50.3))

    def test_end_to_end_search_download_airbus(self):
        self.execute(
            'airbus-ds',
            'S2_MSI_L1C',
            '2018-05-01',
            '2018-06-01',
            (0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565))

    def test_end_to_end_search_download_peps_before_20161205(self):
        self.execute(
            'peps',
            'S2_MSI_L1C',
            '2016-06-05',
            '2016-06-16',
            (137.772897, -37.134202, 153.749135, 73.885986))

    def test_end_to_end_search_download_peps_after_20161205(self):
        self.execute(
            'peps',
            'S2_MSI_L1C',
            '2018-06-05',
            '2018-06-16',
            (137.772897, -37.134202, 153.749135, 73.885986))

    def test_end_to_end_search_download_scihub(self):
        self.execute(
            'scihub',
            'S2_MSI_L1C',
            '2018-02-01',
            '2018-02-16',
            (-161.187910, 64.821439, -159.177830, 65.809122))
