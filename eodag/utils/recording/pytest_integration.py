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
"""This submodule defines a pytest plugin that permits to replay EODAG requests.

.. note::
    This plugin has been strongly inspired by `pytest-recording
    <https://pypi.org/project/pytest-recording/>`_

    Yet, integration into pytest is done in
    :mod:`eodag.utils.recording.pytest_integration`, and it is volontarily not imported
    here. Indeed ``pytest`` is not an execution dependency of eodag.

    You'll have to do it explicitely in the tests of your projets that depends on eodag.
    See :ref:`recording preparation procedure <recording-preparation>`.

The plugin intercepts and supercedes the three following methods of
:class:`eodag.EODataAccessGateway` at class level (meaning it will apply to all
instances, even those created by the tested application).

* ``search()``      -> cassette, ``search`` section
* ``search_all()``  -> cassette, ``search_all`` section (aggregated result of all pages:
    no pagination token is recorded)
* ``download()``    -> cassette, ``download`` section

Every call is considered as a pure function call, no context is kept. Given an execution
in real mode, eodag response is registered under a key, and replaying under the same
conditions (i.e. same key), the same response will be returned.



At CLI level you can choose the execution mode:
``--eodag-record-mode={none,once,all,new_episodes}``. See vcrpy documentation for more
details about the various modes.

Mode priority: CLI > marqueur > fixture ``eodag_record_mode`` > ``none``.

.. warning: currently only Linux is supported (given how symbolic links are used internally)
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

import pytest

from eodag.utils.recording.recorder import EodagRecorder, RecordMode

# --------------------------------------------------------------------------- #
# pytest integration
# --------------------------------------------------------------------------- #
MARKER = "eodag_record"
_REPORT_KEY = pytest.StashKey[dict]()


def eodag_record(
    cassettes: str | Sequence[str] | Callable[..., Any] | None = None,
    *,
    write_to: str | None = None,
    record_mode: RecordMode | str | None = None,
    archive_dir: str | Path | None = None,
):
    """
    Decorator equivalent to ``@pytest.mark.eodag_record(...)``.

    :param cassettes: name, list of names (relative to :func:`eodag_cassette_dir`), or
        callable ``f(request) -> name | list``. Default: name is derived from test name.
    :param write_to: recording cassette (mandatory if several cassettes are specified and *if* we can
        write).
    :param record_mode: ``none`` | ``once`` | ``all`` | ``new_episodes``.
    :param archive_dir: directory where eodag actually downloads EO products.
    """
    options = {
        "cassettes": cassettes,
        "write_to": write_to,
        "record_mode": record_mode,
        "archive_dir": archive_dir,
    }
    return getattr(pytest.mark, MARKER)(
        **{k: v for k, v in options.items() if v is not None}
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    """pytest initialization hook: Registers :option:`--eodag-record-mode`."""
    group = parser.getgroup("eodag-recording")
    group.addoption(
        "--eodag-record-mode",
        choices=[m.value for m in RecordMode],
        default=None,
        help="eodag recording mode (is prioritary over marker and fixtures).",
    )


def pytest_configure(config: pytest.Config) -> None:
    """pytest initialization hook: Registers ``@pytest.mark.eodag_record``."""
    config.addinivalue_line(
        "markers",
        f"{MARKER}(cassettes=None, write_to=None, record_mode=None, archive_dir=None): "
        "records/replays search(), search_all() et download() from eodag.",
    )


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """pytest runtest hook: Make sure to update casettes only on test success."""
    outcome = yield
    report = outcome.get_result()
    item.stash.setdefault(_REPORT_KEY, {})[report.when] = report


def _marker_options(node: pytest.Item) -> dict[str, Any]:
    """Merges markers (the closest from the function wins)."""
    options: dict[str, Any] = {}
    for mark in reversed(list(node.iter_markers(MARKER))):
        options.update(mark.kwargs)
        if mark.args:  # @pytest.mark.eodag_record("a.yaml")
            options["cassettes"] = mark.args[0]
    return options


def _sanitize(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.\-\[\]]+", "_", name)
    if len(name) > 150:
        digest = hashlib.sha1(name.encode()).hexdigest()[:10]
        name = f"{name[:130]}_{digest}"
    return name


@pytest.fixture
def eodag_record_mode() -> str:
    """Default mode (can be overridden) ; has a lesser priority than marker or CLI"""
    return RecordMode.NONE.value


@pytest.fixture
def eodag_cassette_dir(request: pytest.FixtureRequest) -> Path:
    """Cassettes root (can be overridden) : ``<test directory>/cassettes``."""
    return Path(request.node.path).parent / "cassettes"


@pytest.fixture
def eodag_archive_dir(eodag_cassette_dir: Path) -> Path:
    """Download archive directory (can be overridden)."""
    return eodag_cassette_dir / "_downloads"


@pytest.fixture
def eodag_cassette_name(request: pytest.FixtureRequest) -> str:
    """Default cassette name (can be overridden): ``<module>/<[Class.]test[params]>.yaml``."""
    node = request.node
    module = Path(node.path).stem
    cls = f"{node.cls.__name__}." if getattr(node, "cls", None) else ""
    return f"{module}/{_sanitize(cls + node.name)}.yaml"


def _as_list(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else [value]


@pytest.fixture
def eodag_recorder(
    request: pytest.FixtureRequest,
    eodag_record_mode: str,
    eodag_cassette_dir: Path,
    eodag_archive_dir: Path,
    eodag_cassette_name: str,
) -> Iterator[EodagRecorder]:
    """Activate recording/reply for the test (patches dateway class)."""
    options = _marker_options(request.node)

    mode = (
        request.config.getoption("--eodag-record-mode")
        or options.get("record_mode")
        or eodag_record_mode
    )

    names = options.get("cassettes", eodag_cassette_name)
    if callable(names):
        names = names(request)
    cassettes = [
        (
            p
            if (p := Path(n if Path(n).suffix else f"{n}.yaml")).is_absolute()
            else eodag_cassette_dir / p
        )
        for n in _as_list(names)
    ]

    write_to = options.get("write_to")
    if write_to is not None:
        write = Path(write_to if Path(write_to).suffix else f"{write_to}.yaml")
        write_to = write if write.is_absolute() else eodag_cassette_dir / write

    archive_dir = options.get("archive_dir", eodag_archive_dir)
    recorder = EodagRecorder(mode, cassettes, archive_dir, write_to=write_to)
    with recorder.patched():
        yield recorder
    reports = request.node.stash.get(_REPORT_KEY, {})
    passed = all(r.passed for r in reports.values()) and "call" in reports
    recorder.finalize(save=passed)


@pytest.fixture(autouse=True)
def _eodag_recording_auto(request: pytest.FixtureRequest) -> None:
    """Activates ``eodag_recorder`` for tests marked."""
    if request.node.get_closest_marker(MARKER) is not None:
        request.getfixturevalue("eodag_recorder")
