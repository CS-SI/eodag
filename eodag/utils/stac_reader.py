# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, http://www.c-s.fr
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
import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import concurrent.futures
from jsonpath_ng.ext import parse

logger = logging.getLogger("eodag.utils.stac_reader")


HTTP_REQ_TIMEOUT = 5


def read_local_json(json_path):
    """Read JSON local file
    """
    with open(json_path, "r") as fh:
        return json.load(fh)


def read_http_remote_json(url):
    """Read JSON remote HTTP file
    """
    res = urlopen(url, timeout=HTTP_REQ_TIMEOUT)
    content_type = res.getheader("Content-Type")

    if content_type is None:
        encoding = "utf-8"
    else:
        m = re.search(r"charset\s*=\s*(\S+)", content_type, re.I)
        if m is None:
            encoding = "utf-8"
        else:
            encoding = m.group(1)
    return json.loads(res.read().decode(encoding))


class CatalogOpener(object):
    """Opener manager
    """

    def __init__(self, opener_list):
        self.opener_list = opener_list

    def read(self, url, available_openers=[]):
        """Read file using opener

        Openers try priority is defined by order in list
        """
        try:
            if not available_openers:
                available_openers = self.opener_list.copy()
            return available_openers[0](url)
        # reading errors for used openers: add more if needed
        except FileNotFoundError:
            # set lowest priority to current opener
            oldindex = self.opener_list.index(available_openers[0])
            newindex = len(self.opener_list) - 1
            self.opener_list.insert(newindex, self.opener_list.pop(oldindex))
            # do not use current downloader on next try
            available_openers.remove(available_openers[0])
            # try again
            return self.read(url, available_openers=available_openers)
        except IndexError:
            logger.error("No opener available to open %s" % url)
            return None
        except (HTTPError, URLError) as e:
            logger.error("%s: %s", url, e)
            return None


def fetch_stac_items(catalog_path, recursive=False, max_connections=100, opener=None):
    """Fetch STAC items from given catalog
    """
    opener = CatalogOpener(opener_list=[read_local_json, read_http_remote_json]).read

    items = []
    # fetch item in catalog_path
    items += _fetch_stac_item_from_content(catalog_path, opener)

    # fetch items in catalog_path
    items += _fetch_stac_items_from_content(catalog_path, opener)

    # fetch items from links
    item_urls = _fetch_stac_item_links(catalog_path, opener=opener)
    if item_urls:
        logger.debug("Fetching %s items from %s", len(item_urls), catalog_path)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_connections
        ) as executor:
            future_to_url = (executor.submit(opener, url) for url in item_urls)
            for future in concurrent.futures.as_completed(future_to_url):
                item = future.result()
                if item:
                    items.append(future.result())

    # fetch items recursively in children
    if recursive:
        child_links = _fetch_stac_child_links(catalog_path, opener=opener)
        for link in child_links:
            items += fetch_stac_items(link, recursive=True, opener=opener)

    logger.debug("Found %s items in %s", len(items), catalog_path)

    return items


def _fetch_stac_with_jsonpath(catalog_path, opener, expression):
    """Fetch JSON elements with a JSONPath expression.
    """
    json_data = opener(catalog_path)
    jsonpath_expression = parse(expression)
    res_jp = [match.value for match in jsonpath_expression.find(json_data)]
    return res_jp


def _fetch_stac_item_links(catalog_path, opener):
    """Fetch STAC item links from given catalog
    """
    return _fetch_stac_with_jsonpath(catalog_path, opener, 'links[?rel = "item"].href')


def _fetch_stac_child_links(catalog_path, opener):
    """Fetch STAC child links from given catalog
    """
    return _fetch_stac_with_jsonpath(catalog_path, opener, 'links[?rel = "child"].href')


def _fetch_stac_items_from_content(catalog_path, opener):
    """Fetch STAC items from given FeatureCollection
    """
    return _fetch_stac_with_jsonpath(catalog_path, opener, 'links[?type = "Feature"]')


def _fetch_stac_item_from_content(catalog_path, opener):
    """Fetch STAC item from given feature
    """
    # This JSONPATH '$[?($.type == "Feature")]' didn't work (returned [])
    # with jsonpath-ng while it should indeed return the object if it
    # has "type": "Feature". It's actually just a simple key:value check.
    json_content = opener(catalog_path)
    if json_content.get("type") == "Feature":
        return [json_content]
    else:
        return []
