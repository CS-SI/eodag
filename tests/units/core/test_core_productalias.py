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

from eodag import EODataAccessGateway
from eodag.api.collection import Collection
from eodag.utils.exceptions import NoMatchingCollection
from tests.units.core.base import TestCoreBase


class TestCoreProductAlias(TestCoreBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dag = EODataAccessGateway()
        products = cls.dag.collections_config
        products.update(
            {
                "S2_MSI_L1C": Collection.create_with_dag(
                    cls.dag,
                    alias="S2_MSI_ALIAS",
                    **products["S2_MSI_L1C"].model_dump(exclude={"alias"}),
                )
            }
        )

    def test_get_alias_from_collection(self):
        # return product alias
        self.assertEqual(
            "S2_MSI_ALIAS", self.dag.get_alias_from_collection("S2_MSI_L1C")
        )
        # collection without alias
        self.assertEqual("S1_SAR_GRD", self.dag.get_alias_from_collection("S1_SAR_GRD"))
        # not existing collection
        with self.assertRaises(NoMatchingCollection):
            self.dag.get_alias_from_collection("JUST_A_TYPE")

    def test_get_collection_from_alias(self):
        # return product id
        self.assertEqual(
            "S2_MSI_L1C", self.dag.get_collection_from_alias("S2_MSI_ALIAS")
        )
        # collection without alias
        self.assertEqual("S1_SAR_GRD", self.dag.get_collection_from_alias("S1_SAR_GRD"))
        # not existing collection
        with self.assertRaises(NoMatchingCollection):
            self.dag.get_collection_from_alias("JUST_A_TYPE")
