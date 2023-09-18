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

from jsonpath_ng.ext import parse
from lxml import etree
from shapely import wkt

from tests.context import (
    NOT_AVAILABLE,
    format_metadata,
    get_geometry_from_various,
    properties_from_json,
)


class TestMetadataFormatter(unittest.TestCase):
    def test_convert_datetime_to_timestamp_milliseconds(self):
        to_format = "{fieldname#datetime_to_timestamp_milliseconds}"
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T18:27:19.123Z"),
            "1619029639123",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T18:27:19.123"),
            "1619029639123",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21"), "1618963200000"
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T00:00:00+02:00"),
            "1618956000000",
        )

    def test_convert_to_iso_utc_datetime_from_milliseconds(self):
        to_format = "{fieldname#to_iso_utc_datetime_from_milliseconds}"
        self.assertEqual(
            format_metadata(to_format, fieldname=1619029639123),
            "2021-04-21T18:27:19.123Z",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname=1618963200000),
            "2021-04-21T00:00:00.000Z",
        )

    def test_convert_to_iso_utc_datetime(self):
        to_format = "{fieldname#to_iso_utc_datetime}"
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T18:27:19.123Z"),
            "2021-04-21T18:27:19.123Z",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T18:27:19.123"),
            "2021-04-21T18:27:19.123Z",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21"),
            "2021-04-21T00:00:00.000Z",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T00:00:00.000+02:00"),
            "2021-04-20T22:00:00.000Z",
        )

    def test_convert_to_iso_date(self):
        to_format = "{fieldname#to_iso_date}"
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T18:27:19.123Z"),
            "2021-04-21",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T18:27:19.123"),
            "2021-04-21",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21"), "2021-04-21"
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="2021-04-21T00:00:00+06:00"),
            "2021-04-20",
        )

    def test_convert_to_rounded_wkt(self):
        to_format = "{fieldname#to_rounded_wkt}"
        geom = get_geometry_from_various(geometry="POINT (0.11111 1.22222222)")
        self.assertEqual(
            format_metadata(to_format, fieldname=geom),
            "POINT (0.1111 1.2222)",
        )

    def test_convert_to_bounds_lists(self):
        to_format = "{fieldname#to_bounds_lists}"
        geom = get_geometry_from_various(
            geometry="""MULTIPOLYGON (
                ((1.23 43.42, 1.23 43.76, 1.68 43.76, 1.68 43.42, 1.23 43.42)),
                ((2.23 43.42, 2.23 43.76, 3.68 43.76, 3.68 43.42, 2.23 43.42))
            )"""
        )
        self.assertEqual(
            format_metadata(to_format, fieldname=geom),
            "[[2.23, 43.42, 3.68, 43.76], [1.23, 43.42, 1.68, 43.76]]",
        )

    def test_convert_to_geojson(self):
        to_format = "{fieldname#to_geojson}"
        geom = get_geometry_from_various(geometry="POINT (0.11 1.22)")
        self.assertEqual(
            format_metadata(to_format, fieldname=geom),
            '{"type": "Point", "coordinates": [0.11, 1.22]}',
        )

    def test_convert_from_ewkt(self):
        to_format = "{fieldname#from_ewkt}"
        wkt_str = format_metadata(
            to_format, fieldname="SRID=3857;POINT (321976 5390999)"
        )
        geom = wkt.loads(wkt_str)
        self.assertEqual(round(geom.x, 1), 2.9)
        self.assertEqual(round(geom.y, 1), 43.5)

    def test_convert_to_ewkt(self):
        to_format = "{fieldname#to_ewkt}"
        geom = get_geometry_from_various(geometry="POINT (0.11 1.22)")
        self.assertEqual(
            format_metadata(to_format, fieldname=geom),
            "SRID=4326;POINT (0.1100 1.2200)",
        )

    def test_convert_from_georss(self):
        to_format = "{fieldname#from_georss}"
        # polygon
        georss = etree.Element("polygon")
        georss.text = "1.23 43.42 1.23 43.76 1.68 43.76 1.68 43.42 1.23 43.42"
        geom = format_metadata(to_format, fieldname=georss)
        self.assertEqual(
            geom,
            "POLYGON ((1.23 43.42, 1.23 43.76, 1.68 43.76, 1.68 43.42, 1.23 43.42))",
        )
        # multipolygon
        georss = etree.Element("where")
        sub_multipolygon = etree.SubElement(georss, "Multisurface")
        sub_polygon1 = etree.SubElement(sub_multipolygon, "foo")
        sub_polygon1.text = "1.23 43.42 1.23 43.76 1.68 43.76 1.68 43.42 1.23 43.42"
        sub_polygon2 = etree.SubElement(sub_multipolygon, "bar")
        sub_polygon2.text = "2.23 43.42 2.23 43.76 3.68 43.76 3.68 43.42 2.23 43.42"
        geom = format_metadata(to_format, fieldname=georss)
        self.assertEqual(
            geom,
            (
                "MULTIPOLYGON ("
                "((1.23 43.42, 1.23 43.76, 1.68 43.76, 1.68 43.42, 1.23 43.42)), "
                "((2.23 43.42, 2.23 43.76, 3.68 43.76, 3.68 43.42, 2.23 43.42))"
                ")"
            ),
        )
        # multipolygon in different projection
        georss = etree.Element("where")
        sub_multipolygon = etree.SubElement(georss, "Multisurface")
        sub_multipolygon.attrib["srsName"] = "EPSG:3857"
        sub_polygon1 = etree.SubElement(sub_multipolygon, "foo")
        sub_polygon1.text = (
            "136923 5376120 136923 5428376 187017 5428376 187017 5376120 136923 5376120"
        )
        sub_polygon2 = etree.SubElement(sub_multipolygon, "bar")
        sub_polygon2.text = (
            "248242 5376120 248242 5428376 409655 5428376 409655 5376120 248242 5376120"
        )
        wkt_str = format_metadata(to_format, fieldname=georss)
        geom = wkt.loads(wkt_str)
        self.assertEqual(len(geom.geoms), 2)
        self.assertEqual(
            [round(x, 2) for x in geom.geoms[0].bounds], [1.23, 43.42, 1.68, 43.76]
        )
        self.assertEqual(
            [round(x, 2) for x in geom.geoms[1].bounds], [2.23, 43.42, 3.68, 43.76]
        )

    def test_convert_csv_list(self):
        to_format = "{fieldname#csv_list}"
        self.assertEqual(
            format_metadata(to_format, fieldname=[1, 2, 3]),
            "1,2,3",
        )

    def test_convert_remove_extension(self):
        to_format = "{fieldname#remove_extension}"
        self.assertEqual(
            format_metadata(to_format, fieldname="foo.bar"),
            "foo",
        )

    def test_convert_get_group_name(self):
        to_format = (
            "{fieldname#get_group_name((?P<this_is_foo>foo)|(?P<that_is_bar>bar))}"
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="foo"),
            "this_is_foo",
        )

    def test_convert_replace_str(self):
        to_format = r"{fieldname#replace_str(r'(.*) is (.*)',r'\1 was \2...')}"
        self.assertEqual(
            format_metadata(to_format, fieldname="this is foo"),
            "this was foo...",
        )

    def test_convert_recursive_sub_str(self):
        to_format = r"{fieldname#recursive_sub_str(r'(.*) is (.*)',r'\1 was \2...')}"
        self.assertEqual(
            format_metadata(
                to_format, fieldname=[{"a": "this is foo", "b": [{"c": "that is bar"}]}]
            ),
            "[{'a': 'this was foo...', 'b': [{'c': 'that was bar...'}]}]",
        )

    def test_convert_dict_update(self):
        to_format = '{fieldname#dict_update([["b",[["href","bar"],["title","baz"]]]])}'
        self.assertEqual(
            format_metadata(to_format, fieldname={"a": {"title": "foo"}}),
            "{'a': {'title': 'foo'}, 'b': {'href': 'bar', 'title': 'baz'}}",
        )

    def test_convert_slice_str(self):
        to_format = "{fieldname#slice_str(1,12,2)}"
        self.assertEqual(
            format_metadata(to_format, fieldname="abcdefghijklmnop"),
            "bdfhjl",
        )

    def test_convert_fake_l2a_title_from_l1c(self):
        to_format = "{fieldname#fake_l2a_title_from_l1c}"
        self.assertEqual(
            format_metadata(
                to_format,
                fieldname="S2B_MSIL1C_20210427T103619_N0300_R008_T31TCJ_20210427T124539",
            ),
            "S2B_MSIL2A_20210427T103619____________T31TCJ________________",
        )

    def test_convert_s2msil2a_title_to_aws_productinfo(self):
        to_format = "{fieldname#s2msil2a_title_to_aws_productinfo}"
        self.assertEqual(
            format_metadata(
                to_format,
                fieldname="S2A_MSIL2A_20201201T100401_N0214_R122_T32SNA_20201201T114520",
            ),
            "https://roda.sentinel-hub.com/sentinel-s2-l2a/tiles/32/S/NA/2020/12/1/0/{collection}.json",
        )

    def test_format_stac_extension_parameter(self):
        to_format = "{some_extension:a_parameter}"
        self.assertEqual(
            format_metadata(to_format, **{"some_extension:a_parameter": "value"}),
            "value",
        )

    def test_properties_from_json_discovery_config(self):
        """properties_from_json must extract and discover metadata"""
        json = {
            "foo": "foo-val",
            "bar": "bar-val",
            "baz": {"baaz": "baz-val"},
            "qux": [
                {"somekey": "a", "someval": "a-val"},
                {"somekey": "b", "someval": "b-val", "some": "thing"},
                {"somekey": "c"},
                {"someval": "d-val"},
            ],
            "ignored": "ignored-val",
        }
        mapping = {
            "fooProperty": (None, parse("$.foo")),
            "missingProperty": (None, parse("$.missing")),
        }
        # basic discovery
        discovery_config = {
            "auto_discovery": True,
            "metadata_pattern": r"^(?!ignored)[a-zA-Z0-9_]+$",
            "metadata_path": "$.*",
        }
        properties = properties_from_json(
            json=json, mapping=mapping, discovery_config=discovery_config
        )
        self.assertDictEqual(
            properties,
            {
                "fooProperty": "foo-val",
                "bar": "bar-val",
                "baz": {"baaz": "baz-val"},
                "missingProperty": NOT_AVAILABLE,
                "qux": [
                    {"somekey": "a", "someval": "a-val"},
                    {"somekey": "b", "someval": "b-val", "some": "thing"},
                    {"somekey": "c"},
                    {"someval": "d-val"},
                ],
            },
        )
        # advanced discovery
        discovery_config = {
            "auto_discovery": True,
            "metadata_pattern": r"^(?!ignored)[a-zA-Z0-9_]+$",
            "metadata_path": "$.qux[*]",
            "metadata_path_id": "somekey",
            "metadata_path_value": "someval",
        }
        properties = properties_from_json(
            json=json, mapping=mapping, discovery_config=discovery_config
        )
        self.assertDictEqual(
            properties,
            {
                "fooProperty": "foo-val",
                "missingProperty": NOT_AVAILABLE,
                "a": "a-val",
                "b": "b-val",
                "c": NOT_AVAILABLE,
            },
        )

    def test_convert_split_id_into_s1_params(self):
        to_format = "{id#split_id_into_s1_params}"
        expected = {
            "sensorMode": "IW",
            "processingLevel": "LEVEL1",
            "startDate": "2014-11-26T23:08:43Z",
            "endDate": "2014-11-26T23:09:05Z",
            "productType": "GRD-COG",
            "polarisation": "VV+VH",
        }
        self.assertEqual(
            format_metadata(
                to_format,
                id="S1A_IW_GRDH_1SDV_20141126T230844_20141126T230904_003459_0040CE_E073_COG",
            ),
            str(expected),
        )

    def test_convert_get_processing_level_from_s1_id(self):
        to_format = "{id#get_processing_level_from_s1_id}"
        self.assertEqual(
            format_metadata(
                to_format,
                id="S1A_IW_GRDH_1SDV_20141126T230844_20141126T230904_003459_0040CE_E073_COG",
            ),
            "LEVEL1",
        )

    def test_convert_get_sensor_mode_from_s1_id(self):
        to_format = "{id#get_sensor_mode_from_s1_id}"
        self.assertEqual(
            format_metadata(
                to_format,
                id="S1A_IW_GRDH_1SDV_20141126T230844_20141126T230904_003459_0040CE_E073_COG",
            ),
            "IW",
        )

    def test_convert_get_processing_level_from_s2_id(self):
        to_format = "{id#get_processing_level_from_s2_id}"
        self.assertEqual(
            format_metadata(
                to_format,
                id="S2A_MSIL1C_20160602T065342_N0202_R077_T39KVU_20160602T065342",
            ),
            "S2MSIL1C",
        )

    def test_convert_split_id_into_s3_params(self):
        to_format = "{id#split_id_into_s3_params}"
        expected = {
            "productType": "OL_2_LRR___",
            "startDate": "2021-06-01T22:38:21Z",
            "endDate": "2021-06-01T23:22:48Z",
            "timeliness": "NT",
            "sat": "Sentinel-3B",
        }
        self.assertEqual(
            format_metadata(
                to_format,
                id="S3B_OL_2_LRR____20210601T223822_20210601T232247_20210603T035324_2665_053_101______LN1_O_NT_002",
            ),
            str(expected),
        )

    def test_convert_split_id_into_s5p_params(self):
        to_format = "{id#split_id_into_s5p_params}"
        expected = {
            "productType": "L2__NP_BD7",
            "processingMode": "RPRO",
            "processingLevel": "L2",
            "startDate": "2018-05-31T22:38:42Z",
            "endDate": "2018-06-01T00:22:30Z",
        }
        self.assertEqual(
            format_metadata(
                to_format,
                id="S5P_RPRO_L2__NP_BD7_20180531T223852_20180601T002220_03271_01_010002_20190528T184222",
            ),
            str(expected),
        )

    def test_convert_get_processing_level_from_s5p_id(self):
        to_format = "{id#get_processing_level_from_s5p_id}"
        self.assertEqual(
            format_metadata(
                to_format,
                id="S5P_RPRO_L2__NP_BD7_20180531T223852_20180601T002220_03271_01_010002_20190528T184222",
            ),
            "L2",
        )

    def test_convert_split_cop_dem_id(self):
        to_format = "{id#split_cop_dem_id}"
        self.assertEqual(
            str(
                format_metadata(
                    to_format,
                    id="Copernicus_DSM_10_N59_00_E119_00",
                )
            ),
            str([118, 58, 120, 60]),
        )
        self.assertEqual(
            str(
                format_metadata(
                    to_format,
                    id="Copernicus_DSM_10_S59_00_W119_00",
                )
            ),
            str([-120, -60, -118, -58]),
        )

    def test_convert_split_corine_id(self):
        self.assertEqual(
            format_metadata(
                "{id#split_corine_id}",
                id="u2006_clc2000_v2020_20u1_raster100m",
            ),
            "Corine Land Cover 2000",
        )
        self.assertEqual(
            format_metadata(
                "{id#split_corine_id}",
                id="u2006_cha0006_v2020_20u1_raster100m",
            ),
            "Corine Land Change 2000 2006",
        )

    def test_convert_to_datetime_dict(self):
        to_format = "{date#to_datetime_dict(list)}"
        expected_result = {
            "year": ["2023"],
            "month": ["01"],
            "day": ["31"],
            "hour": ["00"],
            "minute": ["00"],
            "second": ["00"],
        }
        self.assertEqual(
            format_metadata(to_format, date="2023-01-31T00:00"), str(expected_result)
        )
        to_format = "{date#to_datetime_dict(string)}"
        expected_result = {
            "year": "2023",
            "month": "01",
            "day": "31",
            "hour": "00",
            "minute": "00",
            "second": "00",
        }
        self.assertEqual(
            format_metadata(to_format, date="2023-01-31T00:00"), str(expected_result)
        )

    def test_convert_get_ecmwf_time(self):
        to_format = "{date#get_ecmwf_time}"
        self.assertEqual(
            format_metadata(to_format, date="2023-01-31T00:00"), str(["00:00"])
        )
        self.assertEqual(
            format_metadata(to_format, date="2023-01-31T23:59"), str(["23:00"])
        )
