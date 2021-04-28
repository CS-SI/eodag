# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, https://www.csgroup.eu/
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
import json
import os
import shutil
import unittest
from copy import deepcopy

from shapely import wkt
from shapely.geometry import LineString, MultiPolygon, Polygon

from eodag.utils import GENERIC_PRODUCT_TYPE
from tests import TEST_RESOURCES_PATH
from tests.context import (
    DEFAULT_MAX_ITEMS_PER_PAGE,
    EODataAccessGateway,
    EOProduct,
    NoMatchingProductType,
    PluginImplementationError,
    SearchResult,
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
            "astraea_eod",
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
        "S2_MSI_L2A_COG": ["earth_search_cog"],
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
            "usgs",
            "creodias",
            "astraea_eod",
            "usgs_satapi_aws",
            "earth_search",
            "earth_search_cog",
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
        "earth_search_cog",
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
        self.assertEqual(len(geom_france), 3)  # France + Guyana + Corsica

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
        self.assertEqual(len(geom_regex_pa), 2)

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
        self.assertEqual(len(geom_combined), 4)
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
        self.assertEqual(len(geom_combined), 3)


class TestCoreSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        search_results_data_2 = deepcopy(cls.search_results.data)
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
            "S2_MSI_L3A_WASP",
        ]
        self.assertEqual(actual, expected)

    def test_guess_product_type_without_kwargs(self):
        """guess_product_type must raise an exception when no kwargs are provided"""
        with self.assertRaises(NoMatchingProductType):
            self.dag.guess_product_type()

    def test_guess_product_type_has_no_limit(self):
        """guess_product_type must run a whoosh search without any limit"""
        # Filter that should give more than 10 products referenced in the catalog.
        opt_prods = [
            p for p in self.dag.list_product_types() if p["sensorType"] == "OPTICAL"
        ]
        if len(opt_prods) <= 10:
            self.skipTest("This test requires that more than 10 products are 'OPTICAL'")
        guesses = self.dag.guess_product_type(
            sensorType="OPTICAL",
        )
        self.assertGreater(len(guesses), 10)

    def test__prepare_search_no_parameters(self):
        """_prepare_search must create some kwargs even when no parameter has been provided"""  # noqa
        prepared_search = self.dag._prepare_search()
        expected = {
            "geometry": None,
            "productType": None,
        }
        expected = set(["geometry", "productType", "auth", "search_plugin"])
        self.assertSetEqual(expected, set(prepared_search))

    def test__prepare_search_dates(self):
        """_prepare_search must handle start & end dates"""
        base = {
            "start": "2020-01-01",
            "end": "2020-02-01",
        }
        prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(prepared_search["startTimeFromAscendingNode"], base["start"])
        self.assertEqual(
            prepared_search["completionTimeFromAscendingNode"], base["end"]
        )

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
        prepared_search = self.dag._prepare_search(**base)
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
        prepared_search = self.dag._prepare_search(**base)
        self.assertEqual(len(base.keys() & prepared_search.keys()), 0)

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
        self.assertEqual(prepared_search["productType"], base["productType"])
        self.assertEqual(prepared_search["cloudCover"], base["cloudCover"])

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
        """_do_search must provide a best estimate when a provider doesn't return a count"""  # noqa
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
        """_do_search must provide a best estimate when a provider returns a fuzzy count"""  # noqa
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
        """_do_search must provide a best estimate when a provider returns a null count"""  # noqa
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
        """_do_search must register each product's downloader if search_intersection is not None"""  # noqa
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
        prepare_seach.return_value = dict(search_plugin=search_plugin)
        page_iterator = self.dag.search_iter_page(items_per_page=2)
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
        """search_iter_page must stop as soon as less than items_per_page products were retrieved"""  # noqa
        search_plugin.provider = "peps"
        search_plugin.query.side_effect = [
            (self.search_results.data, None),
            ([self.search_results_2.data[0]], None),
        ]

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()
        prepare_seach.return_value = dict(search_plugin=search_plugin)
        page_iterator = self.dag.search_iter_page(items_per_page=2)
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
        prepare_seach.return_value = dict(search_plugin=search_plugin)
        page_iterator = self.dag.search_iter_page(items_per_page=2)
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
        prepare_seach.return_value = dict(search_plugin=search_plugin)
        page_iterator = self.dag.search_iter_page()
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

        page_iterator = dag.search_iter_page(productType="S2_MSI_L1C")
        next(page_iterator)
        search_plugin = next(
            dag._plugins_manager.get_search_plugins(product_type="S2_MSI_L1C")
        )
        self.assertIsNone(search_plugin.next_page_url)
        self.assertEqual(
            search_plugin.config.pagination["next_page_url_tpl"],
            "dummy_next_page_url_tpl",
        )

    @mock.patch("eodag.api.core.EODataAccessGateway._prepare_search", autospec=True)
    @mock.patch("eodag.plugins.search.qssearch.QueryStringSearch", autospec=True)
    def test_search_all_must_collect_them_all(self, search_plugin, prepare_seach):
        """search_all must return all the products available"""  # noqa
        search_plugin.provider = "peps"
        search_plugin.query.side_effect = [
            (self.search_results.data, None),
            ([self.search_results_2.data[0]], None),
        ]

        class DummyConfig:
            pagination = {}

        search_plugin.config = DummyConfig()

        # Infinite generator her because passing directly the dict to
        # prepare_search.return_value (or side_effect) didn't work. One function
        # would do a dict.pop("search_plugin") that would remove the item from the
        # mocked return value. Later calls would then break
        def yield_search_plugin():
            while True:
                yield {"search_plugin": search_plugin}

        prepare_seach.side_effect = yield_search_plugin()
        all_results = self.dag.search_all(items_per_page=2)
        self.assertIsInstance(all_results, SearchResult)
        self.assertEqual(len(all_results), 3)

    @mock.patch("eodag.api.core.EODataAccessGateway.search_iter_page", autospec=True)
    def test_search_all_use_max_items_per_page(self, mocked_search_iter_page):
        """search_all must use the configured parameter max_items_per_page if available"""  # noqa
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

    @mock.patch("eodag.api.core.EODataAccessGateway.search_iter_page", autospec=True)
    def test_search_all_use_default_value(self, mocked_search_iter_page):
        """search_all must use the DEFAULT_MAX_ITEMS_PER_PAGE if the provider's one wasn't configured"""  # noqa
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

    @mock.patch("eodag.api.core.EODataAccessGateway.search_iter_page", autospec=True)
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
