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

"""Pytest plugin that records and replays EODAG calls.

.. note::
    Strongly inspired by `pytest-recording <https://pypi.org/project/pytest-recording/>`_.

    It is deliberately not imported by :mod:`eodag.utils.recording`, as ``pytest`` is
    not a runtime dependency of eodag: projects have to enable it explicitly. See the
    :ref:`recording preparation procedure <recording-preparation>`.

At class level (so for every instance, including those created by the application
under test), the plugin intercepts the following methods of
:class:`eodag.EODataAccessGateway`:

* ``search()``: ``search`` section of the cassette;
* ``search_all()``: ``search_all`` section. The aggregated result of all pages is
  recorded, so no pagination token is needed;
* ``download()``: ``download`` section.

Each call is treated as a pure function: the answer of the provider is stored under a
key made of the parameters actually passed, and the same call replayed later returns
the same answer. No state is kept between two calls.

The recording mode is chosen, by decreasing priority, with: the
``--eodag-record-mode={none,once,all,new_episodes}`` CLI option, the ``record_mode``
argument of the marker, the ``eodag_record_mode`` fixture, then ``none``. See
:class:`~eodag.utils.recording.recorder.RecordMode` and the
`VCR.py documentation <https://vcrpy.readthedocs.io/en/stable/usage.html#record-modes>`_
for details about the modes.

By default, cassettes are stored in ``<test directory>/cassettes/<module>/<test>.yaml``
and downloaded products in ``<test directory>/cassettes/_downloads``. Override the
fixtures ``eodag_cassette_dir``, ``eodag_archive_dir`` and ``eodag_cassette_name`` to
change this.

.. warning::

    Only Linux is currently supported, as replayed downloads rely on symbolic links.
"""

from __future__ import annotations

import hashlib
import os
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

    :param cassettes: name, list of names (relative to the :func:`eodag_cassette_dir`
        fixture), or callable ``f(request) -> name | list``. Default: the name is
        derived from the test name.
    :param write_to: cassette to write to. Mandatory when several cassettes are given
        and the mode may write.
    :param record_mode: ``none`` | ``once`` | ``all`` | ``new_episodes``.
    :param archive_dir: directory where eodag actually downloads EO products.
    :return: the ``pytest.mark.eodag_record`` marker, to be used as a decorator.
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
        help="eodag recording mode (takes precedence over marker and fixtures).",
    )


def pytest_configure(config: pytest.Config) -> None:
    """pytest initialization hook: Registers ``@pytest.mark.eodag_record``."""
    config.addinivalue_line(
        "markers",
        f"{MARKER}(cassettes=None, write_to=None, record_mode=None, archive_dir=None): "
        "records/replays search(), search_all() and download() from eodag.",
    )


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """pytest runtest hook: stores the report of each phase on the test item, so that
    cassettes are only written if the test succeeded."""
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
    """Default recording mode (overridable). Has a lower priority than the marker and the CLI option."""
    return RecordMode.NONE.value


@pytest.fixture
def eodag_cassette_dir(request: pytest.FixtureRequest) -> Path:
    """Cassettes root directory (overridable): ``<test directory>/cassettes``."""
    return Path(request.node.path).parent / "cassettes"


@pytest.fixture
def eodag_archive_dir(eodag_cassette_dir: Path) -> Path:
    """Directory where products are actually downloaded (overridable)."""
    return eodag_cassette_dir / "_downloads"


@pytest.fixture
def eodag_cassette_name(request: pytest.FixtureRequest) -> str:
    """Default cassette name (overridable): ``<module>/<[Class.]test[params]>.yaml``."""
    node = request.node
    module = Path(node.path).stem
    cls = f"{node.cls.__name__}." if getattr(node, "cls", None) else ""
    return os.path.join(module, f"{_sanitize(cls + node.name)}.yaml")


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
    """Activates recording/replay for the test (patches the gateway class)."""
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
    """Activates ``eodag_recorder`` for the tests carrying the ``eodag_record`` marker."""
    if request.node.get_closest_marker(MARKER) is not None:
        request.getfixturevalue("eodag_recorder")
