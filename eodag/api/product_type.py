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

import logging
import re
from collections import UserDict, UserList
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from pydantic import ValidationError as PydanticValidationError
from pydantic import field_validator, model_validator
from pydantic_core import ErrorDetails, InitErrorDetails, PydanticCustomError

from eodag.utils.env import is_env_var_true
from eodag.utils.exceptions import ValidationError
from eodag.utils.repr import dict_to_html_table

if TYPE_CHECKING:
    from pydantic import ModelWrapValidatorHandler
    from typing_extensions import Self

    from eodag.api.core import EODataAccessGateway
    from eodag.api.search_result import SearchResult
    from eodag.types.queryables import QueryablesDict

logger = logging.getLogger("eodag.api.product_type")

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
    _dag: EODataAccessGateway = PrivateAttr()

    # allow extra attributes in the model to accept "dag" attribute
    # however other extra attributes will raise an error during validation
    model_config = ConfigDict(extra="allow")

    def __init__(__pydantic_self__, dag: EODataAccessGateway, **values: Any) -> None:
        """
        Constructror to make linters pass during model calls with "dag" parameter.
        This parameter will allow to set "_dag" private attribute during validation.

        :param dag: The gateway instance to use to search products and to list queryables of the product type instance
        """
        super().__init__(**{"dag": dag, **values})

    def model_post_init(self, context: Any) -> None:
        """Post-initialization method to set internal attributes."""
        self._id = self.id
        # set "_dag" private attribute and remove "dag" public one created during the validation
        self._dag = getattr(self, "dag")
        delattr(self, "dag")

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

        # Match against RFC3339 regex
        result = re.match(RFC3339_PATTERN, value)
        if not result:
            raise PydanticCustomError(
                "string_type",
                "Input should be a valid datetime string in RFC3339 format (e.g. '2024-06-10T12:00:00Z')",
            )

        return value

    @model_validator(mode="before")
    @classmethod
    def remove_extra_attributes(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Remove extra attributes not defined in the model (except "dag") if any"""
        allowed_keys = set(cls.model_fields.keys())
        extra_keys = set(values.keys()) - allowed_keys
        errors: list[InitErrorDetails] = []

        for key in extra_keys:
            if key != "dag":
                error = InitErrorDetails(
                    type=PydanticCustomError(
                        "extra_forbidden", "Extra inputs are not permitted"
                    ),
                    loc=(key,),
                    input=values[key],
                )
                errors.append(error)

        if errors:
            raise PydanticValidationError.from_exception_data(
                title=cls.__name__, line_errors=errors
            )

        return values

    @model_validator(mode="after")
    def set_id_from_alias(self) -> Self:
        """if an alias exists, use it to update id attribute"""
        if self.alias is not None:
            self.id = self.alias
        return self

    @model_validator(mode="wrap")
    @classmethod
    def validate_product_type(
        cls, values: dict[str, Any] | Self, handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        """Allow to create a product type instance with bad formatted attributes (except "id").
        Set incorrectly formatted attributes to None and ignore extra attributes.
        Log a warning about validation errors if EODAG_VALIDATE_PRODUCT_TYPES is set to True.
        """
        errors: list[ErrorDetails] = []
        continue_validation: bool = True

        # iterate over each step of validation where error(s) raise(s)
        while continue_validation:
            try:
                handler(values)
            except PydanticValidationError as e:
                tmp_errors = e.errors()
                # raise an error if the id is invalid
                if any(error["loc"][0] == "id" for error in tmp_errors):
                    raise ValidationError.from_error(e) from e

                # convert values to dict if it is a model instance
                values_dict = values if isinstance(values, dict) else values.__dict__

                # set incorrectly formatted attribute(s) to None and ignore its extra attribute(s)
                for error in tmp_errors:
                    wrong_param = error["loc"][0]
                    if not isinstance(wrong_param, str):
                        continue
                    if wrong_param not in cls.model_fields:
                        del values_dict[wrong_param]
                    else:
                        values_dict[wrong_param] = None

                errors.extend(tmp_errors)
            else:
                continue_validation = False

        # log a warning if there were validation errors and the env var is set to True
        if errors and is_env_var_true("EODAG_VALIDATE_PRODUCT_TYPES"):
            # log all errors at once
            error_title = f'product type {values_dict["id"]}'
            init_errors: list[InitErrorDetails] = [
                InitErrorDetails(
                    type=PydanticCustomError(error["type"], error["msg"]),
                    loc=error["loc"],
                    input=error["input"],
                )
                for error in errors
            ]
            pydantic_error = PydanticValidationError.from_exception_data(
                title=error_title, line_errors=init_errors
            )
            logger.warning(pydantic_error)

        # Create a fresh instance with the cleaned values
        return handler(values)

    def __str__(self) -> str:
        return f'{type(self).__name__}("{self.id}")'

    def __repr_str__(self, join_str: str) -> str:
        return join_str.join(
            repr(v) if a is None else f"{a}={v!r}"
            for a, v in self.__repr_args__()
            if v is not None
        )

    def _repr_html_(self, embedded: bool = False) -> str:
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                {type(self).__name__}("<span style='color: black'>{self.id}</span>")</td></tr></thead>
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

    def search(self, **kwargs: Any) -> SearchResult:
        """Look for products of this product type matching criteria using the `dag` attribute of the instance.

        :param kwargs: Some other criteria that will be used to do the search,
                       using parameters compatible with the provider

        :returns: A collection of EO products matching the criteria.
        :raises: :class:`~eodag.utils.exceptions.ValidationError`: If the `productType` argument is set in `kwargs`,
                                                                   since it is already defined by the instance
        """
        product_type_search_arg = "productType"
        if product_type_search_arg in kwargs:
            raise ValidationError(
                f"{product_type_search_arg} should not be set in kwargs since a product type instance is used",
                {product_type_search_arg},
            )

        return self._dag.search(productType=self.id, **kwargs)

    def list_queryables(self, **kwargs: Any) -> QueryablesDict:
        """Fetch the queryable properties for this product type using the `dag` attribute of the instance.

        :param kwargs: additional filters for queryables

        :returns: A :class:`~eodag.api.product.queryables.QuerybalesDict` containing the EODAG queryable
                  properties, associating parameters to their annotated type, and a additional_properties attribute
        :raises: :class:`~eodag.utils.exceptions.ValidationError`: If the `productType` argument is set in `kwargs`,
                                                                   since it is already defined by the instance
        """
        product_type_search_arg = "productType"
        if product_type_search_arg in kwargs:
            raise ValidationError(
                f"{product_type_search_arg} should not be set in kwargs since a product type instance is used",
                {product_type_search_arg},
            )

        return self._dag.list_queryables(productType=self.id, **kwargs)


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

    def __str__(self) -> str:
        return "{" + ", ".join(f'"{pt}": {pt_f}' for pt, pt_f in self.items()) + "}"

    def __repr__(self) -> str:
        return str(self)


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

    def __str__(self) -> str:
        return f"{type(self).__name__}([{", ".join(str(pt) for pt in self)}])"

    def __repr__(self) -> str:
        return str(self)

    def _repr_html_(self, embedded: bool = False) -> str:
        # mock "thead" tag by reproduicing its style to make "details" and "summary" tags work properly
        mock_thead = (
            f"""<details class='foldable'>
                <summary style='text-align: left; color: grey; font-size: 12px;'>
                {type(self).__name__}&ensp;({len(self)})
                </summary>
            """
            if not embedded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embedded else ""

        return (
            f"{mock_thead}<table><tbody>"
            + "".join(
                [
                    f"""<tr {tr_style}><td style='text-align: left;'>
                        <details>
                        <summary style='color: grey; font-family: monospace;'>
                        {i}&ensp;
                        {type(pt).__name__}("<span style='color: black'>{pt.id}</span>")
                    </summary>
                    {re.sub(r"(<thead>.*|.*</thead>)", "", pt._repr_html_())}
                    </details>
                    </td></tr>
                    """
                    for i, pt in enumerate(self)
                ]
            )
            + "</tbody></table></details>"
        )
