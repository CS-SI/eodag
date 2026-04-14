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
from pydantic import BaseModel, ConfigDict, Field, model_validator

Percentage = Annotated[float, Ge(0), Le(100)]


class Centroid(BaseModel):
    """Centroid object for projection extension.

    https://github.com/stac-extensions/projection#centroid-object
    """

    lat: Optional[float] = Field(None)
    lon: Optional[float] = Field(None)


class CubeDimension(BaseModel):
    """Cube dimension object for datacube extension.

    https://github.com/stac-extensions/datacube#dimension-object
    """

    type: Optional[str] = Field(None)
    axis: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    extent: Optional[list[float]] = Field(None)
    values: Optional[list[float]] = Field(None)
    step: Optional[float] = Field(None)
    unit: Optional[str] = Field(None)
    reference_system: Optional[Union[str, int, dict[str, Any]]] = Field(None)


class CubeVariable(BaseModel):
    """Cube variable object for datacube extension.

    https://github.com/stac-extensions/datacube#variable-object
    """

    dimensions: Optional[list[str]] = Field(None)
    type: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    extent: Optional[list[Union[float, str, None]]] = Field(None)
    values: Optional[list[Union[float, str]]] = Field(None)
    unit: Optional[str] = Field(None)
    nodata: Optional[Union[float, str]] = Field(None)
    data_type: Optional[str] = Field(None)


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
    https://github.com/stac-extensions/sar
    """

    sar_instrument_mode: Annotated[str, Field(None)]
    sar_frequency_band: Annotated[str, Field(None)]
    sar_center_frequency: Annotated[float, Field(None)]
    sar_polarizations: Annotated[list[str], Field(None)]
    sar_resolution_range: Annotated[float, Field(None)]
    sar_resolution_azimuth: Annotated[float, Field(None)]
    sar_pixel_spacing_range: Annotated[float, Field(None)]
    sar_pixel_spacing_azimuth: Annotated[float, Field(None)]
    sar_looks_range: Annotated[int, Field(None)]
    sar_looks_azimuth: Annotated[int, Field(None)]
    sar_looks_equivalent_number: Annotated[float, Field(None)]
    sar_observation_direction: Annotated[str, Field(None)]
    sar_relative_burst: Annotated[int, Field(None)]
    sar_beam_ids: Annotated[list[str], Field(None)]


class SarExtension(BaseStacExtension):
    """STAC SAR extension."""

    FIELDS: type[BaseModel] = SarFields

    schema_href: str = "https://stac-extensions.github.io/sar/v1.3.0/schema.json"
    field_name_prefix: Optional[str] = "sar"


class SatelliteFields(BaseModel):
    """
    https://github.com/stac-extensions/sat
    """

    sat_platform_international_designator: Annotated[str, Field(None)]
    sat_orbit_cycle: Annotated[int, Field(None)]
    sat_orbit_state: Annotated[str, Field(None)]
    sat_absolute_orbit: Annotated[int, Field(None)]
    sat_relative_orbit: Annotated[int, Field(None)]
    sat_anx_datetime: Annotated[str, Field(None)]


class SatelliteExtension(BaseStacExtension):
    """STAC Satellite extension."""

    FIELDS: type[BaseModel] = SatelliteFields

    schema_href: str = "https://stac-extensions.github.io/sat/v1.1.0/schema.json"
    field_name_prefix: Optional[str] = "sat"


class TimestampFields(BaseModel):
    """
    https://github.com/stac-extensions/timestamps
    """

    published: Annotated[str, Field(None)]
    unpublished: Annotated[str, Field(None)]
    expires: Annotated[str, Field(None)]


class TimestampExtension(BaseStacExtension):
    """STAC timestamp extension"""

    FIELDS: type[BaseModel] = TimestampFields

    schema_href: str = "https://stac-extensions.github.io/timestamps/v1.1.0/schema.json"


class ProcessingFields(BaseModel):
    """
    https://github.com/stac-extensions/processing
    """

    processing_expression: Annotated[dict[str, Any], Field(None)]
    processing_lineage: Annotated[str, Field(None)]
    processing_level: Annotated[str, Field(None)]
    processing_facility: Annotated[str, Field(None)]
    processing_software: Annotated[dict[str, str], Field(None)]


class ProcessingExtension(BaseStacExtension):
    """STAC processing extension."""

    FIELDS: type[BaseModel] = ProcessingFields

    schema_href: str = "https://stac-extensions.github.io/processing/v1.2.0/schema.json"
    field_name_prefix: Optional[str] = "processing"


class ViewGeometryFields(BaseModel):
    """
    https://github.com/stac-extensions/view
    """

    view_off_nadir: Annotated[float, Field(None)]
    view_incidence_angle: Annotated[float, Field(None)]
    view_azimuth: Annotated[float, Field(None)]
    view_sun_azimuth: Annotated[float, Field(None)]
    view_sun_elevation: Annotated[float, Field(None)]


class ViewGeometryExtension(BaseStacExtension):
    """STAC ViewGeometry extension."""

    FIELDS: type[BaseModel] = ViewGeometryFields

    schema_href: str = "https://stac-extensions.github.io/view/v1.1.0/schema.json"
    field_name_prefix: Optional[str] = "view"


class ElectroOpticalFields(BaseModel):
    """
    https://github.com/stac-extensions/eo
    """

    eo_cloud_cover: Annotated[Percentage, Field(None)]
    eo_snow_cover: Annotated[Percentage, Field(None)]
    eo_bands: Annotated[list[dict[str, Union[str, int]]], Field(None)]


class ElectroOpticalExtension(BaseStacExtension):
    """STAC ElectroOptical extension."""

    FIELDS: type[BaseModel] = ElectroOpticalFields

    schema_href: str = "https://stac-extensions.github.io/eo/v2.0.0/schema.json"
    field_name_prefix: Optional[str] = "eo"


class ScientificCitationFields(BaseModel):
    """
    https://github.com/stac-extensions/scientific
    """

    sci_doi: Annotated[str, Field(None)]
    sci_citation: Annotated[str, Field(None)]
    sci_publications: Annotated[list[dict[str, str]], Field(None)]


class ScientificCitationExtension(BaseStacExtension):
    """STAC scientific extension."""

    FIELDS: type[BaseModel] = ScientificCitationFields

    schema_href: str = "https://stac-extensions.github.io/scientific/v1.0.0/schema.json"
    field_name_prefix: Optional[str] = "sci"


class ProductFields(BaseModel):
    """
    https://github.com/stac-extensions/product
    """

    product_type: Annotated[str, Field(None)]
    product_timeliness: Annotated[str, Field(None)]
    product_timeliness_category: Annotated[str, Field(None)]
    product_acquisition_type: Annotated[str, Field(None)]


class ProductExtension(BaseStacExtension):
    """STAC product extension."""

    FIELDS: type[BaseModel] = ProductFields

    schema_href: str = "https://stac-extensions.github.io/product/v1.0.0/schema.json"
    field_name_prefix: Optional[str] = "product"


class StorageFields(BaseModel):
    """
    https://github.com/stac-extensions/storage
    """

    storage_schemes: Annotated[dict[str, Any], Field(None)]
    storage_refs: Annotated[list[str], Field(None)]


class StorageExtension(BaseStacExtension):
    """STAC product extension."""

    FIELDS: type[BaseModel] = StorageFields

    schema_href: str = "https://stac-extensions.github.io/storage/v2.0.0/schema.json"
    field_name_prefix: Optional[str] = "storage"


class OrderFields(BaseModel):
    """
    https://github.com/stac-extensions/order
    """

    order_status: Annotated[str, Field(None)]
    order_id: Annotated[str, Field(None)]
    order_date: Annotated[str, Field(None)]


class OrderExtension(BaseStacExtension):
    """STAC product extension."""

    FIELDS: type[BaseModel] = OrderFields

    schema_href: str = "https://stac-extensions.github.io/order/v1.1.0/schema.json"
    field_name_prefix: Optional[str] = "order"


class GridFields(BaseModel):
    """
    https://github.com/stac-extensions/grid
    """

    grid_code: Annotated[
        str, Field(default=None, pattern=r"^[A-Z0-9]+-[-_.A-Za-z0-9]+$")
    ]


class GridExtension(BaseStacExtension):
    """STAC grid extension."""

    FIELDS: type[BaseModel] = GridFields

    schema_href: str = "https://stac-extensions.github.io/grid/v1.1.0/schema.json"
    field_name_prefix: Optional[str] = "grid"


class MgrsFields(BaseModel):
    """
    https://github.com/stac-extensions/mgrs
    """

    mgrs_grid_square: Annotated[str, Field(None)]
    mgrs_latitude_band: Annotated[str, Field(None)]
    mgrs_utm_zone: Annotated[int, Field(None)]


class MgrsExtension(BaseStacExtension):
    """STAC mgrs extension."""

    FIELDS: type[BaseModel] = MgrsFields

    schema_href: str = "https://stac-extensions.github.io/mgrs/v1.0.0/schema.json"
    field_name_prefix: Optional[str] = "mgrs"


class ProjectionFields(BaseModel):
    """
    https://github.com/stac-extensions/projection
    """

    proj_code: Annotated[str, Field(None)]
    proj_wkt2: Annotated[str, Field(None)]
    proj_projjson: Annotated[dict[str, Any], Field(None)]
    proj_geometry: Annotated[dict[str, Any], Field(None)]
    proj_bbox: Annotated[list[float], Field(None)]
    proj_centroid: Annotated[Centroid, Field(None)]
    proj_shape: Annotated[list[int], Field(None)]
    proj_transform: Annotated[list[float], Field(None)]


class ProjectionExtension(BaseStacExtension):
    """STAC projection extension."""

    FIELDS: type[BaseModel] = ProjectionFields

    schema_href: str = "https://stac-extensions.github.io/projection/v2.0.0/schema.json"
    field_name_prefix: Optional[str] = "proj"


class DatacubeFields(BaseModel):
    """
    https://github.com/stac-extensions/datacube
    """

    cube_dimensions: Annotated[dict[str, CubeDimension], Field(None)]
    cube_variables: Annotated[dict[str, CubeVariable], Field(None)]


class DatacubeExtension(BaseStacExtension):
    """STAC datacube extension."""

    FIELDS: type[BaseModel] = DatacubeFields

    schema_href: str = "https://stac-extensions.github.io/datacube/v2.3.0/schema.json"
    field_name_prefix: Optional[str] = "cube"


class LabelCountObject(BaseModel):
    """
    https://github.com/stac-extensions/label
    """

    name: Annotated[str, Field(None)]
    count: Annotated[int, Field(None)]


class LabelStatsObject(BaseModel):
    """
    https://github.com/stac-extensions/label
    """

    name: Annotated[str, Field(None)]
    value: Annotated[float, Field(None)]


class LabelClassObject(BaseModel):
    """
    https://github.com/stac-extensions/label
    """

    name: Annotated[str, Field(None)]  # required but may be null
    classes: Annotated[list[Union[str, int]], Field(None)]


class LabelOverview(BaseModel):
    """
    https://github.com/stac-extensions/label
    """

    property_key: Annotated[str, Field(None)]
    counts: Annotated[list[LabelCountObject], Field(None)]
    statistics: Annotated[list[LabelStatsObject], Field(None)]


class LabelFields(BaseModel):
    """
    https://github.com/stac-extensions/label
    """

    @model_validator(mode="before")
    @classmethod
    def parse_methods(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        Convert methods ``str`` to ``list``.
        """
        if methods := values.get("methods"):
            values["methods"] = (
                ",".join(methods.split()).split(",")
                if isinstance(methods, str)
                else methods
            )
            if None in values["methods"]:
                values["methods"].remove(None)
        return values

    label_properties: Annotated[list[str], Field(None)]
    label_classes: Optional[list[LabelClassObject]] = Field(default=None)
    label_description: str = Field(default="")
    label_type: str = Field(default="")
    label_tasks: Annotated[list[str], Field(None)]
    label_methods: Annotated[list[str], Field(None)]
    label_overviews: Annotated[list[LabelOverview], Field(None)]


class LabelExtension(BaseStacExtension):
    """STAC label extension."""

    FIELDS: type[BaseModel] = LabelFields

    schema_href: str = "https://stac-extensions.github.io/label/v1.0.1/schema.json"
    field_name_prefix: Optional[str] = "label"


class FederationFields(BaseModel):
    """
    https://github.com/Open-EO/openeo-api/tree/master/extensions/federation
    """

    federation_backends: Annotated[list[str], Field(None)]


class FederationExtension(BaseStacExtension):
    """STAC federation extension."""

    FIELDS: type[BaseModel] = FederationFields

    schema_href: str = "https://api.openeo.org/extensions/federation/0.1.0"
    field_name_prefix: Optional[str] = "federation"


class EcmwfItemProperties(BaseModel):
    """
    STAC extension from ECMWF MARS keywords.

    https://confluence.ecmwf.int/display/UDOC/Keywords+in+MARS+and+Dissemination+requests
    """

    ecmwf_accuracy: Annotated[str, Field(None)]
    ecmwf_anoffset: Annotated[str, Field(None)]
    ecmwf_area: Annotated[str, Field(None)]
    ecmwf_bitmap: Annotated[str, Field(None)]
    ecmwf_block: Annotated[str, Field(None)]
    ecmwf_channel: Annotated[str, Field(None)]
    ecmwf_class: Optional[str] = Field(default=None, alias="class")
    ecmwf_database: Annotated[str, Field(None)]
    ecmwf_date: Annotated[str, Field(None)]
    ecmwf_diagnostic: Annotated[str, Field(None)]
    ecmwf_direction: Annotated[str, Field(None)]
    ecmwf_domain: Annotated[str, Field(None)]
    ecmwf_duplicates: Annotated[str, Field(None)]
    ecmwf_expect: Annotated[str, Field(None)]
    ecmwf_expver: Annotated[str, Field(None)]
    ecmwf_fcmonth: Annotated[str, Field(None)]
    ecmwf_fcperiod: Annotated[str, Field(None)]
    ecmwf_fieldset: Annotated[str, Field(None)]
    ecmwf_filter: Annotated[str, Field(None)]
    ecmwf_format: Annotated[str, Field(None)]
    ecmwf_frame: Annotated[str, Field(None)]
    ecmwf_frequency: Annotated[str, Field(None)]
    ecmwf_grid: Annotated[str, Field(None)]
    ecmwf_hdate: Annotated[str, Field(None)]
    ecmwf_ident: Annotated[str, Field(None)]
    ecmwf_interpolation: Annotated[str, Field(None)]
    ecmwf_intgrid: Annotated[str, Field(None)]
    ecmwf_iteration: Annotated[str, Field(None)]
    ecmwf_latitude: Annotated[str, Field(None)]
    ecmwf_levelist: Annotated[str, Field(None)]
    ecmwf_levtype: Annotated[str, Field(None)]
    ecmwf_longitude: Annotated[str, Field(None)]
    ecmwf_lsm: Annotated[str, Field(None)]
    ecmwf_method: Annotated[str, Field(None)]
    ecmwf_number: Annotated[str, Field(None)]
    ecmwf_obsgroup: Annotated[str, Field(None)]
    ecmwf_obstype: Annotated[str, Field(None)]
    ecmwf_origin: Annotated[str, Field(None)]
    ecmwf_packing: Annotated[str, Field(None)]
    ecmwf_padding: Annotated[str, Field(None)]
    ecmwf_param: Annotated[str, Field(None)]
    ecmwf_priority: Annotated[str, Field(None)]
    ecmwf_product: Annotated[str, Field(None)]
    ecmwf_range: Annotated[str, Field(None)]
    ecmwf_refdate: Annotated[str, Field(None)]
    ecmwf_reference: Annotated[str, Field(None)]
    ecmwf_reportype: Annotated[str, Field(None)]
    ecmwf_repres: Annotated[str, Field(None)]
    ecmwf_resol: Annotated[str, Field(None)]
    ecmwf_rotation: Annotated[str, Field(None)]
    ecmwf_section: Annotated[str, Field(None)]
    ecmwf_source: Annotated[str, Field(None)]
    ecmwf_step: Annotated[str, Field(None)]
    ecmwf_stream: Annotated[str, Field(None)]
    ecmwf_system: Annotated[str, Field(None)]
    ecmwf_target: Annotated[str, Field(None)]
    ecmwf_time: Annotated[str, Field(None)]
    ecmwf_truncation: Annotated[str, Field(None)]
    ecmwf_type: Annotated[str, Field(None)]
    ecmwf_use: Annotated[str, Field(None)]


class EcmwfExtension(BaseStacExtension):
    """STAC SAR extension."""

    FIELDS: type[BaseModel] = EcmwfItemProperties

    field_name_prefix: Optional[str] = "ecmwf"


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
    ProjectionExtension(),
    DatacubeExtension(),
    LabelExtension(),
    FederationExtension(),
]
