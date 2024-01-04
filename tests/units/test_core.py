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

import copy
import glob
import json
import logging
import os
import shutil
import unittest
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from pkg_resources import resource_filename
from shapely import wkt
from shapely.geometry import LineString, MultiPolygon, Polygon

from eodag import __version__ as eodag_version
from eodag.utils import GENERIC_PRODUCT_TYPE
from tests import TEST_RESOURCES_PATH
from tests.context import (
    DEFAULT_MAX_ITEMS_PER_PAGE,
    CommonQueryables,
    EODataAccessGateway,
    EOProduct,
    NoMatchingProductType,
    PluginImplementationError,
    ProviderConfig,
    Queryables,
    RequestError,
    SearchResult,
    UnsupportedProductType,
    UnsupportedProvider,
    get_geometry_from_various,
    load_default_config,
    makedirs,
    model_fields_to_annotated_tuple,
)
from tests.utils import mock, write_eodag_conf_with_fake_credentials


class TestCoreBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestCoreBase, cls).setUpClass()
        # Mock home and eodag conf directory to tmp dir
        cls.tmp_home_dir = TemporaryDirectory()
        cls.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=cls.tmp_home_dir.name
        )
        cls.expanduser_mock.start()

        # create eodag conf dir in tmp home dir
        eodag_conf_dir = os.path.join(cls.tmp_home_dir.name, ".config", "eodag")
        os.makedirs(eodag_conf_dir, exist_ok=False)
        # use empty config file with fake credentials in order to have full
        # list for tests and prevent providers to be pruned
        write_eodag_conf_with_fake_credentials(
            os.path.join(eodag_conf_dir, "eodag.yml")
        )

    @classmethod
    def tearDownClass(cls):
        super(TestCoreBase, cls).tearDownClass()
        # stop Mock and remove tmp config dir
        cls.expanduser_mock.stop()
        cls.tmp_home_dir.cleanup()
        # reset logging
        logger = logging.getLogger("eodag")
        logger.handlers = []
        logger.level = 0


class TestCore(TestCoreBase):
    SUPPORTED_PRODUCT_TYPES = {
        "CAMS_GAC_FORECAST": ["cop_ads"],
        "CAMS_EU_AIR_QUALITY_FORECAST": ["cop_ads"],
        "CAMS_GFE_GFAS": ["cop_ads"],
        "CAMS_GRF": ["cop_ads"],
        "CAMS_GRF_AUX": ["cop_ads"],
        "CAMS_SOLAR_RADIATION": ["cop_ads"],
        "CAMS_GREENHOUSE_EGG4_MONTHLY": ["cop_ads"],
        "CAMS_GREENHOUSE_EGG4": ["cop_ads"],
        "CAMS_GREENHOUSE_INVERSION": ["cop_ads"],
        "CAMS_GLOBAL_EMISSIONS": ["cop_ads"],
        "CAMS_EAC4": ["cop_ads"],
        "CAMS_EAC4_MONTHLY": ["cop_ads"],
        "CAMS_EU_AIR_QUALITY_RE": ["cop_ads"],
        "CBERS4_AWFI_L2": ["aws_eos"],
        "CBERS4_AWFI_L4": ["aws_eos"],
        "CBERS4_MUX_L2": ["aws_eos"],
        "CBERS4_MUX_L4": ["aws_eos"],
        "CBERS4_PAN10M_L2": ["aws_eos"],
        "CBERS4_PAN10M_L4": ["aws_eos"],
        "CBERS4_PAN5M_L2": ["aws_eos"],
        "CBERS4_PAN5M_L4": ["aws_eos"],
        "CLMS_CORINE": ["wekeo"],
        "CLMS_GLO_DMP_333M": ["wekeo"],
        "CLMS_GLO_FAPAR_333M": ["wekeo"],
        "CLMS_GLO_FCOVER_333M": ["wekeo"],
        "CLMS_GLO_GDMP_333M": ["wekeo"],
        "CLMS_GLO_LAI_333M": ["wekeo"],
        "CLMS_GLO_NDVI_1KM_LTS": ["wekeo"],
        "CLMS_GLO_NDVI_333M": ["wekeo"],
        "COP_DEM_GLO30_DGED": ["creodias", "creodias_s3", "wekeo"],
        "COP_DEM_GLO30_DTED": ["creodias", "creodias_s3"],
        "COP_DEM_GLO90_DGED": ["creodias", "creodias_s3", "wekeo"],
        "COP_DEM_GLO90_DTED": ["creodias", "creodias_s3"],
        "EEA_DAILY_SSM_1KM": ["wekeo"],
        "EEA_DAILY_SWI_1KM": ["wekeo"],
        "EEA_DAILY_VI": ["wekeo"],
        "EFAS_FORECAST": ["cop_cds", "wekeo"],
        "EFAS_HISTORICAL": ["cop_cds", "wekeo"],
        "EFAS_REFORECAST": ["cop_cds", "wekeo"],
        "EFAS_SEASONAL": ["cop_cds", "wekeo"],
        "EFAS_SEASONAL_REFORECAST": ["cop_cds", "wekeo"],
        "ERA5_LAND": ["cop_cds", "wekeo"],
        "ERA5_LAND_MONTHLY": ["cop_cds", "wekeo"],
        "ERA5_PL": ["cop_cds", "wekeo"],
        "ERA5_PL_MONTHLY": ["cop_cds", "wekeo"],
        "ERA5_SL": ["cop_cds", "wekeo"],
        "ERA5_SL_MONTHLY": ["cop_cds", "wekeo"],
        "FIRE_HISTORICAL": ["cop_cds", "wekeo"],
        "GLACIERS_DIST_RANDOLPH": ["cop_cds", "wekeo"],
        "GLACIERS_ELEVATION_AND_MASS_CHANGE": ["wekeo"],
        "GLOFAS_FORECAST": ["cop_cds", "wekeo"],
        "GLOFAS_HISTORICAL": ["cop_cds", "wekeo"],
        "GLOFAS_REFORECAST": ["cop_cds", "wekeo"],
        "GLOFAS_SEASONAL": ["cop_cds", "wekeo"],
        "GLOFAS_SEASONAL_REFORECAST": ["cop_cds", "wekeo"],
        "L57_REFLECTANCE": ["theia"],
        "L8_OLI_TIRS_C1L1": ["aws_eos", "earth_search", "earth_search_gcs", "onda"],
        "L8_REFLECTANCE": ["theia"],
        "LANDSAT_C2L1": [
            "astraea_eod",
            "planetary_computer",
            "usgs",
            "usgs_satapi_aws",
        ],
        "LANDSAT_C2L2": ["planetary_computer", "usgs"],
        "LANDSAT_C2L2ALB_BT": ["usgs_satapi_aws"],
        "LANDSAT_C2L2ALB_SR": ["usgs_satapi_aws"],
        "LANDSAT_C2L2ALB_ST": ["usgs_satapi_aws"],
        "LANDSAT_C2L2ALB_TA": ["usgs_satapi_aws"],
        "LANDSAT_C2L2_SR": ["usgs_satapi_aws"],
        "LANDSAT_C2L2_ST": ["usgs_satapi_aws"],
        "LANDSAT_ETM_C1": ["usgs"],
        "LANDSAT_ETM_C2L1": ["usgs"],
        "LANDSAT_ETM_C2L2": ["usgs"],
        "LANDSAT_TM_C1": ["usgs"],
        "LANDSAT_TM_C2L1": ["usgs"],
        "LANDSAT_TM_C2L2": ["usgs"],
        "MODIS_MCD43A4": ["astraea_eod", "aws_eos", "planetary_computer"],
        "NAIP": ["astraea_eod", "aws_eos", "planetary_computer"],
        "NEMSAUTO_TCDC": ["meteoblue"],
        "NEMSGLOBAL_TCDC": ["meteoblue"],
        "OSO": ["theia"],
        "PLD_BUNDLE": ["theia"],
        "PLD_PAN": ["theia"],
        "PLD_PANSHARPENED": ["theia"],
        "PLD_XS": ["theia"],
        "S1_SAR_GRD": [
            "astraea_eod",
            "aws_eos",
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "peps",
            "planetary_computer",
            "sara",
            "wekeo",
        ],
        "S1_SAR_OCN": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "peps",
            "sara",
            "wekeo",
        ],
        "S1_SAR_RAW": ["cop_dataspace", "creodias", "creodias_s3", "onda", "wekeo"],
        "S1_SAR_SLC": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "peps",
            "sara",
            "wekeo",
        ],
        "S2_MSI_L1C": [
            "astraea_eod",
            "aws_eos",
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "earth_search",
            "earth_search_gcs",
            "onda",
            "peps",
            "sara",
            "usgs",
            "wekeo",
        ],
        "S2_MSI_L2A": [
            "astraea_eod",
            "aws_eos",
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "earth_search",
            "onda",
            "planetary_computer",
            "sara",
            "wekeo",
        ],
        "S2_MSI_L2AP": ["wekeo"],
        "S2_MSI_L2A_COG": ["earth_search_cog"],
        "S2_MSI_L2A_MAJA": ["theia"],
        "S2_MSI_L2B_MAJA_SNOW": ["theia"],
        "S2_MSI_L2B_MAJA_WATER": ["theia"],
        "S2_MSI_L3A_WASP": ["theia"],
        "S3_EFR": ["cop_dataspace", "creodias", "creodias_s3", "onda", "sara", "wekeo"],
        "S3_ERR": ["cop_dataspace", "creodias", "creodias_s3", "onda", "sara", "wekeo"],
        "S3_LAN": ["cop_dataspace", "creodias", "creodias_s3", "onda", "sara", "wekeo"],
        "S3_OLCI_L2LFR": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "sara",
            "wekeo",
        ],
        "S3_OLCI_L2LRR": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "sara",
            "wekeo",
        ],
        "S3_OLCI_L2WFR": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "sara",
            "wekeo",
        ],
        "S3_OLCI_L2WRR": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "sara",
            "wekeo",
        ],
        "S3_RAC": ["sara"],
        "S3_SLSTR_L1RBT": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "sara",
            "wekeo",
        ],
        "S3_SLSTR_L2": ["wekeo"],
        "S3_SLSTR_L2AOD": ["cop_dataspace", "creodias", "creodias_s3", "sara", "wekeo"],
        "S3_SLSTR_L2FRP": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "sara",
            "wekeo",
        ],
        "S3_SLSTR_L2LST": ["cop_dataspace", "creodias", "creodias_s3", "onda", "sara"],
        "S3_SLSTR_L2WST": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "sara",
            "wekeo",
        ],
        "S3_SRA": ["cop_dataspace", "creodias", "creodias_s3", "onda", "sara", "wekeo"],
        "S3_SRA_A": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "sara",
            "wekeo",
        ],
        "S3_SRA_BS": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "sara",
            "wekeo",
        ],
        "S3_SY_AOD": ["cop_dataspace", "creodias", "creodias_s3", "onda", "sara"],
        "S3_SY_SYN": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "onda",
            "sara",
            "wekeo",
        ],
        "S3_SY_V10": ["cop_dataspace", "creodias", "creodias_s3", "onda", "sara"],
        "S3_SY_VG1": ["cop_dataspace", "creodias", "creodias_s3", "onda", "sara"],
        "S3_SY_VGP": ["cop_dataspace", "creodias", "creodias_s3", "onda", "sara"],
        "S3_WAT": ["cop_dataspace", "creodias", "creodias_s3", "onda", "sara", "wekeo"],
        "S3_OLCI_L2WFR_BC003": ["wekeo"],
        "S3_OLCI_L2WRR_BC003": ["wekeo"],
        "S3_SRA_1A_BC004": ["wekeo"],
        "S3_SRA_1B_BC004": ["wekeo"],
        "S3_SRA_BS_BC004": ["wekeo"],
        "S3_WAT_BC004": ["wekeo"],
        "S3_SLSTR_L1RBT_BC004": ["wekeo"],
        "S3_SLSTR_L2WST_BC003": ["wekeo"],
        "S3_OLCI_L4BALTIC": ["wekeo"],
        "S6_P4_L1AHR_F06": ["wekeo"],
        "S6_P4_L1BLR_F06": ["wekeo"],
        "S6_P4_L1BAHR_F06": ["wekeo"],
        "S6_P4_L2LR_F06": ["wekeo"],
        "S6_P4_L2HR_F06": ["wekeo"],
        "S6_AMR_L2_F06": ["wekeo"],
        "S5P_L1B2_IR_ALL": ["wekeo"],
        "S5P_L1B_IR_SIR": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L1B_IR_UVN": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L1B_RA_BD1": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L1B_RA_BD2": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L1B_RA_BD3": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L1B_RA_BD4": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L1B_RA_BD5": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L1B_RA_BD6": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L1B_RA_BD7": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L1B_RA_BD8": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_AER_AI": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_AER_LH": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_CH4": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_CLOUD": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_CO": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_HCHO": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_NO2": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_NP_BD3": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_NP_BD6": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_NP_BD7": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_O3": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_O3_PR": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "S5P_L2_O3_TCL": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_SO2": ["cop_dataspace", "creodias", "creodias_s3", "onda"],
        "SATELLITE_CARBON_DIOXIDE": ["cop_cds", "wekeo"],
        "SATELLITE_METHANE": ["cop_cds", "wekeo"],
        "SATELLITE_SEA_LEVEL_BLACK_SEA": ["cop_cds", "wekeo"],
        "SEASONAL_MONTHLY_PL": ["cop_cds", "wekeo"],
        "SEASONAL_MONTHLY_SL": ["cop_cds", "wekeo"],
        "SEASONAL_ORIGINAL_PL": ["cop_cds", "wekeo"],
        "SEASONAL_ORIGINAL_SL": ["cop_cds", "wekeo"],
        "SEASONAL_POSTPROCESSED_PL": ["cop_cds", "wekeo"],
        "SEASONAL_POSTPROCESSED_SL": ["cop_cds", "wekeo"],
        "SIS_HYDRO_MET_PROJ": ["cop_cds", "wekeo"],
        "SPOT5_SPIRIT": ["theia"],
        "SPOT_SWH": ["theia"],
        "SPOT_SWH_OLD": ["theia"],
        "TIGGE_CF_SFC": ["ecmwf"],
        "UERRA_EUROPE_SL": ["cop_cds", "wekeo"],
        "VENUS_L1C": ["theia"],
        "VENUS_L2A_MAJA": ["theia"],
        "VENUS_L3A_MAJA": ["theia"],
        GENERIC_PRODUCT_TYPE: [
            "theia",
            "peps",
            "onda",
            "usgs",
            "creodias",
            "astraea_eod",
            "usgs_satapi_aws",
            "earth_search",
            "earth_search_cog",
            "earth_search_gcs",
            "ecmwf",
            "cop_ads",
            "cop_cds",
            "meteoblue",
            "cop_dataspace",
            "planetary_computer",
            "hydroweb_next",
            "creodias_s3",
        ],
    }
    SUPPORTED_PROVIDERS = [
        "peps",
        "usgs",
        "theia",
        "creodias",
        "onda",
        "aws_eos",
        "astraea_eod",
        "usgs_satapi_aws",
        "earth_search",
        "earth_search_cog",
        "earth_search_gcs",
        "ecmwf",
        "cop_ads",
        "cop_cds",
        "sara",
        "meteoblue",
        "cop_dataspace",
        "planetary_computer",
        "hydroweb_next",
        "wekeo",
        "creodias_s3",
    ]

    def setUp(self):
        super(TestCore, self).setUp()
        self.dag = EODataAccessGateway()
        self.conf_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
        # mock os.environ to empty env
        self.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        self.mock_os_environ.start()

    def tearDown(self):
        super(TestCore, self).tearDown()
        # stop os.environ
        self.mock_os_environ.stop()

    def test_supported_providers_in_unit_test(self):
        """Every provider must be referenced in the core unittest SUPPORTED_PROVIDERS class attribute"""
        for provider in self.dag.available_providers():
            self.assertIn(provider, self.SUPPORTED_PROVIDERS)

    def test_supported_product_types_in_unit_test(self):
        """Every product type must be referenced in the core unit test SUPPORTED_PRODUCT_TYPES class attribute"""
        for product_type in self.dag.list_product_types(fetch_providers=False):
            assert (
                product_type["ID"] in self.SUPPORTED_PRODUCT_TYPES.keys()
                or product_type["_id"] in self.SUPPORTED_PRODUCT_TYPES.keys()
            )

    def test_list_product_types_ok(self):
        """Core api must correctly return the list of supported product types"""
        product_types = self.dag.list_product_types(fetch_providers=False)
        self.assertIsInstance(product_types, list)
        for product_type in product_types:
            self.assertListProductTypesRightStructure(product_type)
        # There should be no repeated product type in the output
        self.assertEqual(len(product_types), len(set(pt["ID"] for pt in product_types)))
        # add alias for product type - should still work
        products = self.dag.product_types_config
        products["S2_MSI_L1C"]["alias"] = "S2_MSI_ALIAS"
        product_types = self.dag.list_product_types(fetch_providers=False)
        for product_type in product_types:
            self.assertListProductTypesRightStructure(product_type)
        # There should be no repeated product type in the output
        self.assertEqual(len(product_types), len(set(pt["ID"] for pt in product_types)))
        # use alias as id
        self.assertIn("S2_MSI_ALIAS", [pt["ID"] for pt in product_types])

    def test_list_product_types_for_provider_ok(self):
        """Core api must correctly return the list of supported product types for a given provider"""
        for provider in self.SUPPORTED_PROVIDERS:
            product_types = self.dag.list_product_types(
                provider=provider, fetch_providers=False
            )
            self.assertIsInstance(product_types, list)
            for product_type in product_types:
                self.assertListProductTypesRightStructure(product_type)
                if product_type["ID"] in self.SUPPORTED_PRODUCT_TYPES:
                    self.assertIn(
                        provider, self.SUPPORTED_PRODUCT_TYPES[product_type["ID"]]
                    )
                else:
                    self.assertIn(
                        provider, self.SUPPORTED_PRODUCT_TYPES[product_type["_id"]]
                    )

    def test_list_product_types_for_unsupported_provider(self):
        """Core api must raise UnsupportedProvider error for list_product_types with unsupported provider"""
        unsupported_provider = "a"
        self.assertRaises(
            UnsupportedProvider,
            self.dag.list_product_types,
            provider=unsupported_provider,
        )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test_list_product_types_fetch_providers(self, mock_fetch_product_types_list):
        """Core api must fetch providers for new product types if option is passed to list_product_types"""
        self.dag.list_product_types(fetch_providers=False)
        assert not mock_fetch_product_types_list.called
        self.dag.list_product_types(provider="peps", fetch_providers=True)
        mock_fetch_product_types_list.assert_called_once_with(self.dag, provider="peps")

    def test_update_product_types_list(self):
        """Core api.update_product_types_list must update eodag product types list"""
        with open(os.path.join(TEST_RESOURCES_PATH, "ext_product_types.json")) as f:
            ext_product_types_conf = json.load(f)

        self.assertNotIn("foo", self.dag.providers_config["astraea_eod"].products)
        self.assertNotIn("bar", self.dag.providers_config["astraea_eod"].products)
        self.assertNotIn("foo", self.dag.product_types_config)
        self.assertNotIn("bar", self.dag.product_types_config)

        self.dag.update_product_types_list(ext_product_types_conf)

        self.assertIn("foo", self.dag.providers_config["astraea_eod"].products)
        self.assertIn("bar", self.dag.providers_config["astraea_eod"].products)
        self.assertEqual(self.dag.product_types_config["foo"]["license"], "WTFPL")
        self.assertEqual(
            self.dag.product_types_config["bar"]["title"], "Bar collection"
        )

    def test_update_product_types_list_unknown_provider(self):
        """Core api.update_product_types_list on unkwnown provider must not crash and not update conf"""
        with open(os.path.join(TEST_RESOURCES_PATH, "ext_product_types.json")) as f:
            ext_product_types_conf = json.load(f)
        self.dag.providers_config.pop("astraea_eod")

        self.dag.update_product_types_list(ext_product_types_conf)
        self.assertNotIn("astraea_eod", self.dag.providers_config)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.discover_product_types",
        autospec=True,
    )
    def test_update_product_types_list_with_api_plugin(
        self, mock_plugin_discover_product_types
    ):
        """Core api.update_product_types_list with the api plugin must update eodag product types list"""
        with open(os.path.join(TEST_RESOURCES_PATH, "ext_product_types.json")) as f:
            ext_product_types_conf = json.load(f)

        # we keep the existing ext-conf to use it for a provider with an api plugin
        ext_product_types_conf["ecmwf"] = ext_product_types_conf.pop("astraea_eod")

        self.assertNotIn("foo", self.dag.providers_config["ecmwf"].products)
        self.assertNotIn("bar", self.dag.providers_config["ecmwf"].products)
        self.assertNotIn("foo", self.dag.product_types_config)
        self.assertNotIn("bar", self.dag.product_types_config)

        # ecmwf must have discover_product_types attribute to allow the launch of update_product_types_list
        self.dag.update_providers_config(
            """
            ecmwf:
                api:
                    discover_product_types:
                        fetch_url: 'http://new-endpoint'
                    need_auth: False
            """
        )

        self.dag.update_product_types_list(ext_product_types_conf)

        self.assertIn("foo", self.dag.providers_config["ecmwf"].products)
        self.assertIn("bar", self.dag.providers_config["ecmwf"].products)
        self.assertEqual(self.dag.product_types_config["foo"]["license"], "WTFPL")
        self.assertEqual(
            self.dag.product_types_config["bar"]["title"], "Bar collection"
        )

    def test_update_product_types_list_without_plugin(self):
        """Core api.update_product_types_list without search and api plugin do nothing"""
        with open(os.path.join(TEST_RESOURCES_PATH, "ext_product_types.json")) as f:
            ext_product_types_conf = json.load(f)

        self.assertNotIn("foo", self.dag.providers_config["astraea_eod"].products)
        self.assertNotIn("bar", self.dag.providers_config["astraea_eod"].products)
        self.assertNotIn("foo", self.dag.product_types_config)
        self.assertNotIn("bar", self.dag.product_types_config)

        delattr(self.dag.providers_config["astraea_eod"], "search")

        self.dag.update_product_types_list(ext_product_types_conf)

        self.assertNotIn("foo", self.dag.providers_config["astraea_eod"].products)
        self.assertNotIn("bar", self.dag.providers_config["astraea_eod"].products)
        self.assertNotIn("foo", self.dag.product_types_config)
        self.assertNotIn("bar", self.dag.product_types_config)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.discover_product_types",
        autospec=True,
        return_value={
            "providers_config": {"foo": {"productType": "foo"}},
            "product_types_config": {"foo": {"title": "Foo collection"}},
        },
    )
    def test_discover_product_types(self, mock_plugin_discover_product_types):
        """Core api must fetch providers for product types"""
        ext_product_types_conf = self.dag.discover_product_types(provider="astraea_eod")
        self.assertEqual(
            ext_product_types_conf["astraea_eod"]["providers_config"]["foo"][
                "productType"
            ],
            "foo",
        )
        self.assertEqual(
            ext_product_types_conf["astraea_eod"]["product_types_config"]["foo"][
                "title"
            ],
            "Foo collection",
        )

    @mock.patch(
        "eodag.plugins.apis.ecmwf.EcmwfApi.discover_product_types",
        autospec=True,
        return_value={
            "providers_config": {"foo": {"productType": "foo"}},
            "product_types_config": {"foo": {"title": "Foo collection"}},
        },
    )
    def test_discover_product_types_with_api_plugin(
        self, mock_plugin_discover_product_types
    ):
        """Core api must fetch providers with api plugin for product types"""
        self.dag.update_providers_config(
            """
            ecmwf:
                api:
                    discover_product_types:
                        fetch_url: 'http://new-endpoint'
                    need_auth: False
            """
        )
        ext_product_types_conf = self.dag.discover_product_types(provider="ecmwf")
        self.assertEqual(
            ext_product_types_conf["ecmwf"]["providers_config"]["foo"]["productType"],
            "foo",
        )
        self.assertEqual(
            ext_product_types_conf["ecmwf"]["product_types_config"]["foo"]["title"],
            "Foo collection",
        )

    def test_discover_product_types_without_plugin(self):
        """Core api must not fetch providers without search and api plugins"""
        delattr(self.dag.providers_config["astraea_eod"], "search")
        ext_product_types_conf = self.dag.discover_product_types(provider="astraea_eod")
        self.assertEqual(
            ext_product_types_conf,
            None,
        )

    @mock.patch("eodag.api.core.get_ext_product_types_conf", autospec=True)
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.discover_product_types", autospec=True
    )
    def test_fetch_product_types_list(
        self, mock_discover_product_types, mock_get_ext_product_types_conf
    ):
        """Core api must fetch product types list and update if needed"""
        # check that no provider has already been fetched
        for provider_config in self.dag.providers_config.values():
            self.assertFalse(getattr(provider_config, "product_types_fetched", False))

        # check that by default get_ext_product_types_conf() is called without args
        self.dag.fetch_product_types_list()
        mock_get_ext_product_types_conf.assert_called_with()

        # check that with an empty/mocked ext-conf, no provider has been fetched
        for provider_config in self.dag.providers_config.values():
            self.assertFalse(getattr(provider_config, "product_types_fetched", False))

        # check that EODAG_EXT_PRODUCT_TYPES_CFG_FILE env var will be used as get_ext_product_types_conf() arg
        os.environ["EODAG_EXT_PRODUCT_TYPES_CFG_FILE"] = "some/file"
        self.dag.fetch_product_types_list()
        mock_get_ext_product_types_conf.assert_called_with("some/file")
        os.environ.pop("EODAG_EXT_PRODUCT_TYPES_CFG_FILE")

        # check that with a non-empty ext-conf, a provider will be marked as fetched, and eodag conf updated
        mock_get_ext_product_types_conf.return_value = {
            "astraea_eod": {
                "providers_config": {"foo": {"productType": "foo"}},
                "product_types_config": {"foo": {"title": "Foo collection"}},
            }
        }
        # add an empty ext-conf for other providers to prevent them to be fetched
        for provider, provider_config in self.dag.providers_config.items():
            if provider != "astraea_eod" and hasattr(provider_config, "search"):
                provider_search_config = provider_config.search
            elif provider != "astraea_eod" and hasattr(provider_config, "api"):
                provider_search_config = provider_config.api
            else:
                continue
            if hasattr(
                provider_search_config, "discover_product_types"
            ) and provider_search_config.discover_product_types.get("fetch_url", None):
                mock_get_ext_product_types_conf.return_value[provider] = {}
        self.dag.fetch_product_types_list()
        self.assertTrue(self.dag.providers_config["astraea_eod"].product_types_fetched)
        self.assertEqual(
            self.dag.providers_config["astraea_eod"].products["foo"],
            {"productType": "foo"},
        )
        self.assertEqual(
            self.dag.product_types_config.source["foo"], {"title": "Foo collection"}
        )

        # update existing provider conf and check that discover_product_types() is launched for it
        self.assertEqual(mock_discover_product_types.call_count, 0)
        self.dag.update_providers_config(
            """
            astraea_eod:
                search:
                    discover_product_types:
                        fetch_url: 'http://new-endpoint'
            """
        )
        self.dag.fetch_product_types_list()
        mock_discover_product_types.assert_called_once_with(
            self.dag, provider="astraea_eod"
        )

        # add new provider conf and check that discover_product_types() is launched for it
        self.assertEqual(mock_discover_product_types.call_count, 1)
        self.dag.update_providers_config(
            """
            foo_provider:
                search:
                    type: StacSearch
                    api_endpoint: https://foo.bar/search
                products:
                    GENERIC_PRODUCT_TYPE:
                        productType: '{productType}'
            """
        )
        self.dag.fetch_product_types_list()
        mock_discover_product_types.assert_called_with(
            self.dag, provider="foo_provider"
        )
        # discover_product_types() should have been called 2 more times
        # (once per dynamically configured provider)
        self.assertEqual(mock_discover_product_types.call_count, 3)

        # now check that if provider is specified, only this one is fetched
        mock_discover_product_types.reset_mock()
        self.dag.fetch_product_types_list(provider="foo_provider")
        mock_discover_product_types.assert_called_once_with(
            self.dag, provider="foo_provider"
        )

    @mock.patch("eodag.api.core.get_ext_product_types_conf", autospec=True)
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.discover_product_types", autospec=True
    )
    def test_fetch_product_types_list_without_ext_conf(
        self, mock_discover_product_types, mock_get_ext_product_types_conf
    ):
        """Core api must not fetch product types list and must discover product types without ext-conf"""
        # check that no provider has already been fetched
        for provider_config in self.dag.providers_config.values():
            self.assertFalse(getattr(provider_config, "product_types_fetched", False))

        # check that without an ext-conf, discover_product_types() is launched for it
        mock_get_ext_product_types_conf.return_value = {}
        self.dag.fetch_product_types_list()
        self.assertEqual(mock_discover_product_types.call_count, 1)

        # check that without an ext-conf, no provider has been fetched
        for provider_config in self.dag.providers_config.values():
            self.assertFalse(getattr(provider_config, "product_types_fetched", False))

    @mock.patch("eodag.api.core.get_ext_product_types_conf", autospec=True)
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.discover_product_types", autospec=True
    )
    def test_fetch_product_types_list_updated_system_conf(
        self, mock_discover_product_types, mock_get_ext_product_types_conf
    ):
        """fetch_product_types_list must launch product types discovery for new system-wide providers"""
        # add a new system-wide provider not listed in ext-conf
        new_default_conf = load_default_config()
        new_default_conf["new_provider"] = new_default_conf["astraea_eod"]

        with mock.patch(
            "eodag.api.core.load_default_config",
            return_value=new_default_conf,
            autospec=True,
        ):
            self.dag = EODataAccessGateway()

            mock_get_ext_product_types_conf.return_value = {}

            # disabled product types discovery
            os.environ["EODAG_EXT_PRODUCT_TYPES_CFG_FILE"] = ""
            self.dag.fetch_product_types_list()
            mock_discover_product_types.assert_not_called()
            os.environ.pop("EODAG_EXT_PRODUCT_TYPES_CFG_FILE")

            # add an empty ext-conf for other providers to prevent them to be fetched
            for provider, provider_config in self.dag.providers_config.items():
                if provider != "new_provider" and hasattr(provider_config, "search"):
                    provider_search_config = provider_config.search
                elif provider != "new_provider" and hasattr(provider_config, "api"):
                    provider_search_config = provider_config.api
                else:
                    continue
                if hasattr(
                    provider_search_config, "discover_product_types"
                ) and provider_search_config.discover_product_types.get(
                    "fetch_url", None
                ):
                    mock_get_ext_product_types_conf.return_value[provider] = {}

            self.dag.fetch_product_types_list()
            mock_discover_product_types.assert_called_once_with(
                self.dag, provider="new_provider"
            )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.discover_product_types", autospec=True
    )
    def test_fetch_product_types_list_disabled(self, mock_discover_product_types):
        """fetch_product_types_list must not launch product types discovery if disabled"""

        # disable product types discovery
        os.environ["EODAG_EXT_PRODUCT_TYPES_CFG_FILE"] = ""

        # default settings
        self.dag.fetch_product_types_list()
        mock_discover_product_types.assert_not_called()

        # only user-defined providers must be fetched
        self.dag.update_providers_config(
            """
            astraea_eod:
                search:
                    discover_product_types:
                        fetch_url: 'http://new-endpoint'
            foo_provider:
                search:
                    type: StacSearch
                    api_endpoint: https://foo.bar/search
                products:
                    GENERIC_PRODUCT_TYPE:
                        productType: '{productType}'
            """
        )
        self.dag.fetch_product_types_list()
        self.assertEqual(mock_discover_product_types.call_count, 2)

    def assertListProductTypesRightStructure(self, structure):
        """Helper method to verify that the structure given is a good result of
        EODataAccessGateway.list_product_types
        """
        self.assertIsInstance(structure, dict)
        self.assertIn("ID", structure)
        self.assertIn("abstract", structure)
        self.assertIn("instrument", structure)
        self.assertIn("platform", structure)
        self.assertIn("platformSerialIdentifier", structure)
        self.assertIn("processingLevel", structure)
        self.assertIn("sensorType", structure)
        assert (
            structure["ID"] in self.SUPPORTED_PRODUCT_TYPES
            or structure["_id"] in self.SUPPORTED_PRODUCT_TYPES
        )

    @mock.patch("eodag.api.core.open_dir", autospec=True)
    @mock.patch("eodag.api.core.exists_in", autospec=True, return_value=True)
    def test_core_object_open_index_if_exists(self, exists_in_mock, open_dir_mock):
        """The core object must use the existing index dir if any"""
        index_dir = os.path.join(self.conf_dir, ".index")
        if not os.path.exists(index_dir):
            makedirs(index_dir)
        EODataAccessGateway()
        open_dir_mock.assert_called_with(index_dir)

    def test_core_object_set_default_locations_config(self):
        """The core object must set the default locations config on instantiation"""
        default_shpfile = os.path.join(
            self.conf_dir, "shp", "ne_110m_admin_0_map_units.shp"
        )
        self.assertIsInstance(self.dag.locations_config, list)
        self.assertEqual(
            self.dag.locations_config,
            [dict(attr="ADM0_A3_US", name="country", path=default_shpfile)],
        )

    def test_core_object_locations_file_not_found(self):
        """The core object must set the locations to an empty list when the file is not found"""
        dag = EODataAccessGateway(locations_conf_path="no_locations.yml")
        self.assertEqual(dag.locations_config, [])

    def test_prune_providers_list(self):
        """Providers needing auth for search but without credentials must be pruned on init"""
        empty_conf_file = resource_filename(
            "eodag", os.path.join("resources", "user_conf_template.yml")
        )
        try:
            # Default conf: no auth needed for search
            dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
            assert not getattr(dag.providers_config["peps"].search, "need_auth", False)

            # auth needed for search without credentials
            os.environ["EODAG__PEPS__SEARCH__NEED_AUTH"] = "true"
            dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
            assert "peps" not in dag.available_providers()

            # auth needed for search with credentials
            os.environ["EODAG__PEPS__SEARCH__NEED_AUTH"] = "true"
            os.environ["EODAG__PEPS__AUTH__CREDENTIALS__USERNAME"] = "foo"
            dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
            assert "peps" in dag.available_providers()
            assert getattr(dag.providers_config["peps"].search, "need_auth", False)

        # Teardown
        finally:
            os.environ.pop("EODAG__PEPS__SEARCH__NEED_AUTH", None)
            os.environ.pop("EODAG__PEPS__AUTH__CREDENTIALS__USERNAME", None)

    def test_prune_providers_list_for_search_without_auth(self):
        """Providers needing auth for search but without auth plugin must be pruned on init"""
        empty_conf_file = resource_filename(
            "eodag", os.path.join("resources", "user_conf_template.yml")
        )
        try:
            # auth needed for search with need_auth but without auth plugin
            os.environ["EODAG__PEPS__SEARCH__NEED_AUTH"] = "true"
            os.environ["EODAG__PEPS__AUTH__CREDENTIALS__USERNAME"] = "foo"
            dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
            delattr(dag.providers_config["peps"], "auth")
            assert "peps" in dag.available_providers()
            assert getattr(dag.providers_config["peps"].search, "need_auth", False)
            assert not hasattr(dag.providers_config["peps"], "auth")

            with self.assertLogs(level="INFO") as cm:
                dag._prune_providers_list()
                self.assertNotIn("peps", dag.providers_config.keys())
                self.assertIn(
                    "peps: provider needing auth for search has been pruned because no auth plugin could be found",
                    str(cm.output),
                )

        # Teardown
        finally:
            os.environ.pop("EODAG__PEPS__SEARCH__NEED_AUTH", None)
            os.environ.pop("EODAG__PEPS__AUTH__CREDENTIALS__USERNAME", None)

    def test_prune_providers_list_without_api_or_search_plugin(self):
        """Providers without api or search plugin must be pruned on init"""
        empty_conf_file = resource_filename(
            "eodag", os.path.join("resources", "user_conf_template.yml")
        )
        dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
        delattr(dag.providers_config["peps"], "search")
        assert "peps" in dag.available_providers()
        assert not hasattr(dag.providers_config["peps"], "api")
        assert not hasattr(dag.providers_config["peps"], "search")

        assert "peps" in dag.available_providers()

        with self.assertLogs(level="INFO") as cm:
            dag._prune_providers_list()
            self.assertNotIn("peps", dag.providers_config.keys())
            self.assertIn(
                "peps: provider has been pruned because no api or search plugin could be found",
                str(cm.output),
            )

    def test_rebuild_index(self):
        """Change product_types_config_md5 and check that whoosh index is rebuilt"""
        index_dir = os.path.join(self.dag.conf_dir, ".index")
        index_dir_mtime = os.path.getmtime(index_dir)
        random_md5 = uuid.uuid4().hex

        self.assertNotEqual(self.dag.product_types_config_md5, random_md5)

        self.dag.product_types_config_md5 = random_md5
        self.dag.build_index()

        # check that index_dir has beeh re-created
        self.assertNotEqual(os.path.getmtime(index_dir), index_dir_mtime)

    def test_get_version(self):
        """Test if the version we get is the current one"""
        version_str = self.dag.get_version()
        self.assertEqual(eodag_version, version_str)

    @mock.patch("eodag.api.core.exists_in", autospec=True)
    def test_build_index_ko(self, exists_in_mock):
        """
        Trying to build index with unsupported pickle version or other reason leads to ValueError
        and may delete the current index to rebuild it
        """
        exists_in_mock.side_effect = ValueError("unsupported pickle protocol")
        index_dir = os.path.join(self.conf_dir, ".index")
        path = Path(index_dir)
        self.assertTrue(path.is_dir())
        last_index_modif_date = os.stat(index_dir).st_atime_ns
        with self.assertLogs(level="DEBUG") as cm:
            self.dag.build_index()
            new_index_modif_date = os.stat(index_dir).st_atime_ns
            self.assertIn(
                f"Need to recreate whoosh .index: '{exists_in_mock.side_effect}'",
                str(cm.output),
            )
            self.assertNotEqual(last_index_modif_date, new_index_modif_date)

        exists_in_mock.side_effect = ValueError("dummy error")
        with self.assertLogs(level="ERROR") as cm_logs:
            with self.assertRaisesRegex(ValueError, "dummy error"):
                self.dag.build_index()
            self.assertIn(
                "Error while opening .index using whoosh, "
                "please report this issue and try to delete",
                str(cm_logs.output),
            )

    def test_set_preferred_provider(self):
        """set_preferred_provider must set the preferred provider with increasing priority"""

        self.assertEqual(self.dag.get_preferred_provider(), ("peps", 1))

        self.assertRaises(
            UnsupportedProvider, self.dag.set_preferred_provider, "unknown"
        )

        self.dag.set_preferred_provider("creodias")
        self.assertEqual(self.dag.get_preferred_provider(), ("creodias", 2))

        self.dag.set_preferred_provider("theia")
        self.assertEqual(self.dag.get_preferred_provider(), ("theia", 3))

        self.dag.set_preferred_provider("creodias")
        self.assertEqual(self.dag.get_preferred_provider(), ("creodias", 4))

    def test_update_providers_config(self):
        """update_providers_config must update providers configuration"""

        new_config = """
            my_new_provider:
                search:
                    type: StacSearch
                    api_endpoint: https://api.my_new_provider/search
                products:
                    GENERIC_PRODUCT_TYPE:
                        productType: '{productType}'
            """
        # add new provider
        self.dag.update_providers_config(new_config)
        self.assertIsInstance(
            self.dag.providers_config["my_new_provider"], ProviderConfig
        )

        self.assertEqual(self.dag.providers_config["my_new_provider"].priority, 0)

        # run a 2nd time: check that it does not raise an error
        self.dag.update_providers_config(new_config)

    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.discover_queryables", autospec=True
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test_list_queryables(
        self, mock_discover_queryables, mock_fetch_product_types_list
    ):
        """list_queryables must return queryables list adapted to provider and product-type"""
        with self.assertRaises(UnsupportedProvider):
            self.dag.list_queryables(provider="not_supported_provider")

        with self.assertRaises(UnsupportedProductType):
            self.dag.list_queryables(product_type="not_supported_product_type")

        queryables_none_none = self.dag.list_queryables()
        expected_result = model_fields_to_annotated_tuple(CommonQueryables.model_fields)
        self.assertEqual(len(queryables_none_none), len(expected_result))
        for key, queryable in queryables_none_none.items():
            # compare obj.__repr__
            self.assertEqual(str(expected_result[key]), str(queryable))

        queryables_peps_none = self.dag.list_queryables(provider="peps")
        expected_longer_result = model_fields_to_annotated_tuple(
            Queryables.model_fields
        )
        self.assertGreater(len(queryables_peps_none), len(queryables_none_none))
        self.assertLess(len(queryables_peps_none), len(expected_longer_result))
        for key, queryable in queryables_peps_none.items():
            # compare obj.__repr__
            self.assertEqual(str(expected_longer_result[key]), str(queryable))

        queryables_peps_s1grd = self.dag.list_queryables(
            provider="peps", product_type="S1_SAR_GRD"
        )
        self.assertGreater(len(queryables_peps_s1grd), len(queryables_none_none))
        self.assertLess(len(queryables_peps_s1grd), len(queryables_peps_none))
        self.assertLess(len(queryables_peps_s1grd), len(expected_longer_result))
        for key, queryable in queryables_peps_s1grd.items():
            # compare obj.__repr__
            self.assertEqual(str(expected_longer_result[key]), str(queryable))

    def test_list_sortables(self):
        """list_sortables must return sortable(s) and its (their) maximum  number dict adapted to provider"""
        # raise an error if the provider is unsupported
        with self.assertRaises(UnsupportedProvider):
            self.dag.list_sortables(provider="not_supported_provider")

        # check if all providers are listed if the method does not have argument
        expected_result = {
            "peps": None,
            "usgs": None,
            "creodias": {
                "sortables": [
                    "startTimeFromAscendingNode",
                    "completionTimeFromAscendingNode",
                    "publicationDate",
                ],
                "max_sort_params": 1,
            },
            "aws_eos": None,
            "theia": None,
            "onda": {
                "sortables": ["startTimeFromAscendingNode", "uid"],
                "max_sort_params": 1,
            },
            "astraea_eod": None,
            "usgs_satapi_aws": None,
            "earth_search": None,
            "earth_search_cog": None,
            "earth_search_gcs": None,
            "ecmwf": None,
            "cop_ads": None,
            "cop_cds": None,
            "sara": {
                "sortables": [
                    "startTimeFromAscendingNode",
                    "completionTimeFromAscendingNode",
                    "sensorMode",
                ],
                "max_sort_params": 1,
            },
            "meteoblue": None,
            "cop_dataspace": {
                "sortables": [
                    "startTimeFromAscendingNode",
                    "completionTimeFromAscendingNode",
                    "publicationDate",
                    "modificationDate",
                ],
                "max_sort_params": 1,
            },
            "planetary_computer": None,
            "hydroweb_next": None,
            "wekeo": None,
            "creodias_s3": None,
        }
        sortables = self.dag.list_sortables()
        self.assertDictEqual(sortables, expected_result)

        # check if only sortables of the provider given in argument are displayed and if they are set to None
        # when the provider does not support the sorting feature
        expected_result = {"peps": None}
        sortables = self.dag.list_sortables(provider="peps")
        self.assertFalse(hasattr(self.dag.providers_config["peps"].search, "sort"))
        self.assertDictEqual(sortables, expected_result)

        # check if sortable parameter(s) and its (their) maximum number of a provider are set
        # to their value when the provider supports the sorting feature and has a maximum number of sortables
        expected_result = {
            "creodias": {
                "sortables": [
                    "startTimeFromAscendingNode",
                    "completionTimeFromAscendingNode",
                    "publicationDate",
                ],
                "max_sort_params": 1,
            }
        }
        sortables = self.dag.list_sortables(provider="creodias")
        self.assertTrue(hasattr(self.dag.providers_config["creodias"].search, "sort"))
        self.assertTrue(
            self.dag.providers_config["creodias"].search.sort.get("max_sort_params")
        )
        self.assertDictEqual(sortables, expected_result)

        # TODO: provider supports the sorting feature and does not have a maximum number of sortables


class TestCoreConfWithEnvVar(TestCoreBase):
    @classmethod
    def setUpClass(cls):
        super(TestCoreConfWithEnvVar, cls).setUpClass()
        cls.dag = EODataAccessGateway()
        # mock os.environ to empty env
        cls.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        cls.mock_os_environ.start()

    @classmethod
    def tearDownClass(cls):
        super(TestCoreConfWithEnvVar, cls).tearDownClass()
        # stop os.environ
        cls.mock_os_environ.stop()

    def test_core_object_prioritize_locations_file_in_envvar(self):
        """The core object must use the locations file pointed by the EODAG_LOCS_CFG_FILE env var"""
        try:
            os.environ["EODAG_LOCS_CFG_FILE"] = os.path.join(
                TEST_RESOURCES_PATH, "file_locations_override.yml"
            )
            dag = EODataAccessGateway()
            self.assertEqual(
                dag.locations_config,
                [dict(attr="dummyattr", name="dummyname", path="dummypath.shp")],
            )
        finally:
            os.environ.pop("EODAG_LOCS_CFG_FILE", None)

    def test_core_object_prioritize_config_file_in_envvar(self):
        """The core object must use the config file pointed by the EODAG_CFG_FILE env var"""
        try:
            os.environ["EODAG_CFG_FILE"] = os.path.join(
                TEST_RESOURCES_PATH, "file_config_override.yml"
            )
            dag = EODataAccessGateway()
            # usgs priority is set to 5 in the test config overrides
            self.assertEqual(dag.get_preferred_provider(), ("usgs", 5))
            # peps outputs prefix is set to /data
            self.assertEqual(
                dag.providers_config["peps"].download.outputs_prefix, "/data"
            )
        finally:
            os.environ.pop("EODAG_CFG_FILE", None)

    def test_core_object_prioritize_providers_file_in_envvar(self):
        """The core object must use the providers conf file pointed by the EODAG_PROVIDERS_CFG_FILE env var"""
        try:
            os.environ["EODAG_PROVIDERS_CFG_FILE"] = os.path.join(
                TEST_RESOURCES_PATH, "file_providers_override.yml"
            )
            dag = EODataAccessGateway()
            # only foo_provider in conf
            self.assertEqual(dag.available_providers(), ["foo_provider"])
            self.assertEqual(
                dag.providers_config["foo_provider"].search.api_endpoint,
                "https://foo.bar/search",
            )
        finally:
            os.environ.pop("EODAG_PROVIDERS_CFG_FILE", None)


class TestCoreInvolvingConfDir(unittest.TestCase):
    def setUp(self):
        super(TestCoreInvolvingConfDir, self).setUp()
        self.dag = EODataAccessGateway()

    def tearDown(self):
        super(TestCoreInvolvingConfDir, self).tearDown()
        for old in glob.glob1(self.dag.conf_dir, "*.old") + glob.glob1(
            self.dag.conf_dir, ".*.old"
        ):
            old_path = os.path.join(self.dag.conf_dir, old)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    shutil.rmtree(old_path)

    def execution_involving_conf_dir(self, inspect=None):
        """Check that the path(s) inspected (str, list) are created after the instantation
        of EODataAccessGateway. If they were already there, rename them (.old), instantiate,
        check, delete the new files, and restore the existing files to there previous name."""
        if inspect is not None:
            if isinstance(inspect, str):
                inspect = [inspect]
            conf_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
            olds = []
            currents = []
            for inspected in inspect:
                old = current = os.path.join(conf_dir, inspected)
                if os.path.exists(current):
                    old = os.path.join(conf_dir, "{}.old".format(inspected))
                    shutil.move(current, old)
                olds.append(old)
                currents.append(current)
            EODataAccessGateway()
            for old, current in zip(olds, currents):
                self.assertTrue(os.path.exists(current))
                if old != current:
                    try:
                        shutil.rmtree(current)
                    except OSError:
                        os.unlink(current)
                    shutil.move(old, current)

    def test_core_object_creates_config_standard_location(self):
        """The core object must create a user config file in standard user config location on instantiation"""
        self.execution_involving_conf_dir(inspect="eodag.yml")

    def test_core_object_creates_index_if_not_exist(self):
        """The core object must create an index in user config directory"""
        self.execution_involving_conf_dir(inspect=".index")

    def test_core_object_creates_locations_standard_location(self):
        """The core object must create a locations config file and a shp dir in standard user config location on instantiation"""  # noqa
        self.execution_involving_conf_dir(inspect=["locations.yml", "shp"])


class TestCoreGeometry(TestCoreBase):
    @classmethod
    def setUpClass(cls):
        super(TestCoreGeometry, cls).setUpClass()
        cls.dag = EODataAccessGateway()

    def test_get_geometry_from_various_no_locations(self):
        """The search geometry can be set from a dict, list, tuple, WKT string or shapely geom"""
        ref_geom_as_wkt = "POLYGON ((0 50, 0 52, 2 52, 2 50, 0 50))"
        ref_geom = wkt.loads(ref_geom_as_wkt)
        # Good dict
        geometry = {
            "lonmin": 0,
            "latmin": 50,
            "lonmax": 2,
            "latmax": 52,
        }
        self.assertEqual(get_geometry_from_various([], geometry=geometry), ref_geom)
        # Bad dict with a missing key
        del geometry["lonmin"]
        self.assertRaises(
            TypeError,
            get_geometry_from_various,
            [],
            geometry=geometry,
        )
        # Tuple
        geometry = (0, 50, 2, 52)
        self.assertEqual(get_geometry_from_various([], geometry=geometry), ref_geom)
        # List
        geometry = list(geometry)
        self.assertEqual(get_geometry_from_various([], geometry=geometry), ref_geom)
        # List without 4 items
        geometry.pop()
        self.assertRaises(
            TypeError,
            get_geometry_from_various,
            [],
            geometry=geometry,
        )
        # WKT
        geometry = ref_geom_as_wkt
        self.assertEqual(get_geometry_from_various([], geometry=geometry), ref_geom)
        # Some other shapely geom
        geometry = LineString([[0, 0], [1, 1]])
        self.assertIsInstance(
            get_geometry_from_various([], geometry=geometry), LineString
        )

    def test_get_geometry_from_various_only_locations(self):
        """The search geometry can be set from a locations config file query"""
        locations_config = self.dag.locations_config
        # No query args
        self.assertIsNone(get_geometry_from_various(locations_config))
        # France
        geom_france = get_geometry_from_various(
            locations_config, locations=dict(country="FRA")
        )
        self.assertIsInstance(geom_france, MultiPolygon)
        self.assertEqual(len(geom_france.geoms), 3)  # France + Guyana + Corsica

    def test_get_geometry_from_various_locations_with_wrong_location_name_in_kwargs(
        self,
    ):
        """The search geometry is world wide if the location name is wrong"""
        locations_config = self.dag.locations_config
        # Bad location name in kwargs
        # 'country' is the expected name here, but kwargs are passed
        # to get_geometry_from_various so we can't detect a bad location name
        self.assertIsNone(
            get_geometry_from_various(locations_config, bad_query_arg="FRA")
        )

    def test_get_geometry_from_various_locations_with_wrong_location_name_in_locations_dict(
        self,
    ):
        """If the location search has a wrong location name then a ValueError must be raised"""
        locations_config = self.dag.locations_config
        # Bad location name in kwargs
        # 'country' is the expected name here, but kwargs are passed
        # to get_geometry_from_various so we can't detect a bad location name
        with self.assertRaisesRegex(ValueError, "bad_query_arg"):
            get_geometry_from_various(
                locations_config, locations=dict(bad_query_arg="FRA")
            )

    def test_get_geometry_from_various_only_locations_regex(self):
        """The search geometry can be set from a locations config file query and a regex"""
        locations_config = self.dag.locations_config
        # Pakistan + Panama (each has a unique polygon) => Multypolygon of len 2
        geom_regex_pa = get_geometry_from_various(
            locations_config, locations=dict(country="PA[A-Z]")
        )
        self.assertIsInstance(geom_regex_pa, MultiPolygon)
        self.assertEqual(len(geom_regex_pa.geoms), 2)

    def test_get_geometry_from_various_locations_no_match_raises_error(self):
        """If the location search doesn't match any of the feature attribute a ValueError must be raised"""
        locations_config = self.dag.locations_config
        with self.assertRaisesRegex(ValueError, "country.*regexmatchingnothing"):
            get_geometry_from_various(
                locations_config, locations=dict(country="regexmatchingnothing")
            )

    def test_get_geometry_from_various_geometry_and_locations(self):
        """The search geometry can be set from a given geometry and a locations config file query"""
        geometry = {
            "lonmin": 20,
            "latmin": 50,
            "lonmax": 22,
            "latmax": 52,
        }
        locations_config = self.dag.locations_config
        geom_combined = get_geometry_from_various(
            locations_config, locations=dict(country="FRA"), geometry=geometry
        )
        self.assertIsInstance(geom_combined, MultiPolygon)
        # France + Guyana + Corsica + somewhere over Poland
        self.assertEqual(len(geom_combined.geoms), 4)
        geometry = {
            "lonmin": 0,
            "latmin": 50,
            "lonmax": 2,
            "latmax": 52,
        }
        geom_combined = get_geometry_from_various(
            locations_config, locations=dict(country="FRA"), geometry=geometry
        )
        self.assertIsInstance(geom_combined, MultiPolygon)
        # The bounding box overlaps with France inland
        self.assertEqual(len(geom_combined.geoms), 3)


class TestCoreSearch(TestCoreBase):
    @classmethod
    def setUpClass(cls):
        super(TestCoreSearch, cls).setUpClass()
        cls.dag = EODataAccessGateway()
        # Get a SearchResult obj with 2 S2_MSI_L1C peps products
        search_results_file = os.path.join(
            TEST_RESOURCES_PATH, "eodag_search_result_peps.geojson"
        )
        with open(search_results_file, encoding="utf-8") as f:
            search_results_geojson = json.load(f)
        cls.search_results = SearchResult.from_geojson(search_results_geojson)
        cls.search_results_size = len(cls.search_results)
        # Change the id of these products, to emulate different products
        search_results_data_2 = copy.deepcopy(cls.search_results.data)
        search_results_data_2[0].properties["id"] = "a"
        search_results_data_2[1].properties["id"] = "b"
        cls.search_results_2 = SearchResult(search_results_data_2)
        cls.search_results_size_2 = len(cls.search_results_2)

    def test_guess_product_type_with_kwargs(self):
        """guess_product_type must return the products matching the given kwargs"""
        kwargs = dict(
            instrument="MSI",
            platform="SENTINEL2",
            platformSerialIdentifier="S2A",
        )
        actual = self.dag.guess_product_type(**kwargs)
        expected = [
            "S2_MSI_L1C",
            "S2_MSI_L2A",
            "S2_MSI_L2AP",
            "S2_MSI_L2A_COG",
            "S2_MSI_L2A_MAJA",
            "S2_MSI_L2B_MAJA_SNOW",
            "S2_MSI_L2B_MAJA_WATER",
            "S2_MSI_L3A_WASP",
            "EEA_DAILY_VI",
        ]
        self.assertEqual(actual, expected)

        # with product type specified
        actual = self.dag.guess_product_type(productType="foo")
        self.assertEqual(actual, ["foo"])

    def test_guess_product_type_without_kwargs(self):
        """guess_product_type must raise an exception when no kwargs are provided"""
        with self.assertRaises(NoMatchingProductType):
            self.dag.guess_product_type()

    def test_guess_product_type_has_no_limit(self):
        """guess_product_type must run a whoosh search without any limit"""
        # Filter that should give more than 10 products referenced in the catalog.
        opt_prods = [
            p
            for p in self.dag.list_product_types(fetch_providers=False)
            if p["sensorType"] == "OPTICAL"
        ]
        if len(opt_prods) <= 10:
            self.skipTest("This test requires that more than 10 products are 'OPTICAL'")
        guesses = self.dag.guess_product_type(
            sensorType="OPTICAL",
        )
        self.assertGreater(len(guesses), 10)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test__prepare_search_no_parameters(self, mock_fetch_product_types_list):
        """_prepare_search must create some kwargs even when no parameter has been provided"""
        _, prepared_search = self.dag._prepare_search()
        expected = {
            "geometry": None,
            "productType": None,
        }
        expected = set(["geometry", "productType"])
        self.assertSetEqual(expected, set(prepared_search))

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test__prepare_search_dates(self, mock_fetch_product_types_list):
        """_prepare_search must handle start & end dates"""
        base = {
            "start": "2020-01-01",
            "end": "2020-02-01",
        }
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(prepared_search["startTimeFromAscendingNode"], base["start"])
        self.assertEqual(
            prepared_search["completionTimeFromAscendingNode"], base["end"]
        )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test__prepare_search_geom(self, mock_fetch_product_types_list):
        """_prepare_search must handle geom, box and bbox"""
        # The default way to provide a geom is through the 'geom' argument.
        base = {"geom": (0, 50, 2, 52)}
        # "geom": "POLYGON ((1 43, 1 44, 2 44, 2 43, 1 43))"
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        # 'box' and 'bbox' are supported for backwards compatibility,
        # The priority is geom > bbox > box
        base = {"box": (0, 50, 2, 52)}
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        base = {"bbox": (0, 50, 2, 52)}
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        base = {
            "geom": "POLYGON ((1 43, 1 44, 2 44, 2 43, 1 43))",
            "bbox": (0, 50, 2, 52),
            "box": (0, 50, 1, 51),
        }
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        self.assertNotIn("bbox", prepared_search)
        self.assertNotIn("bbox", prepared_search)
        self.assertIsInstance(prepared_search["geometry"], Polygon)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test__prepare_search_locations(self, mock_fetch_product_types_list):
        """_prepare_search must handle a location search"""
        # When locations where introduced they could be passed
        # as regular kwargs. The new and recommended way to provide
        # them is through the 'locations' parameter.
        base = {"locations": {"country": "FRA"}}
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)

        # TODO: Remove this when support for locations kwarg is dropped.
        base = {"country": "FRA"}
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        self.assertNotIn("country", prepared_search)

    def test__prepare_search_product_type_provided(self):
        """_prepare_search must handle when a product type is given"""
        base = {"productType": "S2_MSI_L1C"}
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(prepared_search["productType"], base["productType"])

    def test__prepare_search_product_type_guess_it(self):
        """_prepare_search must guess a product type when required to"""
        # Uses guess_product_type to find the product matching
        # the best the given params.
        base = dict(
            instrument="MSI",
            platform="SENTINEL2",
            platformSerialIdentifier="S2A",
        )
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(prepared_search["productType"], "S2_MSI_L1C")

    def test__prepare_search_remove_guess_kwargs(self):
        """_prepare_search must remove the guess kwargs"""
        # Uses guess_product_type to find the product matching
        # the best the given params.
        base = dict(
            instrument="MSI",
            platform="SENTINEL2",
            platformSerialIdentifier="S2A",
        )
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(len(base.keys() & prepared_search.keys()), 0)

    def test__prepare_search_with_id(self):
        """_prepare_search must handle a search by id"""
        base = {"id": "dummy-id", "provider": "creodias"}
        _, prepared_search = self.dag._prepare_search(**base)
        expected = {"id": "dummy-id"}
        self.assertDictEqual(expected, prepared_search)

    def test__prepare_search_preserve_additional_kwargs(self):
        """_prepare_search must preserve additional kwargs"""
        base = {
            "productType": "S2_MSI_L1C",
            "cloudCover": 10,
        }
        _, prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(prepared_search["productType"], base["productType"])
        self.assertEqual(prepared_search["cloudCover"], base["cloudCover"])

    def test__prepare_search_search_plugin_has_known_product_properties(self):
        """_prepare_search must attach the product properties to the search plugin"""
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("peps")
            base = {"productType": "S2_MSI_L1C"}
            search_plugins, _ = self.dag._prepare_search(**base)
            # Just check that the title has been set correctly. There are more (e.g.
            # abstract, platform, etc.) but this is sufficient to check that the
            # product_type_config dict has been created and populated.
            self.assertEqual(
                search_plugins[0].config.product_type_config["title"],
                "SENTINEL2 Level-1C",
            )
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test__prepare_search_search_plugin_has_generic_product_properties(
        self, mock_fetch_product_types_list
    ):
        """_prepare_search must be able to attach the generic product properties to the search plugin"""
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("peps")
            base = {"productType": "product_unknown_to_eodag"}
            search_plugins, _ = self.dag._prepare_search(**base)
            # product_type_config is still created if the product is not known to eodag
            # however it contains no data.
            self.assertIsNone(
                search_plugins[0].config.product_type_config["title"],
            )
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

    def test__prepare_search_peps_plugins_product_available(self):
        """_prepare_search must return the search plugins when productType is defined"""
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("peps")
            base = {"productType": "S2_MSI_L1C"}
            search_plugins, _ = self.dag._prepare_search(**base)
            self.assertEqual(search_plugins[0].provider, "peps")
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

    def test__prepare_search_peps_plugins_product_available_with_alias(self):
        """_prepare_search must return the search plugins when productType is defined and alias is used"""
        products = self.dag.product_types_config
        products["S2_MSI_L1C"]["alias"] = "S2_MSI_ALIAS"
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("peps")
            base = {"productType": "S2_MSI_ALIAS"}
            search_plugins, _ = self.dag._prepare_search(**base)
            self.assertEqual(search_plugins[0].provider, "peps")
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

    def test__prepare_search_no_plugins_when_search_by_id(self):
        """_prepare_search must not return the search and auth plugins for a search by id"""
        base = {"id": "some_id", "provider": "some_provider"}
        search_plugins, prepared_search = self.dag._prepare_search(**base)
        self.assertListEqual(search_plugins, [])
        self.assertNotIn("auth", prepared_search)

    def test__prepare_search_peps_plugins_product_not_available(self):
        """_prepare_search can use another search plugin than the preferred one"""
        # Document a special behaviour whereby the search and auth plugins don't
        # correspond to the preferred one. This occurs whenever the searched product
        # isn't available for the preferred provider but is made available by  another
        # one. In that case peps provides it and happens to be the first one on the list
        # of providers that make it available.
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("theia")
            base = {"productType": "S2_MSI_L1C"}
            search_plugins, _ = self.dag._prepare_search(**base)
            self.assertEqual(search_plugins[0].provider, "peps")
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test__prepare_search_unknown_product_type(self, mock_fetch_product_types_list):
        """_prepare_search must fetch product types if product_type is unknown"""
        self.dag._prepare_search(product_type="foo")
        mock_fetch_product_types_list.assert_called_once_with(self.dag)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway._do_search",
        autospec=True,
        return_value=([mock.Mock()], 1),
    )
    @mock.patch("eodag.plugins.manager.PluginManager.get_auth_plugin", autospec=True)
    @mock.patch(
        "eodag.plugins.manager.PluginManager.get_search_plugins",
        autospec=True,
        return_value=[mock.Mock()],
    )
    def test__search_by_id(
        self, mock_get_search_plugins, mock_get_auth_plugin, mock__do_search
    ):
        """_search_by_id must filter search plugins using given kwargs, clear plugin and perform search"""

        found = self.dag._search_by_id(uid="foo", productType="bar", provider="baz")

        from eodag.utils.logging import get_logging_verbose

        _ = get_logging_verbose()
        # get_search_plugins
        mock_get_search_plugins.assert_called_once_with(
            self.dag._plugins_manager, product_type="bar", provider="baz"
        )

        # search plugin clear
        mock_get_search_plugins.return_value[0].clear.assert_called_once()

        # _do_search returns 1 product
        mock__do_search.assert_called_once_with(
            self.dag,
            mock_get_search_plugins.return_value[0],
            id="foo",
            productType="bar",
        )
        self.assertEqual(found, mock__do_search.return_value)

        mock__do_search.reset_mock()
        # return None if more than 1 product is found
        m = mock.MagicMock()
        p = EOProduct(
            "peps", {"id": "a", "geometry": {"type": "Point", "coordinates": [1, 1]}}
        )
        m.__len__.return_value = 2
        m.__iter__.return_value = [p, p]
        mock__do_search.return_value = (m, 2)
        with self.assertLogs(level="INFO") as cm:
            found = self.dag._search_by_id(uid="foo", productType="bar", provider="baz")
            self.assertEqual(found, (SearchResult([]), 0))
            self.assertIn("Several products found for this id", str(cm.output))

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_support_itemsperpage_higher_than_maximum(self, search_plugin):
        """_do_search must create a count query by default"""
        search_plugin.provider = "peps"
        search_plugin.query.return_value = (
            self.search_results.data,  # a list must be returned by .query
            self.search_results_size,
        )

        class DummyConfig:
            pagination = {"max_items_per_page": 1}

        search_plugin.config = DummyConfig()
        sr, estimate = self.dag._do_search(
            search_plugin=search_plugin,
            items_per_page=2,
        )
        self.assertIsInstance(sr, SearchResult)
        self.assertEqual(len(sr), self.search_results_size)
        self.assertEqual(estimate, self.search_results_size)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_counts_by_default(self, search_plugin):
        """_do_search must create a count query by default"""
        search_plugin.provider = "peps"
        search_plugin.query.return_value = (
            self.search_results.data,  # a list must be returned by .query
            self.search_results_size,
        )

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        sr, estimate = self.dag._do_search(search_plugin=search_plugin)
        self.assertIsInstance(sr, SearchResult)
        self.assertEqual(len(sr), self.search_results_size)
        self.assertEqual(estimate, self.search_results_size)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_without_count(self, search_plugin):
        """_do_search must be able to create a query without a count"""
        search_plugin.provider = "peps"
        search_plugin.query.return_value = (
            self.search_results.data,
            None,  # .query must return None if count is False
        )

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        sr, estimate = self.dag._do_search(search_plugin=search_plugin, count=False)
        self.assertIsNone(estimate)
        self.assertEqual(len(sr), self.search_results_size)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_paginated_handle_no_count_returned(self, search_plugin):
        """_do_search must provide a best estimate when a provider doesn't return a count"""
        search_plugin.provider = "peps"
        # If the provider doesn't return a count, .query returns 0
        search_plugin.query.return_value = (self.search_results.data, 0)

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        page = 4
        sr, estimate = self.dag._do_search(
            search_plugin=search_plugin,
            page=page,
            items_per_page=2,
        )
        self.assertEqual(len(sr), self.search_results_size)
        # The count guess is: page * number_of_products_returned
        self.assertEqual(estimate, page * self.search_results_size)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_paginated_handle_fuzzy_count(self, search_plugin):
        """_do_search must provide a best estimate when a provider returns a fuzzy count"""
        search_plugin.provider = "peps"
        search_plugin.query.return_value = (
            self.search_results.data * 4,  # 8 products returned
            22,  # fuzzy number, less than the real total count
        )

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        page = 4
        items_per_page = 10
        sr, estimate = self.dag._do_search(
            search_plugin=search_plugin,
            page=page,
            items_per_page=items_per_page,
        )
        # At page 4 with 10 items_per_page we should have a count of at least 30
        # products available. However the provider returned 22. We know it's wrong.
        # So we update the count with our current knowledge: 30 + 8
        # Note that this estimate could still be largely inferior to the real total
        # count.
        expected_estimate = items_per_page * (page - 1) + len(sr)
        self.assertEqual(len(sr), 8)
        self.assertEqual(estimate, expected_estimate)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_paginated_handle_null_count(self, search_plugin):
        """_do_search must provide a best estimate when a provider returns a null count"""
        # TODO: check the underlying implementation, it doesn't make so much sense since
        # this case is already covered with nb_res = len(res) * page. This one uses
        # nb_res = items_per_page * (page - 1) whick actually makes more sense. Choose
        # one of them.
        search_plugin.provider = "peps"
        search_plugin.query.return_value = ([], 0)

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        page = 4
        items_per_page = 10
        sr, estimate = self.dag._do_search(
            search_plugin=search_plugin,
            page=page,
            items_per_page=items_per_page,
        )
        expected_estimate = items_per_page * (page - 1)
        self.assertEqual(len(sr), 0)
        self.assertEqual(estimate, expected_estimate)

    def test__do_search_does_not_raise_by_default(self):
        """_do_search must not raise any error by default"""
        # provider attribute required internally by __do_search for logging purposes.
        class DummyConfig:
            pagination = {}

        class DummySearchPlugin:
            provider = "peps"
            config = DummyConfig()

        sr, estimate = self.dag._do_search(search_plugin=DummySearchPlugin())
        self.assertIsInstance(sr, SearchResult)
        self.assertEqual(len(sr), 0)
        self.assertEqual(estimate, 0)

    def test__do_search_can_raise_errors(self):
        """_do_search must not raise errors if raise_errors=True"""

        class DummySearchPlugin:
            provider = "peps"

        # AttributeError raised when .query is tried to be accessed on the dummy plugin.
        with self.assertRaises(AttributeError):
            self.dag._do_search(search_plugin=DummySearchPlugin(), raise_errors=True)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_query_products_must_be_a_list(self, search_plugin):
        """_do_search expects that each search plugin returns a list of products."""
        search_plugin.provider = "peps"
        search_plugin.query.return_value = (
            self.search_results,  # This is not a list but a SearchResult
            self.search_results_size,
        )

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        with self.assertRaises(PluginImplementationError):
            self.dag._do_search(search_plugin=search_plugin, raise_errors=True)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_register_downloader_if_search_intersection(self, search_plugin):
        """_do_search must register each product's downloader if search_intersection is not None"""
        search_plugin.provider = "peps"
        search_plugin.query.return_value = (
            self.search_results.data,
            self.search_results_size,
        )

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        sr, _ = self.dag._do_search(search_plugin=search_plugin)
        for product in sr:
            self.assertIsNotNone(product.downloader)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_doest_not_register_downloader_if_no_search_intersection(
        self, search_plugin
    ):
        """_do_search must not register downloaders if search_intersection is None"""

        class DummyProduct:
            seach_intersecion = None

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        search_plugin.provider = "peps"
        search_plugin.query.return_value = ([DummyProduct(), DummyProduct()], 2)
        sr, _ = self.dag._do_search(search_plugin=search_plugin)
        for product in sr:
            self.assertIsNone(product.downloader)

    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_search_iter_page_returns_iterator(self, search_plugin, prepare_seach):
        """search_iter_page must return an iterator"""
        search_plugin.provider = "peps"
        search_plugin.query.side_effect = [
            (self.search_results.data, None),
            (self.search_results_2.data, None),
        ]

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        prepare_seach.return_value = ([search_plugin], {})
        page_iterator = self.dag.search_iter_page_plugin(
            items_per_page=2, search_plugin=search_plugin
        )
        first_result_page = next(page_iterator)
        self.assertIsInstance(first_result_page, SearchResult)
        self.assertEqual(len(first_result_page), self.search_results_size)
        second_result_page = next(page_iterator)
        self.assertIsInstance(second_result_page, SearchResult)
        self.assertEqual(len(second_result_page), self.search_results_size_2)

    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_search_iter_page_exhaust_get_all_pages_and_quit_early(
        self, search_plugin, prepare_seach
    ):
        """search_iter_page must stop as soon as less than items_per_page products were retrieved"""
        search_plugin.provider = "peps"
        search_plugin.query.side_effect = [
            (self.search_results.data, None),
            ([self.search_results_2.data[0]], None),
        ]

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        prepare_seach.return_value = ([search_plugin], {})
        page_iterator = self.dag.search_iter_page_plugin(
            items_per_page=2, search_plugin=search_plugin
        )
        all_page_results = list(page_iterator)
        self.assertEqual(len(all_page_results), 2)
        self.assertIsInstance(all_page_results[0], SearchResult)

    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_search_iter_page_exhaust_get_all_pages_no_products_last_page(
        self, search_plugin, prepare_seach
    ):
        """search_iter_page must stop if the page doesn't return any product"""
        search_plugin.provider = "peps"
        search_plugin.query.side_effect = [
            (self.search_results.data, None),
            (self.search_results_2.data, None),
            ([], None),
        ]

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        prepare_seach.return_value = ([search_plugin], {})
        page_iterator = self.dag.search_iter_page_plugin(
            items_per_page=2, search_plugin=search_plugin
        )
        all_page_results = list(page_iterator)
        self.assertEqual(len(all_page_results), 2)
        self.assertIsInstance(all_page_results[0], SearchResult)

    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_search_iter_page_does_not_handle_query_errors(
        self, search_plugin, prepare_seach
    ):
        """search_iter_page must propagate errors"""
        search_plugin.provider = "peps"
        search_plugin.query.side_effect = AttributeError()
        page_iterator = self.dag.search_iter_page_plugin(search_plugin=search_plugin)
        with self.assertRaises(AttributeError):
            next(page_iterator)

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    def test_search_iter_page_must_reset_next_attrs_if_next_mechanism(
        self, normalize_results, _request
    ):
        """search_iter_page must reset the search plugin if the next mechanism is used"""
        # More specifically: next_page_url must be None and
        # config.pagination["next_page_url_tpl"] must be equal to its original value.
        _request.return_value.json.return_value = {
            "features": [],
            "links": [{"rel": "next", "href": "url/to/next/page"}],
        }

        p1 = EOProduct("dummy", dict(geometry="POINT (0 0)", id="1"))
        p1.search_intersection = None
        p2 = EOProduct("dummy", dict(geometry="POINT (0 0)", id="2"))
        p2.search_intersection = None
        normalize_results.side_effect = [[p1], [p2]]
        dag = EODataAccessGateway()
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_url_tpl: 'dummy_next_page_url_tpl'
                    next_page_url_key_path: '$.links[?(@.rel="next")].href'
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    productType: '{productType}'
        """
        dag.update_providers_config(dummy_provider_config)
        dag.set_preferred_provider("dummy_provider")

        search_plugin = next(
            dag._plugins_manager.get_search_plugins(product_type="S2_MSI_L1C")
        )
        self.assertIsNone(search_plugin.next_page_url)
        self.assertEqual(
            search_plugin.config.pagination["next_page_url_tpl"],
            "dummy_next_page_url_tpl",
        )

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    def test_search_sort_by(self, mock_normalize_results, mock__request):
        """search must sort results by sorting parameter(s) in their sorting order
        from the "sortBy" argument or by default sorting parameters if exist"""
        mock__request.return_value.json.return_value = {
            "properties": {"totalResults": 2},
            "features": [],
            "links": [{"rel": "next", "href": "url/to/next/page"}],
        }

        p1 = EOProduct(
            "dummy", dict(geometry="POINT (0 0)", id="1", eodagSortParam="1")
        )
        p1.search_intersection = None
        p2 = EOProduct(
            "dummy", dict(geometry="POINT (0 0)", id="2", eodagSortParam="2")
        )
        p2.search_intersection = None
        mock_normalize_results.return_value = [p2, p1]

        dag = EODataAccessGateway()
        # sort by a sorting parameter and a sorting order from "sortBy" argument
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_url_tpl: 'dummy_next_page_url_tpl{sort_by}'
                    total_items_nb_key_path: '$.properties.totalResults'
                sort:
                    sort_url_tpl: '&sortParam={sort_param}&sortOrder={sort_order}'
                    sort_by_mapping:
                        eodagSortParam: providerSortParam
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    productType: '{productType}'
        """
        dag.update_providers_config(dummy_provider_config)

        dag.search(
            provider="dummy_provider",
            productType="S2_MSI_L1C",
            sortBy=[("eodagSortParam", "DESC")],
        )

        self.assertIn(
            "&sortParam=providerSortParam&sortOrder=desc",
            mock__request.call_args[0][1],
        )

        # TODO: sort by default sorting parameter and sorting order

    def test_search_sort_by_errors(self):
        """search used with "sortBy" argument must raise errors if the argument is incorrect or if the provider does
        not support a maximum number of sorting parameter, one sorting parameter or the sorting feature"""
        dag = EODataAccessGateway()
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_url_tpl: '{url}?{search}{sort_by}&maxRecords={items_per_page}&page={page}&exactCount=1'
                    total_items_nb_key_path: '$.properties.totalResults'
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    productType: '{productType}'
        """
        dag.update_providers_config(dummy_provider_config)
        # raise an error with a provider which does not support sorting feature
        with self.assertLogs(level="ERROR") as cm_logs:
            dag.search(
                provider="dummy_provider",
                productType="S2_MSI_L1C",
                sortBy=[("eodagSortParam", "ASC")],
            )
            self.assertIn(
                "dummy_provider does not support sorting feature", str(cm_logs.output)
            )

        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_url_tpl: '{url}?{search}{sort_by}&maxRecords={items_per_page}&page={page}&exactCount=1'
                    total_items_nb_key_path: '$.properties.totalResults'
                sort:
                    sort_url_tpl: '&sortParam={sort_param}&sortOrder={sort_order}'
                    sort_by_mapping:
                        eodagSortParam: providerSortParam
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    productType: '{productType}'
        """
        dag.update_providers_config(dummy_provider_config)
        # raise an error with a parameter not sortable with a provider
        with self.assertLogs(level="ERROR") as cm_logs:
            dag.search(
                provider="dummy_provider",
                productType="S2_MSI_L1C",
                sortBy=[("otherEodagSortParam", "ASC")],
            )
            self.assertIn(
                "\\'otherEodagSortParam\\' parameter is not sortable with dummy_provider. "
                "Here is the list of sortable parameter(s) with dummy_provider: eodagSortParam",
                str(cm_logs.output),
            )
        # raise an error with a sorting order called with different values for a same sorting parameter
        with self.assertLogs(level="ERROR") as cm_logs:
            dag.search(
                provider="dummy_provider",
                productType="S2_MSI_L1C",
                sortBy=[("eodagSortParam", "ASC"), ("eodagSortParam", "DESC")],
            )
            self.assertIn(
                "\\'eodagSortParam\\' parameter is called several times to sort results with different sorting "
                "orders. Please set it to only one (\\'ASC\\' (ASCENDING) or \\'DESC\\' (DESCENDING))",
                str(cm_logs.output),
            )

        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_url_tpl: '{url}?{search}{sort_by}&maxRecords={items_per_page}&page={page}&exactCount=1'
                    total_items_nb_key_path: '$.properties.totalResults'
                sort:
                    sort_url_tpl: '&sortParam={sort_param}&sortOrder={sort_order}'
                    sort_by_mapping:
                        eodagSortParam: providerSortParam
                        otherEodagSortParam: otherProviderSortParam
                    max_sort_params: 1
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    productType: '{productType}'
        """
        dag.update_providers_config(dummy_provider_config)
        # raise an error with more sorting parameters than supported by the provider
        with self.assertLogs(level="ERROR") as cm_logs:
            dag.search(
                provider="dummy_provider",
                productType="S2_MSI_L1C",
                sortBy=[("eodagSortParam", "ASC"), ("otherEodagSortParam", "ASC")],
            )
            self.assertIn(
                "Search results can be sorted by only 1 parameter(s) with dummy_provider",
                str(cm_logs.output),
            )

    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_search_all_must_collect_them_all(self, search_plugin, prepare_seach):
        """search_all must return all the products available"""
        search_plugin.provider = "peps"
        search_plugin.query.side_effect = [
            (self.search_results.data, None),
            ([self.search_results_2.data[0]], None),
        ]

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        # Infinite generator here because passing directly the dict to
        # prepare_search.return_value (or side_effect) didn't work. One function
        # would do a dict.pop("search_plugin") that would remove the item from the
        # mocked return value. Later calls would then break
        def yield_search_plugin():
            while True:
                yield ([search_plugin], {})

        prepare_seach.side_effect = yield_search_plugin()
        all_results = self.dag.search_all(items_per_page=2)
        self.assertIsInstance(all_results, SearchResult)
        self.assertEqual(len(all_results), 3)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.search_iter_page_plugin", autospec=True
    )
    def test_search_all_use_max_items_per_page(self, mocked_search_iter_page):
        """search_all must use the configured parameter max_items_per_page if available"""
        dag = EODataAccessGateway()
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    max_items_per_page: 2
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    productType: '{productType}'
        """
        mocked_search_iter_page.return_value = (self.search_results for _ in range(1))
        dag.update_providers_config(dummy_provider_config)
        dag.set_preferred_provider("dummy_provider")
        dag.search_all(productType="S2_MSI_L1C")
        self.assertEqual(mocked_search_iter_page.call_args[1]["items_per_page"], 2)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.search_iter_page_plugin", autospec=True
    )
    def test_search_all_use_default_value(self, mocked_search_iter_page):
        """search_all must use the DEFAULT_MAX_ITEMS_PER_PAGE if the provider's one wasn't configured"""
        dag = EODataAccessGateway()
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    productType: '{productType}'
        """
        mocked_search_iter_page.return_value = (self.search_results for _ in range(1))
        dag.update_providers_config(dummy_provider_config)
        dag.set_preferred_provider("dummy_provider")
        dag.search_all(productType="S2_MSI_L1C")
        self.assertEqual(
            mocked_search_iter_page.call_args[1]["items_per_page"],
            DEFAULT_MAX_ITEMS_PER_PAGE,
        )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.search_iter_page_plugin", autospec=True
    )
    def test_search_all_user_items_per_page(self, mocked_search_iter_page):
        """search_all must use the value of items_per_page provided by the user"""
        dag = EODataAccessGateway()
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    productType: '{productType}'
        """
        mocked_search_iter_page.return_value = (self.search_results for _ in range(1))
        dag.update_providers_config(dummy_provider_config)
        dag.set_preferred_provider("dummy_provider")
        dag.search_all(productType="S2_MSI_L1C", items_per_page=7)
        self.assertEqual(mocked_search_iter_page.call_args[1]["items_per_page"], 7)

    @unittest.skip("Disable until fixed")
    def test_search_all_request_error(self):
        """search_all must stop iteration and move to next provider when error occurs"""

        product_type = "S2_MSI_L1C"
        dag = EODataAccessGateway()

        for plugin in dag._plugins_manager.get_search_plugins(
            product_type=product_type
        ):
            plugin.query = mock.MagicMock()
            plugin.query.side_effect = RequestError

        dag.search_all(productType="S2_MSI_L1C")

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.search_iter_page_plugin", autospec=True
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test_search_all_unknown_product_type(
        self, mock_fetch_product_types_list, mock_search_iter_page_plugin
    ):
        """search_all must fetch product types if product_type is unknown"""
        self.dag.search_all(productType="foo")
        mock_fetch_product_types_list.assert_called_with(self.dag)
        mock_search_iter_page_plugin.assert_called_once()


class TestCoreDownload(TestCoreBase):
    @classmethod
    def setUpClass(cls):
        super(TestCoreDownload, cls).setUpClass()
        cls.dag = EODataAccessGateway()

    def test_download_local_product(self):
        """download must skip local products"""
        product = EOProduct("dummy", dict(geometry="POINT (0 0)", id="dummy_product"))

        product.location = "file:///some/path"
        with self.assertLogs(level="INFO") as cm:
            self.dag.download(product)
            self.assertIn("Local product detected. Download skipped", str(cm.output))

        product.location = "file:/some/path"
        with self.assertLogs(level="INFO") as cm:
            self.dag.download(product)
            self.assertIn("Local product detected. Download skipped", str(cm.output))

        product.location = "file:///c:/some/path"
        with self.assertLogs(level="INFO") as cm:
            self.dag.download(product)
            self.assertIn("Local product detected. Download skipped", str(cm.output))

        product.location = "file:/c:/some/path"
        with self.assertLogs(level="INFO") as cm:
            self.dag.download(product)
            self.assertIn("Local product detected. Download skipped", str(cm.output))


class TestCoreProductAlias(TestCoreBase):
    @classmethod
    def setUpClass(cls):
        super(TestCoreProductAlias, cls).setUpClass()
        cls.dag = EODataAccessGateway()
        products = cls.dag.product_types_config
        products["S2_MSI_L1C"]["alias"] = "S2_MSI_ALIAS"

    def test_get_alias_from_product_type(self):
        # return product alias
        self.assertEqual(
            "S2_MSI_ALIAS", self.dag.get_alias_from_product_type("S2_MSI_L1C")
        )
        # product type without alias
        self.assertEqual(
            "S1_SAR_GRD", self.dag.get_alias_from_product_type("S1_SAR_GRD")
        )
        # not existing product type
        with self.assertRaises(NoMatchingProductType):
            self.dag.get_alias_from_product_type("JUST_A_TYPE")

    def test_get_product_type_from_alias(self):
        # return product id
        self.assertEqual(
            "S2_MSI_L1C", self.dag.get_product_type_from_alias("S2_MSI_ALIAS")
        )
        # product type without alias
        self.assertEqual(
            "S1_SAR_GRD", self.dag.get_product_type_from_alias("S1_SAR_GRD")
        )
        # not existing product type
        with self.assertRaises(NoMatchingProductType):
            self.dag.get_product_type_from_alias("JUST_A_TYPE")
