# -*- coding: utf-8 -*-
# Copyright 2025, CS GROUP - France, https://www.cs-soprasteria.com
#
# This file is part of stac-fastapi-eodag project
#     https://www.github.com/CS-SI/stac-fastapi-eodag
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
"""property fields."""

from collections.abc import Callable
from datetime import datetime as dt
from typing import Annotated, Any, ClassVar, Optional, Union, cast

import attr
from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    Field,
    field_serializer,
    model_validator,
)
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.fields import FieldInfo
from stac_pydantic.item import ItemProperties
from stac_pydantic.shared import Provider
from typing_extensions import Self

from eodag.types.stac_extensions import STAC_EXTENSIONS, BaseStacExtension


class CommonStacMetadata(ItemProperties):
    """Common STAC properties."""

    # TODO: replace dt by stac_pydantic.shared.UtcDatetime.
    # Requires timezone to be set in EODAG datetime properties
    # Tested with EFAS FORECAST
    datetime: Annotated[dt, Field(None, validation_alias="start_datetime")]
    start_datetime: Annotated[dt, Field(None)]  # TODO do not set if start = end
    end_datetime: Annotated[dt, Field(None)]  # TODO do not set if start = end
    created: Annotated[dt, Field(None)]
    updated: Annotated[dt, Field(None)]
    platform: Annotated[str, Field(None)]
    instruments: Annotated[list[str], Field(None)]
    constellation: Annotated[str, Field(None)]
    providers: Annotated[list[Provider], Field(None)]
    gsd: Annotated[float, Field(None, gt=0)]
    collection: Annotated[str, Field(None)]
    title: Annotated[str, Field(None)]
    description: Annotated[str, Field(None)]
    license: Annotated[str, Field(None)]

    _conformance_classes: ClassVar[dict[str, str]]
    get_conformance_classes: ClassVar[Callable[[Any], list[str]]]

    @field_serializer(
        "datetime", "start_datetime", "end_datetime", "created", "updated"
    )
    def format_datetime(self, value: dt):
        """format datetime properties"""
        return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    @model_validator(mode="before")
    @classmethod
    def parse_instruments(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        Convert instrument ``str`` to ``list``.
        """
        if instrument := values.get("instruments"):
            values["instruments"] = (
                ",".join(instrument.split()).split(",")
                if isinstance(instrument, str)
                else instrument
            )
            if None in values["instruments"]:
                values["instruments"].remove(None)
        return values

    @model_validator(mode="before")
    @classmethod
    def parse_platform(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        Convert platform ``list`` to ``str``.
        TODO: This should be removed after the refactoring of cop_marine because an item should only have one platform
        """
        if platform := values.get("platform"):
            values["platform"] = (
                ",".join(platform) if isinstance(platform, list) else platform
            )
        return values

    @model_validator(mode="before")
    @classmethod
    def convert_processing_level(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Convert processing level to ``str`` if it is ``int`"""
        if processing_level := values.get("processing:level"):
            if isinstance(processing_level, int):
                values["processing:level"] = f"L{processing_level}"
        return values

    @model_validator(mode="before")
    @classmethod
    def remove_id_property(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        Remove "id" property which is not STAC compliant if exists.
        """
        values.pop("id", None)
        return values

    @model_validator(mode="after")
    def validate_datetime_or_start_end(self) -> Self:
        """disable validation of datetime.

        This model is used for properties conversion not validation.
        """
        return self

    @model_validator(mode="after")
    def validate_start_end(self) -> Self:
        """disable validation of datetime.

        This model is used for properties conversion not validation.
        """
        return self

    @classmethod
    def _create_from_stac_map(
        cls,
    ) -> dict[str, Optional[Union[str, AliasChoices, AliasPath]]]:
        """Create mapping to convert fields from STAC to python-style"""
        return {
            v.serialization_alias or k: v.validation_alias
            for k, v in cls.model_fields.items()
        }

    @classmethod
    def from_stac(cls, field_name: str) -> str:
        """Convert a STAC parameter to its matching python-style name.

        :param field_name: STAC field name
        :returns: EODAG field name
        """
        field_dict: dict[str, Optional[Union[str, AliasChoices, AliasPath]]] = {
            stac_name: py_name
            for stac_name, py_name in cls._create_from_stac_map().items()
            if field_name == stac_name
        }
        if field_dict:
            if field_dict[field_name] is None:
                return field_name
            if isinstance(field_dict[field_name], (AliasChoices, AliasPath)):
                raise NotImplementedError(
                    f"Error for stac name {field_name}: AliasChoices and AliasPath are not currently handled to"
                    "convert stac names to eodag names"
                )
            return field_dict[field_name]  # type: ignore
        return field_name

    @classmethod
    def to_stac(cls, field_name: str) -> str:
        """Convert an python-style parameter to its matching STAC name.

        :param field_name: python-style field name
        :returns: STAC field name
        """
        field_dict: dict[str, Optional[Union[str, AliasChoices, AliasPath]]] = {
            stac_name: py_name
            for stac_name, py_name in cls._create_from_stac_map().items()
            if field_name == py_name
        }
        if field_dict:
            return list(field_dict.keys())[0]
        return field_name


def create_stac_metadata_model(
    extensions: list[BaseStacExtension] = STAC_EXTENSIONS,
    base_models: list[type[BaseModel]] = [CommonStacMetadata],
    class_name: str = "StacMetadata",
) -> type[CommonStacMetadata]:
    """Create a pydantic model to validate item properties.

    :param extensions: list of STAC extensions to include in the model
    :param base_model: base model to extend
    :param class_name: name of the created model
    :returns: pydantic model class
    """
    extension_models: list[ModelMetaclass] = []

    # Check extensions for additional parameters to include
    for extension in extensions:
        if extension_model := extension.FIELDS:
            extension_models.append(extension_model)

    models = base_models + extension_models

    # check for duplicate field aliases (e.g., start_datetime and start in Queryables)
    aliases: dict[str, Optional[str]] = dict()
    duplicates = set()
    for bm in base_models:
        for key, field in bm.model_fields.items():
            if key not in aliases.keys() and key in aliases.values():
                duplicates.add(key)
            else:
                aliases[key] = field.alias

    model: type[CommonStacMetadata] = attr.make_class(
        class_name,
        attrs={},
        bases=tuple(models),
        class_body={
            "_conformance_classes": {
                e.__class__.__name__: e.schema_href for e in extensions
            },
            "get_conformance_classes": _get_conformance_classes,
        },
    )

    for key in duplicates:
        model.model_fields.pop(key)

    return model


def _get_conformance_classes(self) -> list[str]:
    """Extract list of conformance classes from set fields metadata"""
    conformance_classes: set[str] = set()

    model_fields_by_alias = {
        field_info.serialization_alias: field_info
        for name, field_info in self.model_fields.items()
        if field_info.serialization_alias
    }

    for f in self.model_fields_set:
        mf = model_fields_by_alias.get(f) or self.model_fields.get(f)
        if not mf or not isinstance(mf, FieldInfo) or not mf.metadata:
            continue
        extension = next(
            (
                cast(str, m["extension"])
                for m in mf.metadata
                if isinstance(m, dict) and "extension" in m
            ),
            None,
        )
        if c := self._conformance_classes.get(extension, None):
            conformance_classes.add(c)

    return list(conformance_classes)
