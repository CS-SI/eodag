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

import glob
import os
import shutil
import tempfile
import unittest
from unittest import mock

from eodag import EODataAccessGateway
from eodag.utils import makedirs


class TestCoreInvolvingConfDir(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dag = EODataAccessGateway()
        # mock os.environ to empty env
        cls.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        cls.mock_os_environ.start()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # stop os.environ
        cls.mock_os_environ.stop()

    def setUp(self):
        super().setUp()
        self.dag = EODataAccessGateway()

    def tearDown(self):
        super().tearDown()
        for old_path in glob.glob(os.path.join(self.dag.conf_dir, "*.old")) + glob.glob(
            os.path.join(self.dag.conf_dir, ".*.old")
        ):
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    shutil.rmtree(old_path)

    def execution_involving_conf_dir(self, inspect=None, conf_dir=None):
        """Check that the path(s) inspected (str, list) are created after the instantation
        of EODataAccessGateway. If they were already there, rename them (.old), instantiate,
        check, delete the new files, and restore the existing files to there previous name.
        """
        if inspect is not None:
            if conf_dir is None:
                conf_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
            if isinstance(inspect, str):
                inspect = [inspect]
            olds = []
            currents = []
            for inspected in inspect:
                old = current = os.path.join(conf_dir, inspected)
                if os.path.exists(current):
                    old = os.path.join(conf_dir, "{}.old".format(inspected))
                    shutil.move(current, old)
                olds.append(old)
                currents.append(current)
            EODataAccessGateway()
            for old, current in zip(olds, currents):
                self.assertTrue(os.path.exists(current))
                if old != current:
                    try:
                        shutil.rmtree(current)
                    except OSError:
                        os.unlink(current)
                    shutil.move(old, current)

    def test_core_object_creates_config_standard_location(self):
        """The core object must create a user config file in standard user config location on instantiation"""
        self.execution_involving_conf_dir(inspect="eodag.yml")

    def test_core_object_creates_locations_standard_location(self):
        """The core object must create a locations config file and a shp dir in standard user config location on instantiation"""  # noqa
        self.execution_involving_conf_dir(inspect=["locations.yml", "shp"])

    def test_read_only_home_dir(self):
        # standard directory
        home_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
        self.execution_involving_conf_dir(inspect="eodag.yml", conf_dir=home_dir)

        # user defined directory
        user_dir = os.path.join(os.path.expanduser("~"), ".config", "another_eodag")
        os.environ["EODAG_CFG_DIR"] = user_dir
        self.execution_involving_conf_dir(inspect="eodag.yml", conf_dir=user_dir)
        shutil.rmtree(user_dir)
        del os.environ["EODAG_CFG_DIR"]

        # fallback temporary folder
        def makedirs_side_effect(dir):
            if dir == os.path.join(os.path.expanduser("~"), ".config", "eodag"):
                raise OSError("Mock makedirs error")
            else:
                return makedirs(dir)

        with mock.patch(
            "eodag.api.core.makedirs", side_effect=makedirs_side_effect
        ) as mock_makedirs:
            # backup temp_dir if exists
            temp_dir = temp_dir_old = os.path.join(
                tempfile.gettempdir(), ".config", "eodag"
            )
            if os.path.exists(temp_dir):
                temp_dir_old = f"{temp_dir}.old"
                shutil.move(temp_dir, temp_dir_old)

            EODataAccessGateway()
            expected = [unittest.mock.call(home_dir), unittest.mock.call(temp_dir)]
            mock_makedirs.assert_has_calls(expected)
            self.assertTrue(os.path.exists(temp_dir))

            # restore temp_dir
            if temp_dir_old != temp_dir:
                try:
                    shutil.rmtree(temp_dir)
                except OSError:
                    os.unlink(temp_dir)
                shutil.move(temp_dir_old, temp_dir)
