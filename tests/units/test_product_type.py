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
    EODataAccessGateway,
    ProductType,
    ProductTypesDict,
    ProductTypesList,
)


class TestProductType(unittest.TestCase):
    def setUp(self):
        super(TestProductType, self).setUp()
        self.dag = EODataAccessGateway()
        self.product_type = ProductType(dag=self.dag, id="foo")

        # mock os.environ to empty env
        self.mock_os_environ = mock.patch.dict(os.environ, {}, clear=True)
        self.mock_os_environ.start()

    def tearDown(self):
        super(TestProductType, self).tearDown()
        # stop os.environ
        self.mock_os_environ.stop()

    def test_product_type_set_ids_and_alias(self):
        """Product type ids and alias must be correctly set"""
        product_type = ProductType(dag=self.dag, id="foo", alias="bar")

        # check that id attribute has the same value as alias attribute
        self.assertIsInstance(product_type, ProductType)
        self.assertEqual(product_type.id, "bar")
        self.assertEqual(product_type.alias, "bar")

        # check that the internal id attribute is set to the original id
        self.assertEqual(product_type._id, "foo")

    def test_product_type_disable_validation(self):
        """Creation of product type with wrong attributes is allowed
        when validation is disabled (behaviour by default)"""
        try:
            # ensure validation is disabled for product types
            os.environ["EODAG_VALIDATE_PRODUCT_TYPES"] = "False"

            # try to create a product type with a wrong attribute
            # and check that logs have been emitted
            with self.assertLogs(level="DEBUG") as cm:
                product_type = ProductType(
                    dag=self.dag, id="foo", platform=0, bar="bat"
                )

            self.assertIn("Validation failed for the product type foo", str(cm.output))
            self.assertIn("platform\\n  Input should be a valid string", str(cm.output))
            self.assertIn("bar\\n  Extra inputs are not permitted", str(cm.output))

            # check that the product type has been created
            # and that its incorrectly formatted attribute is set to None
            # and its extra attribute is removed
            self.assertIsInstance(product_type, ProductType)
            self.assertEqual(product_type.id, "foo")
            self.assertIsNone(product_type.platform)
            self.assertFalse(getattr(product_type, "bar", False))
        finally:
            # remove the environment variable
            os.environ.pop("EODAG_VALIDATE_PRODUCT_TYPES", None)

    def test_product_type_enable_validation(self):
        """Product type validation is enabled by an environment variable
        to raise errors on wrong product type initialization"""
        try:
            # ensure validation is enabled for product types
            os.environ["EODAG_VALIDATE_PRODUCT_TYPES"] = "True"

            # retry to create a product type with a wrong attribute
            # and check that ValidationError has been raised
            with self.assertRaises(ValidationError) as context:
                ProductType(dag=self.dag, id="foo", platform=0)
            self.assertIn(
                "platform\n  Input should be a valid string", str(context.exception)
            )
        finally:
            # remove the environment variable
            os.environ.pop("EODAG_VALIDATE_PRODUCT_TYPES", None)

    def test_product_type_wrong_id(self):
        """Product type with a missing or wrong id must raise an error
        even if validation of product types is disabled"""
        try:
            # ensure validation is disabled for product types
            os.environ["EODAG_VALIDATE_PRODUCT_TYPES"] = "False"

            # try to create a product type with a missing id
            with self.assertRaises(ValidationError) as context:
                ProductType(dag=self.dag)
            self.assertIn("id\n  Field required", str(context.exception))

            # try to create a product type with a wrong id
            with self.assertRaises(ValidationError) as context:
                ProductType(dag=self.dag, id=1)
            self.assertIn(
                "id\n  Input should be a valid string", str(context.exception)
            )
        finally:
            # remove the environment variable
            os.environ.pop("EODAG_VALIDATE_PRODUCT_TYPES", None)

    def test_product_type_wrong_start_end_mission_date(self):
        """Product type with a start or end mission date not in RFC3339 format
        must raise the custom pydantic error from their field validator"""
        try:
            # ensure validation is activated for product types
            os.environ["EODAG_VALIDATE_PRODUCT_TYPES"] = "True"

            # try to create a product type with a wrong mission start datetime
            with self.assertRaises(ValidationError) as context:
                ProductType(dag=self.dag, id="foo", missionStartDate="not-a-datetime")
            self.assertIn(
                "missionStartDate\n  Input should be a valid datetime string in RFC3339 format",
                str(context.exception),
            )

            # try to create a product type with a wrong mission end datetime
            with self.assertRaises(ValidationError) as context:
                ProductType(dag=self.dag, id="foo", missionEndDate="not-a-datetime")
            self.assertIn(
                "missionEndDate\n  Input should be a valid datetime string in RFC3339 format",
                str(context.exception),
            )
        finally:
            # remove the environment variable
            os.environ.pop("EODAG_VALIDATE_PRODUCT_TYPES", None)

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.search",
        autospec=True,
    )
    def test_product_type_search_ok(self, mock_search):
        """ProductType.search must search for products of this product type"""
        self.product_type.search()
        mock_search.assert_called_once_with(
            self.dag,
            productType=self.product_type.id,
        )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.search",
        autospec=True,
    )
    def test_product_type_search_error(self, mock_search):
        """ProductType.search must raise an error if "productType" kwarg is given"""
        with self.assertRaises(ValidationError) as context:
            self.product_type.search(productType=self.product_type.id)
        self.assertIn(
            "productType should not be set in kwargs since a product type instance is used",
            str(context.exception),
        )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.list_queryables",
        autospec=True,
    )
    def test_product_type_list_queryables_ok(self, mock_search):
        """ProductType.list_queryables must list queryables of this product type"""
        self.product_type.list_queryables()
        mock_search.assert_called_once_with(
            self.dag,
            productType=self.product_type.id,
        )

    @mock.patch(
        "eodag.api.core.EODataAccessGateway.search",
        autospec=True,
    )
    def test_product_type_list_queryables_error(self, mock_search):
        """ProductType.list_queryables must raise an error if "productType" kwarg is given"""
        with self.assertRaises(ValidationError) as context:
            self.product_type.list_queryables(productType=self.product_type.id)
        self.assertIn(
            "productType should not be set in kwargs since a product type instance is used",
            str(context.exception),
        )

    def test_search_result_repr_html(self):
        """ProductType html repr must be correctly formatted"""
        sr_repr = html.fromstring(self.product_type._repr_html_())
        self.assertIn("ProductType", sr_repr.xpath("//thead/tr/td")[0].text)


class TestProductTypesDict(unittest.TestCase):
    def setUp(self):
        super(TestProductTypesDict, self).setUp()
        self.dag = EODataAccessGateway()
        self.product_types_dict = ProductTypesDict(
            [ProductType(dag=self.dag, id="foo")]
        )

    def test_search_result_is_dict_like(self):
        """ProductTypesDict must provide a dict interface"""
        self.assertIsInstance(self.product_types_dict, UserDict)


class TestProductTypesList(unittest.TestCase):
    def setUp(self):
        super(TestProductTypesList, self).setUp()
        self.dag = EODataAccessGateway()
        self.product_types_list = ProductTypesList(
            [ProductType(dag=self.dag, id="foo")]
        )

    def test_search_result_is_list_like(self):
        """ProductTypesList must provide a list interface"""
        self.assertIsInstance(self.product_types_list, UserList)

    def test_search_result_repr_html(self):
        """ProductTypesList html repr must be correctly formatted"""
        sr_repr = html.fromstring(self.product_types_list._repr_html_())
        self.assertIn("ProductTypesList", sr_repr.xpath("//thead/tr/td")[0].text)
