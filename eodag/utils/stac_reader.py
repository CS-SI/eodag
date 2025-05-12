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
from __future__ import annotations

import logging
import re
import socket
from typing import Any, Callable, Optional, Union
from urllib.error import URLError
from urllib.request import urlopen

import concurrent.futures
import orjson
import pystac
from pystac.stac_object import STACObjectType

from eodag.utils import HTTP_REQ_TIMEOUT, get_ssl_context
from eodag.utils.exceptions import STACOpenerError

logger = logging.getLogger("eodag.utils.stac_reader")


class _TextOpener:
    """Exhaust read methods for pystac.StacIO in the order defined
    in the openers list"""

    def __init__(self, timeout: int, ssl_verify: bool) -> None:
        self.openers = [self.read_local_json, self.read_http_remote_json]
        # Only used by read_http_remote_json
        self.timeout = timeout
        self.ssl_verify = ssl_verify

    @staticmethod
    def read_local_json(url: str, as_json: bool = False) -> Any:
        """Read JSON local file"""
        try:
            if as_json:
                with open(url, "rb") as f:
                    return orjson.loads(f.read())
            else:
                with open(url) as f:
                    return f.read()
        except OSError:
            raise STACOpenerError("read_local_json is not the right STAC opener")

    def read_http_remote_json(self, url: str, as_json: bool = False) -> Any:
        """Read JSON remote HTTP file"""
        ssl_ctx = get_ssl_context(self.ssl_verify)

        try:
            res = urlopen(url, timeout=self.timeout, context=ssl_ctx)
            content_type = res.getheader("Content-Type")
            if content_type is None:
                encoding = "utf-8"
            else:
                m = re.search(r"charset\s*=\s*(\S+)", content_type, re.I)
                if m is None:
                    encoding = "utf-8"
                else:
                    encoding = m.group(1)
            content = res.read().decode(encoding)
            return orjson.loads(content) if as_json else content
        except URLError as e:
            if isinstance(e.reason, socket.timeout):
                logger.error("%s: %s", url, e)
                raise socket.timeout(
                    f"{url} with a timeout of {self.timeout} seconds"
                ) from None
            else:
                raise STACOpenerError(
                    "read_http_remote_json is not the right STAC opener"
                )

    def __call__(self, url: str, as_json: bool = False) -> Any:
        openers = self.openers[:]
        res = None
        while openers:
            try:
                res = openers[0](url, as_json)
            except STACOpenerError:
                # Remove the opener that just failed
                openers.pop(0)
            if res is not None:
                break
        if res is None:
            raise STACOpenerError(f"No opener available to open {url}")
        return res


def fetch_stac_items(
    stac_path: str,
    recursive: bool = False,
    max_connections: int = 100,
    timeout: int = HTTP_REQ_TIMEOUT,
    ssl_verify: bool = True,
) -> list[dict[str, Any]]:
    """Fetch STAC item from a single item file or items from a catalog.

    :param stac_path: A STAC object filepath
    :param recursive: (optional) Browse recursively in child nodes if True
    :param max_connections: (optional) Maximum number of connections for concurrent HTTP requests
    :param timeout: (optional) Timeout in seconds for each internal HTTP request
    :param ssl_verify: (optional) SSL Verification for HTTP request
    :returns: The items found in `stac_path`
    """

    # URI opener used by PySTAC internally, instantiated here
    # to retrieve the timeout.
    _text_opener = _TextOpener(timeout, ssl_verify)
    stac_io = pystac.StacIO.default()
    stac_io.read_text = _text_opener  # type: ignore[assignment]

    stac_obj = pystac.read_file(stac_path, stac_io=stac_io)
    # Single STAC item
    if isinstance(stac_obj, pystac.Item):
        return [stac_obj.to_dict(transform_hrefs=False)]
    # STAC catalog
    elif isinstance(stac_obj, pystac.Catalog):
        return _fetch_stac_items_from_catalog(
            stac_obj, recursive, max_connections, _text_opener
        )
    else:
        raise STACOpenerError(f"{stac_path} must be a STAC catalog or a STAC item")


def _fetch_stac_items_from_catalog(
    cat: pystac.Catalog,
    recursive: bool,
    max_connections: int,
    _text_opener: Callable[[str, bool], Any],
) -> list[Any]:
    """Fetch items from a STAC catalog"""
    items: list[dict[Any, Any]] = []

    # pystac cannot yet return links from a single file catalog, see:
    # https://github.com/stac-utils/pystac/issues/256
    extensions: Optional[Union[list[str], str]] = getattr(cat, "stac_extensions", None)
    if extensions:
        extensions = extensions if isinstance(extensions, list) else [extensions]
        if "single-file-stac" in extensions:
            items = [
                feature for feature in cat.to_dict(transform_hrefs=False)["features"]
            ]
            return items

    # Making the links absolutes allow for both relative and absolute links to be handled.
    if not recursive:
        hrefs: list[Optional[str]] = [
            link.get_absolute_href() for link in cat.get_item_links()
        ]
    else:
        hrefs = []
        for parent_catalog, _, _ in cat.walk():
            hrefs += [
                link.get_absolute_href() for link in parent_catalog.get_item_links()
            ]

    if hrefs:
        logger.debug("Fetching %s items", len(hrefs))
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_connections
        ) as executor:
            future_to_href = (
                executor.submit(_text_opener, str(href), True) for href in hrefs
            )
            for future in concurrent.futures.as_completed(future_to_href):
                item = future.result()
                if item:
                    items.append(item)
    return items


def fetch_stac_collections(
    stac_path: str,
    collection: Optional[str] = None,
    max_connections: int = 100,
    timeout: int = HTTP_REQ_TIMEOUT,
    ssl_verify: bool = True,
) -> list[dict[str, Any]]:
    """Fetch STAC collection(s) from a catalog.

    :param stac_path: A STAC object filepath
    :param collection: the collection to fetch
    :param max_connections: (optional) Maximum number of connections for HTTP requests
    :param timeout: (optional) Timeout in seconds for each internal HTTP request
    :param ssl_verify: (optional) SSL Verification for HTTP request
    :returns: The collection(s) found in `stac_path`
    """

    # URI opener used by PySTAC internally, instantiated here to retrieve the timeout.
    _text_opener = _TextOpener(timeout, ssl_verify)
    stac_io = pystac.StacIO.default()
    stac_io.read_text = _text_opener  # type: ignore[assignment]

    stac_obj = pystac.read_file(stac_path, stac_io=stac_io)
    if isinstance(stac_obj, pystac.Catalog):
        return _fetch_stac_collections_from_catalog(
            stac_obj, collection, max_connections, _text_opener
        )
    else:
        raise STACOpenerError(f"{stac_path} must be a STAC catalog")


def _fetch_stac_collections_from_catalog(
    cat: pystac.Catalog,
    collection: Optional[str],
    max_connections: int,
    _text_opener: Callable[[str, bool], Any],
) -> list[Any]:
    """Fetch collections from a STAC catalog"""
    collections: list[dict[Any, Any]] = []

    # Making the links absolutes allow for both relative and absolute links to be handled.
    hrefs: list[Optional[str]] = [
        link.get_absolute_href()
        for link in cat.get_child_links()
        if collection is not None and link.title == collection
    ]
    if len(hrefs) == 0:
        hrefs = [link.get_absolute_href() for link in cat.get_child_links()]

    if hrefs:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_connections
        ) as executor:
            future_to_href = (
                executor.submit(_text_opener, str(href), True) for href in hrefs
            )
            for future in concurrent.futures.as_completed(future_to_href):
                fetched_collection = future.result()
                if (
                    fetched_collection
                    and fetched_collection["type"] == STACObjectType.COLLECTION
                    and (
                        collection is None
                        or collection is not None
                        and fetched_collection.get("id") == collection
                    )
                ):
                    collections.append(fetched_collection)
    return collections
