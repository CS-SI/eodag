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
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import re

import numpy
import rasterio
import requests
import six
import xarray as xr
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from requests import HTTPError
from shapely import geometry, geos, wkb, wkt

from eodag.api.product.drivers import DRIVERS, NoDriver
from eodag.api.product.metadata_mapping import NOT_AVAILABLE, NOT_MAPPED
from eodag.plugins.download.base import DEFAULT_DOWNLOAD_TIMEOUT, DEFAULT_DOWNLOAD_WAIT
from eodag.utils import ProgressCallback
from eodag.utils.exceptions import DownloadError, UnsupportedDatasetAddressScheme

try:
    from shapely.errors import TopologicalError
except ImportError:
    from shapely.geos import TopologicalError


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
    :type provider: str or unicode
    :param properties: The metadata of the product
    :type properties: dict

    .. note::
        The geojson spec `enforces <https://github.com/geojson/draft-geojson/pull/6>`_
        the expression of geometries as
        WGS84 CRS (EPSG:4326) coordinates and EOProduct is intended to be transmitted
        as geojson between applications. Therefore it stores geometries in the before
        mentioned CRS.
    """

    def __init__(self, provider, properties, *args, **kwargs):
        self.provider = provider
        self.product_type = kwargs.get("productType")
        self.location = self.remote_location = properties.get("downloadLink", "")
        self.properties = {
            key: value
            for key, value in properties.items()
            if key != "geometry" and value not in [NOT_MAPPED, NOT_AVAILABLE]
        }
        product_geometry = properties["geometry"]
        # Let's try 'latmin lonmin latmax lonmax'
        if isinstance(product_geometry, six.string_types):
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
        if isinstance(product_geometry, six.string_types):
            try:
                product_geometry = wkt.loads(product_geometry)
            except geos.WKTReadingError:
                try:
                    product_geometry = wkb.loads(product_geometry)
                # Also catching TypeError because product_geometry can be a unicode
                # string and not a bytes string
                except (geos.WKBReadingError, TypeError):
                    # Giv up!
                    raise
        self.geometry = self.search_intersection = geometry.shape(product_geometry)
        self.search_args = args
        self.search_kwargs = kwargs
        if self.search_kwargs.get("geometry") is not None:
            searched_bbox = self.search_kwargs["geometry"]
            searched_bbox_as_shape = geometry.box(
                searched_bbox["lonmin"],
                searched_bbox["latmin"],
                searched_bbox["lonmax"],
                searched_bbox["latmax"],
            )
            try:
                self.search_intersection = self.geometry.intersection(
                    searched_bbox_as_shape
                )
            except TopologicalError:
                logger.warning(
                    "Unable to intersect the requested extent: %s with the product "
                    "geometry: %s",
                    searched_bbox_as_shape,
                    product_geometry,
                )
                self.search_intersection = None
        self.driver = DRIVERS.get(self.product_type, NoDriver())
        self.downloader = None
        self.downloader_auth = None

    def get_data(self, crs, resolution, band, extent):
        """Retrieves all or part of the raster data abstracted by the :class:`EOProduct`

        :param crs: The coordinate reference system in which the dataset should be
                    returned
        :type crs: str or unicode
        :param resolution: The resolution in which the dataset should be returned
                           (given in the unit of the crs)
        :type resolution: float
        :param band: The band of the dataset to retrieve (e.g.: 'B01')
        :type band: str or unicode
        :param extent: The coordinates on which to zoom as a tuple
                       (min_x, min_y, max_x, max_y) in the given `crs`
        :type extent: (float, float, float, float)
        :returns: The numeric matrix corresponding to the sub dataset or an empty
                  array if unable to get the data
        :rtype: xarray.DataArray
        """
        fail_value = xr.DataArray(numpy.empty(0))
        try:
            dataset_address = self.driver.get_data_address(self, band)
        except UnsupportedDatasetAddressScheme:
            logger.warning(
                "Eodag does not support getting data from distant sources by now. "
                "Falling back to first downloading the product and then getting the "
                "data..."
            )
            try:
                path_of_downloaded_file = self.download()
            except (RuntimeError, DownloadError):
                import traceback

                logger.warning(
                    "Error while trying to download the product:\n %s",
                    traceback.format_exc(),
                )
                logger.warning(
                    "There might be no download plugin registered for this EO product. "
                    "Try performing: product.register_downloader(download_plugin, "
                    "auth_plugin) before trying to call product.get_data(...)"
                )
                return fail_value
            if not path_of_downloaded_file:
                return fail_value
            dataset_address = self.driver.get_data_address(self, band)
        min_x, min_y, max_x, max_y = extent
        height = int((max_y - min_y) / resolution)
        width = int((max_x - min_x) / resolution)
        out_shape = (width, height)
        with rasterio.open(dataset_address) as src:
            with WarpedVRT(src, crs=crs, resampling=Resampling.bilinear) as vrt:
                array = vrt.read(
                    1,
                    window=vrt.window(*extent),
                    out_shape=out_shape,
                    resampling=Resampling.bilinear,
                )
                return xr.DataArray(array)

    def as_dict(self):
        """Builds a representation of EOProduct as a dictionary to enable its geojson
        serialization

        :returns: The representation of a :class:`~eodag.api.product.EOProduct` as a
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
        """Builds an :class:`~eodag.api.product.EOProduct` object from its
        representation as geojson

        :param feature: The representation of a :class:`~eodag.api.product.EOProduct`
                        as a Python dict
        :type feature: dict
        :returns: An instance of :class:`~eodag.api.product.EOProduct`
        :rtype: :class:`~eodag.api.product.EOProduct`
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
        return "{}(id={}, provider={})".format(
            self.__class__.__name__, self.properties["id"], self.provider
        )

    def encode(self, raster, encoding="protobuf"):
        """Encode the subset to a network-compatible format.

        :param raster: The raster data to encode
        :type raster: xarray.DataArray
        :param encoding: The encoding of the export
        :type encoding: str or unicode
        :return: The data encoded in the specified encoding
        :rtype: bytes
        """
        # If no encoding return an empty byte
        if not encoding:
            logger.warning("Trying to encode a raster without specifying an encoding")
            return b""
        strategy = getattr(self, "_{encoding}".format(**locals()), None)
        if strategy:
            return strategy(raster)
        logger.error("Unknown encoding: %s", encoding)
        return b""

    def _protobuf(self, raster):
        """Google's Protocol buffers encoding strategy.

        :param raster: The raster to encode
        :type raster: xarray.DataArray
        :returns: The raster data represented by this subset in protocol buffers
                  encoding
        :rtype: bytes
        """
        from eodag.api.product.protobuf import eo_product_pb2

        subdataset = eo_product_pb2.EOProductSubdataset()
        subdataset.id = self.properties["id"]
        subdataset.producer = self.provider
        subdataset.product_type = self.product_type
        subdataset.platform = self.properties["platformSerialIdentifier"]
        subdataset.sensor = self.properties["instrument"]
        data = subdataset.data
        data.array.extend(list(raster.values.flatten().astype(int)))
        data.shape.extend(list(raster.values.shape))
        data.dtype = raster.values.dtype.name
        return subdataset.SerializeToString()

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
        self.location = self.location % vars(self.downloader.config)
        self.remote_location = self.remote_location % vars(self.downloader.config)
        for k, v in self.properties.items():
            if isinstance(v, six.string_types):
                try:
                    self.properties[k] = v % vars(self.downloader.config)
                except TypeError:
                    pass

    def download(
        self,
        progress_callback=None,
        wait=DEFAULT_DOWNLOAD_WAIT,
        timeout=DEFAULT_DOWNLOAD_TIMEOUT,
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
        :returns: The absolute path to the downloaded product on the local filesystem
        :rtype: str or unicode
        :raises: :class:`~eodag.utils.exceptions.PluginImplementationError`
        :raises: :class:`RuntimeError`
        """
        if progress_callback is None:
            progress_callback = ProgressCallback()
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
        fs_location = self.downloader.download(
            self,
            auth=auth,
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
        )
        if fs_location is None:
            raise DownloadError(
                "Invalid file location returned by download process: '{}'".format(
                    fs_location
                )
            )
        self.location = "file://{}".format(fs_location)
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
        return self.location

    def get_quicklook(self, filename=None, base_dir=None, progress_callback=None):
        """Download the quick look image of a given EOProduct from its provider if it
        exists.

        :param filename: (optional) the name to give to the downloaded quicklook.
        :type filename: str (Python 3) or unicode (Python 2)
        :param base_dir: (optional) the absolute path of the directory where to store
                         the quicklooks in the filesystem. If it is not given, it
                         defaults to the `quicklooks` directory under this EO product
                         downloader's ``outputs_prefix`` config param
        :type base_dir: str (Python 3) or unicode (Python 2)
        :param progress_callback: (optional) A method or a callable object
                                  which takes a current size and a maximum
                                  size as inputs and handle progress bar
                                  creation and update to give the user a
                                  feedback on the download progress
        :type progress_callback: :class:`~eodag.utils.ProgressCallback` or None
        :returns: The absolute path of the downloaded quicklook
        :rtype: str (Python 3) or unicode (Python 2)

        .. versionchanged::
            1.0

                * Added the ``base_dir`` optional parameter to choose where to download
                  the retrieved quicklook
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

        if progress_callback is None:
            progress_callback = ProgressCallback()

        if self.properties["quicklook"] is None:
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
            # it is a HTTP URL. If not, we assume it is a byte string, in which case
            # we just write the content into the quicklook_file and return it.
            if not (
                self.properties["quicklook"].startswith("http")
                or self.properties["quicklook"].startswith("https")
            ):
                with open(quicklook_file, "wb") as fd:
                    fd.write(self.properties["quicklook"])
                return quicklook_file

            auth = (
                self.downloader_auth.authenticate()
                if self.downloader_auth is not None
                else None
            )
            with requests.get(
                self.properties["quicklook"], stream=True, auth=auth
            ) as stream:
                try:
                    stream.raise_for_status()
                except HTTPError as e:
                    import traceback as tb

                    logger.error("Error while getting resource :\n%s", tb.format_exc())
                    return str(e)
                else:
                    stream_size = int(stream.headers.get("content-length", 0))
                    with open(quicklook_file, "wb") as fhandle:
                        for chunk in stream.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                fhandle.write(chunk)
                                progress_callback(len(chunk), stream_size)
                    logger.info("Download recorded in %s", quicklook_file)
        return quicklook_file
