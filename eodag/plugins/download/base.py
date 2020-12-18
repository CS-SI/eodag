# -*- coding: utf-8 -*-
# Copyright 2020, CS GROUP - France, http://www.c-s.fr
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

import hashlib
import logging
import os
import zipfile
from datetime import datetime, timedelta
from time import sleep

from tqdm import tqdm

from eodag.plugins.base import PluginTopic
from eodag.utils import ProgressCallback, sanitize
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
    :type config: str
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

    def _prepare_download(self, product):
        """Check if file has already been downloaded, and prepare product download

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product.EOProduct`
        :return: fs_path, record_filename
        :rtype: tuple
        """
        if product.location != product.remote_location:
            scheme_prefix_len = len("file://")
            fs_path = product.location[scheme_prefix_len:]
            # The fs path of a product is either a file (if 'extract' config is False) or a directory
            if os.path.isfile(fs_path) or os.path.isdir(fs_path):
                logger.info(
                    "Product already present on this platform. Identifier: %s", fs_path
                )
                # Do not download data if we are on site. Instead give back the absolute path to the data
                return fs_path, None

        url = product.remote_location
        if not url:
            logger.debug(
                "Unable to get download url for %s, skipping download", product
            )
            return None, None
        logger.info("Download url: %s", url)

        # Strong asumption made here: all products downloaded will be zip files
        # If they are not, the '.zip' extension will be removed when they are downloaded and returned as is
        prefix = os.path.abspath(self.config.outputs_prefix)
        sanitized_title = sanitize(product.properties["title"])
        if sanitized_title == product.properties["title"]:
            collision_avoidance_suffix = ""
        else:
            collision_avoidance_suffix = "-" + sanitize(product.properties["id"])
        fs_path = os.path.join(
            prefix,
            "{}{}.zip".format(
                sanitize(product.properties["title"]), collision_avoidance_suffix
            ),
        )
        fs_dir_path = fs_path.replace(".zip", "")
        download_records_dir = os.path.join(prefix, ".downloaded")
        try:
            os.makedirs(download_records_dir)
        except OSError as exc:
            import errno

            if exc.errno != errno.EEXIST:  # Skip error if dir exists
                import traceback as tb

                logger.warning(
                    "Unable to create records directory. Got:\n%s", tb.format_exc()
                )
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        record_filename = os.path.join(download_records_dir, url_hash)
        if os.path.isfile(record_filename) and os.path.isfile(fs_path):
            logger.info("Product already downloaded: %s", fs_path)
            return self._finalize(fs_path), None
        elif os.path.isfile(record_filename) and os.path.isdir(fs_dir_path):
            logger.info("Product already downloaded: %s", fs_dir_path)
            return self._finalize(fs_dir_path), None
        # Remove the record file if fs_path is absent (e.g. it was deleted while record wasn't)
        elif os.path.isfile(record_filename):
            logger.debug(
                "Record file found (%s) but not the actual file", record_filename
            )
            logger.debug("Removing record file : %s", record_filename)
            os.remove(record_filename)

        return fs_path, record_filename

    def _finalize(self, fs_path):
        """Finalize the download process.

        :param fs_path: The path to the local zip archive downloaded or already present
        :type fs_path: str
        :return: the absolute path to the product
        """
        if not getattr(self.config, "extract", False):
            logger.info("Extraction not activated. The product is available as is.")
            return fs_path
        product_path = (
            fs_path[: fs_path.index(".zip")] if ".zip" in fs_path else fs_path
        )
        product_path_exists = os.path.exists(product_path)
        if product_path_exists and os.path.isfile(product_path):
            logger.info(
                "Remove existing partially downloaded file: %s (%s/%s)"
                % (
                    product_path,
                    os.stat(product_path).st_size,
                    os.stat(fs_path).st_size,
                )
            )
            os.remove(product_path)
        elif (
            product_path_exists
            and os.path.isdir(product_path)
            and len(os.listdir(product_path)) == 0
        ):
            logger.info(
                "Remove existing empty destination directory: %s" % product_path
            )
            os.rmdir(product_path)
        elif (
            product_path_exists
            and os.path.isdir(product_path)
            and len(os.listdir(product_path)) > 0
        ):
            logger.info(
                "Extraction cancelled, destination directory already exists and is not empty: %s"
                % product_path
            )
            return product_path
        if not os.path.exists(product_path):
            logger.info("Extraction activated")
            with zipfile.ZipFile(fs_path, "r") as zfile:
                fileinfos = zfile.infolist()
                with tqdm(
                    fileinfos,
                    unit="file",
                    desc="Extracting files from {}".format(os.path.basename(fs_path)),
                ) as progressbar:
                    for fileinfo in progressbar:
                        zfile.extract(
                            fileinfo,
                            path=os.path.join(self.config.outputs_prefix, product_path),
                        )
        # Handle depth levels in the product archive. For example, if the downloaded archive was
        # extracted to: /top_level/product_base_dir and archive_depth was configured to 2, the product
        # location will be /top_level/product_base_dir.
        # WARNING: A strong assumption is made here: there is only one subdirectory per level
        archive_depth = getattr(self.config, "archive_depth", 1)
        count = 1
        while count < archive_depth:
            product_path = os.path.join(product_path, os.listdir(product_path)[0])
            count += 1
        return product_path

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
                for idx, product in enumerate(products):
                    if datetime.now() >= product.next_try:
                        products[idx].next_try += timedelta(minutes=wait)
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
                                    wait=wait,
                                    timeout=-1,
                                )
                            )

                            # product downloaded, to not retry it
                            products.remove(product)
                            bar.update(1)

                            # reset stop time for next product
                            stop_time = datetime.now() + timedelta(minutes=timeout)

                        except NotAvailableError as e:
                            logger.info(e)
                            continue

                        except RuntimeError:
                            import traceback as tb

                            logger.error(
                                "A problem occurred during download of product: %s. "
                                "Skipping it",
                                product,
                            )
                            logger.debug("\n%s", tb.format_exc())
                            stop_time = datetime.now()

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
