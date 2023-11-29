from datetime import datetime
from typing import Optional, Literal

from typing_extensions import Annotated
from annotated_types import Lt

from pydantic import BaseModel
from pydantic.types import PositiveInt, PositiveFloat


Percentage = Annotated[PositiveInt, Lt(100)]
AngleDegrees = Annotated[PositiveFloat, Lt(360)]


def snake_to_camel(snake_case_str: str) -> str:
    """
    Convert a snake_case string to camelCase.

    :param snake_case_str: Input string in snake_case.
    :type snake_case_str: str

    :return: camelCase version of the input string.
    :rtype: str

    :Example:
    >>> snake_to_camel("example_string")
    'exampleString'
    """
    words = snake_case_str.split("_")
    return words[0] + "".join(word.capitalize() for word in words[1:])


class InvalidAngleError(ValueError):
    """Custom exception to represent an error when an invalid angle is encountered."""

    pass


# :param Optional[str] resolution: Optional parameter for resolution.
# :param Optional[str] specification: Optional parameter for specification.
class OSEOQueryParams(BaseModel):
    """
    Model for representing OSEO query parameters.

    This model defines the structure for OSEO (OpenSearch for Earth Observation) query parameters.
    It is designed to be used for validating and parsing incoming query parameters
    for searches related to Earth Observation data.

    :param Optional[str] uid: resource identifier within the search engine context.
    :param Optional[str] product_type: entry type.
    :param Optional[str] doi: Digital Object Identifier identifying the product (see http://www.doi.org).
    :param Optional[str] platform: platform short name (e.g. Sentinel-1)
    :param Optional[str] platform_serial_identifier: platform serial identifier.
    :param Optional[str] instrument: instrument (e.g. MERIS, AATSR, ASAR, HRVIR. SAR).
    :param Optional[str] sensor_type: sensor type.
    :param Optional[str] composite_type: Type of composite product expressed as time period that the composite product covers  (e.g. P10D for a 10 day composite).
    :param Optional[str] processing_level: processing level applied to the entry.
    :param Optional[str] orbit_type: platform orbit type (e.g. LEO, GEO).
    :param Optional[str] spectral_range: sensor spectral range (e.g. INFRARED, NEAR-INFRARED, UV, VISIBLE).
    :param Optional[str] has_security_constraints: informing if the resource has any security constraints.
    :param Optional[str] dissemination: dissemination method (e.g. EUMETCast, EUMETCast-Europe, DataCentre).
    :param Optional[str] parent_identifier: parent of the entry in a hierarchy of resources.
    :param Optional[str] production_status: status of the entry (e.g. ARCHIVED, ACQUIRED, CANCELLED).
    :param Optional[str] acquisition_type: distinguish at a high level the appropriateness of the acquisition for "general" use.
    :param Optional[str] orbit_direction: acquisition orbit direction.
    :param Optional[str] track: orbit track.
    :param Optional[str] frame: orbit frame.
    :param Optional[str] swath_identifier: identifier that correspond to precise incidence angles for the sensor.
    :param Optional[str] product_version: version of the Product.
    :param Optional[str] product_quality_status: must be provided if the product passed a quality check.
    :param Optional[str] product_quality_degradation_tag: keywords giving information on the degradations affecting the product.
    :param Optional[str] processor_name: processor software name.
    :param Optional[str] processing_center: processing center (e.g. PDHS-E, PDHS-K, DPA, F-ACRI).
    :param Optional[str] sensor_mode: sensor mode.
    :param Optional[str] archiving_center: archiving center.
    :param Optional[str] processing_mode: processing mode, often referred to as Real Time, Near Real Time etc.
    :param Optional[str] acquisition_station: station used for the acquisition.
    :param Optional[str] acquisition_sub_type: acquisition sub-type.
    :param Optional[str] polarization_mode: polarisation mode.
    :param Optional[str] polarization_channels: polarisation channel transmit/receive configuration.
    :param Optional[str] antenna_look_direction: LEFT or RIGHT.
    :param Optional[str] title: name given to the resource.
    :param Optional[str] topic_category: Main theme(s) of the dataset.
    :param Optional[str] keyword: commonly used word(s) or formalised word(s) or phrase(s) used to describe the subject.
    :param Optional[str] abstract: Parameter for abstract.
    :param Optional[str] organisation_name: name of the organization responsible for the resource.
    :param Optional[str] organisation_role: function performed by the responsible party.
    :param Optional[str] lineage: general explanation of the data producer's knowledge about the lineage of a dataset.
    :param Optional[str] use_limitation: informs if the resource has usage limitations.
    :param Optional[str] access_constraint: applied to assure the protection of privacy or intellectual property, and any special restrictions or limitations on obtaining the resource.
    :param Optional[str] other_constraint: other restrictions and legal prerequisites for accessing and using the resource or metadata.
    :param Optional[str] classification: name of the handling restrictions on the resource or metadata.
    :param Optional[str] language: language of the intellectual content of the metadata record.

    :param Optional[PositiveInt] wavelengths: sensor wavelengths in nanometers.
    :param Optional[PositiveInt] orbit_number: a number requesting the acquisition orbit.
    :param Optional[PositiveInt] start_time_from_ascending_node: start time of acquisition in milliseconds from Ascending node date.
    :param Optional[PositiveInt] completion_time_from_ascending_node: completion time of acquisition in milliseconds from Ascending node date.
    :param Optional[Percentage] cloud_cover: a number of the cloud cover % (0-100).
    :param Optional[Percentage] snow_cover: a number of the snow cover % (0-100).

    :param Optional[PositiveFloat] lowest_location: bottom height of datalayer (in meters).
    :param Optional[PositiveFloat] highest_location: top height of datalayer (in meters).
    :param Optional[PositiveFloat] doppler_frequency: Doppler frequency of acquisition.
    :param Optional[AngleDegrees] illumination_azimuth_angle: mean illumination/solar azimuth angle given in degrees.
    :param Optional[AngleDegrees] illumination_zenith_angle: mean illumination/solar zenith angle given in degrees.
    :param Optional[AngleDegrees] illumination_elevation_angle: mean illumination/solar elevation angle given in degrees.
    :param Optional[AngleDegrees] minimum_incidence_angle: minimum incidence angle given in degrees.
    :param Optional[AngleDegrees] maximum_incidence_angle: maximum incidence angle given in degrees.
    :param Optional[AngleDegrees] incidence_angle_variation: incidence angle variation given in degrees.

    :param Optional[datetime] publication_date: date when the resource was issued.
    :param Optional[datetime] creation_date: date when the metadata item was inserted in the catalogue.
    :param Optional[datetime] modification_date: date when the metadata item was last updated in the catalogue.
    :param Optional[datetime] processing_date: date interval requesting entries processed within a given time interval.
    :param Optional[datetime] availability_time: time when the result became available.



    :raises InvalidAngleError: If an invalid angle value is encountered during validation.

    :meta Config:
    :param alias_generator: function for generating field aliases.
    :type alias_generator: callable

    """

    uid: Optional[str] = None
    product_type: Optional[str] = None
    doi: Optional[str] = None
    platform: Optional[str] = None
    platform_serial_identifier: Optional[str] = None
    instrument: Optional[str] = None
    sensor_type: Optional[str] = None
    composite_type: Optional[str] = None
    processing_level: Optional[str] = None
    orbit_type: Optional[str] = None
    spectral_range: Optional[str] = None
    dissemination: Optional[str] = None
    parent_identifier: Optional[str] = None
    production_status: Optional[str] = None
    track: Optional[str] = None
    frame: Optional[str] = None
    swath_identifier: Optional[str] = None
    product_version: Optional[str] = None
    product_quality_degradation_tag: Optional[str] = None
    processor_name: Optional[str] = None
    processing_center: Optional[str] = None
    polarization_channels: Optional[str] = None
    sensor_mode: Optional[str] = None
    archiving_center: Optional[str] = None
    processing_mode: Optional[str] = None
    acquisition_station: Optional[str] = None
    acquisition_sub_type: Optional[str] = None
    title: Optional[str] = None
    topic_category: Optional[str] = None
    keyword: Optional[str] = None
    abstract: Optional[str] = None
    organisation_name: Optional[str] = None
    organisation_role: Optional[str] = None
    lineage: Optional[str] = None
    use_limitation: Optional[str] = None
    access_constraint: Optional[str] = None
    other_constraint: Optional[str] = None
    classification: Optional[str] = None
    language: Optional[str] = None
    has_security_constraints: Optional[Literal["TRUE", "FALSE"]] = None
    acquisition_type: Optional[Literal["NOMINAL", "CALIBRATION", "OTHER"]] = None
    orbit_direction: Optional[Literal["ASCENDING", "DESCENDING"]] = None
    product_quality_status: Optional[Literal["NONIMAL", "DEGRADED"]] = None
    polarization_mode: Optional[Literal["S", "D", "T", "Q", "UNDEFINED"]] = None
    antenna_look_direction: Optional[Literal["LEFT", "RIGHT"]] = None

    orbit_number: Optional[PositiveInt] = None
    wavelengths: Optional[PositiveInt] = None
    start_time_from_ascending_node: Optional[PositiveInt] = None
    completion_time_from_ascending_node: Optional[PositiveInt] = None
    cloud_cover: Optional[Percentage] = None
    snow_cover: Optional[Percentage] = None

    lowest_location: Optional[PositiveFloat] = None
    highest_location: Optional[PositiveFloat] = None
    doppler_frequency: Optional[PositiveFloat] = None
    illumination_azimuth_angle: Optional[AngleDegrees] = None
    illumination_zenith_angle: Optional[AngleDegrees] = None
    illumination_elevation_angle: Optional[AngleDegrees] = None
    minimum_incidence_angle: Optional[AngleDegrees] = None
    maximum_incidence_angle: Optional[AngleDegrees] = None
    incidence_angle_variation: Optional[AngleDegrees] = None

    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    processing_date: Optional[datetime] = None
    availability_time: Optional[datetime] = None
    publication_date: Optional[datetime] = None

    class Config:
        alias_generator = snake_to_camel
