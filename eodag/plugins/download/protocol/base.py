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

import datetime
import hashlib
import json
import logging
import os
import shutil
import tarfile
import tempfile
import traceback
import zipfile
from abc import abstractmethod
from threading import Lock
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple, TypeVar, Union, final

from mypy_boto3_s3 import S3ServiceResource
from requests import Response
from requests.auth import AuthBase

from eodag.plugins.base import PluginTopic
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    Mime,
    Processor,
    ProgressCallback,
    sanitize,
)

from ..contentiterator import FileContentIterator
from ..httputils import HttpUtils
from ..streamresponse import StreamResponse

if TYPE_CHECKING:
    from eodag.api.product import Asset, EOProduct
    from eodag.api.search_result import SearchResult
    from eodag.config import PluginConfig
    from eodag.types.download_args import DownloadConf
    from eodag.utils import Unpack


logger = logging.getLogger("eodag.download.base")

T = TypeVar("T")


class Download(PluginTopic):
    """Base Download Plugin.

    A Download plugin has two download methods that it must implement:

    - ``download``: download a single :class:`~eodag.api.product._product.EOProduct`
    - ``download_all``: download multiple products from a :class:`~eodag.api.search_result.SearchResult`

    They must:

    - download data in the ``output_dir`` folder defined in the plugin's
      configuration or passed through kwargs
    - extract products from their archive (if relevant) if ``extract`` is set to ``True``
      (``True`` by default)
    - save a product in an archive/directory (in ``output_dir``) whose name must be
      the product's ``title`` property

    :param provider: An eodag providers configuration dictionary
    :param config: Path to the user configuration file
    """

    directories_mutex = Lock()

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(Download, self).__init__(provider, config)

    @abstractmethod
    def download(
        self,
        asset: Asset,
        auth: Optional[Union[AuthBase, S3ServiceResource]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        no_cache: bool = False,
        stream: bool = False,
        **kwargs: Unpack[DownloadConf],
    ) -> Union[Optional[str], StreamResponse]:
        """
        Base download method. Not available, it must be defined for each plugin.

        :param asset: The Asset to download
        :param auth: (optional) authenticated object
        :param progress_callback: (optional) A progress callback
        :param executor: (optional) An executor to download assets of ``product`` in parallel if it has any
        :param wait: (optional) If download fails, wait time in minutes between two download tries
        :param timeout: (optional) If download fails, maximum time in minutes before stop retrying
                        to download
        :param stream: (optional) if method return local_path of downloaded item, or a streamresponse
        :param kwargs: `output_dir` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :returns: The absolute path to the downloaded product in the local filesystem
            (e.g. ``/tmp/product.zip`` on Linux or
            ``C:\\Users\\username\\AppData\\Local\\Temp\\product.zip`` on Windows)
        """
        raise NotImplementedError(
            "A Download plugin must implement a method named download"
        )

    @final
    def asset_metadata_from_response(self, asset: Asset, response: Response):
        """Update asset properties from response"""
        if isinstance(response, Response):
            headers = HttpUtils.format_headers(response.headers)
            filesize = headers.get("Content-Length", None)
            if filesize is not None:
                asset["file:size"] = filesize
                asset.size = int(filesize)
            mimetype = headers.get("Content-Type", None)
            if mimetype is not None:
                asset["type"] = mimetype
            hashmd5 = headers.get("Etag", None)
            if hashmd5 is not None:
                hashmd5 = hashmd5.strip('"')
                if len(hashmd5) > 32:
                    hashmd5 = hashmd5[0:32]
                asset["file:checksum"] = hashmd5
            updated = headers.get("Last-Modified", None)
            if updated is not None:
                try:
                    # From RFC 2822 to ISO 8601 Extended
                    updated = datetime.datetime.strptime(
                        updated, "%a, %d %b %Y %H:%M:%S %Z"
                    )
                    asset["update"] = updated.strftime("%Y-%m-%dT%H:%M:%S%z")
                except Exception:
                    pass

    @final
    def asset_metadata_from_file(self, asset: Asset, file_path: str):
        """Update asset properties from a local file"""
        if os.path.isfile(file_path):
            stat = os.stat(file_path)
            asset.filename = os.path.basename(file_path)
            asset.size = stat.st_size
            asset["update"] = datetime.datetime.fromtimestamp(stat.st_mtime).strftime(
                "%Y-%m-%dT%H:%M:%S%z"
            )
            asset["type"] = Mime.guess_file_type(file_path)
            asset["file:size"] = stat.st_size
            with open(file_path, "rb") as fd:
                asset["file:checksum"] = hashlib.md5(fd.read()).hexdigest()

    @final
    def asset_metadata_from_s3object(self, asset: Asset, s3_object: dict):
        """Update asset properties from a s3 object"""
        headers = HttpUtils.format_headers(
            s3_object.get("ResponseMetadata", {}).get("HTTPHeaders", {})
        )
        filesize = headers.get("Content-Length", None)
        if filesize is not None:
            asset["file:size"] = filesize
            asset.size = int(filesize)
        mimetype = headers.get("Content-Type", None)
        if mimetype is not None:
            asset["type"] = mimetype
        hashmd5 = headers.get("Etag", None)
        if hashmd5 is not None:
            hashmd5 = hashmd5.strip('"')
            if len(hashmd5) > 32:
                hashmd5 = hashmd5[0:32]
            asset["file:checksum"] = hashmd5
        updated = headers.get("Last-Modified", None)
        if updated is not None:
            try:
                # From RFC 2822 to ISO 8601 Extended
                updated = datetime.datetime.strptime(
                    updated, "%a, %d %b %Y %H:%M:%S %Z"
                )
                asset["update"] = updated.strftime("%Y-%m-%dT%H:%M:%S%z")
            except Exception:
                pass

    @final
    def get_statements(
        self,
        asset: Asset,
        **kwargs,
    ) -> dict[str, Any]:
        """Check if file has already been downloaded, and prepare asset download
        :param asset: The Asset to download
        :param progress_callback: (optional) A progress callback
        returns: fs_path, record_path, cached
        """
        output_dir, statement_dir = self._prepare_directories(**kwargs)
        statement_file = self._get_statement_path(asset, statement_dir)

        # Try load statement file
        statements = {
            "ordered": False,
            "order_id": "",
            "status_link": "",
            "search_link": "",
            "href": "",
            "local_path": "",
        }

        if os.path.isfile(statement_file):
            try:
                with open(statement_file, "r") as fd:
                    content = fd.read()
                imported_statements = json.loads(content)

                # Keep it is href not changed since previous download
                # means: old and new are defined and diffrents
                if asset.get("href", "") in ["", imported_statements.get("href", "")]:
                    statements = imported_statements
                else:
                    raise Exception("Out-dated statement (href changed)")
            except Exception as e:
                logger.debug(
                    "Asset {} fail to load steatement file: {}".format(
                        asset.key, str(e)
                    )
                )
                # Corrupted or out-dated file
                try:
                    os.remove(statement_file)
                except Exception as e:
                    logger.debug(
                        "Revome corrupted asset {} startements: {}".format(asset.key, e)
                    )

        product_dir = os.path.join(
            output_dir, sanitize(asset.product.properties.get("title", ""))
        )
        if not os.path.isdir(product_dir):
            os.makedirs(product_dir)

        # Generate expected local path
        local_path = os.path.join(product_dir, sanitize(asset.key))
        if not os.path.isdir(local_path):
            computed_extension: Optional[str] = None
            if asset.get("type") not in [None, "", Mime.DEFAULT]:
                computed_extension = Mime.guess_extension(asset.get("type"))
            if computed_extension is None:
                computed_extension = ""
            output_extension: str = kwargs.get(
                "output_extension",
                getattr(self.config, "output_extension", computed_extension),
            )
            if (
                not isinstance(output_extension, str)
                or len(output_extension) == 0
                or output_extension[0] != "."
            ):
                logger.debug("Malformed output extension {}".format(computed_extension))
                output_extension = ""

            if not os.path.isdir(local_path) and not local_path.endswith(
                output_extension
            ):
                local_path = "{}{}".format(local_path.rstrip("/\\"), output_extension)
                if not os.path.isfile(local_path):
                    # Find matchind file, excluding extension restrict
                    # When asset is a directory, result could be an archive
                    base_path = os.path.join(product_dir, sanitize(asset.key))
                    for file in os.listdir(product_dir):
                        path = os.path.join(product_dir.rstrip("/\\"), file)
                        if os.path.isfile(path) and path.startswith(
                            "{}.".format(base_path)
                        ):
                            local_path = path
                            statements["local_path"] = local_path
                            self.set_statements(asset, statements, **kwargs)
                            break

        # If an old cache exists and way to generate path changed, move cached file (file only)
        statement_local_path: str = str(statements.get("local_path", ""))
        if (
            statement_local_path != ""
            and os.path.isfile(statement_local_path)
            and statement_local_path != local_path
        ):
            os.rename(statement_local_path, local_path)
            logger.debug(
                "Asset {} local_path moved from {} to {}",
                asset.key,
                statement_local_path,
                local_path,
            )
            statements["local_path"] = local_path
            self.set_statements(asset, statements, **kwargs)
        else:
            statements["local_path"] = local_path

        return statements

    @final
    def set_statements(self, asset: Asset, status: dict[str, Any], **kwargs):

        """update asset statement"""
        _, statement_dir = self._prepare_directories(**kwargs)
        statement_file = self._get_statement_path(asset, statement_dir)
        logger.debug(
            "Asset {} statements updated at {} with data".format(
                asset.key, statement_file
            )
        )
        with open(statement_file, "w+") as fd:
            fd.write(json.dumps(status))

    def _get_statement_path(self, asset: Asset, statement_dir):

        # statement file
        asset_hash = "{}-{}-{}".format(
            str(asset.product.collection),
            str(asset.product.properties.get("id")),
            asset.key,
        )
        return "{}/{}.json".format(
            statement_dir, hashlib.md5(asset_hash.encode("utf-8")).hexdigest()
        )

    def _prepare_directories(self, **kwargs: Unpack[DownloadConf]) -> Tuple[str, str]:

        # output dir
        output_dir = kwargs.get("output_dir", None)  # type: ignore
        if output_dir is None:
            output_dir = getattr(self.config, "output_dir", None)
        if output_dir is None:
            output_dir = tempfile.gettempdir()
        output_dir = os.path.abspath(output_dir)

        # statement dir
        statement_dir = os.path.join(output_dir, ".downloaded")

        Download.directories_mutex.acquire()
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        if not os.path.isdir(statement_dir):
            try:
                os.makedirs(statement_dir)
            except OSError:
                logger.warning(
                    "Unable to create download directory:\n" + traceback.format_exc()
                )
        Download.directories_mutex.release()

        return output_dir, statement_dir

    @final
    def get_cache(
        self, asset: Asset, statements: dict[str, str], stream: bool = False
    ) -> Optional[Union[Optional[str], StreamResponse]]:
        """Get current asset cache if exists and accurate"""
        local_path = statements.get("local_path", None)

        # Check cached (file exists, url changed)
        if (
            isinstance(local_path, str)
            and (os.path.isfile(local_path) or os.path.isdir(local_path))
            and (
                asset.get("href", "") == ""
                or asset.get("href", "") == statements.get("href")
            )
        ):

            if not stream:
                if os.path.isfile(local_path):
                    # Update asset from file
                    self.asset_metadata_from_file(asset, local_path)

                logger.debug("Cache found, served as path {}".format(local_path))
                return local_path
            else:

                # If cache is a directory, pack it to a archive
                if os.path.isdir(local_path):
                    local_path = self.pack_archive(asset, local_path)

                    # Watch when stream end to remove archive
                    fci = FileContentIterator(local_path)

                    def on_complete():
                        if os.path.isfile(local_path):
                            os.remove(local_path)

                    fci.on("complete", on_complete)

                    def on_error(error: Exception):
                        if os.path.isfile(local_path):
                            os.remove(local_path)

                    fci.on("error", on_error)

                    # Update asset from file
                    self.asset_metadata_from_file(asset, local_path)

                    # Build stream response from file
                    logger.debug(
                        "Cache found, served as stream from file {}".format(local_path)
                    )
                    return StreamResponse(
                        content=fci,
                        filename=asset.filename,
                        size=asset.size,
                        headers={
                            "Content-Length": str(asset.size),
                            "Content-Type": asset.get("type", Mime.DEFAULT),
                        },
                        media_type=asset.get("type", Mime.DEFAULT),
                        status_code=200,
                        arcname=None,
                    )

                else:

                    # Update asset from file
                    self.asset_metadata_from_file(asset, local_path)

                    # Build stream response from file
                    logger.debug(
                        "Cache found, served as stream from file {}".format(local_path)
                    )

                    return StreamResponse.from_file(local_path)
        return None

    @final
    def pack_archive(self, asset: Asset, dir_path: str) -> str:
        """Transform a directory to an archive"""
        if os.path.isfile(dir_path):
            return dir_path
        if not os.path.isdir(dir_path):
            raise NotImplementedError(
                "Asset {} error: asset directory {} not found".format(
                    asset.key, dir_path
                )
            )

        file_path = "{}.zip".format(dir_path)

        logger.debug("Pack directory to archive {}".format(dir_path))

        if os.path.isfile(file_path):
            os.remove(file_path)

        def crawl_relpath(path: str, onitem: Callable[..., str], rel_path: str = ""):
            local_path = os.path.join(path, rel_path)
            for item in os.listdir(local_path):
                item_path = os.path.join(local_path, item)
                item_relpath = os.path.join(rel_path, item)
                if os.path.isfile(item_path):
                    onitem(item_path, item_relpath)
                elif os.path.isdir(item_path):
                    crawl_relpath(path, onitem, item_relpath)

        if os.path.isfile(file_path):
            os.remove(file_path)

        with zipfile.ZipFile(file_path, "w") as zf:

            def onfile(full_path, rel_path):
                logger.debug("  pack file {}".format(rel_path))
                zf.write(full_path, rel_path)

            crawl_relpath(dir_path, onfile)

        return file_path

    @final
    def unpack_archive(
        self,
        asset: Asset,
        file_path: str,
        progress_callback: Optional[ProgressCallback] = None,
        **kwargs: Unpack[DownloadConf],
    ) -> str:
        """Post process download if asset is an archive

                :param fs_path: The path to the local zip archive downloaded or already present
        :param progress_callback: (optional) A progress callback
        :returns: The absolute path to the product
        """
        if not os.path.isfile(file_path):
            return file_path

        # check if file is an archive
        is_zip = zipfile.is_zipfile(file_path)
        is_tar = False
        if not is_zip:
            is_tar = tarfile.is_tarfile(file_path)
            if not is_tar:
                # not a supported archive
                return file_path

        # Paremeters
        extract = kwargs.get("extract", getattr(self.config, "extract", True))
        if not extract:
            # archive will not be extracted
            return file_path

        delete_archive = kwargs.get(
            "delete_archive", getattr(self.config, "delete_archive", True)
        )

        # progress bar init
        if progress_callback is None:
            progress_callback = ProgressCallback(
                unit="file",
                unit_scale=False,
                position=2,
            )
            # one shot progress callback to close after download
            close_progress_callback = True
        else:
            close_progress_callback = False
            progress_callback.unit = "file"
            progress_callback.unit_scale = False
            progress_callback.refresh()

        # Remove extension if found to generate directory path
        new_dir_path: str = file_path
        start_at = -1
        pos = file_path.rfind("/")
        if pos >= 0:
            start_at = pos
        else:
            pos = file_path.rfind("\\")
            if pos >= 0:
                start_at = pos

        if start_at >= 0:
            pos = file_path.rfind(".", start_at + 1)
            if pos >= 0:
                new_dir_path = new_dir_path[:pos]

        # File has no extension, to avoid linux collision, add one
        if is_zip:
            new_file_path = file_path
            if not new_file_path.endswith(".zip"):
                new_file_path = "{}.zip".format(file_path)
            if file_path != new_file_path:
                if os.path.isfile(new_file_path):
                    os.remove(new_file_path)
                os.rename(file_path, new_file_path)
            file_path = new_file_path
        elif is_tar:
            new_file_path = file_path
            if not new_file_path.endswith(".tar") and not not new_file_path.endswith(
                ".tar.gz"
            ):
                new_file_path = "{}.tar".format(file_path)
            if file_path != new_file_path:
                if os.path.isfile(new_file_path):
                    os.remove(new_file_path)
                os.rename(file_path, new_file_path)
            file_path = new_file_path

        # Clean uncompress archive destination directory
        if os.path.isdir(new_dir_path):
            shutil.rmtree(new_dir_path)
        os.makedirs(new_dir_path)

        # Uncompress archive
        try:
            if is_zip:
                progress_callback.refresh()
                with zipfile.ZipFile(file_path, "r") as zfile:
                    fileinfos = zfile.infolist()
                    progress_callback.reset(total=len(fileinfos))
                    for fileinfo in fileinfos:
                        zfile.extract(
                            fileinfo,
                            path=new_dir_path,
                        )
                        progress_callback(1)
            elif is_tar:
                progress_callback.refresh()
                with tarfile.open(file_path, "r") as zfile:
                    progress_callback.reset(total=1)
                    zfile.extractall(path=new_dir_path)
                    progress_callback(1)
            else:
                if os.path.isdir(new_dir_path):
                    shutil.rmtree(new_dir_path)
                # not extractable
                progress_callback(1, total=1)
                if close_progress_callback:
                    progress_callback.close()
                return file_path
        except Exception as e:
            logger.info("Asset {}, Archive extract fails: {}".format(asset.key, str(e)))
            progress_callback(1, total=1)
            if close_progress_callback:
                progress_callback.close()
            return file_path

        # Postprocess archive
        self._resolve_archive_depth(new_dir_path)

        # Delete archove on succes if it's configured
        if delete_archive and os.path.isfile(file_path):
            os.remove(file_path)

        progress_callback(1, total=1)
        if close_progress_callback:
            progress_callback.close()

        return new_dir_path

    def _resolve_archive_depth(self, asset_path: str):
        """Update product_path using archive_depth from provider configuration.

        Handle depth levels in the product archive. For example, if the downloaded archive was
        extracted to: ``/top_level/product_base_dir`` and ``archive_depth`` was configured to 2, the product
        location will be ``/top_level/product_base_dir``.
        :param product_path: The path to the extracted product

        example: apply map to level2: file file, trunk path under level 2
            [dir] Level1                    [dir] Level2
                [dir] Level2                    [file] Level3
                    [file] Level3           [dir] Level2
                [dir] Level2                    [file] Level3
                    [file] Level3               [file] Level3
                    [file] Level3           [file] Level2
                    [dir] Level3
                [file] Level2
        """
        # Recursive list files and dirs, and map it new local path by wanted level
        def map_items_depth_level(
            base_path: str, local_path: str = "", wanted_level: int = 1, level: int = 1
        ) -> list[dict[str, str]]:
            files: list[dict[str, str]] = []
            full_path = os.path.join(base_path, local_path)
            for item in os.listdir(full_path):
                path = os.path.join(full_path, item)
                if os.path.isfile(path):
                    from_path = os.path.join(local_path, item)
                    if level >= wanted_level:
                        segments = from_path.split(os.path.sep)
                        to_path = os.path.sep.join(segments[wanted_level - 1 :])
                        files.append({"from_path": from_path, "to_path": to_path})
                elif os.path.isdir(path):
                    sub = map_items_depth_level(
                        base_path,
                        os.path.join(local_path, item),
                        wanted_level,
                        level + 1,
                    )
                    for subitem in sub:
                        files.append(subitem)
            return files

        archive_depth = int(getattr(self.config, "archive_depth", 1))
        if archive_depth > 1:

            files = map_items_depth_level(asset_path, "", archive_depth, 1)

            # Keep only mapped files, located on new location
            from_dir = asset_path
            to_dir = "{}_new".format(asset_path)
            if os.path.isdir(to_dir):
                shutil.rmtree(to_dir)
            os.makedirs(to_dir)
            for file in files:
                from_path = os.path.join(from_dir, file["from_path"])
                if os.path.isfile(from_path):
                    to_path = os.path.join(to_dir, file["to_path"])
                    to_local_dir = os.path.dirname(to_path)
                    if not os.path.isdir(to_local_dir):
                        os.makedirs(to_local_dir)
                    os.rename(from_path, to_path)

            # Replace current location by new location
            shutil.rmtree(from_dir)
            os.rename(to_dir, from_dir)

    def download_all(
        self,
        search_result: SearchResult,
        downloaded_callback: Optional[Callable[[EOProduct], None]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> list[str]:
        """download_all method
        :param progress_callback: (optional) A progress callback
        :param wait: (optional) If download fails, wait time in minutes between two download tries
        :param timeout: (optional) If download fails, maximum time in minutes before stop retrying
        :param kwargs: `output_dir` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :returns: List of absolute paths to the downloaded products in the local
            filesystem (e.g. ``['/tmp/product.zip']`` on Linux or
            ``['C:\\Users\\username\\AppData\\Local\\Temp\\product.zip']`` on Windows)
        """
        nb_products = len(search_result)

        # progress bar init
        if progress_callback is None:
            progress_callback = ProgressCallback(
                total=nb_products,
                unit="product",
                desc="Downloaded products",
                unit_scale=False,
            )
            product_progress_callback = None
        else:
            product_progress_callback = progress_callback.copy()
            progress_callback.reset(total=nb_products)
            progress_callback.unit = "product"
            progress_callback.desc = "Downloaded products"
            progress_callback.unit_scale = False
        progress_callback.refresh()

        # Download all files (parallelized)
        max_workers = getattr(self.config, "max_workers", os.cpu_count())
        passthrough_data: dict[str, Any] = {
            "paths": [],
            "error": None,
            "progress_callback": progress_callback,
        }

        def callback(paths, error: Optional[Exception], product: EOProduct):
            # interrupt parallelized download on error
            if error is not None:
                passthrough_data["error"] = error  # type: ignore
                Processor.stop()  # type: ignore
            else:
                if callable(downloaded_callback):
                    downloaded_callback(product)
                passthrough_data["paths"] += paths
                passthrough_data["progress_callback"](1)  # type: ignore

        ids: list[int] = []
        for product in search_result:
            taskid = Processor.queue(
                product.download,
                product_progress_callback,
                wait,
                timeout,
                q_timeout=int(timeout * 60),
                q_parallelize=max_workers,
                q_callback=callback,
                q_callback_kwargs={"product": product},
                **kwargs,
            )
            ids.append(taskid)
        Processor.wait(ids)

        # An error occurs
        if passthrough_data["error"] is not None:
            raise passthrough_data["error"]

        return passthrough_data["paths"]


__all__ = ["Download"]
