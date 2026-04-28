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

from unittest import mock  # PY3

from .eodagtestbase import EODagTestBase


class EODagTestCase(EODagTestBase):
    """Extended base test case that additionally patches requests.get."""

    def setUp(self):
        super().setUp()
        self.requests_http_get_patcher = mock.patch("requests.get", autospec=True)
        self.requests_http_get = self.requests_http_get_patcher.start()

    def tearDown(self):
        self.requests_http_get_patcher.stop()
        super().tearDown()

    def assertHttpGetCalledOnceWith(self, expected_url, expected_params=None):
        """Helper method for doing assertions on requests http get method mock"""
        self.assertEqual(self.requests_http_get.call_count, 1)
        actual_url = self.requests_http_get.call_args[0][0]
        self.assertEqual(actual_url, expected_url)
        if expected_params:
            actual_params = self.requests_http_get.call_args[1]["params"]
            self.assertDictEqual(actual_params, expected_params)


__all__ = ["EODagTestCase"]
