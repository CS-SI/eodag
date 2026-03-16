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
from typing import TYPE_CHECKING, Any, Optional, Union

from typing_extensions import override

from eodag.api.product.metadata_mapping import NOT_AVAILABLE, OFFLINE_STATUS
from eodag.utils import guess_file_type
from eodag.utils.exceptions import NotAvailableError
from eodag.utils.repr import dict_to_html_table

if TYPE_CHECKING:
    from eodag.api.product import EOProduct
    from eodag.types.download_args import DownloadConf
    from eodag.utils import Unpack

logger = logging.getLogger("eodag.api.product.assets")


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
    >>> type(product.assets)
    <class 'eodag.api.product._assets.AssetsDict'>
    >>> product.assets.update({"foo": {"href": "http://somewhere/something"}})
    >>> product.assets
    {'foo': {'href': 'http://somewhere/something'}}
    """

    product: EOProduct

    TECHNICAL_ASSETS = ["download_link", "quicklook", "thumbnail"]

    def __init__(self, product: EOProduct, *args: Any, **kwargs: Any) -> None:
        self.product = product
        super(AssetsDict, self).__init__(*args, **kwargs)

    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        if not self._check(key, value):
            return
        super().__setitem__(key, Asset(self.product, key, value))
        self.sort()

    @override
    def update(self, value: Union[dict[str, Any], AssetsDict]) -> None:  # type: ignore
        """Used to self update with exernal value"""
        buffer: dict = {}
        for key in value:
            if self._check(key, value[key]):
                buffer[key] = value[key]
        super().update(buffer)
        self.sort()

    def _check(self, asset_key: str, asset_values: dict[str, Any]) -> bool:

        # Asset must have href or order_link
        href = asset_values.pop("href", None)
        if href not in [None, "", NOT_AVAILABLE]:
            asset_values["href"] = href
        order_link = asset_values.pop("order_link", None)
        if order_link not in [None, "", NOT_AVAILABLE]:
            asset_values["order_link"] = order_link

        if "href" not in asset_values and "order_link" not in asset_values:
            logger.warning(
                "asset '{}' skipped ignored because neither href nor order_link is available".format(
                    asset_key
                ),
            )
            return False

        def target_url(asset: dict) -> Optional[str]:
            target_url = None
            if "href" in asset:
                target_url = asset["href"]
            elif "order_link" in asset:
                target_url = asset["order_link"]
            return target_url

        assets = self.as_dict()
        used_urls = []
        for key in assets:
            if key == asset_key:
                # Duplicated key
                return False
            used_urls.append(target_url(assets[key]))

        # Prevent asset key / asset target url replication (out from technical ones)
        # thumbnail and quicklook can share same url
        url = target_url(asset_values)
        if asset_key not in AssetsDict.TECHNICAL_ASSETS and (url in used_urls):
            # Duplicated url
            return False

        return True

    def sort(self):
        """Used to self sort"""
        sorted_assets = {}
        data = self.as_dict()
        # Keep technical assets first
        for key in AssetsDict.TECHNICAL_ASSETS:
            if key in data:
                sorted_assets[key] = data.pop(key)
        # Sort and add others
        data = dict(sorted(data.items()))
        for key in data:
            sorted_assets[key] = data[key]
        super().update(sorted_assets)

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
        if asset_filter:
            if regex:
                filter_regex = re.compile(asset_filter)
                assets_keys = list(self.keys())
                assets_keys = list(filter(filter_regex.fullmatch, assets_keys))
            else:
                assets_keys = [a for a in self.keys() if a == asset_filter]
            filtered_assets = {}
            if len(assets_keys) > 0:
                filtered_assets = {a_key: self.get(a_key) for a_key in assets_keys}
            assets_values = [a for a in filtered_assets.values() if a and "href" in a]
            if not assets_values and regex:
                # retry without regex
                return self.get_values(asset_filter, regex=False)
            elif not assets_values:
                raise NotAvailableError(
                    rf"No asset key matching re.fullmatch(r'{asset_filter}') was found in {self.product}"
                )
            else:
                return assets_values
        else:
            return [a for a in self.values() if "href" in a]

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
            + "".join(
                [
                    f"""<tr {tr_style}><td style='text-align: left;'>
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
                """
                    for k, v in self.items()
                ]
            )
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
    >>> type(product.assets["foo"])
    <class 'eodag.api.product._assets.Asset'>
    >>> product.assets["foo"]
    {'href': 'http://somewhere/something'}
    """

    product: EOProduct

    # Location
    location: Optional[str]
    remote_location: Optional[str]

    # File
    size: int
    filename: Optional[str]
    rel_path: str

    def __init__(self, product: EOProduct, key: str, *args: Any, **kwargs: Any) -> None:
        self.product = product
        self.key = key
        self.location = None
        self.remote_location = None
        super(Asset, self).__init__(*args, **kwargs)
        self._update()

    def __setitem__(self, key, item):
        super().__setitem__(key, item)
        self._update()

    def _update(self):

        title = self.get("title", None)
        if title is None:
            super().__setitem__("title", self.key)

        # Order link behaviour require order:status state
        orderlink = self.get("order_link", None)
        orderstatus = self.get("order:status", None)
        if orderlink is not None and orderstatus is None:
            super().__setitem__("order:status", OFFLINE_STATUS)

        href = self.get("href", None)
        if href is None:
            super().__setitem__("href", "")
            href = ""

        if href != "":
            # Provide location and remote_location when undefined and href updated
            if self.location is None:
                self.location = href
            if self.remote_location is None:
                self.remote_location = href
            # With order behaviour, href can be fill later
            content_type = self.get("type", None)
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
        return self.product.download(asset=self.key, **kwargs)

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
