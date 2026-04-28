# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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
import os
from typing import TYPE_CHECKING, Annotated, cast

import geojson
from ecmwfapi import ECMWFDataServer, ECMWFService
from ecmwfapi.api import APIException, Connection, get_apikey_values
from pydantic.fields import FieldInfo

from eodag.api.search_result import RawSearchResult
from eodag.plugins.download import FileContentIterator, StreamResponse
from eodag.plugins.search import ECMWFSearch, PreparedSearch, Search, ecmwf_mtd
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    Mime,
    Processor,
    ProgressCallback,
    get_geometry_from_various,
    urlsplit,
)
from eodag.utils.exceptions import AuthenticationError, DownloadError
from eodag.utils.logging import get_logging_verbose

from .base import Api

if TYPE_CHECKING:
    from typing import Any, Optional, Union

    from mypy_boto3_s3 import S3ServiceResource
    from requests.auth import AuthBase

    from eodag.api.product import Asset
    from eodag.api.search_result import SearchResult
    from eodag.config import PluginConfig
    from eodag.types.download_args import DownloadConf
    from eodag.utils import Unpack


logger = logging.getLogger("eodag.apis.ecmwf")

ECMWF_MARS_KNOWN_FORMATS = {"grib": "grib", "netcdf": "nc"}


class EcmwfApi(Api, ECMWFSearch):
    """A plugin that enables to build download-request and download data on ECMWF MARS.

    Builds a single ready-to-download :class:`~eodag.api.product._product.EOProduct`
    during the search stage.

    Download will then be performed on ECMWF Public Datasets (if ``dataset`` parameter
    is in query), or on MARS Operational Archive (if ``dataset`` parameter is not in
    query).

    This class inherits from :class:`~eodag.plugins.apis.base.Api` for compatibility and
    :class:`~eodag.plugins.search.build_search_result.ECMWFSearch` for the creation
    of the search result.

    :param provider: provider name
    :param config: Api plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): EcmwfApi
        * :attr:`~eodag.config.PluginConfig.auth_endpoint` (``str``) (**mandatory**): url of
          the authentication endpoint of the ecmwf api
        * :attr:`~eodag.config.PluginConfig.metadata_mapping` (``dict[str, Union[str, list]]``): how
          parameters should be mapped between the provider and eodag; If a string is given, this is
          the mapping parameter returned by provider -> eodag parameter. If a list with 2 elements
          is given, the first one is the mapping eodag parameter -> provider query parameters
          and the second one the mapping provider result parameter -> eodag parameter
    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        # init self.config.metadata_mapping using Search Base plugin
        config.metadata_mapping = {
            **ecmwf_mtd(),
            **config.metadata_mapping,
        }
        Search.__init__(self, provider, config)

        # needed by QueryStringSearch.build_query_string / format_free_text_search
        self.config.__dict__.setdefault("free_text_search_operations", {})
        # needed for compatibility
        self.config.__dict__.setdefault("pagination", {"next_page_query_obj": "{{}}"})
        self.config.__dict__.setdefault("api_endpoint", "")

    def do_search(
        self, prep: PreparedSearch = PreparedSearch(limit=None), **kwargs: Any
    ) -> RawSearchResult:
        """Should perform the actual search request."""
        raw_search_results = RawSearchResult([{}])
        raw_search_results.search_params = kwargs
        raw_search_results.query_params = (
            prep.query_params if hasattr(prep, "query_params") else {}
        )
        raw_search_results.collection_def_params = (
            prep.collection_def_params if hasattr(prep, "collection_def_params") else {}
        )
        return raw_search_results

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> SearchResult:
        """Build ready-to-download SearchResult"""

        # check collection, dates, geometry, use defaults if not specified
        # collection
        if not kwargs.get("collection"):
            kwargs["collection"] = "%s_%s_%s" % (
                kwargs.get("ecmwf:dataset", "mars"),
                kwargs.get("ecmwf:type", ""),
                kwargs.get("ecmwf:levtype", ""),
            )

        # geometry
        if "geometry" in kwargs:
            kwargs["geometry"] = get_geometry_from_various(geometry=kwargs["geometry"])

        return ECMWFSearch.query(self, prep, **kwargs)

    def authenticate(self) -> dict[str, Optional[str]]:
        """Check credentials and returns information needed for auth

        :returns: {key, url, email} dictionary
        :raises: :class:`~eodag.utils.exceptions.AuthenticationError`
        """
        # Get credentials from eodag or using ecmwf conf
        email = getattr(self.config, "credentials", {}).get("username", None)
        key = getattr(self.config, "credentials", {}).get("password", None)
        url = getattr(self.config, "auth_endpoint", None)

        # if some data missing, Load env
        if not all([email, key, url]):
            key, url, email = get_apikey_values()

        # Check auth parameters
        if email is None or email == "":
            raise AuthenticationError(
                "Please check your ECMWF credentials (missing or empty username)"
            )
        if key is None or key == "":
            raise AuthenticationError(
                "Please check your ECMWF credentials (missing or empty password)"
            )
        if url is None or url == "":
            raise AuthenticationError(
                "Please check your ECMWF credentials (missing or empty auth_endpoint)"
            )

        # APIRequest to check credentials
        ecmwf_connection = Connection(url=url, email=email, key=key)

        try:
            ecmwf_connection.call("{}/{}".format(url, "who-am-i"))
            logger.debug("Credentials checked on ECMWF")
        except APIException as e:
            logger.error(e)
            raise AuthenticationError("Please check your ECMWF credentials.")

        return {"key": key, "url": url, "email": email}

    def download(  # type: ignore
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
        """Download data from ECMWF MARS"""

        # Force create progress_callback
        if not isinstance(progress_callback, ProgressCallback):
            logger.info("Progress bar unavailable")
            progress_callback = ProgressCallback(disable=True)
        progress_callback = cast(ProgressCallback, progress_callback)

        if asset.key == "download_link":
            product_format = asset.product.properties.get("format", "grib")
            product_extension = ECMWF_MARS_KNOWN_FORMATS.get(
                product_format, product_format
            )
            if isinstance(product_extension, str) and "output_extension" not in kwargs:
                kwargs["output_extension"] = ".{}".format(product_extension)  # type: ignore

        # Gather current asset statements
        statements = self.get_statements(asset, **kwargs)
        local_path: str = statements.get("local_path", "")

        # Already downloaded ? (cache)
        if not no_cache:
            cache = self.get_cache(asset, statements, stream)
            if cache is not None:
                progress_callback.reset()
                return cache

        # Check if need order
        max_workers = getattr(self.config, "max_workers", os.cpu_count())

        shared: dict[str, Any] = {"error": None}

        def callback(_, error: Optional[Exception]):
            if error is not None:
                shared["error"] = error
                logger.warning(error)

        taskid = Processor.queue(
            self._download,
            asset,
            local_path,
            **kwargs,
            q_parallelize=max_workers,
            q_callback=callback,
        )
        Processor.wait(taskid)
        if shared["error"] is not None:
            raise shared["error"]

        self._download(asset, local_path, **kwargs)

        # Post process archive
        local_path = self.unpack_archive(asset, local_path, progress_callback, **kwargs)  # type: ignore
        self.asset_metadata_from_file(asset, local_path)

        # Update cache location
        statements["local_path"] = local_path
        statements["href"] = asset.get("href")
        self.set_statements(asset, statements, **kwargs)

        if stream:

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
                return StreamResponse.from_file(local_path)

        else:
            return local_path

    def _download(self, asset: Asset, local_path: str, **kwargs):

        # get download request dict from product.location/eodag:download_link url query string
        # separate url & parameters
        download_request = geojson.loads(urlsplit(asset.get("href")).query)

        # Set verbosity
        eodag_verbosity = get_logging_verbose()
        ecmwf_verbose = False
        ecmwf_log = logger.info
        if eodag_verbosity is not None and eodag_verbosity >= 3:
            # debug verbosity
            ecmwf_verbose = True
            ecmwf_log = logger.debug

        auth_dict = self.authenticate()

        # Send download request to ECMWF web API
        logger.info("Request download on ECMWF: %s" % download_request)

        try:
            if "dataset" in download_request and not download_request[
                "dataset"
            ].startswith("mars_"):
                # Public dataset
                ecmwf_server = ECMWFDataServer(
                    verbose=ecmwf_verbose, log=ecmwf_log, **auth_dict
                )
                ecmwf_server.retrieve(dict(download_request, **{"target": local_path}))
            else:
                # Operational Archive
                ecmwf_server = ECMWFService(
                    service="mars", verbose=ecmwf_verbose, log=ecmwf_log, **auth_dict
                )
                download_request.pop("dataset", None)
                ecmwf_server.execute(download_request, local_path)
        except APIException as e:
            logger.error(e)
            raise DownloadError(e)

        return None

    def clear(self) -> None:
        """Clear search context"""
        pass

    def discover_queryables(
        self,
        **kwargs: Any,
    ) -> Optional[dict[str, Annotated[Any, FieldInfo]]]:
        """Fetch queryables list from provider using metadata mapping

        :param kwargs: additional filters for queryables (`collection` and other search
                       arguments)
        :returns: fetched queryable parameters dict
        """
        collection = kwargs.get("collection")
        return self.queryables_from_metadata_mapping(collection)


__all__ = ["EcmwfApi"]
