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
from datetime import datetime, timedelta
from time import sleep

from tqdm import tqdm

from eodag.plugins.base import PluginTopic
from eodag.utils import ProgressCallback
from eodag.utils.exceptions import NotAvailableError
from eodag.utils.notebook import NotebookWidgets

logger = logging.getLogger("eodag.plugins.download.base")

# default wait times in minutes
DEFAULT_DOWNLOAD_WAIT = 2
DEFAULT_DOWNLOAD_TIMEOUT = 20


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

    def download(
        self,
        product,
        auth=None,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
    ):
        """
        Base download method. Not available, should be defined for each plugin
        """
        raise NotImplementedError(
            "A Download plugin must implement a method named download"
        )

    def download_all(
        self,
        products,
        auth=None,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
    ):
        """
        A sequential download_all implementation
        using download method for every products
        """
        paths = []
        # initiate retry loop
        start_time = datetime.now()
        stop_time = datetime.now() + timedelta(minutes=timeout)
        nb_products = len(products)
        retry_count = 0
        # another output for notbooks
        nb_info = NotebookWidgets()

        for product in products:
            product.next_try = start_time

        with tqdm(
            total=len(products), unit="product", desc="Downloading products"
        ) as bar:
            while "Loop until all products are download or timeout is reached":
                # try downloading each product before retry
                for product in products:
                    if datetime.now() >= product.next_try:
                        product.next_try += timedelta(minutes=wait)
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
                                    product,
                                    auth=auth,
                                    progress_callback=progress_callback,
                                    timeout=-1,
                                )
                            )

                            # product downloaded, to not retry it
                            products.remove(product)
                            bar.update(1)

                        except NotAvailableError as e:
                            logger.info(e)
                            continue

                        except Exception:
                            import traceback as tb

                            logger.warning(
                                "A problem occurred during download of product: %s. "
                                "Skipping it",
                                product,
                            )
                            logger.debug("\n%s", tb.format_exc())

                if (
                    len(products) > 0
                    and datetime.now() < products[0].next_try
                    and datetime.now() < stop_time
                ):
                    wait_seconds = (products[0].next_try - datetime.now()).seconds
                    retry_count += 1
                    info_message = (
                        "[Retry #%s, %s/%s D/L] Waiting %ss until next download try (retry every %s' for %s')"
                        % (
                            retry_count,
                            (nb_products - len(products)),
                            nb_products,
                            wait_seconds,
                            wait,
                            timeout,
                        )
                    )
                    logger.info(info_message)
                    nb_info.display_html(info_message)
                    sleep(wait_seconds + 1)
                elif len(products) > 0 and datetime.now() >= stop_time:
                    logger.warning(
                        "%s products could not be downloaded: %s",
                        len(products),
                        [prod.properties["title"] for prod in products],
                    )
                    break
                elif len(products) == 0:
                    break

        return paths
