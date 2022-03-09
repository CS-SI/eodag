# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, http://www.c-s.fr
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

from tests.context import format_metadata, get_geometry_from_various


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

    def test_convert_to_geo_interface(self):
        to_format = "{fieldname#to_geo_interface}"
        geom = get_geometry_from_various(geometry="POINT (0.11 1.22)")
        self.assertEqual(
            format_metadata(to_format, fieldname=geom),
            '{"type": "Point", "coordinates": [0.11, 1.22]}',
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
