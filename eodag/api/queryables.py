import re
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from eodag.api.product.metadata_mapping import OSEO_METADATA_MAPPING
from eodag.config import load_stac_config

CAMEL_TO_SPACE_TITLED = re.compile(r"[:_-]|(?<=[a-z])(?=[A-Z])")


def rename_to_stac_standard(key: str) -> str:
    """Fetch the queryable properties for a collection.

    :param key: The camelCase key name obtained from a collection's metadata mapping.
    :type key: str
    :returns: The STAC-standardized property name if it exists, else the default camelCase queryable name
    :rtype: str
    """
    # Load the stac config properties for renaming the properties
    # to their STAC standard
    stac_config = load_stac_config()
    stac_config_properties: Dict[str, Any] = stac_config["item"]["properties"]

    for stac_property, value in stac_config_properties.items():
        if isinstance(value, list):
            value = value[0]
        if str(value).endswith(key):
            return stac_property

    if key in OSEO_METADATA_MAPPING:
        return "oseo:" + key

    return key


class QueryableProperty(BaseModel):
    """A class representing a queryable property.

    :param description: The description of the queryables property
    :type description: str
    :param ref: (optional) A reference link to the schema of the property.
    :type ref: str
    """

    description: str
    ref: Optional[str] = Field(default=None, serialization_alias="$ref")
    type: Optional[list] = None


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


def format_queryable(queryable_key: str) -> QueryableProperty:
    """
    creates a queryable property from a property key
    :param queryable_key: key of the property for which the queryable property shall be created
    :type queryable_key: str
    :returns: queryable property for the given key
    :rtype: QueryableProperty
    """
    if queryable_key not in ["start", "end", "geom", "locations", "id"]:
        stac_key = rename_to_stac_standard(queryable_key)
    else:
        stac_key = queryable_key
    titled_name = re.sub(CAMEL_TO_SPACE_TITLED, " ", stac_key.split(":")[-1]).title()
    return QueryableProperty(description=titled_name)


def format_provider_queryables(
    provider_queryables: dict, queryables: dict
) -> Dict[str, Any]:
    """
    formats the provider queryables and adds them to the existing queryables
    :param provider_queryables: queryables fetched from the provider
    :type provider_queryables: dict
    :param queryables: default queryables to which provider queryables will be added
    :type queryables: dict
    :returns queryable_properties: A dict containing the formatted queryable properties
                                       including queryables fetched from the provider.
    :rtype dict

    """
    for queryable, data in provider_queryables.items():
        attributes = {"description": queryable}
        if "type" in data:
            if isinstance(data["type"], list):
                attributes["type"] = data["type"]
            else:
                attributes["type"] = [data["type"]]
        if "ref" in data:
            attributes["ref"] = data["ref"]
        queryables[queryable] = QueryableProperty(**attributes)
    return queryables
