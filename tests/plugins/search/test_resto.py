# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import unittest
from unittest.mock import patch

from dateutil.parser import parse as dateparse
from dateutil.relativedelta import relativedelta
from tests.context import RestoSearch


class TestRestoSearchPlugin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tested_plugin_instance_config = {
            'api_endpoint': 'http://finder.eocloud.eu/resto/api/',
            'products': {
                'Sentinel2': {
                    'min_start_date': '2016-12-10',  # new S2 products specification
                    'product_type': 'L1C',
                    'instrument': None,
                    'band2_pattern': '*B02.tif',
                    'lms': '40',
                },
                'Landsat8': {
                    'min_start_date': '2013-05-26',
                    'product_type': 'L1T',
                    'instrument': 'OLI',
                    'band2_pattern': '*_B2.tif',
                    'lms': '120',
                },
                'Envisat': {
                    'min_start_date': '2002-05-17',
                    'product_type': 'FRS',
                    'instrument': None,
                    'band2_pattern': '*_band_02.tif',
                    'lms': '1200',
                },
            },
        }
        cls.RestoSearchInstance = RestoSearch(config=tested_plugin_instance_config)

    def setUp(self):
        self.search_criteria = {
            'box': '',
            'startDate': '',
            'endDate': '',
            'cloudCover': '',
            'productType': '',
            'geometry': ''
        }

    def test_query_url_template_ok(self):
        """Query url template is ok"""
        self.assertEqual(
            self.RestoSearchInstance.query_url_tpl,
            'http://finder.eocloud.eu/resto/api/collections/{collection}/search.json'
        )

    def test_query_product_type_is_configured(self):
        """A queried productType must be configured for the RestoSearch plugin instance"""
        self.search_criteria['productType'] = 'inexistent'
        self.assertRaises(RuntimeError, self.RestoSearchInstance.query, self.search_criteria['productType'])

    def test_query_cloud_cover_percent(self):
        """CloudCover query param must be a percentage"""
        self.search_criteria['productType'] = 'L1C'
        self.search_criteria['cloudCover'] = 110
        self.assertRaises(
            RuntimeError,
            self.RestoSearchInstance.query,
            self.search_criteria['productType'],
            cloudCover=self.search_criteria['cloudCover']
        )

    @patch('requests.get')
    def test_query_cloud_cover_capped(self, requests_get_mock):
        """CloudCover query param must be capped to the max value configured"""
        self.search_criteria['productType'] = 'L1C'
        self.search_criteria['cloudCover'] = RestoSearch.DEFAULT_MAX_CLOUD_COVER + 1
        self.RestoSearchInstance.query(
            self.search_criteria['productType'],
            cloudCover=self.search_criteria['cloudCover']
        )
        requests_get_mock.assert_called_once_with(
            'http://finder.eocloud.eu/resto/api/collections/Sentinel2/search.json',
            params={
                'sortOrder': 'descending',
                'sortParam': 'startDate',
                'startDate': '2016-12-10',
                'cloudCover': '[0,{}]'.format(RestoSearch.DEFAULT_MAX_CLOUD_COVER),
                'productType': 'L1C',
            }
        )

    @patch('requests.get')
    def test_query_start_date_capped(self, requests_get_mock):
        """StartDate query param must be capped to the min start date configured for a collection.

        This means querying a start date older than what configured gives the results for up to the minimum known start
        date of the collection: when min start date is 2016-12-10, querying for start date 2015-12-10 gives an oldest
        result from 2016-12-10
        """
        self.search_criteria['productType'] = 'L1C'
        self.search_criteria['startDate'] = str(
            dateparse(self.RestoSearchInstance.config['products']['Sentinel2']['min_start_date'])
            + relativedelta(years=-1)
        )
        self.RestoSearchInstance.query(
            self.search_criteria['productType'],
            startDate=self.search_criteria['startDate']
        )
        self.assertLess(
            dateparse(self.search_criteria['startDate']),
            dateparse(self.RestoSearchInstance.config['products']['Sentinel2']['min_start_date'])
        )
        requests_get_mock.assert_called_once_with(
            'http://finder.eocloud.eu/resto/api/collections/Sentinel2/search.json',
            params={
                'sortOrder': 'descending',
                'sortParam': 'startDate',
                'startDate': self.RestoSearchInstance.config['products']['Sentinel2']['min_start_date'],
                'cloudCover': '[0,{}]'.format(RestoSearch.DEFAULT_MAX_CLOUD_COVER),
                'productType': 'L1C',
            }
        )

    @patch('requests.get')
    def test_query_end_date_in_request(self, requests_get_mock):
        """Giving an end date should modify the request parameters"""
        self.search_criteria['productType'] = 'L1C'
        self.search_criteria['endDate'] = str(
            dateparse(self.RestoSearchInstance.config['products']['Sentinel2']['min_start_date'])
            + relativedelta(months=+1)
        )
        self.RestoSearchInstance.query(
            self.search_criteria['productType'],
            endDate=self.search_criteria['endDate']
        )
        requests_get_mock.assert_called_once_with(
            'http://finder.eocloud.eu/resto/api/collections/Sentinel2/search.json',
            params={
                'sortOrder': 'descending',
                'sortParam': 'startDate',
                'startDate': self.RestoSearchInstance.config['products']['Sentinel2']['min_start_date'],
                'cloudCover': '[0,{}]'.format(RestoSearch.DEFAULT_MAX_CLOUD_COVER),
                'productType': 'L1C',
                'completionDate': '2017-01-10 00:00:00',
            }
        )

