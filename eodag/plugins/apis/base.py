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
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from eodag.api.product import EOProduct
    from eodag.api.search_result import SearchResult
    from eodag.config import PluginConfig
    from eodag.utils import DownloadedCallback, ProgressCallback, Annotated

from eodag.plugins.base import PluginTopic
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_PAGE,
)

logger = logging.getLogger("eodag.apis.base")


class Api(PluginTopic):
    """Plugins API Base plugin

    An Api plugin has three download methods that it must implement:

    - ``query``: search for products
    - ``download``: download a single :class:`~eodag.api.product._product.EOProduct`
    - ``download_all``: download multiple products from a :class:`~eodag.api.search_result.SearchResult`

    The download methods must:

    - download data in the ``outputs_prefix`` folder defined in the plugin's
      configuration or passed through kwargs
    - extract products from their archive (if relevant) if ``extract`` is set to True
      (True by default)
    - save a product in an archive/directory (in ``outputs_prefix``) whose name must be
      the product's ``title`` property
    - update the product's ``location`` attribute once its data is downloaded (and
      eventually after it's extracted) to the product's location given as a file URI
      (e.g. 'file:///tmp/product_folder' on Linux or
      'file:///C:/Users/username/AppData/LOcal/Temp' on Windows)
    - save a *record* file in the directory ``outputs_prefix/.downloaded`` whose name
      is built on the MD5 hash of the product's ``remote_location`` attribute
      (``hashlib.md5(remote_location.encode("utf-8")).hexdigest()``) and whose content is
      the product's ``remote_location`` attribute itself.
    - not try to download a product whose ``location`` attribute already points to an
      existing file/directory
    - not try to download a product if its *record* file exists as long as the expected
      product's file/directory. If the *record* file only is found, it must be deleted
      (it certainly indicates that the download didn't complete)
    """

    def clear(self) -> None:
        """Method used to clear a search context between two searches."""
        pass

    def query(
        self,
        product_type: Optional[str] = None,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        page: int = DEFAULT_PAGE,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[EOProduct], Optional[int]]:
        """Implementation of how the products must be searched goes here.

        This method must return a tuple with (1) a list of EOProduct instances (see eodag.api.product module)
        which will be processed by a Download plugin (2) and the total number of products matching
        the search criteria. If ``count`` is False, the second element returned must be ``None``.
        """
        raise NotImplementedError("A Api plugin must implement a method named query")

    def discover_product_types(self) -> Optional[Dict[str, Any]]:
        """Fetch product types list from provider using `discover_product_types` conf"""
        return None

    def discover_queryables(
        self, product_type: Optional[str] = None
    ) -> Optional[Dict[str, Tuple[Annotated[Any, FieldInfo], Any]]]:
        """Fetch queryables list from provider using `discover_queryables` conf"""
        return None

    def download(
        self,
        product: EOProduct,
        auth: Optional[PluginConfig] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Any,
    ) -> Optional[str]:
        """
        Base download method. Not available, it must be defined for each plugin.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: (optional) The configuration of a plugin of type Authentication
        :type auth: :class:`~eodag.config.PluginConfig`
        :param progress_callback: (optional) A progress callback
        :type progress_callback: :class:`~eodag.utils.ProgressCallback`
        :param wait: (optional) If download fails, wait time in minutes between two download tries
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes before stop retrying
                        to download
        :type timeout: int
        :param kwargs: `outputs_prefix` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :type kwargs: Union[str, bool, dict]
        :returns: The absolute path to the downloaded product in the local filesystem
            (e.g. '/tmp/product.zip' on Linux or
            'C:\\Users\\username\\AppData\\Local\\Temp\\product.zip' on Windows)
        :rtype: str
        """
        raise NotImplementedError(
            "An Api plugin must implement a method named download"
        )

    def download_all(
        self,
        products: SearchResult,
        auth: Optional[PluginConfig] = None,
        downloaded_callback: Optional[DownloadedCallback] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Any,
    ) -> List[str]:
        """
        Base download_all method.

        :param products: Products to download
        :type products: :class:`~eodag.api.search_result.SearchResult`
        :param auth: (optional) The configuration of a plugin of type Authentication
        :type auth: :class:`~eodag.config.PluginConfig`
        :param downloaded_callback: (optional) A method or a callable object which takes
                                    as parameter the ``product``. You can use the base class
                                    :class:`~eodag.api.product.DownloadedCallback` and override
                                    its ``__call__`` method. Will be called each time a product
                                    finishes downloading
        :type downloaded_callback: Callable[[:class:`~eodag.api.product._product.EOProduct`], None]
                                   or None
        :param progress_callback: (optional) A progress callback
        :type progress_callback: :class:`~eodag.utils.ProgressCallback`
        :param wait: (optional) If download fails, wait time in minutes between two download tries
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes before stop retrying
                        to download
        :type timeout: int
        :param kwargs: `outputs_prefix` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :type kwargs: Union[str, bool, dict]
        :returns: List of absolute paths to the downloaded products in the local
            filesystem (e.g. ``['/tmp/product.zip']`` on Linux or
            ``['C:\\Users\\username\\AppData\\Local\\Temp\\product.zip']`` on Windows)
        :rtype: list
        """
        raise NotImplementedError(
            "A Api plugin must implement a method named download_all"
        )
