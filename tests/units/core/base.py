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

import logging
import os
import unittest
from tempfile import TemporaryDirectory
from unittest import mock

from tests.utils import write_eodag_conf_with_fake_credentials


class TestCoreBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Mock home and eodag conf directory to tmp dir
        cls.tmp_home_dir = TemporaryDirectory()
        cls.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=cls.tmp_home_dir.name
        )
        cls.expanduser_mock.start()

        # create eodag conf dir in tmp home dir
        eodag_conf_dir = os.path.join(cls.tmp_home_dir.name, ".config", "eodag")
        os.makedirs(eodag_conf_dir, exist_ok=False)
        # use empty config file with fake credentials in order to have full
        # list for tests and prevent providers to be pruned
        write_eodag_conf_with_fake_credentials(
            os.path.join(eodag_conf_dir, "eodag.yml")
        )

    @classmethod
    def tearDownClass(cls):
        super(TestCoreBase, cls).tearDownClass()
        # stop Mock and remove tmp config dir
        cls.expanduser_mock.stop()
        cls.tmp_home_dir.cleanup()
        # reset logging
        logger = logging.getLogger("eodag")
        logger.handlers = []
        logger.level = 0


__all__ = ["TestCoreBase"]
