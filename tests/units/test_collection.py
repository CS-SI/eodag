# -*- coding: utf-8 -*-
# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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

import os
import unittest
from collections import UserDict, UserList
from tempfile import TemporaryDirectory
from typing import cast
from unittest import mock

import orjson
from lxml import html

from eodag.types.stac_metadata import CommonStacMetadata, create_stac_metadata_model
from eodag.utils.exceptions import ValidationError
from tests.context import (
    Collection,
    CollectionsDict,
    CollectionsList,
    EODataAccessGateway,
)


class TestCollection(unittest.TestCase):
    def setUp(self):
        super(TestCollection, self).setUp()
        # Mock home and eodag conf directory to tmp dir
        self.tmp_home_dir = TemporaryDirectory()
        self.expanduser_mock = mock.patch(
            "os.path.expanduser", autospec=True, return_value=self.tmp_home_dir.name
        )
        self.expanduser_mock.start()

        self.dag = EODataAccessGateway()
        self.collection = Collection.create_with_dag(self.dag, id="foo")

        # mock os.environ to empty env
        self.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        self.mock_os_environ.start()

    def tearDown(self):
        super(TestCollection, self).tearDown()
        # stop os.environ
        self.mock_os_environ.stop()

        # stop Mock and remove tmp config dir
        self.expanduser_mock.stop()
        self.tmp_home_dir.cleanup()

    def test_collection_enable_validation(self):
        """Collection validation is enabled by an environment variable.
        It allows to log warnings on bad formatted attributes spotted during collection initialization"""
        try:
            # ensure validation is enabled for collections
            os.environ["EODAG_VALIDATE_COLLECTIONS"] = "True"

            # try to create a collection with bad formatted attributes
            # and check that logs have been emitted
            with self.assertLogs(level="DEBUG") as cm:
                collection = Collection(id="foo", platform=0, bar="bat")

            self.assertIn("2 validation errors for collection foo", str(cm.output))
            self.assertIn(
                "platform.0\\n  Input should be a valid string", str(cm.output)
            )
            self.assertIn("bar\\n  Extra inputs are not permitted", str(cm.output))

            # check that the collection has been created
            # and that its incorrectly formatted attribute is set to None
            # and its extra attribute is removed
            self.assertIsInstance(collection, Collection)
            self.assertEqual(collection.id, "foo")
            self.assertIsNone(collection.platform)
            self.assertFalse(getattr(collection, "bar", False))
        finally:
            # remove the environment variable
            os.environ.pop("EODAG_VALIDATE_COLLECTIONS", None)

    def test_collection_set_ids_and_alias(self):
        """Collection ids and alias must be correctly set"""
        collection = Collection(id="foo", alias="bar")

        # check that id attribute has the same value as alias attribute
        self.assertIsInstance(collection, Collection)
        self.assertEqual(collection.id, "bar")
        self.assertEqual(collection.alias, "bar")

        # check that the internal id attribute is set to the original id
        self.assertEqual(collection._id, "foo")

    def test_collection_stac_fields(self):
        """Check that stac fields are fields of the model"""
        for field in Collection.__stac_fields__:
            self.assertIn(field, Collection.model_fields)

    def test_collection_static_fields(self):
        """Check that static fields are fields of the model"""
        for field in Collection.__static_fields__:
            self.assertIn(field, Collection.model_fields)

    def test_collection_wrong_static_fields(self):
        """Check that static fields are set to their default value"""
        self.assertIn("type", Collection.__static_fields__)
        type_default = Collection.model_fields["type"].get_default()
        self.assertEqual(type_default, "Collection")

        # if a static field is not set, it will be set correctly without raising an error
        collection = Collection(id="foo")

        self.assertEqual(collection.type, type_default)

        # if a static field is set to another value than the default one,
        # logs can be emitted before the field is eventually set
        try:
            # ensure validation is enabled for collections
            os.environ["EODAG_VALIDATE_COLLECTIONS"] = "True"

            with self.assertLogs(level="DEBUG") as cm:
                collection = Collection(id="foo", type=1)

            self.assertIn(
                f"type\\n  Input is fixed to its default value: {type_default}",
                str(cm.output),
            )
            self.assertEqual(collection.type, type_default)
        finally:
            # remove the environment variable
            os.environ.pop("EODAG_VALIDATE_COLLECTIONS", None)

    def test_collection_summaries_fields(self):
        """Check that summaries fields are fields of the model"""
        for field in Collection.summaries_fields():
            self.assertIn(field, Collection.model_fields)

    def test_collection_summaries(self):
        """Collection summaries must be correctly set"""

        # if there is no property of "summaries", "summaries" is set to None
        collection = Collection(
            id="foo",
        )

        self.assertIsNone(collection.summaries)

        # only add a field to field "summaries" as a property of it if it is the case
        # when it is the case, the pair (field, "summaries" property) must have the same values after validation
        collection = Collection(
            id="foo",
            platform=["S2A", "S2B"],
            foo=["bar"],
            summaries={"constellation": ["SENTINEL2"], "qux": ["quux"]},
        )

        self.assertIn(
            Collection.get_collection_field_from_alias("platform"),
            Collection.summaries_fields(),
        )
        self.assertIn(
            Collection.get_collection_field_from_alias("constellation"),
            Collection.summaries_fields(),
        )
        self.assertNotIn(
            Collection.get_collection_field_from_alias("foo"),
            Collection.summaries_fields(),
        )
        self.assertNotIn(
            Collection.get_collection_field_from_alias("qux"),
            Collection.summaries_fields(),
        )

        self.assertListEqual(collection.constellation, ["SENTINEL2"])
        self.assertListEqual(collection.platform, ["S2A", "S2B"])
        self.assertDictEqual(
            collection.summaries,
            {"constellation": ["SENTINEL2"], "platform": ["S2A", "S2B"]},
        )

        # specific logs can be emitted when unknown properties are set in field "summaries"
        try:
            # ensure validation is enabled for collections
            os.environ["EODAG_VALIDATE_COLLECTIONS"] = "True"

            with self.assertLogs(level="DEBUG") as cm:
                collection = Collection(
                    id="foo",
                    summaries={"constellation": ["SENTINEL2"], "foo": ["bar"]},
                )

            self.assertIn(
                'summaries.foo\\n  Extra inputs are not permitted in collection field "summaries"',
                str(cm.output),
            )
        finally:
            # remove the environment variable
            os.environ.pop("EODAG_VALIDATE_COLLECTIONS", None)

        # if a "summaries" field or property is not validated, their value is set
        # to the default value of the field for both of them

        # if their default value is None, the property is removed from field "summaries" which does not keep null values
        collection = Collection(
            id="foo",
            platform=["S2A", "S2B"],
            constellation=[1],
            summaries={"instruments": [1]},
        )

        constellation_default = Collection.model_fields["constellation"].get_default()
        self.assertIsNone(constellation_default)
        self.assertEqual(collection.constellation, constellation_default)
        self.assertNotIn("constellation", collection.summaries)

        instruments_default = Collection.model_fields["instruments"].get_default()
        self.assertIsNone(instruments_default)
        self.assertIsNone(collection.instruments, instruments_default)
        self.assertNotIn("instruments", collection.summaries)

        # remove only the bad formatted elements in a list or a dict of a property of "summaries"
        # if all elements are bad formatted, the field is reset to None if it is its default value
        # and removed from "summaries"
        collection = Collection(
            id="foo",
            platform=["S2A", "S2B", 1],
            processing_level=[1],
        )

        processing_level_default = Collection.model_fields[
            "processing_level"
        ].get_default()
        self.assertIsNone(processing_level_default)
        self.assertEqual(collection.processing_level, processing_level_default)
        self.assertNotIn("processing_level", collection.summaries)

        self.assertDictEqual(collection.summaries, {"platform": ["S2A", "S2B"]})

        # properties of "summaries" set in kwargs have priority over the ones
        # set in "summaries" directly except if they are null

        # bad formatted values in kwargs still keep their priority
        collection = Collection(
            id="foo",
            platform="S2A,S2B",
            constellation=None,
            instruments=1,
            summaries={
                "constellation": "SENTINEL2",
                "platform": ["S2C"],
                "instruments": ["MSI"],
            },
        )

        self.assertNotIn("instruments", collection.summaries)
        self.assertDictEqual(
            collection.summaries,
            {"constellation": ["SENTINEL2"], "platform": ["S2A", "S2B"]},
        )

        # use aliases of fields in field "summaries" properties to make field "summaries" STAC-formatted
        collection = Collection(
            id="foo",
            eodag_sensor_type=["OPTICAL"],
            summaries={"processing_level": ["L2"]},
        )

        eodag_sensor_type_alias = Collection.get_collection_alias_from_field(
            "eodag_sensor_type"
        )
        processing_level_alias = Collection.get_collection_alias_from_field(
            "processing_level"
        )

        self.assertEqual(eodag_sensor_type_alias, "eodag:sensor_type")
        self.assertEqual(processing_level_alias, "processing:level")
        self.assertDictEqual(
            collection.summaries,
            {"eodag:sensor_type": ["OPTICAL"], "processing:level": ["L2"]},
        )

        # it must work by using alias in properties, and priority must work too
        collection = Collection(
            id="foo",
            processing_level="L1",
            summaries={"processing:level": "L2", "eodag:sensor_type": ["OPTICAL"]},
        )
        self.assertDictEqual(
            collection.summaries,
            {"processing:level": ["L1"], "eodag:sensor_type": ["OPTICAL"]},
        )

        collection = Collection(
            **{
                "id": "foo",
                "processing:level": "L1",
                "summaries": {"processing_level": ["L2"]},
            }
        )

        self.assertDictEqual(
            collection.summaries,
            {"processing:level": ["L1"]},
        )

        # only accept lists and dictionaries for properties of "summaries", otherwise convert values to list if possible
        collection = Collection(
            id="foo",
            processing_level={"L2"},
            platform="S2A,S2B",
            eodag_sensor_type=1,
            summaries={"constellation": "SENTINEL2", "instruments": ["MSI"]},
        )

        # "processing_level" and "eodag_sensor_type" should have been converted to a list
        # if their field allow list of sets or of integer
        # TODO: add a test with a "summaries" field accepting an other type
        # than string when a field will allow to deal with this case
        self.assertDictEqual(
            collection.summaries,
            {
                "constellation": ["SENTINEL2"],
                "platform": ["S2A", "S2B"],
                "instruments": ["MSI"],
            },
        )

        # if a property of "summaries" is set to an empty value (None,
        # or [], {} or "" when they are not its default value),
        # it must not be present in "summaries" after validation
        # TODO: add a test with an empty value among [], {} and "" which is a default value
        # when a field will allow to deal with this case
        collection = Collection(
            id="foo",
            processing_level=None,
            instruments=[],
            constellation="",
            eodag_sensor_type="OPTICAL",
            summaries={"constellation": None},
        )

        processing_level_default = Collection.model_fields[
            "processing_level"
        ].get_default()
        self.assertIsNone(processing_level_default)
        self.assertIsNone(collection.processing_level)

        instruments_default = Collection.model_fields["instruments"].get_default()
        self.assertIsNone(instruments_default)
        self.assertIsNone(collection.instruments)

        eodag_sensor_type_default = Collection.model_fields[
            "eodag_sensor_type"
        ].get_default()
        self.assertIsNone(eodag_sensor_type_default)
        self.assertIsNone(collection.constellation)

        self.assertEqual(collection.eodag_sensor_type, ["OPTICAL"])
        self.assertDictEqual(collection.summaries, {"eodag:sensor_type": ["OPTICAL"]})

        # if all properties of "summaries" are bad formatted or set to None,
        # "summaries" must be reset to None, its default value
        collection = Collection(
            id="foo", processing_level=1, summaries={"constellation": None}
        )

        summaries_default = Collection.model_fields["summaries"].get_default()

        self.assertIsNone(summaries_default)
        self.assertEqual(collection.summaries, summaries_default)

    def test_collection_wrong_id(self):
        """Collection with a missing or wrong id must raise an error
        even if validation of collections is disabled"""
        try:
            # ensure validation is disabled for collections
            os.environ["EODAG_VALIDATE_COLLECTIONS"] = "False"

            # try to create a collection with a missing id
            with self.assertRaises(ValidationError) as context:
                Collection()

            self.assertIn("id\n  Field required", str(context.exception))

            # try to create a collection with a wrong id
            with self.assertRaises(ValidationError) as context:
                Collection(id=1)

            self.assertIn(
                "id\n  Input should be a valid string", str(context.exception)
            )
        finally:
            # remove the environment variable
            os.environ.pop("EODAG_VALIDATE_COLLECTIONS", None)

    def test_wrong_description(self):
        """when description is null or not validated, it is set to the value of id"""
        collection = Collection(id="foo")

        self.assertEqual(collection.description, "foo")

        collection = Collection(id="foo", description="")

        self.assertEqual(collection.description, "foo")

        collection = Collection(
            id="foo",
            description=1,
        )

        self.assertEqual(collection.description, "foo")

    def test_collection_wrong_spatial_extent(self):
        """Collection with a spatial extent bbox in a wrong format
        must raise the custom pydantic error from their field validator"""
        try:
            # ensure validation is activated for collections
            os.environ["EODAG_VALIDATE_COLLECTIONS"] = "True"

            # try to create a collection with wrong start and end temporal extent datetimes
            # and check that logs have been emitted
            with self.assertLogs(level="DEBUG") as cm:
                Collection(
                    id="foo",
                    extent={
                        "spatial": {
                            "bbox": [
                                [
                                    "not-a-lonmin",
                                    "not-a-latmin",
                                    "not-a-lonmax",
                                    "not-a-latmax",
                                ]
                            ]
                        },
                        "temporal": {
                            "interval": [
                                ["2025-01-01T00:00:00Z", "2025-01-02T00:00:00Z"]
                            ]
                        },
                    },
                )

            self.assertIn(
                (
                    "extent.spatial.bbox.0.tuple[union[float,int], union[float,int], union[float,int], "
                    "union[float,int]].0.float\\n  Input should be a valid number, unable to parse string as a number"
                ),
                str(cm.output),
            )
            self.assertIn(
                (
                    "extent.spatial.bbox.0.tuple[union[float,int], union[float,int], union[float,int], "
                    "union[float,int]].1.float\\n  Input should be a valid number, unable to parse string as a number"
                ),
                str(cm.output),
            )
            self.assertIn(
                (
                    "extent.spatial.bbox.0.tuple[union[float,int], union[float,int], union[float,int], "
                    "union[float,int]].2.float\\n  Input should be a valid number, unable to parse string as a number"
                ),
                str(cm.output),
            )
            self.assertIn(
                (
                    "extent.spatial.bbox.0.tuple[union[float,int], union[float,int], union[float,int], "
                    "union[float,int]].3.float\\n  Input should be a valid number, unable to parse string as a number"
                ),
                str(cm.output),
            )

        finally:
            # remove the environment variable
            os.environ.pop("EODAG_VALIDATE_COLLECTIONS", None)

    def test_collection_wrong_temporal_extent(self):
        """Collection with a start or end temporal extent date in a wrong format
        must raise the custom pydantic error from their field validator"""
        try:
            # ensure validation is activated for collections
            os.environ["EODAG_VALIDATE_COLLECTIONS"] = "True"

            # try to create a collection with wrong start and end temporal extent datetimes
            # and check that logs have been emitted
            with self.assertLogs(level="DEBUG") as cm:
                Collection(
                    id="foo",
                    extent={
                        "spatial": {"bbox": [[-180.0, -90.0, 180.0, 90.0]]},
                        "temporal": {
                            "interval": [["not-a-datetime", "not-a-datetime"]]
                        },
                    },
                )

            self.assertIn(
                "extent.temporal.interval.0.0\\n  Input should be a valid datetime or date, invalid character in year",
                str(cm.output),
            )
            self.assertIn(
                "extent.temporal.interval.0.1\\n  Input should be a valid datetime or date, invalid character in year",
                str(cm.output),
            )

        finally:
            # remove the environment variable
            os.environ.pop("EODAG_VALIDATE_COLLECTIONS", None)

    def test_collection_dump(self):
        """When a collection is dumped, unset fields are returned and ``summaries`` property ``stac_extensions``
        can be displayed or not"""
        collection_obj = Collection(
            id="foo",
            processing_level="L2",
            constellation="SENTINEL2",
        )

        # case with extensions displayed
        collection_dict = collection_obj.model_dump(display_extensions=True)

        summaries_model = cast(CommonStacMetadata, create_stac_metadata_model())

        self.assertDictEqual(
            summaries_model.model_fields["processing_level"].metadata[0],
            {"extension": "ProcessingExtension"},
        )
        self.assertIn("processing", collection_dict["stac_extensions"][0])

        # there is no more extension since the only other "summaries" property does not have an extension
        self.assertListEqual(summaries_model.model_fields["constellation"].metadata, [])
        self.assertEqual(len(collection_dict["stac_extensions"]), 1)

        # unset field is also displayed
        self.assertEqual(collection_dict["type"], "Collection")

        # case with extensions not displayed
        collection_dict = collection_obj.model_dump()

        self.assertListEqual(collection_dict["stac_extensions"], [])

        # unset field is still displayed
        self.assertEqual(collection_dict["type"], "Collection")

    def test_collection_dump_json(self):
        """When a collection is dumped in a JSON string, unset fields are returned and ``summaries`` property
        ``stac_extensions`` can be displayed or not"""
        collection_obj = Collection(
            id="foo",
            processing_level="L2",
            constellation="SENTINEL2",
        )

        # case with extensions displayed
        collection_str = collection_obj.model_dump_json(display_extensions=True)
        collection_dict = orjson.loads(collection_str)

        summaries_model = cast(CommonStacMetadata, create_stac_metadata_model())

        self.assertDictEqual(
            summaries_model.model_fields["processing_level"].metadata[0],
            {"extension": "ProcessingExtension"},
        )
        self.assertIn("processing", collection_dict["stac_extensions"][0])

        # there is no more extension since the only other "summaries" property does not have an extension
        self.assertListEqual(summaries_model.model_fields["constellation"].metadata, [])
        self.assertEqual(len(collection_dict["stac_extensions"]), 1)

        # unset field is also displayed
        self.assertEqual(collection_dict["type"], "Collection")

        # case with extensions not displayed
        collection_str = collection_obj.model_dump_json()
        collection_dict = orjson.loads(collection_str)

        self.assertListEqual(collection_dict["stac_extensions"], [])

        # unset field is still displayed
        self.assertEqual(collection_dict["type"], "Collection")

    def test_collection_missing_dag(self):
        """Collection.search must raise an error if no dag is set"""
        with self.assertRaises(RuntimeError) as context:
            Collection(id="foo").search()
        self.assertIn(
            (
                "Collection 'foo' needs EODataAccessGateway to perform this operation. "
                "Create with: Collection.create_with_dag(dag, id='...')"
            ),
            str(context.exception),
        )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.search",
        autospec=True,
    )
    def test_collection_search_ok(self, mock_search):
        """Collection.search must search for products of this collection"""
        self.collection.search()
        mock_search.assert_called_once_with(
            self.dag,
            collection=self.collection.id,
        )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.search",
        autospec=True,
    )
    def test_collection_search_error(self, mock_search):
        """Collection.search must raise an error if "collection" kwarg is given"""
        with self.assertRaises(ValidationError) as context:
            self.collection.search(collection=self.collection.id)
        self.assertIn(
            "collection should not be set in kwargs since a collection instance is used",
            str(context.exception),
        )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.list_queryables",
        autospec=True,
    )
    def test_collection_list_queryables_ok(self, mock_search):
        """Collection.list_queryables must list queryables of this collection"""
        self.collection.list_queryables()
        mock_search.assert_called_once_with(
            self.dag,
            collection=self.collection.id,
        )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.search",
        autospec=True,
    )
    def test_collection_list_queryables_error(self, mock_search):
        """Collection.list_queryables must raise an error if "collection" kwarg is given"""
        with self.assertRaises(ValidationError) as context:
            self.collection.list_queryables(collection=self.collection.id)
        self.assertIn(
            "collection should not be set in kwargs since a collection instance is used",
            str(context.exception),
        )

    def test_search_result_repr_html(self):
        """Collection html repr must be correctly formatted"""
        sr_repr = html.fromstring(self.collection._repr_html_())
        self.assertIn("Collection", sr_repr.xpath("//thead/tr/td")[0].text)


class TestCollectionsDict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures for the class."""
        super().setUpClass()
        cls.collections_dict = CollectionsDict([Collection(id="foo")])

    def test_search_result_is_dict_like(self):
        """CollectionsDict must provide a dict interface"""
        self.assertIsInstance(self.collections_dict, UserDict)


class TestCollectionsList(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures for the class."""
        super().setUpClass()
        cls.collections_list = CollectionsList([Collection(id="foo")])

    def test_search_result_is_list_like(self):
        """CollectionsList must provide a list interface"""
        self.assertIsInstance(self.collections_list, UserList)

    def test_search_result_repr_html(self):
        """CollectionsList html repr must be correctly formatted"""
        sr_repr = html.fromstring(self.collections_list._repr_html_())
        self.assertIn("CollectionsList", sr_repr.xpath("//details/summary")[0].text)
