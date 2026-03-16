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
import logging
import os
import re
import shutil
import time
from threading import Lock
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple, Union, cast

import requests
from jsonpath_ng.ext import parse
from requests import RequestException, Response
from usgs import USGSAuthExpiredError, USGSError, api

from eodag.api.product import Asset, EOProduct
from eodag.api.product.metadata_mapping import (
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
)
from eodag.api.search_result import SearchResult
from eodag.plugins.apis import Api
from eodag.plugins.download import HttpUtils, ResponseContentIterator, StreamResponse
from eodag.plugins.search import PreparedSearch
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_LIMIT,
    DEFAULT_PAGE,
    GENERIC_COLLECTION,
    USER_AGENT,
    Mime,
    ProgressCallback,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    DownloadError,
    NoMatchingCollection,
    NotAvailableError,
    RequestError,
    ValidationError,
)

if TYPE_CHECKING:
    from requests.auth import AuthBase

    from eodag.config import PluginConfig
    from eodag.types.download_args import DownloadConf
    from eodag.utils import Unpack

logger = logging.getLogger("eodag.apis.usgs")


class UsgsApi(Api):
    """A plugin that enables to query and download data on the USGS catalogues

    :param provider: provider name
    :param config: Api plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): UsgsApi
        * :attr:`~eodag.config.PluginConfig.pagination` (:class:`~eodag.config.PluginConfig.Pagination`)
          (**mandatory**): object containing parameters for pagination; should contain the attribute
          :attr:`~eodag.config.PluginConfig.Pagination.total_items_nb_key_path`
          which is indicating the key for the number of total items in the provider result
        * :attr:`~eodag.config.PluginConfig.ssl_verify` (``bool``): if the ssl certificates
          should be verified in the download request; default: ``True``
        * :attr:`~eodag.config.PluginConfig.need_auth` (``bool``): if authentication is required
          for search; default: ``False``
        * :attr:`~eodag.config.PluginConfig.extract` (``bool``): if the content of the downloaded
          file should be extracted; default: ``True``
        * :attr:`~eodag.config.PluginConfig.order_enabled` (``bool``): if the product has to
          be ordered to download it; default: ``False``
        * :attr:`~eodag.config.PluginConfig.metadata_mapping` (``dict[str, Union[str, list]]``): how
          parameters should be mapped between the provider and eodag; If a string is given, this is
          the mapping parameter returned by provider -> eodag parameter. If a list with 2 elements
          is given, the first one is the mapping eodag parameter -> provider query parameters
          and the second one the mapping provider result parameter -> eodag parameter
    """

    SESSION_FILE_LIFETIME: int = 3600

    session_file_mutex = Lock()

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(UsgsApi, self).__init__(provider, config)

        # Same method as in base.py, Search.__init__()
        # Prepare the metadata mapping
        # Do a shallow copy, the structure is flat enough for this to be sufficient
        metas: dict[str, Any] = {}
        # Update the defaults with the mapping value. This will add any new key
        # added by the provider mapping that is not in the default metadata.
        metas.update(self.config.metadata_mapping)
        self.config.metadata_mapping = mtd_cfg_as_conversion_and_querypath(
            metas,
            self.config.metadata_mapping,
            result_type=getattr(self.config, "result_type", "json"),
        )

    def authenticate(self) -> Optional[str]:
        """Login to usgs api

        :raises: :class:`~eodag.utils.exceptions.AuthenticationError`
        """
        username = getattr(self.config, "credentials", {}).get("username", None)
        if username is None:
            raise AuthenticationError(
                'Please check your USGS credentials, missing "username"'
            )
        password = getattr(self.config, "credentials", {}).get("password", None)
        if password is None:
            raise AuthenticationError(
                'Please check your USGS credentials, missing "password"'
            )

        # File storage is concurency unsafe
        if os.path.isfile(api.TMPFILE):
            os.remove(api.TMPFILE)

        session_token: Optional[str] = self._read_session()
        if session_token is not None and session_token != "":
            return session_token

        for _ in range(2):
            try:
                logger.debug('usgs logging with account "{}"'.format(username))
                response = api.login(username, password, save=False)
                session_token = response.get("data", None)
                logger.debug('usgs logged with account "{}"'.format(username))
                break
            # if API key expired, retry to login once after logout
            except USGSAuthExpiredError:
                self._logout()
                session_token = None
            except USGSError as e:
                self._logout()
                session_token = None
                raise AuthenticationError("Please check your USGS credentials.") from e
            except Exception as e:
                raise AuthenticationError("Authentication failure") from e

        return session_token

    def _logout(self):
        session = self._read_session()
        if session is not None:
            # logout need creted tmp file
            if not os.path.isfile(api.TMPFILE):
                with open(api.TMPFILE, "w+") as fd:
                    fd.write(session)
            try:
                # Logout can't raise 403 -_-
                api.logout()
            except Exception:
                pass
            if os.path.isfile(api.TMPFILE):
                os.remove(api.TMPFILE)
        _, session_file = self._get_session_file()
        UsgsApi.session_file_mutex.acquire(True)
        try:
            if os.path.isfile(session_file):
                os.remove(session_file)
        except Exception:
            pass
        UsgsApi.session_file_mutex.release()

    def _get_session_file(self) -> Tuple[Optional[str], Optional[str]]:
        username = getattr(self.config, "credentials", {}).get("username", None)
        if username is None:
            return None, None
        sanitized_username = re.sub("[^A-Za-z0-9]+", "_", username)
        sanitized_username = re.sub("[_]+", "_", sanitized_username)
        sanitized_username = sanitized_username.strip("_")
        return username, os.path.join(
            os.path.dirname(api.TMPFILE), ".{}.usgs.eodag".format(sanitized_username)
        )

    def _read_session(self) -> Optional[str]:
        session_token: Optional[str] = None
        username, session_file = self._get_session_file()
        UsgsApi.session_file_mutex.acquire(True)
        try:
            if session_file is not None and os.path.isfile(session_file):
                stat = os.stat(session_file)
                delay = datetime.datetime.now(
                    datetime.timezone.utc
                ) - datetime.datetime.fromtimestamp(
                    stat.st_mtime, datetime.timezone.utc
                )
                # Restrict session cache to 1 hour
                if delay.total_seconds() < UsgsApi.SESSION_FILE_LIFETIME:
                    with open(session_file, "r") as fd:
                        session_token = fd.read()
                        logger.debug(
                            "usgs restore session for user {}".format(username)
                        )
        except Exception:
            session_token = None
        UsgsApi.session_file_mutex.release()
        return session_token

    def _write_session(self, session: Optional[str] = None):
        username, session_file = self._get_session_file()
        if session_file is None:
            return
        UsgsApi.session_file_mutex.acquire(True)
        try:
            if session is None:
                if os.path.isfile(session_file):
                    os.remove(session_file)
            else:
                session_dir = os.path.dirname(session_file)
                if not os.path.isdir(session_dir):
                    os.makedirs(session_dir)
                with open(session_file, "w+") as fd:
                    fd.write(session)
                logger.debug(
                    "usgs token session for user {} saved at {}".format(
                        username, session_file
                    )
                )
        except Exception:
            pass
        UsgsApi.session_file_mutex.release()

    def _with_auth(self, routine: Callable, *args, **kwargs) -> Any:

        # Manullally manage session file
        session_token: Optional[str] = self._read_session()
        if session_token is None:
            session_token = self.authenticate()
            if session_token is not None:
                self._write_session(session_token)

        # Inject api_key parameter
        kwargs["api_key"] = "*****"
        logger.debug(
            "usgs with_auth api.{} {} {}".format(str(routine.__name__), args, kwargs)
        )
        kwargs["api_key"] = session_token

        try:
            return routine(*args, **kwargs)
        except USGSAuthExpiredError:
            logger.debug(
                "usgs with_auth api.{} error: (token expired)".format(routine.__name__)
            )
            self._logout()
            session_token = self.authenticate()
            if session_token is not None:
                self._write_session(session_token)
            kwargs["api_key"] = session_token
            return routine(*args, **kwargs)
        except Exception as e:
            self._logout()
            logger.debug(
                "usgs with_auth api.{} error: {}".format(routine.__name__, str(e))
            )
            raise e

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> SearchResult:
        """Search for data on USGS catalogues"""

        # Page crawl token
        token = (
            int(prep.next_page_token)
            if prep.next_page_token is not None
            else DEFAULT_PAGE
        )
        limit = prep.limit or kwargs.pop("max_results", None) or DEFAULT_LIMIT
        search_params = {"limit": limit} | kwargs

        # Check/format parameters
        collection = kwargs.get("collection")
        if collection is None:
            raise NoMatchingCollection(
                "Cannot search on USGS without collection specified"
            )
        if kwargs.get("sort_by"):
            raise ValidationError("USGS does not support sorting feature")

        collection_config = self.config.products.get(collection)
        if collection_config is None:
            collection_config = self.config.products[GENERIC_COLLECTION]

        usgs_collection = collection_config.get("_collection", collection)

        start_date = kwargs.pop("start_datetime", None)
        end_date = kwargs.pop("end_datetime", None)
        geom = kwargs.pop("geometry", None)
        footprint: dict[str, str] = {}
        if hasattr(geom, "bounds"):
            (
                footprint["lonmin"],
                footprint["latmin"],
                footprint["lonmax"],
                footprint["latmax"],
            ) = geom.bounds
        else:
            footprint = geom

        products: list[EOProduct] = []
        if footprint and len(footprint.keys()) == 4:  # a rectangle (or bbox)
            lower_left = {
                "longitude": footprint["lonmin"],
                "latitude": footprint["latmin"],
            }
            upper_right = {
                "longitude": footprint["lonmax"],
                "latitude": footprint["latmax"],
            }
        else:
            lower_left, upper_right = None, None

        # Collect results
        error: Optional[Exception] = None
        try:
            api_search_kwargs = dict(
                start_date=start_date,
                end_date=end_date,
                ll=lower_left,
                ur=upper_right,
                max_results=limit,
                starting_number=token,
            )
            # search by id
            if searched_id := kwargs.get("id"):
                dataset_filters = self._with_auth(api.dataset_filters, usgs_collection)
                # ip pattern set as parameter queryable (first element of param conf list)
                id_pattern = self.config.metadata_mapping["id"][0]
                # loop on matching dataset_filters until one returns expected results
                for dataset_filter in dataset_filters["data"]:
                    if id_pattern in dataset_filter["searchSql"]:
                        logger.debug(
                            "Try using %s dataset filter to search by id on %s",
                            dataset_filter["searchSql"],
                            usgs_collection,
                        )
                        full_api_search_kwargs = {
                            "where": {
                                "filter_id": dataset_filter["id"],
                                "value": searched_id,
                            },
                            **api_search_kwargs,
                        }
                        logger.info(
                            f"Sending search request for {usgs_collection} with {full_api_search_kwargs}"
                        )

                        results = self._with_auth(
                            api.scene_search, usgs_collection, **full_api_search_kwargs
                        )

                        nb_results = len(results.get("data", {}).get("results", []))
                        logger.info(
                            "Search request returns {} results".format(nb_results)
                        )

                        if nb_results == 1:
                            # search by id using this dataset_filter succeeded
                            break
            else:
                logger.info(
                    f"Sending search request for {usgs_collection} with {api_search_kwargs}"
                )
                results = self._with_auth(
                    api.scene_search, usgs_collection, **api_search_kwargs
                )

            # Map result by entity id
            results_by_entity_id = {}
            for result in results.get("data", {}).get("results", []):
                if (
                    "entityId" in result
                    and result["entityId"] not in results_by_entity_id
                ):
                    results_by_entity_id[result["entityId"]] = result
            logger.debug(
                f"Adapting {len(results_by_entity_id)} plugin results to eodag product representation"
            )

        except USGSError as e:
            logger.warning(
                f"Collection {usgs_collection} may not exist on USGS EE catalog"
            )
            raise e

        # Update results with storage info from download_options()
        assets_by_entityid: dict[str, dict] = {}
        try:

            download_options = self._with_auth(
                api.download_options,
                usgs_collection,
                list(results_by_entity_id.keys()),
            )

            # Index results by entityId, process data to asset structure
            def tree_crawl(
                download_option: dict, usgs_collection: str, base_path: str = ""
            ) -> list[dict]:
                items: list[dict] = []
                item = {
                    "title": download_option.get("displayId"),
                    "href": "{}/{}".format(
                        base_path, download_option.get("displayId")
                    ).lstrip("/"),
                    "type": Mime.guess_file_type(download_option.get("displayId", "")),
                    "roles": ["data"],
                    "file:size": download_option.get("filesize"),
                    "usgs:productId": download_option.get("id"),
                    "usgs:entityId": download_option.get("entityId"),
                    "usgs:type": download_option.get("downloadSystem"),
                }
                if item["usgs:type"] == "ls_zip":
                    item[
                        "href"
                    ] = "https://earthexplorer.usgs.gov/download/external/options/{}/{}/M2M/".format(
                        usgs_collection, item["usgs:entityId"]
                    )
                    item["type"] = "application/zip"
                    item["roles"] = ["archive", "data"]

                if item["usgs:type"] == "dds_ms":
                    item[
                        "href"
                    ] = "https://earthexplorer.usgs.gov/download/external/options/{}/{}/M2M/".format(
                        usgs_collection, item["usgs:entityId"]
                    )
                    item["type"] = "application/gzip"
                    item["roles"] = ["archive", "data"]

                for checksum in download_option.get("checksum", []):
                    if checksum.get("id") == "md5":
                        item["file:checksum"] = checksum.get("value")

                available = (
                    "available" not in download_option
                    or download_option.get("available", False)
                ) or (
                    "bulkAvailable" not in download_option
                    and download_option.get("bulkAvailable", False)
                )

                if available and download_option.get("downloadSystem") in [
                    "ls_s3",
                    "ls_zip",
                    "dds_ms",
                ]:
                    items.append(item)

                # Recursive
                for sub in download_option.get("secondaryDownloads", []):
                    items += tree_crawl(
                        sub, usgs_collection, download_option.get("displayId", "")
                    )

                # Post sort, archives first
                def item_sort(item):
                    if "archive" in item["roles"]:
                        return 0
                    else:
                        return 1

                items.sort(key=item_sort)

                return items

            if download_options.get("data") is not None:
                # index download_data
                for download_option in download_options["data"]:
                    entityId = download_option.get("entityId")
                    if entityId is not None:
                        if entityId not in assets_by_entityid:
                            assets_by_entityid[entityId] = {}
                        for item in tree_crawl(download_option, usgs_collection):
                            assets_by_entityid[entityId][item["href"]] = item

        except Exception as e:
            logger.debug(("usgs api.download_options fails: {}".format(str(e))))
            raise e

        # Post format result with download informations, formatted as assets
        for entityid in results_by_entity_id:
            result = results_by_entity_id[entityid]
            result["collection"] = usgs_collection
            # Inject "assets" in results
            result["assets"] = assets_by_entityid.get(entityid, {})

            product_properties = properties_from_json(
                result, self.config.metadata_mapping
            )
            product = EOProduct(
                collection=collection,
                provider=self.provider,
                properties=product_properties,
                geometry=footprint,
            )
            # Apply asset configuration
            product.assets.update(self.get_assets_from_mapping(result, product))
            products.append(product)

        self._logout()

        if error is not None:
            raise RequestError.from_error(error) from error

        if products:
            # parse total_results
            path_parsed = parse(self.config.pagination["total_items_nb_key_path"])  # type: ignore
            total_results = path_parsed.find(results["data"])[0].value
        else:
            total_results = 0

        formated_result = SearchResult(
            products,
            total_results,
            search_params=search_params,
            next_page_token=results["data"]["nextRecord"],
        )
        return formated_result

    def download(  # type: ignore
        self,
        asset: Asset,
        auth: Optional[AuthBase] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        no_cache: bool = False,
        stream: bool = False,
        **kwargs: Unpack[DownloadConf],
    ) -> Union[Optional[str], StreamResponse]:
        """Download data from USGS catalogues"""

        if progress_callback is None:
            progress_callback = ProgressCallback(disable=True)

        collection = asset.product.collection
        if collection is None and GENERIC_COLLECTION in self.config.products:
            collection = GENERIC_COLLECTION

        # Add configured extension is asset is download_link
        if (
            asset.key == "download_link"
            and collection is not None
            and collection in self.config.products
        ):
            value = self.config.products[collection].get("output_extension", ".tar.gz")
            output_extension = cast(str, value)
            kwargs["output_extension"] = kwargs.get("output_extension", output_extension)  # type: ignore

        # Gather current asset statements
        statements = self.get_statements(asset, **kwargs)

        # Already downloaded ? (cache)
        if not no_cache:
            cache = self.get_cache(asset, statements, stream)
            if cache is not None:
                progress_callback.reset()
                return cache

        usgs_dataset: str = GENERIC_COLLECTION
        if asset.product.collection is not None:
            buffer = self.config.products.get(asset.product.collection, {})
            usgs_dataset = buffer.get("_collection", usgs_dataset)

        # Gather download url
        try:
            url: str = asset.get("href", "")

            for field in ["usgs:entityId", "usgs:productId"]:
                if asset.get(field) is None:
                    raise NotAvailableError(
                        "Asset {} not downloadable, require field {}".format(
                            asset.key, field
                        )
                    )
            download_request_results = self._with_auth(
                api.download_request,
                usgs_dataset,
                asset.get("usgs:entityId"),
                asset.get("usgs:productId"),
            )

            urls = []
            if "data" in download_request_results:
                if "availableDownloads" in download_request_results["data"]:
                    for item in download_request_results["data"]["availableDownloads"]:
                        urls.append(item.get("url"))
                if "preparingDownloads" in download_request_results["data"]:
                    for item in download_request_results["data"]["preparingDownloads"]:
                        urls.append(item.get("url"))

            if len(urls) == 0:
                if stream:
                    raise NotAvailableError(
                        "Asset {} not found in download_request".format(asset.key)
                    )
                else:
                    return None
            url = "{}".format(urls[0])

        except Exception as e:
            raise e

        logger.debug("Download {}".format(url))

        # Try, and retry download
        def now():
            return datetime.datetime.now(datetime.timezone.utc)

        timeout_at = now() + datetime.timedelta(minutes=max(timeout, 0))
        wait_offset = datetime.timedelta(minutes=wait)
        interruption_error = None
        completed = False
        while not completed and interruption_error is None and now() < timeout_at:
            try:
                response = self._download_request(url, timeout=timeout * 60)
                if response is None:
                    raise Exception("no response")
                response.raise_for_status()
                completed = True
            except NotAvailableError as e:
                interruption_error = e
            except Exception as e:
                logger.debug(
                    "Download fails, retry after {} seconds: {}".format(
                        wait_offset.total_seconds(), str(e)
                    )
                )
                time.sleep(wait_offset.total_seconds())

        if interruption_error is not None:
            raise interruption_error

        if not completed:
            self._logout()
            raise TimeoutError("Download fails: timeout")

        # Fill asset fields from retreives data
        self.asset_metadata_from_response(asset, response)

        # Remove previous download
        local_path = statements.get("local_path", None)
        if local_path is None:
            raise DownloadError("Fail to locate download local_file")
        if os.path.isfile(local_path):
            os.remove(local_path)
        elif os.path.isdir(local_path):
            shutil.rmtree(local_path)

        # Rewrite response iterator to include progress_bar display
        sci = ResponseContentIterator(
            response, progress_callback, asset.filename, asset.size
        )

        if not stream:

            # Flat download response to local file
            #   even if no_cache is True
            #   must write a file to return a path
            try:
                with open(local_path, "wb") as fd:
                    for chunk in sci:
                        fd.write(chunk)

                # File has no extension ?
                filename = os.path.basename(local_path)
                pos = filename.rfind(".")
                if pos < 0:
                    ext = Mime.guess_extension_from_fileheaders(local_path)
                    if ext is not None:
                        new_file_path = "{}.{}".format(local_path, ext)
                        os.rename(local_path, new_file_path)
                        local_path = new_file_path

                # Post process archive
                local_path = self.unpack_archive(
                    asset, local_path, progress_callback, **kwargs  # type: ignore
                )

                self.asset_metadata_from_file(asset, local_path)

                # Update cache location
                statements["local_path"] = local_path
                statements["href"] = asset.get("href")
                self.set_statements(asset, statements, **kwargs)

                return local_path
            except Exception as e:
                # Not allow corrumpted download file
                if os.path.isfile(local_path):
                    os.remove(local_path)
                raise e

        else:

            # if allow cache, intercept served chunks to generate local cache
            if not no_cache:

                # During stream service, intercept chunks to save a cache
                passthrough_data = {
                    "fp": open(local_path, "wb"),
                    "asset": asset,
                    "local_path": local_path,
                    "progress_callback": progress_callback,
                    "statements": statements,
                    "kwargs": kwargs,
                }

                # Trigger when stream succedfully finished
                def on_complete():
                    passthrough_data["fp"].close()

                    # Post process archive
                    local_path = self.unpack_archive(
                        passthrough_data["asset"],
                        passthrough_data["local_path"],
                        passthrough_data["progress_callback"],
                        **passthrough_data["kwargs"],
                    )

                    # File has no extension ?
                    if os.path.isfile(local_path):
                        filename = os.path.basename(local_path)
                        pos = filename.rfind(".")
                        if pos < 0:
                            ext = Mime.guess_extension_from_fileheaders(local_path)
                            if ext is not None:
                                new_file_path = "{}.{}".format(local_path, ext)
                                os.rename(local_path, new_file_path)
                                local_path = new_file_path

                    # Update cache location
                    passthrough_data["statements"]["local_path"] = local_path
                    passthrough_data["statements"]["href"] = passthrough_data[
                        "asset"
                    ].get("href")
                    self.set_statements(
                        passthrough_data["asset"],
                        passthrough_data["statements"],
                        **kwargs,
                    )

                sci.on("complete", on_complete)

                # Trigger when stream chunk is transfered
                def on_chunk(chunk: bytes):
                    passthrough_data["fp"].write(chunk)

                sci.on("chunk", on_chunk)

                # Trigger when stream transfer fails
                def on_error(error: Exception):
                    passthrough_data["fp"].close()
                    os.remove(passthrough_data["local_path"])

                sci.on("error", on_error)

            # Stream response
            return StreamResponse(
                content=sci,
                filename=asset.filename,
                size=asset.size,
                headers=HttpUtils.format_headers(response.headers),
                media_type=asset.get("type", Mime.DEFAULT),
                status_code=response.status_code,
                arcname=None,
            )

    def _download_request(
        self, url: str, timeout: float = DEFAULT_DOWNLOAD_TIMEOUT
    ) -> Response:
        ssl_verify = getattr(self.config, "ssl_verify", True)
        try:
            response = requests.get(
                url,
                headers=USER_AGENT,
                timeout=timeout,
                stream=True,
                verify=ssl_verify,
            )
            response.raise_for_status()
        except RequestException as e:
            if e.response and hasattr(e.response, "content"):
                error_message = f"{e.response.content.decode('utf-8')} - {e}"
            else:
                error_message = str(e)
            raise NotAvailableError(error_message)
        except requests.exceptions.Timeout as e:
            if e.response and hasattr(e.response, "content"):
                error_message = f"{e.response.content.decode('utf-8')} - {e}"
            else:
                error_message = str(e)
            raise NotAvailableError(error_message)
        return response


__all__ = ["UsgsApi"]
