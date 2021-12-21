# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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

import builtins
import sys
import unittest
from contextlib import closing
from datetime import datetime
from io import StringIO
from unittest.mock import patch

from tests.context import (
    DownloadedCallback,
    ProgressCallback,
    ask_confirmation,
    get_timestamp,
    merge_mappings,
    path_to_uri,
    setup_logging,
    uri_to_path,
)


class TestUtils(unittest.TestCase):
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
        else:
            expected_path = "/tmp/file.txt"
            tested_uri = "file:///tmp/file.txt"
        actual_path = uri_to_path(tested_uri)
        self.assertEqual(actual_path, expected_path)
        with self.assertRaises(ValueError):
            uri_to_path("not_a_uri")

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

    def test_ask_confirmation_answer_y(self):
        """The method :meth:`~eodag.utils.cli.ask_confirmation` returns True if input is 'y'"""
        with patch.object(builtins, "input", lambda _: "y"):
            confirm = ask_confirmation("test ?")
        self.assertTrue(confirm)

    def test_ask_confirmation_answer_n(self):
        """The method :meth:`~eodag.utils.cli.ask_confirmation` returns False if input is 'n'"""
        with patch.object(builtins, "input", lambda _: "n"):
            confirm = ask_confirmation("test ?")
        self.assertFalse(confirm)

    def test_ask_confirmation_answer_something_else(self):
        """The method :meth:`~eodag.utils.cli.ask_confirmation` returns False if input response is neither 'y'/'n'"""
        with patch.object(builtins, "input", lambda _: "something else"):
            confirm = ask_confirmation("test ?")
        self.assertFalse(confirm)

    def test_ask_confirmation_no_answer(self):
        """The method :meth:`~eodag.utils.cli.ask_confirmation` returns False if input response is empty"""
        with patch.object(builtins, "input", lambda _: ""):
            confirm = ask_confirmation("test ?")
        self.assertFalse(confirm)
