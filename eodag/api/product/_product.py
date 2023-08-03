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
import base64
import logging
import os
import re
import urllib.parse

import requests
import shapely.errors
from requests import RequestException
from shapely import geometry, wkb, wkt
from shapely.errors import ShapelyError

from eodag.api.product.drivers import DRIVERS, NoDriver
from eodag.api.product.metadata_mapping import NOT_AVAILABLE, NOT_MAPPED
from eodag.plugins.download.base import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
)
from eodag.utils import USER_AGENT, ProgressCallback, get_geometry_from_various
from eodag.utils.exceptions import DownloadError, MisconfiguredError

try:
    from shapely.errors import GEOSException
except ImportError:
    # shapely < 2.0 compatibility
    from shapely.errors import TopologicalError as GEOSException


logger = logging.getLogger("eodag.api.product")


class EOProduct(object):
    """A wrapper around an Earth Observation Product originating from a search.

    Every Search plugin instance must build an instance of this class for each of
    the result of its query method, and return a list of such instances. A EOProduct
    has a `location` attribute that initially points to its remote location, but is
    later changed to point to its path on the filesystem when the product has been
    downloaded. It also has a `remote_location` that always points to the remote
    location, so that the product can be downloaded at anytime if it is deleted from
    the filesystem. An EOProduct instance also has a reference to the search
    parameters that led to its creation.

    :param provider: The provider from which the product originates
    :type provider: str
    :param properties: The metadata of the product
    :type properties: dict
    :ivar product_type: The product type
    :vartype product_type: str
    :ivar location: The path to the product, either remote or local if downloaded
    :vartype location: str
    :ivar remote_location: The remote path to the product
    :vartype remote_location: str
    :ivar search_kwargs: The search kwargs used by eodag to search for the product
    :vartype search_kwargs: Any
    :ivar geometry: The geometry of the product
    :vartype geometry: :class:`shapely.geometry.base.BaseGeometry`
    :ivar search_intersection: The intersection between the product's geometry
                               and the search area.
    :vartype search_intersection: :class:`shapely.geometry.base.BaseGeometry` or None


    .. note::
        The geojson spec `enforces <https://github.com/geojson/draft-geojson/pull/6>`_
        the expression of geometries as
        WGS84 CRS (EPSG:4326) coordinates and EOProduct is intended to be transmitted
        as geojson between applications. Therefore it stores geometries in the before
        mentioned CRS.
    """

    def __init__(self, provider, properties, **kwargs):
        self.provider = provider
        self.product_type = kwargs.get("productType")
        self.location = self.remote_location = properties.get("downloadLink", "")
        self.properties = {
            key: value
            for key, value in properties.items()
            if key != "geometry"
            and value != NOT_MAPPED
            and NOT_AVAILABLE not in str(value)
        }
        if "geometry" not in properties or (
            (
                properties["geometry"] == NOT_AVAILABLE
                or properties["geometry"] == NOT_MAPPED
            )
            and "defaultGeometry" not in properties
        ):
            raise MisconfiguredError(
                f"No geometry available to build EOProduct(id={properties.get('id', None)}, provider={provider})"
            )
        elif properties["geometry"] == NOT_AVAILABLE:
            product_geometry = properties["defaultGeometry"]
        else:
            product_geometry = properties["geometry"]
        # Let's try 'latmin lonmin latmax lonmax'
        if isinstance(product_geometry, str):
            bbox_pattern = re.compile(
                r"^(-?\d+\.?\d*) (-?\d+\.?\d*) (-?\d+\.?\d*) (-?\d+\.?\d*)$"
            )
            found_bbox = bbox_pattern.match(product_geometry)
            if found_bbox:
                coords = found_bbox.groups()
                if len(coords) == 4:
                    product_geometry = geometry.box(
                        float(coords[1]),
                        float(coords[0]),
                        float(coords[3]),
                        float(coords[2]),
                    )
        # Best effort to understand provider specific geometry (the default is to
        # assume an object implementing the Geo Interface: see
        # https://gist.github.com/2217756)
        if isinstance(product_geometry, str):
            try:
                product_geometry = wkt.loads(product_geometry)
            except (ShapelyError, GEOSException):
                try:
                    product_geometry = wkb.loads(product_geometry)
                # Also catching TypeError because product_geometry can be a
                # string and not a bytes string
                except (ShapelyError, GEOSException, TypeError):
                    # Giv up!
                    raise
        self.geometry = self.search_intersection = geometry.shape(product_geometry)
        self.search_kwargs = kwargs
        if self.search_kwargs.get("geometry") is not None:
            searched_geom = get_geometry_from_various(
                **{"geometry": self.search_kwargs["geometry"]}
            )
            try:
                self.search_intersection = self.geometry.intersection(searched_geom)
            except (GEOSException, ShapelyError):
                logger.warning(
                    "Unable to intersect the requested extent: %s with the product "
                    "geometry: %s",
                    searched_geom,
                    product_geometry,
                )
                self.search_intersection = None
        self.driver = self.get_driver()
        self.downloader = None
        self.downloader_auth = None

    def as_dict(self):
        """Builds a representation of EOProduct as a dictionary to enable its geojson
        serialization

        :returns: The representation of a :class:`~eodag.api.product._product.EOProduct` as a
                  Python dict
        :rtype: dict
        """
        search_intersection = None
        if self.search_intersection is not None:
            search_intersection = geometry.mapping(self.search_intersection)
        geojson_repr = {
            "type": "Feature",
            "geometry": geometry.mapping(self.geometry),
            "id": self.properties["id"],
            "properties": {
                "eodag_product_type": self.product_type,
                "eodag_provider": self.provider,
                "eodag_search_intersection": search_intersection,
            },
        }
        geojson_repr["properties"].update(
            {
                key: value
                for key, value in self.properties.items()
                if key not in ("geometry", "id")
            }
        )
        return geojson_repr

    @classmethod
    def from_geojson(cls, feature):
        """Builds an :class:`~eodag.api.product._product.EOProduct` object from its
        representation as geojson

        :param feature: The representation of a :class:`~eodag.api.product._product.EOProduct`
                        as a Python dict
        :type feature: dict
        :returns: An instance of :class:`~eodag.api.product._product.EOProduct`
        :rtype: :class:`~eodag.api.product._product.EOProduct`
        """
        properties = feature["properties"]
        properties["geometry"] = feature["geometry"]
        properties["id"] = feature["id"]
        provider = feature["properties"]["eodag_provider"]
        product_type = feature["properties"]["eodag_product_type"]
        obj = cls(provider, properties, productType=product_type)
        obj.search_intersection = geometry.shape(
            feature["properties"]["eodag_search_intersection"]
        )
        return obj

    # Implementation of geo-interface protocol (See
    # https://gist.github.com/sgillies/2217756)
    __geo_interface__ = property(as_dict)

    def __repr__(self):
        try:
            return "{}(id={}, provider={})".format(
                self.__class__.__name__, self.properties["id"], self.provider
            )
        except KeyError as e:
            raise MisconfiguredError(
                f"Unable to get {e.args[0]} key from EOProduct.properties"
            )

    def register_downloader(self, downloader, authenticator):
        """Give to the product the information needed to download itself.

        :param downloader: The download method that it can use
        :type downloader: Concrete subclass of
                          :class:`~eodag.plugins.download.base.Download` or
                          :class:`~eodag.plugins.api.base.Api`
        :param authenticator: The authentication method needed to perform the download
        :type authenticator: Concrete subclass of
                             :class:`~eodag.plugins.authentication.base.Authentication`
        """
        self.downloader = downloader
        self.downloader_auth = authenticator

        # resolve locations and properties if needed with downloader configuration
        location_attrs = ("location", "remote_location")
        for location_attr in location_attrs:
            try:
                setattr(
                    self,
                    location_attr,
                    urllib.parse.unquote(getattr(self, location_attr))
                    % vars(self.downloader.config),
                )
            except ValueError as e:
                logger.debug(
                    f"Could not resolve product.{location_attr} ({getattr(self, location_attr)})"
                    f" in register_downloader: {str(e)}"
                )

        for k, v in self.properties.items():
            if isinstance(v, str):
                try:
                    if "%" in v:
                        parsed = urllib.parse.urlparse(v)
                        prop = urllib.parse.unquote(parsed.path) % vars(
                            self.downloader.config
                        )
                        parsed = parsed._replace(path=urllib.parse.quote(prop))
                        self.properties[k] = urllib.parse.urlunparse(parsed)
                    else:
                        self.properties[k] = v % vars(self.downloader.config)
                except (TypeError, ValueError) as e:
                    logger.debug(
                        f"Could not resolve {k} property ({v}) in register_downloader: {str(e)}"
                    )

    def download(
        self,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs,
    ):
        """Download the EO product using the provided download plugin and the
        authenticator if necessary.

        The actual download of the product occurs only at the first call of this
        method. A side effect of this method is that it changes the ``location``
        attribute of an EOProduct, from its remote address to the local address.

        :param progress_callback: (optional) A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :type progress_callback: :class:`~eodag.utils.ProgressCallback` or None
        :param wait: (optional) If download fails, wait time in minutes between
                     two download tries
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes
                        before stop retrying to download
        :type timeout: int
        :param kwargs: `outputs_prefix` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :type kwargs: Union[str, bool, dict]
        :returns: The absolute path to the downloaded product on the local filesystem
        :rtype: str
        :raises: :class:`~eodag.utils.exceptions.PluginImplementationError`
        :raises: :class:`RuntimeError`
        """
        if self.downloader is None:
            raise RuntimeError(
                "EO product is unable to download itself due to lacking of a "
                "download plugin"
            )

        auth = (
            self.downloader_auth.authenticate()
            if self.downloader_auth is not None
            else self.downloader_auth
        )

        # resolve remote location if needed with downloader configuration
        self.remote_location = urllib.parse.unquote(self.remote_location) % vars(
            self.downloader.config
        )
        if not self.location.startswith("file"):
            self.location = urllib.parse.unquote(self.location)

        progress_callback, close_progress_callback = self._init_progress_bar(
            progress_callback
        )

        fs_path = self.downloader.download(
            self,
            auth=auth,
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
            **kwargs,
        )

        # close progress bar if needed
        if close_progress_callback:
            progress_callback.close()

        if fs_path is None:
            raise DownloadError("Missing file location returned by download process")
        logger.debug(
            "Product location updated from '%s' to '%s'",
            self.remote_location,
            self.location,
        )
        logger.info(
            "Remote location of the product is still available through its "
            "'remote_location' property: %s",
            self.remote_location,
        )

        return fs_path

    def _init_progress_bar(self, progress_callback):
        # progress bar init
        if progress_callback is None:
            progress_callback = ProgressCallback(position=1)
            # one shot progress callback to close after download
            close_progress_callback = True
        else:
            close_progress_callback = False
            # update units as bar may have been previously used for extraction
            progress_callback.unit = "B"
            progress_callback.unit_scale = True
        progress_callback.desc = str(self.properties.get("id", ""))
        progress_callback.refresh()
        return [progress_callback, close_progress_callback]

    def get_quicklook(self, filename=None, base_dir=None, progress_callback=None):
        """Download the quicklook image of a given EOProduct from its provider if it
        exists.

        :param filename: (optional) The name to give to the downloaded quicklook. If not
                         given, it defaults to the product's ID (without file extension).
        :type filename: str
        :param base_dir: (optional) The absolute path of the directory where to store
                         the quicklooks in the filesystem. If not given, it defaults to the
                         `quicklooks` directory under this EO product downloader's ``outputs_prefix``
                         config param (e.g. '/tmp/quicklooks/')
        :type base_dir: str
        :param progress_callback: (optional) A method or a callable object which takes
                                   a current size and a maximum size as inputs and handle progress bar
                                   creation and update to give the user a feedback on the download progress
        :type progress_callback: :class:`~eodag.utils.ProgressCallback` or None
        :returns: The absolute path of the downloaded quicklook
        :rtype: str
        """

        def format_quicklook_address():
            """If the quicklook address is a Python format string, resolve the
            formatting with the properties of the product."""
            fstrmatch = re.match(r".*{.+}*.*", self.properties["quicklook"])
            if fstrmatch:
                self.properties["quicklook"].format(
                    {
                        prop_key: prop_val
                        for prop_key, prop_val in self.properties.items()
                        if prop_key != "quicklook"
                    }
                )

        # progress bar init
        if progress_callback is None:
            progress_callback = ProgressCallback()
            # one shot progress callback to close after download
            close_progress_callback = True
        else:
            close_progress_callback = False
            # update units as bar may have been previously used for extraction
            progress_callback.unit = "B"
            progress_callback.unit_scale = True
        progress_callback.desc = "quicklooks/%s" % self.properties.get("id", "")

        if self.properties.get("quicklook", None) is None:
            logger.warning(
                "Missing information to retrieve quicklook for EO product: %s",
                self.properties["id"],
            )
            return ""

        format_quicklook_address()

        if base_dir is not None:
            quicklooks_base_dir = os.path.abspath(os.path.realpath(base_dir))
        else:
            quicklooks_base_dir = os.path.join(
                self.downloader.config.outputs_prefix, "quicklooks"
            )
        if not os.path.isdir(quicklooks_base_dir):
            os.makedirs(quicklooks_base_dir)
        quicklook_file = os.path.join(
            quicklooks_base_dir,
            filename if filename is not None else self.properties["id"],
        )

        if not os.path.isfile(quicklook_file):
            # VERY SPECIAL CASE (introduced by the onda provider): first check if
            # it is a HTTP URL. If not, we assume it is a base64 string, in which case
            # we just decode the content, write it into the quicklook_file and return it.
            if not (
                self.properties["quicklook"].startswith("http")
                or self.properties["quicklook"].startswith("https")
            ):
                with open(quicklook_file, "wb") as fd:
                    img = self.properties["quicklook"].encode("ascii")
                    fd.write(base64.b64decode(img))
                return quicklook_file

            auth = (
                self.downloader_auth.authenticate()
                if self.downloader_auth is not None
                else None
            )
            with requests.get(
                self.properties["quicklook"],
                stream=True,
                auth=auth,
                headers=USER_AGENT,
                timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            ) as stream:
                try:
                    stream.raise_for_status()
                except RequestException as e:
                    import traceback as tb

                    logger.error("Error while getting resource :\n%s", tb.format_exc())
                    return str(e)
                else:
                    stream_size = int(stream.headers.get("content-length", 0))
                    progress_callback.reset(stream_size)
                    with open(quicklook_file, "wb") as fhandle:
                        for chunk in stream.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                fhandle.write(chunk)
                                progress_callback(len(chunk))
                    logger.info("Download recorded in %s", quicklook_file)

            # close progress bar if needed
            if close_progress_callback:
                progress_callback.close()

        return quicklook_file

    def get_driver(self):
        """Get the most appropriate driver"""
        try:
            for driver_conf in DRIVERS:
                if all([criteria(self) for criteria in driver_conf["criteria"]]):
                    return driver_conf["driver"]
        except TypeError:
            logger.warning(
                "Drivers definition seems out-of-date, please update eodag-cube"
            )
            pass
        return NoDriver()
