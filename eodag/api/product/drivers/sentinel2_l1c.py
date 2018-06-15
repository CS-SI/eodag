# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import os
import re

import rasterio

from eodag.api.product.drivers.base import DatasetDriver
from eodag.utils.exceptions import AddressNotFound, UnsupportedDatasetAddressScheme


class Sentinel2L1C(DatasetDriver):
    BAND_FILE_PATTERN_TPL = r'^.+_{band}\.jp2$'
    SPATIAL_RES_PER_BANDS = {
        '10m': ('B02', 'B03', 'B04', 'B08'),
        '20m': ('B05', 'B06', 'B07', 'B11', 'B12', 'B8A'),
        '60m': ('B01', 'B09', 'B10'),
        'TCI': ('TCI',),
    }

    def get_data_address(self, eo_product, band):
        """Compute the address of a subdataset for a Sentinel2 product.

        The algorithm is as follows:
            - First compute the top level metadata file path from the ``eo_product.property['productIdentifier']``, the name
              of its sensor (e.g.: 'MSI'), and its product type (e.g.: 'L1C') and open it as a `rasterio` dataset
            - Then mimics the shell command ``gdalinfo -sd n /path/metadata.xml`` to get the final address:
                - iterate through the subdataset addresses ('<DRIVER>:<path>/<mtd>.xml:<spatial-resolution>:<crs>')
                  detected by the rasterio dataset
                - open only the address for which the extracted spatial resolution maps to a tuple of bands including
                  the band of interest
            - Finally, filter the list of files of the previously opened rasterio dataset, to return the filesystem-like
              address that matches the band file pattern ``r'^.+_B01\.jp2$'`` if band = 'B01' for example.

        See :func:`~eodag.api.product.drivers.base.DatasetDriver.get_data_address` to get help on the formal
        parameters.
        """
        product_location_scheme = eo_product.location.split('://')[0]
        if product_location_scheme == 'file':
            top_level_mtd = os.path.join(re.sub(r'file://', '', eo_product.location), 'MTD_MSIL1C.xml')
            with rasterio.open(top_level_mtd) as dataset:
                for address in dataset.subdatasets:
                    spatial_res = address.split(':')[-2]
                    if band in self.SPATIAL_RES_PER_BANDS[spatial_res]:
                        with rasterio.open(address) as subdataset:
                            band_file_pattern = re.compile(self.BAND_FILE_PATTERN_TPL.format(band=band))
                            for filename in filter(lambda f: band_file_pattern.match(f), subdataset.files):
                                return filename
            raise AddressNotFound
        raise UnsupportedDatasetAddressScheme('eo product {} is accessible through a location scheme that is not yet '
                                              'supported by eodag: {}'.format(eo_product, product_location_scheme))
