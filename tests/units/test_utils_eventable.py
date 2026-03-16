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

from eodag.utils.eventable import Eventable


class TestUtilsEventable(unittest.TestCase):
    def test_utils_eventable(self):

        event_counter: dict = {
            "event_a": 0,
            "event_a_args": [],
            "event_b": 0,
            "event_b_args": [],
            "event_c": 0,
            "event_c_args": [],
        }

        ev = Eventable()

        def handler_event_a(*args):
            event_counter["event_a"] += 1
            event_counter["event_a_args"].append(args)

        def handler_event_b(*args):
            event_counter["event_b"] += 1
            event_counter["event_b_args"].append(args)

        def handler_event_c1(*args):
            event_counter["event_c"] += 1
            event_counter["event_c_args"].append(args)

        def handler_event_c2(*args):
            event_counter["event_c"] += 1
            event_counter["event_c_args"].append(args)

        def handler_event_c3(*args):
            event_counter["event_c"] += 1
            event_counter["event_c_args"].append(args)

        ev.fire("event_a", 14)
        ev.on("event_a", handler_event_a)
        ev.fire("event_a", 15)
        ev.off("event_a")
        ev.fire("event_a", 16)

        ev.on("event_b", handler_event_b)
        ev.on("event_b", handler_event_b)  # not cumulate same handler reference
        ev.on("event_b", handler_event_b)
        ev.fire("event_b", 17)
        ev.off("event_b")
        ev.fire("event_b", 18)

        ev.on("event_c", handler_event_c1)
        ev.on("event_c", handler_event_c2)
        ev.on("event_c", handler_event_c3)
        ev.fire("event_c", 19)
        ev.off("event_c")
        ev.fire("event_c", 20)

        self.assertEqual(event_counter["event_a"], 1)
        self.assertEqual(event_counter["event_a_args"][0][0], 15)
        self.assertEqual(event_counter["event_b"], 1)
        self.assertEqual(event_counter["event_b_args"][0][0], 17)
        self.assertEqual(event_counter["event_c"], 3)
        self.assertEqual(event_counter["event_c_args"][0][0], 19)
        self.assertEqual(event_counter["event_c_args"][1][0], 19)
        self.assertEqual(event_counter["event_c_args"][2][0], 19)
