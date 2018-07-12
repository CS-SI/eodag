# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
import zipfile

import numpy
import rasterio
import xarray as xr
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT
from shapely import geometry
from tqdm import tqdm


try:
    from shapely.errors import TopologicalError
except ImportError:
    from shapely.geos import TopologicalError

from eodag.api.product.drivers import DRIVERS, NoDriver
from eodag.api.product.representations import DEFAULT_METADATA_MAPPING, properties_from_json
from eodag.utils.exceptions import UnsupportedDatasetAddressScheme


logger = logging.getLogger('eodag.api.product')


class EOProduct(object):
    """A wrapper around an Earth Observation Product originating from a search.

    Every Search plugin instance must build an instance of this class for each of the result of its query method, and
    return a list of such instances.

    :param product_type: The product type of the product as defined in eodag
    :type product_type: str or unicode
    :param provider: The provider from which the product originates
    :type provider: str or unicode
    :param download_url: A uri informing where to go to download the product
    :type download_url: str or unicode
    :param properties: The metadata of the product
    :type properties: dict
    :param searched_bbox: (optional) The extent that was passed as a search constraint, used to attach to the EOProduct
                           the intersection of its geometry with this extent
    :type searched_bbox: dict

    .. note::
        The geojson spec `enforces <https://github.com/geojson/draft-geojson/pull/6>`_ the expression of geometries as
        WGS84 CRS (EPSG:4326) coordinates and EOProduct is intended to be transmitted as geojson between applications.
        Therefore it stores geometries in the before mentioned CRS.
    """

    def __init__(self, product_type, provider, download_url, properties, searched_bbox=None):
        self.product_type = product_type
        self.provider = provider
        self.location = download_url
        self.properties = properties
        self.geometry = self.search_intersection = geometry.shape(self.properties['geometry'])
        if searched_bbox is not None:
            searched_bbox_as_shape = geometry.box(searched_bbox['lonmin'], searched_bbox['latmin'],
                                                  searched_bbox['lonmax'], searched_bbox['latmax'])
            try:
                self.search_intersection = self.geometry.intersection(searched_bbox_as_shape)
            except TopologicalError:
                import traceback as tb
                logger.warning('Unable to intersect the requested extent: %s with the product geometry: %s. Got:\n%s',
                               searched_bbox_as_shape, self.properties['geometry'], tb.format_exc())
                self.search_intersection = None
        self.driver = DRIVERS.get(self.product_type, NoDriver())
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
        :rtype: xarray.DataArray
        """
        fail_value = xr.DataArray(numpy.empty(0))
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
                               'product.register_downloader(download_plugin, auth_plugin) before trying to call '
                               'product.get_data(...)')
                return fail_value
            if not path_of_downloaded_file:
                return fail_value
            dataset_address = self.driver.get_data_address(self, band)
        min_x, min_y, max_x, max_y = extent
        height = int((max_y - min_y) / resolution)
        width = int((max_x - min_x) / resolution)
        out_shape = (width, height)
        with rasterio.open(dataset_address) as src:
            with WarpedVRT(src, dst_crs=crs, resampling=Resampling.bilinear) as vrt:
                array = vrt.read(1, window=vrt.window(*extent), out_shape=out_shape, resampling=Resampling.bilinear)
                return xr.DataArray(array)

    def as_dict(self):
        """Builds a representation of EOProduct as a dictionary to enable its geojson serialization

        :returns: The representation of a :class:`~eodag.api.product.EOProduct` as a Python dict
        :rtype: dict
        """
        geojson_repr = {
            'type': 'Feature',
            'geometry': geometry.mapping(self.geometry),
            'id': self.properties['id'],
            'properties': {
                'eodag_product_type': self.product_type,
                'eodag_provider': self.provider,
                'eodag_download_url': self.location,
                'eodag_search_intersection': geometry.mapping(self.search_intersection),
            }
        }
        geojson_repr['properties'].update({
            key: value
            for key, value in self.properties.items()
            if key not in ('geometry', 'id')
        })
        return geojson_repr

    @classmethod
    def from_geojson(cls, feature):
        """Builds an :class:`~eodag.api.product.EOProduct` object from its representation as geojson

        :param feature: The representation of a :class:`~eodag.api.product.EOProduct` as a Python dict
        :type feature: dict
        :returns: An instance of :class:`~eodag.api.product.EOProduct`
        :rtype: :class:`~eodag.api.product.EOProduct`
        """
        obj = cls(
            feature['properties']['eodag_product_type'],
            feature['properties']['eodag_provider'],
            feature['properties']['eodag_download_url'],
            properties_from_json(feature, DEFAULT_METADATA_MAPPING)
        )
        obj.search_intersection = feature['properties']['eodag_search_intersection']
        return obj

    # Implementation of geo-interface protocol (See https://gist.github.com/sgillies/2217756)
    __geo_interface__ = property(as_dict)

    def __repr__(self):
        return '{}(id={}, provider={})'.format(self.__class__.__name__, self.properties['id'], self.provider)

    def encode(self, raster, encoding='protobuf'):
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
        :type raster: xarray.DataArray
        :returns: The raster data represented by this subset in protocol buffers encoding
        :rtype: bytes
        """
        from eodag.api.product.protobuf import eo_product_pb2
        subdataset = eo_product_pb2.EOProductSubdataset()
        subdataset.id = self.properties['id']
        subdataset.producer = self.provider
        subdataset.product_type = self.product_type
        subdataset.platform = self.properties['platformSerialIdentifier']
        subdataset.sensor = self.properties['instrument']
        data = subdataset.data
        data.array.extend(list(raster.values.flatten().astype(int)))
        data.shape.extend(list(raster.values.shape))
        data.dtype = raster.values.dtype.name
        return subdataset.SerializeToString()

    def register_downloader(self, downloader, authenticator):
        """Give to the product the information needed to download itself.

        :param downloader: The download method that it can use
        :type downloader: Concrete subclass of :class:`~eodag.plugins.download.base.Download` or
                          :class:`~eodag.plugins.api.base.Api`
        :param authenticator: The authentication method needed to perform the download
        :type authenticator: Concrete subclass of :class:`~eodag.plugins.authentication.base.Authentication`
        """
        self.downloader = downloader
        self.downloader_auth = authenticator

    def download(self):
        """Download the EO product using the provided download plugin and the authenticator if necessary.

        The actual download of the product occurs only at the first call of this method. A side effect of this method is
        that it changes the `location` attribute of an EOProduct, from its remote address to the local address.

        :returns: The absolute path to the downloaded product on the local filesystem
        :rtype: str or unicode
        """
        if self.downloader is None:
            raise RuntimeError('EO product is unable to download itself due to the lack of a download plugin')
        # Remove the capability for the downloader to perform extraction if the downloaded product is a zipfile. This
        # way, the eoproduct is able to control how it stores itself on the local filesystem
        old_extraction_config = self.downloader.config['extract']
        self.downloader.config['extract'] = False
        auth = self.downloader_auth.authenticate() if self.downloader_auth is not None else self.downloader_auth
        fs_location = self.downloader.download(self, auth=auth)
        if fs_location is None:
            logger.warning('The download may have fail or the location of the downloaded file on the local filesystem '
                           'have not been returned by the download plugin')
            return ''
        if zipfile.is_zipfile(fs_location):
            # Unzip only if it was not done before
            if not os.path.exists(fs_location[:fs_location.index('.zip')]):
                with zipfile.ZipFile(fs_location, 'r') as zfile:
                    fileinfos = tqdm(zfile.infolist(), unit='file', desc='Extracting files from {}'.format(fs_location))
                    for fileinfo in fileinfos:
                        zfile.extract(fileinfo, path=fs_location[:fs_location.index('.zip')])
            # Handle depth levels in the product archive. For example, if the downloaded archive was
            # extracted to: /top_level/product_base_dir and archive_depth was configured to 2, the product
            # location will be /top_level/product_base_dir.
            # WARNING: A strong assumption is made here: there is only one subdirectory per level
            archive_depth = self.downloader.config.get('archive_depth', 1)
            fs_location = fs_location[:fs_location.index('.zip')]
            count = 1
            while count < archive_depth:
                fs_location = os.path.join(fs_location, os.listdir(fs_location)[0])
                count += 1
        # After the product has been downloaded, we need to modify its location attribute to reflect that it is now
        # in the filesystem
        logger.debug('Product location updated from %s to %s', self.location, fs_location)
        self.location = 'file://{}'.format(fs_location)
        # Restore configuration
        self.downloader.config['extract'] = old_extraction_config
        return fs_location
