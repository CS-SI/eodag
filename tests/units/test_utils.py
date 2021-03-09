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
from datetime import datetime

from tests.context import get_timestamp


class TestUtils(unittest.TestCase):
    def test_utils_get_timestamp(self):
        """get_timestamp must handle UTC dates"""
        requested_date = "2020-08-08"
        date_format = "%Y-%m-%d"
        # If as_utc is False, get_timestamp takes into account the
        # local timezone (because of datetime.timestamp)
        ts_in_secs = get_timestamp(requested_date, date_format=date_format, as_utc=True)
        expected_dt = datetime.strptime(requested_date, date_format)
        actual_utc_dt = datetime.utcfromtimestamp(ts_in_secs)
        self.assertEqual(actual_utc_dt, expected_dt)
