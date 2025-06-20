# -*- coding: utf-8 -*-
# Copyright 2025, CS GROUP - France, https://www.cs-soprasteria.com/
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

from eodag.cache import instance_cached_method


class TestCachedMethodDecorator(unittest.TestCase):
    def test_per_instance_caching(self):
        class TestClass:
            def __init__(self):
                self.call_count = 0

            @instance_cached_method(maxsize=2)
            def method(self, x):
                self.call_count += 1
                return x * 2

        obj1 = TestClass()
        obj2 = TestClass()

        # Call with same argument twice on obj1 - second should hit cache
        result1 = obj1.method(10)
        result2 = obj1.method(10)
        self.assertEqual(result1, 20)
        self.assertEqual(result2, 20)
        self.assertEqual(
            obj1.call_count, 1, "Method should be called once due to caching"
        )

        # Different argument - cache miss, increments call_count
        result3 = obj1.method(5)
        self.assertEqual(result3, 10)
        self.assertEqual(obj1.call_count, 2)

        # obj2 is a separate instance - cache is separate, so call_count should start fresh
        result4 = obj2.method(10)
        self.assertEqual(result4, 20)
        self.assertEqual(obj2.call_count, 1)

        # Calling again on obj2 with same arg hits cache
        result5 = obj2.method(10)
        self.assertEqual(result5, 20)
        self.assertEqual(obj2.call_count, 1)

    def test_cache_eviction(self):
        class TestClass:
            def __init__(self):
                self.call_count = 0

            @instance_cached_method(maxsize=2)
            def method(self, x):
                self.call_count += 1
                return x

        obj = TestClass()

        obj.method(1)
        obj.method(2)
        self.assertEqual(obj.call_count, 2)

        # Cache is full, next unique call evicts oldest
        obj.method(3)
        self.assertEqual(obj.call_count, 3)

        # Calling with 1 again is a cache miss (evicted), so call_count increments
        obj.method(1)
        self.assertEqual(obj.call_count, 4)


if __name__ == "__main__":
    unittest.main()
