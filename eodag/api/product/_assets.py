# -*- coding: utf-8 -*-
# Copyright 2023, CS GROUP - France, https://www.csgroup.eu/
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
from collections import UserDict
from typing import TYPE_CHECKING, Any, Optional

from typing_extensions import override

from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    OFFLINE_STATUS,
    ONLINE_STATUS,
)
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    guess_file_type,
    path_to_uri,
    uri_to_path,
)
from eodag.utils.exceptions import NotAvailableError
from eodag.utils.repr import dict_to_html_table

if TYPE_CHECKING:
    import datetime as dt

    import requests

    from eodag.api.product import EOProduct
    from eodag.types.download_args import DownloadConf
    from eodag.utils import StreamResponse, Unpack

logger = logging.getLogger("eodag.api.product.assets")

TECHNICAL_ASSET_KEYS: tuple[str, ...] = ("download_link", "quicklook", "thumbnail")


class AssetsDict(UserDict):
    """A UserDict object which values are :class:`~eodag.api.product._assets.Asset`
    contained in a :class:`~eodag.api.product._product.EOProduct` resulting from a
    search.

    :param product: Product resulting from a search
    :param args: (optional) Arguments used to init the dictionary
    :param kwargs: (optional) Additional named-arguments used to init the dictionary

    Example
    -------

    >>> from eodag.api.product import EOProduct
    >>> product = EOProduct(
    ...     provider="foo",
    ...     properties={"id": "bar", "geometry": "POINT (0 0)"}
    ... )
    >>> from eodag.api.product._assets import AssetsDict
    >>> isinstance(product.assets, AssetsDict)
    True
    >>> product.assets.update({"foo": {"href": "http://somewhere/something"}})
    >>> product.assets
    {'foo': {'href': 'http://somewhere/something', 'title': 'foo', 'type': 'application/octet-stream'}}
    """

    product: EOProduct

    def __init__(self, product: EOProduct, *args: Any, **kwargs: Any) -> None:
        self.product = product
        super(AssetsDict, self).__init__(*args, **kwargs)

    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        if not self._check(key, value):
            return
        super().__setitem__(key, self._make_asset(key, value))
        self.sort()

    def _make_asset(self, key: str, value: dict[str, Any]) -> Asset:
        """Build the :class:`Asset` to store for the given key/value pair.

        Subclasses (e.g. eodag_cube) can override this to use an extended
        :class:`Asset` subclass without duplicating the sorting and other
        logic implemented in :meth:`__setitem__`/:meth:`update`.

        :param key: Asset key
        :param value: Already-validated asset dictionary
        :returns: The :class:`Asset` instance to store
        """
        return Asset(self.product, key, value)

    @override
    def update(self, *args: Any, **kwargs: Any) -> None:
        """Used to self update with external value"""
        incoming = {k: v for k, v in dict(*args, **kwargs).items() if self._check(k, v)}

        if not incoming:
            return

        if type(self).__setitem__ is not AssetsDict.__setitem__:
            # Preserve custom __setitem__ behavior implemented by subclasses.
            super().update(incoming)
        else:
            # Avoid sorting after every insertion in the base implementation.
            for key, value in incoming.items():
                self.data[key] = self._make_asset(key, value)
        self.sort()

    def order(
        self,
        asset_filter: str = "",
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
    ) -> None:
        """Order the assets matching the given filter that are not online yet, and
        poll their status until they become available.

        :param asset_filter: (optional) regex filter on asset keys; all assets if empty
        :param wait: (optional) Wait time in minutes between two order status checks
        :param timeout: (optional) Maximum time in minutes before stop checking order status
        """
        for asset in self.get_values(asset_filter):
            asset.order(wait=wait, timeout=timeout)

    def _check(self, asset_key: str, asset_value: dict[str, Any]) -> bool:
        """Validate an asset before insertion.

        Checks that the asset has a valid ``href`` or ``eodag:order_link`` and that its
        URL is not already used by another (non-technical) asset.  Mutates
        *asset_value* in place by stripping empty/unavailable href/eodag:order_link entries.

        :param asset_key: Key under which the asset will be stored
        :param asset_value: Mutable asset dictionary (modified in place)
        :returns: ``True`` if the asset is valid and can be inserted, ``False`` otherwise
        """
        # Asset must have href or eodag:order_link
        href = asset_value.pop("href", None)
        if href not in [None, "", NOT_AVAILABLE]:
            asset_value["href"] = href
        order_link = asset_value.pop("eodag:order_link", None)
        if order_link not in [None, "", NOT_AVAILABLE]:
            asset_value["eodag:order_link"] = order_link

        if "href" not in asset_value and "eodag:order_link" not in asset_value:
            logger.warning(
                "asset '{}' skipped ignored because neither href nor eodag:order_link is available".format(
                    asset_key
                ),
            )
            return False

        def target_url(asset: dict[str, Any]) -> Optional[str]:
            return asset.get("href") or asset.get("eodag:order_link")

        assets = self.as_dict()
        used_urls = [
            target_url(asset) for key, asset in assets.items() if key != asset_key
        ]

        # Prevent asset key / asset target url replication (out from technical ones)
        # thumbnail and quicklook can share same url
        url = target_url(asset_value)
        if asset_key not in TECHNICAL_ASSET_KEYS and (url in used_urls):
            # Duplicated url
            return False

        return True

    @staticmethod
    def _remove_private_fields(asset: Asset) -> None:
        """Delete private asset fields (fields starting with '_')"""
        for private_field in [key for key in asset if key.startswith("_")]:
            del asset[private_field]

    def sort(self):
        """Used to self sort"""
        sorted_assets = {}
        # Keep technical assets first
        for key in TECHNICAL_ASSET_KEYS:
            if key in self.data:
                asset = self.data.pop(key)
                self._remove_private_fields(asset)
                sorted_assets[key] = asset

        # Sort and add others
        for key in sorted(self.data):
            asset = self.data[key]
            self._remove_private_fields(asset)
            sorted_assets[key] = asset
        self.data = sorted_assets

    def as_dict(self) -> dict[str, Any]:
        """Builds a representation of AssetsDict to enable its serialization

        :returns: The representation of a :class:`~eodag.api.product._assets.AssetsDict`
                  as a Python dict
        """
        return {k: v.as_dict() for k, v in self.data.items()}

    def get_values(self, asset_filter: str = "", regex=True) -> list[Asset]:
        """
        retrieves the assets matching the given filter

        :param asset_filter: regex filter with which the assets should be matched
        :param regex: Uses regex to match the asset key or simply compare strings
        :return: list of assets
        """
        if not asset_filter:
            return [a for a in self.values() if "href" in a]

        if regex:
            filter_regex = re.compile(asset_filter)
            assets_keys = [k for k in self.keys() if filter_regex.fullmatch(k)]
        else:
            assets_keys = [k for k in self.keys() if k == asset_filter]

        assets_values = [
            a
            for k in assets_keys
            for a in [self.get(k)]
            if isinstance(a, Asset) and "href" in a
        ]

        if assets_values:
            return assets_values
        if regex:
            # retry without regex
            return self.get_values(asset_filter, regex=False)
        raise NotAvailableError(
            rf"No asset key matching re.fullmatch(r'{asset_filter}') was found in {self.product}"
        )

    def _repr_html_(self, embeded=False):
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                {type(self).__name__}&ensp;({len(self)})
                </td></tr></thead>
            """
            if not embeded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embeded else ""
        return (
            f"<table>{thead}"
            + "".join([f"""<tr {tr_style}><td style='text-align: left;'>
                <details><summary style='color: grey;'>
                    <span style='color: black'>'{k}'</span>:&ensp;
                    {{
                        {"'roles': '<span style='color: black'>" + str(v['roles']) + "</span>',&ensp;"
                         if v.get("roles") else ""}
                        {"'type': '" + str(v['type']) + "',&ensp;"
                         if v.get("type") else ""}
                        {"'title': '<span style='color: black'>" + str(v['title']) + "</span>',&ensp;"
                         if v.get("title") else ""}
                        ...
                    }}
                </summary>
                    {dict_to_html_table(v, depth=2)}
                </details>
                </td></tr>
                """ for k, v in self.items()])
            + "</table>"
        )


class Asset(UserDict):
    """A UserDict object containg one of the
    :attr:`~eodag.api.product._product.EOProduct.assets` resulting from a search.

    :param product: Product resulting from a search
    :param key: asset key
    :param args: (optional) Arguments used to init the dictionary
    :param kwargs: (optional) Additional named-arguments used to init the dictionary

    Example
    -------

    >>> from eodag.api.product import EOProduct
    >>> product = EOProduct(
    ...     provider="foo",
    ...     properties={"id": "bar", "geometry": "POINT (0 0)"}
    ... )
    >>> product.assets.update({"foo": {"href": "http://somewhere/something"}})
    >>> from eodag.api.product._assets import Asset
    >>> isinstance(product.assets["foo"], Asset)
    True
    >>> product.assets["foo"]
    {'href': 'http://somewhere/something', 'title': 'foo', 'type': 'application/octet-stream'}
    """

    product: EOProduct

    # Transient download state, not serialized (persistent state is stored in STAC fields
    # like ``file:size``, ``file:local_path`` or ``order:status``)
    filename: Optional[str]
    rel_path: str
    next_try: dt.datetime
    _stream: requests.Response

    def __init__(self, product: EOProduct, key: str, *args: Any, **kwargs: Any) -> None:
        self.product = product
        self.key = key
        # Faster than UserDict.__init__, which goes through MutableMapping.update()
        self.data = dict(*args, **kwargs)
        self._update()

    def __setitem__(self, key, item):
        super().__setitem__(key, item)
        self._update()

    @property
    def remote_location(self) -> str:
        """Remote location of the asset, alias of its ``href``"""
        return self.data.get("href", "")

    @remote_location.setter
    def remote_location(self, value: str) -> None:
        self["href"] = value

    @property
    def location(self) -> str:
        """Local location of the asset as URI if downloaded (``file:local_path``),
        otherwise its ``href``"""
        if local_path := self.data.get("file:local_path"):
            return path_to_uri(local_path)
        return self.remote_location

    @location.setter
    def location(self, value: str) -> None:
        if value.startswith("file:"):
            self["file:local_path"] = uri_to_path(value)
        else:
            self.data.pop("file:local_path", None)
            self.remote_location = value

    def _update(self):
        """Normalize asset fields.

        Fills in default ``title``, ``href``, ``order:status`` and ``type`` entries
        when missing.
        """

        title = self.get("title")
        if title is None:
            super().__setitem__("title", self.key)

        # Order link behaviour require order:status state
        orderlink = self.get("eodag:order_link")
        orderstatus = self.get("order:status")
        if orderlink is not None and orderstatus is None:
            super().__setitem__("order:status", OFFLINE_STATUS)

        href = self.get("href")
        if href is None:
            super().__setitem__("href", "")
            href = ""

        if href != "":
            # With order behaviour, href can be fill later
            content_type = self.get("type")
            if content_type is None:
                super().__setitem__("type", guess_file_type(href))

    def as_dict(self) -> dict[str, Any]:
        """Builds a representation of Asset to enable its serialization

        :returns: The representation of a :class:`~eodag.api.product._assets.Asset` as a
                  Python dict
        """
        return self.data

    def download(self, **kwargs: Unpack[DownloadConf]) -> str:
        """Downloads a single asset

        :param kwargs: (optional) Additional named-arguments passed to `plugin.download()`
        :returns: The absolute path to the downloaded product on the local filesystem
        """
        kwargs["asset"] = self.key
        return self.product.download(**kwargs)

    def stream_download(self, **kwargs: Unpack[DownloadConf]) -> StreamResponse:
        """Downloads a single asset as StreamResponse

        :param kwargs: (optional) Additional named-arguments passed to `plugin.download()`
        :returns: StreamResponse stream representation of the asset file
        """
        kwargs["asset"] = self.key
        return self.product.stream_download(**kwargs)

    def order(
        self,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
    ) -> None:
        """Order the asset if it is not online yet, and poll its status until it becomes
        available.

        :param wait: (optional) Wait time in minutes between two order status checks
        :param timeout: (optional) Maximum time in minutes before stop checking order status
        :raises: :class:`RuntimeError` if no download plugin is registered on the product
        :raises: :class:`NotImplementedError` if the download plugin does not support ordering
        """
        if self.get("order:status", ONLINE_STATUS) == ONLINE_STATUS:
            return
        downloader = self.product.downloader
        if downloader is None:
            raise RuntimeError(
                f"{self.product} asset {self.key} is unable to order itself due to "
                "lacking of a download plugin"
            )
        if (order := getattr(downloader, "order", None)) is None:
            raise NotImplementedError(
                f"{type(downloader).__name__} plugin does not support ordering"
            )
        downloader_auth = self.product.downloader_auth
        auth = downloader_auth.authenticate() if downloader_auth else None
        order(self.product, auth, wait=wait, timeout=timeout, asset=self.key)

    def _repr_html_(self):
        thead = f"""<thead><tr><td style='text-align: left; color: grey;'>
            {type(self).__name__}&ensp;-&ensp;{self.key}
            </td></tr></thead>
        """
        return f"""<table>{thead}
                <tr><td style='text-align: left;'>
                    {dict_to_html_table(self)}
                </details>
                </td></tr>
            </table>"""
