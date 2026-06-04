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

import os
import subprocess
import sys
from tempfile import TemporaryDirectory

from tests import test_cli
from tests.integration import test_core_search_results
from tests.units import test_stac_reader
from tests.utils import write_eodag_conf_with_fake_credentials


def _prepare_isolated_test_env(tmp_home_dir):
    """Create an isolated HOME + eodag config and return subprocess environment."""
    eodag_conf_dir = os.path.join(tmp_home_dir, ".config", "eodag")
    os.makedirs(eodag_conf_dir, exist_ok=False)
    write_eodag_conf_with_fake_credentials(os.path.join(eodag_conf_dir, "eodag.yml"))

    env = os.environ.copy()
    env["HOME"] = tmp_home_dir
    return env


def _run_subprocess(command, env):
    """Run a subprocess command and return captured stdout/stderr and exit code."""
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _run_unittest_method(test_case_cls, method_name):
    """Run one unittest test method with isolated setup/teardown."""
    test_case = test_case_cls(methodName=method_name)
    test_case.setUp()
    try:
        getattr(test_case, method_name)()
    finally:
        test_case.tearDown()


def _run_cli_subprocess_without_args(env):
    """Run the CLI in a subprocess to include Python and entrypoint startup cost."""
    result = _run_subprocess([sys.executable, "-m", "eodag.cli"], env)
    # Click >= 8.2 returns 2 for no-args-is-help
    assert result.returncode in (0, 2)
    cli_output = f"{result.stdout}{result.stderr}"
    assert "Earth Observation Data Access Gateway" in cli_output


def _instantiate_eodag_subprocess(env):
    """Instantiate EODataAccessGateway in a subprocess (cold start path)."""
    result = _run_subprocess(
        [
            sys.executable,
            "-c",
            ("from eodag import EODataAccessGateway;" "EODataAccessGateway()"),
        ],
        env,
    )
    assert result.returncode == 0, result.stderr


def test_benchmark_cli_without_args_subprocess(benchmark):
    with TemporaryDirectory() as tmp_home_dir:
        env = _prepare_isolated_test_env(tmp_home_dir)

        benchmark.pedantic(
            _run_cli_subprocess_without_args,
            kwargs={"env": env},
            rounds=10,
            iterations=1,
        )


def test_benchmark_eodag_instantiation_subprocess(benchmark):
    with TemporaryDirectory() as tmp_home_dir:
        env = _prepare_isolated_test_env(tmp_home_dir)

        benchmark.pedantic(
            _instantiate_eodag_subprocess,
            kwargs={"env": env},
            rounds=10,
            iterations=1,
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


def test_benchmark_cli_version(benchmark):
    benchmark(
        lambda: _run_unittest_method(test_cli.TestEodagCli, "test_eodag_cli_version")
    )


def test_benchmark_core_search_with_count(benchmark):
    benchmark(
        lambda: _run_unittest_method(
            test_core_search_results.TestCoreSearchResults,
            "test_core_search_with_count",
        )
    )


def test_benchmark_stac_reader_fetch_recursive(benchmark):
    benchmark(
        lambda: _run_unittest_method(
            test_stac_reader.TestStacReader,
            "test_stac_reader_fetch_root_recursive",
        )
    )
