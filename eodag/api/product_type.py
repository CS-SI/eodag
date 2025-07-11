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
from __future__ import annotations

import re
from collections import UserDict, UserList
from typing import TYPE_CHECKING, Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    field_validator,
    model_validator,
)

from eodag.utils.exceptions import ValidationError
from eodag.utils.repr import dict_to_html_table

if TYPE_CHECKING:
    from typing_extensions import Self

RFC3339_PATTERN = (
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:T(\d{2}):(\d{2}):(\d{2})(\.\d+)?"
    r"(Z|([+-])(\d{2}):(\d{2}))?)?$"
)


class ProductType(BaseModel):
    """A class representing a product type."""

    id: str = Field()
    title: Optional[str] = Field(default=None)
    missionStartDate: Optional[str] = Field(
        default=None,
        description="Date/time as string in ISO 8601 format (e.g. '2024-06-10T12:00:00Z')",
    )
    missionEndDate: Optional[str] = Field(
        default=None,
        description="Date/time as string in ISO 8601 format (e.g. '2024-06-10T12:00:00Z')",
    )
    processingLevel: Optional[str] = Field(default=None)
    instrument: Optional[str] = Field(default=None)
    platform: Optional[str] = Field(default=None)
    platformSerialIdentifier: Optional[str] = Field(default=None)
    sensorType: Optional[str] = Field(default=None)
    keywords: Optional[str] = Field(default=None)
    license: Optional[str] = Field(default=None)
    abstract: Optional[str] = Field(default=None)
    alias: Optional[str] = Field(
        default=None,
        description="An alias given by a user to use his customized id intead of the internal id of EODAG",
        repr=False,
    )

    # Private property to store the eodag internal id values. Not part of the model schema.
    _id: str = PrivateAttr()

    model_config = ConfigDict(extra="forbid")

    def model_post_init(self, context: Any) -> None:
        """Post-initialization method to set the internal id."""
        self._id = self.id

    @field_validator("missionStartDate", "missionEndDate")
    @classmethod
    def validate_start_end_mission_date(cls, value: Optional[str]) -> Optional[str]:
        """
        datetimes must be valid RFC3339 strings
        we assume that only one missionStartDate/missionEndDate filter is used
        """
        if value is None:
            return value

        # Uppercase the string
        value = value.upper()

        # Match against RFC3339 regex.
        result = re.match(RFC3339_PATTERN, value)
        if not result:
            raise ValidationError("Invalid RFC3339 datetime.")

        return value

    @model_validator(mode="after")
    def set_id_from_alias(self) -> Self:
        """if an alias exists, use it to update id attribute"""
        if self.alias is not None:
            self.id = self.alias
        return self

    def __str__(self) -> str:
        return f'ProductType("{self.id}")'

    def __repr_str__(self, join_str: str) -> str:
        return join_str.join(
            repr(v) if a is None else f"{a}={v!r}"
            for a, v in self.__repr_args__()
            if v is not None
        )

    def _repr_html_(self, embedded: bool = False) -> str:
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                {type(self).__name__}("{self.id}")</td></tr></thead>
            """
            if not embedded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embedded else ""
        pt_html_table = dict_to_html_table(
            self.model_dump(exclude={"alias"}), depth=1, brackets=False
        )

        return (
            f"<table>{thead}<tbody>"
            f"<tr {tr_style}><td style='text-align: left;'>"
            f"{pt_html_table}</td></tr>"
            "</tbody></table>"
        )

    # TODO: Add a method to do a search from the product type

    # TODO: Add a method to list queryables from the product type


class ProductTypesDict(UserDict[str, ProductType]):
    """A UserDict object which values are :class:`~eodag.api.product_type.ProductType` objects, keyed by provider id.

    :param product_types: A list of product types

    :cvar data: List of product types
    """

    def __init__(
        self,
        product_types: list[ProductType],
    ) -> None:
        super().__init__()

        self.data = {pt.id: pt for pt in product_types}


class ProductTypesList(UserList[ProductType]):
    """An object representing a collection of :class:`~eodag.api.product_type.ProductType`.

    :param product_types: A list of product types

    :cvar data: List of product types
    """

    def __init__(
        self,
        product_types: list[ProductType],
    ) -> None:
        super().__init__(product_types)

    def _repr_html_(self, embedded: bool = False) -> str:
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                {type(self).__name__}&ensp;({len(self)})</td></tr></thead>
            """
            if not embedded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embedded else ""

        return (
            f"<table>{thead}<tbody>"
            + "".join(
                [
                    f"""<tr {tr_style}><td style='text-align: left;'>
                        <details><summary style='color: grey;'>
                        <span style='color: black'>{pt}</span>:&ensp;
                        title={pt.title},&ensp;...
                    </summary>
                    {re.sub(r"(<thead>.*|.*</thead>)", "", pt._repr_html_())}
                    </details>
                    </td></tr>
                    """
                    for pt in self
                ]
            )
            + "</tbody></table>"
        )
