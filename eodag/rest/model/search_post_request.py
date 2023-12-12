from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import (
    BaseModel,
    Field,
    conint,
    conlist,
    field_validator,
    root_validator,
    validator,
)
from shapely.geometry import (
    GeometryCollection,
    LinearRing,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
    shape,
)
from shapely.geometry.base import GEOMETRY_TYPES

from eodag.rest.rfc3339 import rfc3339_str_to_datetime, str_to_interval

PositiveInt = conint(gt=0)

NumType = Union[float, int]
BBox = Union[
    conlist(NumType, min_length=4, max_length=4),  # 2D bbox
    conlist(NumType, min_length=6, max_length=6),  # 3D bbox
    Tuple[NumType, NumType, NumType, NumType],  # 2D bbox
    Tuple[NumType, NumType, NumType, NumType, NumType, NumType],  # 3D bbox
]

Geometry = Union[
    Dict[str, Any],
    Point,
    MultiPoint,
    LineString,
    MultiLineString,
    Polygon,
    MultiPolygon,
    LinearRing,
    GeometryCollection,
]


class SearchPostRequest(BaseModel):
    """
    class which describes the body of a search request

    Overrides the validation for datetime and spatial filter from the base request model.
    """

    provider: Optional[str] = None
    collections: Optional[List[str]] = None
    ids: Optional[List[str]] = None
    bbox: Optional[BBox] = None
    intersects: Optional[Geometry] = None
    datetime: Optional[str] = None
    limit: Optional[PositiveInt] = Field(  # type: ignore
        None, description="Maximum number of items per page."
    )
    page: Optional[PositiveInt] = Field(  # type: ignore
        None, description="Page number, must be a positive integer."
    )
    query: Optional[Dict[str, Any]] = None
    filter: Optional[Dict[str, Any]] = None
    filter_lang: Optional[str] = Field(
        None, alias="filter-lang", description="The language used for filtering."
    )

    class Config:
        """Model config"""

        populate_by_name = True
        arbitrary_types_allowed = True

    @root_validator(pre=True)
    @classmethod
    def check_filter_lang(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Verify filter-lang has correct value"""
        _filter = values.get("filter")
        filter_lang = values.get("filter-lang")
        if _filter and not filter_lang:
            raise ValueError("filter-lang must be set if filter is provided")
        if _filter and filter_lang and filter_lang != "cql2-json":
            raise ValueError('Only filter language "cql2-json" is accepted')
        return values

    @property
    def start_date(self) -> Optional[str]:
        """Extract the start date from the datetime string."""
        return self.get_dates(pos="start")

    @property
    def end_date(self) -> Optional[str]:
        """Extract the end date from the datetime string."""
        return self.get_dates(pos="end")

    @validator("ids", "collections", pre=True)
    @classmethod
    def str_to_str_list(cls, v: Union[str, List[str]]) -> List[str]:
        """Convert ids and collections strings to list of strings"""
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    @validator("intersects")
    @classmethod
    def validate_spatial(cls, v: Geometry, values: Dict[str, Any]) -> Geometry:
        """Check bbox and intersects are not both supplied."""
        if values["bbox"]:
            raise ValueError("intersects and bbox parameters are mutually exclusive")

        if not isinstance(v, dict) or not v.get("type") in GEOMETRY_TYPES:
            raise ValueError("Not a valid geometry")

        return shape(v)

    @field_validator("bbox", mode="before")
    @classmethod
    def str_bbox_to_list(cls, v: Union[str, BBox]) -> BBox:
        """convert bbox str to list of NumType"""
        if isinstance(v, str):
            return [float(b.strip()) for b in v.split(",")]
        return v

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: BBox) -> BBox:
        """Check order of supplied bbox coordinates."""
        # Validate order
        if len(v) == 4:
            xmin, ymin, xmax, ymax = v
        else:
            xmin, ymin, min_elev, xmax, ymax, max_elev = v
            if max_elev < min_elev:
                raise ValueError(
                    "Maximum elevation must greater than minimum elevation"
                )

        if xmax < xmin:
            raise ValueError("Maximum longitude must be greater than minimum longitude")

        if ymax < ymin:
            raise ValueError("Maximum longitude must be greater than minimum longitude")

        # Validate against WGS84
        if xmin < -180 or ymin < -90 or xmax > 180 or ymax > 90:
            raise ValueError("Bounding box must be within (-180, -90, 180, 90)")

        return v

    @validator("datetime")
    @classmethod
    def validate_datetime(cls, v: str) -> str:
        """Validate datetime."""
        if "/" in v:
            values = v.split("/")
        else:
            # Single date is interpreted as end date
            values = ["..", v]

        dates = []
        for value in values:
            if value == ".." or value == "":
                dates.append("..")
                continue

            # throws ValueError if invalid RFC 3339 string
            dates.append(rfc3339_str_to_datetime(value))

        if dates[0] == ".." and dates[1] == "..":
            raise ValueError(
                "Invalid datetime range, both ends of range may not be open"
            )

        if ".." not in dates and dates[0] > dates[1]:
            raise ValueError(
                "Invalid datetime range, must match format (begin_date, end_date)"
            )

        return v

    @property
    def spatial_filter(self) -> Optional[Geometry]:
        """Return a geojson-pydantic object representing the spatial filter for the search
        request.

        Check for both because the ``bbox`` and ``intersects`` parameters are
        mutually exclusive.
        """
        if self.bbox:
            return Polygon(
                (
                    (self.bbox[0], self.bbox[1]),
                    (self.bbox[0], self.bbox[3]),
                    (self.bbox[2], self.bbox[3]),
                    (self.bbox[2], self.bbox[1]),
                )
            )
        if self.intersects:
            return self.intersects
        return None

    def get_dates(self, pos: Literal["start", "end"]) -> Optional[str]:
        """extract start or end dates from datetime"""
        if not self.datetime:
            return None

        if "/" not in self.datetime:
            return rfc3339_str_to_datetime(self.datetime).isoformat()

        interval = str_to_interval(self.datetime)
        if not interval:
            return None

        start, end = interval

        if pos == "end":
            return end.isoformat() if end else None
        else:
            return start.isoformat() if start else None
