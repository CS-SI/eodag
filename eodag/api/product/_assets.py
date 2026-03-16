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
from typing import TYPE_CHECKING, Any, Optional, Tuple, Union, cast

from typing_extensions import override

from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    OFFLINE_STATUS,
    ONLINE_STATUS,
)
from eodag.plugins.download import StreamResponse
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    Mime,
    ProgressCallback,
)
from eodag.utils.exceptions import NotAvailableError
from eodag.utils.repr import dict_to_html_table

if TYPE_CHECKING:
    from eodag.api.product import EOProduct
    from eodag.plugins.apis import Api
    from eodag.plugins.authentication.base import Authentication
    from eodag.plugins.download import Download
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
    """

    product: EOProduct

    TECHNICAL_ASSETS = ["download_link", "quicklook", "thumbnail"]

    def __init__(self, product: EOProduct, *args: Any, **kwargs: Any) -> None:
        self.product = product
        super(AssetsDict, self).__init__(*args, **kwargs)

    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        if not self._pre_check(key, value):
            return
        super().__setitem__(key, Asset(self.product, key, value))
        self.sort()
        self._post_check()

    @override
    def update(self, value: Union[dict[str, Any], AssetsDict]) -> None:  # type: ignore
        """Used to self update with exernal value"""
        buffer: dict[str, Any] = {}
        for key in value:
            if self._pre_check(key, value[key]):
                if isinstance(value[key], dict):
                    asset = Asset(self.product, key=key)
                    asset.update(value[key])
                    buffer[key] = asset
                else:
                    buffer[key] = value[key]
        super().update(buffer)
        self.sort()
        self._post_check()

    def _target_url(self, asset):
        target_url = None
        if "href" in asset:
            target_url = asset["href"]
        elif "order_link" in asset:
            target_url = asset["order_link"]
        return target_url

    def _pre_check(self, asset_key: str, asset_values: dict[str, Any]) -> bool:
        # Asset must have href or order_link
        href = None
        if "href" in asset_values:
            href = asset_values.pop("href")
        if href not in [None, "", NOT_AVAILABLE]:
            asset_values["href"] = href
        order_link = None
        if "order_link" in asset_values:
            order_link = asset_values.pop("order_link")
        if order_link not in [None, "", NOT_AVAILABLE]:
            asset_values["order_link"] = order_link

        if "href" not in asset_values and "order_link" not in asset_values:
            logger.debug(
                "asset '{}' skipped ignored because neither href nor order_link is available".format(
                    asset_key
                ),
            )
            return False

        assets = self.as_dict()
        used_urls = []
        for key in assets:
            if key == asset_key:
                # Duplicated key
                return False
            used_urls.append(self._target_url(assets[key]))

        # Prevent asset key / asset target url replication (out from technical ones)
        # thumbnail and quicklook can share same url
        url = self._target_url(asset_values)
        if asset_key not in AssetsDict.TECHNICAL_ASSETS and (url in used_urls):
            # Duplicated url
            logger.debug("Exclude asset {}: duplicated url".format(key))
            return False

        return True

    def _post_check(self):

        # When technical asset are added after asets, could have some url duplication
        assets = self.as_dict()
        used_urls = []
        buffer = {}
        update = False
        for key in assets:
            url = self._target_url(assets[key])
            if key in AssetsDict.TECHNICAL_ASSETS:
                used_urls.append(url)
                buffer[key] = assets[key]
            else:
                if url not in used_urls:
                    used_urls.append(url)
                    buffer[key] = assets[key]
                else:
                    # Duplicated url
                    logger.debug("Exclude asset {}: duplicated url".format(key))
                    update = True
        if update:
            super().update(buffer)

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
    """

    product: EOProduct

    # File
    size: Optional[int]
    filename: Optional[str]

    def __init__(self, product: EOProduct, key: str, *args: Any, **kwargs: Any) -> None:
        self.product = product
        self.key = key
        self.size = None
        self.filename = None
        self.auth_checked = False
        super(Asset, self).__init__(*args, **kwargs)
        self._update()

    def __setitem__(self, key, item):
        if key == "order:status" and item == OFFLINE_STATUS:
            # Disable href when not online
            # order:status OFFLINE mean have to use order_link
            super().__setitem__("href", "")
        super().__setitem__(key, item)
        self._update()

    def _update(self):
        title = self.get("title", None)
        if title is None:
            super().__setitem__("title", self.key)

        # Order link behaviour require order:status state
        href = self.get("href", None)
        if href is None:
            super().__setitem__("href", "")
            href = ""

        if href != "":
            # With order behaviour, href can be fill later
            content_type = self.get("type", None)
            if content_type is None:
                super().__setitem__("type", Mime.guess_file_type(href))

        asset = self.as_dict()
        orderstatus = self.get("order:status", None)
        if "order_link" not in asset and orderstatus is None:
            # Nothing orderable
            super().__setitem__("order:status", OFFLINE_STATUS)
        else:
            if href == "":
                super().__setitem__("order:status", OFFLINE_STATUS)
            else:
                # If href is defined, no need to order
                super().__setitem__("order:status", ONLINE_STATUS)

    def as_dict(self) -> dict[str, Any]:
        """Builds a representation of Asset to enable its serialization

        :returns: The representation of a :class:`~eodag.api.product._assets.Asset` as a
                  Python dict
        """
        return self.data

    def download(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        no_cache: bool = False,
        **kwargs: Unpack[DownloadConf],
    ) -> Optional[str]:
        """Download the asset as local_file

        :param Optional[ProgressCallback] progress_callback: Used to manage progress bar in console
        :param float wait: (optional) on fails, time in minutes to wait before retry
        :param float timeout: (optional) Total time in minute before timeout
        :param kwargs: `output_dir` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :returns str|None: local_path
        """

        return self._download(  # type: ignore
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
            stream=False,
            no_cache=no_cache,
            **kwargs,
        )

    def stream_download(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        no_cache: bool = False,
        **kwargs: Unpack[DownloadConf],
    ) -> StreamResponse:
        """Download the asset as StreamResponse

        :param Optional[ProgressCallback] progress_callback: Used to manage progress bar in console
        :param float wait: (optional) on fails, time in minutes to wait before retry
        :param float timeout: (optional) Total time in minute before timeout
        :param kwargs: `output_dir` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :returns StreamResponse:
        """
        return self._download(  # type: ignore
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
            no_cache=no_cache,
            stream=True,
            **kwargs,
        )

    def _download(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        stream: bool = False,
        **kwargs: Unpack[DownloadConf],
    ) -> Union[Optional[str], StreamResponse]:
        """Download the EO product asset using the provided download plugin and the
        authenticator if necessary.

        The actual download occurs only at the first call of this method.
        A side effect of this method is that it changes the ``location``
        attribute of an EOProduct, from its remote address to the local address.
        :param progress_callback: (optional) A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :param wait: (optional) If download fails, wait time in minutes between
                     two download tries
        :param timeout: (optional) If download fails, maximum time in minutes
                        before stop retrying to download
        :param kwargs: `output_dir` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :returns: The absolute path to the downloaded asset on the local filesystem
        :raises: :class:`~eodag.utils.exceptions.PluginImplementationError`
        :raises: :class:`RuntimeError`
        """

        downloader, authenticator = self.get_downloader_and_auth()

        # Check downloader
        if downloader is None:
            raise RuntimeError(
                "Asset is unable to download itself due to lacking of a download plugin in it's product"
            )

        # Check authenticator
        auth = None
        if authenticator is not None:
            auth = authenticator.authenticate()

        # Init progress bar init
        close_progress_callback = False
        if progress_callback is None:
            if stream:
                progress_callback = ProgressCallback(disable=True)
            else:
                progress_callback = ProgressCallback(position=1)
                # one shot progress callback to close after download
                close_progress_callback = True
        else:
            close_progress_callback = False
            progress_callback.pos = 1
            # update units as bar may have been previously used for extraction
            progress_callback.unit = "B"
            progress_callback.unit_scale = True
        progress_callback.desc = "{}:{}".format(
            self.product.properties.get("id", ""), self.get("title", "")
        )
        progress_callback.refresh()

        # Download
        error = None
        try:
            result = downloader.download(
                self,  # type: ignore[arg-type]
                auth=auth,
                progress_callback=progress_callback,
                wait=wait,
                timeout=timeout,
                stream=stream,
                **kwargs,
            )
            if not stream:
                result = cast(Optional[str], result)
            else:
                result = cast(StreamResponse, result)
        except Exception as e:
            error = e

        if error is not None:
            raise error

        # Dispose progress bar
        if close_progress_callback:
            progress_callback.close()

        return result

    def get_downloader_and_auth(
        self,
    ) -> Tuple[Optional[Union[Api, Download]], Optional[Authentication]]:
        """Compute downloader and authenticator from plugin manager"""
        downloader: Optional[Union[Api, Download]] = None
        authenticator: Optional[Authentication] = None

        if self.product is not None and self.product.plugins_manager is not None:
            downloader = self.product.plugins_manager.get_download_plugin(
                self.product.provider
            )
            authenticator = self.product.plugins_manager.get_auth_plugin(downloader, self)  # type: ignore

        return downloader, authenticator

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


__all__ = ["Asset", "AssetsDict"]
