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

"""YAML cassettes and (de)serialization of EODAG results.

A cassette is a YAML file holding a ``version`` and, for each section (``search``,
``search_all``, ``download``), a list of entries. Entries are sorted by key, to get
readable diffs:

.. code-block:: yaml

    version: 1
    search:
      - params: {collection: S2_MSI_L1C, limit: 5}   # parameters actually passed
        result:
          number_matched: null
          errors: []
          products:
            - provider: ...
              collection: ...
              geometry: <WKT>
              search_intersection: <WKT or null>
              properties: {...}
        # or, if the call raised: raises: {type: RequestError, message: ...}
    download:
      - params: {provider: ..., id: ...}
        result: {path: <relative to the archive directory>}
"""

from __future__ import annotations

import copy
import enum
import inspect
import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import yaml
from shapely import wkt as shapely_wkt
from shapely.geometry.base import BaseGeometry

from eodag.api.product import EOProduct
from eodag.api.search_result import SearchResult
from eodag.utils import exceptions as eodag_exc
from eodag.utils.recording.errors import CassetteFormatError, DuplicateKeyError

logger = logging.getLogger(__name__)

#: Current cassettes format version.
#: (Will be incremented as new :py:const:`SECTIONS` are supported, or if the serialization format
#: changes)
CASSETTE_VERSION = 1

#: Sections that are serialized in cassettes.
SECTIONS = ("search", "search_all", "download")

#: Product properties never written to cassettes.
#: (URLs are not needed for replay, and they may be temporary and thus useless anyway)
_DROPPED_PROPERTIES = frozenset({"eodag:download_link"})

#: Exceptions recorded in cassettes, indexed by class name.
#: Matching is done on the exact type (``isinstance`` cannot be used):
#: :class:`~eodag.utils.exceptions.TimeOutError` and
#: :class:`~eodag.utils.exceptions.DownloadError`, which inherit from
#: :class:`~eodag.utils.exceptions.RequestError`, are deliberately not recorded.
_RECORDABLE_EXCEPTIONS: dict[str, type[Exception]] = {
    "RequestError": eodag_exc.RequestError,
    "NotAvailableError": eodag_exc.NotAvailableError,
}


# --------------------------------------------------------------------------- #
# Normalisation / serialisation
# --------------------------------------------------------------------------- #
def normalize(value: Any) -> Any:
    """Converts ``value`` into a deterministic JSON/YAML object.

    * Geometries are transformed into a WKT
    * Dates to ISO format
    * Tuples/sets into lists
    * Dictionaries are sorted by keys -- to guarantee reproducibility

    :raises TypeError: if ``value`` cannot be serialized.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, BaseGeometry):
        return value.wkt
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return normalize(value.value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {
            str(k): normalize(v)
            for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
        }
    if isinstance(value, (set, frozenset)):
        return sorted((normalize(v) for v in value), key=lambda v: json.dumps(v))
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    if hasattr(value, "item") and callable(value.item):  # numpy scalars
        return normalize(value.item())
    raise TypeError(
        f"Value cannot be serialized for eodag cassettes: {value!r} "
        f"({type(value).__name__})"
    )


def canonical_key(params: dict[str, Any]) -> str:
    """Builds the matching key: canonical JSON of the normalized parameters."""
    return json.dumps(
        normalize(params), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def bind_passed_params(func: Callable, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Binds arguments *actually passed* to names from the signature.

    Default values are not applied: ``search(a=1)`` and ``search(a=1, page=1)`` give
    different keys, while ``search(1)`` and ``search(page=1)`` give the exact same key.
    ``**kwargs`` are flattened.  ``self`` is ignored.
    """
    sig = inspect.signature(func)
    bound = sig.bind(*args, **kwargs)
    params: dict[str, Any] = {}
    for name, value in bound.arguments.items():
        kind = sig.parameters[name].kind
        if kind is inspect.Parameter.VAR_KEYWORD:
            params.update(value)
        elif kind is inspect.Parameter.VAR_POSITIONAL:
            params[name] = list(value)
        else:
            params[name] = value
    params.pop("self", None)
    return params


def encode_exception(exc: BaseException) -> dict[str, Any] | None:
    """
    Encodes an exception into a serializable dictionary.

    Returns ``None`` if the exception shall not be recorded (e.g. a timeout). Only the
    types of :py:const:`_RECORDABLE_EXCEPTIONS` are recorded, compared on their exact
    type: :class:`~eodag.utils.exceptions.TimeOutError` and
    :class:`~eodag.utils.exceptions.DownloadError` inherit from
    :class:`~eodag.utils.exceptions.RequestError` but are not recorded.
    """
    name = type(exc).__name__
    if _RECORDABLE_EXCEPTIONS.get(name) is not type(exc):
        return None
    encoded: dict[str, Any] = {"type": name, "message": str(exc)}
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        encoded["status_code"] = status_code
    return encoded


def decode_exception(encoded: dict[str, Any]) -> Exception:
    """Decodes back an exception from a dictionary.

    :raises CassetteFormatError: if the exception type is not a recordable one.
    """
    cls = _RECORDABLE_EXCEPTIONS.get(encoded["type"])
    if cls is None:
        raise CassetteFormatError(
            f"Unknown exception type in cassette: {encoded['type']!r}"
        )
    exc = cls(encoded.get("message", ""))
    if "status_code" in encoded:
        setattr(exc, "status_code", encoded["status_code"])
    return exc


def _encode_product(product: EOProduct) -> dict[str, Any]:
    """
    Encodes an :class:`eodag.api.product._product.EOProduct` into a dictionary ready for
    YAML serialization.

    Discards :py:const:`_DROPPED_PROPERTIES` properties. ``collection`` and
    ``search_intersection`` are stored explicitly, see :func:`_decode_product` for why.

    .. note::

        :func:`SearchResult.from_dict` and :func:`EOProduct.from_dict` exist, but they
        go through a STAC validation that transforms properties. A dedicated and
        minimalist serialization is used instead.
    """
    intersection = getattr(product, "search_intersection", None)
    properties = {
        k: v for k, v in product.properties.items() if k not in _DROPPED_PROPERTIES
    }
    return {
        "provider": product.provider,
        "collection": product.collection,
        "geometry": product.geometry.wkt if product.geometry is not None else None,
        "search_intersection": intersection.wkt if intersection is not None else None,
        "properties": normalize(properties),
    }


def _decode_product(data: dict[str, Any]) -> EOProduct:
    """
    Decodes back an :class:`eodag.api.product._product.EOProduct` from a dictionary.

    The product is rebuilt with ``EOProduct(provider, {**properties, "geometry": wkt})``
    and then:

    * ``collection`` is passed explicitly: the ``EOProduct`` constructor removes it from
      the properties and stores it as a separate attribute.
    * ``search_intersection`` is restored manually after construction (it can be
      ``None``): the constructor only computes it if ``geometry`` is given in its
      keyword arguments.
    """
    properties = copy.deepcopy(data["properties"])
    properties["geometry"] = data["geometry"]
    product = EOProduct(data["provider"], properties, collection=data.get("collection"))
    intersection = data.get("search_intersection")
    product.search_intersection = (
        shapely_wkt.loads(intersection) if intersection else None
    )
    return product


def encode_search_result(result: SearchResult) -> dict[str, Any]:
    """
    Encodes an :class:`eodag.api.search_result.SearchResult` into a dictionary ready for
    YAML serialization.

    Discards :py:const:`_DROPPED_PROPERTIES` properties from
    :class:`eodag.api.product._product.EOProduct`, and encodes any
    :py:const:`_RECORDABLE_EXCEPTIONS`.
    """
    errors = []
    for provider, exc in getattr(result, "errors", None) or []:
        encoded = encode_exception(exc)
        if encoded is None:
            logger.debug("Unrecordable error ignored: %r", exc)
            continue
        errors.append({"provider": provider, **encoded})
    return {
        "number_matched": result.number_matched,
        "errors": errors,
        "products": [_encode_product(p) for p in result],
    }


def decode_search_result(data: dict[str, Any]) -> SearchResult:
    """
    Decodes back a :class:`eodag.api.search_result.SearchResult` from a dictionary.
    """
    logger.debug("└─> emulated")
    errors = [
        (e.get("provider"), decode_exception(e)) for e in data.get("errors") or []
    ]
    return SearchResult(
        [_decode_product(p) for p in data["products"]],
        number_matched=data.get("number_matched"),
        errors=errors,
    )


# --------------------------------------------------------------------------- #
# Cassette
# --------------------------------------------------------------------------- #
class _Dumper(yaml.SafeDumper):
    """YAML dumper that never emits anchors/aliases, which would make cassettes hard to
    read and to diff."""

    def ignore_aliases(self, data: Any) -> bool:
        """Never use anchors/aliases, even for objects shared between entries."""
        return True


class Cassette:
    """YAML record file: one map ``key -> value`` per section."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.entries: dict[str, dict[str, dict[str, Any]]] = {s: {} for s in SECTIONS}

    def __repr__(self) -> str:
        return f"Cassette({self.path})"

    @classmethod
    def load(cls, path: str | Path) -> "Cassette":
        """
        :class:`Cassette` factory.

        Either creates a new and empty cassette if the file does not exist, or loads the
        existing YAML cassette at the specified location.

        :raises CassetteFormatError:
            - if the YAML is invalid,
            - or if elements (like exceptions cannot be decoded),
            - or if the version doesn't match the currently supported
              :py:const:`CASSETTE_VERSION`,
            - or if unknown :py:const:`SECTIONS` are present in the cassette.

        :raises DuplicateKeyError: if a key is present twice in the cassette. Keys
            identify the entries to replay, so they need to be unique.
        """
        cassette = cls(path)
        if not cassette.path.exists():
            return cassette
        try:
            data = yaml.safe_load(cassette.path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise CassetteFormatError(f"{cassette.path}: invalid YAML ({exc})") from exc
        if not isinstance(data, dict) or data.get("version") != CASSETTE_VERSION:
            raise CassetteFormatError(
                f"{cassette.path}: version {data.get('version') if isinstance(data, dict) else '?'} "
                f"is not supported (expected: {CASSETTE_VERSION})"
            )
        unknown = set(data) - {"version", *SECTIONS}
        if unknown:
            raise CassetteFormatError(
                f"{cassette.path}: unknown sections {sorted(unknown)}"
            )
        for section in SECTIONS:
            for entry in data.get(section) or []:
                key = canonical_key(entry["params"])
                if key in cassette.entries[section]:
                    raise DuplicateKeyError(
                        f"{cassette.path}: duplicated key in section {section!r} : {key}"
                    )
                cassette.entries[section][key] = entry
        return cassette

    def add(
        self, section: str, params: dict[str, Any], payload: dict[str, Any]
    ) -> bool:
        """
        Adds an entry.

        Keys are defined by the parameters actually passed to each eodag function.

        :return: ``False``, leaving the cassette unchanged, if the key already exists
            (the first entry wins), ``True`` otherwise.
        """
        key = canonical_key(params)
        if key in self.entries[section]:
            return False
        self.entries[section][key] = {"params": normalize(params), **payload}
        return True

    def dump(self) -> None:
        """Writes the cassette on disk (entries are sorted by key, atomic write)."""
        data: dict[str, Any] = {"version": CASSETTE_VERSION}
        for section in SECTIONS:
            if self.entries[section]:
                data[section] = [
                    self.entries[section][k] for k in sorted(self.entries[section])
                ]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(
            yaml.dump(
                data,
                Dumper=_Dumper,
                sort_keys=False,
                allow_unicode=True,
                width=1_000_000,
                default_flow_style=False,
            ),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)
