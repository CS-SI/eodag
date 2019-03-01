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

import functools
import json
import unittest

import geojson

from tests.context import ValidationError, _get_date, eodag_http_server, DEFAULT_ITEMS_PER_PAGE


class RequestTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tested_product_type = 'S2_MSI_L1C'

    def setUp(self):
        self.app = eodag_http_server.app.test_client()

    def test_route(self):
        response = self.app.get('/', follow_redirects=True)
        self.assertEquals(200, response.status_code)

        response = self.app.get('{}'.format(self.tested_product_type), follow_redirects=True)
        self.assertEquals(200, response.status_code)

    def _request_valid(self, url):
        # Limit the results to 2
        from ..context import eodag_api
        old_search = eodag_api.search
        eodag_api.search = functools.partial(eodag_api.search, max_results=2)
        response = self.app.get(url, follow_redirects=True)
        self.assertEquals(200, response.status_code)
        # Restore authentic search method
        eodag_api.search = old_search
        # Assert response format is GeoJSON
        return geojson.loads(response.data)

    def _request_not_valid(self, url):
        response = self.app.get(url, follow_redirects=True)
        response_content = json.loads(response.data)

        self.assertEquals(400, response.status_code)
        self.assertIn('error', response_content)
        self.assertIn('invalid', response_content['error'])

    def _request_not_found(self, url):
        response = self.app.get(url, follow_redirects=True)
        response_content = json.loads(response.data)

        self.assertEquals(404, response.status_code)
        self.assertIn('error', response_content)
        self.assertIn('Not Found', response_content['error'])

    def test_request_params(self):
        self._request_not_valid('{}?box=1'.format(self.tested_product_type))
        self._request_not_valid('{}?box=0,43,1'.format(self.tested_product_type))
        self._request_not_valid('{}?box=0,,1'.format(self.tested_product_type))
        self._request_not_valid('{}?box=a,43,1,44'.format(self.tested_product_type))

        self._request_valid('{}'.format(self.tested_product_type))
        self._request_valid('{}?box=0,43,1,44'.format(self.tested_product_type))

    def test_not_found(self):
        """A request to eodag server with a not supported product type must return a 404 HTTP error code"""
        self._request_not_found('/ZZZ/?box=0,43,1,44')

    def test_filter(self):
        result1 = self._request_valid('{}?box=0,43,1,44'.format(self.tested_product_type))
        result2 = self._request_valid('{}?box=0,43,1,44&filter=latestIntersect'.format(self.tested_product_type))
        self.assertGreaterEqual(len(result1.features), len(result2.features))

    def test_get_date(self):
        """Date validation function must correctly validate dates"""
        _get_date('2018-01-01')
        _get_date('2018-01-01T')
        _get_date('2018-01-01T00:00')
        _get_date('2018-01-01T00:00:00')
        _get_date('2018-01-01T00:00:00Z')
        _get_date('20180101')

        self.assertRaises(ValidationError, _get_date, 'foo')
        self.assertRaises(ValidationError, _get_date, 'foo2018-01-01')

        self.assertIsNone(_get_date(None))

    def test_date_search(self):
        result1 = self._request_valid('{}?box=0,43,1,44'.format(self.tested_product_type))
        result2 = self._request_valid(
            '{}?box=0,43,1,44&dtstart=2018-01-20&dtend=2018-01-25'.format(self.tested_product_type))
        self.assertGreaterEqual(len(result1.features), len(result2.features))

    def test_cloud_cover_search(self):
        result1 = self._request_valid('{}?box=0,43,1,44'.format(self.tested_product_type))
        result2 = self._request_valid('{}?box=0,43,1,44&cloudCover=10'.format(self.tested_product_type))
        self.assertGreaterEqual(len(result1.features), len(result2.features))

    def test_search_response_contains_pagination_info(self):
        """Responses to valid search requests must return a geojson with pagination info in properties"""
        response = self._request_valid('{}'.format(self.tested_product_type))
        self.assertIn('properties', response)
        self.assertEqual(1, response['properties']['page'])
        self.assertEqual(DEFAULT_ITEMS_PER_PAGE, response['properties']['itemsPerPage'])
        self.assertIn('totalResults', response['properties'])
