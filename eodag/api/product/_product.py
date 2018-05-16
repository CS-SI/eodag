# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import zipfile
from uuid import uuid4

import numpy
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from shapely import geometry
from shapely.errors import TopologicalError
from tqdm import tqdm

from eodag.api.product.drivers import DRIVERS
from eodag.utils import maybe_generator
from eodag.utils.exceptions import UnsupportedDatasetAddressScheme


logger = logging.getLogger('eodag.api.product')
EOPRODUCT_PROPERTIES = (
    'cloudCover', 'description', 'keywords', 'organisationName', 'resolution', 'snowCover', 'startDate',
    'endDate', 'title', 'productIdentifier', 'orbitNumber'
)


class EOProduct(object):
    """A wrapper around an Earth Observation Product originating from a search.

    Every Search plugin instance should build an instance of this class for each of the result of its query method, and
    return a :class:`~eodag.api.search_result.SearchResult` made up of a list of such instances, providing a uniform
    object on which the other plugins can work.

    :param provider: The system from which the product originates
    :type provider: str or unicode
    :param download_url: The location from where the product must be downloaded
    :type download_url: str or unicode
    :param local_filename: The name that will be given to the downloaded file (an archive) in the local filesystem
    :type local_filename: str or unicode
    :param geom: The geometry representing the geographical footprint of the product
    :type geom: :class:`shapely.geometry.base.BaseGeometry` (e.g. :class:`shapely.geometry.point.Point`)
    :param bbox_or_intersect: The extent of a search request, or the intersection of a :class:`~eodag.api.product.EOProduct`
                              with the extent of a search request (when instantiating a :class:EOProduct from a geojson
                              file)
    :type bbox_or_intersect: dict
    :param product_type: The product type (e.g. L1C)
    :type product_type: str or unicode
    :param platform: The name of the satellite that produced the raw data of the product
    :type platform: str or unicode
    :param instrument: The name of the sensing instrument embedded in the platform
    :type instrument: str or unicode
    :param provider_id: (optional) The product ID as returned by the provider (usually a string-like uid)
    :type provider_id: undefined
    :param id: (optional) The ID of the product as defined in this library. This option is intended to be used to allow
               instantiating a EOProduct from its geojson representation
    :type id: str or unicode
    :param kwargs: Additional information holding properties of the product
    :type kwargs: dict

    .. note::
        EOProduct stores geometries in WGS84 CRS (EPSG:4326), as it is intended to be transmitted as geojson
        between applications and geojson spec enforces this.
        See: https://github.com/geojson/draft-geojson/pull/6.

    .. note::
        Each time a EOProduct object is created, a random unique id is created  and attached to this object to identify
        it across the api.
    """

    def __init__(self, provider, download_url, local_filename, geom, bbox_or_intersect, product_type, platform=None,
                 instrument=None, id=None, provider_id=None, **kwargs):
        self.location_url_tpl = download_url
        self.local_filename = local_filename
        self.id = id or uuid4().urn
        self.provider = provider
        self.geometry = geom
        self.product_type = product_type
        self.sensing_platform = platform
        self.sensor = instrument
        if bbox_or_intersect:
            # Handle the case where we initialize EOProduct from a geojson representation of another EOProduct
            # (bbox_or_intersect is a geometry representing the intersection of the extent covered by the product and
            # the extent requested in the search)
            if 'type' in bbox_or_intersect and 'coordinates' in bbox_or_intersect:
                self.search_intersection = geometry.asShape(bbox_or_intersect)
            else:
                minx, miny = bbox_or_intersect['lonmin'], bbox_or_intersect['latmin']
                maxx, maxy = bbox_or_intersect['lonmax'], bbox_or_intersect['latmax']
                requested_geom = geometry.box(minx, miny, maxx, maxy)
                try:
                    self.search_intersection = geom.intersection(requested_geom)
                except TopologicalError as e:
                    # TODO before finding a good way to handle this, just ignore the error
                    logger.warning('Unable to intersect the requested geometry: %s with the geometry: %s. Cause: %s',
                                   requested_geom, geom, e)
                    self.search_intersection = None
        # If There was no extent requested, store the product geometry as its "intersection" with a fictional search
        # extent
        else:
            self.search_intersection = geom
        self.properties = {
            prop_key: kwargs.get(prop_key)
            for prop_key in EOPRODUCT_PROPERTIES
        }
        # This allows plugin developers to add their own properties to the EOProduct object
        self.properties.update(kwargs)
        if provider_id is not None:
            self.properties['provider_id'] = provider_id
        self.driver = DRIVERS.get((self.sensing_platform, self.sensor), DRIVERS[(None, None)])()
        self.downloader = None
        self.downloader_auth = None

    def get_data(self, crs, resolution, band, extent):
        """Retrieves all or part of the raster data abstracted by the :class:`EOProduct`

        :param crs: The coordinate reference system in which the dataset should be returned
        :type crs: str or unicode
        :param resolution: The resolution in which the dataset should be returned (given in the unit of the crs)
        :type resolution: float
        :param band: The band of the dataset to retrieve (e.g.: 'B01')
        :type band: str or unicode
        :param extent: The coordinates on which to zoom as a tuple (min_x, min_y, max_x, max_y) in the given `crs`
        :type extent: (float, float, float, float)
        :returns: The numeric matrix corresponding to the sub dataset or an empty array if unable to get the data
        :rtype: numpy.ndarray
        """
        fail_value = numpy.empty(0)
        try:
            dataset_address = self.driver.get_data_address(self, band)
        except UnsupportedDatasetAddressScheme:
            logger.warning('Eodag does not support getting data from distant sources by now. Falling back to first '
                           'downloading the product and then getting the data...')
            try:
                path_of_downloaded_file = self.download()
            except RuntimeError:
                import traceback
                logger.warning('Error while trying to download the product:\n %s', traceback.format_exc())
                logger.warning('There might be no download plugin registered for this EO product. Try performing: '
                               'product.register_downloader(download_plugin, download_auth_plugin) before trying to '
                               'call product.get_data(...)')
                return fail_value
            if not path_of_downloaded_file:
                return fail_value
            self.location_url_tpl = 'file://{}'.format(path_of_downloaded_file)
            dataset_address = self.driver.get_data_address(self, band)
        min_x, min_y, max_x, max_y = extent
        height = int((max_y - min_y) / resolution)
        width = int((max_x - min_x) / resolution)
        out_shape = (width, height)
        with rasterio.open(dataset_address) as src:
            with WarpedVRT(src, dst_crs=crs, resampling=Resampling.bilinear) as vrt:
                return vrt.read(1, window=vrt.window(*extent), out_shape=out_shape, resampling=Resampling.bilinear)

    def as_dict(self):
        """Builds a representation of EOProduct as a dictionary to enable its geojson serialization

        :returns: The representation of a :class:`~eodag.api.product.EOProduct` as a Python dict
        :rtype: dict
        """
        geojson_repr = {
            'type': 'Feature',
            'id': self.id,
            'geometry': self.geometry,
            'properties': {
                'eodag_provider': self.provider,
                'eodag_download_url': self.location_url_tpl,
                'eodag_local_name': self.local_filename,
                'eodag_search_intersection': self.search_intersection,
                'productType': self.product_type,
                'platform': self.sensing_platform,
                'instrument': self.sensor,
            }
        }
        geojson_repr['properties'].update(self.properties)
        return geojson_repr

    @classmethod
    def from_geojson(cls, feature):
        """Builds an :class:`~eodag.api.product.EOProduct` object from its representation as geojson

        :param feature: The representation of a :class:`~eodag.api.product.EOProduct` as a Python dict
        :type feature: dict
        :returns: An instance of :class:`~eodag.api.product.EOProduct`
        :rtype: :class:`~eodag.api.product.EOProduct`
        """
        return cls(
            feature['properties']['eodag_provider'],
            feature['properties']['eodag_download_url'],
            feature['properties']['eodag_local_name'],
            feature['geometry'],
            feature['properties']['eodag_search_intersection'],
            feature['properties']['productType'],
            id=feature['id'],
            **feature['properties'])

    # Implementation of geo-interface protocol (See https://gist.github.com/sgillies/2217756)
    __geo_interface__ = property(as_dict)

    def __repr__(self):
        return '{}(id={}, provider={})'.format(self.__class__.__name__, self.id, self.provider)

    def encode(self, raster, encoding='protobuf'):
        """Encode the subset to a network-compatible format.

        :param raster: The raster data to encode
        :type raster: numpy.ndarray
        :param encoding: The encoding of the export
        :type encoding: str or unicode
        :return: The data encoded in the specified encoding
        :rtype: bytes
        """
        # If no encoding return an empty byte
        if not encoding:
            logger.warning('Trying to encode a raster without specifying an encoding')
            return b''
        strategy = getattr(self, '_{encoding}'.format(**locals()), None)
        if strategy:
            return strategy(raster)
        logger.error('Unknown encoding: %s', encoding)
        return b''

    def _protobuf(self, raster):
        """Google's Protocol buffers encoding strategy.

        :param raster: The raster to encode
        :type raster: numpy.ndarray
        :returns: The raster data represented by this subset in protocol buffers encoding
        :rtype: bytes
        """
        from eodag.api.product.protobuf import eo_product_pb2
        subdataset = eo_product_pb2.EOProductSubdataset()
        subdataset.id = self.id
        subdataset.producer = self.provider
        subdataset.product_type = self.product_type
        subdataset.platform = self.sensing_platform
        subdataset.sensor = self.sensor
        data = subdataset.data
        data.array.extend(list(raster.flatten().astype(int)))
        data.shape.extend(list(raster.shape))
        data.dtype = raster.dtype.name
        return subdataset.SerializeToString()

    def register_downloader(self, downloader, authenticator):
        """Give to the product the information needed to download itself.

        :param downloader: The download method that it can use
        :type downloader: Concrete subclass of :class:`~eodag.plugins.download.base.Download` or
                          :class:`~eodag.plugins.api.base.Api`
        :param authenticator: The authentication method needed to perform the download
        :type authenticator: Concrete subclass of :class:`~eodag.plugins.authentication.base.Authentication`
        """
        if not self.downloader or self.downloader != downloader:
            self.downloader = downloader
        if not self.downloader_auth or self.downloader_auth != authenticator:
            self.downloader_auth = authenticator

    def download(self):
        """Download the EO product using the provided download plugin and the authenticator if necessary.

        :returns: The absolute path to the downloaded product on the local filesystem
        :rtype: str or unicode
        """
        if not self.downloader:
            raise RuntimeError('EO product is unable to download itself due to the lack of a download plugin')
        # Remove the capability for the downloader to perform extraction if the downloaded product is a zipfile. This
        # way, the eoproduct is able to control how the it stores itself on the local filesystem
        old_extraction_config = self.downloader.config['extract']
        self.downloader.config['extract'] = False
        # Since we are sure extraction will not be done, we only retrieve the first (and sole) value returned
        local_filepath = next(maybe_generator(self.downloader.download(self, auth=self.downloader_auth)), None)
        if local_filepath is None:
            logger.warning('The download may have fail or the location of the downloaded file on the local filesystem '
                           'have not been returned by the download plugin')
            return ''
        fs_location = local_filepath[:local_filepath.index('.zip')]
        if zipfile.is_zipfile(local_filepath):
            with zipfile.ZipFile(local_filepath, 'r') as zfile:
                fileinfos = tqdm(zfile.infolist(), unit='file', desc='Extracting files from {}'.format(local_filepath))
                for fileinfo in fileinfos:
                    zfile.extract(fileinfo, path=fs_location)
            self.location_url_tpl = 'file://{}'.format(fs_location)
        # Restore configuration
        self.downloader.config['extract'] = old_extraction_config
        return fs_location
