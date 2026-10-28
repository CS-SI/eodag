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

"""Record and replay of EODAG calls: ``search()``, ``search_all()`` and ``download()``.

The three methods of :class:`~eodag.api.core.EODataAccessGateway` are patched at class
level, so every instance is affected, including those created by the application under
test.

For ``download()``, eodag always downloads into the *archive directory*, and the patched
method returns ``<output_dir>/<name>``, a symbolic link to ``<archive_dir>/<name>``
created on the fly. ``output_dir`` is the one the caller would have got without the
plugin (the ``output_dir`` keyword, otherwise the downloader configuration). Recorded
and replayed runs are thus indistinguishable for the caller.
"""

from __future__ import annotations

import contextvars
import difflib
import enum
import json
import logging
import os
import tempfile
import threading
import warnings
from contextlib import ExitStack, contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator, Sequence
from unittest import mock

from eodag.api.core import EODataAccessGateway
from eodag.api.product import EOProduct
from eodag.api.search_result import SearchResult
from eodag.utils.recording.cassette import (
    SECTIONS,
    Cassette,
    bind_passed_params,
    canonical_key,
    decode_exception,
    decode_search_result,
    encode_exception,
    encode_search_result,
    normalize,
)
from eodag.utils.recording.errors import (
    DuplicateKeyError,
    EodagRecordingConfigError,
    EodagRecordingError,
    EodagRecordingWarning,
    NoMatchingRecordError,
)

logger = logging.getLogger(__name__)


class RecordMode(str, enum.Enum):
    """Recording mode, following the `VCR.py record modes
    <https://vcrpy.readthedocs.io/en/stable/usage.html#record-modes>`_ semantics.

    With several cassettes, only the one designated by ``write_to`` is ever written.
    """

    #: Replay only. A call with no matching entry raises
    #: :class:`~eodag.utils.recording.errors.NoMatchingRecordError`.
    NONE = "none"

    #: Behaves like :attr:`ALL` if the cassette to write to does not exist yet, like
    #: :attr:`NONE` otherwise.
    ONCE = "once"

    #: Every call is executed for real and the cassette to write to is rewritten from
    #: scratch. The other cassettes are ignored (a warning is emitted).
    ALL = "all"

    #: Calls with a matching entry are replayed. Unknown calls are executed for real
    #: and appended to the cassette to write to.
    NEW_EPISODES = "new_episodes"


# --------------------------------------------------------------------------- #
# Recorder
# --------------------------------------------------------------------------- #
#: ``True`` while ``search_all()`` is actually being executed: the internal
#: ``search()`` call (first page) must not be recorded separately.
_PASSTHROUGH: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "eodag_recording_passthrough", default=False
)


def _first_component(rel: str) -> str:
    """First component of a relative path as stored in cassettes (``/`` separated)."""
    return PurePosixPath(rel).parts[0]


def _ensure_symlink(link: Path, target: Path) -> None:
    """Creates ``link -> target``.
    If ``link`` already exists, we assume the product has already been downloaded -- unless the
    link is broken, in which case it's recreated.
    """
    if os.path.lexists(link):
        logger.debug(
            "'%s' already exists. symlink? %s, exist? %s",
            link,
            link.is_symlink(),
            link.exists(),
        )
        if link.is_symlink() and not link.exists():
            link.unlink()
        else:
            return
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        logger.debug("Create symlink from '%s' to '%s'", target, link)
        # On Windows a symlink is either a file or a directory one, so we say which
        os.symlink(target, link, target_is_directory=target.is_dir())
    except FileExistsError:  # Race between two calls
        pass
    except (OSError, NotImplementedError) as exc:
        hint = (
            " On Windows, enable Developer Mode (or run with the 'create symbolic "
            "links' privilege). Only the case where the archive directory and the "
            "output directory are on the same drive is supported."
            if os.name == "nt"
            else ""
        )
        raise EodagRecordingError(
            f"Cannot create symbolic link '{link}' -> '{target}': {exc}.{hint}"
        ) from exc


def _default_output_dir(gateway: EODataAccessGateway, product: EOProduct) -> str:
    """``output_dir`` that eodag would use if no explicit kwargs is provided.

    .. note:: We need to use private eodag API to extract this value
    """
    try:
        plugin = gateway._plugins_manager.get_download_plugin(product)
        output_dir = plugin.config.output_dir
    except Exception as exc:  # noqa: BLE001
        logger.debug("download plugin output_dir unavailable (%r)", exc)
        output_dir = None
    return output_dir or tempfile.gettempdir()


class EodagRecorder:
    """Records or replays EODAG calls for one test.

    Holds the test state: cassettes, mode, archive directory, and gateway patch.

    :param mode: Requested recording mode. ``once`` is resolved at construction, see
        :attr:`effective_mode`.
    :param cassettes: Cassette files used by the test.
    :param archive_dir: Directory where eodag actually downloads products.
    :param write_to: Cassette to write to. Optional if there is a single cassette,
        mandatory otherwise whenever recording may happen.
    :raises EodagRecordingConfigError: if there is no cassette, if ``write_to`` is not
        one of the cassettes, or if it is missing when required.
    :raises DuplicateKeyError: if the same key is present in several cassettes.
    """

    def __init__(
        self,
        mode: RecordMode | str,
        cassettes: Sequence[str | Path],
        archive_dir: str | Path,
        write_to: str | Path | None = None,
    ) -> None:
        #: Current recording mode
        self.mode = RecordMode(mode)
        #: Cassettes used by the test
        self.cassette_paths = [Path(p).resolve() for p in cassettes]
        if not self.cassette_paths:
            raise EodagRecordingConfigError("At least one cassette is required.")
        #: Directory where eodag actually downloads products, and where replays link to
        self.archive_dir = Path(archive_dir).resolve()
        self._lock = threading.RLock()
        self._dirty = False
        self._patched = False

        #: Path to the cassette that is written to (``None`` if it cannot be determined)
        self.write_path = self._resolve_write_path(write_to)
        #: Effective recording mode
        self.effective_mode = self._resolve_effective_mode()
        self._write_cassette: Cassette | None = None
        self._read_cassettes: list[Cassette] = []
        self._load()

    # ---- configuration ---------------------------------------------------- #
    def _resolve_write_path(self, write_to: str | Path | None) -> Path | None:
        if write_to is not None:
            path = Path(write_to).resolve()
            if path not in self.cassette_paths:
                raise EodagRecordingConfigError(
                    f"write_to={write_to!r} shall be one of the cassettes: "
                    f"{[str(p) for p in self.cassette_paths]}"
                )
            return path
        if len(self.cassette_paths) == 1:
            return self.cassette_paths[0]
        return None

    def _resolve_effective_mode(self) -> RecordMode:
        mode = self.mode
        if mode is RecordMode.ONCE:
            if self.write_path is None:
                raise EodagRecordingConfigError(
                    "Several cassettes specified in mode 'once': write_to is mandatory."
                )
            mode = RecordMode.NONE if self.write_path.exists() else RecordMode.ALL
        if (
            mode in (RecordMode.ALL, RecordMode.NEW_EPISODES)
            and self.write_path is None
        ):
            raise EodagRecordingConfigError(
                "write_to is mandatory when several cassettes are specified in mode "
                f"{self.mode.value!r}: the cassette to write to must be designated "
                "explicitly."
            )
        return mode

    def _load(self) -> None:
        if self.effective_mode is RecordMode.ALL:
            self._write_cassette = Cassette(self.write_path)  # type: ignore[arg-type]
            logger.debug("Write cassette set to '%s'", self.write_path)
            others = [
                p for p in self.cassette_paths if p != self.write_path and p.exists()
            ]
            if others:
                warnings.warn(
                    f"Mode {self.mode.value!r}: cassettes are ignored in replay "
                    f"(every call is executed for real): {[str(p) for p in others]}",
                    EodagRecordingWarning,
                    stacklevel=2,
                )
            return
        cassettes = [Cassette.load(p) for p in self.cassette_paths]
        self._check_duplicates(cassettes)
        self._read_cassettes = cassettes
        logger.debug("Cassettes read: %s", self._read_cassettes)
        if self.effective_mode is RecordMode.NEW_EPISODES:
            self._write_cassette = next(
                c for c in cassettes if c.path == self.write_path
            )
            logger.debug("Write cassette set to '%s'", self._write_cassette)

    @staticmethod
    def _check_duplicates(cassettes: Sequence[Cassette]) -> None:
        seen: dict[tuple[str, str], Path] = {}
        for cassette in cassettes:
            for section in SECTIONS:
                for key in cassette.entries[section]:
                    other = seen.setdefault((section, key), cassette.path)
                    if other != cassette.path:
                        raise DuplicateKeyError(
                            f"Duplicated key (section {section!r}) between {other} and "
                            f"{cassette.path} : {key}"
                        )

    # ---- kernel : recording / replay -------------------------------------- #
    def _lookup(self, section: str, key: str) -> dict[str, Any] | None:
        for cassette in self._read_cassettes:
            entry = cassette.entries[section].get(key)
            if entry is not None:
                return entry
        return None

    def _record(
        self, section: str, params: dict[str, Any], payload: dict[str, Any]
    ) -> None:
        assert self._write_cassette is not None
        with self._lock:
            if self._write_cassette.add(section, params, payload):
                self._dirty = True

    def _no_match(self, section: str, params: dict[str, Any]) -> NoMatchingRecordError:
        got = normalize(params)
        candidates: list[dict[str, Any]] = []
        for cassette in self._read_cassettes:
            candidates.extend(e["params"] for e in cassette.entries[section].values())
        got_key = canonical_key(got)
        candidates.sort(
            key=lambda p: -difflib.SequenceMatcher(
                None, got_key, canonical_key(p)
            ).ratio()
        )
        lines = [
            f"No recording matches {section}() (mode {self.mode.value!r}).",
            f"Cassettes: {[str(p) for p in self.cassette_paths]}",
            "Parameters received:",
            json.dumps(got, indent=2, ensure_ascii=False, sort_keys=True),
        ]
        if not candidates:
            lines.append(
                f"No {section!r} entry in the cassettes (missing or empty cassette?)."
            )
        for i, cand in enumerate(candidates[:3], 1):
            lines.append(f"Closest recording #{i} — differences:")
            lines.extend("  " + d for d in _describe_diff(got, cand))
        lines.append(
            "Re-run with --eodag-record-mode=all (or new_episodes) to record this call."
        )
        return NoMatchingRecordError("\n".join(lines))

    def handle(
        self,
        section: str,
        params: dict[str, Any],
        real_call: Callable[[], Any],
        *,
        encode: Callable[[Any], dict[str, Any] | None],
        replay: Callable[[dict[str, Any]], Any],
    ) -> Any:
        """
        Replays the matching entry, or executes ``real_call`` and records its outcome,
        according to the effective mode.

        :class:`~eodag.utils.exceptions.RequestError` and
        :class:`~eodag.utils.exceptions.NotAvailableError` raised by ``real_call`` are
        recorded and re-raised. Any other exception propagates without being recorded.

        :param section:   Cassette section, which is also the name of the method
                          wrapped/mocked.
        :param params:    Actual parameters passed to the wrapped method.
        :param real_call: Wrapped EODAG function, without arguments, executed if the
                          call is not replayed.
        :param encode:    Hook that encodes the result of ``real_call()`` for the
                          cassette. It can return ``None`` to record nothing.
        :param replay:    Hook that builds the expected result from the cassette
                          content.
        :return: The replayed or actual result.
        :raises NoMatchingRecordError: in ``none`` mode, if no entry matches.
        """
        key = canonical_key(params)
        if self.effective_mode is not RecordMode.ALL:
            entry = self._lookup(section, key)
            if entry is not None:
                if "raises" in entry:
                    raise decode_exception(entry["raises"])
                return replay(entry["result"])
            if self.effective_mode is RecordMode.NONE:
                raise self._no_match(section, params)

        # real call (modes ALL, or NEW_EPISODES without match)
        try:
            result = real_call()
        except Exception as exc:
            encoded = encode_exception(exc)
            if encoded is not None:
                self._record(section, params, {"raises": encoded})
            raise
        payload = encode(result)
        if payload is not None:
            self._record(section, params, {"result": payload})
        return result

    # ---- search / search_all ------------------------------------------------ #
    def _make_search_wrapper(self, section: str, original: Callable) -> Callable:
        """
        Creates the mock wrapper of
        :func:`eodag.api.core.EODataAccessGateway.search()` or
        :func:`eodag.api.core.EODataAccessGateway.search_all()`, depending on
        ``original``.
        """
        recorder = self

        def wrapper(
            gateway: EODataAccessGateway, *args: Any, **kwargs: Any
        ) -> SearchResult:
            """
            Replacement for :func:`eodag.api.core.EODataAccessGateway.search()` and
            :func:`eodag.api.core.EODataAccessGateway.search_all()`.
            """
            logger.debug("Call to %s(%s, %s)", original.__name__, args, kwargs)
            if _PASSTHROUGH.get():
                return original(gateway, *args, **kwargs)
            params = bind_passed_params(original, gateway, *args, **kwargs)

            def real_call() -> SearchResult:
                """Actual call to the original method (``search()`` or ``search_all()``)."""
                logger.debug(
                    "└─> forwarded to %s(%s, %s)", original.__name__, args, kwargs
                )
                token = _PASSTHROUGH.set(True)
                try:
                    return original(gateway, *args, **kwargs)
                finally:
                    _PASSTHROUGH.reset(token)

            return recorder.handle(
                section,
                params,
                real_call,
                encode=encode_search_result,
                replay=decode_search_result,
            )

        wrapper.__name__ = original.__name__
        wrapper.__doc__ = original.__doc__
        return wrapper

    # ---- download ---------------------------------------------------------- #
    def _make_download_wrapper(self, original: Callable) -> Callable:
        """
        Creates :func:`eodag.api.core.EODataAccessGateway.download()` mock wrapper.

        In every mode, the wrapper returns :file:`<output_dir>/<name>`, a symbolic link
        to :file:`<archive_dir>/<name>` created on the fly. When really executed,
        eodag downloads into the archive directory (its ``output_dir`` is replaced), and
        the product path relative to the archive directory is what gets recorded.

        .. note:: About ``output_dir`` resolution:

            - EODAG uses ``output_dir`` from ``kwargs``, otherwise
              ``downloader.config.output_dir``, otherwise the system tmpdir.
            - The returned path is :file:`output_dir/<sanitized title><output_extension>`.
              With ``archive_depth`` or extraction, it can be a sub-path.
            - EODAG creates a :file:`.downloaded/<hash>` directory in ``output_dir``.
              As ``output_dir`` is redirected to the archive directory, it ends up in
              the archive.
            - The default ``output_dir`` is read through a private EODAG API, see
              :func:`_default_output_dir`.
        """
        recorder = self

        def wrapper(
            gateway: EODataAccessGateway, product: EOProduct, *args: Any, **kwargs: Any
        ) -> str:
            """Replacement for :func:`eodag.api.core.EODataAccessGateway.download()`"""
            logger.debug("Call to download(%s, %s)...", args, kwargs)
            params = {"provider": product.provider, "id": product.properties["id"]}
            virtual_dir = Path(
                os.path.abspath(
                    kwargs.get("output_dir") or _default_output_dir(gateway, product)
                )
            )

            def real_call() -> str:
                """Actual call to the ``download()`` method."""
                real_kwargs = dict(kwargs, output_dir=str(recorder.archive_dir))
                recorder.archive_dir.mkdir(parents=True, exist_ok=True)
                logger.debug("└─> forwarded to download(%s, %s)", args, real_kwargs)
                return original(gateway, product, *args, **real_kwargs)

            def encode(path: Any) -> dict[str, Any] | None:
                """Encodes the ``download()`` result for the cassette."""
                return recorder._encode_download(path, virtual_dir)

            def replay(result: dict[str, Any]) -> str:
                """
                Replays a previously encoded ``download()`` result from the cassette.
                """
                logger.debug(
                    "└─> emulated: linking '%s' to '%s'", result["path"], virtual_dir
                )
                return recorder._materialize(result["path"], virtual_dir)

            real_result: dict[str, Any] = {}

            def real_and_link() -> str:
                """Runs the actual download and keeps the path it returned."""
                path = real_call()
                real_result["path"] = path
                return path

            returned = recorder.handle(
                "download", params, real_and_link, encode=encode, replay=replay
            )
            if "path" in real_result:  # actual call : return "virtual" path
                rel = recorder._relative_to_archive(real_result["path"])
                if rel is None:
                    return returned  # non archivable (e.g. local product) : as-is
                return recorder._materialize(rel, virtual_dir)
            return returned

        wrapper.__name__ = original.__name__
        wrapper.__doc__ = original.__doc__
        return wrapper

    def _relative_to_archive(self, path: Any) -> str | None:
        """Path relative to the archive directory, ``/`` separated whatever the OS (so
        that cassettes are portable), or ``None`` if ``path`` is not in the archive."""
        if not isinstance(path, (str, os.PathLike)):
            return None
        try:
            rel = os.path.relpath(os.path.abspath(path), self.archive_dir)
        except ValueError:  # Windows: path and archive are on different drives
            return None
        if rel == "." or rel.startswith(".." + os.sep) or rel == "..":
            return None
        return Path(rel).as_posix()

    def _encode_download(self, path: Any, virtual_dir: Path) -> dict[str, Any] | None:
        rel = self._relative_to_archive(path)
        if rel is None:
            warnings.warn(
                f"download() returned {path!r}, which is outside of the archive "
                f"directory {self.archive_dir} (local product?): not recorded.",
                EodagRecordingWarning,
                stacklevel=2,
            )
            return None
        return {"path": rel}

    def _materialize(self, rel: str, virtual_dir: Path) -> str:
        """Creates the link ``virtual_dir/<x> -> archive/<x>`` if required, where ``<x>`` is
        the first component of ``rel``, and returns ``virtual_dir/<rel>``."""
        first = _first_component(rel)
        target = self.archive_dir / first
        if not target.exists():
            raise EodagRecordingError(
                f"Archived product not found: {target} (cassette and archive directory "
                "are out of sync; record again with --eodag-record-mode=all)."
            )
        if virtual_dir != self.archive_dir:
            _ensure_symlink(virtual_dir / first, target)
        return str(virtual_dir / rel)

    # ---- patch ------------------------------------------------------------- #
    @contextmanager
    def patched(self) -> Iterator["EodagRecorder"]:
        """Context manager that patches ``search``, ``search_all`` and ``download`` on
        :class:`~eodag.api.core.EODataAccessGateway` (class level, so every instance is
        affected), and restores them on exit.

        :raises EodagRecordingError: if the class is already patched.
        """
        if self._patched or getattr(
            EODataAccessGateway, "_eodag_recording_active", False
        ):
            raise EodagRecordingError("EODataAccessGateway has already been patched.")
        cls = EODataAccessGateway
        wrappers = {
            "search": self._make_search_wrapper("search", cls.search),
            "search_all": self._make_search_wrapper("search_all", cls.search_all),
            "download": self._make_download_wrapper(cls.download),
        }
        with ExitStack() as stack:
            for name, wrapper in wrappers.items():
                stack.enter_context(mock.patch.object(cls, name, new=wrapper))
            cls._eodag_recording_active = True  # type: ignore[attr-defined]
            self._patched = True
            try:
                yield self
            finally:
                self._patched = False
                del cls._eodag_recording_active  # type: ignore[attr-defined]

    def finalize(self, save: bool) -> None:
        """Writes the cassette to write to if new entries have been added and the test
        succeeded.

        :param save: ``False`` if the test failed, in which case nothing is written.
        """
        if save and self._dirty and self._write_cassette is not None:
            self._write_cassette.dump()
            self._dirty = False


def _describe_diff(got: dict[str, Any], recorded: dict[str, Any]) -> list[str]:
    """Describes, parameter by parameter, how a call differs from a recorded one.

    Lines start with ``+`` for a parameter passed but absent from the recording, ``-``
    for a recorded parameter that was not passed, and ``~`` for a different value.
    """

    def short(v: Any) -> str:
        s = json.dumps(v, ensure_ascii=False, sort_keys=True)
        return s if len(s) <= 100 else s[:97] + "..."

    out = []
    for name in sorted(set(got) | set(recorded)):
        if name not in recorded:
            out.append(f"+ {name}={short(got[name])} (not in recording)")
        elif name not in got:
            out.append(f"- {name}={short(recorded[name])} (recorded, but not passed)")
        elif got[name] != recorded[name]:
            out.append(
                f"~ {name}: received {short(got[name])} / recorded {short(recorded[name])}"
            )
    return out or ["(no visible difference)"]
