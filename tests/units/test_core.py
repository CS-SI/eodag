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
import tempfile
import unittest
from importlib.resources import files as res_files
from tempfile import TemporaryDirectory

import yaml
from lxml import html
from pydantic import ValidationError
from shapely import wkt
from shapely.geometry import LineString, MultiPolygon, Polygon

from eodag import __version__ as eodag_version
from eodag.types.queryables import QueryablesDict
from eodag.utils import GENERIC_PRODUCT_TYPE, cached_yaml_load_all
from tests import TEST_RESOURCES_PATH
from tests.context import (
    DEFAULT_ITEMS_PER_PAGE,
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
    model_fields_to_annotated,
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
        "AERIS_IAGOS": ["dedl"],
        "AG_ERA5": ["cop_cds", "wekeo_ecmwf"],
        "CAMS_GAC_FORECAST": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CAMS_EU_AIR_QUALITY_FORECAST": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CAMS_GFE_GFAS": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CAMS_GRF": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CAMS_GRF_AUX": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CAMS_SOLAR_RADIATION": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CAMS_GREENHOUSE_EGG4_MONTHLY": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CAMS_GREENHOUSE_EGG4": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CAMS_GREENHOUSE_INVERSION": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CAMS_GLOBAL_EMISSIONS": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CAMS_EAC4": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CAMS_EAC4_MONTHLY": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CAMS_EU_AIR_QUALITY_RE": ["cop_ads", "dedl", "wekeo_ecmwf"],
        "CBERS4_AWFI_L2": ["aws_eos"],
        "CBERS4_AWFI_L4": ["aws_eos"],
        "CBERS4_MUX_L2": ["aws_eos"],
        "CBERS4_MUX_L4": ["aws_eos"],
        "CBERS4_PAN10M_L2": ["aws_eos"],
        "CBERS4_PAN10M_L4": ["aws_eos"],
        "CBERS4_PAN5M_L2": ["aws_eos"],
        "CBERS4_PAN5M_L4": ["aws_eos"],
        "CLMS_CORINE": ["dedl", "wekeo_main"],
        "CLMS_GLO_DMP_333M": ["dedl", "wekeo_main"],
        "CLMS_GLO_FAPAR_333M": ["dedl", "wekeo_main"],
        "CLMS_GLO_FCOVER_333M": ["dedl", "wekeo_main"],
        "CLMS_GLO_GDMP_333M": ["dedl", "wekeo_main"],
        "CLMS_GLO_LAI_333M": ["dedl", "wekeo_main"],
        "CLMS_GLO_NDVI_1KM_LTS": ["dedl", "wekeo_main"],
        "CLMS_GLO_NDVI_333M": ["dedl", "wekeo_main"],
        "COP_DEM_GLO30_DGED": [
            "creodias",
            "creodias_s3",
            "dedl",
            "earth_search",
            "wekeo_main",
        ],
        "COP_DEM_GLO30_DTED": ["creodias", "creodias_s3", "dedl", "wekeo_main"],
        "COP_DEM_GLO90_DGED": [
            "creodias",
            "creodias_s3",
            "dedl",
            "earth_search",
            "wekeo_main",
        ],
        "COP_DEM_GLO90_DTED": ["creodias", "creodias_s3", "dedl", "wekeo_main"],
        "DT_EXTREMES": ["dedl", "dedt_lumi"],
        "DT_CLIMATE_ADAPTATION": ["dedl", "dedt_lumi"],
        "EEA_DAILY_VI": ["dedl", "wekeo_main"],
        "EFAS_FORECAST": ["cop_ewds", "dedl"],
        "EFAS_HISTORICAL": ["cop_ewds", "dedl"],
        "EFAS_REFORECAST": ["cop_ewds", "dedl"],
        "EFAS_SEASONAL": ["cop_ewds", "dedl"],
        "EFAS_SEASONAL_REFORECAST": ["cop_ewds", "dedl"],
        "ERA5_LAND": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "ERA5_LAND_MONTHLY": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "ERA5_PL": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "ERA5_PL_MONTHLY": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "ERA5_SL": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "ERA5_SL_MONTHLY": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "EUSTAT_AVAILABLE_BEDS_HOSPITALS_NUTS2": ["dedl"],
        "EUSTAT_BATHING_SITES_WATER_QUALITY": ["dedl"],
        "EUSTAT_GREENHOUSE_GAS_EMISSION_AGRICULTURE": ["dedl"],
        "EUSTAT_POP_AGE_GROUP_SEX_NUTS3": ["dedl"],
        "EUSTAT_POP_AGE_SEX_NUTS2": ["dedl"],
        "EUSTAT_POP_CHANGE_DEMO_BALANCE_CRUDE_RATES_NUTS3": ["dedl"],
        "EUSTAT_POP_DENSITY_NUTS3": ["dedl"],
        "EUSTAT_SHARE_ENERGY_FROM_RENEWABLE": ["dedl"],
        "EUSTAT_SOIL_SEALING_INDEX": ["dedl"],
        "EUSTAT_SURFACE_TERRESTRIAL_PROTECTED_AREAS": ["dedl"],
        "FIRE_HISTORICAL": ["cop_ewds", "dedl", "wekeo_ecmwf"],
        "FIRE_SEASONAL": ["cop_ewds"],
        "GLACIERS_DIST_RANDOLPH": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "GLOFAS_FORECAST": ["cop_ewds", "dedl"],
        "GLOFAS_HISTORICAL": ["cop_ewds", "dedl"],
        "GLOFAS_REFORECAST": ["cop_ewds", "dedl"],
        "GLOFAS_SEASONAL": ["cop_ewds", "dedl"],
        "GLOFAS_SEASONAL_REFORECAST": ["cop_ewds", "dedl"],
        "GRIDDED_GLACIERS_MASS_CHANGE": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "GSW_CHANGE": ["dedl"],
        "GSW_EXTENT": ["dedl"],
        "GSW_OCCURRENCE": ["dedl"],
        "GSW_RECURRENCE": ["dedl"],
        "GSW_SEASONALITY": ["dedl"],
        "GSW_TRANSITIONS": ["dedl"],
        "ISIMIP_CLIMATE_FORCING_ISIMIP3B": ["dedl"],
        "ISIMIP_SOCIO_ECONOMIC_FORCING_ISIMIP3B": ["dedl"],
        "L8_OLI_TIRS_C1L1": ["aws_eos", "earth_search_gcs"],
        "LANDSAT_C2L1": [
            "dedl",
            "planetary_computer",
            "usgs",
            "usgs_satapi_aws",
        ],
        "LANDSAT_C2L2": ["dedl", "earth_search", "planetary_computer", "usgs"],
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
        "METOP_AMSU_L1": ["dedl", "eumetsat_ds"],
        "METOP_ASCSZF1B": ["dedl", "eumetsat_ds"],
        "METOP_ASCSZFR02": ["dedl", "eumetsat_ds"],
        "METOP_ASCSZO1B": ["dedl", "eumetsat_ds"],
        "METOP_ASCSZOR02": ["dedl", "eumetsat_ds"],
        "METOP_ASCSZR1B": ["dedl", "eumetsat_ds"],
        "METOP_ASCSZRR02": ["dedl", "eumetsat_ds"],
        "METOP_AVHRRL1": ["dedl", "eumetsat_ds"],
        "METOP_AVHRRGACR02": ["dedl", "eumetsat_ds"],
        "METOP_GLB_SST_NC": ["dedl", "eumetsat_ds"],
        "METOP_GOMEL1": ["dedl", "eumetsat_ds"],
        "METOP_GOMEL1R03": ["dedl", "eumetsat_ds"],
        "METOP_HIRSL1": ["dedl", "eumetsat_ds"],
        "METOP_IASTHR011": ["dedl", "eumetsat_ds"],
        "METOP_IASSND02": ["dedl", "eumetsat_ds"],
        "METOP_IASIL1C_ALL": ["dedl", "eumetsat_ds"],
        "METOP_LSA_002": ["dedl", "eumetsat_ds"],
        "METOP_MHSL1": ["dedl", "eumetsat_ds"],
        "METOP_OSI_104": ["dedl", "eumetsat_ds"],
        "METOP_OSI_150A": ["dedl", "eumetsat_ds"],
        "METOP_OSI_150B": ["dedl", "eumetsat_ds"],
        "METOP_SOMO12": ["dedl", "eumetsat_ds"],
        "METOP_SOMO25": ["dedl", "eumetsat_ds"],
        "MSG_CLM": ["dedl", "eumetsat_ds"],
        "MSG_CLM_IODC": ["dedl", "eumetsat_ds"],
        "MSG_GSAL2R02": ["dedl", "eumetsat_ds"],
        "MSG_HRSEVIRI": ["dedl", "eumetsat_ds"],
        "MSG_HRSEVIRI_IODC": ["dedl", "eumetsat_ds"],
        "MSG_RSS_CLM": ["dedl", "eumetsat_ds"],
        "MSG_MSG15_RSS": ["dedl", "eumetsat_ds"],
        "MSG_LSA_FRM": ["dedl", "eumetsat_ds"],
        "MSG_LSA_LST_CDR": ["dedl", "eumetsat_ds"],
        "MSG_LSA_LSTDE": ["dedl", "eumetsat_ds"],
        "MSG_AMVR02": ["dedl", "eumetsat_ds"],
        "MSG_CTH": ["eumetsat_ds"],
        "MSG_CTH_IODC": ["eumetsat_ds"],
        "MFG_GSA_57": ["eumetsat_ds"],
        "MFG_GSA_63": ["eumetsat_ds"],
        "MSG_MFG_GSA_0": ["eumetsat_ds"],
        "HIRS_FDR_1_MULTI": ["eumetsat_ds"],
        "MSG_OCA_CDR": ["eumetsat_ds"],
        "S6_RADIO_OCCULTATION": ["eumetsat_ds"],
        "MTG_LI_AF": ["eumetsat_ds"],
        "MTG_LI_LFL": ["eumetsat_ds"],
        "MTG_LI_LGR": ["eumetsat_ds"],
        "MTG_LI_AFA": ["eumetsat_ds"],
        "MTG_LI_AFR": ["eumetsat_ds"],
        "MTG_LI_LEF": ["eumetsat_ds"],
        "MTG_FCI_FDHSI": ["eumetsat_ds"],
        "MTG_FCI_HRFI": ["eumetsat_ds"],
        "MTG_FCI_ASR_BUFR": ["eumetsat_ds"],
        "MTG_FCI_ASR_NETCDF": ["eumetsat_ds"],
        "MTG_FCI_AMV_BUFR": ["eumetsat_ds"],
        "MTG_FCI_AMV_NETCDF": ["eumetsat_ds"],
        "MTG_FCI_CLM": ["eumetsat_ds"],
        "MTG_FCI_GII": ["eumetsat_ds"],
        "MTG_FCI_OCA": ["eumetsat_ds"],
        "MTG_FCI_OLR": ["eumetsat_ds"],
        "MODIS_MCD43A4": ["aws_eos", "planetary_computer"],
        "MO_GLOBAL_ANALYSISFORECAST_PHY_001_024": ["cop_marine", "dedl"],
        "MO_GLOBAL_ANALYSISFORECAST_BGC_001_028": ["cop_marine", "dedl"],
        "MO_GLOBAL_ANALYSISFORECAST_WAV_001_027": ["cop_marine", "dedl"],
        "MO_GLOBAL_MULTIYEAR_BGC_001_033": ["cop_marine", "dedl"],
        "MO_GLOBAL_MULTIYEAR_WAV_001_032": ["cop_marine", "dedl"],
        "MO_GLOBAL_MULTIYEAR_PHY_ENS_001_031": ["cop_marine", "dedl"],
        "MO_INSITU_GLO_PHY_UV_DISCRETE_NRT_013_048": ["cop_marine", "dedl"],
        "MO_INSITU_GLO_PHY_TS_OA_NRT_013_002": ["cop_marine", "dedl"],
        "MO_INSITU_GLO_PHY_TS_OA_MY_013_052": ["cop_marine", "dedl"],
        "MO_MULTIOBS_GLO_BIO_BGC_3D_REP_015_010": ["cop_marine", "dedl"],
        "MO_MULTIOBS_GLO_BIO_CARBON_SURFACE_MYNRT_015_008": ["cop_marine", "dedl"],
        "MO_MULTIOBS_GLO_BGC_NUTRIENTS_CARBON_PROFILES_MYNRT_015_009": [
            "cop_marine",
            "dedl",
        ],
        "MO_MULTIOBS_GLO_PHY_MYNRT_015_003": ["cop_marine", "dedl"],
        "MO_MULTIOBS_GLO_PHY_S_SURFACE_MYNRT_015_013": ["cop_marine", "dedl"],
        "MO_MULTIOBS_GLO_PHY_TSUV_3D_MYNRT_015_012": ["cop_marine", "dedl"],
        "MO_MULTIOBS_GLO_PHY_W_3D_REP_015_007": ["cop_marine", "dedl"],
        "MO_SEAICE_GLO_SEAICE_L4_NRT_OBSERVATIONS_011_001": ["cop_marine", "dedl"],
        "MO_SEAICE_GLO_SEAICE_L4_REP_OBSERVATIONS_011_009": ["cop_marine", "dedl"],
        "MO_SEAICE_GLO_SEAICE_L4_NRT_OBSERVATIONS_011_006": ["cop_marine", "dedl"],
        "MO_SEALEVEL_GLO_PHY_L4_NRT_008_046": ["cop_marine", "dedl"],
        "MO_SEALEVEL_GLO_PHY_MDT_008_063": ["cop_marine", "dedl"],
        "MO_SST_GLO_SST_L3S_NRT_OBSERVATIONS_010_010": ["cop_marine", "dedl"],
        "MO_SST_GLO_SST_L4_NRT_OBSERVATIONS_010_001": ["cop_marine", "dedl"],
        "MO_SST_GLO_SST_L4_REP_OBSERVATIONS_010_011": ["cop_marine", "dedl"],
        "MO_SST_GLO_SST_L4_REP_OBSERVATIONS_010_024": ["cop_marine", "dedl"],
        "MO_WAVE_GLO_PHY_SPC_FWK_L3_NRT_014_002": ["cop_marine", "dedl"],
        "MO_WAVE_GLO_PHY_SWH_L3_NRT_014_001": ["cop_marine", "dedl"],
        "MO_WAVE_GLO_PHY_SWH_L4_NRT_014_003": ["cop_marine", "dedl"],
        "MO_WIND_GLO_PHY_CLIMATE_L4_MY_012_003": ["cop_marine", "dedl"],
        "MO_WIND_GLO_PHY_L3_NRT_012_002": ["cop_marine", "dedl"],
        "MO_WIND_GLO_PHY_L3_MY_012_005": ["cop_marine", "dedl"],
        "MO_WIND_GLO_PHY_L4_NRT_012_004": ["cop_marine", "dedl"],
        "MO_WIND_GLO_PHY_L4_MY_012_006": ["cop_marine", "dedl"],
        "MO_OCEANCOLOUR_GLO_BGC_L3_MY_009_107": ["cop_marine", "dedl"],
        "MO_OCEANCOLOUR_GLO_BGC_L3_NRT_009_101": ["cop_marine", "dedl"],
        "MO_OCEANCOLOUR_GLO_BGC_L3_MY_009_103": ["cop_marine", "dedl"],
        "MO_OCEANCOLOUR_GLO_BGC_L4_NRT_009_102": ["cop_marine", "dedl"],
        "MO_OCEANCOLOUR_GLO_BGC_L4_MY_009_104": ["cop_marine", "dedl"],
        "MO_OCEANCOLOUR_GLO_BGC_L4_MY_009_108": ["cop_marine", "dedl"],
        "NAIP": ["aws_eos", "earth_search", "planetary_computer"],
        "NEMSAUTO_TCDC": ["meteoblue"],
        "NEMSGLOBAL_TCDC": ["meteoblue"],
        "S1_SAR_GRD": [
            "aws_eos",
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "earth_search",
            "geodes",
            "geodes_s3",
            "peps",
            "planetary_computer",
            "sara",
            "wekeo_main",
        ],
        "S1_SAR_GRD_COG": ["cop_dataspace"],
        "S1_SAR_OCN": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "geodes",
            "geodes_s3",
            "peps",
            "sara",
            "wekeo_main",
        ],
        "S1_SAR_RAW": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "wekeo_main",
        ],
        "S1_SAR_SLC": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "geodes",
            "geodes_s3",
            "peps",
            "sara",
            "wekeo_main",
        ],
        "S2_MSI_L1C": [
            "aws_eos",
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "earth_search",
            "earth_search_gcs",
            "geodes",
            "geodes_s3",
            "peps",
            "sara",
            "usgs",
            "wekeo_main",
        ],
        "S2_MSI_L2A": [
            "aws_eos",
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "planetary_computer",
            "sara",
            "wekeo_main",
        ],
        "S2_MSI_L2A_COG": ["earth_search_cog"],
        "S2_MSI_L2A_MAJA": ["geodes", "geodes_s3"],
        "S2_MSI_L2B_MAJA_SNOW": ["geodes", "geodes_s3"],
        "S2_MSI_L2B_MAJA_WATER": ["geodes", "geodes_s3"],
        "S3_EFR": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "eumetsat_ds",
            "sara",
            "wekeo_main",
        ],
        "S3_EFR_BC002": ["eumetsat_ds"],
        "S3_ERR": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "eumetsat_ds",
            "sara",
            "wekeo_main",
        ],
        "S3_ERR_BC002": ["eumetsat_ds"],
        "S3_LAN": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "sara",
            "wekeo_main",
        ],
        "S3_OLCI_L2LFR": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "sara",
            "wekeo_main",
        ],
        "S3_OLCI_L2LRR": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "sara",
            "wekeo_main",
        ],
        "S3_OLCI_L2WFR": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "eumetsat_ds",
            "sara",
            "wekeo_main",
        ],
        "S3_OLCI_L2WRR": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "eumetsat_ds",
            "sara",
            "wekeo_main",
        ],
        "S3_RAC": ["sara"],
        "S3_SLSTR_L1RBT": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "eumetsat_ds",
            "sara",
            "wekeo_main",
        ],
        "S3_SLSTR_L1RBT_BC003": ["eumetsat_ds"],
        "S3_SLSTR_L2": ["wekeo_main"],
        "S3_SLSTR_L2AOD": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "eumetsat_ds",
            "sara",
        ],
        "S3_SLSTR_L2FRP": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "eumetsat_ds",
            "sara",
        ],
        "S3_SLSTR_L2LST": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "sara",
        ],
        "S3_SLSTR_L2WST": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "eumetsat_ds",
            "sara",
        ],
        "S3_SRA": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "eumetsat_ds",
            "sara",
            "wekeo_main",
        ],
        "S3_SRA_A": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "eumetsat_ds",
            "sara",
            "wekeo_main",
        ],
        "S3_SRA_BS": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "eumetsat_ds",
            "sara",
            "wekeo_main",
        ],
        "S3_SY_AOD": ["cop_dataspace", "creodias", "creodias_s3", "sara"],
        "S3_SY_SYN": ["cop_dataspace", "creodias", "creodias_s3", "sara"],
        "S3_SY_V10": ["cop_dataspace", "creodias", "creodias_s3", "sara"],
        "S3_SY_VG1": ["cop_dataspace", "creodias", "creodias_s3", "sara"],
        "S3_SY_VGP": ["cop_dataspace", "creodias", "creodias_s3", "sara"],
        "S3_WAT": [
            "cop_dataspace",
            "creodias",
            "creodias_s3",
            "dedl",
            "eumetsat_ds",
            "sara",
            "wekeo_main",
        ],
        "S3_LAN_HY": ["wekeo_main"],
        "S3_LAN_SI": ["wekeo_main"],
        "S3_LAN_LI": ["wekeo_main"],
        "S5P_L1B_IR_ALL": ["dedl", "wekeo_main"],
        "S5P_L2_IR_ALL": ["dedl", "wekeo_main"],
        "S3_OLCI_L2WFR_BC003": ["eumetsat_ds"],
        "S3_OLCI_L2WRR_BC003": ["eumetsat_ds"],
        "S3_SRA_1A_BC004": ["eumetsat_ds"],
        "S3_SRA_1A_BC005": ["eumetsat_ds"],
        "S3_SRA_1B_BC004": ["eumetsat_ds"],
        "S3_SRA_1B_BC005": ["eumetsat_ds"],
        "S3_SRA_BS_BC004": ["eumetsat_ds"],
        "S3_SRA_BS_BC005": ["eumetsat_ds"],
        "S3_WAT_BC004": ["eumetsat_ds"],
        "S3_WAT_BC005": ["eumetsat_ds"],
        "S3_SLSTR_L1RBT_BC004": ["eumetsat_ds"],
        "S3_SLSTR_L2WST_BC003": ["eumetsat_ds"],
        "S5P_L1B_IR_SIR": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L1B_IR_UVN": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L1B_RA_BD1": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L1B_RA_BD2": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L1B_RA_BD3": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L1B_RA_BD4": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L1B_RA_BD5": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L1B_RA_BD6": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L1B_RA_BD7": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L1B_RA_BD8": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_AER_AI": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_AER_LH": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_CH4": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_CLOUD": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_CO": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_HCHO": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_NO2": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_NP_BD3": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_NP_BD6": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_NP_BD7": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_O3": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_O3_PR": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_O3_TCL": ["cop_dataspace", "creodias", "creodias_s3"],
        "S5P_L2_SO2": ["cop_dataspace", "creodias", "creodias_s3"],
        "SATELLITE_CARBON_DIOXIDE": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "SATELLITE_FIRE_BURNED_AREA": ["cop_cds", "wekeo_ecmwf"],
        "SATELLITE_METHANE": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "SATELLITE_SEA_ICE_EDGE_TYPE": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "SATELLITE_SEA_LEVEL_GLOBAL": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "SATELLITE_SEA_ICE_CONCENTRATION": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "SATELLITE_SEA_ICE_THICKNESS": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "SEASONAL_MONTHLY_PL": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "SEASONAL_MONTHLY_SL": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "SEASONAL_ORIGINAL_PL": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "SEASONAL_ORIGINAL_SL": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "SEASONAL_POSTPROCESSED_PL": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "SEASONAL_POSTPROCESSED_SL": ["cop_cds", "dedl", "wekeo_ecmwf"],
        "SIS_HYDRO_MET_PROJ": ["cop_cds", "dedl"],
        "TIGGE_CF_SFC": ["ecmwf"],
        "UERRA_EUROPE_SL": ["cop_cds", "dedl", "wekeo_ecmwf"],
        GENERIC_PRODUCT_TYPE: [
            "peps",
            "usgs",
            "creodias",
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
            "dedl",
        ],
    }
    SUPPORTED_PROVIDERS = [
        "peps",
        "aws_eos",
        "cop_ads",
        "cop_cds",
        "cop_dataspace",
        "cop_ewds",
        "cop_marine",
        "creodias",
        "creodias_s3",
        "dedl",
        "dedt_lumi",
        "earth_search",
        "earth_search_cog",
        "earth_search_gcs",
        "ecmwf",
        "eumetsat_ds",
        "fedeo_ceda",
        "geodes",
        "geodes_s3",
        "hydroweb_next",
        "meteoblue",
        "planetary_computer",
        "sara",
        "usgs",
        "usgs_satapi_aws",
        "wekeo_cmems",
        "wekeo_ecmwf",
        "wekeo_main",
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
                        provider,
                        self.SUPPORTED_PRODUCT_TYPES[product_type["ID"]],
                        f"missing in supported providers for {product_type['ID']}",
                    )
                else:
                    self.assertIn(
                        provider,
                        self.SUPPORTED_PRODUCT_TYPES[product_type["_id"]],
                        f"missing in supported providers for {product_type['_id']}",
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

    def test_guess_product_type_with_filter(self):
        """Testing the search terms"""

        with open(
            os.path.join(TEST_RESOURCES_PATH, "ext_product_types_free_text_search.json")
        ) as f:
            ext_product_types_conf = json.load(f)
        self.dag.update_product_types_list(ext_product_types_conf)

        # Search any filter contains filter value
        filter = "ABSTRACTFOO"
        product_types_ids = self.dag.guess_product_type(filter)
        self.assertListEqual(product_types_ids, ["foo"])
        # Search the exact phrase. Search is case insensitive
        filter = '"THIS IS FOO. fooandbar"'
        product_types_ids = self.dag.guess_product_type(filter)
        self.assertListEqual(product_types_ids, ["foo"])

        # Free text search: match in the keywords
        filter = "LECTUS_BAR_KEY"
        product_types_ids = self.dag.guess_product_type(filter)
        self.assertListEqual(product_types_ids, ["bar"])

        # Free text search: match the phrase in title
        filter = '"FOOBAR COLLECTION"'
        product_types_ids = self.dag.guess_product_type(filter)
        self.assertListEqual(product_types_ids, ["foobar_alias"])

        # Free text search: Using OR term match
        filter = "FOOBAR OR BAR"
        product_types_ids = self.dag.guess_product_type(filter)
        self.assertListEqual(sorted(product_types_ids), ["bar", "foobar_alias"])

        # Free text search: using OR term match with additional filter UNION
        filter = "FOOBAR OR BAR"
        product_types_ids = self.dag.guess_product_type(filter, title="FOO")
        self.assertListEqual(sorted(product_types_ids), ["bar", "foo", "foobar_alias"])

        # Free text search: Using AND term match
        filter = "suspendisse AND FOO"
        product_types_ids = self.dag.guess_product_type(filter)
        self.assertListEqual(product_types_ids, ["foo"])

        # Free text search: Parentheses can be used to group terms
        filter = "(FOOBAR OR BAR) AND titleFOOBAR"
        product_types_ids = self.dag.guess_product_type(filter)
        self.assertListEqual(product_types_ids, ["foobar_alias"])

        # Free text search: multiple terms joined with param search (INTERSECT)
        filter = "FOOBAR OR BAR"
        product_types_ids = self.dag.guess_product_type(
            filter, intersect=True, title="titleFOO*"
        )
        self.assertListEqual(product_types_ids, ["foobar_alias"])

    def test_guess_product_type_with_mission_dates(self):
        """Testing the datetime interval"""

        with open(
            os.path.join(TEST_RESOURCES_PATH, "ext_product_types_free_text_search.json")
        ) as f:
            ext_product_types_conf = json.load(f)
        self.dag.update_product_types_list(ext_product_types_conf)

        product_types_ids = self.dag.guess_product_type(
            title="TEST DATES",
            missionStartDate="2013-02-01",
            missionEndDate="2013-02-05",
        )
        self.assertListEqual(product_types_ids, ["interval_end"])
        product_types_ids = self.dag.guess_product_type(
            title="TEST DATES",
            missionStartDate="2013-02-01",
            missionEndDate="2013-02-15",
        )
        self.assertListEqual(
            sorted(product_types_ids),
            ["interval_end", "interval_start", "interval_start_end"],
        )
        product_types_ids = self.dag.guess_product_type(
            title="TEST DATES", missionStartDate="2013-02-01"
        )
        self.assertListEqual(
            sorted(product_types_ids),
            ["interval_end", "interval_start", "interval_start_end"],
        )
        product_types_ids = self.dag.guess_product_type(
            title="TEST DATES", missionEndDate="2013-02-20"
        )
        self.assertListEqual(
            sorted(product_types_ids),
            ["interval_end", "interval_start", "interval_start_end"],
        )

    def test_update_product_types_list(self):
        """Core api.update_product_types_list must update eodag product types list"""
        with open(os.path.join(TEST_RESOURCES_PATH, "ext_product_types.json")) as f:
            ext_product_types_conf = json.load(f)

        self.assertNotIn("foo", self.dag.providers_config["earth_search"].products)
        self.assertNotIn("bar", self.dag.providers_config["earth_search"].products)
        self.assertNotIn("foo", self.dag.product_types_config)
        self.assertNotIn("bar", self.dag.product_types_config)

        self.dag.update_product_types_list(ext_product_types_conf)

        self.assertIn("foo", self.dag.providers_config["earth_search"].products)
        self.assertIn("bar", self.dag.providers_config["earth_search"].products)
        self.assertEqual(self.dag.product_types_config["foo"]["license"], "WTFPL")
        self.assertEqual(
            self.dag.product_types_config["bar"]["title"], "Bar collection"
        )

    def test_update_product_types_list_unknown_provider(self):
        """Core api.update_product_types_list on unkwnown provider must not crash and not update conf"""
        with open(os.path.join(TEST_RESOURCES_PATH, "ext_product_types.json")) as f:
            ext_product_types_conf = json.load(f)
        self.dag.providers_config.pop("earth_search")

        self.dag.update_product_types_list(ext_product_types_conf)
        self.assertNotIn("earth_search", self.dag.providers_config)

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
        ext_product_types_conf["ecmwf"] = ext_product_types_conf.pop("earth_search")

        self.assertNotIn("foo", self.dag.providers_config["ecmwf"].products)
        self.assertNotIn("bar", self.dag.providers_config["ecmwf"].products)
        self.assertNotIn("foo", self.dag.product_types_config)
        self.assertNotIn("bar", self.dag.product_types_config)

        # update existing provider conf and check that update_product_types_list() is launched for it
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

        self.assertNotIn("foo", self.dag.providers_config["earth_search"].products)
        self.assertNotIn("bar", self.dag.providers_config["earth_search"].products)
        self.assertNotIn("foo", self.dag.product_types_config)
        self.assertNotIn("bar", self.dag.product_types_config)

        delattr(self.dag.providers_config["earth_search"], "search")

        self.dag.update_product_types_list(ext_product_types_conf)

        self.assertNotIn("foo", self.dag.providers_config["earth_search"].products)
        self.assertNotIn("bar", self.dag.providers_config["earth_search"].products)
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
        ext_product_types_conf = self.dag.discover_product_types(
            provider="earth_search"
        )
        self.assertEqual(
            ext_product_types_conf["earth_search"]["providers_config"]["foo"][
                "productType"
            ],
            "foo",
        )
        self.assertEqual(
            ext_product_types_conf["earth_search"]["product_types_config"]["foo"][
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
        delattr(self.dag.providers_config["earth_search"], "search")
        ext_product_types_conf = self.dag.discover_product_types(
            provider="earth_search"
        )
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
            "earth_search": {
                "providers_config": {"foo": {"productType": "foo"}},
                "product_types_config": {"foo": {"title": "Foo collection"}},
            }
        }
        # add an empty ext-conf for other providers to prevent them to be fetched
        for provider, provider_config in self.dag.providers_config.items():
            if provider != "earth_search" and hasattr(provider_config, "search"):
                provider_search_config = provider_config.search
            elif provider != "earth_search" and hasattr(provider_config, "api"):
                provider_search_config = provider_config.api
            else:
                continue
            if hasattr(
                provider_search_config, "discover_product_types"
            ) and provider_search_config.discover_product_types.get("fetch_url"):
                mock_get_ext_product_types_conf.return_value[provider] = {}
        self.dag.fetch_product_types_list()
        self.assertTrue(self.dag.providers_config["earth_search"].product_types_fetched)
        self.assertEqual(
            self.dag.providers_config["earth_search"].products["foo"],
            {"productType": "foo"},
        )
        self.assertEqual(
            self.dag.product_types_config.source["foo"],
            {"_id": "foo", "title": "Foo collection"},
        )

        # update existing provider conf and check that discover_product_types() is launched for it
        self.assertEqual(mock_discover_product_types.call_count, 0)
        self.dag.update_providers_config(
            """
            earth_search:
                search:
                    discover_product_types:
                        fetch_url: 'http://new-endpoint'
            """
        )
        self.dag.fetch_product_types_list()
        mock_discover_product_types.assert_called_once_with(
            self.dag, provider="earth_search"
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
        new_default_conf["new_provider"] = new_default_conf["earth_search"]

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
                ) and provider_search_config.discover_product_types.get("fetch_url"):
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
            earth_search:
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
        self.assertTrue(
            structure["ID"] in self.SUPPORTED_PRODUCT_TYPES
            or structure["_id"] in self.SUPPORTED_PRODUCT_TYPES
        )

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
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
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

    @mock.patch("eodag.plugins.manager.importlib_metadata.entry_points", autospec=True)
    def test_prune_providers_list_skipped_plugin(self, mock_iter_ep):
        """Providers needing skipped plugin must be pruned on init"""
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
        )

        def skip_qssearch(group):
            ep = mock.MagicMock()
            if group == "eodag.plugins.search":
                ep.name = "QueryStringSearch"
                ep.load = mock.MagicMock(side_effect=ModuleNotFoundError())
            return [ep]

        mock_iter_ep.side_effect = skip_qssearch

        dag = EODataAccessGateway(user_conf_file_path=empty_conf_file)
        self.assertNotIn("peps", dag.available_providers())
        self.assertEqual(dag._plugins_manager.skipped_plugins, ["QueryStringSearch"])
        dag._plugins_manager.skipped_plugins = []

    def test_prune_providers_list_for_search_without_auth(self):
        """Providers needing auth for search but without auth plugin must be pruned on init"""
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
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
        empty_conf_file = str(
            res_files("eodag") / "resources" / "user_conf_template.yml"
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

    def test_get_version(self):
        """Test if the version we get is the current one"""
        version_str = self.dag.get_version()
        self.assertEqual(eodag_version, version_str)

    def test_set_preferred_provider(self):
        """set_preferred_provider must set the preferred provider with increasing priority"""

        self.assertEqual(self.dag.get_preferred_provider(), ("peps", 1))

        self.assertRaises(
            UnsupportedProvider, self.dag.set_preferred_provider, "unknown"
        )

        self.dag.set_preferred_provider("creodias")
        self.assertEqual(self.dag.get_preferred_provider(), ("creodias", 2))

        self.dag.set_preferred_provider("cop_dataspace")
        self.assertEqual(self.dag.get_preferred_provider(), ("cop_dataspace", 3))

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
        "eodag.plugins.manager.PluginManager.get_auth_plugin",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.discover_queryables",
        autospec=True,
        return_value={},
    )
    def test_list_queryables(
        self,
        mock_stacsearch_discover_queryables: mock.Mock,
        mock_fetch_product_types_list: mock.Mock,
        mock_auth_plugin: mock.Mock,
    ) -> None:
        """list_queryables must return queryables list adapted to provider and product-type"""

        with self.assertRaises(UnsupportedProvider):
            self.dag.list_queryables(provider="not_supported_provider")

        with self.assertRaises(UnsupportedProductType):
            self.dag.list_queryables(productType="not_supported_product_type")

        # No provider & no product type
        queryables_none_none = self.dag.list_queryables()
        expected_result = model_fields_to_annotated(CommonQueryables.model_fields)
        self.assertEqual(len(queryables_none_none), len(expected_result))
        for key, queryable in queryables_none_none.items():
            # compare obj.__repr__
            self.assertEqual(str(expected_result[key]), str(queryable))
        self.assertTrue(queryables_none_none.additional_properties)

        # Only provider
        # when only a provider is specified, return the union of the queryables for all product types
        queryables_peps_none = self.dag.list_queryables(provider="peps")
        expected_longer_result = model_fields_to_annotated(Queryables.model_fields)
        self.assertGreater(len(queryables_peps_none), len(queryables_none_none))
        self.assertLess(len(queryables_peps_none), len(expected_longer_result))
        for key, queryable in queryables_peps_none.items():
            # compare obj.__repr__
            self.assertEqual(str(expected_longer_result[key]), str(queryable))
        self.assertTrue(queryables_peps_none.additional_properties)

        # provider & product type
        queryables_peps_s1grd = self.dag.list_queryables(
            provider="peps", productType="S1_SAR_GRD"
        )
        self.assertGreater(len(queryables_peps_s1grd), len(queryables_none_none))
        self.assertLess(len(queryables_peps_s1grd), len(expected_longer_result))
        for key, queryable in queryables_peps_s1grd.items():
            if key == "productType":
                self.assertEqual("S1_SAR_GRD", queryable.__metadata__[0].get_default())
            else:
                # compare obj.__repr__
                self.assertEqual(str(expected_longer_result[key]), str(queryable))
        self.assertTrue(queryables_peps_s1grd.additional_properties)

        # provider & product type alias
        # result should be the same if alias is used
        products = self.dag.product_types_config
        products["S1_SAR_GRD"]["alias"] = "S1_SG"
        queryables_peps_s1grd_alias = self.dag.list_queryables(
            provider="peps", productType="S1_SG"
        )
        self.assertEqual(len(queryables_peps_s1grd), len(queryables_peps_s1grd_alias))
        self.assertEqual(
            "S1_SG",
            queryables_peps_s1grd_alias["productType"].__metadata__[0].get_default(),
        )
        products["S1_SAR_GRD"].pop("alias")

        # Only product type
        # when a product type is specified but not the provider, the union of the queryables of all providers
        # having the product type in its config is returned
        queryables_none_s1grd = self.dag.list_queryables(productType="S1_SAR_GRD")
        self.assertGreaterEqual(len(queryables_none_s1grd), len(queryables_none_none))
        self.assertGreater(len(queryables_none_s1grd), len(queryables_peps_none))
        self.assertGreaterEqual(len(queryables_none_s1grd), len(queryables_peps_s1grd))
        self.assertLess(len(queryables_none_s1grd), len(expected_longer_result))
        # check that peps gets the highest priority
        self.assertEqual(self.dag.get_preferred_provider()[0], "peps")
        for key, queryable in queryables_peps_s1grd.items():
            if key == "productType":
                self.assertEqual("S1_SAR_GRD", queryable.__metadata__[0].get_default())
            else:
                # compare obj.__repr__
                self.assertEqual(str(expected_longer_result[key]), str(queryable))
            # queryables for provider peps are in queryables for all providers
            self.assertEqual(str(queryable), str(queryables_none_s1grd[key]))
        self.assertTrue(queryables_none_s1grd.additional_properties)

        # model_validate should validate input parameters using the queryables result
        queryables_validated = queryables_peps_s1grd.get_model().model_validate(
            {"productType": "S1_SAR_GRD", "snowCover": 50}
        )
        self.assertIn("snowCover", queryables_validated.__dict__)
        with self.assertRaises(ValidationError):
            queryables_peps_s1grd.get_model().model_validate(
                {"productType": "S1_SAR_GRD", "snowCover": 500}
            )

    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch.discover_queryables",
        autospec=True,
    )
    def test_additional_properties_in_list_queryables(
        self, mock_discover_queryables: mock.Mock
    ):
        """additional_properties in queryables must be adapted to provider's configuration"""
        # Check if discover_metadata.auto_discovery is False
        self.assertFalse(
            self.dag.providers_config["cop_marine"].search.discover_metadata[
                "auto_discovery"
            ]
        )
        cop_marine_queryables = self.dag.list_queryables(provider="cop_marine")
        self.assertFalse(cop_marine_queryables.additional_properties)

        item_cop_marine_queryables = self.dag.list_queryables(
            productType="MO_INSITU_GLO_PHY_TS_OA_NRT_013_002", provider="cop_marine"
        )
        self.assertFalse(item_cop_marine_queryables.additional_properties)

        # Check if discover_metadata.auto_discovery is True
        self.assertTrue(
            self.dag.providers_config["peps"].search.discover_metadata["auto_discovery"]
        )
        peps_queryables = self.dag.list_queryables(provider="peps")
        self.assertTrue(peps_queryables.additional_properties)

        item_peps_queryables = self.dag.list_queryables(
            productType="S2_MSI_L1C", provider="peps"
        )
        self.assertTrue(item_peps_queryables.additional_properties)

        # additional_properties set to False for EcmwfSearch plugin
        cop_cds_queryables = self.dag.list_queryables(provider="cop_cds")
        self.assertFalse(cop_cds_queryables.additional_properties)

    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch.discover_queryables",
        autospec=True,
    )
    def test_list_queryables_with_constraints(
        self, mock_discover_queryables: mock.Mock
    ):
        plugin = next(
            self.dag._plugins_manager.get_search_plugins(
                provider="cop_cds", product_type="ERA5_SL"
            )
        )
        # default values should be added to params
        self.dag.list_queryables(provider="cop_cds", productType="ERA5_SL")
        defaults = {
            "productType": "ERA5_SL",
            "product_type": "reanalysis",
            "dataset": "reanalysis-era5-single-levels",
            "data_format": "grib",
            "download_format": "zip",
            "variable": "10m_u_component_of_wind",
        }
        mock_discover_queryables.assert_called_once_with(plugin, **defaults)
        mock_discover_queryables.reset_mock()
        # default values + additional param
        res = self.dag.list_queryables(
            provider="cop_cds", **{"productType": "ERA5_SL", "month": "02"}
        )
        params = {
            "productType": "ERA5_SL",
            "product_type": "reanalysis",
            "dataset": "reanalysis-era5-single-levels",
            "data_format": "grib",
            "download_format": "zip",
            "variable": "10m_u_component_of_wind",
            "month": "02",
        }
        mock_discover_queryables.assert_called_once_with(plugin, **params)
        self.assertFalse(res.additional_properties)
        mock_discover_queryables.reset_mock()

        # unset default values
        self.dag.list_queryables(
            provider="cop_cds", **{"productType": "ERA5_SL", "data_format": ""}
        )
        defaults = {
            "productType": "ERA5_SL",
            "product_type": "reanalysis",
            "dataset": "reanalysis-era5-single-levels",
            "variable": "10m_u_component_of_wind",
            "data_format": "",
            "download_format": "zip",
        }
        mock_discover_queryables.assert_called_once_with(plugin, **defaults)

    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.list_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch.list_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.build_search_result.WekeoECMWFSearch.list_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.manager.PluginManager.get_auth_plugin",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test_list_queryables_priority_sorted(
        self,
        mock_fetch_product_types_list: mock.Mock,
        get_auth_plugin: mock.Mock,
        mock_wekeo_list_queryables: mock.Mock,
        mock_ecmwf_list_queryables: mock.Mock,
        mock_dedl_list_queryables: mock.Mock,
    ):
        mock_wekeo_list_queryables.return_value = QueryablesDict(
            additional_properties=False,
            additional_information="Mocked WEkEO queryables",
            property1="value_from_wekeo",
        )

        mock_ecmwf_list_queryables.return_value = QueryablesDict(
            additional_properties=False,
            additional_information="Mocked ECMWF queryables for cop_cds",
            property1="value_cds1",
            property2="value_cds2",
        )

        mock_dedl_list_queryables.return_value = QueryablesDict(
            additional_properties=False,
            additional_information="Mocked STAC queryables for dedl",
            property1="value_dedl1",
            property2="value_dedl2",
            property3="value_dedl3",
        )

        self.dag.set_preferred_provider("wekeo_ecmwf")

        queryables = self.dag.list_queryables(productType="ERA5_SL")

        self.assertEqual(queryables["property1"], "value_from_wekeo")
        self.assertEqual(queryables["property2"], "value_cds2")
        self.assertEqual(queryables["property3"], "value_dedl3")

        self.dag.set_preferred_provider("cop_cds")

        queryables = self.dag.list_queryables(productType="ERA5_SL")

        self.assertEqual(queryables["property1"], "value_cds1")
        self.assertEqual(queryables["property2"], "value_cds2")
        self.assertEqual(queryables["property3"], "value_dedl3")

        self.dag.set_preferred_provider("dedl")

        queryables = self.dag.list_queryables(productType="ERA5_SL")

        self.assertEqual(queryables["property1"], "value_dedl1")
        self.assertEqual(queryables["property2"], "value_dedl2")
        self.assertEqual(queryables["property3"], "value_dedl3")

    @mock.patch(
        "eodag.plugins.search.qssearch.StacSearch.list_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.build_search_result.ECMWFSearch.list_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.search.build_search_result.WekeoECMWFSearch.list_queryables",
        autospec=True,
    )
    @mock.patch(
        "eodag.plugins.manager.PluginManager.get_auth_plugin",
        autospec=True,
    )
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    def test_list_queryables_additional(
        self,
        mock_fetch_product_types_list: mock.Mock,
        get_auth_plugin: mock.Mock,
        mock_wekeo_list_queryables: mock.Mock,
        mock_ecmwf_list_queryables: mock.Mock,
        mock_dedl_list_queryables: mock.Mock,
    ):
        mock_wekeo_list_queryables.return_value = QueryablesDict(
            additional_properties=False,
            additional_information="Mocked WEkEO queryables",
        )

        mock_ecmwf_list_queryables.return_value = QueryablesDict(
            additional_properties=False,
            additional_information="Mocked ECMWF queryables for cop_cds",
        )

        mock_dedl_list_queryables.return_value = QueryablesDict(
            additional_properties=False,
            additional_information="Mocked STAC queryables for dedl",
        )

        queryables = self.dag.list_queryables(productType="ERA5_SL")

        self.assertEqual(
            queryables.additional_information,
            (
                "cop_cds: Mocked ECMWF queryables for cop_cds"
                " | wekeo_ecmwf: Mocked WEkEO queryables"
                " | dedl: Mocked STAC queryables for dedl"
            ),
        )
        self.assertEqual(queryables.additional_properties, False)

        mock_dedl_list_queryables.return_value = QueryablesDict(
            additional_properties=True,
            additional_information="Mocked STAC queryables for dedl",
        )
        queryables = self.dag.list_queryables(productType="ERA5_SL")

        self.assertEqual(queryables.additional_properties, True)

    def test_queryables_repr(self):
        queryables = self.dag.list_queryables(provider="peps", productType="S1_SAR_GRD")
        self.assertIsInstance(queryables, QueryablesDict)
        queryables_repr = html.fromstring(queryables._repr_html_())
        self.assertIn("QueryablesDict", queryables_repr.xpath("//thead/tr/td")[0].text)
        spans = queryables_repr.xpath("//tbody/tr/td/details/summary/span")
        product_type_present = False
        for i, span in enumerate(spans):
            if "productType" in span.text:
                product_type_present = True
                self.assertIn("str", spans[i + 1].text)
        self.assertTrue(product_type_present)

    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    def test_available_sortables(self, mock_auth_session_request):
        """available_sortables must return available sortable(s) and its (their)
        maximum number dict for providers which support the sorting feature"""
        self.maxDiff = None
        expected_result = {
            "peps": None,
            "aws_eos": None,
            "cop_ads": None,
            "cop_cds": None,
            "cop_dataspace": {
                "sortables": [
                    "startTimeFromAscendingNode",
                    "completionTimeFromAscendingNode",
                    "publicationDate",
                    "modificationDate",
                ],
                "max_sort_params": 1,
            },
            "cop_ewds": None,
            "creodias": {
                "sortables": [
                    "startTimeFromAscendingNode",
                    "completionTimeFromAscendingNode",
                    "publicationDate",
                    "modificationDate",
                ],
                "max_sort_params": 1,
            },
            "creodias_s3": {
                "sortables": [
                    "startTimeFromAscendingNode",
                    "completionTimeFromAscendingNode",
                    "publicationDate",
                    "modificationDate",
                ],
                "max_sort_params": 1,
            },
            "dedl": {
                "max_sort_params": None,
                "sortables": [
                    "id",
                    "startTimeFromAscendingNode",
                    "creationDate",
                    "modificationDate",
                    "platformSerialIdentifier",
                    "resolution",
                    "cloudCover",
                ],
            },
            "dedt_lumi": None,
            "earth_search": {
                "sortables": [
                    "id",
                    "startTimeFromAscendingNode",
                    "creationDate",
                    "modificationDate",
                    "platformSerialIdentifier",
                    "resolution",
                    "cloudCover",
                ],
                "max_sort_params": None,
            },
            "earth_search_gcs": {
                "sortables": [
                    "id",
                    "startTimeFromAscendingNode",
                    "creationDate",
                    "modificationDate",
                    "platformSerialIdentifier",
                    "resolution",
                    "cloudCover",
                ],
                "max_sort_params": None,
            },
            "earth_search_cog": {
                "sortables": [
                    "id",
                    "startTimeFromAscendingNode",
                    "creationDate",
                    "modificationDate",
                    "platform",
                    "platformSerialIdentifier",
                    "resolution",
                    "cloudCover",
                ],
                "max_sort_params": None,
            },
            "ecmwf": None,
            "eumetsat_ds": {
                "sortables": [
                    "startTimeFromAscendingNode",
                    "publicationDate",
                ],
                "max_sort_params": 1,
            },
            "cop_marine": None,
            "fedeo_ceda": {"max_sort_params": None, "sortables": []},
            "geodes": {
                "max_sort_params": None,
                "sortables": [
                    "id",
                    "startTimeFromAscendingNode",
                    "completionTimeFromAscendingNode",
                    "platformSerialIdentifier",
                    "cloudCover",
                ],
            },
            "geodes_s3": {
                "max_sort_params": None,
                "sortables": [
                    "id",
                    "startTimeFromAscendingNode",
                    "completionTimeFromAscendingNode",
                    "platformSerialIdentifier",
                    "cloudCover",
                ],
            },
            "hydroweb_next": {
                "sortables": [
                    "id",
                    "startTimeFromAscendingNode",
                    "completionTimeFromAscendingNode",
                    "productVersion",
                    "processingLevel",
                ],
                "max_sort_params": None,
            },
            "meteoblue": None,
            "planetary_computer": {
                "sortables": [
                    "id",
                    "startTimeFromAscendingNode",
                    "platformSerialIdentifier",
                ],
                "max_sort_params": None,
            },
            "sara": {
                "sortables": [
                    "startTimeFromAscendingNode",
                    "completionTimeFromAscendingNode",
                    "sensorMode",
                ],
                "max_sort_params": 1,
            },
            "usgs": None,
            "usgs_satapi_aws": {
                "sortables": [
                    "id",
                    "startTimeFromAscendingNode",
                    "creationDate",
                    "modificationDate",
                    "platformSerialIdentifier",
                    "illuminationElevationAngle",
                    "illuminationAzimuthAngle",
                    "cloudCover",
                ],
                "max_sort_params": None,
            },
            "wekeo_cmems": None,
            "wekeo_ecmwf": None,
            "wekeo_main": None,
        }
        sortables = self.dag.available_sortables()
        self.assertDictEqual(sortables, expected_result)

        # check if sortables are set to None when the provider does not support the sorting feature
        self.assertFalse(hasattr(self.dag.providers_config["peps"].search, "sort"))
        self.assertIsNone(sortables["peps"])

        # check if sortable parameter(s) and its (their) maximum number of a provider are set
        # to their value when the provider supports the sorting feature and has a maximum number of sortables
        self.assertTrue(hasattr(self.dag.providers_config["creodias"].search, "sort"))
        self.assertTrue(
            self.dag.providers_config["creodias"].search.sort.get("max_sort_params")
        )
        if sortables["creodias"]:
            self.assertIsNotNone(sortables["creodias"]["max_sort_params"])

        # check if sortable parameter(s) of a provider is set to its value and its (their) maximum number is set
        # to None when the provider supports the sorting feature and does not have a maximum number of sortables
        self.assertTrue(
            hasattr(self.dag.providers_config["planetary_computer"].search, "sort")
        )
        self.assertFalse(
            self.dag.providers_config["planetary_computer"].search.sort.get(
                "max_sort_params"
            )
        )
        if sortables["planetary_computer"]:
            self.assertIsNone(sortables["planetary_computer"]["max_sort_params"])


class TestCoreConfWithEnvVar(TestCoreBase):
    def tearDown(self):
        """Teardown run after every test"""
        if hasattr(self, "dag"):
            del self.dag

    def test_core_object_prioritize_locations_file_in_envvar(self):
        """The core object must use the locations file pointed by the EODAG_LOCS_CFG_FILE env var"""
        try:
            os.environ["EODAG_LOCS_CFG_FILE"] = os.path.join(
                TEST_RESOURCES_PATH, "file_locations_override.yml"
            )
            self.dag = EODataAccessGateway()
            self.assertEqual(
                self.dag.locations_config,
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
            self.dag = EODataAccessGateway()
            # usgs priority is set to 5 in the test config overrides
            self.assertEqual(self.dag.get_preferred_provider(), ("usgs", 5))
            # peps outputs prefix is set to /data
            self.assertEqual(
                self.dag.providers_config["peps"].download.output_dir, "/data"
            )
        finally:
            os.environ.pop("EODAG_CFG_FILE", None)

    def test_core_object_prioritize_providers_file_in_envvar(self):
        """The core object must use the providers conf file pointed by the EODAG_PROVIDERS_CFG_FILE env var"""
        try:
            os.environ["EODAG_PROVIDERS_CFG_FILE"] = os.path.join(
                TEST_RESOURCES_PATH, "file_providers_override.yml"
            )
            self.dag = EODataAccessGateway()
            # only foo_provider in conf
            self.assertEqual(self.dag.available_providers(), ["foo_provider"])
            self.assertEqual(
                self.dag.providers_config["foo_provider"].search.api_endpoint,
                "https://foo.bar/search",
            )
        finally:
            os.environ.pop("EODAG_PROVIDERS_CFG_FILE", None)

    def test_core_product_types_config_envvar(self):
        """product types should be loaded from file defined in env var"""
        # setup providers config
        config_path = os.path.join(TEST_RESOURCES_PATH, "file_providers_override.yml")
        providers_config: list[ProviderConfig] = cached_yaml_load_all(config_path)
        providers_config[0].products["TEST_PRODUCT_1"] = {"productType": "TP1"}
        providers_config[0].products["TEST_PRODUCT_2"] = {"productType": "TP2"}
        with open(
            os.path.join(self.tmp_home_dir.name, "file_providers_override2.yml"), "w"
        ) as f:
            f.write(yaml.dump(providers_config[0]))
        # set env variables
        os.environ["EODAG_PROVIDERS_CFG_FILE"] = os.path.join(
            self.tmp_home_dir.name, "file_providers_override2.yml"
        )
        os.environ["EODAG_PRODUCT_TYPES_CFG_FILE"] = os.path.join(
            TEST_RESOURCES_PATH, "file_product_types_override.yml"
        )

        # check product types
        try:
            self.dag = EODataAccessGateway()
            pt = self.dag.list_product_types(fetch_providers=False)
            self.assertEqual(2, len(pt))
            self.assertEqual("TEST_PRODUCT_1", pt[0]["ID"])
            self.assertEqual("TEST_PRODUCT_2", pt[1]["ID"])
        finally:
            # remove env variables
            os.environ.pop("EODAG_PROVIDERS_CFG_FILE", None)
            os.environ.pop("EODAG_PRODUCT_TYPES_CFG_FILE", None)


class TestCoreInvolvingConfDir(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestCoreInvolvingConfDir, cls).setUpClass()
        cls.dag = EODataAccessGateway()
        # mock os.environ to empty env
        cls.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        cls.mock_os_environ.start()

    @classmethod
    def tearDownClass(cls):
        super(TestCoreInvolvingConfDir, cls).tearDownClass()
        # stop os.environ
        cls.mock_os_environ.stop()

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

    def execution_involving_conf_dir(self, inspect=None, conf_dir=None):
        """Check that the path(s) inspected (str, list) are created after the instantation
        of EODataAccessGateway. If they were already there, rename them (.old), instantiate,
        check, delete the new files, and restore the existing files to there previous name.
        """
        if inspect is not None:
            if conf_dir is None:
                conf_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
            if isinstance(inspect, str):
                inspect = [inspect]
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

    def test_core_object_creates_locations_standard_location(self):
        """The core object must create a locations config file and a shp dir in standard user config location on instantiation"""  # noqa
        self.execution_involving_conf_dir(inspect=["locations.yml", "shp"])

    def test_read_only_home_dir(self):
        # standard directory
        home_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
        self.execution_involving_conf_dir(inspect="eodag.yml", conf_dir=home_dir)

        # user defined directory
        user_dir = os.path.join(os.path.expanduser("~"), ".config", "another_eodag")
        os.environ["EODAG_CFG_DIR"] = user_dir
        self.execution_involving_conf_dir(inspect="eodag.yml", conf_dir=user_dir)
        shutil.rmtree(user_dir)
        del os.environ["EODAG_CFG_DIR"]

        # fallback temporary folder
        def makedirs_side_effect(dir):
            if dir == os.path.join(os.path.expanduser("~"), ".config", "eodag"):
                raise OSError("Mock makedirs error")
            else:
                return makedirs(dir)

        with mock.patch(
            "eodag.api.core.makedirs", side_effect=makedirs_side_effect
        ) as mock_makedirs:
            # backup temp_dir if exists
            temp_dir = temp_dir_old = os.path.join(
                tempfile.gettempdir(), ".config", "eodag"
            )
            if os.path.exists(temp_dir):
                temp_dir_old = f"{temp_dir}.old"
                shutil.move(temp_dir, temp_dir_old)

            EODataAccessGateway()
            expected = [unittest.mock.call(home_dir), unittest.mock.call(temp_dir)]
            mock_makedirs.assert_has_calls(expected)
            self.assertTrue(os.path.exists(temp_dir))

            # restore temp_dir
            if temp_dir_old != temp_dir:
                try:
                    shutil.rmtree(temp_dir)
                except OSError:
                    os.unlink(temp_dir)
                shutil.move(temp_dir_old, temp_dir)


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
            "S2_MSI_L2A_COG",
            "S2_MSI_L2A_MAJA",
            "S2_MSI_L2B_MAJA_SNOW",
            "S2_MSI_L2B_MAJA_WATER",
            "EEA_DAILY_VI",
        ]
        self.assertListEqual(actual, expected)

        # with product type specified
        actual = self.dag.guess_product_type(productType="foo")
        self.assertListEqual(actual, ["foo"])

        # with dates
        self.assertEqual(
            self.dag.product_types_config.source["S2_MSI_L1C"]["missionStartDate"],
            "2015-06-23T00:00:00Z",
        )
        self.assertNotIn(
            "S2_MSI_L1C", self.dag.guess_product_type(missionEndDate="2015-06-01")
        )
        self.assertIn(
            "S2_MSI_L1C", self.dag.guess_product_type(missionEndDate="2015-07-01")
        )

        # with individual filters
        actual = self.dag.guess_product_type(
            platform="SENTINEL1", processingLevel="L2", intersect=True
        )
        self.assertListEqual(actual, ["S1_SAR_OCN"])
        # without intersect, the most appropriate product type must be at first position
        actual = self.dag.guess_product_type(platform="SENTINEL1", processingLevel="L2")
        self.assertGreater(len(actual), 1)
        self.assertEqual(actual[0], "S1_SAR_OCN")

    def test_guess_product_type_without_kwargs(self):
        """guess_product_type must raise an exception when no kwargs are provided"""
        with self.assertRaises(NoMatchingProductType):
            self.dag.guess_product_type()

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    def test__prepare_search_no_parameters(
        self, mock_auth_session_request, mock_fetch_product_types_list
    ):
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
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    def test__prepare_search_dates(
        self, mock_auth_session_request, mock_fetch_product_types_list
    ):
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
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    def test__prepare_search_geom(
        self, mock_auth_session_request, mock_fetch_product_types_list
    ):
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
    @mock.patch(
        "eodag.plugins.authentication.openid_connect.requests.sessions.Session.request",
        autospec=True,
    )
    def test__prepare_search_locations(
        self, mock_auth_session_request, mock_fetch_product_types_list
    ):
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
            products["S2_MSI_L1C"].pop("alias")

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
            self.dag.set_preferred_provider("cop_cds")
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
        return_value=(SearchResult([mock.Mock()], 1)),
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
        # max_items_per_page plugin conf
        mock_config = mock.Mock()
        type(mock_config).pagination = mock.PropertyMock(
            return_value={"max_items_per_page": 100}
        )
        type(mock_get_search_plugins.return_value[0]).config = mock.PropertyMock(
            return_value=mock_config
        )
        type(
            mock_get_search_plugins.return_value[0]
        ).next_page_query_obj = mock.PropertyMock(return_value={})
        # mocked search result id
        type(mock__do_search.return_value[0]).properties = mock.PropertyMock(
            return_value={"id": "foo"}
        )

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
            raise_errors=True,
            page=1,
            items_per_page=100,
        )
        self.assertEqual(found, mock__do_search.return_value)

        mock__do_search.reset_mock()
        # return None if more than 1 product is found
        mock__do_search.return_value = SearchResult([mock.Mock(), mock.Mock()], 2)
        type(mock__do_search.return_value[0]).properties = mock.PropertyMock(
            return_value={"id": "foo"}
        )
        type(mock__do_search.return_value[1]).properties = mock.PropertyMock(
            return_value={"id": "foo"}
        )
        with self.assertLogs(level="INFO") as cm:
            found = self.dag._search_by_id(uid="foo", productType="bar", provider="baz")
            self.assertEqual(found, SearchResult([], 0))
            self.assertIn("Several products found for this id", str(cm.output))

        mock__do_search.reset_mock()
        # return 1 result if more than 1 product is found but only 1 has the matching id
        mock__do_search.return_value = SearchResult([mock.Mock(), mock.Mock()], 2)
        type(mock__do_search.return_value[0]).properties = mock.PropertyMock(
            return_value={"id": "foo"}
        )
        type(mock__do_search.return_value[1]).properties = mock.PropertyMock(
            return_value={"id": "foooooo"}
        )
        found = self.dag._search_by_id(uid="foo", productType="bar", provider="baz")
        self.assertEqual(found.number_matched, 1)
        self.assertEqual(len(found), 1)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_support_itemsperpage_higher_than_maximum(self, search_plugin):
        """_do_search must support itemsperpage higher than maximum"""
        search_plugin.provider = "peps"
        search_plugin.query.return_value = (
            self.search_results.data,  # a list must be returned by .query
            self.search_results_size,
        )

        class DummyConfig:
            pagination = {"max_items_per_page": 1}

        search_plugin.config = DummyConfig()
        with self.assertLogs(level="WARNING") as cm:
            sr = self.dag._do_search(
                count=True,
                search_plugin=search_plugin,
                items_per_page=2,
            )
            self.assertIsInstance(sr, SearchResult)
            self.assertEqual(len(sr), self.search_results_size)
            self.assertEqual(sr.number_matched, self.search_results_size)
            self.assertIn(
                "Try to lower the value of 'items_per_page'",
                str(cm.output),
            )

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_counts(self, search_plugin):
        """_do_search must create a count query if specified"""
        search_plugin.provider = "peps"
        search_plugin.query.return_value = (
            self.search_results.data,  # a list must be returned by .query
            self.search_results_size,
        )

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        sr = self.dag._do_search(search_plugin=search_plugin, count=True)
        self.assertIsInstance(sr, SearchResult)
        self.assertEqual(len(sr), self.search_results_size)
        self.assertEqual(sr.number_matched, self.search_results_size)

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

        sr = self.dag._do_search(search_plugin=search_plugin, count=False)
        self.assertIsNone(sr.number_matched)
        self.assertEqual(len(sr), self.search_results_size)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_paginated_handle_no_count_returned(self, search_plugin):
        """_do_search must return None as count if provider does not return the count"""
        search_plugin.provider = "peps"
        search_plugin.query.return_value = (self.search_results.data, None)

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        page = 4
        sr = self.dag._do_search(
            count=True,
            search_plugin=search_plugin,
            page=page,
            items_per_page=2,
        )
        self.assertEqual(len(sr), self.search_results_size)
        self.assertIsNone(sr.number_matched)

    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test__do_search_paginated_handle_null_count(self, search_plugin):
        """_do_search must return provider response even if provider returns a null count"""
        search_plugin.provider = "peps"
        search_plugin.query.return_value = ([], 0)

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        page = 4
        items_per_page = 10
        sr = self.dag._do_search(
            count=True,
            search_plugin=search_plugin,
            page=page,
            items_per_page=items_per_page,
        )
        self.assertEqual(len(sr), 0)
        self.assertEqual(sr.number_matched, 0)

    def test__do_search_does_not_raise_by_default(self):
        """_do_search must not raise any error by default"""

        # provider attribute required internally by __do_search for logging purposes.
        class DummyConfig:
            pagination = {}

        class DummySearchPlugin:
            provider = "peps"
            config = DummyConfig()

        sr = self.dag._do_search(search_plugin=DummySearchPlugin(), count=True)
        self.assertIsInstance(sr, SearchResult)
        self.assertEqual(len(sr), 0)
        self.assertEqual(sr.number_matched, 0)

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

        sr = self.dag._do_search(search_plugin=search_plugin)
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
        sr = self.dag._do_search(search_plugin=search_plugin)
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

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.fetch_product_types_list", autospec=True
    )
    @mock.patch("eodag.api.core.EODataAccessGateway._do_search", autospec=True)
    def test_search_iter_page_count(self, mock_do_seach, mock_fetch_product_types_list):
        """search_iter_page must return an iterator"""
        mock_do_seach.side_effect = [
            self.search_results,
            self.search_results_2,
        ]

        # no count by default
        page_iterator = self.dag.search_iter_page(productType="S2_MSI_L1C")
        next(page_iterator)
        mock_do_seach.assert_called_once_with(
            mock.ANY,
            mock.ANY,
            productType="S2_MSI_L1C",
            geometry=None,
            raise_errors=True,
            page=1,
            items_per_page=DEFAULT_ITEMS_PER_PAGE,
        )

        # count only on 1st page if specified
        mock_do_seach.reset_mock()
        mock_do_seach.side_effect = [
            self.search_results,
            self.search_results_2,
        ]
        page_iterator = self.dag.search_iter_page(
            productType="S2_MSI_L1C", count=True, items_per_page=2
        )
        next(page_iterator)
        mock_do_seach.assert_called_once_with(
            mock.ANY,
            mock.ANY,
            productType="S2_MSI_L1C",
            geometry=None,
            count=True,
            raise_errors=True,
            page=1,
            items_per_page=2,
        )
        # 2nd page: no count
        next(page_iterator)
        self.assertEqual(mock_do_seach.call_count, 2)
        mock_do_seach.assert_called_with(
            mock.ANY,
            mock.ANY,
            productType="S2_MSI_L1C",
            geometry=None,
            count=False,
            raise_errors=True,
            page=2,
            items_per_page=2,
        )

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

    @mock.patch("eodag.plugins.search.qssearch.PostJsonSearch._request", autospec=True)
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch._request", autospec=True
    )
    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.normalize_results",
        autospec=True,
    )
    def test_search_sort_by(
        self,
        mock_normalize_results,
        mock_qssearch__request,
        mock_postjsonsearch__request,
    ):
        """search must sort results by sorting parameter(s) in their sorting order
        from the "sort_by" argument or by default sorting parameter if exists"""
        mock_qssearch__request.return_value.json.return_value = {
            "properties": {"totalResults": 2},
            "features": [],
            "links": [{"rel": "next", "href": "url/to/next/page"}],
        }
        mock_postjsonsearch__request.return_value.json.return_value = {
            "meta": {"found": 2},
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

        # with a GET mode search
        dummy_provider_config = """
        dummy_provider:
            search:
                type: QueryStringSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_url_tpl: '{url}?{search}'
                    total_items_nb_key_path: '$.properties.totalResults'
                sort:
                    sort_by_tpl: '&sortParam={sort_param}&sortOrder={sort_order}'
                    sort_param_mapping:
                        eodagSortParam: providerSortParam
                    sort_order_mapping:
                        ascending: asc
                        descending: desc
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
            sort_by=[("eodagSortParam", "DESC")],
        )

        # a provider-specific string has been created to sort by
        self.assertIn(
            "sortParam=providerSortParam&sortOrder=desc",
            mock_qssearch__request.call_args[0][1].url,
        )

        # with a POST mode search
        dummy_provider_config = """
        other_dummy_provider:
            search:
                type: PostJsonSearch
                api_endpoint: https://api.my_new_provider/search
                pagination:
                    next_page_query_obj: '{{"limit":{items_per_page},"page":{page}}}'
                    total_items_nb_key_path: '$.meta.found'
                sort:
                    sort_by_tpl: '{{"sort_by": [ {{"field": "{sort_param}", "direction": "{sort_order}" }} ] }}'
                    sort_param_mapping:
                        eodagSortParam: providerSortParam
                    sort_order_mapping:
                        ascending: asc
                        descending: desc
                metadata_mapping:
                    dummy: 'dummy'
            products:
                S2_MSI_L1C:
                    productType: '{productType}'
        """
        dag.update_providers_config(dummy_provider_config)
        dag.search(
            provider="other_dummy_provider",
            productType="S2_MSI_L1C",
            sort_by=[("eodagSortParam", "DESC")],
        )

        # a provider-specific dictionary has been created to sort by
        self.assertIn(
            "sort_by", mock_postjsonsearch__request.call_args[0][1].query_params.keys()
        )
        self.assertEqual(
            [{"field": "providerSortParam", "direction": "desc"}],
            mock_postjsonsearch__request.call_args[0][1].query_params["sort_by"],
        )

        # TODO: sort by default sorting parameter and sorting order

    def test_search_sort_by_raise_errors(self):
        """search used with "sort_by" argument must raise errors if the argument is incorrect or if the provider does
        not support a maximum number of sorting parameter, one sorting parameter or the sorting feature
        """
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
                sort_by=[("eodagSortParam", "ASC")],
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
                    sort_by_tpl: '&sortParam={sort_param}&sortOrder={sort_order}'
                    sort_param_mapping:
                        eodagSortParam: providerSortParam
                    sort_order_mapping:
                        ascending: asc
                        descending: desc
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
                sort_by=[("otherEodagSortParam", "ASC")],
            )
            self.assertIn(
                "\\'otherEodagSortParam\\' parameter is not sortable with dummy_provider. "
                "Here is the list of sortable parameter(s) with dummy_provider: eodagSortParam",
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
                    sort_by_tpl: '&sortParam={sort_param}&sortOrder={sort_order}'
                    sort_param_mapping:
                        eodagSortParam: providerSortParam
                        otherEodagSortParam: otherProviderSortParam
                    sort_order_mapping:
                        ascending: asc
                        descending: desc
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
                sort_by=[("eodagSortParam", "ASC"), ("otherEodagSortParam", "ASC")],
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


class TestCoreProviderGroup(TestCoreBase):
    # create a group with a provider which has product type discovery mechanism
    # and the other one which has not it to test different cases
    group = ("creodias", "earth_search")
    group_name = "testgroup"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.dag = EODataAccessGateway()
        providers_configs = cls.dag.providers_config

        setattr(providers_configs[cls.group[0]], "group", cls.group_name)
        setattr(providers_configs[cls.group[1]], "group", cls.group_name)

    def test_available_providers_by_group(self) -> None:
        """
        The method available_providers returns only one entry for both grouped providers
        """
        providers = self.dag.available_providers()

        # check that setting "by_group" argument to True removes names of grouped providers and add names of their group
        groups = []
        for provider, provider_config in self.dag.providers_config.items():
            provider_group = getattr(provider_config, "group", None)
            if provider_group and provider_group not in groups:
                groups.append(provider_group)
                providers.append(provider_group)
            if provider_group:
                providers.remove(provider)

        self.assertCountEqual(self.dag.available_providers(by_group=True), providers)

    def test_list_product_types(self) -> None:
        """
        List the product types for the provider group.
        EODAG return the merged list of product types from both providers of the group.
        """

        search_products = []
        for provider in self.group:
            search_products.extend(
                self.dag.list_product_types(provider, fetch_providers=False)
            )

        merged_list = list({d["ID"]: d for d in search_products}.values())

        self.assertCountEqual(
            self.dag.list_product_types(self.group_name, fetch_providers=False),
            merged_list,
        )

    @mock.patch("eodag.api.core.get_ext_product_types_conf", autospec=True)
    @mock.patch(
        "eodag.api.core.EODataAccessGateway.discover_product_types", autospec=True
    )
    def test_fetch_product_types_list_grouped_providers(
        self, mock_discover_product_types, mock_get_ext_product_types_conf
    ):
        """Core api must fetch product types list and update if needed"""
        # store providers config
        tmp_providers_config = copy.deepcopy(self.dag.providers_config)

        # check that no provider has already been fetched
        for provider_config in self.dag.providers_config.values():
            self.assertFalse(getattr(provider_config, "product_types_fetched", False))

        mock_get_ext_product_types_conf.return_value = {
            provider: {
                "providers_config": {"foo": {"productType": "foo"}},
                "product_types_config": {"foo": {"title": "Foo collection"}},
            }
            for provider in self.group
        }
        # add an empty ext-conf for other providers to prevent them to be fetched
        for provider, provider_config in self.dag.providers_config.items():
            if hasattr(provider_config, "search"):
                provider_search_config = provider_config.search
            elif hasattr(provider_config, "api"):
                provider_search_config = provider_config.api
            elif provider not in self.group:
                continue
            if (
                provider not in self.group
                and hasattr(provider_search_config, "discover_product_types")
                and provider_search_config.discover_product_types.get("fetch_url")
            ):
                mock_get_ext_product_types_conf.return_value[provider] = {}
            # update grouped providers conf and check that discover_product_types() is launched for them
            if provider in self.group and getattr(
                provider_search_config, "discover_product_types", {}
            ).get("fetch_url"):
                provider_search_config_key = (
                    "search" if hasattr(provider_config, "search") else "api"
                )
                self.dag.update_providers_config(
                    f"""
                    {provider}:
                        {provider_search_config_key}:
                            discover_product_types:
                                fetch_url: 'http://new-{provider}-endpoint'
                            """
                )

        # now check that if provider is specified, only this one is fetched
        with self.assertLogs(level="INFO") as cm:
            self.dag.fetch_product_types_list(provider=self.group_name)
            self.assertIn(
                f"Fetch product types for {self.group_name} group: {', '.join(self.group)}",
                str(cm.output),
            )

        # discover_product_types() should have been called one time per each provider of the group
        # which has product type discovery mechanism. dag configuration of these providers should have been updated
        for provider in self.group:
            if getattr(
                self.dag.providers_config[provider].search, "discover_product_types", {}
            ).get("fetch_url", False):
                self.assertTrue(
                    getattr(
                        self.dag.providers_config[provider],
                        "product_types_fetched",
                        False,
                    )
                )
                self.assertEqual(
                    self.dag.providers_config[provider].products["foo"],
                    {"productType": "foo"},
                )
                mock_discover_product_types.assert_called_with(
                    self.dag, provider=provider
                )
            else:
                self.assertFalse(
                    getattr(
                        self.dag.providers_config[provider],
                        "product_types_fetched",
                        False,
                    )
                )
                self.assertNotIn(
                    "foo", list(self.dag.providers_config[provider].products.keys())
                )

        self.assertEqual(
            self.dag.product_types_config.source["foo"],
            {"_id": "foo", "title": "Foo collection"},
        )

        # restore providers config
        self.dag.providers_config = tmp_providers_config

    @mock.patch(
        "eodag.plugins.search.qssearch.QueryStringSearch.discover_product_types",
        autospec=True,
        return_value={
            "providers_config": {"foo": {"productType": "foo"}},
            "product_types_config": {"foo": {"title": "Foo collection"}},
        },
    )
    def test_discover_product_types_grouped_providers(
        self, mock_plugin_discover_product_types
    ):
        """Core api must fetch grouped providers for product types"""
        with self.assertLogs(level="INFO") as cm:
            ext_product_types_conf = self.dag.discover_product_types(
                provider=self.group_name
            )
            self.assertIn(
                f"Discover product types for {self.group_name} group: {', '.join(self.group)}",
                str(cm.output),
            )

        self.assertIsNotNone(ext_product_types_conf)

        # discover_product_types() of providers search plugin should have been called one time per each provider
        # of the group which has product type discovery mechanism. Only config of these providers should have been
        # added in the external config
        mock_call_args_list = [
            mock_plugin_discover_product_types.call_args_list[i].args[0]
            for i in range(len(mock_plugin_discover_product_types.call_args_list))
        ]
        for provider in self.group:
            provider_search_plugin = next(
                self.dag._plugins_manager.get_search_plugins(provider=provider)
            )
            if getattr(
                self.dag.providers_config[provider].search, "discover_product_types", {}
            ).get("fetch_url", False):
                self.assertIn(provider_search_plugin, mock_call_args_list)
                self.assertEqual(
                    ext_product_types_conf[provider]["providers_config"]["foo"][
                        "productType"
                    ],
                    "foo",
                )
                self.assertEqual(
                    ext_product_types_conf[provider]["product_types_config"]["foo"][
                        "title"
                    ],
                    "Foo collection",
                )
            else:
                self.assertNotIn(provider_search_plugin, mock_call_args_list)
                self.assertNotIn(provider, list(ext_product_types_conf.keys()))

    def test_get_search_plugins(
        self,
    ) -> None:
        """
        The method _plugins_manager.get_search_plugins is called with provider group
        It returns a list containing the 2 grouped plugins
        """
        plugin1 = list(
            self.dag._plugins_manager.get_search_plugins(provider=self.group[0])
        )
        plugin2 = list(
            self.dag._plugins_manager.get_search_plugins(provider=self.group[1])
        )

        group_plugins = list(
            self.dag._plugins_manager.get_search_plugins(provider=self.group_name)
        )

        self.assertCountEqual(group_plugins, [*plugin1, *plugin2])


class TestCoreStrictMode(TestCoreBase):
    def setUp(self):
        super().setUp()
        # Ensure a clean environment for each test
        self.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        self.mock_os_environ.start()

        # This file removes TEST_PRODUCT_2 from the main config, in order to test strict and permissive behavior
        os.environ["EODAG_PRODUCT_TYPES_CFG_FILE"] = os.path.join(
            TEST_RESOURCES_PATH, "file_product_types_modes.yml"
        )
        os.environ["EODAG_PROVIDERS_CFG_FILE"] = os.path.join(
            TEST_RESOURCES_PATH, "file_providers_override.yml"
        )

    def tearDown(self):
        self.mock_os_environ.stop()
        super().tearDown()

    def test_list_product_types_strict_mode(self):
        """list_product_types must only return product types from the main config in strict mode"""
        try:
            os.environ["EODAG_STRICT_PRODUCT_TYPES"] = "true"
            dag = EODataAccessGateway()

            # In strict mode, TEST_PRODUCT_2 should not be listed
            product_types = dag.list_product_types(fetch_providers=False)
            ids = [pt["ID"] for pt in product_types]
            self.assertNotIn("TEST_PRODUCT_2", ids)

        finally:
            os.environ.pop("EODAG_STRICT_PRODUCT_TYPES", None)

    def test_list_product_types_permissive_mode(self):
        """list_product_types must include provider-only product types in permissive mode"""
        if "EODAG_STRICT_PRODUCT_TYPES" in os.environ:
            del os.environ["EODAG_STRICT_PRODUCT_TYPES"]

        dag = EODataAccessGateway()

        # In permissive mode, TEST_PRODUCT_2 should be listed
        product_types = dag.list_product_types(fetch_providers=False)
        ids = [pt["ID"] for pt in product_types]
        self.assertIn("TEST_PRODUCT_2", ids)
