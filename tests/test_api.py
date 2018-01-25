# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import unittest

from .context import api


class TestGeoProductsDownloaderApi(unittest.TestCase):
    def setUp(self):
        self.gpda = api.GeoProductsDownloaderApi()

    def test_get_searcher_ok(self):
        assert True

    def test_get_interface_query_params_ok(self):
        assert True

    def test_search(self):
        assert True