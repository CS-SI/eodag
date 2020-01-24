# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
from __future__ import absolute_import, print_function, unicode_literals

import logging

from tqdm import tqdm

from eodag.plugins.base import PluginTopic
from eodag.utils import ProgressCallback

logger = logging.getLogger("eodag.plugins.download.base")


class Download(PluginTopic):
    """Base Download Plugin.

    :param provider: An eodag providers configuration dictionary
    :type provider: dict
    :param config: Path to the user configuration file
    :type config: str or unicode
    """

    def __init__(self, provider, config):
        super(Download, self).__init__(provider, config)
        self.authenticate = bool(getattr(self.config, "authenticate", False))

    def download(self, product, auth=None, progress_callback=None):
        """
        Base download method. Not available, should be defined for each plugin
        """
        raise NotImplementedError(
            "A Download plugin must implement a method named download"
        )

    def download_all(self, products, auth=None, progress_callback=None):
        """
        A sequential download_all implementation
        using download method for every products
        """
        paths = []
        with tqdm(products, unit="product", desc="Downloading products") as bar:
            for product in bar:
                try:
                    if progress_callback is None:
                        progress_callback = ProgressCallback()
                    if product.downloader is None:
                        raise RuntimeError(
                            "EO product is unable to download itself due to lacking of a "
                            "download plugin"
                        )

                    auth = (
                        product.downloader_auth.authenticate()
                        if product.downloader_auth is not None
                        else product.downloader_auth
                    )
                    # resolve remote location if needed with downloader configuration
                    product.remote_location = product.remote_location % vars(
                        product.downloader.config
                    )

                    paths.append(
                        self.download(
                            product, auth=auth, progress_callback=progress_callback
                        )
                    )
                except Exception:
                    import traceback as tb

                    logger.warning(
                        "A problem occurred during download of product: %s. "
                        "Skipping it",
                        product,
                    )
                    logger.debug("\n%s", tb.format_exc())
        return paths
