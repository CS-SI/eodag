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

import logging
import os
import shutil
import tempfile
import zipfile
from typing import TYPE_CHECKING, Any, Iterable, Optional, cast

import geojson
import orjson
from pystac import Item
from shapely import geometry
from shapely.errors import ShapelyError

from eodag.types.queryables import CommonStacMetadata
from eodag.types.stac_metadata import create_stac_metadata_model

try:
    # import from eodag-cube if installed
    from eodag_cube.api.product import (  # pyright: ignore[reportMissingImports]
        AssetsDict,
    )
except ImportError:
    from ._assets import AssetsDict  # type: ignore

from eodag.api.product.drivers import DRIVERS
from eodag.api.product.drivers.generic import GenericDriver
from eodag.api.product.metadata_mapping import (
    DEFAULT_GEOMETRY,
    NOT_AVAILABLE,
    NOT_MAPPED,
    normalize_bands,
)
from eodag.plugins.download import StreamResponse
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    DEFAULT_SHAPELY_GEOMETRY,
    GENERIC_STAC_PROVIDER,
    STAC_VERSION,
    Eventable,
    Processor,
    ProgressCallback,
    _deprecated,
    deepcopy,
    get_geometry_from_various,
)
from eodag.utils.deserialize import (
    import_stac_item_from_eodag_server,
    import_stac_item_from_known_provider,
    import_stac_item_from_unknown_provider,
)
from eodag.utils.exceptions import MisconfiguredError, ValidationError
from eodag.utils.repr import dict_to_html_table

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from eodag import EODataAccessGateway
    from eodag.api.product.drivers.base import DatasetDriver
    from eodag.plugins.manager import PluginManager
    from eodag.types.download_args import DownloadConf
    from eodag.utils import Unpack

logger = logging.getLogger("eodag.product")


class EOProduct(Eventable):
    """A wrapper around an Earth Observation Product originating from a search.

    Every Search plugin instance must build an instance of this class for each of
    the result of its query method, and return a list of such instances. A EOProduct
    has a `location` attribute that initially points to its remote location, but is
    later changed to point to its path on the filesystem when the product has been
    downloaded.

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
    #: The collection
    collection: Optional[str]
    #: The geometry of the product
    geometry: BaseGeometry
    #: The intersection between the product's geometry and the search area.
    search_intersection: Optional[BaseGeometry]
    #: Assets of the product
    assets: AssetsDict
    #: Driver enables additional methods to be called on the EOProduct
    driver: DatasetDriver
    #: Product search keyword arguments, stored during search
    search_kwargs: Any

    def __init__(
        self, provider: str, properties: dict[str, Any], **kwargs: Any
    ) -> None:
        super().__init__()

        self.provider = provider
        self.collection = (
            kwargs.get("collection")
            or properties.pop("collection", None)
            or properties.get("_collection")
        )
        self.assets = AssetsDict(self)  # type: ignore[arg-type]
        self.properties = {
            key: value
            for key, value in properties.items()
            if key != "geometry"
            and value != NOT_MAPPED
            and NOT_AVAILABLE not in str(value)
            and not key.startswith("_")
        }
        self.properties.setdefault(
            "datetime",
            self.properties.get("start_datetime")
            or self.properties.get("end_datetime"),
        )

        # sort properties to have common stac properties first
        common_stac_properties = {
            key: self.properties[key]
            for key in sorted(self.properties)
            if ":" not in key
        }
        extensions_stac_properties = {
            key: self.properties[key] for key in sorted(self.properties) if ":" in key
        }
        self.properties = common_stac_properties | extensions_stac_properties

        if "geometry" not in properties or (
            (
                properties["geometry"] == NOT_AVAILABLE
                or properties["geometry"] == NOT_MAPPED
            )
            and "eodag:default_geometry" not in properties
        ):
            product_geometry = DEFAULT_SHAPELY_GEOMETRY
        elif not properties["geometry"] or properties["geometry"] == NOT_AVAILABLE:
            product_geometry = properties.pop(
                "eodag:default_geometry", DEFAULT_GEOMETRY
            )
        else:
            product_geometry = properties["geometry"]

        geometry_obj = get_geometry_from_various(geometry=product_geometry)
        # whole world as default geometry
        if geometry_obj is None:
            geometry_obj = DEFAULT_SHAPELY_GEOMETRY
        self.geometry = self.search_intersection = geometry_obj

        self.search_kwargs = kwargs
        if self.search_kwargs.get("geometry") is not None:
            searched_geom = get_geometry_from_various(
                **{"geometry": self.search_kwargs["geometry"]}
            )
            try:
                self.search_intersection = self.geometry.intersection(searched_geom)
            except ShapelyError:
                logger.warning(
                    "Unable to intersect the requested extent: %s with the product "
                    "geometry: %s",
                    searched_geom,
                    product_geometry,
                )
                self.search_intersection = None
        self.driver = self.get_driver()
        self.plugins_manager: Optional[PluginManager] = None

    def as_dict(self, skip_invalid: bool = True) -> dict[str, Any]:
        """Builds a representation of EOProduct as a dictionary to enable its geojson
        serialization

        :param skip_invalid: Whether to skip properties whose values are not valid according to the STAC specification.
        :returns: The representation of a :class:`~eodag.api.product._product.EOProduct` as a
                  Python dict
        """
        search_intersection = None
        if self.search_intersection is not None:
            search_intersection = orjson.loads(
                orjson.dumps(self.search_intersection.__geo_interface__)
            )

        # product properties
        stac_properties = {
            **{
                key: value
                for key, value in self.properties.items()
                if key not in ("geometry", "id")
            },
            "eodag:provider": self.provider,
            "eodag:search_intersection": search_intersection,
            "federation:backends": [self.provider],
        }
        stac_providers = self.properties.get("providers", [])
        if not any("host" in p.get("roles", []) for p in stac_providers):
            stac_providers.append({"name": self.provider, "roles": ["host"]})
            stac_properties["providers"] = stac_providers

        props_model = cast(type[CommonStacMetadata], create_stac_metadata_model())
        props_validated = props_model.safe_validate(
            stac_properties, skip_invalid=skip_invalid
        )
        stac_extensions: set[str] = set(props_validated.get_conformance_classes())

        # skip invalid properties
        if skip_invalid:
            props_validated_dict = props_validated.model_dump(
                by_alias=False, exclude_unset=False
            )
            pythonic_fields_properties = {
                props_model.get_field_from_alias(k): v
                for k, v in stac_properties.items()
            }
            invalid_properties = {
                k
                for k, v in pythonic_fields_properties.items()
                # keep none values
                if props_model.has_field(k)
                and props_validated_dict[k] is None
                and v is not None
            }
            for key in invalid_properties:
                stac_key = props_model.model_fields[key].alias or key
                stac_properties.pop(stac_key, None)

        # get conformance classes for assets properties
        assets_dict = {**self.assets.as_dict()}
        for asset_key, asset_properties in self.assets.as_dict().items():
            asset_props_validated = props_model.safe_validate(
                asset_properties, skip_invalid=skip_invalid
            )
            stac_extensions.update(asset_props_validated.get_conformance_classes())

            # skip invalid assets properties
            if skip_invalid:
                invalid_asset_properties = {
                    k
                    for k in asset_properties.keys()
                    if k not in asset_props_validated.model_dump()
                    and props_model.has_field(k)
                }
                for key in invalid_asset_properties:
                    assets_dict[asset_key].pop(key, None)

        geojson_repr: dict[str, Any] = {
            "type": "Feature",
            "geometry": orjson.loads(orjson.dumps(self.geometry.__geo_interface__)),
            "bbox": list(self.geometry.bounds),
            "id": self.properties.get("id"),
            "assets": assets_dict,
            "properties": stac_properties,
            "links": [
                {
                    "rel": "collection",
                    "href": f"{self.collection}.json",
                    "type": "application/json",
                },
            ],
            "stac_extensions": list(stac_extensions),
            "stac_version": STAC_VERSION,
            "collection": self.collection,
        }
        return geojson_repr

    def as_pystac_object(self, skip_invalid: bool = True) -> Item:
        """Builds a representation of EOProduct as a pystac Item to enable its manipulation with pystac methods

        :param skip_invalid: Whether to skip properties whose values are not valid according to the STAC specification.
        :returns: The representation of a :class:`~eodag.api.product._product.EOProduct` as a :class:`pystac.Item`
        """
        prod_dict = self.as_dict(skip_invalid=skip_invalid)
        return Item.from_dict(prod_dict)

    @classmethod
    def from_dict(
        cls,
        feature: dict[str, Any],
        dag: Optional[EODataAccessGateway] = None,
        raise_errors: bool = False,
    ) -> EOProduct:
        """Builds an :class:`~eodag.api.product._product.EOProduct` object from its
        serialized representation as a Python dict.

        :param feature: The representation of a :class:`~eodag.api.product._product.EOProduct`
                        as a Python dict
        :param dag: (optional) The EODataAccessGateway instance to use for registering the product downloader. If not
                    provided, the downloader and authenticator will not be registered.
        :param raise_errors: (optional) Whether to raise exceptions in case of errors during the deserialize process.
                             If False, and if ``dag`` is given, several import methods will be tried: from serialized,
                             from eodag-server, from known provider, from unknown provider.
        :returns: An instance of :class:`~eodag.api.product._product.EOProduct`
        :raises: :class:`~eodag.utils.exceptions.ValidationError`
        """
        if dag is not None:
            # add a generic STAC provider that might be needed to handle the items
            dag.add_provider(GENERIC_STAC_PROVIDER)
            plugin_manager = dag._plugins_manager
            product = cls._from_stac_item(
                feature, plugin_manager, provider=None, raise_errors=raise_errors
            )
            if product is None:
                raise ValidationError(
                    "Unable to build EOProduct from the provided dictionary, no import method succeeded"
                )
        else:
            product = cls._import_stac_item_from_serialized(feature)

        features_assets = feature.get("assets", {})
        assets = AssetsDict(product)
        for key in features_assets:
            assets.update({key: feature["assets"][key]})
        product.assets.update(assets)

        return product

    @classmethod
    def from_file(
        cls,
        filepath: str,
        dag: Optional[EODataAccessGateway] = None,
        raise_errors: bool = False,
    ) -> EOProduct:
        """Builds an :class:`~eodag.api.product._product.EOProduct` object from a file containing its serialized
        representation as geojson.

        :param filepath: The path to the file containing the serialized representation of a product
        :param dag: (optional) The EODataAccessGateway instance to use for registering the product downloader. If not
                    provided, the downloader and authenticator will not be registered.
        :param raise_errors: (optional) Whether to raise exceptions in case of errors during the deserialize process.
                             If False, several import methods will be tried: from serialized, from eodag-server, from
                             known provider, from unknown provider.
        :returns: An instance of :class:`~eodag.api.product._product.EOProduct`
        :raises: :class:`~eodag.utils.exceptions.ValidationError`
        """
        with open(filepath, "r") as fh:
            feature = geojson.load(fh)

        return cls.from_dict(feature, dag=dag, raise_errors=raise_errors)

    @classmethod
    def from_pystac(
        cls,
        item: Item,
        dag: Optional[EODataAccessGateway] = None,
        raise_errors: bool = False,
    ) -> EOProduct:
        """Builds an :class:`~eodag.api.product._product.EOProduct` object from a pystac Item.

        :param item: The :class:`pystac.Item` containing the metadata of the product
        :param dag: (optional) The EODataAccessGateway instance to use for registering the product downloader. If not
                    provided, the downloader and authenticator will not be registered.
        :param raise_errors: (optional) Whether to raise exceptions in case of errors during the deserialize process.
                             If False, several import methods will be tried: from serialized, from eodag-server, from
                             known provider, from unknown provider.
        :returns: An instance of :class:`~eodag.api.product._product.EOProduct`
        :raises: :class:`~eodag.utils.exceptions.ValidationError`
        """
        feature = item.to_dict()
        return cls.from_dict(feature, dag=dag, raise_errors=raise_errors)

    @classmethod
    @_deprecated(
        reason="Please use 'EOProduct.from_dict' instead",
        version="4.1.0",
    )
    def from_geojson(cls, feature: dict[str, Any]) -> EOProduct:
        """Builds an :class:`~eodag.api.product._product.EOProduct` object from its
        representation as geojson

        :param feature: The representation of a :class:`~eodag.api.product._product.EOProduct`
                        as a Python dict
        :returns: An instance of :class:`~eodag.api.product._product.EOProduct`
        :raises: :class:`~eodag.utils.exceptions.ValidationError`
        """
        return cls.from_dict(feature, raise_errors=True)

    def _normalize_bands(self) -> None:
        """Normalize bands in properties and each asset
        from STAC 1.0 (``eo:bands`` / ``raster:bands``) to STAC 1.1 (``bands``), in place.
        """
        normalize_bands(self.properties)
        for key in self.assets:
            normalize_bands(self.assets[key])

    # Implementation of geo-interface protocol (See
    # https://gist.github.com/sgillies/2217756)
    __geo_interface__ = property(as_dict)

    def __repr__(self) -> str:
        try:
            return "{}(id={}, provider={})".format(
                self.__class__.__name__, self.properties.get("id", "?"), self.provider
            )
        except KeyError as e:
            raise MisconfiguredError(
                f"Unable to get {e.args[0]} key from EOProduct.properties"
            )

    def register_plugin_manager(self, plugins_manager: PluginManager):
        """Register the plugin manager
        :param plugins_manager: The plugins manager instance.
        """
        self.plugins_manager = plugins_manager
        self.fire("register_plugin_manager", self)

    def download(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        no_cache: bool = False,
        **kwargs: Unpack[DownloadConf],
    ) -> list[str]:
        """Download the EO product as local_file

        :param Optional[ProgressCallback] progress_callback: Used to manage progress bar in console
        :param float wait: (optional) on fails, time in minutes to wait before retry
        :param float timeout: (optional) Total time in minute before timeout
        :param kwargs: `output_dir` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :returns str|None: local_path
        """

        # Try download asset 'download_link"
        if "download_link" in self.assets:
            fs_path = self.assets["download_link"].download(
                progress_callback=progress_callback,
                wait=wait,
                timeout=timeout,
                no_cache=no_cache,
                **kwargs,
            )
            if fs_path is not None:
                return [fs_path]
            else:
                logger.debug(
                    "Product download: download_link not found, download all assets"
                )

        # Download all assets
        assets = []
        for key in self.assets:
            if key != "download_link":
                assets.append(self.assets[key])

        if len(assets) == 0:
            return []
        elif len(assets) == 1:
            fs_path = assets[0].download(
                progress_callback=progress_callback,
                wait=wait,
                timeout=timeout,
                no_cache=no_cache,
                **kwargs,
            )
            if fs_path is not None:
                return [fs_path]
        else:
            # Parallelize download
            shared: dict[str, list] = {"list_path": [], "errors": []}

            def callback(path, error):
                if error is not None:
                    shared["errors"].append(error)
                    logger.warning(error)
                else:
                    if path is not None:
                        shared["list_path"].append(path)

            ids: list = []
            for asset in assets:
                taskid = Processor.queue(
                    asset.download,
                    progress_callback=progress_callback,
                    wait=wait,
                    timeout=timeout,
                    no_cache=no_cache,
                    q_timeout=int(timeout * 60),
                    q_callback=callback,
                    **kwargs,
                )
                ids.append(taskid)
            Processor.wait(ids)

            for error in shared["errors"]:
                logger.error(error)

            return shared["list_path"]

        return []

    def stream_download(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        no_cache: bool = False,
        **kwargs: Unpack[DownloadConf],
    ) -> StreamResponse:
        """Download the EO product as StreamResponse

        :param Optional[ProgressCallback] progress_callback: Used to manage progress bar in console
        :param float wait: (optional) on fails, time in minutes to wait before retry
        :param float timeout: (optional) Total time in minute before timeout
        :param kwargs: `output_dir` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :returns StreamResponse:
        """
        if "download_link" in self.assets:
            return self.assets["download_link"].stream_download(
                progress_callback=progress_callback,
                wait=wait,
                timeout=timeout,
                no_cache=no_cache,
                **kwargs,
            )
        else:
            # Parallelize download
            proc = Processor()
            list_path = []

            def callback(path, error):
                if error is not None:
                    logger.warning(error)
                else:
                    if path is not None:
                        list_path.append(path)

            for key in self.assets:
                if key != "download_link":
                    proc.queue(
                        self.assets[key].download,
                        progress_callback=progress_callback,
                        wait=wait,
                        timeout=timeout,
                        no_cache=no_cache,
                        q_timeout=int(timeout * 60),
                        callback=callback,
                    )
            proc.wait()

            if len(list_path) == 0:
                raise FileNotFoundError("No any file to download found")

            tmp = tempfile.NamedTemporaryFile(delete=False)
            tmp_file = tmp.name
            with zipfile.ZipFile(tmp_file, "w") as zf:
                for path in list_path:
                    zf.write(path, os.path.basename(path))

            return StreamResponse.from_file(tmp_file)

    def download_quicklook(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        no_cache: bool = False,
        **kwargs: Unpack[DownloadConf],
    ) -> Optional[str]:
        """Download the quicklook image from the EOProduct's quicklook URL"""
        if "quicklook" in self.assets:
            return self.assets["quicklook"].download(
                progress_callback=progress_callback,
                wait=wait,
                timeout=timeout,
                no_cache=no_cache,
            )
        return None

    def get_quicklook(
        self,
        filename: Optional[str] = None,
        output_dir: Optional[str] = None,
        no_cache: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Optional[str]:
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
        fs_path = self.download_quicklook(progress_callback, no_cache=no_cache)
        if fs_path is not None:
            if filename is None:
                filename = self.properties.get("id", os.path.basename(fs_path))
            if output_dir is not None:
                dest_path = os.path.join(output_dir, filename)
                shutil.copyfile(fs_path, dest_path)
                return dest_path
        return fs_path

    def download_thumbnail(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        no_cache: bool = False,
        **kwargs: Unpack[DownloadConf],
    ) -> Optional[str]:
        """Download the thumbnail image from the EOProduct's quicklook URL"""
        if "thumbnail" in self.assets:
            return self.assets["quicklook"].download(
                progress_callback=progress_callback,
                wait=wait,
                timeout=timeout,
                no_cache=no_cache,
            )
        return None

    def get_driver(self) -> DatasetDriver:
        """Get the most appropriate driver"""
        for driver_conf in DRIVERS:

            # Select a driver if all criterias match
            match = True
            for criteria in driver_conf["criteria"]:
                if not criteria(self):
                    match = False
                    break
            if match:
                return driver_conf["driver"]

        return GenericDriver()

    def _repr_html_(self):
        thumbnail = self.properties.get("eodag:thumbnail") or self.properties.get(
            "eodag:quicklook"
        )
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
                         "collection": self.collection,
                         "properties[&quot;id&quot;]": self.properties.get('id'),
                         "properties[&quot;start_datetime&quot;]": self.properties.get(
                             'start_datetime'
                         ),
                         "properties[&quot;end_datetime&quot;]": self.properties.get(
                             'end_datetime'
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

    def to_xarray(
        self,
        asset_key: Optional[str] = None,
        wait: float = DEFAULT_DOWNLOAD_WAIT,
        timeout: float = DEFAULT_DOWNLOAD_TIMEOUT,
        roles: Iterable[str] = {"data", "data-mask"},
        **xarray_kwargs: Any,
    ):
        """
        Return product data as a dictionary of :class:`xarray.Dataset`.

        :param asset_key: (optional) key of the asset. If not specified the whole
                          product data will be retrieved
        :param wait: (optional) If order is needed, wait time in minutes between two
                     order status check
        :param timeout: (optional) If order is needed, maximum time in minutes before
                        stop checking order status
        :param roles: (optional) roles of assets that must be fetched
        :param xarray_kwargs: (optional) keyword arguments passed to :func:`xarray.open_dataset`
        :returns: a dictionary of :class:`xarray.Dataset`
        """
        raise NotImplementedError("Install eodag-cube to make this method available.")

    def augment_from_xarray(
        self,
        roles: Iterable[str] = {"data", "data-mask"},
    ) -> EOProduct:
        """
        Annotate the product properties and assets with STAC metadata got by fetching its xarray representation.

        :param roles: (optional) roles of assets that must be fetched
        :returns: updated EOProduct
        """
        raise NotImplementedError("Install eodag-cube to make this method available.")

    @classmethod
    def _import_stac_item_from_serialized(
        cls, feature: dict[str, Any], plugins_manager: Optional[PluginManager] = None
    ) -> EOProduct:
        """Import a STAC item from a EODAG serialized EOProduct.

        :param feature: A STAC item as a dictionary
        :param plugins_manager: The EODAG plugin manager instance
        :returns: An EOProduct created from the STAC item
        :raises: :class:`~eodag.utils.exceptions.ValidationError`
        """
        try:
            collection = feature.get("collection")
            properties = deepcopy(feature["properties"])
            properties["geometry"] = feature["geometry"]
            properties["id"] = feature.get("id")
            provider = properties.pop("eodag:provider")
            search_intersection = properties.pop("eodag:search_intersection")
        except KeyError as e:
            raise ValidationError(
                "Key %s not found in geojson, make sure it comes from a serialized SearchResult or EOProduct"
                % e.args[0]
            ) from e
        obj = cls(provider, properties, collection=collection)
        obj.search_intersection = geometry.shape(search_intersection)
        obj.assets.update(feature.get("assets", {}))

        if plugins_manager is not None:
            # register
            obj.register_plugin_manager(plugins_manager)

        return obj

    @classmethod
    def _from_stac_item(
        cls,
        feature: dict[str, Any],
        plugins_manager: PluginManager,
        provider: Optional[str] = None,
        raise_errors: bool = False,
    ) -> Optional[EOProduct]:
        """Create a SearchResult from a STAC item.

        :param feature: A STAC item as a dictionary
        :param plugins_manager: The EODAG plugin manager instance
        :provider: (optional) The provider to which the STAC item belongs, if known. If not provided, the method will
                   try to determine it from the STAC item properties.
        :param raise_errors: (optional) Whether to raise exceptions in case of errors during the deserialize process.
                             If False, several import methods will be tried: from serialized, from eodag-server, from
                             known provider, from unknown provider.
        :returns: An EOProduct created from the STAC item
        """
        result: Optional[EOProduct] = None
        try:
            # try importing from a serialized EODAG EOProduct
            if result := cls._import_stac_item_from_serialized(
                feature, plugins_manager
            ):
                return result
        except ValidationError:
            if raise_errors:
                raise

        # Try importing from EODAG Server
        if result := import_stac_item_from_eodag_server(feature, plugins_manager):
            return result

        # try importing from a known STAC provider
        if result := import_stac_item_from_known_provider(
            feature, plugins_manager, provider
        ):
            return result

        # try importing from an unknown STAC provider
        return import_stac_item_from_unknown_provider(feature, plugins_manager)


__all__ = ["EOProduct"]
