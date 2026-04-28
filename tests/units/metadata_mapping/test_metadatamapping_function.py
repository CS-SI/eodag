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

from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    format_metadata,
    get_provider_queryable_key,
    get_provider_queryable_path,
    get_queryable_from_provider,
    properties_from_xml,
)
from eodag.types.queryables import Queryables


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

    def test_convert_not_available(self):
        to_format = "{value#not_available}"
        self.assertEqual(
            format_metadata(
                to_format,
                value="any value",
            ),
            NOT_AVAILABLE,
        )
