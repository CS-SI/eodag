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
from shapely.geometry import LineString, MultiPolygon, Polygon

from eodag.utils import GENERIC_PRODUCT_TYPE
from tests import TEST_RESOURCES_PATH
from tests.context import (
    EODataAccessGateway,
    NoMatchingProductType,
    UnsupportedProvider,
    get_geometry_from_various,
    makedirs,
)
from tests.utils import mock


class TestCore(unittest.TestCase):
    SUPPORTED_PRODUCT_TYPES = {
        "L8_REFLECTANCE": ["theia"],
        "L57_REFLECTANCE": ["theia"],
        "L8_OLI_TIRS_C1L1": ["onda", "usgs", "aws_eos", "astraea_eod", "earth_search"],
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
            "earth_search",
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
            "earth_search",
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
            "earth_search",
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
        "earth_search",
    ]

    @classmethod
    def setUpClass(cls):
        cls.dag = EODataAccessGateway()
        cls.conf_dir = os.path.join(os.path.expanduser("~"), ".config", "eodag")

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
        """The core object must set the default locations config on instantiation"""  # noqa
        default_shpfile = os.path.join(
            self.conf_dir, "shp", "ne_110m_admin_0_map_units.shp"
        )
        self.assertIsInstance(self.dag.locations_config, list)
        self.assertEqual(
            self.dag.locations_config,
            [dict(attr="ADM0_A3_US", name="country", path=default_shpfile)],
        )

    def test_core_object_locations_file_not_found(self):
        """The core object must set the locations to an empty list when the file is not found"""  # noqa
        dag = EODataAccessGateway(locations_conf_path="no_locations.yml")
        self.assertEqual(dag.locations_config, [])

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


class TestCoreConfWithEnvVar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dag = EODataAccessGateway()

    @classmethod
    def tearDownClass(cls):
        if os.getenv("EODAG_CFG_FILE") is not None:
            os.environ.pop("EODAG_CFG_FILE")
        if os.getenv("EODAG_LOCS_CFG_FILE") is not None:
            os.environ.pop("EODAG_LOCS_CFG_FILE")

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
        """The core object must create a user config file in standard user config location on instantiation"""  # noqa
        self.execution_involving_conf_dir(inspect="eodag.yml")

    def test_core_object_creates_index_if_not_exist(self):
        """The core object must create an index in user config directory"""
        self.execution_involving_conf_dir(inspect=".index")

    def test_core_object_creates_locations_standard_location(self):
        """The core object must create a locations config file and a shp dir in standard user config location on instantiation"""  # noqa
        self.execution_involving_conf_dir(inspect=["locations.yml", "shp"])


class TestCoreGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        self.assertEquals(get_geometry_from_various([], geometry=geometry), ref_geom)
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
        self.assertEquals(get_geometry_from_various([], geometry=geometry), ref_geom)
        # List
        geometry = list(geometry)
        self.assertEquals(get_geometry_from_various([], geometry=geometry), ref_geom)
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
        # France + Guyana + Corsica + somewhere over Poland
        self.assertEquals(len(geom_combined), 4)
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
        self.assertEquals(len(geom_combined), 3)


class TestCoreSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dag = EODataAccessGateway()

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
            "S2_MSI_L2A_MAJA",
            "S2_MSI_L2B_MAJA_SNOW",
            "S2_MSI_L2B_MAJA_WATER",
            "S2_MSI_L3A_WASP",
        ]
        self.assertEqual(actual, expected)

    def test_guess_product_type_without_kwargs(self):
        """guess_product_type must raise an exception when no kwargs are provided"""
        with self.assertRaises(NoMatchingProductType):
            self.dag.guess_product_type()

    def test__prepare_search_no_parameters(self):
        """_prepare_search must create some kwargs even when no parameter has been provided"""  # noqa
        prepared_search = self.dag._prepare_search()
        expected = {
            "geometry": None,
            "locations": None,
            "productType": None,
        }
        self.assertDictContainsSubset(expected, prepared_search)

    def test__prepare_search_dates(self):
        """_prepare_search must handle start & end dates"""
        base = {
            "start": "2020-01-01",
            "end": "2020-02-01",
        }
        prepared_search = self.dag._prepare_search(**base)
        expected = {
            "startTimeFromAscendingNode": base["start"],
            "completionTimeFromAscendingNode": base["end"],
        }
        self.assertDictContainsSubset(expected, prepared_search)

    def test__prepare_search_geom(self):
        """_prepare_search must handle geom, box and bbox"""
        # The default way to provide a geom is through the 'geom' argument.
        base = {"geom": (0, 50, 2, 52)}
        # "geom": "POLYGON ((1 43, 1 44, 2 44, 2 43, 1 43))"
        prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        # 'box' and 'bbox' are supported for backwards compatibility,
        # The priority is geom > bbox > box
        base = {"box": (0, 50, 2, 52)}
        prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        base = {"bbox": (0, 50, 2, 52)}
        prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        base = {
            "geom": "POLYGON ((1 43, 1 44, 2 44, 2 43, 1 43))",
            "bbox": (0, 50, 2, 52),
            "box": (0, 50, 1, 51),
        }
        prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        self.assertNotIn("bbox", prepared_search)
        self.assertNotIn("bbox", prepared_search)
        self.assertIsInstance(prepared_search["geometry"], Polygon)

    def test__prepare_search_locations(self):
        """_prepare_search must handle a location search"""
        # When locations where introduced they could be passed
        # as regular kwargs. The new and recommended way to provide
        # them is through the 'locations' parameter.
        base = {"locations": {"country": "FRA"}}
        prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)

        # TODO: Remove this when support for locations kwarg is dropped.
        base = {"country": "FRA"}
        prepared_search = self.dag._prepare_search(**base)
        self.assertIn("geometry", prepared_search)
        self.assertNotIn("country", prepared_search)

    def test__prepare_search_product_type_provided(self):
        """_prepare_search must handle when a product type is given"""
        base = {"productType": "S2_MSI_L1C"}
        prepared_search = self.dag._prepare_search(**base)
        expected = {"productType": base["productType"]}
        self.assertDictContainsSubset(expected, prepared_search)

    def test__prepare_search_product_type_guess_it(self):
        """_prepare_search must guess a product type when required to"""
        # Uses guess_product_type to find the product matching
        # the best the given params.
        base = dict(
            instrument="MSI",
            platform="SENTINEL2",
            platformSerialIdentifier="S2A",
        )
        prepared_search = self.dag._prepare_search(**base)
        expected = {"productType": "S2_MSI_L1C", **base}
        self.assertDictContainsSubset(expected, prepared_search)

    def test__prepare_search_with_id(self):
        """_prepare_search must handle a search by id"""
        base = {"id": "dummy-id", "provider": "sobloo"}
        prepared_search = self.dag._prepare_search(**base)
        expected = base
        self.assertDictEqual(expected, prepared_search)

    def test__prepare_search_preserve_additional_kwargs(self):
        """_prepare_search must preserve additional kwargs"""
        base = {
            "productType": "S2_MSI_L1C",
            "cloudCover": 10,
        }
        prepared_search = self.dag._prepare_search(**base)
        expected = base
        self.assertDictContainsSubset(expected, prepared_search)

    def test__prepare_search_search_plugin_has_known_product_properties(self):
        """_prepare_search must attach the product properties to the search plugin"""
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("peps")
            base = {"productType": "S2_MSI_L1C"}
            prepared_search = self.dag._prepare_search(**base)
            # Just check that the title has been set correctly. There are more (e.g.
            # abstract, platform, etc.) but this is sufficient to check that the
            # product_type_config dict has been created and populated.
            self.assertEqual(
                prepared_search["search_plugin"].config.product_type_config["title"],
                "SENTINEL2 Level-1C",
            )
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

    def test__prepare_search_search_plugin_has_generic_product_properties(self):
        """_prepare_search must be able to attach the generic product properties to the search plugin"""  # noqa
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("peps")
            base = {"productType": "product_unknown_to_eodag"}
            prepared_search = self.dag._prepare_search(**base)
            # product_type_config is still created if the product is not known to eodag
            # however it contains no data.
            self.assertIsNone(
                prepared_search["search_plugin"].config.product_type_config["title"],
            )
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

    def test__prepare_search_peps_plugins_product_available(self):
        """_prepare_search must return the search and auth plugins when productType is defined"""  # noqa
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("peps")
            base = {"productType": "S2_MSI_L1C"}
            prepared_search = self.dag._prepare_search(**base)
            self.assertEqual(prepared_search["search_plugin"].provider, "peps")
            self.assertEqual(prepared_search["auth"].provider, "peps")
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)

    def test__prepare_search_no_plugins_when_search_by_id(self):
        """_prepare_search must not return the search and auth plugins for a search by id"""  # noqa
        base = {"id": "some_id", "provider": "some_provider"}
        prepared_search = self.dag._prepare_search(**base)
        self.assertNotIn("search_plugin", prepared_search)
        self.assertNotIn("auth", prepared_search)

    def test__prepare_search_peps_plugins_product_not_available(self):
        """_prepare_search can use another set of search and auth plugins than the ones of the preferred provider"""  # noqa
        # Document a special behaviour whereby the search and auth plugins don't
        # correspond to the preferred one. This occurs whenever the searched product
        # isn't available for the preferred provider but is made available by  another
        # one. In that case peps provides it and happens to be the first one on the list
        # of providers that make it available.
        prev_fav_provider = self.dag.get_preferred_provider()[0]
        try:
            self.dag.set_preferred_provider("theia")
            base = {"productType": "S2_MSI_L1C"}
            prepared_search = self.dag._prepare_search(**base)
            self.assertEqual(prepared_search["search_plugin"].provider, "peps")
            self.assertEqual(prepared_search["auth"].provider, "peps")
        finally:
            self.dag.set_preferred_provider(prev_fav_provider)
