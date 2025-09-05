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
from unittest import mock

import orjson
from jsonpath_ng.ext import parse
from lxml import etree
from shapely import LineString, Polygon, wkt

from eodag.api.product.metadata_mapping import (
    WKT_MAX_LEN,
    get_provider_queryable_key,
    get_provider_queryable_path,
    get_queryable_from_provider,
    properties_from_xml,
)
from eodag.types.queryables import Queryables
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

    def test_convert_to_rounded_wkt_too_long(self):
        """Test rounding WKT coordinates for long geometries"""
        to_format = "{fieldname#to_rounded_wkt}"
        coords = [(x, x * 0.5) for x in range(1000)]
        geom = LineString(coords)

        with self.assertLogs(level="DEBUG") as cm:
            result = format_metadata(to_format, fieldname=geom)

        self.assertIsInstance(result, str)
        self.assertLessEqual(len(result), WKT_MAX_LEN)
        self.assertIn("Geometry WKT is too long", cm.output[0])

    def test_convert_to_rounded_wkt_warns_if_still_too_long(self):
        """Test warning when rounding WKT coordinates does not help enough"""
        to_format = "{fieldname#to_rounded_wkt}"
        coords = [(x, x * 0.5) for x in range(10000)]
        geom = LineString(coords)

        with mock.patch("eodag.api.product.metadata_mapping.WKT_MAX_LEN", 10):
            with self.assertLogs(level="WARNING") as cm:
                result = format_metadata(to_format, fieldname=geom)

        self.assertIsInstance(result, str)
        self.assertIn("Failed to reduce WKT length lower than", cm.output[0])

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

    def test_convert_to_bounds_lists_with_polygon(self):
        """Test converting to bounds lists with a single polygon geometry"""
        to_format = "{fieldname#to_bounds_lists}"
        geom = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

        result = format_metadata(to_format, fieldname=geom)

        expected = "[[0.0, 0.0, 1.0, 1.0]]"
        self.assertEqual(result, expected)

    def test_convert_to_bounds(self):
        to_format = "{fieldname#to_bounds}"
        # multi-geometry
        geom = get_geometry_from_various(
            geometry="""MULTIPOLYGON (
                ((1.23 43.42, 1.23 43.76, 1.68 43.76, 1.68 43.42, 1.23 43.42)),
                ((2.23 43.42, 2.23 43.76, 3.68 43.76, 3.68 43.42, 2.23 43.42))
            )"""
        )
        self.assertEqual(
            format_metadata(to_format, fieldname=geom),
            "[1.23, 43.42, 3.68, 43.76]",
        )
        # single geometry
        geom = get_geometry_from_various(geometry="POINT (0.1111 1.2222)")
        self.assertEqual(
            format_metadata(to_format, fieldname=geom),
            "[0.1111, 1.2222, 0.1111, 1.2222]",
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
        self.assertEqual(
            wkt_str,
            format_metadata(
                to_format, fieldname="geography'SRID=3857;POINT (321976 5390999)'"
            ),
        )

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
        to_format = "{fieldname#csv_list(+)}"
        self.assertEqual(
            format_metadata(to_format, fieldname=[1, 2, 3]),
            "1+2+3",
        )

    def test_convert_remove_extension(self):
        to_format = "{fieldname#remove_extension}"
        self.assertEqual(
            format_metadata(to_format, fieldname="foo.bar"),
            "foo",
        )

    def test_convert_remove_extension_no_parts(self):
        """Test removing extension from a filename with no parts"""
        to_format = "{fieldname#remove_extension}"
        self.assertEqual(
            format_metadata(to_format, fieldname=""),
            "",
        )

    def test_convert_get_group_name(self):
        to_format = (
            "{fieldname#get_group_name((?P<this is foo>foo)|(?P<that_is_bar>bar))}"
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="foo"),
            "this is foo",
        )

    def test_convert_get_group_name_not_available(self):
        """Test getting group name when no group matches"""
        to_format = "{fieldname#get_group_name(foo)}"
        string = "this has foo in it"

        self.assertEqual(
            format_metadata(to_format, fieldname=string),
            NOT_AVAILABLE,
        )

    def test_convert_replace_str(self):
        to_format = r"{fieldname#replace_str(r'(.*) is (.*)',r'\1 was \2...')}"

        # Test with a string
        self.assertEqual(
            format_metadata(to_format, fieldname="this is foo"),
            "this was foo...",
        )

        # Test with a dictionary
        self.assertEqual(
            format_metadata(to_format, fieldname={"key": "this is foo"}),
            '{"key": "this was foo"}...',
        )

        # Test with a list (should fail)
        with self.assertRaises(TypeError):
            format_metadata(to_format, fieldname=["this is foo"])

        # Test with an integer (should fail)
        with self.assertRaises(TypeError):
            format_metadata(to_format, fieldname=123)

    def test_convert_replace_str_tuple(self):
        to_format = r"{fieldname#replace_str_tuple((('foo','bar'),('this','that')))}"

        # Test with a string
        self.assertEqual(
            format_metadata(to_format, fieldname="this is foo"),
            "that is bar",
        )

        # Test with a dictionary
        self.assertEqual(
            format_metadata(to_format, fieldname={"key": "this is foo"}),
            '{"key": "that is bar"}',
        )

        # Test with a list (should fail)
        with self.assertRaises(TypeError):
            format_metadata(to_format, fieldname=["this is foo"])

        # Test with an integer (should fail)
        with self.assertRaises(TypeError):
            format_metadata(to_format, fieldname=123)

    def test_convert_ceda_collection_name(self):
        to_format = r"{fieldname#ceda_collection_name}"
        self.assertEqual(
            format_metadata(to_format, fieldname="https://bar/data/foo/v1.1"),
            "FOO_V1.1",
        )
        self.assertEqual(
            format_metadata(to_format, fieldname="NOT_AVAILABLE"),
            "NOT_AVAILABLE",
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

    def test_convert_dict_filter(self):
        to_format = '{fieldname#dict_filter($[?(href=~"^s3.*")])}'
        self.assertEqual(
            format_metadata(
                to_format,
                fieldname={"a": {"href": "https://foo"}, "b": {"href": "s3://bar"}},
            ),
            "{'b': {'href': 's3://bar'}}",
        )

    def test_convert_from_alternate(self):
        """
        Test converting assets by replacing href with alternate.<value>.href,
        copying metadata, and removing alternate.
        """
        to_format = "{fieldname#from_alternate(s3)}"
        self.assertEqual(format_metadata(to_format, fieldname=None), "None")

        # Cas 2 : aucun alternate.s3
        assets1 = {
            "a": {"href": "http://example.com/a"},
            "b": {"href": "http://example.com/b"},
        }
        self.assertEqual(format_metadata(to_format, fieldname=assets1), "{}")

        # Cas 3 : alternate.s3 avec href simple
        assets2 = {
            "a": {
                "href": "http://example.com/a",
                "alternate": {"s3": {"href": "s3://bucket/a"}},
            },
            "b": {"href": "http://example.com/b"},
        }
        expected2 = """{'a': {'href': 's3://bucket/a'}}"""
        self.assertEqual(format_metadata(to_format, fieldname=assets2), expected2)

        # Cas 4 : alternate.s3 avec métadonnées supplémentaires
        assets3 = {
            "c": {
                "href": "http://example.com/c",
                "size": 123,
                "alternate": {
                    "s3": {
                        "href": "s3://bucket/c",
                        "storage:region": "eu-west-1",
                        "storage:class": "STANDARD",
                    }
                },
            }
        }
        expected3 = (
            "{'c': {'href': 's3://bucket/c', 'size': 123, "
            "'storage:region': 'eu-west-1', 'storage:class': 'STANDARD'}}"
        )
        self.assertEqual(format_metadata(to_format, fieldname=assets3), expected3)

        # Cas 5 : asset "index" doit disparaître si pas d'alternate.s3
        assets4 = {
            "index": {"href": "http://example.com/index"},
            "d": {
                "href": "http://example.com/d",
                "alternate": {"s3": {"href": "s3://bucket/d"}},
            },
        }
        expected4 = """{'d': {'href': 's3://bucket/d'}}"""
        self.assertEqual(format_metadata(to_format, fieldname=assets4), expected4)

    def test_convert_slice_str(self):
        to_format = "{fieldname#slice_str(1,12,2)}"
        self.assertEqual(
            format_metadata(to_format, fieldname="abcdefghijklmnop"),
            "bdfhjl",
        )

    def test_convert_to_lower(self):
        to_format = r"{fieldname#to_lower}"
        self.assertEqual(format_metadata(to_format, fieldname="FoO.bAr"), "foo.bar")

    def test_convert_to_lower_not_available(self):
        to_format = r"{fieldname#to_lower}"
        self.assertEqual(
            format_metadata(to_format, fieldname="Not Available"), "Not Available"
        )

    def test_convert_to_upper(self):
        to_format = r"{fieldname#to_upper}"
        self.assertEqual(format_metadata(to_format, fieldname="FoO.bAr"), "FOO.BAR")

    def test_convert_to_upper_empty(self):
        to_format = r"{fieldname#to_upper}"
        self.assertEqual(format_metadata(to_format, fieldname=None), "None")

    def test_convert_to_title(self):
        to_format = r"{fieldname#to_title}"
        self.assertEqual(format_metadata(to_format, fieldname="FoO.bAr"), "Foo.Bar")

    def test_convert_to_title_not_available(self):
        to_format = r"{fieldname#to_title}"
        self.assertEqual(
            format_metadata(to_format, fieldname="Not Available"), "Not Available"
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

    def test_convert_fake_l2a_title_from_l1c_not_match(self):
        """Test converting L1C title to fake L2A title when input does not match expected format"""
        to_format = "{fieldname#fake_l2a_title_from_l1c}"

        self.assertEqual(
            format_metadata(
                to_format,
                fieldname="",
            ),
            NOT_AVAILABLE,
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

    def test_convert_s2msil2a_title_to_aws_productinfo_not_available(self):
        """Test converting S2MSIL2A title to AWS product info when input does not match expected format"""
        to_format = "{fieldname#s2msil2a_title_to_aws_productinfo}"
        self.assertEqual(
            format_metadata(
                to_format,
                fieldname="",
            ),
            NOT_AVAILABLE,
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

    def test_convert_split_id_into_s3_params(self):
        to_format = "{id#split_id_into_s3_params}"
        expected = {
            "collection": "OL_2_LRR___",
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

    def test_convert_interval_to_datetime_dict(self):
        to_format = "{date#interval_to_datetime_dict}"
        formated = format_metadata(to_format, date="2023-01-31T00:00/2023-02-03T00:00")
        expected_result = {
            "year": ["2023"],
            "month": ["01", "02"],
            "day": ["31", "01", "02", "03"],
        }
        formated_dict = orjson.loads(formated.replace("'", '"'))
        for k in expected_result.keys():
            self.assertCountEqual(formated_dict[k], expected_result[k])

    def test_convert_interval_to_datetime_dict_without_separator_in_date(self):
        """Test converting interval to datetime dict when input date does not contain a '/' separator"""
        to_format = "{date#interval_to_datetime_dict}"
        with self.assertRaises(ValueError):
            format_metadata(to_format, date="wrong_date")

    def test_convert_get_ecmwf_time(self):
        to_format = "{date#get_ecmwf_time}"
        self.assertEqual(
            format_metadata(to_format, date="2023-01-31T00:00"), str(["00:00"])
        )
        self.assertEqual(
            format_metadata(to_format, date="2023-01-31T23:59"), str(["23:00"])
        )

    def test_convert_get_dates_from_string(self):
        to_format = "{text#get_dates_from_string}"
        self.assertEqual(
            format_metadata(to_format, text="20231019-20231020"),
            str(
                {
                    "startDate": "2023-10-19T00:00:00Z",
                    "endDate": "2023-10-20T00:00:00Z",
                }
            ),
        )
        to_format = "{text#get_dates_from_string(_)}"
        self.assertEqual(
            format_metadata(to_format, text="20231019_20231020"),
            str(
                {
                    "startDate": "2023-10-19T00:00:00Z",
                    "endDate": "2023-10-20T00:00:00Z",
                }
            ),
        )

    def test_convert_get_hydrological_year(self):
        to_format = "{date#get_hydrological_year}"
        self.assertEqual(
            format_metadata(to_format, date="2010-01-11T17:42:24Z"), str(["2010_11"])
        )

    def test_convert_to_longitude_latitude(self):
        to_format = "{input_geom_unformatted#to_longitude_latitude}"
        geometry = (
            """POLYGON ((1.23 43.42, 1.23 43.76, 1.68 43.76, 1.68 43.42, 1.23 43.42))"""
        )

        self.assertEqual(
            format_metadata(to_format, input_geom_unformatted=geometry),
            str({"lon": 1.455, "lat": 43.59}),
        )
        geometry = """POINT (1.23 43.42)"""

        self.assertEqual(
            format_metadata(to_format, input_geom_unformatted=geometry),
            str({"lon": 1.23, "lat": 43.42}),
        )

    def test_convert_get_variables_from_path(self):
        to_format = "{path#get_variables_from_path}"
        self.assertEqual(
            format_metadata(to_format, path="productA.nc?depth,latitude"),
            str(["depth", "latitude"]),
        )
        self.assertEqual(
            format_metadata(to_format, path="productA.nc"),
            str([]),
        )

    def test_convert_dates_from_cmems_id(self):
        to_format = "{product_id#dates_from_cmems_id}"
        self.assertEqual(
            format_metadata(
                to_format, product_id="mfwamglocep_2021121102_R20211212_12H.nc"
            ),
            str(
                {
                    "min_date": "2021-12-11T02:00:00Z",
                    "max_date": "2021-12-12T02:00:00Z",
                }
            ),
        )
        self.assertEqual(
            format_metadata(
                to_format,
                product_id="glo12_rg_1d-m_20220601-20220601_3D-uovo_hcst_R20220615.nc",
            ),
            str(
                {
                    "min_date": "2022-06-01T00:00:00Z",
                    "max_date": "2022-06-02T00:00:00Z",
                }
            ),
        )

    def test_convert_assets_list_to_dict(self):
        # by default, the name of the asset is searched in "title" value
        to_format = "{assets#assets_list_to_dict}"
        assets_list = [
            {"href": "foo", "title": "asset1", "name": "foo-name"},
            {"href": "bar", "title": "path/to/asset1", "name": "bar-name"},
            {"href": "baz", "title": "path/to/asset2", "name": "baz-name"},
            {"href": "qux", "title": "asset3", "name": "qux-name"},
        ]
        expected_result = {
            "asset1": assets_list[0],
            "path/to/asset1": assets_list[1],
            "asset2": assets_list[2],
            "asset3": assets_list[3],
        }
        self.assertEqual(
            format_metadata(to_format, assets=assets_list), str(expected_result)
        )

        # we can adapt if the name of the asset is in the value of a different key
        to_format = "{assets#assets_list_to_dict(name)}"
        assets_list = [
            {"href": "foo", "title": "foo-title", "name": "asset1"},
            {"href": "bar", "title": "bar-title", "name": "path/to/asset1"},
            {"href": "baz", "title": "baz-title", "name": "path/to/asset2"},
            {"href": "qux", "title": "qux-title", "name": "asset3"},
        ]
        expected_result = {
            "asset1": assets_list[0],
            "path/to/asset1": assets_list[1],
            "asset2": assets_list[2],
            "asset3": assets_list[3],
        }
        self.assertEqual(
            format_metadata(to_format, assets=assets_list), str(expected_result)
        )


class TestMetadataMappingFunctions(unittest.TestCase):
    def test_properties_from_xml_single_value_no_conversion(self):
        """Test extracting a single value from XML without conversion"""
        xml = """<root><id>123</id></root>"""
        mapping = {"id": (None, "./id/text()")}
        props = properties_from_xml(xml, mapping)
        assert props["id"] == "123"

    def test_properties_from_xml_not_available(self):
        """Test extracting a single value from XML when not available"""
        xml = """<root></root>"""
        mapping = {"id": (None, "./id/text()")}
        props = properties_from_xml(xml, mapping)
        assert props["id"] == NOT_AVAILABLE

    def test_properties_from_xml_with_conversion(self):
        """Test extracting a single value from XML with conversion"""
        xml = """<root><val>hello</val></root>"""
        mapping = {"val": (["to_upper"], "./val/text()")}
        props = properties_from_xml(xml, mapping)
        assert props["val"] == "HELLO"

    def test_properties_from_xml_multiple_values(self):
        """Test extracting multiple values from XML without conversion"""
        xml = """<root>
            <item>A</item>
            <item>B</item>
        </root>"""
        mapping = {"items": (None, "./item/text()")}
        props = properties_from_xml(xml, mapping)
        assert props["items"] == ["A", "B"]

    def test_properties_from_xml_xpath_eval_error(self):
        """Test handling of XPath evaluation error"""
        xml = """<root><id>123</id></root>"""
        mapping = {"custom": (None, "//*invalid_xpath")}
        props = properties_from_xml(xml, mapping)
        assert props["custom"] == "//*invalid_xpath"

    def test_properties_from_xml_discovery(self):
        """Test auto-discovery of metadata from XML"""
        xml = """<root>
            <auto_discovered>value1</auto_discovered>
        </root>"""
        mapping = {}
        discovery_config = {
            "metadata_pattern": "^[a-z_]+$",
            "metadata_path": "./*",
        }
        props = properties_from_xml(xml, mapping, discovery_config=discovery_config)
        assert props["auto_discovered"] == "value1"

    def test_properties_from_xml_multiple_matches_with_conversion(self):
        """Test extracting multiple values from XML with conversion"""
        xml = """<root>
                    <val>hello</val>
                    <val>world</val>
                </root>"""
        mapping = {"val": (["to_upper"], "./val/text()")}
        props = properties_from_xml(xml, mapping)
        assert props["val"] == ["HELLO", "WORLD"]

    def test_properties_from_xml_multiple_matches_with_conversion_and_args(self):
        """Test extracting multiple values from XML with conversion that requires arguments"""
        xml = """<root>
                    <val>test1</val>
                    <val>test2</val>
                </root>"""
        mapping = {"val": ("to_upper", "./val/text()")}

        props = properties_from_xml(xml, mapping)
        assert props["val"] == ["TEST1", "TEST2"]

    def test_properties_from_xml_multiple_matches_no_conversion(self):
        """Test extracting multiple values from XML without conversion"""
        xml = """<root>
                    <val>a</val>
                    <val>b</val>
                </root>"""
        mapping = {"val": (None, "./val/text()")}

        props = properties_from_xml(xml, mapping)

        assert props["val"] == ["a", "b"]

    def test_get_queryable_from_provider_found(self):
        """Test getting a queryable from provider mapping when found"""
        metadata_mapping = {
            "year": ["year"],
            "date": ["date"],
        }
        provider_queryable = "year"

        result = get_queryable_from_provider(provider_queryable, metadata_mapping)

        expected = Queryables.get_queryable_from_alias("year")
        self.assertEqual(result, expected)

    def test_get_provider_queryable_path(self):
        """Test getting the provider queryable path"""
        metadata_mapping = {"id": "id", "path": ["path1", "path2"]}
        queryable_path = get_provider_queryable_path("path", metadata_mapping)
        self.assertEqual(queryable_path, "path1")
        queryable_path = get_provider_queryable_path("id", metadata_mapping)
        self.assertEqual(queryable_path, None)

    def test_get_provider_queryable_key(self):
        metadata_mapping = {
            "id": "id",
            "start_datetime": [
                "datetime: {start_datetime}",
                "$.datetime",
            ],
            "api_collection": ["collection", "$.properties.collection"],
            "variable": ["variable", "$.variable"],
            "variable_type": ["variable_type", "$.variable_type"],
        }
        provider_queryables = {
            "datetime": {"type": "str", "description": "datetime"},
            "id": {"type": "str"},
            "collection": {"type": "str"},
            "level": {"type": int},
            "variable": {"type": "str"},
            "variable_type": {"type": "str"},
        }
        provider_key = get_provider_queryable_key(
            "start_datetime", provider_queryables, metadata_mapping
        )
        self.assertEqual("datetime", provider_key)
        provider_key = get_provider_queryable_key(
            "api_collection", provider_queryables, metadata_mapping
        )
        self.assertEqual("collection", provider_key)
        provider_key = get_provider_queryable_key(
            "id", provider_queryables, metadata_mapping
        )
        self.assertEqual("id", provider_key)
        provider_key = get_provider_queryable_key(
            "variable_type", provider_queryables, metadata_mapping
        )
        self.assertEqual("variable_type", provider_key)
        provider_key = get_provider_queryable_key(
            "variable", provider_queryables, metadata_mapping
        )
        self.assertEqual("variable", provider_key)
        provider_key = get_provider_queryable_key(
            "not_here", provider_queryables, metadata_mapping
        )
        self.assertEqual("", provider_key)

    def test_convert_sanitize(self):
        to_format = "{path#sanitize}"
        self.assertEqual(
            format_metadata(
                to_format,
                path="replaçe,  pônctuation:;sïgns!?byunderscorekeeping-hyphen.dot_and_underscore",
            ),
            "replace_ponctuation_signs_byunderscorekeeping-hyphen.dot_and_underscore",
        )
