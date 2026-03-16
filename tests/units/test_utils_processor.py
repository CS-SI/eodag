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

import time
import unittest

from eodag.utils import Processor


class TestProcessor(unittest.TestCase):
    """Unit tests for utility functions in eodag.utils."""

    def test_processor(self):

        shared: dict = {"trace": []}

        def routine(index: int, duration: float):
            shared["trace"].append("start {}".format(index))
            time.sleep(1)
            shared["trace"].append("end {}".format(index))
            return index

        def callback(index, error):
            shared["trace"].append("done {}".format(index))

        for index in range(0, 8):
            shared["trace"].append("queue {}".format(index))
            Processor.queue(
                routine,
                index,
                1 + (index % 8) / 10,
                q_parallelize=4,
                q_callback=callback,
            )

        Processor.wait()

        for index in range(0, 8):
            self.assertIn("queue {}".format(index), shared["trace"])
            self.assertIn("start {}".format(index), shared["trace"])
            self.assertIn("end {}".format(index), shared["trace"])
            self.assertIn("done {}".format(index), shared["trace"])

    def test_processor_stop_all(self):

        shared: dict = {"trace": []}

        def routine(index: int):
            time.sleep(1)
            return index

        def routine_stop(index: int):
            Processor.stop()
            return index

        def callback(index, error):
            shared["trace"].append("process {}: {}".format(index, str(error)))

        Processor.queue(routine, 1, q_parallelize=2, q_callback=callback)
        Processor.queue(routine, 2, q_parallelize=2, q_callback=callback)
        Processor.queue(routine_stop, 3, q_parallelize=2, q_callback=callback)
        Processor.queue(routine, 4, q_parallelize=2, q_callback=callback)

        Processor.wait()

        self.assertIn("process 1: None", shared["trace"])
        self.assertIn("process 2: None", shared["trace"])
        self.assertIn("process 3: Process interrupted", shared["trace"])

    def test_processor_wait_once(self):

        shared: dict = {"trace": []}

        def routine(index: int):
            time.sleep(0.1)
            return index

        def callback(index, error):
            shared["trace"].append("task {} done".format(index))

        Processor.queue(routine, 1, q_parallelize=2, q_callback=callback)
        task2 = Processor.queue(routine, 2, q_parallelize=2, q_callback=callback)
        task3 = Processor.queue(routine, 3, q_parallelize=2, q_callback=callback)
        task4 = Processor.queue(routine, 4, q_parallelize=2, q_callback=callback)
        Processor.queue(routine, 5, q_parallelize=2, q_callback=callback)

        Processor.wait(task2)
        self.assertIn("task 1 done", shared["trace"])
        self.assertIn("task 2 done", shared["trace"])

        Processor.wait([task3, task4])
        self.assertIn("task 1 done", shared["trace"])
        self.assertIn("task 2 done", shared["trace"])
        self.assertIn("task 3 done", shared["trace"])
        self.assertIn("task 4 done", shared["trace"])

        Processor.wait()
        self.assertIn("task 1 done", shared["trace"])
        self.assertIn("task 2 done", shared["trace"])
        self.assertIn("task 3 done", shared["trace"])
        self.assertIn("task 4 done", shared["trace"])
        self.assertIn("task 5 done", shared["trace"])

    def test_processor_timeout(self):

        shared: dict = {"done": [], "errors": []}

        def routine(index: int, duration: float):
            time.sleep(duration)
            return index

        def callback(index, error):
            if error is None:
                shared["done"].append(index)
            else:
                shared["errors"].append(error)

        Processor.queue(routine, 1, 1.5, q_callback=callback, q_timeout=2)
        Processor.queue(routine, 2, 2.0, q_callback=callback, q_timeout=2)
        Processor.queue(routine, 3, 1.0, q_callback=callback, q_timeout=2)
        Processor.queue(routine, 4, 3.0, q_callback=callback, q_timeout=2)
        Processor.queue(routine, 5, 2.5, q_callback=callback, q_timeout=2)
        Processor.queue(routine, 6, 3.5, q_callback=callback, q_timeout=2)

        Processor.wait()

        self.assertIn(1, shared["done"])
        self.assertIn(2, shared["done"])
        self.assertIn(3, shared["done"])
        self.assertGreater(
            len(shared["errors"]), 0
        )  # Care, windows+python 3.9 stop at first, not see 3 items
        self.assertTrue(isinstance(shared["errors"][0], TimeoutError))
