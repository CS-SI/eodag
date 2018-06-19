# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import hashlib
import os
import shutil
import tempfile
import unittest
import zipfile

import requests

from tests import TEST_RESOURCES_PATH
from tests.context import EOProduct, SatImagesAPI, SearchResult


try:
    from unittest import mock  # PY3
except ImportError:
    import mock  # PY2


class TestIntegrationCoreDownloadPlugins(unittest.TestCase):

    def test_core_http_download_local_product(self):
        """A local product must not be downloaded and the download plugin must return its local absolute path"""
        self.product.location = 'file:///absolute/path/to/local/product.zip'
        paths = self.eodag.download_all(SearchResult([self.product]))
        self.assertEqual(paths[0], '/absolute/path/to/local/product.zip')
        self.assertHttpDownloadNotDone()

    def test_core_http_download_remote_product_no_extract(self):
        """A remote product must be downloaded as is if extraction config is set to False"""
        self.eodag.providers_config[self.test_provider]['download']['extract'] = False
        self.product.location = '{base}/path/to/product.zip'
        self.requests_get.return_value = self._requests_get_response()

        paths = self.eodag.download_all(SearchResult([self.product]))
        self.assertHttpDownloadDone(paths[0])

    def test_core_http_download_remote_product_extract(self):
        """A remote product must be downloaded and extracted as is if extraction config is set to True (by default)"""
        self.eodag.providers_config[self.test_provider]['download']['extract'] = True
        self.product.location = '{base}/path/to/product.zip'
        self.requests_get.return_value = self._requests_get_response()

        paths = self.eodag.download_all(SearchResult([self.product]))
        self.assertHttpDownloadDone(paths[0], with_extraction=True)

    def test_core_http_download_remote_no_url(self):
        """Download must fail on an EOProduct with no download url"""
        paths = self.eodag.download_all(SearchResult([self.product]))
        self.assertEqual(len(paths), 1)
        self.assertIsNone(paths[0])
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
        self.assertEqual(self.requests_get.call_count, 1)
        self.assertFalse(os.path.exists(self.expected_record_file))

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
        self.assertEqual('file://{}'.format(path), self.product.location)
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
