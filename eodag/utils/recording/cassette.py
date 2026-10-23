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

#: Sections that will be serialized in Cassettes.
SECTIONS = ("search", "search_all", "download")

#: Product properties never written down in cassettes.
#: (e.g. we don't need URLs for replay, also they could be temporary, and thus completly useless in
#: replay situations)
_DROPPED_PROPERTIES = frozenset({"eodag:download_link"})

#: Registered exceptions.
#: (Matching is done on the exact type; :class:`eodag.utils.exceptions.TimeOutError` and
#: :class:`eodag.utils.exceptions.DownloadError` which inherit
#: :class:`eodag.utils.exceptions.RequestError` are voluntarilly not recorded)
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
    * Dictionaries are sorted by keys -- to guarantee reproductibility
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
    """Matching key: Canonical JSON of normallized parameters"""
    return json.dumps(
        normalize(params), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def bind_passed_params(func: Callable, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Binds arguments *actually passed* to names from the signature.

    Default values are not applied: ``search(a=1)`` and ``search(a=1, page=1)`` given
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
    Encodes the exceptions into a serializable dictionary.
    Returns None if the exception shall not be registered (e.g.: timeout).
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
    """Decode back an exception from a dictionary."""
    cls = _RECORDABLE_EXCEPTIONS.get(encoded["type"])
    if cls is None:
        raise CassetteFormatError(
            f"Unknown exception type in cassette: {encoded['type']!r}"
        )
    exc = cls(encoded.get("message", ""))
    if "status_code" in encoded:
        exc.status_code = encoded["status_code"]  # type: ignore[attr-defined]
    return exc


def _encode_product(product: EOProduct) -> dict[str, Any]:
    """
    Encodes an :class:`eodag.api.product._product.EOProduct` into a dictionary ready for
    YAML serialization.

    Discards :py:const:`_DROPPED_PROPERTIES` properties.

    .. note::

        :func:`SearchResult.from_dict` and :func:`EOProduct.from_dict` exist, but they
        do through a STAC validation that transforms properties.  Instead we use here a
        dedicated and minimalist serialization and a real
        ``EOProduct(provider, {**properties, "geometry": wkt})``

    .. note::

        :class:`EOProduct <eodag.api.product._product.EOProduct>` constructor removes
        ``collection`` from properties and stores it as a different attribute. As a
        consequence, we have to store it explicitly.

    .. note::

        ``search_intersection``is recomputed at construction only if we pass
        ``geometry=`` in ``kwargs``. We have to restore it manually after construction
        (it could be ``None``)

    .. note::

        :class:`RequestError`, :class:`NotAvailableError`, :class:`TimeOutError` and
        :class:`DownloadError` are distinct. However :class:`TimeOutError` and
        :class:`DownloadError` inherit from :class:`RequestError`.
        As a consequence, a direct type comparison is required (with a with list
        ``{RequestError, NotAvailableError}``), we cannot use ``isinstance``.
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
    def ignore_aliases(self, data: Any) -> bool:  # no d'anchor/YAML alias
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

        Either creates a new and empty cassette at the specified location, or load an
        existing (YAML) casette at the specified location.

        :raises CassetteFormatError:
            - if the YAML is invalid,
            - or if elements (like exceptions cannot be decoded),
            - or if the version doesn't match the currently supported
              :py:const:`CASSETTE_VERSION`,
            - or if unknown :py:const:`SECTIONS` are present in the cassette.

        :raises DuplicateKeyError: if a key is present twice in the cassette. As keys
            permit to identity *things* to replay, they need to be unique.
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
                f"is not supported (excepted : {CASSETTE_VERSION})"
            )
        unknown = set(data) - {"version", *SECTIONS}
        if unknown:
            raise CassetteFormatError(
                f"{cassette.path}: unkonwn sections {sorted(unknown)}"
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
        Add an entry ; ignore (False) if key already exists (the first wins).

        Keys are defined by the parameters actually passed to each eodag function.
        """
        key = canonical_key(params)
        if key in self.entries[section]:
            return False
        self.entries[section][key] = {"params": normalize(params), **payload}
        return True

    def dump(self) -> None:
        """Write cassette on disk (entries are sorted by key, atomic write)."""
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
