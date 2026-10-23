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
from contextlib import contextmanager
from pathlib import Path
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
    """Recording mode -- follows `VCR.py semantics
    <https://vcrpy.readthedocs.io/en/stable/usage.html#record-modes>`_"""

    #: No recording is done. Cassettes will only be replayed.
    NONE = "none"

    #: Recording is accepted only once. Existing and non-empty cassettes will be read-only.
    ONCE = "once"

    #: Recording from actual data. All cassettes will be recorded.
    ALL = "all"

    #: Only new data is recorded. Pre-existing keys are replay only.
    NEW_EPISODES = "new_episodes"


# --------------------------------------------------------------------------- #
# Recorder
# --------------------------------------------------------------------------- #
#: True while real execution of ``search_all`` : the internal ``search()``
#: (first page) shall not be registered separately.
_PASSTHROUGH: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "eodag_recording_passthrough", default=False
)


def _first_component(rel: str) -> str:
    return Path(rel).parts[0]


def _ensure_symlink(link: Path, target: Path) -> None:
    """Creates ``link -> target``.
    If ``link`` already exists, we suppose the product has already been downloaded -- unless the
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
        os.symlink(target, link)
    except FileExistsError:  # Race between two calls
        pass


def _default_output_dir(gateway: EODataAccessGateway, product: EOProduct) -> str:
    """``output_dir`` that eodag would use if no explicit kwargs is provided.

    .. note:: We need to use private eodag API to extract this value
    """
    try:
        plugin = gateway._plugins_manager.get_download_plugin(product)
        output_dir = plugin.config.output_dir
    except Exception as exc:  # noqa: BLE001
        logger.debug("output_dir du plugin indisponible (%r)", exc)
        output_dir = None
    return output_dir or tempfile.gettempdir()


class EodagRecorder:
    """Test state: cassettes, mode, recording directory, and gateway patch."""

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
        #: Where EOProducts are actually stored and expected
        self.archive_dir = Path(archive_dir).resolve()
        self._lock = threading.RLock()
        self._dirty = False
        self._patched = False

        #: Path to the cassette that will be written to
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
                f"Several cassettes specified in mode {self.mode.value!r}: write_to is "
                "mandatory (write_to cassette shall be explicitly specified)."
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
                    f"(everything is actually executed) : {[str(p) for p in others]}",
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
            f"No recording matches {section}() " f"(mode {self.mode.value!r}).",
            f"Cassettes : {[str(p) for p in self.cassette_paths]}",
            "Parameters received:",
            json.dumps(got, indent=2, ensure_ascii=False, sort_keys=True),
        ]
        if not candidates:
            lines.append(
                f"Section {section!r} is empty (empty cassette or not in this call)."
            )
        for i, cand in enumerate(candidates[:3], 1):
            lines.append(f"Closest recording #{i} — differences :")
            lines.extend("  " + d for d in _describe_diff(got, cand))
        lines.append(
            "Launch again with --eodag-record-mode=all (or new_episodes) to register a use case."
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
        The method that handles real execution (and recording) or replay.

        :param section:   Cassette section, but also the method wrapped/mocked
        :param params:    Actual parameters passed to the method wrapped
        :param real_call: Actual EODAG fonction wrapped, the one that will get executed
                          if not in replay.
        :param encode:    Hook used to encode the result of EODAG execution (i.e. the
                          result of ``real_call(**param)``
        :param replay:    Hook that builds the expected result from the cassette content
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
        Creates :func:`eodag.api.core.EODataAccessGateway.search()` and
        :func:`eodag.api.core.EODataAccessGateway.search_all()` mock wrappers.
        """
        recorder = self

        def wrapper(
            gateway: EODataAccessGateway, *args: Any, **kwargs: Any
        ) -> SearchResult:
            """
            Replacement for :func:`eodag.api.core.EODataAccessGateway.search()` and
            :func:`eodag.api.core.EODataAccessGateway.search_all()`.
            """
            logger.debug("Call to search(%s, %s)", args, kwargs)
            if _PASSTHROUGH.get():
                return original(gateway, *args, **kwargs)
            params = bind_passed_params(original, gateway, *args, **kwargs)

            def real_call() -> SearchResult:
                """Actual call to the ``search()`` method."""
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

        .. note:: About ``output_dir`` resolution:

            - EODAG uses ``output_dir`` from ``kwargs``, otherwise
              ``downloader.config.output_dir``, otherwise system tmpdir.
            - Returned path is :file:`output_dir/<title sanitisé><output_extension>`.
              With ``archive_depth`` or extraction, it can be a sub-path
            - EODAG creates a :file:`.downloaded/<hash>` in ``output_dir`` directory. It
              will be in the archive.
            - Default ``output_dir`` is returned by a private API.
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
                """Encodes ``download()`` result in the casette."""
                return recorder._encode_download(path, virtual_dir)

            def replay(result: dict[str, Any]) -> str:
                """
                Replays an previouly encoded ``download()`` result from the casette.
                """
                logger.debug(
                    "└─> emulated: linking '%s' to '%s'", result["path"], virtual_dir
                )
                return recorder._materialize(result["path"], virtual_dir)

            real_result: dict[str, Any] = {}

            def real_and_link() -> str:
                """Wraps actual downloading, and takes care of symlinks"""
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
        if not isinstance(path, (str, os.PathLike)):
            return None
        rel = os.path.relpath(os.path.abspath(path), self.archive_dir)
        if rel == "." or rel.startswith(".." + os.sep) or rel == "..":
            return None
        return rel

    def _encode_download(self, path: Any, virtual_dir: Path) -> dict[str, Any] | None:
        rel = self._relative_to_archive(path)
        if rel is None:
            warnings.warn(
                f"download() has returned {path!r}, which is outside the recording directory "
                f"{self.archive_dir} (local product ?) : not recorded.",
                EodagRecordingWarning,
                stacklevel=2,
            )
            return None
        return {"path": rel}

    def _materialize(self, rel: str, virtual_dir: Path) -> str:
        """Creates (if required) the link ``virtual_dir/<x> -> archive/<x>`` and returns
        ``virtual_dir/<rel>``."""
        first = _first_component(rel)
        target = self.archive_dir / first
        if not target.exists():
            raise EodagRecordingError(
                f"Record file cannot be found: {target} (cassette or archive "
                "unsynchronized ; record again with --eodag-record-mode=all)."
            )
        if virtual_dir != self.archive_dir:
            _ensure_symlink(virtual_dir / first, target)
        return str(virtual_dir / rel)

    # ---- patch ------------------------------------------------------------- #
    @contextmanager
    def patched(self) -> Iterator["EodagRecorder"]:
        """Takes care of patching the supported methods."""
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
        with mock.patch.multiple(cls, create=False, **wrappers):
            cls._eodag_recording_active = True  # type: ignore[attr-defined]
            self._patched = True
            try:
                yield self
            finally:
                self._patched = False
                del cls._eodag_recording_active  # type: ignore[attr-defined]

    def finalize(self, save: bool) -> None:
        """Writes the record cassette if new entries have been added and if test succeeds"""
        if save and self._dirty and self._write_cassette is not None:
            self._write_cassette.dump()
            self._dirty = False


def _describe_diff(got: dict[str, Any], recorded: dict[str, Any]) -> list[str]:
    def short(v: Any) -> str:
        s = json.dumps(v, ensure_ascii=False, sort_keys=True)
        return s if len(s) <= 100 else s[:97] + "..."

    out = []
    for name in sorted(set(got) | set(recorded)):
        if name not in recorded:
            out.append(f"+ {name}={short(got[name])} (not in recording)")
        elif name not in got:
            out.append(f"- {name}={short(recorded[name])} (recorded, failed)")
        elif got[name] != recorded[name]:
            out.append(
                f"~ {name}: reçu {short(got[name])} / recorded {short(recorded[name])}"
            )
    return out or ["(no visible difference)"]
