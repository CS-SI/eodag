# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
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
from collections import UserDict
from datetime import date, datetime
from typing import Annotated, Any, Optional, Union

from annotated_types import Lt
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo
from pydantic.types import PositiveInt

from eodag.types import annotated_dict_to_model, model_fields_to_annotated

Percentage = Annotated[PositiveInt, Lt(100)]


class CommonQueryables(BaseModel):
    """A class representing search common queryable properties."""

    product_type: Annotated[str, Field(alias="productType")]

    @classmethod
    def get_queryable_from_alias(cls, value: str) -> str:
        """Get queryable parameter from alias
        >>> CommonQueryables.get_queryable_from_alias('productType')
        'product_type'
        """
        alias_map = {
            field_info.alias: name
            for name, field_info in cls.model_fields.items()
            if field_info.alias
        }
        return alias_map.get(value, value)

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


class Queryables(CommonQueryables):
    """A class representing all search queryable properties."""

    start: Annotated[
        Union[datetime, date], Field(None, alias="startTimeFromAscendingNode")
    ]
    end: Annotated[
        Union[datetime, date], Field(None, alias="completionTimeFromAscendingNode")
    ]
    geom: Annotated[str, Field(None, alias="geometry")]
    uid: Annotated[str, Field(None)]
    # OpenSearch Parameters for Collection Search (Table 3)
    doi: Annotated[str, Field(None)]
    platform: Annotated[str, Field(None)]
    platformSerialIdentifier: Annotated[str, Field(None)]
    instrument: Annotated[str, Field(None)]
    sensorType: Annotated[str, Field(None)]
    compositeType: Annotated[str, Field(None)]
    processingLevel: Annotated[str, Field(None)]
    orbitType: Annotated[str, Field(None)]
    spectralRange: Annotated[str, Field(None)]
    wavelengths: Annotated[str, Field(None)]
    hasSecurityConstraints: Annotated[str, Field(None)]
    dissemination: Annotated[str, Field(None)]
    # INSPIRE obligated OpenSearch Parameters for Collection Search (Table 4)
    title: Annotated[str, Field(None)]
    topicCategory: Annotated[str, Field(None)]
    keyword: Annotated[str, Field(None)]
    abstract: Annotated[str, Field(None)]
    resolution: Annotated[int, Field(None)]
    organisationName: Annotated[str, Field(None)]
    organisationRole: Annotated[str, Field(None)]
    publicationDate: Annotated[str, Field(None)]
    lineage: Annotated[str, Field(None)]
    useLimitation: Annotated[str, Field(None)]
    accessConstraint: Annotated[str, Field(None)]
    otherConstraint: Annotated[str, Field(None)]
    classification: Annotated[str, Field(None)]
    language: Annotated[str, Field(None)]
    specification: Annotated[str, Field(None)]
    # OpenSearch Parameters for Product Search (Table 5)
    parentIdentifier: Annotated[str, Field(None)]
    productionStatus: Annotated[str, Field(None)]
    acquisitionType: Annotated[str, Field(None)]
    orbitNumber: Annotated[int, Field(None)]
    orbitDirection: Annotated[str, Field(None)]
    track: Annotated[str, Field(None)]
    frame: Annotated[str, Field(None)]
    swathIdentifier: Annotated[str, Field(None)]
    cloudCover: Annotated[Percentage, Field(None)]
    snowCover: Annotated[Percentage, Field(None)]
    lowestLocation: Annotated[str, Field(None)]
    highestLocation: Annotated[str, Field(None)]
    productVersion: Annotated[str, Field(None)]
    productQualityStatus: Annotated[str, Field(None)]
    productQualityDegradationTag: Annotated[str, Field(None)]
    processorName: Annotated[str, Field(None)]
    processingCenter: Annotated[str, Field(None)]
    creationDate: Annotated[str, Field(None)]
    modificationDate: Annotated[str, Field(None)]
    processingDate: Annotated[str, Field(None)]
    sensorMode: Annotated[str, Field(None)]
    archivingCenter: Annotated[str, Field(None)]
    processingMode: Annotated[str, Field(None)]
    # OpenSearch Parameters for Acquistion Parameters Search (Table 6)
    availabilityTime: Annotated[str, Field(None)]
    acquisitionStation: Annotated[str, Field(None)]
    acquisitionSubType: Annotated[str, Field(None)]
    illuminationAzimuthAngle: Annotated[str, Field(None)]
    illuminationZenithAngle: Annotated[str, Field(None)]
    illuminationElevationAngle: Annotated[str, Field(None)]
    polarizationMode: Annotated[str, Field(None)]
    polarizationChannels: Annotated[str, Field(None)]
    antennaLookDirection: Annotated[str, Field(None)]
    minimumIncidenceAngle: Annotated[float, Field(None)]
    maximumIncidenceAngle: Annotated[float, Field(None)]
    dopplerFrequency: Annotated[float, Field(None)]
    incidenceAngleVariation: Annotated[float, Field(None)]


class QueryablesDict(UserDict):
    """Class inheriting from UserDict which contains queryables with their annotated type;

    :param additional_properties: if additional properties (properties not given in EODAG config)
                                  are allowed
    :param kwargs: named arguments to initialise the dict (queryable keys + annotated types)
    """

    additional_properties: bool = Field(True)

    def __init__(self, additional_properties: bool, **kwargs):
        self.additional_properties = additional_properties
        super().__init__(kwargs)

    def _repr_html_(self, embedded: bool = False):
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                        {type(self).__name__}&ensp;({len(self)})
                        </td></tr></thead>
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
                            <span style='color: black'>'{k}'</span>:&ensp;
                            {{
                                {"'alias': '<span style='color: black'>" + v.__metadata__[0].alias + "</span>',&ensp;"
                if v.__metadata__[0].alias else ""}
                                {"'type': '<span style='color: black'>" + str(v.__args__[0]) + "</span>',&ensp;"
                if not hasattr(v.__args__[0], "__name__") or v.__args__[0].__name__ == "Union" else(
                                "'type': '<span style='color: black'>" + v.__args__[0].__name__ + "</span>',&ensp;")}
                                {"'default': '<span style='color: black'>" +
                                 str(v.__metadata__[0].get_default()) + "</span>',&ensp;"
                if v.__metadata__[0].get_default() else ""}
                                {"'required': '<span style='color: black'>" +
                                 str(v.__metadata__[0].is_required()) + "</span>',&ensp;"}
                            }}
                        </summary>
                        </details>
                        </td></tr>
                        """
                    for k, v in self.items()
                ]
            )
            + "</tbody></table>"
        )

    def get_model(self) -> BaseModel:
        """
        Converts object from :class:`eodag.api.product.QueryablesDict` to :class:`pydantic.BaseModel`
        so that validation can be performed

        :returns: pydantic BaseModel of the queryables dict
        """
        return annotated_dict_to_model("Queryables", self.data)
