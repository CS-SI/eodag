from __future__ import annotations

from collections import UserDict
from typing import Annotated, Any, Optional, Union

from annotated_types import Lt
from pydantic import BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo
from pydantic.types import PositiveInt
from pydantic_core import PydanticUndefined
from shapely.geometry.base import BaseGeometry

from eodag.types import annotated_dict_to_model, model_fields_to_annotated
from eodag.utils.repr import remove_class_repr, shorter_type_repr

Percentage = Annotated[PositiveInt, Lt(100)]


class CommonQueryables(BaseModel):
    """A class representing search common queryable properties."""

    collection: Annotated[str, Field()]

    @classmethod
    def get_queryable_from_alias(cls, value: str) -> str:
        """Get queryable parameter from alias

        >>> CommonQueryables.get_queryable_from_alias('collection')
        'collection'
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
    """A class representing all search queryable properties.

    Parameters default value is set to ``None`` to have them not required.
    """

    start: Annotated[
        str,
        Field(
            None,
            alias="start_datetime",
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
            alias="geometry",
            description="Read EODAG documentation for all supported geometry format.",
        ),
    ]
    # common metadata
    constellation: Annotated[str, Field(None)]
    created: Annotated[str, Field(None)]
    description: Annotated[str, Field(None)]
    gsd: Annotated[int, Field(None)]
    id: Annotated[str, Field(None)]
    instruments: Annotated[str, Field(None)]
    keywords: Annotated[str, Field(None)]
    license: Annotated[str, Field(None)]
    platform: Annotated[str, Field(None)]
    providers: Annotated[str, Field(None)]
    title: Annotated[str, Field(None)]
    uid: Annotated[str, Field(None)]
    updated: Annotated[str, Field(None)]
    # eo extension
    eo_cloud_cover: Annotated[Percentage, Field(None, alias="eo:cloud_cover")]
    eo_snow_cover: Annotated[Percentage, Field(None, alias="eo:snow_cover")]
    # grid extension
    grid_code: Annotated[
        str, Field(None, alias="grid:code", pattern=r"[0-9]{2}[A-Z]{3}")
    ]
    # mgrs extension
    mgrs_grid_square: Annotated[str, Field(None, alias="mgrs:grid_square")]
    mgrs_latitude_band: Annotated[str, Field(None, alias="mgrs:latitude_band")]
    mgrs_utm_zone: Annotated[str, Field(None, alias="mgrs:utm_zone")]
    # order extension
    order_status: Annotated[str, Field(None, alias="order:status")]
    # processing extension
    processing_level: Annotated[str, Field(None, alias="processing:level")]
    # product extension
    product_acquisition_type: Annotated[
        str, Field(None, alias="product:acquisition_type")
    ]
    product_timeliness: Annotated[str, Field(None, alias="product:timeliness")]
    product_type: Annotated[str, Field(None, alias="product:type")]
    # sar extension
    sar_beam_ids: Annotated[str, Field(None, alias="sar:beam_ids")]
    sar_frequency_band: Annotated[float, Field(None, alias="sar:frequency_band")]
    sar_instrument_mode: Annotated[str, Field(None, alias="sar:instrument_mode")]
    sar_polarizations: Annotated[list[str], Field(None, alias="sar:polarizations")]
    # sat extension
    sat_absolute_orbit: Annotated[int, Field(None, alias="sat:absolute_orbit")]
    sat_orbit_cycle: Annotated[int, Field(None, alias="sat:orbit_cycle")]
    sat_orbit_state: Annotated[str, Field(None, alias="sat:orbit_state")]
    sat_relative_orbit: Annotated[int, Field(None, alias="sat:relative_orbit")]
    # sci extension
    sci_doi: Annotated[str, Field(None, alias="sci:doi")]
    # view extension
    view_incidence_angle: Annotated[str, Field(None, alias="view:incidence_angle")]
    view_sun_azimuth: Annotated[str, Field(None, alias="view:sun_azimuth")]
    view_sun_elevation: Annotated[str, Field(None, alias="view:sun_elevation")]

    model_config = ConfigDict(arbitrary_types_allowed=True)


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
        return (
            f"<table>{thead}<tbody>"
            + "".join(
                [
                    f"""<tr {tr_style}><td style='text-align: left;'>
                        <details><summary style='color: grey;'>
                        <span style='color: black'>'{k}'</span>:&ensp;
                        typing.Annotated[{
                        "<span style='color: black'>" + shorter_type_repr(v.__args__[0]) + "</span>,&ensp;"
                    }
                    FieldInfo({"'default': '<span style='color: black'>"
                               + str(v.__metadata__[0].get_default()) + "</span>',&ensp;"
                               if v.__metadata__[0].get_default()
                               and v.__metadata__[0].get_default() != PydanticUndefined else ""}
                            {"'required': <span style='color: black'>"
                             + str(v.__metadata__[0].is_required()) + "</span>,"}
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
                    for k, v in self.items()
                ]
            )
            + "</tbody></table>"
        )

    def get_model(self, model_name: str = "Queryables") -> BaseModel:
        """
        Converts object from :class:`eodag.api.product.QueryablesDict` to :class:`pydantic.BaseModel`
        so that validation can be performed

        :param model_name: name used for :class:`pydantic.BaseModel` creation
        :return: pydantic BaseModel of the queryables dict
        """
        return annotated_dict_to_model(model_name, self.data)
