# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, http://www.c-s.fr
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
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

import yaml

from tests.context import TEST_RESOURCES_PATH, AwsDownload, EOProduct, NotAvailableError


class TestSafeBuild(unittest.TestCase):
    def setUp(self):
        super(TestSafeBuild, self).setUp()

        self.awsd = AwsDownload("some_provider", {})
        self.logger = logging.getLogger("eodag.download.aws")

        self.tmp_download_dir = TemporaryDirectory()
        self.tmp_download_path = self.tmp_download_dir.name

        with open(
            os.path.join(TEST_RESOURCES_PATH, "safe_build", "aws_sentinel_chunks.yml"),
            "r",
        ) as fh:
            self.aws_sentinel_chunks = yaml.load(fh, Loader=yaml.SafeLoader)

    def tearDown(self):
        self.tmp_download_dir.cleanup()

    def test_safe_build_out_of_pattern(self):
        """Cannot build SAFE product from out of pattern file"""
        prod = EOProduct(
            provider="some_provider",
            properties=self.aws_sentinel_chunks["S1_SAR_GRD"]["properties"],
            productType="S1_SAR_GRD",
        )

        def chunk():
            return None

        chunk.key = "path/to/some/dummy_chunk"

        with self.assertRaisesRegex(
            NotAvailableError, f"Ignored {chunk.key} out of SAFE matching pattern"
        ):
            self.awsd.get_chunk_dest_path(
                prod,
                chunk,
                build_safe=True,
            )

    def test_safe_build_no_safe(self):
        """Do not use patterns if no SAFE is asked"""
        prod = EOProduct(
            provider="some_provider",
            properties=self.aws_sentinel_chunks["S1_SAR_GRD"]["properties"],
            productType="S1_SAR_GRD",
        )

        def chunk():
            return None

        chunk.key = "path/to/some/dummy_chunk"
        chunk_dest_path = self.awsd.get_chunk_dest_path(
            prod,
            chunk,
            build_safe=False,
        )
        self.assertEqual(chunk_dest_path, chunk.key)

        chunk_dest_path = self.awsd.get_chunk_dest_path(
            prod, chunk, build_safe=False, dir_prefix="path/to"
        )
        self.assertEqual(chunk_dest_path, "some/dummy_chunk")

    def test_safe_build_s1_sar_grd(self):
        """build S1_SAR_GRD SAFE product with empty files and check content"""

        prod = EOProduct(
            provider="some_provider",
            properties=self.aws_sentinel_chunks["S1_SAR_GRD"]["properties"],
            productType="S1_SAR_GRD",
        )

        product_path = os.path.join(self.tmp_download_path, prod.properties["title"])

        def chunk():
            return None

        for chunk_key in self.aws_sentinel_chunks["S1_SAR_GRD"]["chunks"]:
            chunk.key = chunk_key
            chunk_dest_rel_path = self.awsd.get_chunk_dest_path(
                prod,
                chunk,
                build_safe=True,
            )

            chunk_abs_path = os.path.join(product_path, chunk_dest_rel_path)
            chunk_abs_path_dir = os.path.dirname(chunk_abs_path)
            if not os.path.isdir(chunk_abs_path_dir):
                os.makedirs(chunk_abs_path_dir)

            Path(chunk_abs_path).touch()

        copyfile(
            os.path.join(TEST_RESOURCES_PATH, "safe_build", "manifest.safe.S1_SAR_GRD"),
            os.path.join(product_path, "manifest.safe"),
        )

        with self.assertLogs(self.logger, logging.WARN) as cm:
            # assertLogs fails if no warning is raised
            self.logger.warning("Dummy warning")
            self.awsd.check_manifest_file_list(product_path)

        self.assertEqual(len(cm.output), 1)
        self.assertIn("Dummy warning", cm.output[0])

    def test_safe_build_s2_msi_l2a(self):
        """build S2_MSI_L2A SAFE product with empty files and check content"""

        prod = EOProduct(
            provider="some_provider",
            properties=self.aws_sentinel_chunks["S2_MSI_L2A"]["properties"],
            productType="S2_MSI_L2A",
        )

        product_path = os.path.join(self.tmp_download_path, prod.properties["title"])

        def chunk():
            return None

        for chunk_key in self.aws_sentinel_chunks["S2_MSI_L2A"]["chunks"]:
            chunk.key = chunk_key
            chunk_dest_rel_path = self.awsd.get_chunk_dest_path(
                prod,
                chunk,
                build_safe=True,
            )

            chunk_abs_path = os.path.join(product_path, chunk_dest_rel_path)
            chunk_abs_path_dir = os.path.dirname(chunk_abs_path)
            if not os.path.isdir(chunk_abs_path_dir):
                os.makedirs(chunk_abs_path_dir)

            Path(chunk_abs_path).touch()

        copyfile(
            os.path.join(TEST_RESOURCES_PATH, "safe_build", "manifest.safe.S2_MSI_L2A"),
            os.path.join(product_path, "manifest.safe"),
        )

        self.awsd.finalize_s2_safe_product(product_path)

        with self.assertLogs(self.logger, logging.WARN) as cm:
            # assertLogs fails if no warning is raised
            self.logger.warning("Dummy warning")
            self.awsd.check_manifest_file_list(product_path)

        self.assertEqual(len(cm.output), 1)
        self.assertIn("Dummy warning", cm.output[0])

    def test_safe_build_s2_msi_l1c(self):
        """build S2_MSI_L1C SAFE product with empty files and check content"""

        prod = EOProduct(
            provider="some_provider",
            properties=self.aws_sentinel_chunks["S2_MSI_L1C"]["properties"],
            productType="S2_MSI_L1C",
        )

        product_path = os.path.join(self.tmp_download_path, prod.properties["title"])

        def chunk():
            return None

        for chunk_key in self.aws_sentinel_chunks["S2_MSI_L1C"]["chunks"]:
            chunk.key = chunk_key
            chunk_dest_rel_path = self.awsd.get_chunk_dest_path(
                prod,
                chunk,
                build_safe=True,
            )

            chunk_abs_path = os.path.join(product_path, chunk_dest_rel_path)
            chunk_abs_path_dir = os.path.dirname(chunk_abs_path)
            if not os.path.isdir(chunk_abs_path_dir):
                os.makedirs(chunk_abs_path_dir)

            Path(chunk_abs_path).touch()

        copyfile(
            os.path.join(TEST_RESOURCES_PATH, "safe_build", "manifest.safe.S2_MSI_L1C"),
            os.path.join(product_path, "manifest.safe"),
        )

        self.awsd.finalize_s2_safe_product(product_path)

        with self.assertLogs(self.logger, logging.WARN) as cm:
            # assertLogs fails if no warning is raised
            self.logger.warning("Dummy warning")
            self.awsd.check_manifest_file_list(product_path)

        self.assertEqual(len(cm.output), 2)
        self.assertIn("Dummy warning", cm.output[0])
        # known missing file, see https://github.com/CS-SI/eodag/pull/218#issuecomment-816770353
        self.assertIn("PVI.jp2 is missing", cm.output[1])
