# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, http://www.c-s.fr
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

import unittest

from eodag.api.product import EOProduct
from eodag.api.product.drivers import DatasetDriver


class TestEOProductDriverBase(unittest.TestCase):
    def test_driver_s2_init(self):
        """Driver base is an abstract"""
        try:
            DatasetDriver.match(
                EOProduct(
                    "fake_provider",
                    {"id": "9deb7e78-9341-5530-8fe8-f81fd99c9f0f"},
                    collection="fake_collection",
                )
            )
            self.fail("Abstract methods are not callable from abstract class")
        except NotImplementedError:
            pass
        except Exception as e:
            self.fail("Unexpected exception: {}".format(str(e)))
