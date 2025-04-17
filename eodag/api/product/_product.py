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

import base64
import logging
import os
import re
import tempfile
from typing import TYPE_CHECKING, Any, Optional, Union

import requests
from requests import RequestException
from requests.auth import AuthBase
from shapely import geometry
from shapely.errors import ShapelyError

try:
    # import from eodag-cube if installed
    from eodag_cube.api.product import (  # pyright: ignore[reportMissingImports]
        AssetsDict,
    )
except ImportError:
    from eodag.api.product._assets import AssetsDict

from eodag.api.product.drivers import DRIVERS, LEGACY_DRIVERS, NoDriver
from eodag.api.product.metadata_mapping import (
    DEFAULT_GEOMETRY,
    NOT_AVAILABLE,
    NOT_MAPPED,
)
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
    USER_AGENT,
    ProgressCallback,
    get_geometry_from_various,
)
from eodag.utils.exceptions import DownloadError, MisconfiguredError
from eodag.utils.repr import dict_to_html_table

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from eodag.api.product.drivers.base import DatasetDriver
    from eodag.plugins.apis.base import Api
    from eodag.plugins.authentication.base import Authentication
    from eodag.plugins.download.base import Download
    from eodag.types.download_args import DownloadConf
    from eodag.utils import Unpack

try:
    from shapely.errors import GEOSException
except ImportError:
    # shapely < 2.0 compatibility
    from shapely.errors import TopologicalError as GEOSException


logger = logging.getLogger("eodag.product")


class EOProduct:
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
    :param properties: The metadata of the product

    .. note::
        The geojson spec `enforces <https://github.com/geojson/draft-geojson/pull/6>`_
        the expression of geometries as
        WGS84 CRS (EPSG:4326) coordinates and EOProduct is intended to be transmitted
        as geojson between applications. Therefore it stores geometries in the before
        mentioned CRS.
    """

    #: The provider from which the product originates
    provider: str
    #: The metadata of the product
    properties: dict[str, Any]
    #: The product type
    product_type: Optional[str]
    #: The geometry of the product
    geometry: BaseGeometry
    #: The intersection between the product's geometry and the search area.
    search_intersection: Optional[BaseGeometry]
    #: The path to the product, either remote or local if downloaded
    location: str
    #: The remote path to the product
    remote_location: str
    #: Assets of the product
    assets: AssetsDict
    #: Driver enables additional methods to be called on the EOProduct
    driver: DatasetDriver
    #: Product data filename, stored during download
    filename: str
    #: Product search keyword arguments, stored during search
    search_kwargs: Any

    def __init__(
        self, provider: str, properties: dict[str, Any], **kwargs: Any
    ) -> None:
        self.provider = provider
        self.product_type = kwargs.get("productType")
        self.location = self.remote_location = properties.get("downloadLink", "")
        self.assets = AssetsDict(self)
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
        elif not properties["geometry"] or properties["geometry"] == NOT_AVAILABLE:
            product_geometry = properties.pop("defaultGeometry", DEFAULT_GEOMETRY)
        else:
            product_geometry = properties["geometry"]

        self.geometry = self.search_intersection = get_geometry_from_various(
            geometry=product_geometry
        )

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
        self.downloader: Optional[Union[Api, Download]] = None
        self.downloader_auth: Optional[Authentication] = None

    def as_dict(self) -> dict[str, Any]:
        """Builds a representation of EOProduct as a dictionary to enable its geojson
        serialization

        :returns: The representation of a :class:`~eodag.api.product._product.EOProduct` as a
                  Python dict
        """
        search_intersection = None
        if self.search_intersection is not None:
            search_intersection = geometry.mapping(self.search_intersection)

        geojson_repr: dict[str, Any] = {
            "type": "Feature",
            "geometry": geometry.mapping(self.geometry),
            "id": self.properties["id"],
            "assets": self.assets.as_dict(),
            "properties": {
                "eodag_product_type": self.product_type,
                "eodag_provider": self.provider,
                "eodag_search_intersection": search_intersection,
                **{
                    key: value
                    for key, value in self.properties.items()
                    if key not in ("geometry", "id")
                },
            },
        }

        return geojson_repr

    @classmethod
    def from_geojson(cls, feature: dict[str, Any]) -> EOProduct:
        """Builds an :class:`~eodag.api.product._product.EOProduct` object from its
        representation as geojson

        :param feature: The representation of a :class:`~eodag.api.product._product.EOProduct`
                        as a Python dict
        :returns: An instance of :class:`~eodag.api.product._product.EOProduct`
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
        obj.assets = AssetsDict(obj, feature.get("assets", {}))
        return obj

    # Implementation of geo-interface protocol (See
    # https://gist.github.com/sgillies/2217756)
    __geo_interface__ = property(as_dict)

    def __repr__(self) -> str:
        try:
            return "{}(id={}, provider={})".format(
                self.__class__.__name__, self.properties["id"], self.provider
            )
        except KeyError as e:
            raise MisconfiguredError(
                f"Unable to get {e.args[0]} key from EOProduct.properties"
            )

    def register_downloader(
        self, downloader: Union[Api, Download], authenticator: Optional[Authentication]
    ) -> None:
        """Give to the product the information needed to download itself.

        :param downloader: The download method that it can use
                          :class:`~eodag.plugins.download.base.Download` or
                          :class:`~eodag.plugins.api.base.Api`
        :param authenticator: The authentication method needed to perform the download
                             :class:`~eodag.plugins.authentication.base.Authentication`
        """
        self.downloader = downloader
        self.downloader_auth = authenticator

        # resolve locations and properties if needed with downloader configuration
        location_attrs = ("location", "remote_location")
        for location_attr in location_attrs:
            if "%(" in getattr(self, location_attr):
                try:
                    setattr(
                        self,
                        location_attr,
                        getattr(self, location_attr) % vars(self.downloader.config),
                    )
                except ValueError as e:
                    logger.debug(
                        f"Could not resolve product.{location_attr} ({getattr(self, location_attr)})"
                        f" in register_downloader: {str(e)}"
                    )

        for k, v in self.properties.items():
            if isinstance(v, str) and "%(" in v:
                try:
                    self.properties[k] = v % vars(self.downloader.config)
                except (TypeError, ValueError) as e:
                    logger.debug(
                        f"Could not resolve {k} property ({v}) in register_downloader: {str(e)}"
                    )

    def download(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> str:
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
        :param wait: (optional) If download fails, wait time in minutes between
                     two download tries
        :param timeout: (optional) If download fails, maximum time in minutes
                        before stop retrying to download
        :param kwargs: `output_dir` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :returns: The absolute path to the downloaded product on the local filesystem
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

    def _init_progress_bar(
        self, progress_callback: Optional[ProgressCallback]
    ) -> tuple[ProgressCallback, bool]:
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
        return (progress_callback, close_progress_callback)

    def _download_quicklook(
        self,
        quicklook_file: str,
        progress_callback: ProgressCallback,
        ssl_verify: Optional[bool] = None,
        auth: Optional[AuthBase] = None,
    ):

        """Download the quicklook image from the EOProduct's quicklook URL.

        This method performs an HTTP GET request to retrieve the quicklook image and saves it
        locally at the specified path. It optionally verifies SSL certificates, uses HTTP
        authentication, and can display a download progress if a callback is provided.

        :param quicklook_file: The full path (including filename) where the quicklook will be saved.
        :param progress_callback: A callable that accepts the current and total download sizes
                                to display or log the download progress. It must support `reset(total)`
                                and be callable with downloaded chunk sizes.
        :param ssl_verify: (optional) Whether to verify SSL certificates. Defaults to True.
        :param auth: (optional) Authentication credentials (e.g., tuple or object) used for the
                        HTTP request if the resource requires authentication.
        :raises HTTPError: If the HTTP request to the quicklook URL fails.
        """
        with requests.get(
            self.properties["quicklook"],
            stream=True,
            auth=auth,
            headers=USER_AGENT,
            timeout=DEFAULT_STREAM_REQUESTS_TIMEOUT,
            verify=ssl_verify,
        ) as stream:
            stream.raise_for_status()
            stream_size = int(stream.headers.get("content-length", 0))
            progress_callback.reset(stream_size)
            with open(quicklook_file, "wb") as fhandle:
                for chunk in stream.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        fhandle.write(chunk)
                        progress_callback(len(chunk))
            logger.info("Download recorded in %s", quicklook_file)

    def get_quicklook(
        self,
        filename: Optional[str] = None,
        output_dir: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        """Download the quicklook image of a given EOProduct from its provider if it
        exists.

        This method retrieves the quicklook URL from the EOProduct metadata and delegates
        the download to the internal `download_quicklook` method.

        :param filename: (optional) The name to give to the downloaded quicklook. If not
                         given, it defaults to the product's ID (without file extension).
        :param output_dir: (optional) The absolute path of the directory where to store
                         the quicklooks in the filesystem. If not given, it defaults to the
                         `quicklooks` directory under this EO product downloader's ``output_dir``
                         config param (e.g. '/tmp/quicklooks/')
        :param progress_callback: (optional) A method or a callable object which takes
                                   a current size and a maximum size as inputs and handle progress bar
                                   creation and update to give the user a feedback on the download progress
        :returns: The absolute path of the downloaded quicklook
        """

        def format_quicklook_address() -> None:
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

        if self.properties.get("quicklook", None) is None:
            logger.warning(
                "Missing information to retrieve quicklook for EO product: %s",
                self.properties["id"],
            )
            return ""

        format_quicklook_address()

        if output_dir is not None:
            quicklooks_output_dir = os.path.abspath(os.path.realpath(output_dir))
        else:
            tempdir = tempfile.gettempdir()
            downloader_output_dir = (
                getattr(self.downloader.config, "output_dir", tempdir)
                if self.downloader
                else tempdir
            )
            quicklooks_output_dir = os.path.join(downloader_output_dir, "quicklooks")
        if not os.path.isdir(quicklooks_output_dir):
            os.makedirs(quicklooks_output_dir)
        quicklook_file = os.path.join(
            quicklooks_output_dir,
            filename if filename is not None else self.properties["id"],
        )

        if not os.path.isfile(quicklook_file):

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
            if not isinstance(auth, AuthBase):
                auth = None
            # Read the ssl_verify parameter used on the provider config
            # to ensure the same behavior for get_quicklook as other download functions
            ssl_verify = (
                getattr(self.downloader.config, "ssl_verify", True)
                if self.downloader
                else True
            )
            try:
                self._download_quicklook(
                    quicklook_file, progress_callback, ssl_verify, auth
                )
            except RequestException as e:

                logger.debug(
                    f"Error while getting resource with authentication. {e} \nTrying without authentication..."
                )
                try:
                    self._download_quicklook(
                        quicklook_file, progress_callback, ssl_verify, None
                    )
                except RequestException as e_no_auth:
                    logger.error(
                        f"Failed to get resource with authentication: {e} \n \
                        Failed to get resource even without authentication. {e_no_auth}"
                    )
                    return str(e)

            # close progress bar if needed
            if close_progress_callback:
                progress_callback.close()

        return quicklook_file

    def get_driver(self) -> DatasetDriver:
        """Get the most appropriate driver"""
        try:
            for driver_conf in DRIVERS:
                if all([criteria(self) for criteria in driver_conf["criteria"]]):
                    driver = driver_conf["driver"]
                    break
            # use legacy driver for deprecated get_data method usage
            for lecacy_conf in LEGACY_DRIVERS:
                if all([criteria(self) for criteria in lecacy_conf["criteria"]]):
                    driver.legacy = lecacy_conf["driver"]
                    break
            return driver
        except TypeError:
            logger.info("No driver matching")
            pass
        return NoDriver()

    def _repr_html_(self):
        thumbnail = self.properties.get("thumbnail", None)
        thumbnail_html = (
            f"<img src='{thumbnail}' width=100 alt='thumbnail'/>"
            if thumbnail and not thumbnail.startswith("s3")
            else ""
        )
        geom_style = "style='color: grey; text-align: center; min-width:100px; vertical-align: top;'"
        thumbnail_style = (
            "style='padding-top: 1.5em; min-width:100px; vertical-align: top;'"
        )

        return f"""<table>
                <thead><tr style='background-color: transparent;'><td style='text-align: left; color: grey;'>
                {type(self).__name__}
                </td></tr></thead>

                <tr style='background-color: transparent;'>
                    <td style='text-align: left; vertical-align: top;'>
                        {dict_to_html_table({
                         "provider": self.provider,
                         "product_type": self.product_type,
                         "properties[&quot;id&quot;]": self.properties.get('id', None),
                         "properties[&quot;startTimeFromAscendingNode&quot;]": self.properties.get(
                             'startTimeFromAscendingNode', None
                         ),
                         "properties[&quot;completionTimeFromAscendingNode&quot;]": self.properties.get(
                             'completionTimeFromAscendingNode', None
                         ),
                         }, brackets=False)}
                        <details><summary style='color: grey; margin-top: 10px;'>properties:&ensp;({len(
                             self.properties)})</summary>{
                                 dict_to_html_table(self.properties, depth=1)}</details>
                        <details><summary style='color: grey; margin-top: 10px;'>assets:&ensp;({len(
                                     self.assets)})</summary>{self.assets._repr_html_(embeded=True)}</details>
                    </td>
                    <td {geom_style} title='geometry'>geometry<br />{self.geometry._repr_svg_()}</td>
                    <td {thumbnail_style} title='properties[&quot;thumbnail&quot;]'>{thumbnail_html}</td>
                </tr>
            </table>"""
