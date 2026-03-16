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
from collections import UserDict
from typing import TYPE_CHECKING, Annotated, Any, Optional, Union, cast

from annotated_types import Lt
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from pydantic.fields import FieldInfo
from pydantic.types import PositiveInt
from pydantic_core import PydanticUndefined
from shapely.geometry.base import BaseGeometry
from typing_extensions import get_args

from eodag.types import (
    BaseModelCustomJsonSchema,
    annotated_dict_to_model,
    model_fields_to_annotated,
)
from eodag.types.stac_extensions import STAC_EXTENSIONS
from eodag.types.stac_metadata import CommonStacMetadata, create_stac_metadata_model
from eodag.utils.dates import (
    COMPACT_DATE_PATTERN,
    COMPACT_DATE_RANGE_PATTERN,
    DATE_PATTERN,
    DATE_RANGE_PATTERN,
    datetime_range,
    format_date,
    format_date_range,
    is_range_in_range,
    parse_date,
)
from eodag.utils.repr import remove_class_repr, shorter_type_repr

if TYPE_CHECKING:
    from eodag.types.stac_extensions import BaseStacExtension

Percentage = Annotated[PositiveInt, Lt(100)]


class CommonQueryables(BaseModelCustomJsonSchema):
    """A class representing search common queryable properties."""

    collection: Annotated[str, Field()]

    @classmethod
    def get_queryable_from_alias(cls, value: str) -> str:
        """Get queryable parameter from alias

        >>> CommonQueryables.get_queryable_from_alias('collection')
        'collection'
        """
        for name, field_info in cls.model_fields.items():
            if field_info.alias:
                if isinstance(field_info.alias, AliasChoices):
                    aliases = field_info.alias.choices
                    if value in aliases:
                        return name
                else:
                    if value == field_info.alias:
                        return name

        return value

    @classmethod
    def get_with_default(
        cls, field: str, default: Optional[Any]
    ) -> Annotated[Any, FieldInfo]:
        """Get field and set default value."""
        annotated_fields = model_fields_to_annotated(cls.model_fields)
        f = annotated_fields[field]
        if default is None:
            return f
        f.__metadata__[0].default = default
        return f

    @classmethod
    def from_stac_models(
        cls,
        extensions: list[BaseStacExtension] = STAC_EXTENSIONS,
        base_model: type[BaseModel] = CommonStacMetadata,
    ) -> type[Queryables]:
        """Creates Queryables from STAC models.

        :param extensions: list of STAC extensions to include in the model
        :param base_model: base STAC model to use
        :return: Queryables model
        """
        return cast(
            type[Queryables],
            create_stac_metadata_model(
                base_models=[cls, base_model],
                extensions=extensions,
                class_name="Queryables",
            ),
        )


class Queryables(CommonQueryables):
    """A class representing all search queryable properties.

    Parameters default value is set to ``None`` to have them not required.
    Fields described here are queryables-specific and complete StacMetadata fields.
    """

    start: Annotated[
        str,
        Field(
            None,
            alias=AliasChoices("start_datetime", "datetime"),
            description="Date/time as string in ISO 8601 format (e.g. '2024-06-10T12:00:00Z')",
        ),
    ]
    end: Annotated[
        str,
        Field(
            None,
            alias="end_datetime",
            description="Date/time as string in ISO 8601 format (e.g. '2024-06-10T12:00:00Z')",
        ),
    ]
    geom: Annotated[
        Union[str, dict[str, float], BaseGeometry],
        Field(
            None,
            alias=AliasChoices("geometry", "intersects"),
            description="Read EODAG documentation for all supported geometry format.",
        ),
    ]
    id: Annotated[str, Field(None)]

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("ecmwf_date", mode="plain", check_fields=False)
    @classmethod
    def check_date_range(cls, v: str) -> str:
        """Validate date ranges"""
        if not isinstance(v, str):
            raise ValueError(
                "date must be a string formatted as single date ('yyyy-mm-dd') or range ('yyyy-mm-dd/yyyy-mm-dd')"
            )
        date_regex = [
            re.compile(p)
            for p in (
                DATE_PATTERN,
                COMPACT_DATE_PATTERN,
                DATE_RANGE_PATTERN,
                COMPACT_DATE_RANGE_PATTERN,
            )
        ]
        if not any(r.match(v) is not None for r in date_regex):
            raise ValueError(
                "date must be a string formatted as single date ('yyyy-mm-dd') or range ('yyyy-mm-dd/yyyy-mm-dd')"
            )
        try:
            start, end = parse_date(v)
        except ValueError as e:
            raise ValueError("date must follow 'yyyy-mm-dd' format") from e
        if end < start:
            raise ValueError("date range end must be after start")
        # enumerate dates in range
        v_set: set[str] = {format_date(d) for d in datetime_range(start, end)}
        # is_range_in_range() support only ranges (no single date allowed) in the format 'yyyy-mm-dd/yyyy-mm-dd'
        v_range: str = format_date_range(start, end)

        field_info = cls.model_fields["ecmwf_date"]
        literals = get_args(field_info.annotation)

        # Collect missing values to report errors
        missing_values = set(v_set)

        # date constraint may be intervals. We identify intervals with a "/" in the value.
        # date constraint can be a mixed list of single values (e.g "2023-06-27")
        # and intervals (e.g. "2024-11-12/2025-11-20")
        # collections with mixed values: CAMS_GAC_FORECAST, CAMS_EU_AIR_QUALITY_FORECAST
        for literal in literals:
            literal_start, literal_end = parse_date(literal)
            if "/" in literal:
                # range with separator / or /to/
                literal_range: str = format_date_range(literal_start, literal_end)
                if is_range_in_range(literal_range, v_range):
                    return v
            else:
                # convert literal to the format 'yyyy-mm-dd'
                literal_start_str = format_date(literal_start)
                if literal_start_str in v_set:
                    missing_values.remove(literal_start_str)
                if not missing_values:
                    return v

        raise ValueError("date not allowed")


class QueryablesDict(UserDict[str, Any]):
    """Class inheriting from UserDict which contains queryables with their annotated type;

    :param additional_properties: if additional properties (properties not given in EODAG config)
                                  are allowed
    :param kwargs: named arguments to initialise the dict (queryable keys + annotated types)
    """

    additional_properties: bool = Field(True)
    additional_information: str = Field("")

    def __init__(
        self,
        additional_properties: bool = True,
        additional_information: str = "",
        **kwargs: Any,
    ):
        self.additional_properties = additional_properties
        self.additional_information = additional_information
        super().__init__(kwargs)
        # sort queryables: first without then with extension prefix
        no_prefix_queryables = {
            key: self.data[key]
            for key in sorted(self.data)
            if ":"
            not in str(
                getattr(self.data[key], "__metadata__", [Field()])[0].alias or key
            )
        }
        with_prefix_queryables = {
            key: self.data[key]
            for key in sorted(self.data)
            if ":"
            in str(getattr(self.data[key], "__metadata__", [Field()])[0].alias or key)
        }
        self.data = no_prefix_queryables | with_prefix_queryables

    def _repr_html_(self, embedded: bool = False) -> str:
        add_info = (
            f"&ensp;additional_information={self.additional_information}"
            if self.additional_information
            else ""
        )
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                {type(self).__name__}&ensp;({len(self)})&ensp;-&ensp;additional_properties={
                self.additional_properties}
            """
            + add_info
            + "</td></tr></thead>"
            if not embedded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embedded else ""
        table = f"<table>{thead}<tbody>"
        table_rows = []
        for k, v in self.items():
            alias = v.__metadata__[0].validation_alias
            if not alias or alias == PydanticUndefined:
                alias = v.__metadata__[0].alias
            if not alias or alias == PydanticUndefined:
                alias = v.__metadata__[0].serialization_alias
            if isinstance(alias, AliasChoices):
                alias_str = (
                    "'alias': '<span style='color:grey'>AliasChoices(choices=[</span>'"
                    + "'<span style='color:black'>"
                    + '", "'.join([str(c) for c in alias.choices])
                    + "</span>'"
                    + "'<span style='color:grey'>])</span>',&ensp;"
                )
            elif alias and alias != PydanticUndefined:
                alias_str = (
                    "'alias': '<span style='color:black'>"
                    + str(alias)
                    + "</span>',&ensp;"
                )
            else:
                alias_str = ""

            table_row = f"""<tr {tr_style}><td style='text-align: left;'>
                        <details><summary style='color: grey;'>
                        <span style='color: black'>'{k}'</span>:&ensp;
                        typing.Annotated[{
                        "<span style='color: black'>" + shorter_type_repr(v.__args__[0]) + "</span>,&ensp;"}
                        FieldInfo({"'default': '<span style='color: black'>"
                                   + str(v.__metadata__[0].get_default()) + "</span>',&ensp;"
                                   if v.__metadata__[0].get_default()
                                   and v.__metadata__[0].get_default() != PydanticUndefined else ""}
                                  {"'required': <span style='color: black'>"
                                   + str(v.__metadata__[0].is_required()) + "</span>,"
                                   if v.__metadata__[0].is_required() else ""}
                                  {alias_str}
                                  ...
                                 )]
                        </summary>
                            <span style='color: grey'>typing.Annotated[</span><table style='margin: 0;'>
                                <tr style='background-color: transparent;'>
                                    <td style='padding: 5px 0 0 10px; text-align: left; vertical-align:top;'>
                                    {remove_class_repr(str(v.__args__[0]))},</td>
                                </tr><tr style='background-color: transparent;'>
                                    <td style='padding: 5px 0 0 10px; text-align: left; vertical-align:top;'>
                                    {v.__metadata__[0].__repr__()}</td>
                                </tr>
                            </table><span style='color: grey'>]</span>
                        </details>
                        </td></tr>
                        """
            table_rows.append(table_row)
        table += "".join(table_rows)
        table += "</tbody></table>"
        return table

    def get_model(self, model_name: str = "Queryables") -> BaseModel:
        """
        Converts object from :class:`eodag.api.product.QueryablesDict` to :class:`pydantic.BaseModel`
        so that validation can be performed

        :param model_name: name used for :class:`pydantic.BaseModel` creation
        :return: pydantic BaseModel of the queryables dict
        """
        return annotated_dict_to_model(model_name, self.data, Queryables)
