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
"""STAC extensions."""

from typing import Annotated, Any, Optional, Union

from annotated_types import Ge, Le
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from eodag.utils import ONLINE_STATUS

Percentage = Annotated[float, Ge(0), Le(100)]


class BaseStacExtension(BaseModel):
    """Abstract base class for defining STAC extensions."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    FIELDS: Optional[type[BaseModel]] = None
    schema_href: Optional[str] = None
    field_name_prefix: Optional[str] = None

    @model_validator(mode="after")
    def setup_field_aliases(self) -> "BaseStacExtension":
        """Add serialization validation_alias to extension properties
        and extension metadata to the field.
        """
        if self.field_name_prefix is None:
            return self

        fields: dict[str, Any] = getattr(self.FIELDS, "model_fields", {})
        for k, v in fields.items():
            v.alias = v.serialization_alias = v.validation_alias = k.replace(
                f"{self.field_name_prefix}_", f"{self.field_name_prefix}:"
            )
            v.metadata.insert(0, {"extension": self.__class__.__name__})
        return self


class SarFields(BaseModel):
    """
    https://github.com/stac-extensions/sar#item-properties-or-asset-fields
    """

    sar_instrument_mode: Optional[str] = Field(None)
    sar_frequency_band: Optional[str] = Field(None)
    sar_center_frequency: Optional[float] = Field(None)
    sar_polarizations: Optional[list[str]] = Field(None)
    sar_resolution_range: Optional[float] = Field(None)
    sar_resolution_azimuth: Optional[float] = Field(None)
    sar_pixel_spacing_range: Optional[float] = Field(None)
    sar_pixel_spacing_azimuth: Optional[float] = Field(None)
    sar_looks_range: Optional[int] = Field(None)
    sar_looks_azimuth: Optional[int] = Field(None)
    sar_looks_equivalent_number: Optional[float] = Field(None)
    sar_observation_direction: Optional[str] = Field(None)
    sar_relative_burst: Optional[int] = Field(None)
    sar_beam_ids: Optional[list[str]] = Field(None)


class SarExtension(BaseStacExtension):
    """STAC SAR extension."""

    FIELDS: type[BaseModel] = SarFields

    schema_href: str = "https://stac-extensions.github.io/sar/v1.0.0/schema.json"
    field_name_prefix: Optional[str] = "sar"


class SatelliteFields(BaseModel):
    """
    https://github.com/stac-extensions/sat#item-properties
    """

    sat_platform_international_designator: Optional[str] = Field(None)
    sat_orbit_cycle: Optional[int] = Field(None)
    sat_orbit_state: Optional[str] = Field(None)
    sat_absolute_orbit: Optional[int] = Field(None)
    sat_relative_orbit: Optional[int] = Field(None)
    sat_anx_datetime: Optional[str] = Field(None)


class SatelliteExtension(BaseStacExtension):
    """STAC Satellite extension."""

    FIELDS: type[BaseModel] = SatelliteFields

    schema_href: str = "https://stac-extensions.github.io/sat/v1.1.0/schema.json"
    field_name_prefix: Optional[str] = "sat"


class TimestampFields(BaseModel):
    """
    https://github.com/stac-extensions/timestamps#item-properties
    """

    published: Optional[str] = Field(None)
    unpublished: Optional[str] = Field(None)
    expires: Optional[str] = Field(None)


class TimestampExtension(BaseStacExtension):
    """STAC timestamp extension"""

    FIELDS: type[BaseModel] = TimestampFields

    schema_href: str = "https://stac-extensions.github.io/timestamps/v1.0.0/schema.json"


class ProcessingFields(BaseModel):
    """
    https://github.com/stac-extensions/processing#item-properties
    """

    processing_expression: Optional[dict[str, Any]] = Field(None)
    processing_lineage: Optional[str] = Field(None)
    processing_level: Optional[str] = Field(None)
    processing_facility: Optional[str] = Field(None)
    processing_software: Optional[dict[str, str]] = Field(None)


class ProcessingExtension(BaseStacExtension):
    """STAC processing extension."""

    FIELDS: type[BaseModel] = ProcessingFields

    schema_href: str = "https://stac-extensions.github.io/processing/v1.0.0/schema.json"
    field_name_prefix: Optional[str] = "processing"


class ViewGeometryFields(BaseModel):
    """
    https://github.com/stac-extensions/view#item-properties
    """

    view_off_nadir: Optional[float] = Field(None)
    view_incidence_angle: Optional[float] = Field(None)
    view_azimuth: Optional[float] = Field(None)
    view_sun_azimuth: Optional[float] = Field(None)
    view_sun_elevation: Optional[float] = Field(None)


class ViewGeometryExtension(BaseStacExtension):
    """STAC ViewGeometry extension."""

    FIELDS: type[BaseModel] = ViewGeometryFields

    schema_href: str = "https://stac-extensions.github.io/view/v1.0.0/schema.json"
    field_name_prefix: Optional[str] = "view"


class ElectroOpticalFields(BaseModel):
    """
    https://github.com/stac-extensions/eo#item-properties
    """

    eo_cloud_cover: Optional[Percentage] = Field(None)
    eo_snow_cover: Optional[Percentage] = Field(None)
    eo_bands: Optional[list[dict[str, Union[str, int]]]] = Field(None)


class ElectroOpticalExtension(BaseStacExtension):
    """STAC ElectroOptical extension."""

    FIELDS: type[BaseModel] = ElectroOpticalFields

    schema_href: str = "https://stac-extensions.github.io/eo/v1.0.0/schema.json"
    field_name_prefix: Optional[str] = "eo"


class ScientificCitationFields(BaseModel):
    """
    https://github.com/stac-extensions/scientific#item-properties
    """

    sci_doi: Optional[str] = Field(None)
    sci_citation: Optional[str] = Field(None)
    sci_publications: Optional[list[dict[str, str]]] = Field(None)


class ScientificCitationExtension(BaseStacExtension):
    """STAC scientific extension."""

    FIELDS: type[BaseModel] = ScientificCitationFields

    schema_href: str = "https://stac-extensions.github.io/scientific/v1.0.0/schema.json"
    field_name_prefix: Optional[str] = "sci"


class ProductFields(BaseModel):
    """
    https://github.com/stac-extensions/product#fields
    """

    product_type: Optional[str] = Field(None)
    product_timeliness: Optional[str] = Field(None)
    product_timeliness_category: Optional[str] = Field(None)
    product_acquisition_type: Optional[str] = Field(None)


class ProductExtension(BaseStacExtension):
    """STAC product extension."""

    FIELDS: type[BaseModel] = ProductFields

    schema_href: str = "https://stac-extensions.github.io/product/v0.1.0/schema.json"
    field_name_prefix: Optional[str] = "product"


class StorageFields(BaseModel):
    """
    https://github.com/stac-extensions/storage#fields
    """

    storage_platform: Optional[str] = Field(default=None)
    storage_region: Optional[str] = Field(default=None)
    storage_requester_pays: Optional[bool] = Field(default=None)
    storage_tier: Optional[str] = Field(default=None, validation_alias="storage:tier")

    @field_validator("storage_tier")
    @classmethod
    def tier_to_stac(cls, v: Optional[str]) -> str:
        """Convert tier from EODAG naming to STAC"""
        return "online" if v == ONLINE_STATUS else "offline"


class StorageExtension(BaseStacExtension):
    """STAC product extension."""

    FIELDS: type[BaseModel] = StorageFields

    schema_href: str = "https://stac-extensions.github.io/storage/v1.0.0/schema.json"
    field_name_prefix: Optional[str] = "storage"


class OrderFields(BaseModel):
    """
    https://github.com/stac-extensions/order#fields
    """

    order_status: Optional[str] = Field(default=None)
    order_id: Optional[str] = Field(default=None, validation_alias="eodag:order_id")
    order_date: Optional[bool] = Field(default=None)


class OrderExtension(BaseStacExtension):
    """STAC product extension."""

    FIELDS: type[BaseModel] = OrderFields

    schema_href: str = "https://stac-extensions.github.io/order/v1.1.0/schema.json"
    field_name_prefix: Optional[str] = "order"


class GridFields(BaseModel):
    """
    https://github.com/stac-extensions/grid
    """

    grid_code: Optional[str] = Field(
        default=None, pattern=r"^[A-Z0-9]+-[-_.A-Za-z0-9]+$"
    )


class GridExtension(BaseStacExtension):
    """STAC grid extension."""

    FIELDS: type[BaseModel] = GridFields

    schema_href: str = "https://stac-extensions.github.io/grid/v1.1.0/schema.json"
    field_name_prefix: Optional[str] = "grid"


class MgrsFields(BaseModel):
    """
    https://github.com/stac-extensions/mgrs
    """

    mgrs_grid_square: Optional[str] = Field(default=None)
    mgrs_latitude_band: Optional[str] = Field(default=None)
    mgrs_utm_zone: Optional[int] = Field(default=None)


class MgrsExtension(BaseStacExtension):
    """STAC mgrs extension."""

    FIELDS: type[BaseModel] = MgrsFields

    schema_href: str = "https://stac-extensions.github.io/mgrs/v1.0.0/schema.json"
    field_name_prefix: Optional[str] = "mgrs"


STAC_EXTENSIONS = [
    SarExtension(),
    SatelliteExtension(),
    TimestampExtension(),
    ProcessingExtension(),
    ViewGeometryExtension(),
    ElectroOpticalExtension(),
    ScientificCitationExtension(),
    ProductExtension(),
    StorageExtension(),
    OrderExtension(),
    GridExtension(),
    MgrsExtension(),
]
