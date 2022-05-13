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
import hashlib
import logging

from ecmwfapi import ECMWFDataServer, ECMWFService
from ecmwfapi.api import APIException, Connection, get_apikey_values

from eodag import EOProduct
from eodag.api.product.metadata_mapping import NOT_AVAILABLE, properties_from_json
from eodag.plugins.apis.base import Api
from eodag.plugins.download.base import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    Download,
)
from eodag.plugins.search.qssearch import QueryStringSearch
from eodag.utils import get_geometry_from_various, parse_qsl, path_to_uri, urlsplit
from eodag.utils.exceptions import AuthenticationError, DownloadError, ValidationError
from eodag.utils.logging import get_logging_verbose

logger = logging.getLogger("eodag.plugins.apis.ecmwf")

ECMWF_MARS_KNOWN_FORMATS = {"grib": "grib", "netcdf": "nc"}


class EcmwfApi(Download, Api, QueryStringSearch):
    """A plugin that enables to build download-request and download data on ECMWF MARS.

    Builds a single ready-to-download :class:`~eodag.api.product._product.EOProduct`
    during the search stage.

    Download will then be performed on ECMWF Public Datasets (if ``dataset`` parameter
    is in query), or on MARS Operational Archive (if ``dataset`` parameter is not in
    query).

    This class inherits from :class:`~eodag.plugins.apis.base.Api` for compatibility,
    :class:`~eodag.plugins.download.base.Download` for download methods, and
    :class:`~eodag.plugins.search.qssearch.QueryStringSearch` for metadata-mapping and
    query build methods.
    """

    def __init__(self, provider, config):
        # init self.config.metadata_mapping using Search Base plugin
        super(QueryStringSearch, self).__init__(provider, config)

        # needed by QueryStringSearch.build_query_string / format_free_text_search
        self.config.__dict__.setdefault("free_text_search_operations", {})
        # needed for compatibility
        self.config.__dict__.setdefault("pagination", {})

    def query(
        self, product_type=None, items_per_page=None, page=None, count=True, **kwargs
    ):
        """Build ready-to-download SearchResult"""

        # check some mandatory parameters
        # start date
        if "startTimeFromAscendingNode" not in kwargs:
            raise ValidationError("Required start date is missing")
        # end date
        if "completionTimeFromAscendingNode" not in kwargs:
            raise ValidationError("Required end date is missing")

        product_type = kwargs.get("productType")

        # Map query args to properties
        product_properties = kwargs
        product_properties.pop("auth", None)
        # geometry
        search_geometry = product_properties.get("geometry", None) or [
            -180,
            -90,
            180,
            90,
        ]
        product_geometry = get_geometry_from_various(geometry=search_geometry)
        product_properties["geometry"] = product_geometry

        # add product_type specific properties from provider configuration (overriden by query args)
        product_properties = dict(
            self.config.products.get(product_type, {}), **product_properties
        )

        # properties mapped using provider configuration
        product_properties = properties_from_json(
            product_properties, self.config.metadata_mapping
        )

        # build query string & parameters dict using from available mapped properties
        product_available_properties = {
            k: v for (k, v) in product_properties.items() if v != NOT_AVAILABLE
        }
        qp, qs = self.build_query_string(product_type, **product_available_properties)

        # query hash, will be used to build a product id
        query_hash = hashlib.sha1(str(qs).encode("UTF-8")).hexdigest()

        # build product id
        if product_type is not None:
            id_prefix = product_type
        else:
            id_prefix = (
                "%s_%s_%s"
                % (
                    qp.get("dataset", "mars"),
                    qp.get("type", ""),
                    qp.get("levtype", ""),
                )
            ).upper()

        product_id = "%s_%s_%s" % (
            id_prefix,
            qp["date"][0].split("/")[0].replace("-", ""),
            query_hash,
        )
        product_properties["id"] = product_properties["title"] = product_id

        # update downloadLink
        product_properties["downloadLink"] += f"?{qs}"

        product = EOProduct(
            provider=self.provider,
            productType=product_type,
            properties=product_properties,
        )
        # use product_type_config as default properties
        product.properties = dict(
            getattr(self.config, "product_type_config", {}), **product.properties
        )

        results_count = 1
        return [
            product,
        ], results_count

    def authenticate(self):
        """Check credentials and returns information needed for auth

        :returns: {key, url, email} dictionary
        :rtype: dict
        :raises: :class:`~eodag.utils.exceptions.AuthenticationError`
        """
        # Get credentials from eodag or using ecmwf conf
        email = getattr(self.config, "credentials", {}).get("username", None)
        key = getattr(self.config, "credentials", {}).get("password", None)
        url = getattr(self.config, "api_endpoint", None)
        if not all([email, key, url]):
            key, url, email = get_apikey_values()

        # APIRequest to check credentials
        ecmwf_connection = Connection(
            url=url,
            email=email,
            key=key,
        )
        try:
            ecmwf_connection.call("{}/{}".format(url, "who-am-i"))
            logger.debug("Credentials checked on ECMWF")
        except APIException as e:
            logger.error(e)
            raise AuthenticationError("Please check your ECMWF credentials.")

        return {"key": key, "url": url, "email": email}

    def download(self, product, auth=None, progress_callback=None, **kwargs):
        """Download data from ECMWF MARS"""

        product_extension = ECMWF_MARS_KNOWN_FORMATS[
            product.properties.get("format", "grib")
        ]

        # Prepare download
        fs_path, record_filename = self._prepare_download(
            product,
            progress_callback=progress_callback,
            outputs_extension=f".{product_extension}",
            **kwargs,
        )

        if not fs_path or not record_filename:
            if fs_path:
                product.location = path_to_uri(fs_path)
            return fs_path

        # get download request dict from product.location/downloadLink url query string
        download_request = dict(parse_qsl(urlsplit(product.location).query))

        # Set verbosity
        eodag_verbosity = get_logging_verbose()
        if eodag_verbosity is not None and eodag_verbosity >= 3:
            # debug verbosity
            ecmwf_verbose = True
            ecmwf_log = logger.debug
        else:
            # default verbosity
            ecmwf_verbose = False
            ecmwf_log = logger.info

        auth_dict = self.authenticate()

        # Send download request to ECMWF web API
        logger.info("Request download on ECMWF: %s" % download_request)
        try:
            if "dataset" in download_request:
                # Public dataset
                ecmwf_server = ECMWFDataServer(
                    verbose=ecmwf_verbose, log=ecmwf_log, **auth_dict
                )
                ecmwf_server.retrieve(dict(download_request, **{"target": fs_path}))
            else:
                # Operational Archive
                ecmwf_server = ECMWFService(
                    service="mars", verbose=ecmwf_verbose, log=ecmwf_log, **auth_dict
                )
                ecmwf_server.execute(download_request, fs_path)
        except APIException as e:
            logger.error(e)
            raise DownloadError(e)

        with open(record_filename, "w") as fh:
            fh.write(product.properties["downloadLink"])
        logger.debug("Download recorded in %s", record_filename)

        # do not try to extract or delete grib/netcdf
        kwargs["extract"] = False

        product_path = self._finalize(
            fs_path,
            progress_callback=progress_callback,
            outputs_extension=f".{product_extension}",
            **kwargs,
        )
        product.location = path_to_uri(product_path)
        return product_path

    def download_all(
        self,
        products,
        auth=None,
        downloaded_callback=None,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs,
    ):
        """
        Download all using parent (base plugin) method
        """
        return super(EcmwfApi, self).download_all(
            products,
            auth=auth,
            downloaded_callback=downloaded_callback,
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
            **kwargs,
        )
