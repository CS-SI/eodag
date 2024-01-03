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
from typing import Optional

from annotated_types import Lt
from pydantic import BaseModel, Field
from pydantic.types import PositiveInt
from typing_extensions import Annotated

Percentage = Annotated[PositiveInt, Lt(100)]


class CommonQueryables(BaseModel):
    """A class representing search common queryable properties."""

    productType: Annotated[str, Field()]
    id: Annotated[Optional[str], Field(None)]
    start: Annotated[Optional[str], Field(None, alias="startTimeFromAscendingNode")]
    end: Annotated[Optional[str], Field(None, alias="completionTimeFromAscendingNode")]
    geom: Annotated[Optional[str], Field(None, alias="geometry")]


class Queryables(CommonQueryables):
    """A class representing all search queryable properties."""

    uid: Annotated[Optional[str], Field(None)]
    # OpenSearch Parameters for Collection Search (Table 3)
    doi: Annotated[Optional[str], Field(None)]
    platform: Annotated[Optional[str], Field(None)]
    platformSerialIdentifier: Annotated[Optional[str], Field(None)]
    instrument: Annotated[Optional[str], Field(None)]
    sensorType: Annotated[Optional[str], Field(None)]
    compositeType: Annotated[Optional[str], Field(None)]
    processingLevel: Annotated[Optional[str], Field(None)]
    orbitType: Annotated[Optional[str], Field(None)]
    spectralRange: Annotated[Optional[str], Field(None)]
    wavelengths: Annotated[Optional[str], Field(None)]
    hasSecurityConstraints: Annotated[Optional[str], Field(None)]
    dissemination: Annotated[Optional[str], Field(None)]
    # INSPIRE obligated OpenSearch Parameters for Collection Search (Table 4)
    title: Annotated[Optional[str], Field(None)]
    topicCategory: Annotated[Optional[str], Field(None)]
    keyword: Annotated[Optional[str], Field(None)]
    abstract: Annotated[Optional[str], Field(None)]
    resolution: Annotated[Optional[int], Field(None)]
    organisationName: Annotated[Optional[str], Field(None)]
    organisationRole: Annotated[Optional[str], Field(None)]
    publicationDate: Annotated[Optional[str], Field(None)]
    lineage: Annotated[Optional[str], Field(None)]
    useLimitation: Annotated[Optional[str], Field(None)]
    accessConstraint: Annotated[Optional[str], Field(None)]
    otherConstraint: Annotated[Optional[str], Field(None)]
    classification: Annotated[Optional[str], Field(None)]
    language: Annotated[Optional[str], Field(None)]
    specification: Annotated[Optional[str], Field(None)]
    # OpenSearch Parameters for Product Search (Table 5)
    parentIdentifier: Annotated[Optional[str], Field(None)]
    productionStatus: Annotated[Optional[str], Field(None)]
    acquisitionType: Annotated[Optional[str], Field(None)]
    orbitNumber: Annotated[Optional[int], Field(None)]
    orbitDirection: Annotated[Optional[str], Field(None)]
    track: Annotated[Optional[str], Field(None)]
    frame: Annotated[Optional[str], Field(None)]
    swathIdentifier: Annotated[Optional[str], Field(None)]
    cloudCover: Annotated[Optional[Percentage], Field(None)]
    snowCover: Annotated[Optional[Percentage], Field(None)]
    lowestLocation: Annotated[Optional[str], Field(None)]
    highestLocation: Annotated[Optional[str], Field(None)]
    productVersion: Annotated[Optional[str], Field(None)]
    productQualityStatus: Annotated[Optional[str], Field(None)]
    productQualityDegradationTag: Annotated[Optional[str], Field(None)]
    processorName: Annotated[Optional[str], Field(None)]
    processingCenter: Annotated[Optional[str], Field(None)]
    creationDate: Annotated[Optional[str], Field(None)]
    modificationDate: Annotated[Optional[str], Field(None)]
    processingDate: Annotated[Optional[str], Field(None)]
    sensorMode: Annotated[Optional[str], Field(None)]
    archivingCenter: Annotated[Optional[str], Field(None)]
    processingMode: Annotated[Optional[str], Field(None)]
    # OpenSearch Parameters for Acquistion Parameters Search (Table 6)
    availabilityTime: Annotated[Optional[str], Field(None)]
    acquisitionStation: Annotated[Optional[str], Field(None)]
    acquisitionSubType: Annotated[Optional[str], Field(None)]
    illuminationAzimuthAngle: Annotated[Optional[str], Field(None)]
    illuminationZenithAngle: Annotated[Optional[str], Field(None)]
    illuminationElevationAngle: Annotated[Optional[str], Field(None)]
    polarizationMode: Annotated[Optional[str], Field(None)]
    polarizationChannels: Annotated[Optional[str], Field(None)]
    antennaLookDirection: Annotated[Optional[str], Field(None)]
    minimumIncidenceAngle: Annotated[Optional[float], Field(None)]
    maximumIncidenceAngle: Annotated[Optional[float], Field(None)]
    dopplerFrequency: Annotated[Optional[float], Field(None)]
    incidenceAngleVariation: Annotated[Optional[float], Field(None)]
