# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, http://www.c-s.fr
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

import glob
import os
import shutil
import unittest

from shapely import wkt
from shapely.geometry import LineString, MultiPolygon

from eodag.utils import GENERIC_PRODUCT_TYPE
from tests import TEST_RESOURCES_PATH
from tests.context import (
    EODataAccessGateway,
    UnsupportedProvider,
    get_geometry_from_various,
    makedirs,
)
from tests.utils import mock


class TestCore(unittest.TestCase):
    SUPPORTED_PRODUCT_TYPES = {
        "L8_REFLECTANCE": ["theia"],
        "L57_REFLECTANCE": ["theia"],
        "L8_OLI_TIRS_C1L1": ["onda", "usgs", "aws_eos", "astraea_eod"],
        "LANDSAT_C2L1": ["usgs_satapi_aws"],
        "LANDSAT_C2L2_SR": ["usgs_satapi_aws"],
        "LANDSAT_C2L2_ST": ["usgs_satapi_aws"],
        "LANDSAT_C2L2ALB_BT": ["usgs_satapi_aws"],
        "LANDSAT_C2L2ALB_SR": ["usgs_satapi_aws"],
        "LANDSAT_C2L2ALB_ST": ["usgs_satapi_aws"],
        "LANDSAT_C2L2ALB_TA": ["usgs_satapi_aws"],
        "S1_SAR_GRD": [
            "peps",
            "sobloo",
            "onda",
            "wekeo",
            "mundi",
            "creodias",
            "aws_eos",
        ],
        "S1_SAR_OCN": ["peps", "sobloo", "onda", "creodias"],
        "S1_SAR_RAW": ["sobloo", "onda", "creodias"],
        "S1_SAR_SLC": ["peps", "sobloo", "onda", "wekeo", "mundi", "creodias"],
        "S2_MSI_L2A": [
            "onda",
            "mundi",
            "creodias",
            "peps",
            "aws_eos",
            "sobloo",
            "astraea_eod",
        ],
        "S2_MSI_L2A_MAJA": ["theia"],
        "S2_MSI_L2B_MAJA_SNOW": ["theia"],
        "S2_MSI_L2B_MAJA_WATER": ["theia"],
        "S2_MSI_L3A_WASP": ["theia"],
        "S2_MSI_L1C": [
            "aws_eos",
            "peps",
            "sobloo",
            "onda",
            "wekeo",
            "mundi",
            "creodias",
            "astraea_eod",
        ],
        "S3_ERR": ["peps", "onda", "wekeo", "creodias"],
        "S3_EFR": ["peps", "onda", "wekeo", "creodias"],
        "S3_LAN": ["peps", "onda", "wekeo", "creodias"],
        "S3_SRA": ["onda", "wekeo", "creodias"],
        "S3_SRA_BS": ["onda", "wekeo", "creodias"],
        "S3_SRA_A_BS": ["onda", "creodias"],
        "S3_WAT": ["onda", "wekeo", "creodias"],
        "S3_OLCI_L2LFR": ["peps", "onda", "wekeo", "creodias", "mundi"],
        "S3_OLCI_L2LRR": ["peps", "onda", "wekeo", "creodias"],
        "S3_SLSTR_L1RBT": ["peps", "onda", "wekeo", "creodias"],
        "S3_SLSTR_L2LST": ["peps", "onda", "wekeo", "creodias"],
        "PLD_PAN": ["theia"],
        "PLD_XS": ["theia"],
        "PLD_BUNDLE": ["theia"],
        "PLD_PANSHARPENED": ["theia"],
        "CBERS4_PAN10M_L2": ["aws_eos"],
        "CBERS4_PAN10M_L4": ["aws_eos"],
        "CBERS4_PAN5M_L2": ["aws_eos"],
        "CBERS4_PAN5M_L4": ["aws_eos"],
        "CBERS4_MUX_L2": ["aws_eos"],
        "CBERS4_MUX_L4": ["aws_eos"],
        "CBERS4_AWFI_L2": ["aws_eos"],
        "CBERS4_AWFI_L4": ["aws_eos"],
        "MODIS_MCD43A4": ["aws_eos", "astraea_eod"],
        "NAIP": ["aws_eos", "astraea_eod"],
        "SPOT_SWH": ["theia"],
        "SPOT_SWH_OLD": ["theia"],
        "SPOT5_SPIRIT": ["theia"],
        "VENUS_L1C": ["theia"],
        "VENUS_L2A_MAJA": ["theia"],
        "VENUS_L3A_MAJA": ["theia"],
        "OSO": ["theia"],
        GENERIC_PRODUCT_TYPE: [
            "theia",
            "peps",
            "sobloo",
            "onda",
            "mundi",
            "creodias",
            "astraea_eod",
            "usgs_satapi_aws",
        ],
    }
    SUPPORTED_PROVIDERS = [
        "peps",
        "usgs",
        "theia",
        "sobloo",
        "creodias",
        "mundi",
        "onda",
        "wekeo",
        "aws_eos",
        "astraea_eod",
        "usgs_satapi_aws",
    ]

    def setUp(self):
        super(TestCore, self).setUp()
        self.dag = EODataAccessGateway()

    def tearDown(self):
        super(TestCore, self).tearDown()
        for old in glob.glob1(self.dag.conf_dir, "*.old") + glob.glob1(
            self.dag.conf_dir, ".*.old"
        ):
            old_path = os.path.join(self.dag.conf_dir, old)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    shutil.rmtree(old_path)
        if os.getenv("EODAG_CFG_FILE") is not None:
            os.environ.pop("EODAG_CFG_FILE")
        if os.getenv("EODAG_LOCS_CFG_FILE") is not None:
            os.environ.pop("EODAG_LOCS_CFG_FILE")

    def test_supported_providers_in_unit_test(self):
        """Every provider must be referenced in the core unittest SUPPORTED_PROVIDERS class attribute"""  # noqa
        for provider in self.dag.available_providers():
            self.assertIn(provider, self.SUPPORTED_PROVIDERS)

    def test_supported_product_types_in_unit_test(self):
        """Every product type must be referenced in the core unit test SUPPORTED_PRODUCT_TYPES class attribute"""  # noqa
        for product_type in self.dag.list_product_types():
            self.assertIn(product_type["ID"], self.SUPPORTED_PRODUCT_TYPES.keys())

    def test_list_product_types_ok(self):
        """Core api must correctly return the list of supported product types"""
        product_types = self.dag.list_product_types()
        self.assertIsInstance(product_types, list)
        for product_type in product_types:
            self.assertListProductTypesRightStructure(product_type)
        # There should be no repeated product type in the output
        self.assertEqual(len(product_types), len(set(pt["ID"] for pt in product_types)))

    def test_list_product_types_for_provider_ok(self):
        """Core api must correctly return the list of supported product types for a given provider"""  # noqa
        for provider in self.SUPPORTED_PROVIDERS:
            product_types = self.dag.list_product_types(provider=provider)
            self.assertIsInstance(product_types, list)
            for product_type in product_types:
                self.assertListProductTypesRightStructure(product_type)
                self.assertIn(
                    provider, self.SUPPORTED_PRODUCT_TYPES[product_type["ID"]]
                )

    def test_list_product_types_for_unsupported_provider(self):
        """Core api must raise UnsupportedProvider error for list_product_types with unsupported provider"""  # noqa
        unsupported_provider = "a"
        self.assertRaises(
            UnsupportedProvider,
            self.dag.list_product_types,
            provider=unsupported_provider,
        )

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
        self.assertIn(structure["ID"], self.SUPPORTED_PRODUCT_TYPES)

    def test_core_object_creates_config_standard_location(self):
        """The core object must create a user config file in standard user config location on instantiation"""  # noqa
        self.execution_involving_conf_dir(inspect="eodag.yml")

    def test_core_object_creates_index_if_not_exist(self):
        """The core object must create an index in user config directory"""
        self.execution_involving_conf_dir(inspect=".index")

    @mock.patch("eodag.api.core.open_dir", autospec=True)
    @mock.patch("eodag.api.core.exists_in", autospec=True, return_value=True)
    def test_core_object_open_index_if_exists(self, exists_in_mock, open_dir_mock):
        """The core object must use the existing index dir if any"""
        conf_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
        index_dir = os.path.join(conf_dir, ".index")
        if not os.path.exists(index_dir):
            makedirs(index_dir)
        EODataAccessGateway()
        open_dir_mock.assert_called_with(index_dir)

    def test_core_object_prioritize_config_file_in_envvar(self):
        """The core object must use the config file pointed to by the EODAG_CFG_FILE env var"""  # noqa
        os.environ["EODAG_CFG_FILE"] = os.path.join(
            TEST_RESOURCES_PATH, "file_config_override.yml"
        )
        dag = EODataAccessGateway()
        # usgs priority is set to 5 in the test config overrides
        self.assertEqual(dag.get_preferred_provider(), ("usgs", 5))
        # peps outputs prefix is set to /data
        self.assertEqual(dag.providers_config["peps"].download.outputs_prefix, "/data")

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

    def test_core_object_creates_locations_standard_location(self):
        """The core object must create a locations config file and a shp dir in standard user config location on instantiation"""  # noqa
        self.execution_involving_conf_dir(inspect=["locations.yml", "shp"])

    def test_core_object_set_default_locations_config(self):
        """The core object must set the default locations config on instantiation"""  # noqa
        dag = EODataAccessGateway()
        conf_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")
        default_shpfile = os.path.join(conf_dir, "shp", "ne_110m_admin_0_map_units.shp")
        self.assertIsInstance(dag.locations_config, list)
        self.assertEqual(
            dag.locations_config,
            [dict(attr="ADM0_A3_US", name="country", path=default_shpfile)],
        )

    def test_core_object_locations_file_not_found(self):
        """The core object must set the locations to an empty list when the file is not found"""  # noqa
        dag = EODataAccessGateway(locations_conf_path="no_locations.yml")
        self.assertEqual(dag.locations_config, [])

    def test_core_object_prioritize_locations_file_in_envvar(self):
        """The core object must use the locations file pointed to by the EODAG_LOCS_CFG_FILE env var"""  # noqa
        os.environ["EODAG_LOCS_CFG_FILE"] = os.path.join(
            TEST_RESOURCES_PATH, "file_locations_override.yml"
        )
        dag = EODataAccessGateway()
        self.assertEqual(
            dag.locations_config,
            [dict(attr="dummyattr", name="dummyname", path="dummypath.shp")],
        )

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
        self.assertEquals(get_geometry_from_various([], geometry=geometry), ref_geom)
        # Bad dict with a missing key
        del geometry["lonmin"]
        self.assertRaises(
            TypeError, get_geometry_from_various, [], geometry=geometry,
        )
        # Tuple
        geometry = (0, 50, 2, 52)
        self.assertEquals(get_geometry_from_various([], geometry=geometry), ref_geom)
        # List
        geometry = list(geometry)
        self.assertEquals(get_geometry_from_various([], geometry=geometry), ref_geom)
        # List without 4 items
        geometry.pop()
        self.assertRaises(
            TypeError, get_geometry_from_various, [], geometry=geometry,
        )
        # WKT
        geometry = ref_geom_as_wkt
        self.assertEquals(get_geometry_from_various([], geometry=geometry), ref_geom)
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
        self.assertEquals(len(geom_france), 3)  # France + Guyana + Corsica

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
        self.assertEquals(len(geom_regex_pa), 2)

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
        self.assertEquals(
            len(geom_combined), 4
        )  # France + Guyana + Corsica + somewhere over Poland
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
        self.assertEquals(
            len(geom_combined), 3
        )  # The bounding box overlaps with France inland

    def test_rebuild_index(self):
        """Change eodag version and check that whoosh index is rebuilt"""

        index_dir = os.path.join(self.dag.conf_dir, ".index")
        index_dir_mtime = os.path.getmtime(index_dir)

        self.assertNotEqual(self.dag.get_version(), "fake-version")

        with mock.patch(
            "eodag.api.core.EODataAccessGateway.get_version",
            autospec=True,
            return_value="fake-version",
        ):
            self.assertEqual(self.dag.get_version(), "fake-version")

            self.dag.build_index()

            # check that index_dir has beeh re-created
            self.assertNotEqual(os.path.getmtime(index_dir), index_dir_mtime)
