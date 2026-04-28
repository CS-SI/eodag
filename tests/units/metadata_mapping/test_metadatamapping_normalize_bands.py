# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, http://www.c-s.fr
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
import unittest

from eodag.api.product import EOProduct


class TestMetadataMappingNormalize(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _test_eoproduct_normalize_assets_bands(self):
        """Test normalisation of eo:bands and raster:bands in EOProduct assets."""

        def create_product_get_asset_dict(assets_update: dict = None):

            if assets_update is None:
                assets_update = {}

            asset_id = "LC08_L2SP_090013_20240502_20240513_02_T1_SR_B1.TIF"
            href = (
                "https://landsateuwest.blob.core.windows.net/landsat-c2/level-2/"
                "standard/oli-tirs/2024/090/013/"
                "LC08_L2SP_090013_20240502_20240513_02_T1/"
                "LC08_L2SP_090013_20240502_20240513_02_T1_SR_B1.TIF"
            )
            common_asset_fields = {
                "href": href,
                "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                "roles": ["data"],
                "title": "LC08_L2SP_090013_20240502_20240513_02_T1_SR_B1.TIF",
                "description": (
                    "Collection 2 Level-2 Coastal/Aerosol Band (SR_B1) Surface Reflectance"
                ),
            }

            product = EOProduct(
                provider="planetary_computer",
                properties={"id": "LC08_L2SP_090013_20240502_02_T1"},
                collection="LANDSAT_C2L2",
            )
            product.assets.update(
                {
                    asset_id: {
                        **common_asset_fields,
                        **assets_update,
                    },
                }
            )
            product._normalize_bands()
            asset = product.assets[asset_id].as_dict()
            return asset

        asset = create_product_get_asset_dict(
            {
                "eo:bands": [
                    {
                        "name": "OLI_B1",
                        "common_name": "coastal",
                        "description": "Coastal/Aerosol",
                        "center_wavelength": 0.44,
                        "full_width_half_max": 0.02,
                    }
                ],
                "raster:bands": [
                    {
                        "scale": 2.75e-05,
                        "nodata": 0,
                        "offset": -0.2,
                        "data_type": "uint16",
                        "spatial_resolution": 30,
                    }
                ],
            }
        )
        self.assertEqual(asset.get("eo:center_wavelength"), 0.44)
        self.assertEqual(asset.get("eo:full_width_half_max"), 0.02)
        self.assertEqual(asset.get("raster:scale"), 2.75e-05)
        self.assertEqual(asset.get("nodata"), 0)
        self.assertEqual(asset.get("raster:offset"), -0.2)
        self.assertEqual(asset.get("data_type"), "uint16")
        self.assertEqual(asset.get("raster:spatial_resolution"), 30)
        self.assertEqual(
            asset.get("bands", []), [{"name": "OLI_B1", "eo:common_name": "coastal"}]
        )

        # Reduce multibands of eo:bands: only join and move parameters with
        # the same value; per-band fields stay on the bands list.
        asset = create_product_get_asset_dict(
            {
                "eo:bands": [
                    {
                        "name": "OLI_B1",
                        "common_name": "coastal",
                        "description": "Coastal/Aerosol",
                        "center_wavelength": 0.44,
                        "full_width_half_max": 0.02,
                    },
                    {
                        "name": "OLI_B2",
                        "common_name": "coastal",
                        "description": "Coastal/Aerosol",
                        "center_wavelength": 0.44,
                        "full_width_half_max": 0.02,
                    },
                    {
                        "name": "OLI_B3",
                        "common_name": "coastal",
                        "description": "Coastal/Aerosol",
                        "center_wavelength": 0.44,
                        "full_width_half_max": 0.02,
                    },
                ]
            }
        )
        self.assertEqual(asset.get("eo:center_wavelength"), 0.44)
        self.assertEqual(asset.get("eo:full_width_half_max"), 0.02)
        self.assertEqual(
            asset.get("bands"),
            [
                {"name": "OLI_B1", "eo:common_name": "coastal"},
                {"name": "OLI_B2", "eo:common_name": "coastal"},
                {"name": "OLI_B3", "eo:common_name": "coastal"},
            ],
        )

        asset = create_product_get_asset_dict(
            {
                "eo:bands": [
                    {
                        "name": "OLI_B1",
                        "common_name": "coastal",
                        "description": "Coastal/Aerosol",
                        "center_wavelength": 0.44,
                        "full_width_half_max": 0.02,
                    },
                    {
                        "name": "OLI_B2",
                        "common_name": "coastal",
                        "description": "Coastal/Aerosol",
                        "center_wavelength": 0.44,
                        "full_width_half_max": 0.02,
                    },
                    {
                        "name": "OLI_B3",
                        "common_name": "coastal",
                        "description": "Coastal/Aerosol",
                        "center_wavelength": 0.44,
                        "full_width_half_max": 0.02,
                    },
                ],
                "raster:bands": [
                    {
                        "scale": 2.75e-05,
                        "nodata": 0,
                        "offset": -0.2,
                        "data_type": "uint16",
                        "spatial_resolution": 30,
                    }
                ],
            }
        )
        self.assertEqual(asset.get("eo:center_wavelength"), 0.44)
        self.assertEqual(asset.get("eo:full_width_half_max"), 0.02)
        self.assertEqual(asset.get("raster:scale"), 2.75e-05)
        self.assertEqual(asset.get("nodata"), 0)
        self.assertEqual(asset.get("raster:offset"), -0.2)
        self.assertEqual(asset.get("data_type"), "uint16")
        self.assertEqual(asset.get("raster:spatial_resolution"), 30)
        self.assertEqual(
            asset.get("bands"),
            [
                {"name": "OLI_B1", "eo:common_name": "coastal"},
                {"name": "OLI_B2", "eo:common_name": "coastal"},
                {"name": "OLI_B3", "eo:common_name": "coastal"},
            ],
        )

    def test_eoproduct_normalize_properties_bands(self):
        """``EOProduct._normalize_bands`` should also migrate
        ``eo:bands``/``raster:bands`` declared at the product properties level.
        """

        def create_product_get_properties(properties: dict = None) -> dict:

            if properties is None:
                properties = {}

            product = EOProduct(
                provider="planetary_computer",
                properties={"id": "LC08_L2SP_090013_20240502_02_T1", **properties},
                collection="LANDSAT_C2L2",
            )
            product._normalize_bands()
            return product.properties

        properties = create_product_get_properties(
            {
                "eo:bands": [
                    {
                        "name": "OLI_B1",
                        "common_name": "coastal",
                        "center_wavelength": 0.44,
                        "full_width_half_max": 0.02,
                    },
                    {
                        "name": "OLI_B2",
                        "common_name": "blue",
                        "center_wavelength": 0.48,
                        "full_width_half_max": 0.02,
                    },
                ],
                "raster:bands": [
                    {"nodata": 0, "data_type": "uint16", "spatial_resolution": 30},
                    {"nodata": 0, "data_type": "uint16", "spatial_resolution": 30},
                ],
            }
        )

        self.assertNotIn("eo:bands", properties)
        self.assertNotIn("raster:bands", properties)
        # fields shared by every band are promoted to the parent
        self.assertEqual(properties.get("eo:full_width_half_max"), 0.02)
        self.assertEqual(properties.get("nodata"), 0)
        self.assertEqual(properties.get("data_type"), "uint16")
        self.assertEqual(properties.get("raster:spatial_resolution"), 30)
        # remaining per-band fields end up in the STAC 1.1 ``bands`` array
        self.assertEqual(
            properties.get("bands"),
            [
                {
                    "name": "OLI_B1",
                    "eo:common_name": "coastal",
                    "eo:center_wavelength": 0.44,
                },
                {
                    "name": "OLI_B2",
                    "eo:common_name": "blue",
                    "eo:center_wavelength": 0.48,
                },
            ],
        )
