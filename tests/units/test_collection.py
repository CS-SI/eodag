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

import os
import unittest
from collections import UserDict, UserList
from unittest import mock

from lxml import html

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
        self.dag = EODataAccessGateway()
        self.collection = Collection.create_with_dag(self.dag, id="foo")

        # mock os.environ to empty env
        self.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        self.mock_os_environ.start()

    def tearDown(self):
        super(TestCollection, self).tearDown()
        # stop os.environ
        self.mock_os_environ.stop()

    def test_collection_set_ids_and_alias(self):
        """Collection ids and alias must be correctly set"""
        collection = Collection(id="foo", alias="bar")

        # check that id attribute has the same value as alias attribute
        self.assertIsInstance(collection, Collection)
        self.assertEqual(collection.id, "bar")
        self.assertEqual(collection.alias, "bar")

        # check that the internal id attribute is set to the original id
        self.assertEqual(collection._id, "foo")

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
            self.assertIn("platform\\n  Input should be a valid string", str(cm.output))
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
    def setUp(self):
        super(TestCollectionsDict, self).setUp()
        self.dag = EODataAccessGateway()
        self.collections_dict = CollectionsDict([Collection(id="foo")])

    def test_search_result_is_dict_like(self):
        """CollectionsDict must provide a dict interface"""
        self.assertIsInstance(self.collections_dict, UserDict)


class TestCollectionsList(unittest.TestCase):
    def setUp(self):
        super(TestCollectionsList, self).setUp()
        self.dag = EODataAccessGateway()
        self.collections_list = CollectionsList([Collection(id="foo")])

    def test_search_result_is_list_like(self):
        """CollectionsList must provide a list interface"""
        self.assertIsInstance(self.collections_list, UserList)

    def test_search_result_repr_html(self):
        """CollectionsList html repr must be correctly formatted"""
        sr_repr = html.fromstring(self.collections_list._repr_html_())
        self.assertIn("CollectionsList", sr_repr.xpath("//details/summary")[0].text)
