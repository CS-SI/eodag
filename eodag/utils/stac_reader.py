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
import logging
import re

import concurrent.futures
import orjson
import pystac

from eodag.utils.exceptions import RequestError, STACOpenerError
from eodag.utils.http import http

logger = logging.getLogger("eodag.utils.stac_reader")


class _TextOpener:
    """Exhaust read methods for pystac.StacIO in the order defined
    in the openers list"""

    def __init__(self, timeout):
        self.openers = [self.read_local_json, self.read_http_remote_json]
        # Only used by read_http_remote_json
        self.timeout = timeout

    @staticmethod
    def read_local_json(url, as_json):
        """Read JSON local file"""
        try:
            if as_json:
                with open(url, "rb") as f:
                    return orjson.loads(f.read())
            else:
                with open(url) as f:
                    return f.read()
        except OSError:
            logger.debug("read_local_json is not the right STAC opener")
            raise STACOpenerError

    def read_http_remote_json(self, url, as_json):
        """Read JSON remote HTTP file"""
        try:
            res = http.get(url, timeout=self.timeout)
            content_type = res.headers.get("Content-Type")
            if content_type is None:
                encoding = "utf-8"
            else:
                m = re.search(r"charset\s*=\s*(\S+)", content_type, re.I)
                if m is None:
                    encoding = "utf-8"
                else:
                    encoding = m.group(1)
            content = res.content.decode(encoding)
            return orjson.loads(content) if as_json else content
        except RequestError:
            logger.debug("read_http_remote_json is not the right STAC opener")
            raise STACOpenerError

    def __call__(self, url, as_json=False):
        res = None
        while self.openers:
            try:
                res = self.openers[0](url, as_json)
            except STACOpenerError:
                # Remove the opener that just failed
                self.openers.pop(0)
            if res is not None:
                break
        if res is None:
            raise STACOpenerError(f"No opener available to open {url}")
        return res


def fetch_stac_items(
    stac_path, recursive=False, max_connections=100, timeout=HTTP_REQ_TIMEOUT
):
    """Fetch STAC item from a single item file or items from a catalog.

    :param stac_path: A STAC object filepath
    :type stac_path: str
    :param recursive: (optional) Browse recursively in child nodes if True
    :type recursive: bool
    :param max_connections: (optional) Maximum number of connections for HTTP requests
    :type max_connections: int
    :param timeout: (optional) Timeout in seconds for each internal HTTP request
    :type timeout: float
    :returns: The items found in `stac_path`
    :rtype: :class:`list`
    """

    # URI opener used by PySTAC internally, instantiated here
    # to retrieve the timeout.
    _text_opener = _TextOpener(timeout)
    pystac.StacIO.read_text = _text_opener

    stac_obj = pystac.read_file(stac_path)
    # Single STAC item
    if isinstance(stac_obj, pystac.Item):
        return [stac_obj.to_dict()]
    # STAC catalog
    elif isinstance(stac_obj, pystac.Catalog):
        return _fetch_stac_items_from_catalog(
            stac_obj, recursive, max_connections, _text_opener
        )
    else:
        raise STACOpenerError(f"{stac_path} must be a STAC catalog or a STAC item")


def _fetch_stac_items_from_catalog(cat, recursive, max_connections, _text_opener):
    """Fetch items from a STAC catalog"""
    # pystac cannot yet return links from a single file catalog, see:
    # https://github.com/stac-utils/pystac/issues/256
    extensions = getattr(cat, "stac_extensions", None)
    if extensions:
        extensions = extensions if isinstance(extensions, list) else [extensions]
        if "single-file-stac" in extensions:
            items = [feature for feature in cat.to_dict()["features"]]
            return items

    # Making the links absolutes allow for both relative and absolute links
    # to be handled.
    if not recursive:
        hrefs = [link.get_absolute_href() for link in cat.get_item_links()]
    else:
        hrefs = []
        for parent_catalog, _, _ in cat.walk():
            hrefs += [
                link.get_absolute_href() for link in parent_catalog.get_item_links()
            ]

    items = []
    if hrefs:
        logger.debug("Fetching %s items", len(hrefs))
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_connections
        ) as executor:
            future_to_href = (
                executor.submit(_text_opener, href, True) for href in hrefs
            )
            for future in concurrent.futures.as_completed(future_to_href):
                item = future.result()
                if item:
                    items.append(future.result())
    return items
