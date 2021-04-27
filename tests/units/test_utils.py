# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, https://www.csgroup.eu/
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

import sys
import unittest
from datetime import datetime

from tests.context import get_timestamp, path_to_uri, uri_to_path


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
