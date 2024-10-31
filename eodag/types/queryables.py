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
from datetime import date, datetime
from typing import Annotated, Any, Optional, Union

from annotated_types import Lt
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo
from pydantic.types import PositiveInt

from eodag.types import model_fields_to_annotated

Percentage = Annotated[PositiveInt, Lt(100)]


class CommonQueryables(BaseModel):
    """A class representing search common queryable properties."""

    product_type: Annotated[str, Field(alias="productType")]

    @classmethod
    def get_queryable_from_alias(cls, value: str) -> str:
        """Get queryable parameter from alias
        >>> CommonQueryables.get_queryable_from_alias('productType')
        'productType'
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
