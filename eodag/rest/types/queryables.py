from typing import Dict, Optional

from pydantic import BaseModel, Field


class QueryableProperty(BaseModel):
    """A class representing a queryable property.

    :param description: The description of the queryables property
    :type description: str
    :param ref: (optional) A reference link to the schema of the property.
    :type ref: str
    """

    description: str
    ref: Optional[str] = Field(default=None, serialization_alias="$ref")


class Queryables(BaseModel):
    """A class representing queryable properties for the STAC API.

    :param json_schema: The URL of the JSON schema.
    :type json_schema: str
    :param q_id: (optional) The identifier of the queryables.
    :type q_id: str
    :param q_type: The type of the object.
    :type q_type: str
    :param title: The title of the queryables.
    :type title: str
    :param description: The description of the queryables
    :type description: str
    :param properties: A dictionary of queryable properties.
    :type properties: dict
    :param additional_properties: Whether additional properties are allowed.
    :type additional_properties: bool
    """

    json_schema: str = Field(
        default="https://json-schema.org/draft/2019-09/schema",
        serialization_alias="$schema",
    )
    q_id: Optional[str] = Field(default=None, serialization_alias="$id")
    q_type: str = Field(default="object", serialization_alias="type")
    title: str = Field(default="Queryables for EODAG STAC API")
    description: str = Field(
        default="Queryable names for the EODAG STAC API Item Search filter."
    )
    properties: Dict[str, QueryableProperty] = Field(
        default={
            "id": QueryableProperty(
                description="ID",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/id",
            ),
            "collection": QueryableProperty(
                description="Collection",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/collection",
            ),
            "geometry": QueryableProperty(
                description="Geometry",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/geometry",
            ),
            "bbox": QueryableProperty(
                description="Bbox",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/item.json#/bbox",
            ),
            "datetime": QueryableProperty(
                description="Datetime",
                ref="https://schemas.stacspec.org/v1.0.0/item-spec/json-schema/datetime.json#/properties/datetime",
            ),
        }
    )
    additional_properties: bool = Field(
        default=True, serialization_alias="additionalProperties"
    )

    def get_properties(self) -> Dict[str, QueryableProperty]:
        """Get the queryable properties.

        :returns: A dictionary containing queryable properties.
        :rtype: typing.Dict[str, QueryableProperty]
        """
        return self.properties

    def __contains__(self, name: str) -> bool:
        return name in self.properties

    def __setitem__(self, name: str, qprop: QueryableProperty) -> None:
        self.properties[name] = qprop
