# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, http://www.c-s.fr
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

from tests.context import format_metadata


class TestMetadataFormatter(unittest.TestCase):
    def test_convert_datetime_to_timestamp_milliseconds(self):
        to_format = "{fieldname#datetime_to_timestamp_milliseconds}"
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T18:27:19.123Z"),
            "1619029639123",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T18:27:19.123"),
            "1619029639123",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21"), "1618963200000"
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T00:00:00+02:00"),
            "1618956000000",
        )

    def test_convert_to_iso_utc_datetime(self):
        to_format = "{fieldname#to_iso_utc_datetime}"
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T18:27:19.123Z"),
            "2021-04-21T18:27:19.123Z",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T18:27:19.123"),
            "2021-04-21T18:27:19.123Z",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21"),
            "2021-04-21T00:00:00.000Z",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T00:00:00.000+02:00"),
            "2021-04-20T22:00:00.000Z",
        )

    def test_convert_to_iso_date(self):
        to_format = "{fieldname#to_iso_date}"
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T18:27:19.123Z"),
            "2021-04-21",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T18:27:19.123"),
            "2021-04-21",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21"), "2021-04-21"
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T00:00:00+06:00"),
            "2021-04-20",
        )

    def test_convert_to_iso_utc_datetime_from_milliseconds(self):
        to_format = "{fieldname#to_iso_utc_datetime_from_milliseconds}"
        self.assertEqual(
            format_metadata(to_format, fieldname=1619029639123),
            "2021-04-21T18:27:19.123Z",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname=1618963200000),
            "2021-04-21T00:00:00.000Z",
        )
