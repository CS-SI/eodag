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

import glob
import os
import shutil
import unittest

from tests import TEST_RESOURCES_PATH
from tests.context import EODataAccessGateway, UnsupportedProvider, makedirs
from tests.utils import mock


class TestCore(unittest.TestCase):
    SUPPORTED_PRODUCT_TYPES = {
        "L8_REFLECTANCE": ["theia"],
        "L57_REFLECTANCE": ["theia"],
        "L5_L1T": [],
        "L5_L1G": [],
        "L5_L1GT": [],
        "L7_L1G": [],
        "L7_L1T": [],
        "L7_L1GT": [],
        "L8_OLI_TIRS_C1L1": ["onda", "usgs"],
        "S1_SAR_GRD": ["peps", "sobloo", "onda", "wekeo", "mundi", "creodias"],
        "S1_SAR_OCN": ["peps", "sobloo", "onda", "creodias"],
        "S1_SAR_RAW": ["sobloo", "onda", "creodias"],
        "S1_SAR_SLC": ["peps", "sobloo", "onda", "wekeo", "mundi", "creodias"],
        "S2_MSI_L2A": ["theia", "onda", "mundi", "creodias", "peps"],
        "S2_MSI_L1C": [
            "aws_s3_sentinel2_l1c",
            "peps",
            "sobloo",
            "onda",
            "wekeo",
            "mundi",
            "creodias",
        ],
        "S3_ERR": ["peps", "onda", "wekeo", "creodias"],
        "S3_EFR": ["peps", "onda", "wekeo", "creodias"],
        "S3_LAN": ["peps", "sobloo", "onda", "wekeo", "creodias"],
        "S3_SRA": ["sobloo", "onda", "wekeo", "creodias"],
        "S3_SRA_BS": ["sobloo", "onda", "wekeo", "creodias"],
        "S3_SRA_A_BS": ["sobloo", "onda", "creodias"],
        "S3_WAT": ["onda", "wekeo", "creodias"],
        "S3_OLCI_L2LFR": ["peps", "onda", "wekeo", "creodias", "mundi"],
        "S3_OLCI_L2LRR": ["peps", "onda", "wekeo", "creodias"],
        "S3_SLSTR_L1RBT": ["peps", "onda", "wekeo", "creodias"],
        "S3_SLSTR_L2LST": ["peps", "onda", "wekeo", "creodias"],
        "PLD_PAN": ["theia"],
        "PLD_XS": ["theia"],
        "PLD_BUNDLE": ["theia"],
        "PLD_PANSHARPENED": ["theia"],
        "ES_FRS": [],
    }
    SUPPORTED_PROVIDERS = [
        "peps",
        "aws_s3_sentinel2_l1c",
        "usgs",
        "theia",
        "sobloo",
        "creodias",
        "mundi",
        "onda",
        "wekeo",
    ]

    def setUp(self):
        super(TestCore, self).setUp()
        self.dag = EODataAccessGateway()

    def tearDown(self):
        super(TestCore, self).tearDown()
        for old in glob.glob1(self.dag.conf_dir, "*.old") + glob.glob1(
            self.dag.conf_dir, ".*.old"
        ):
            old_path = os.path.join(self.dag.conf_dir, old)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    shutil.rmtree(old_path)
        if os.getenv("EODAG_CFG_FILE") is not None:
            os.environ.pop("EODAG_CFG_FILE")

    def test_supported_providers_in_unit_test(self):
        """Every provider must be referenced in the core unittest SUPPORTED_PROVIDERS class attribute"""  # noqa
        for provider in self.dag.available_providers():
            self.assertIn(provider, self.SUPPORTED_PROVIDERS)

    def test_supported_product_types_in_unit_test(self):
        """Every product type must be referenced in the core unit test SUPPORTED_PRODUCT_TYPES class attribute"""  # noqa
        for product_type in self.dag.list_product_types():
            self.assertIn(product_type["ID"], self.SUPPORTED_PRODUCT_TYPES.keys())

    def test_list_product_types_ok(self):
        """Core api must correctly return the list of supported product types"""
        product_types = self.dag.list_product_types()
        self.assertIsInstance(product_types, list)
        for product_type in product_types:
            self.assertListProductTypesRightStructure(product_type)
        # There should be no repeated product type in the output
        self.assertEqual(len(product_types), len(set(pt["ID"] for pt in product_types)))

    def test_list_product_types_for_provider_ok(self):
        """Core api must correctly return the list of supported product types for a given provider"""  # noqa
        for provider in self.SUPPORTED_PROVIDERS:
            product_types = self.dag.list_product_types(provider=provider)
            self.assertIsInstance(product_types, list)
            for product_type in product_types:
                self.assertListProductTypesRightStructure(product_type)
                self.assertIn(
                    provider, self.SUPPORTED_PRODUCT_TYPES[product_type["ID"]]
                )

    def test_list_product_types_for_unsupported_provider(self):
        """Core api must raise UnsupportedProvider error for list_product_types with unsupported provider"""  # noqa
        unsupported_provider = "a"
        self.assertRaises(
            UnsupportedProvider,
            self.dag.list_product_types,
            provider=unsupported_provider,
        )

    def assertListProductTypesRightStructure(self, structure):
        """Helper method to verify that the structure given is a good result of
        EODataAccessGateway.list_product_types
        """
        self.assertIsInstance(structure, dict)
        self.assertIn("ID", structure)
        self.assertIn("abstract", structure)
        self.assertIn("instrument", structure)
        self.assertIn("platform", structure)
        self.assertIn("platformSerialIdentifier", structure)
        self.assertIn("processingLevel", structure)
        self.assertIn("sensorType", structure)
        self.assertIn(structure["ID"], self.SUPPORTED_PRODUCT_TYPES)

    def test_core_object_creates_config_standard_location(self):
        """The core object must create a user config file in standard user config location on instantiation"""  # noqa
        self.execution_involving_conf_dir(inspect="eodag.yml")

    def test_core_object_creates_index_if_not_exist(self):
        """The core object must create an index in user config directory"""
        self.execution_involving_conf_dir(inspect=".index")

    @mock.patch("eodag.api.core.open_dir", autospec=True)
    @mock.patch("eodag.api.core.exists_in", autospec=True, return_value=True)
    def test_core_object_open_index_if_exists(self, exists_in_mock, open_dir_mock):
        """The core object must use the existing index dir if any"""
        conf_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
        index_dir = os.path.join(conf_dir, ".index")
        if not os.path.exists(index_dir):
            makedirs(index_dir)
        EODataAccessGateway()
        open_dir_mock.assert_called_with(index_dir)

    def test_core_object_prioritize_config_file_in_envvar(self):
        """The core object must use the config file pointed to by the EODAG_CFG_FILE env var"""  # noqa
        os.environ["EODAG_CFG_FILE"] = os.path.join(
            TEST_RESOURCES_PATH, "file_config_override.yml"
        )
        dag = EODataAccessGateway()
        # usgs priority is set to 5 in the test config overrides
        self.assertEqual(dag.get_preferred_provider(), ("usgs", 5))
        # peps outputs prefix is set to /data
        self.assertEqual(dag.providers_config["peps"].download.outputs_prefix, "/data")

    def execution_involving_conf_dir(self, inspect=None):
        if inspect is not None:
            conf_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
            old = current = os.path.join(conf_dir, inspect)
            if os.path.exists(current):
                old = os.path.join(conf_dir, "{}.old".format(inspect))
                shutil.move(current, old)
            EODataAccessGateway()
            self.assertTrue(os.path.exists(current))
            if old != current:
                try:
                    shutil.rmtree(current)
                except OSError:
                    os.unlink(current)
                shutil.move(old, current)
