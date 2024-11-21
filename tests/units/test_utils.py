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

import copy
import logging
import os
import ssl
import sys
import unittest
from contextlib import closing
from datetime import datetime
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from requests.exceptions import RequestException

from tests.context import (
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    DownloadedCallback,
    ProgressCallback,
    RequestError,
    deepcopy,
    fetch_json,
    flatten_top_directories,
    get_bucket_name_and_prefix,
    get_ssl_context,
    get_timestamp,
    merge_mappings,
    path_to_uri,
    setup_logging,
    uri_to_path,
)


class TestUtils(unittest.TestCase):
    def setUp(self) -> None:
        super(TestUtils, self).setUp()
        setup_logging(verbose=1)

    def tearDown(self) -> None:
        super(TestUtils, self).tearDown()
        # reset logging
        logger = logging.getLogger("eodag")
        logger.handlers = []
        logger.level = 0

    def test_utils_get_timestamp(self):
        """get_timestamp must return a UNIX timestamp"""
        # Date to timestamp to date, this assumes the date is in UTC
        requested_date = "2020-08-08"  # Considered as 2020-08-08T00:00:00Z
        ts_in_secs = get_timestamp(requested_date)
        expected_dt = datetime.strptime(requested_date, "%Y-%m-%d")
        actual_utc_dt = datetime.utcfromtimestamp(ts_in_secs)
        self.assertEqual(actual_utc_dt, expected_dt)

        # Handle UTC datetime
        self.assertEqual(get_timestamp("2021-04-21T18:27:19.123Z"), 1619029639.123)
        # If date/datetime not in UTC, it assumes it's in UTC
        self.assertEqual(
            get_timestamp("2021-04-21T18:27:19.123"),
            get_timestamp("2021-04-21T18:27:19.123Z"),
        )
        self.assertEqual(
            get_timestamp("2021-04-21"), get_timestamp("2021-04-21T00:00:00.000Z")
        )

        # Non UTC datetime are also supported
        self.assertEqual(get_timestamp("2021-04-21T00:00:00+02:00"), 1618956000)

    def test_uri_to_path(self):
        if sys.platform == "win32":
            expected_path = r"C:\tmp\file.txt"
            tested_uri = r"file:///C:/tmp/file.txt"
            other_tested_uri = r"file:/C:/tmp/file.txt"
        else:
            expected_path = "/tmp/file.txt"
            tested_uri = "file:///tmp/file.txt"
            other_tested_uri = "file:/tmp/file.txt"
        actual_path = uri_to_path(tested_uri)
        self.assertEqual(actual_path, expected_path)
        actual_path = uri_to_path(other_tested_uri)
        self.assertEqual(actual_path, expected_path)
        with self.assertRaises(ValueError):
            uri_to_path("not_a_uri")

    def test_ssl_context(self):

        ssl_ctx = get_ssl_context(False)
        self.assertEqual(ssl_ctx.verify_mode, ssl.CERT_NONE)
        self.assertEqual(ssl_ctx.check_hostname, False)

        ssl_ctx = get_ssl_context(True)
        self.assertEqual(ssl_ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(ssl_ctx.check_hostname, True)

    def test_path_to_uri(self):
        if sys.platform == "win32":
            self.assertEqual(path_to_uri(r"C:\tmp\file.txt"), "file:///C:/tmp/file.txt")
        else:
            self.assertEqual(path_to_uri("/tmp/file.txt"), "file:///tmp/file.txt")

    def test_downloaded_callback(self):
        """DownloadedCallback instance is callable with product as parameter"""
        downloaded_callback = DownloadedCallback()
        self.assertTrue(callable(downloaded_callback))
        try:
            downloaded_callback(product=None)
        except TypeError as e:
            self.fail(f"DownloadedCallback got an error when called: {e}")

    def test_progresscallback_init(self):
        """ProgressCallback can be instantiated using defaults values"""
        with ProgressCallback() as bar:
            self.assertEqual(bar.unit, "B")
            self.assertEqual(bar.unit_scale, True)
            self.assertEqual(bar.desc, "")

    def test_progresscallback_init_customize(self):
        """ProgressCallback can be instantiated using custom values"""
        with ProgressCallback(unit="foo", unit_scale=False, desc="bar", total=5) as bar:
            self.assertEqual(bar.unit, "foo")
            self.assertEqual(bar.unit_scale, False)
            self.assertEqual(bar.desc, "bar")
            self.assertEqual(bar.total, 5)

    def test_progresscallback_copy(self):
        """ProgressCallback can be copied"""
        with ProgressCallback(unit="foo", unit_scale=False, desc="bar", total=5) as bar:
            with bar.copy() as another_bar:
                self.assertEqual(another_bar.unit, "foo")
                self.assertEqual(another_bar.unit_scale, False)
                self.assertEqual(another_bar.desc, "bar")
                self.assertEqual(another_bar.total, 5)

    def test_progresscallback_disable(self):
        """ProgressCallback can be disabled"""
        # enabled
        with closing(StringIO()) as tqdm_out:
            with ProgressCallback(total=2, file=tqdm_out) as bar:
                bar(1)
            self.assertIn("50%", tqdm_out.getvalue())

        # disabled using setup_logging
        setup_logging(verbose=1, no_progress_bar=True)
        with closing(StringIO()) as tqdm_out:
            with ProgressCallback(total=2, file=tqdm_out) as bar:
                bar(1)
            self.assertEqual(tqdm_out.getvalue(), "")
        setup_logging(verbose=1, no_progress_bar=False)

        # disabled using tqdm parameter
        with closing(StringIO()) as tqdm_out:
            with ProgressCallback(total=2, file=tqdm_out, disable=True) as bar:
                bar(1)
            self.assertEqual(tqdm_out.getvalue(), "")

    def test_merge_mappings(self):
        """Configuration mappings must be merged properly."""

        # nested dict
        mapping = {"foo": {"keyA": "obsolete"}}
        merge_mappings(mapping, {"foo": {"keya": "new"}})
        self.assertEqual(mapping, {"foo": {"keyA": "new"}})

        # list replaced by string
        mapping = {"keyA": ["obsolete1", "obsolete2"]}
        merge_mappings(mapping, {"keya": "new"})
        self.assertEqual(mapping, {"keyA": "new"})

        # string replaced by list
        mapping = {"keyA": "obsolete"}
        merge_mappings(mapping, {"keya": ["new1", "new2"]})
        self.assertEqual(mapping, {"keyA": ["new1", "new2"]})

        # bool replaced by str
        mapping = {"keyA": True}
        merge_mappings(mapping, {"keya": "fAlSe"})
        self.assertEqual(mapping, {"keyA": False})

        # int replaced by str
        mapping = {"keyA": 1}
        merge_mappings(mapping, {"keya": "2"})
        self.assertEqual(mapping, {"keyA": 2})

        # override ignored if cast cannot be perfomed to origin type
        mapping = {"keyA": True}
        merge_mappings(mapping, {"keya": "bar"})
        self.assertEqual(mapping, {"keyA": True})

    def test_get_bucket_name_and_prefix(self):
        """get_bucket_name_and_prefix must extract bucket and prefix from url"""
        self.assertEqual(
            get_bucket_name_and_prefix(
                "s3://sentinel-s2-l1c/tiles/50/R/LR/2021/6/8/0/B02.jp2"
            ),
            ("sentinel-s2-l1c", "tiles/50/R/LR/2021/6/8/0/B02.jp2"),
        )
        self.assertEqual(
            get_bucket_name_and_prefix(
                "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/44/2022/10/S2B_20221011/B01.tif"
            ),
            (
                "sentinel-cogs",
                "sentinel-s2-l2a-cogs/44/2022/10/S2B_20221011/B01.tif",
            ),
        )
        self.assertEqual(
            get_bucket_name_and_prefix(
                "https://obs.eu-de.otc.t-systems.com/s2-l1c-2021-q4/30/T/2021/11/14/S2A_MSIL1C_20211114T110321_N0301",
                0,
            ),
            ("s2-l1c-2021-q4", "30/T/2021/11/14/S2A_MSIL1C_20211114T110321_N0301"),
        )
        self.assertEqual(
            get_bucket_name_and_prefix(
                "products/2021/1/5/S2A_MSIL1C_20210105T105441_N0209_R051_T30TYN_20210105T130129",
            ),
            (
                None,
                "products/2021/1/5/S2A_MSIL1C_20210105T105441_N0209_R051_T30TYN_20210105T130129",
            ),
        )
        self.assertEqual(
            get_bucket_name_and_prefix(
                "bucket/path/to/product",
                0,
            ),
            ("bucket", "path/to/product"),
        )
        self.assertEqual(
            get_bucket_name_and_prefix(
                "http://foo/bar/bucket/path/to/product",
                1,
            ),
            ("bucket", "path/to/product"),
        )

    def test_flatten_top_dirs(self):
        """flatten_top_dirs must flatten directory structure"""
        with TemporaryDirectory() as nested_dir_root:
            os.makedirs(os.path.join(nested_dir_root, "a", "b", "c1"))
            os.makedirs(os.path.join(nested_dir_root, "a", "b", "c2"))
            # create empty files
            open(os.path.join(nested_dir_root, "a", "b", "c1", "foo"), "a").close()
            open(os.path.join(nested_dir_root, "a", "b", "c2", "bar"), "a").close()
            open(os.path.join(nested_dir_root, "a", "b", "c2", "baz"), "a").close()

            flatten_top_directories(nested_dir_root)

            dir_content = list(Path(nested_dir_root).glob("**/*"))

            self.assertEqual(len(dir_content), 5)
            self.assertIn(Path(nested_dir_root) / "c1", dir_content)
            self.assertIn(Path(nested_dir_root) / "c1" / "foo", dir_content)
            self.assertIn(Path(nested_dir_root) / "c2", dir_content)
            self.assertIn(Path(nested_dir_root) / "c2" / "bar", dir_content)
            self.assertIn(Path(nested_dir_root) / "c2" / "baz", dir_content)

    def test_flatten_top_dirs_single_file(self):
        """flatten_top_dirs must flatten directory structure containing a single file"""
        with TemporaryDirectory() as nested_dir_root:
            os.makedirs(os.path.join(nested_dir_root, "a", "b", "c1"))
            # create empty file
            open(os.path.join(nested_dir_root, "a", "b", "c1", "foo"), "a").close()

            flatten_top_directories(nested_dir_root)

            dir_content = list(Path(nested_dir_root).glob("**/*"))

            self.assertEqual(len(dir_content), 1)
            self.assertIn(Path(nested_dir_root) / "foo", dir_content)

    def test_flatten_top_dirs_given_subdir(self):
        """flatten_top_dirs must flatten directory structure using given subdirectory"""
        with TemporaryDirectory() as nested_dir_root:
            os.makedirs(os.path.join(nested_dir_root, "a", "b", "c1"))
            os.makedirs(os.path.join(nested_dir_root, "a", "b", "c2"))
            # create empty files
            open(os.path.join(nested_dir_root, "a", "b", "c1", "foo"), "a").close()
            open(os.path.join(nested_dir_root, "a", "b", "c2", "bar"), "a").close()
            open(os.path.join(nested_dir_root, "a", "b", "c2", "baz"), "a").close()

            flatten_top_directories(nested_dir_root, os.path.join(nested_dir_root, "a"))

            dir_content = list(Path(nested_dir_root).glob("**/*"))

            self.assertEqual(len(dir_content), 6)
            self.assertIn(Path(nested_dir_root) / "b", dir_content)
            self.assertIn(Path(nested_dir_root) / "b" / "c1", dir_content)
            self.assertIn(Path(nested_dir_root) / "b" / "c1" / "foo", dir_content)
            self.assertIn(Path(nested_dir_root) / "b" / "c2", dir_content)
            self.assertIn(Path(nested_dir_root) / "b" / "c2" / "bar", dir_content)
            self.assertIn(Path(nested_dir_root) / "b" / "c2" / "baz", dir_content)

    def test_deepcopy(self):
        """deepcopy must to a recursice copy of the given object"""
        original = {"a": [{"b": [0, 1, 2]}]}
        shallow_copied = copy.copy(original)
        deep_copied = deepcopy(original)
        # change original
        original["a"][0]["b"][0] = 5
        # shallow copy also changed
        self.assertEqual(shallow_copied["a"][0]["b"][0], 5)
        # deep copy did not change
        self.assertEqual(deep_copied["a"][0]["b"][0], 0)

    def test_fetch_json(self):
        """fetch_json must be able to fetch a distant json file"""

        # distant
        file_url = "https://foo.bar"
        with unittest.mock.patch(
            "eodag.utils.requests.requests.get",
            autospec=True,
        ) as mock_get:
            mock_get.return_value = unittest.mock.Mock()
            mock_get.return_value.json.return_value = {"foo": "bar"}
            file_content = fetch_json(file_url)
            self.assertEqual(file_content["foo"], "bar")
            mock_get.assert_called_once_with(
                file_url,
                headers=USER_AGENT,
                auth=None,
                timeout=HTTP_REQ_TIMEOUT,
            )

        # distant error
        with unittest.mock.patch(
            "eodag.utils.requests.requests.get",
            autospec=True,
            side_effect=RequestException,
        ) as mock_get:
            self.assertRaises(RequestError, fetch_json, file_url)
