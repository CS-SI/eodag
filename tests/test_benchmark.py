# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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

from tests import test_cli
from tests.integration import test_core_search_results


def _run_unittest_method(test_case_cls, method_name):
    """Run one unittest test method with isolated setup/teardown."""
    test_case = test_case_cls(methodName=method_name)
    test_case.setUp()
    try:
        getattr(test_case, method_name)()
    finally:
        test_case.tearDown()


def test_benchmark_cli_without_args(benchmark):
    benchmark(
        lambda: _run_unittest_method(test_cli.TestEodagCli, "test_eodag_without_args")
    )


def test_benchmark_cli_list_collections(benchmark):
    benchmark(
        lambda: _run_unittest_method(
            test_cli.TestEodagCli, "test_eodag_list_collection_ok"
        )
    )


def test_benchmark_core_search_with_provider(benchmark):
    benchmark(
        lambda: _run_unittest_method(
            test_core_search_results.TestCoreSearchResults,
            "test_core_search_with_provider",
        )
    )
