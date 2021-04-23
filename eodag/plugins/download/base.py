# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, https://www.csgroup.eu/
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
import tarfile
import zipfile
from datetime import datetime, timedelta
from time import sleep

from eodag.plugins.base import PluginTopic
from eodag.utils import get_progress_callback, sanitize, uri_to_path
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    NotAvailableError,
)
from eodag.utils.notebook import NotebookWidgets

logger = logging.getLogger("eodag.plugins.download.base")

# default wait times in minutes
DEFAULT_DOWNLOAD_WAIT = 2
DEFAULT_DOWNLOAD_TIMEOUT = 20


class Download(PluginTopic):
    """Base Download Plugin.

    A Download plugin has two download methods that it must implement:

    - ``download``: download a single ``EOProduct``
    - ``download_all``: download multiple products from a ``SearchResult``

    They must:

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
    - not try to download a product whose ``location`` attribute already points to an
      existing file/directory
    - not try to download a product if its *record* file exists as long as the expected
      product's file/directory. If the *record* file only is found, it must be deleted
      (it certainly indicates that the download didn't complete)

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
        **kwargs,
    ):
        r"""
        Base download method. Not available, it must be defined for each plugin.

        :param product: EO product to download
        :type product: :class:`~eodag.api.product.EOProduct`
        :param progress_callback: A progress callback
        :type progress_callback: :class:`~eodag.utils.ProgressCallback`, optional
        :param wait: If download fails, wait time in minutes between two download tries
        :type wait: int, optional
        :param timeout: If download fails, maximum time in minutes before stop retrying
            to download
        :type timeout: int, optional
        :param dict kwargs: ``outputs_prefix` (``str``), `extract` (``bool``) and
            ``dl_url_params`` (``dict``) can be provided as additional kwargs and will
            override any other values defined in a configuration file or with
            environment variables.
        :returns: The absolute path to the downloaded product in the local filesystem
            (e.g. '/tmp/product.zip' on Linux or
            'C:\\Users\\username\\AppData\\Local\\Temp\\product.zip' on Windows)
        :rtype: str
        """
        raise NotImplementedError(
            "A Download plugin must implement a method named download"
        )

    def _prepare_download(self, product, **kwargs):
        """Check if file has already been downloaded, and prepare product download

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product.EOProduct`
        :return: fs_path, record_filename
        :rtype: tuple
        """
        if product.location != product.remote_location:
            fs_path = uri_to_path(product.location)
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

        outputs_prefix = (
            kwargs.pop("outputs_prefix", None) or self.config.outputs_prefix
        )
        outputs_extension = kwargs.get("outputs_extension", ".zip")

        # Strong asumption made here: all products downloaded will be zip files
        # If they are not, the '.zip' extension will be removed when they are downloaded and returned as is
        prefix = os.path.abspath(outputs_prefix)
        sanitized_title = sanitize(product.properties["title"])
        if sanitized_title == product.properties["title"]:
            collision_avoidance_suffix = ""
        else:
            collision_avoidance_suffix = "-" + sanitize(product.properties["id"])
        fs_path = os.path.join(
            prefix,
            "{}{}{}".format(
                sanitize(product.properties["title"]),
                collision_avoidance_suffix,
                outputs_extension,
            ),
        )
        fs_dir_path = fs_path.replace(outputs_extension, "")
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
            return self._finalize(fs_path, **kwargs), None
        elif os.path.isfile(record_filename) and os.path.isdir(fs_dir_path):
            logger.info("Product already downloaded: %s", fs_dir_path)
            return self._finalize(fs_dir_path, **kwargs), None
        # Remove the record file if fs_path is absent (e.g. it was deleted while record wasn't)
        elif os.path.isfile(record_filename):
            logger.debug(
                "Record file found (%s) but not the actual file", record_filename
            )
            logger.debug("Removing record file : %s", record_filename)
            os.remove(record_filename)

        return fs_path, record_filename

    def _finalize(self, fs_path, **kwargs):
        """Finalize the download process.

        :param fs_path: The path to the local zip archive downloaded or already present
        :type fs_path: str
        :return: the absolute path to the product
        """
        extract = kwargs.pop("extract", None)
        extract = (
            extract if extract is not None else getattr(self.config, "extract", False)
        )
        outputs_extension = kwargs.pop("outputs_extension", ".zip")

        if not extract:
            logger.info("Extraction not activated. The product is available as is.")
            return fs_path
        product_path = (
            fs_path[: fs_path.index(outputs_extension)]
            if outputs_extension in fs_path
            else fs_path
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
        outputs_prefix = (
            kwargs.pop("outputs_prefix", None) or self.config.outputs_prefix
        )
        if not os.path.exists(product_path):
            logger.info("Extraction activated")
            if fs_path.endswith(".zip"):
                with zipfile.ZipFile(fs_path, "r") as zfile:
                    fileinfos = zfile.infolist()
                    with get_progress_callback() as bar:
                        bar.max_size = len(fileinfos)
                        bar.unit = "file"
                        bar.desc = "Extracting files from {}".format(
                            os.path.basename(fs_path)
                        )
                        bar.unit_scale = False
                        bar.position = 2
                        for fileinfo in fileinfos:
                            zfile.extract(
                                fileinfo,
                                path=os.path.join(outputs_prefix, product_path),
                            )
                            bar(1)
            elif fs_path.endswith(".tar.gz"):
                with tarfile.open(fs_path, "r:gz") as zfile:
                    logger.info(
                        "Extracting files from {}".format(os.path.basename(fs_path))
                    )
                    zfile.extractall(path=os.path.join(outputs_prefix, product_path))

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
        **kwargs,
    ):
        """
        Base download_all method.

        This specific implementation uses the ``download`` method implemented by
        the plugin to **sequentially** attempt to download products.

        :param products: Products to download
        :type products: :class:`~eodag.api.search_result.SearchResult`
        :param progress_callback: A progress callback
        :type progress_callback: :class:`~eodag.utils.ProgressCallback`, optional
        :param wait: If download fails, wait time in minutes between two download tries
        :type wait: int, optional
        :param timeout: If download fails, maximum time in minutes before stop retrying
            to download
        :type timeout: int, optional
        :param dict kwargs: ``outputs_prefix` (``str``), `extract` (``bool``) and
            ``dl_url_params`` (``dict``) can be provided as additional kwargs and will
            override any other values defined in a configuration file or with
            environment variables.
        :returns: List of absolute paths to the downloaded products in the local
            filesystem (e.g. ``['/tmp/product.zip']`` on Linux or
            ``['C:\\Users\\username\\AppData\\Local\\Temp\\product.zip']`` on Windows)
        :rtype: list
        """
        # Products are going to be removed one by one from this sequence once
        # downloaded.
        products = products[:]
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

        with get_progress_callback() as bar:
            bar.max_size = nb_products
            bar.unit = "product"
            bar.desc = "Downloaded products"
            bar.unit_scale = False
            bar(0)

            while "Loop until all products are download or timeout is reached":
                # try downloading each product before retry
                for idx, product in enumerate(products):
                    if datetime.now() >= product.next_try:
                        products[idx].next_try += timedelta(minutes=wait)
                        try:
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
                                    **kwargs,
                                )
                            )

                            # product downloaded, to not retry it
                            products.remove(product)
                            bar(1)

                            # reset stop time for next product
                            stop_time = datetime.now() + timedelta(minutes=timeout)

                        except NotAvailableError as e:
                            logger.info(e)
                            continue

                        except (AuthenticationError, MisconfiguredError):
                            logger.exception(
                                "Stopped because of credentials problems with provider %s",
                                self.provider,
                            )
                            raise

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
                        f"[Retry #{retry_count}, {nb_products - len(products)}/{nb_products} D/L] "
                        f"Waiting {wait_seconds}s until next download try (retry every {wait}' for {timeout}')"
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

        if hasattr(progress_callback, "pb") and hasattr(progress_callback.pb, "close"):
            progress_callback.pb.close()

        return paths
