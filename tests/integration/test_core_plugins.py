# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import copy
import functools
import hashlib
import json
import os
import random
import shutil
import tempfile
import unittest
import zipfile
from datetime import datetime

import requests
import shapely
import usgs
from shapely import geometry, wkt

from tests import EODagTestCase, TEST_RESOURCES_PATH
from tests.context import Authentication, Download, EOProduct, SatImagesAPI, SearchResult


try:
    from unittest import mock  # PY3
except ImportError:
    import mock  # PY2


class TestIntegrationCoreSearchPlugins(EODagTestCase):

    def test_core_resto_search_ok(self):
        """A search with a product type supported by a provider implementing RestoSearch must succeed"""
        self.override_properties(
            provider='mock-provider-1',
            product_type='MOCK_PRODUCT_TYPE',
            platform='',
            instrument='')
        provider_search_url_base = 'http://subdomain.domain.eu/resto/api/'  # See ../resources/mock_providers.yml
        resto_results = {
            'features': [
                {
                    'id': 1,
                    'geometry': self.geometry,
                    'properties': {
                        'productType': 'MOCK',  # See ../resources/mock_providers.yml
                        'platform': self.platform,
                        'instrument': self.instrument,
                        'completionDate': '',
                        'collection': 'MockCollection',  # See ../resources/mock_providers.yml
                        'productIdentifier': '/eodata/1/{}'.format(self.local_filename),
                        'organisationName': 'ESA',
                        'title': '1_{}'.format(self.local_filename),
                        'snowCover': '',
                        'cloudCover': '',
                        'description': '',
                        'keywords': '',
                        'resolution': '',
                        'startDate': '',
                        'orbitNumber': 0,
                    },
                },
                {
                    'id': 2,
                    'geometry': self.geometry,
                    'properties': {
                        'productType': 'MOCK',
                        'platform': '',
                        'instrument': '',
                        'completionDate': '',
                        'collection': 'MockCollection',
                        'productIdentifier': '/eodata/2/{}'.format(self.local_filename),
                        'organisationName': 'NOT_ESA',  # To see if the url given in 'services' below is used
                        'title': '2_{}'.format(self.local_filename),
                        'services': {
                            'download': {
                                'url': 'http://download.provider1.com/path/',
                            },
                        },
                        'snowCover': '',
                        'cloudCover': '',
                        'description': '',
                        'keywords': '',
                        'resolution': '',
                        'startDate': '',
                        'orbitNumber': 0,
                    },
                },
                {
                    'id': 3,
                    'geometry': self.geometry,
                    'properties': {
                        'productType': 'MOCK',
                        'platform': '',
                        'instrument': '',
                        'completionDate': '',
                        'collection': 'MockCollection',
                        'productIdentifier': '/eodata/3/{}'.format(self.local_filename),
                        'organisationName': 'NOT_ESA',  # To see if the url given in 'services' below is used
                        'title': '2_{}'.format(self.local_filename),
                        'snowCover': '',
                        'cloudCover': '',
                        'description': '',
                        'keywords': '',
                        'resolution': '',
                        'startDate': '',
                        'orbitNumber': 0,
                    },
                },
            ],
        }
        nominal_params = {
            'startDate': None,
            'sortOrder': 'descending',
            'sortParam': 'startDate',
            'productType': 'MOCK'
        }

        requests_http_get_response = self.requests_http_get.return_value
        requests_http_get_response.raise_for_status = mock.MagicMock()
        requests_http_get_response.json = mock.MagicMock(return_value=resto_results)

        dag = SatImagesAPI(providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'))
        results = dag.search(self.product_type)

        self.assertHttpGetCalledOnceWith(
            '{}collections/MockCollection/search.json'.format(provider_search_url_base),
            expected_params=nominal_params)
        self.assertEqual(requests_http_get_response.raise_for_status.call_count, 1)
        self.assertEqual(requests_http_get_response.json.call_count, 1)

        # Check the search result
        self.assertIsInstance(results, SearchResult)
        self.assertEqual(len(results), len(resto_results['features']))
        for idx, result in enumerate(results):
            self.assertIsInstance(result, EOProduct)
            self.assertEqual(result.provider, self.provider)
            self.assertEqual(result.properties['productType'], 'MOCK')  # See ../resources/mock_providers.yml for 'MOCK'
            self.assertEqual(result.properties['id'], resto_results['features'][idx]['id'])
            self.assertEqual(result.properties['completionTimeFromAscendingNode'],
                             resto_results['features'][idx]['properties']['completionDate'])

            if idx == 0:
                self.assertEqual(result.location,
                                 '{base}/1/S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE.zip')
            if idx == 1:
                self.assertEqual(result.location, 'http://download.provider1.com/path/')
            if idx == 2:
                self.assertEqual(result.location, '{base}/collections/MockCollection/3/download')

        # Test the use case of defining the product location scheme to 'file'
        self.override_properties(product_type='MOCK_PRODUCT_TYPE_5')
        results = dag.search(self.product_type)
        for idx, result in enumerate(results):
            self.assertEqual(result.location,
                             'file://{}'.format(resto_results['features'][idx]['properties']['productIdentifier']))

        # Test that when nothing is found, the returned result is empty
        requests_http_get_response.json = mock.MagicMock(return_value={'features': []})
        results = dag.search(self.product_type)
        self.assertEqual(len(results), 0)

    def test_core_resto_search_http_error(self):
        """If there is an requests.HTTPError, resto search must return an empty list of result"""
        self.override_properties(product_type='MOCK_PRODUCT_TYPE')
        provider_search_url_base = 'http://subdomain.domain.eu/resto/api/'  # See ../resources/mock_providers.yml
        nominal_params = {
            'startDate': None,
            'sortOrder': 'descending',
            'sortParam': 'startDate',
            'productType': 'MOCK'
        }

        requests_http_get_response = self.requests_http_get.return_value
        requests_http_get_response.raise_for_status = mock.MagicMock(side_effect=requests.HTTPError)

        dag = SatImagesAPI(providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'))
        # requests.get will return a response that will raise an requests.HTTPError when raise_for_status is called
        results = dag.search(self.product_type)

        self.assertEqual(requests_http_get_response.raise_for_status.call_count, 1)
        self.assertHttpGetCalledOnceWith(
            '{}collections/MockCollection/search.json'.format(provider_search_url_base),
            expected_params=nominal_params)

        # Assertions showing that the HTTPError was ignored and an empty list was returned as the result
        self.assertIsInstance(results, SearchResult)
        self.assertEqual(len(results), 0)

    def test_core_resto_search_kwargs_cloud_cover_default_ok(self):
        """A search with a cloud cover between 0 and the default max cloud cover must succeed"""
        self.override_properties(product_type='MOCK_PRODUCT_TYPE')
        kwargs = {'cloudCover': 5}
        provider_search_url_base = 'http://subdomain.domain.eu/resto/api/'  # See ../resources/mock_providers.yml
        call_params = {
            'startDate': None,
            'cloudCover': '[0,{cloudCover}]'.format(**kwargs),
            'sortOrder': 'descending',
            'sortParam': 'startDate',
            'productType': 'MOCK'
        }

        dag = SatImagesAPI(providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'))
        dag.search(self.product_type, **kwargs)

        self.assertHttpGetCalledOnceWith(
            '{}collections/MockCollection/search.json'.format(provider_search_url_base),
            expected_params=call_params)

    def test_core_resto_search_kwargs_cloud_cover_outbounds_ko(self):
        """A search with a cloud cover greater than 100 or lower than 0 must raise a RuntimeError"""
        self.override_properties(product_type='MOCK_PRODUCT_TYPE')
        dag = SatImagesAPI(providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'))
        self.assertRaises(RuntimeError, dag.search, self.product_type, cloudCover=101)
        self.assertRaises(RuntimeError, dag.search, self.product_type, cloudCover=-1)

    def test_core_resto_search_kwargs_end_date_ok(self):
        """A search with an endDate must succeed"""
        self.override_properties(product_type='MOCK_PRODUCT_TYPE')
        kwargs = {'completionTimeFromAscendingNode': '2018-05-09'}
        provider_search_url_base = 'http://subdomain.domain.eu/resto/api/'  # See ../resources/mock_providers.yml
        call_params = {
            'startDate': None,
            'sortOrder': 'descending',
            'sortParam': 'startDate',
            'productType': 'MOCK',
            'completionDate': kwargs['completionTimeFromAscendingNode']
        }

        dag = SatImagesAPI(providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'))
        dag.search(self.product_type, **kwargs)

        self.assertHttpGetCalledOnceWith(
            '{}collections/MockCollection/search.json'.format(provider_search_url_base),
            expected_params=call_params)

    def test_core_resto_search_kwargs_footprint_ok(self):
        """A search with a footprint must succeed"""
        self.override_properties(product_type='MOCK_PRODUCT_TYPE')
        provider_search_url_base = 'http://subdomain.domain.eu/resto/api/'  # See ../resources/mock_providers.yml
        dag = SatImagesAPI(providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'))
        call_params = {
            'startDate': None,
            'sortOrder': 'descending',
            'sortParam': 'startDate',
            'productType': 'MOCK',
            'box': '{lonmin},{latmin},{lonmax},{latmax}'.format(**self.footprint)
        }
        dag.search(self.product_type, **{'geometry': self.footprint})
        self.assertHttpGetCalledOnceWith(
            '{}collections/MockCollection/search.json'.format(provider_search_url_base),
            expected_params=call_params)

    @mock.patch('eodag.plugins.search.csw.PropertyIsEqualTo', autospec=True)
    @mock.patch('eodag.plugins.search.csw.PropertyIsLike', autospec=True)
    @mock.patch('eodag.plugins.search.csw.CatalogueServiceWeb', autospec=True)
    def test_core_csw_search_auth_default_version_ok(self, mock_catalogue_web_service, prop_like, prop_eq):
        """A search on a provider implementing CSWSearch with auth requirement and default csw version must succeed"""
        self.override_properties(provider='mock-provider-7', product_type='MOCK_PRODUCT_TYPE_7')
        default_version = '2.0.2'
        dag = SatImagesAPI(
            providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'),
            user_conf_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_user_conf.yml'))
        mock_catalog = mock_catalogue_web_service.return_value

        mock_catalog.getrecords2.side_effect = functools.partial(self.compute_csw_records, mock_catalog)

        results = dag.search(self.product_type)

        # Catalog service is created only once
        self.assertEqual(mock_catalogue_web_service.call_count, 1)

        # One result for each search tag (dc:title and dc:subject)
        self.assertEqual(len(results), 5)
        mock_catalogue_web_service.assert_called_with(
            'http://www.catalog.com/rest/catalog/csw/',
            version=default_version,
            username='user',
            password='pwd')
        self.assertEqual(prop_like.call_count, 4)
        self.assertEqual(prop_eq.call_count, 1)
        prop_like.assert_any_call('dc:title', '%{}%'.format(self.product_type))
        prop_like.assert_any_call('dc:yet_another_thing', '%{}%'.format(self.product_type))
        prop_like.assert_any_call('dc:something', '{}%'.format(self.product_type))
        prop_like.assert_any_call('dc:something_else', '%{}'.format(self.product_type))
        prop_eq.assert_any_call('dc:subject', self.product_type)
        self.assertEqual(mock_catalog.getrecords2.call_count, 5)
        mock_catalog.getrecords2.assert_called_with(
            constraints=mock.ANY,
            esn='full',
            maxrecords=10)

    @mock.patch('eodag.plugins.search.csw.PropertyIsLike', autospec=True)
    @mock.patch('eodag.plugins.search.csw.CatalogueServiceWeb', autospec=True)
    def test_core_csw_search_no_auth_default_version_ok(self, mock_catalogue_web_service, prop_like):
        """A search on a provider implementing CSWSearch without auth and default csw version must succeed"""
        self.override_properties(provider='mock-provider-8', product_type='MOCK_PRODUCT_TYPE_8')
        default_version = '2.0.2'
        dag = SatImagesAPI(providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'))
        mock_catalog = mock_catalogue_web_service.return_value

        mock_catalog.getrecords2.side_effect = functools.partial(self.compute_csw_records, mock_catalog)

        results = dag.search(self.product_type)

        # Catalog service is created only once
        self.assertEqual(mock_catalogue_web_service.call_count, 1)
        self.assertEqual(len(results), 1)
        mock_catalogue_web_service.assert_called_with(
            'http://www.catalog.com/rest/catalog/csw/',
            version=default_version,
            username=None,
            password=None)
        self.assertEqual(prop_like.call_count, 1)
        prop_like.assert_any_call('dc:title', '%{}%'.format(self.product_type))
        self.assertEqual(mock_catalog.getrecords2.call_count, 1)
        mock_catalog.getrecords2.assert_called_with(
            constraints=mock.ANY,
            esn='full',
            maxrecords=10
        )

    @mock.patch('eodag.plugins.search.csw.CatalogueServiceWeb', autospec=True)
    def test_core_csw_search_catalog_init_error_ok(self, mock_catalogue_web_service):
        """A search on a provider implementing CSWSearch must return no result if error during catalog initialisation"""
        self.override_properties(provider='mock-provider-8', product_type='MOCK_PRODUCT_TYPE_8')
        default_version = '2.0.2'
        dag = SatImagesAPI(providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'))
        mock_catalogue_web_service.side_effect = Exception
        mock_catalog = mock_catalogue_web_service.return_value
        results = dag.search(self.product_type)
        self.assertEqual(len(results), 0)
        mock_catalogue_web_service.assert_called_with(
            'http://www.catalog.com/rest/catalog/csw/',
            version=default_version,
            username=None,
            password=None)
        mock_catalog.getrecords2.assert_not_called()

    @mock.patch('eodag.plugins.search.csw.CatalogueServiceWeb', autospec=True)
    def test_core_csw_search_get_records_error_ok(self, mock_catalogue_web_service):
        """A search on a provider implementing CSWSearch must return result even though getrecords fails on some tags"""
        self.override_properties(provider='mock-provider-7', product_type='MOCK_PRODUCT_TYPE_7')
        dag = SatImagesAPI(
            providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'),
            user_conf_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_user_conf.yml'))
        mock_catalog = mock_catalogue_web_service.return_value
        mock_catalog.getrecords2.side_effect = functools.partial(
            self.compute_csw_records, mock_catalog, raise_error_for='dc:title')
        results = dag.search(self.product_type)
        self.assertEqual(len(results), 4)  # Only the number of results is different from a nominal search
        self.assertEqual(mock_catalog.getrecords2.call_count, 5)
        mock_catalog.getrecords2.assert_called_with(
            constraints=mock.ANY,
            esn='full',
            maxrecords=10)

    @mock.patch('eodag.plugins.search.csw.BBox', autospec=True)
    @mock.patch('eodag.plugins.search.csw.PropertyIsLike', autospec=True)
    @mock.patch('eodag.plugins.search.csw.PropertyIsGreaterThanOrEqualTo', autospec=True)
    @mock.patch('eodag.plugins.search.csw.PropertyIsLessThanOrEqualTo', autospec=True)
    @mock.patch('eodag.plugins.search.csw.CatalogueServiceWeb', autospec=True)
    def test_core_csw_search_start_end_dates_footprint(self, mock_catalogue_web_service, prop_le, prop_ge, prop_like,
                                                       bbox):
        """A search on a provider implementing CSWSearch must correctly interpret date tags and footprint"""
        self.override_properties(provider='mock-provider-8', product_type='MOCK_PRODUCT_TYPE_8')
        params = {
            'completionTimeFromAscendingNode': '2018-05-09',
            'startTimeFromAscendingNode': '2018-05-01',
            'geometry': self.footprint
        }
        dag = SatImagesAPI(providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'))
        mock_catalog = mock_catalogue_web_service.return_value
        mock_catalog.getrecords2.side_effect = functools.partial(self.compute_csw_records, mock_catalog)

        results = dag.search(self.product_type, **params)

        self.assertEqual(len(results), 1)
        self.assertEqual(mock_catalog.getrecords2.call_count, 1)
        self.assertEqual(prop_like.call_count, 1)
        prop_like.assert_any_call('dc:title', '%{}%'.format(self.product_type))
        prop_ge.assert_called_with('apiso:TempExtent_begin', params['startTimeFromAscendingNode'])
        prop_le.assert_called_with('apiso:TempExtent_end', params['completionTimeFromAscendingNode'])
        bbox.assert_called_with([
            self.footprint['lonmin'], self.footprint['latmin'], self.footprint['lonmax'], self.footprint['latmax']])
        mock_catalog.getrecords2.assert_called_with(
            constraints=mock.ANY,
            esn='full',
            maxrecords=10)

    def test_core_aws_search_ok(self):
        """A search with a product type supported by a provider implementing AwsSearch must succeed"""
        self.override_properties(provider='mock-provider-6', product_type='MOCK_PRODUCT_TYPE_6')
        provider_search_url_base = 'http://subdomain6.domain.eu/resto/api/'  # See ../resources/mock_providers.yml
        comp_date = '2018-05-09'
        resto_results = {
            'features': [{
                'id': 1,
                'geometry': self.geometry,
                'properties': {
                    'productType': 'MOCK6',  # See ../resources/mock_providers.yml
                    'platform': self.platform,
                    'instrument': self.instrument,
                    'completionDate': comp_date,
                    'collection': 'MockCollection6',
                    'productIdentifier': '/eodata/1/{}'.format(self.local_filename),
                    'organisationName': 'ESA',
                    'title': self.local_filename,
                    'snowCover': '',
                    'cloudCover': '',
                    'description': '',
                    'keywords': '',
                    'resolution': '',
                    'startDate': '',
                    'orbitNumber': 0,
                }
            }]
        }
        nominal_params = {
            'startDate': None,
            'sortOrder': 'descending',
            'sortParam': 'startDate',
            'productType': 'MOCK6'
        }

        requests_http_get_response = self.requests_http_get.return_value
        requests_http_get_response.raise_for_status = mock.MagicMock()
        requests_http_get_response.json = mock.MagicMock(return_value=resto_results)

        dag = SatImagesAPI(providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'))
        results = dag.search(self.product_type)

        self.assertHttpGetCalledOnceWith(
            '{}collections/MockCollection6/search.json'.format(provider_search_url_base),
            expected_params=nominal_params)
        self.assertEqual(requests_http_get_response.raise_for_status.call_count, 1)
        self.assertEqual(requests_http_get_response.json.call_count, 1)

        # Check the search result
        self.assertIsInstance(results, SearchResult)
        self.assertEqual(len(results), len(resto_results['features']))
        for result in results:
            self.assertIsInstance(result, EOProduct)
            self.assertEqual(result.provider, self.provider)
            self.assertEqual(result.location, 'tiles/31/T/DH/2018/5/9/0/')

        # Test that when nothing is found, the returned result is empty
        requests_http_get_response.json = mock.MagicMock(return_value={'features': []})
        results = dag.search(self.product_type)
        self.assertEqual(len(results), 0)

    def test_core_search_filtered_and_prepared_for_download(self):
        """For any search plugin, the result must be filtered and initialized with a downloader and an authenticator"""
        self.override_properties(provider='mock-provider-9', product_type='MOCK_PRODUCT_TYPE_9')
        invalid_geom = wkt.loads('POLYGON((10.469970703124998 3.9957805129630373,12.227783203124998 4.740675384778385,'
                                 '12.095947265625 4.061535597066097,10.491943359375 4.412136788910175,'
                                 '10.469970703124998 3.9957805129630373))')
        search_extent = {
            'lonmin': 10.469970703124998, 'latmin': 3.9957805129630373,
            'lonmax': 12.227783203124998, 'latmax': 4.740675384778385
        }
        resto_results = {
            'features': [
                {
                    'id': 1,
                    'geometry': invalid_geom,
                    'properties': {
                        'productType': 'MOCK9',  # See ../resources/mock_providers.yml
                        'platform': self.platform,
                        'instrument': self.instrument,
                        'completionDate': '',
                        'collection': 'MockCollection9',  # See ../resources/mock_providers.yml
                        'productIdentifier': '/eodata/1/{}'.format(self.local_filename),
                        'organisationName': 'ESA',
                        'title': '1_{}'.format(self.local_filename),
                        'snowCover': '',
                        'cloudCover': '',
                        'description': '',
                        'keywords': '',
                        'resolution': '',
                        'startDate': '',
                        'orbitNumber': 0,
                    },
                },
                {
                    'id': 2,
                    'geometry': self.geometry,
                    'properties': {
                        'productType': 'MOCK9',
                        'platform': '',
                        'instrument': '',
                        'completionDate': '',
                        'collection': 'MockCollection9',
                        'productIdentifier': '/eodata/2/{}'.format(self.local_filename),
                        'organisationName': 'NOT_ESA',  # To see if the url given in 'services' below is used
                        'title': '2_{}'.format(self.local_filename),
                        'services': {
                            'download': {
                                'url': 'https://subdomain9.domain.eu/download/',
                            },
                        },
                        'snowCover': '',
                        'cloudCover': '',
                        'description': '',
                        'keywords': '',
                        'resolution': '',
                        'startDate': '',
                        'orbitNumber': 0,
                    },
                },
            ],
        }

        requests_http_get_response = self.requests_http_get.return_value
        requests_http_get_response.raise_for_status = mock.MagicMock()
        requests_http_get_response.json = mock.MagicMock(return_value=resto_results)

        requests_http_post_response = self.requests_http_post.return_value
        requests_http_post_response.raise_for_status = mock.MagicMock()
        requests_http_post_response.json = mock.MagicMock(return_value={
            'tokenIdentity': 'd3bd997e78b748edb89390ac04c748dd'
        })

        dag = SatImagesAPI(
            providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'),
            user_conf_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_user_conf.yml')
        )
        results = dag.search(self.product_type, geometry=search_extent)

        self.assertEqual(len(results), 1)
        valid_product = next(iter(results))
        self.assertEqual(valid_product.properties['id'], 2)
        self.assertIsInstance(valid_product.downloader, Download)
        self.assertEqual(valid_product.downloader.instance_name, valid_product.provider)
        self.assertIsInstance(valid_product.downloader_auth, Authentication)


class TestIntegrationCoreDownloadPlugins(unittest.TestCase):

    def test_core_http_download_local_product(self):
        """A local product must not be downloaded and the download plugin must return its local absolute path"""
        self.product.location = 'file:///absolute/path/to/local/product.zip'
        paths = self.eodag.download_all(SearchResult([self.product]))
        self.assertEqual(paths[0], '/absolute/path/to/local/product.zip')
        self.assertAuthenticationDone()
        self.assertHttpDownloadNotDone()

    def test_core_http_download_remote_product_no_extract(self):
        """A remote product must be downloaded as is if extraction config is set to False"""
        self.eodag.providers_config[self.test_provider]['download']['extract'] = False
        self.product.location = '{base}/path/to/product.zip'
        self.requests_get.return_value = self._requests_get_response()

        paths = self.eodag.download_all(SearchResult([self.product]))
        self.assertHttpDownloadDone(paths[0])
        self.assertAuthenticationDone()

    def test_core_http_download_remote_product_extract(self):
        """A remote product must be downloaded and extracted as is if extraction config is set to True (by default)"""
        self.eodag.providers_config[self.test_provider]['download']['extract'] = True
        self.product.location = '{base}/path/to/product.zip'
        self.requests_get.return_value = self._requests_get_response()

        paths = self.eodag.download_all(SearchResult([self.product]))
        self.assertHttpDownloadDone(paths[0], with_extraction=True)
        self.assertAuthenticationDone()

    def test_core_http_download_remote_no_url(self):
        """Download must fail on an EOProduct with no download url"""
        paths = self.eodag.download_all(SearchResult([self.product]))
        self.assertEqual(len(paths), 1)
        self.assertIsNone(paths[0])
        self.assertAuthenticationDone()
        self.assertHttpDownloadNotDone()

    def test_core_http_download_remote_already_downloaded(self):
        """Download must return the path of a product already downloaded"""
        self.eodag.providers_config[self.test_provider]['download']['extract'] = False
        self.product.location = '{base}/path/to/product.zip'

        # Simulate a previous download
        os.mkdir(self.expected_record_dir)
        open(self.expected_downloaded_path, 'wb').close()
        open(self.expected_record_file, 'w').close()

        paths = self.eodag.download_all(SearchResult([self.product]))
        self.assertEqual(paths[0], self.expected_downloaded_path)
        self.assertAuthenticationDone()
        self.assertEqual(self.requests_get.call_count, 0)

    @mock.patch('os.remove', autospec=True)
    def test_core_http_download_remote_recorded_file_absent(self, os_remove):
        """Download must be performed and record file must be suppressed if actual product is locally absent"""
        self.eodag.providers_config[self.test_provider]['download']['extract'] = False
        self.product.location = '{base}/path/to/product.zip'
        self.requests_get.return_value = self._requests_get_response()
        os_remove.side_effect = os.unlink

        # Simulate the presence of the record file
        os.mkdir(self.expected_record_dir)
        open(self.expected_record_file, 'w').close()

        paths = self.eodag.download_all(SearchResult([self.product]))
        os_remove.assert_called_with(self.expected_record_file)
        self.assertEqual(os_remove.call_count, 1)
        self.assertAuthenticationDone()
        self.assertHttpDownloadDone(paths[0])

    def test_core_http_download_remote_httperror(self):
        """An error during download must fail without stopping the overall download process"""
        self.eodag.providers_config[self.test_provider]['download']['extract'] = False
        self.product.location = '{base}/path/to/product.zip'
        self.requests_get.return_value = self._requests_get_response()

        def raise_http_error():
            raise requests.HTTPError

        self.requests_get.return_value.raise_for_status = raise_http_error

        paths = self.eodag.download_all(SearchResult([self.product]))
        self.assertEqual(len(paths), 1)
        self.assertIsNone(paths[0])
        self.assertAuthenticationDone()
        self.assertEqual(self.requests_get.call_count, 1)
        self.assertFalse(os.path.exists(self.expected_record_file))

    def test_core_aws_download(self):
        """"""

    def assertAuthenticationDone(self):
        self.assertEqual(self.requests_post.call_count, 1)
        data = self.requests_post.call_args[1]['data']
        self.requests_post.assert_called_with('https://subdomain9.domain.eu/authentication', data=mock.ANY)
        self.assertDictEqual(data, {'username': 'user', 'password': 'pwd'})

    def assertHttpDownloadDone(self, path, with_extraction=False):
        if with_extraction:
            expected_extraction_listing = [
                x.replace(os.path.join(TEST_RESOURCES_PATH, 'products'), tempfile.gettempdir())
                for x in self.list_dir(os.path.join(
                    TEST_RESOURCES_PATH, 'products', self.product.properties['title']))
            ]
            self.assertIn(path, expected_extraction_listing)
        else:
            self.assertEqual(path, self.expected_downloaded_path)
            self.assertTrue(zipfile.is_zipfile(path))
        self.assertEqual(self.requests_get.call_count, 1)
        self.assertTrue(os.path.exists(self.expected_record_file))
        with open(self.expected_record_file, 'r') as fh:
            self.assertEqual(fh.read(), self.expected_dl_url)

    def assertHttpDownloadNotDone(self):
        self.assertFalse(os.path.exists(self.expected_record_file))
        self.assertEqual(self.requests_get.call_count, 0)

    def list_dir(self, root_dir, with_files=True):
        listing = [root_dir]
        if with_files:
            children = os.listdir(root_dir)
        else:
            children = [x for x in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, x))]
        for child in children:
            path = os.path.join(root_dir, child)
            if os.path.isdir(path):
                listing.extend(self.list_dir(path, with_files))
            else:
                listing.append(path)
        return listing

    def _requests_get_response(self):
        class Response(object):
            """Emulation of a response to requests.get method"""

            def __init__(response):
                with open(self.local_product_as_archive_path, 'rb') as fh:
                    response.headers = {'content-length': len(fh.read())}

            def __enter__(response):
                return response

            def __exit__(response, *args):
                pass

            @staticmethod
            def iter_content(**kwargs):
                with open(self.local_product_as_archive_path, 'rb') as fh:
                    while True:
                        chunk = fh.read(kwargs['chunk_size'])
                        if not chunk:
                            break
                        yield chunk

            def raise_for_status(response):
                pass

        return Response()

    def setUp(self):
        self.test_provider = 'mock-provider-9'
        self.local_product_filename = 'S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE.zip'
        self.product = EOProduct.from_geojson({
            'type': 'Feature',
            'properties': {
                'eodag_product_type': '',
                'eodag_download_url': '',  # Will be overriden for each test case
                'eodag_provider': self.test_provider,  # Is necessary for identifying the right download plugin
                'eodag_search_intersection': {},
                'title': 'S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.SAFE',
            },
            'geometry': {
                "type": "Polygon",
                "coordinates": [[[0.495928592903789, 44.22596415476343], [1.870237286761489, 44.24783068396879],
                                 [1.888683014192297, 43.25939191053712], [0.536772323136669, 43.23826255332707],
                                 [0.495928592903789, 44.22596415476343]]]
            },
            'id': '9deb7e78-9341-5530-8fe8-f81fd99c9f0f'
        })
        self.eodag = SatImagesAPI(
            providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'),
            user_conf_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_user_conf.yml')
        )
        self.local_product_as_archive_path = os.path.abspath(
            os.path.join(TEST_RESOURCES_PATH, 'products', 'as_archive', self.local_product_filename))
        self.expected_record_dir = os.path.join(tempfile.gettempdir(), '.downloaded')
        self.expected_downloaded_path = os.path.join(tempfile.gettempdir(), self.local_product_filename)

        self.requests_get_patcher = mock.patch('requests.get', autospec=True)
        self.requests_post_patcher = mock.patch('requests.post', autospec=True)
        self.requests_get = self.requests_get_patcher.start()
        self.requests_post = self.requests_post_patcher.start()

        self.requests_post.return_value.json.return_value = {'tokenIdentity': 'token'}

        self.expected_dl_url = 'https://subdomain9.domain.eu/download/path/to/product.zip'
        self.expected_record_file = os.path.join(
            self.expected_record_dir,
            hashlib.md5(self.expected_dl_url.encode('utf-8')).hexdigest()
        )

    def tearDown(self):
        if os.path.exists(self.expected_record_dir):
            shutil.rmtree(self.expected_record_dir)
        if os.path.exists(self.expected_downloaded_path):
            os.unlink(self.expected_downloaded_path)
        self.requests_get_patcher.stop()
        self.requests_post_patcher.stop()


class TestIntegrationCoreApiPlugins(EODagTestCase):

    def setUp(self):
        super(TestIntegrationCoreApiPlugins, self).setUp()
        self.sentinelsat_patcher = mock.patch("sentinelsat.SentinelAPI", autospec=True)
        self.usgs_api_login_patcher = mock.patch('usgs.api.login')
        self.usgs_api_logout_patcher = mock.patch('usgs.api.logout')
        self.usgs_api_search_patcher = mock.patch('usgs.api.search')

        self.sentinelsatapi_class = self.sentinelsat_patcher.start()
        self.sentinelsatapi = self.sentinelsatapi_class.return_value
        self.usgs_api_login = self.usgs_api_login_patcher.start()
        self.usgs_api_logout = self.usgs_api_logout_patcher.start()
        self.usgs_api_search = self.usgs_api_search_patcher.start()

    def tearDown(self):
        super(TestIntegrationCoreApiPlugins, self).tearDown()
        self.sentinelsat_patcher.stop()
        self.usgs_api_login_patcher.stop()
        self.usgs_api_logout_patcher.stop()
        self.usgs_api_search_patcher.stop()

    def test_core_usgs_search_nominal(self):
        """Nominal search using usgs api must return results"""
        with open(os.path.join(TEST_RESOURCES_PATH, "usgs_search_results.json"), "r") as fp:
            usgs_search_results = json.load(fp)

        def usgs_search_behavior(*args, **kwargs):
            node_type = args[1]
            if node_type == usgs.EARTH_EXPLORER_CATALOG_NODE:
                return usgs_search_results
            raise usgs.USGSError

        self.usgs_api_search.side_effect = usgs_search_behavior
        dag = SatImagesAPI(
            providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'),
            user_conf_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_user_conf.yml')
        )
        self.override_properties(provider='mock-provider-11', product_type='L8_LC8')

        results = dag.search(self.product_type)
        self.assertEqual(len(results), len(usgs_search_results['data']['results']))
        self.assertEqual(self.usgs_api_login.call_count, 1)
        self.usgs_api_login.assert_called_with('user', 'pwd', save=True)
        self.assertEqual(self.usgs_api_search.call_count, len(usgs.CATALOG_NODES))
        self.usgs_api_search.assert_any_call(
            'LANDSAT_8_C1', usgs.EARTH_EXPLORER_CATALOG_NODE, start_date=None, end_date=None, ll=None, ur=None)
        self.usgs_api_search.assert_any_call(
            'LANDSAT_8_C1', usgs.CWIC_LSI_EXPLORER_CATALOG_NODE, start_date=None, end_date=None, ll=None, ur=None)
        self.usgs_api_search.assert_any_call(
            'LANDSAT_8_C1', usgs.HDDS_EXPLORER_CATALOG_NODE, start_date=None, end_date=None, ll=None, ur=None)
        self.usgs_api_search.assert_any_call(
            'LANDSAT_8_C1', usgs.CATALOG_NODES[-1], start_date=None, end_date=None, ll=None, ur=None)

        for idx, result in enumerate(results):
            expected = usgs_search_results['data']['results'][idx]
            self.assertRegexpMatches(
                result.location,
                r'^.+/L8/(\d{3}/){2}.+\.tar\.bz$'
            )
            self.assertEqual(result.properties['id'], expected['entityId'])
            self.assertEqual(result.properties['startTimeFromAscendingNode'], expected['acquisitionDate'])

        # Test searching with footprint as an additional criteria
        search_kwargs = {'geometry': self.footprint}
        dag.search(self.product_type, **search_kwargs)
        self.usgs_api_search.assert_any_call(
            'LANDSAT_8_C1', usgs.EARTH_EXPLORER_CATALOG_NODE, start_date=None, end_date=None,
            ll={'longitude': self.footprint['lonmin'], 'latitude': self.footprint['latmin']},
            ur={'longitude': self.footprint['lonmax'], 'latitude': self.footprint['latmax']})
        self.usgs_api_search.assert_any_call(
            'LANDSAT_8_C1', usgs.CWIC_LSI_EXPLORER_CATALOG_NODE, start_date=None, end_date=None,
            ll={'longitude': self.footprint['lonmin'], 'latitude': self.footprint['latmin']},
            ur={'longitude': self.footprint['lonmax'], 'latitude': self.footprint['latmax']})
        self.usgs_api_search.assert_any_call(
            'LANDSAT_8_C1', usgs.HDDS_EXPLORER_CATALOG_NODE, start_date=None, end_date=None,
            ll={'longitude': self.footprint['lonmin'], 'latitude': self.footprint['latmin']},
            ur={'longitude': self.footprint['lonmax'], 'latitude': self.footprint['latmax']})
        self.usgs_api_search.assert_any_call(
            'LANDSAT_8_C1', usgs.CATALOG_NODES[-1], start_date=None, end_date=None,
            ll={'longitude': self.footprint['lonmin'], 'latitude': self.footprint['latmin']},
            ur={'longitude': self.footprint['lonmax'], 'latitude': self.footprint['latmax']})

    def test_core_usgs_download(self):
        """"""

    def test_core_sentinelsat_search_nominal(self):
        """Nominal search using sentinelsatapi must return results"""
        with open(os.path.join(TEST_RESOURCES_PATH, "sentinelsat_search_results.json"), "r") as fp:
            sentinelsat_search_results = json.load(fp)
            for props in sentinelsat_search_results.values():
                props['beginposition'] = datetime.utcnow()
                props['endposition'] = datetime.utcnow()
        self.sentinelsatapi.query.return_value = copy.deepcopy(sentinelsat_search_results)
        self.override_properties(
            provider='mock-provider-10',
            product_type='MOCK_PRODUCT_TYPE_10',
            platform='Sentinel-1',
            instrument='SAR-C SAR'
        )
        dag = SatImagesAPI(
            providers_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_providers.yml'),
            user_conf_file_path=os.path.join(TEST_RESOURCES_PATH, 'mock_user_conf.yml')
        )
        results = dag.search(self.product_type)

        self.assertEqual(len(results), len(sentinelsat_search_results.keys()))
        self.assertEqual(self.sentinelsatapi_class.call_count, 1)
        self.sentinelsatapi_class.assert_called_with('user', 'pwd', 'https://subdomain10.domain.eu/api/')
        self.assertEqual(self.sentinelsatapi.query.call_count, 1)
        self.sentinelsatapi.query.assert_called_with(
            producttype='OCN',
            limit=10,
            **{}
        )

        for eo_product in results:
            self.assertIn('id', eo_product.properties)
            expected_original = sentinelsat_search_results[eo_product.properties['id']]
            self.assertEqual(eo_product.location, expected_original['link'])
            self.assertEqual(eo_product.geometry, shapely.wkt.loads(expected_original['footprint']))

        # Check that the sentinelsatapi is only instantiated once per query
        dag.search(self.product_type)
        self.assertEqual(self.sentinelsatapi_class.call_count, 1)
        # And that the same instance is used for subsequent calls
        self.assertEqual(self.sentinelsatapi.query.call_count, 2)
        self.sentinelsatapi.query.assert_called_with(
            producttype='OCN',
            limit=10,
            **{}
        )

        # Test searching only with footprint and maxCloudCover (simple cases of searching with additional criteria)
        max_cloud_cover = random.choice(range(100))
        search_kwargs = {
            'geometry': self.footprint,
            'cloudCover': max_cloud_cover,
        }
        # Refresh the return value of the query method, because in sentinelsat.py, the returned value is modified
        self.sentinelsatapi.query.return_value = copy.deepcopy(sentinelsat_search_results)
        results = dag.search(self.product_type, **search_kwargs)
        self.assertNotEqual(len(results), 0)
        self.sentinelsatapi.query.assert_called_with(
            producttype='OCN',
            limit=10, **{
                'area': geometry.box(*(
                    self.footprint['lonmin'],
                    self.footprint['latmin'],
                    self.footprint['lonmax'],
                    self.footprint['latmax']
                )).to_wkt(),
                'cloudcoverpercentage': (0, max_cloud_cover),
            }
        )

        # Test searching with start and/or end date
        # First case: giving only the start date should not take into account the date search key
        start_date = '2018-01-01'
        search_kwargs = {'startTimeFromAscendingNode': start_date}
        dag.search(self.product_type, **search_kwargs)
        self.sentinelsatapi.query.assert_called_with(
            producttype='OCN',
            limit=10,
            **{}  # startDate is not interpreted by sentinelsat plugin
        )
        # Second case: start and end dates are given, either in plain string as above or as datetime or date python
        # objects. They should be transform to string date with format '%Y%m%d'
        search_kwargs['startTimeFromAscendingNode'] = random.choice([
            datetime(2018, 1, 1, 0, 0, 0, 0),
            datetime(2018, 1, 1, 0, 0, 0, 0).date()
        ])
        search_kwargs['completionTimeFromAscendingNode'] = random.choice([
            datetime(2018, 1, 2, 0, 0, 0, 0),
            datetime(2018, 1, 2, 0, 0, 0, 0).date()
        ])
        dag.search(self.product_type, **search_kwargs)
        self.sentinelsatapi.query.assert_called_with(
            producttype='OCN',
            limit=10, **{
                'date': ('20180101', '20180102')
            }
        )
        search_kwargs['startTimeFromAscendingNode'] = start_date
        search_kwargs['completionTimeFromAscendingNode'] = '2018-01-02'
        dag.search(self.product_type, **search_kwargs)
        self.sentinelsatapi.query.assert_called_with(
            producttype='OCN',
            limit=10, **{
                'date': ('20180101', '20180102')
            }
        )

    def test_core_sentinelsat_download(self):
        """"""
