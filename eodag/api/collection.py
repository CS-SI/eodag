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
from __future__ import annotations

import logging
import re
from collections import UserDict, UserList
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Optional, cast

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, PrivateAttr
from pydantic import ValidationError as PydanticValidationError
from pydantic import model_validator
from pydantic_core import InitErrorDetails, PydanticCustomError
from stac_pydantic.collection import Collection as StacCollection
from stac_pydantic.collection import Extent, SpatialExtent, TimeInterval
from stac_pydantic.links import Links
from stac_pydantic.shared import SEMVER_REGEX

from eodag.types.queryables import CommonStacMetadata
from eodag.types.stac_metadata import create_stac_metadata_model
from eodag.utils import STAC_VERSION
from eodag.utils.env import is_env_var_true
from eodag.utils.exceptions import ValidationError
from eodag.utils.repr import dict_to_html_table

if TYPE_CHECKING:
    from pydantic import ModelWrapValidatorHandler
    from pydantic_core import ErrorDetails
    from typing_extensions import Self

    from eodag.api.core import EODataAccessGateway
    from eodag.api.search_result import SearchResult
    from eodag.types.queryables import QueryablesDict

logger = logging.getLogger("eodag.api.collection")

RFC3339_PATTERN = (
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:T(\d{2}):(\d{2}):(\d{2})(\.\d+)?"
    r"(Z|([+-])(\d{2}):(\d{2}))?)?$"
)


class Collection(StacCollection):
    """A class representing a collection, inherited from :class:`~stac_pydantic.collection.Collection`.

    A ``Collection`` object is used to describe a group of
    related :class:`~eodag.api.product._product.EOProduct` objects.
    """

    type: Literal["Collection"] = Field(default="Collection")
    stac_version: str = Field(default=STAC_VERSION, pattern=SEMVER_REGEX)
    description: Optional[str] = Field(default=None, min_length=1)  # type: ignore
    license: str = Field(default="other", min_length=1)
    extent: Extent = Field(
        default=Extent(
            spatial=SpatialExtent(bbox=[[-180.0, -90.0, 180.0, 90.0]]),  # type: ignore
            temporal=TimeInterval(interval=[[None, None]]),
        ),
        description=(
            "The temporal extent of the collection, following the STAC specification for extent definition (e.g. "
            '{"spatial": {"bbox": [[-180.0, -90.0, 180.0, 90.0]]}, '
            '"temporal": {"interval": [["2024-06-10T12:00:00Z", None]]}}'
            "), with date/time strings in RFC 3339 format"
        ),
    )
    # overwrite field "keywords" with type "list" instead of "typing.List"
    keywords: Optional[list[str]] = None
    links: Links = Field(default=Links(root=[]))

    # summaries
    constellation: Optional[list[str]] = Field(default=None, exclude=True, repr=False)
    instruments: Optional[list[str]] = Field(default=None, exclude=True, repr=False)
    platform: Optional[list[str]] = Field(default=None, exclude=True, repr=False)
    processing_level: Optional[list[str]] = Field(
        default=None, alias="processing:level", exclude=True, repr=False
    )
    sci_doi: Optional[list[str]] = Field(
        default=None, alias="sci:doi", exclude=True, repr=False
    )
    eodag_sensor_type: Optional[list[str]] = Field(
        default=None, alias="eodag:sensor_type", exclude=True, repr=False
    )

    # eodag-specific attribute
    alias: Optional[str] = Field(
        default=None,
        min_length=1,
        description="An alias given by a user to use his customized id intead of the internal id of EODAG",
        repr=False,
    )

    # path to external collection metadata file (required by stac-fastapi-eodag)
    eodag_stac_collection: Optional[str] = Field(
        default=None, alias="stacCollection", exclude=True, repr=False
    )

    # Private property to store the eodag internal id value. Not part of the model schema.
    _id: str = PrivateAttr()
    _dag: Optional[EODataAccessGateway] = PrivateAttr(default=None)

    # only STAC fields
    __stac_fields__: ClassVar[list[str]] = list(StacCollection.model_fields.keys())

    # mandatory STAC fields which are fixed by their default value
    __static_fields__: ClassVar[list[str]] = ["type", "stac_version"]

    # fields of the model that must be added to the field "summaries"
    __summaries_fields__: ClassVar[Optional[list[str]]] = None

    model_config = ConfigDict(
        extra="forbid",
        validate_return=True,
        validate_by_name=True,
        serialize_by_alias=True,
        use_enum_values=True,
    )

    def model_post_init(self, context: Any) -> None:
        """Post-initialization method to set internal attributes."""
        self._id = self.id

    @classmethod
    def summaries_fields(cls) -> list[str]:
        """Set and/or return ``__summaries_fields__`` class variable that requires computations"""
        if cls.__summaries_fields__ is None:
            cls.__summaries_fields__ = [
                field
                for field in cls.model_fields
                if field not in cls.__stac_fields__ + ["alias", "eodag_stac_collection"]
            ]
        return cls.__summaries_fields__

    @classmethod
    def create_with_dag(cls, dag: EODataAccessGateway, **kwargs) -> Collection:
        """Create a Collection with a EODataAccessGateway instance.

        :param dag: The gateway instance to use to search products and to list queryables of the collection instance
        :param kwargs: The collection attributes
        """
        instance = cls(**kwargs)
        instance._dag = dag
        return instance

    @classmethod
    def get_collection_field_from_alias(cls, value: str) -> str:
        """Get name of a collection field from its alias

        >>> Collection.get_collection_field_from_alias('processing:level')
        'processing_level'
        """
        alias_map = {
            field_info.alias: name
            for name, field_info in cls.model_fields.items()
            if field_info.alias
        }
        return alias_map.get(value, value)

    @classmethod
    def get_collection_alias_from_field(cls, value: str) -> str:
        """Get alias of a collection field from its name

        >>> Collection.get_collection_alias_from_field('processing_level')
        'processing:level'
        """
        field_map = {
            name: field_info.alias
            for name, field_info in cls.model_fields.items()
            if field_info.alias
        }
        return field_map.get(value, value)

    @model_validator(mode="before")
    @classmethod
    def format_eodag_summaries_values(cls, data: Any) -> Any:
        """Format fields which will be used as properties of field ``summaries`` to make sure
        their validation and the one of ``summaries`` will pass"""
        if not isinstance(data, dict):
            return data

        if "summaries" not in data or data["summaries"] is None:
            data["summaries"] = {}
        elif not isinstance(data["summaries"], dict):
            return data

        # format fields for "summaries"
        for field, v in data.copy().items():
            field_from_alias = cls.get_collection_field_from_alias(field)

            # do not use null values for field "summaries"
            if v is None:
                continue

            if field_from_alias in cls.summaries_fields():
                default = cls.model_fields[field_from_alias].get_default()
                # set empty values ({}, [] or "") which are not the default values to None
                # do not use it neither for field "summaries"
                if not v and isinstance(v, (dict, list, str)) and default is None:
                    data[field] = None
                    continue

                # keep values as they are when they are dictionaries or lists
                # string values have already been converted to lists in validator "format_strings_in_list_field()""
                # make lists with values of other types
                if isinstance(v, dict) or isinstance(v, list):
                    data["summaries"][field] = data[field]
                else:
                    data[field] = data["summaries"][field] = [v]

        return data

    @model_validator(mode="before")
    @classmethod
    def format_strings_in_list_field(cls, data: Any) -> Any:
        """Convert a string to a list of strings in fields whose type is list in the model"""
        for field, v in data.copy().items():
            if not isinstance(v, str) or not v:
                continue

            field_from_alias = cls.get_collection_field_from_alias(field)
            if field_from_alias not in cls.model_fields:
                continue

            # check the type of the field, if it a list or an optional list, convert the string into a list of strings
            annotation = cls.model_fields[field_from_alias].annotation
            if annotation in [list[str], Optional[list[str]]]:
                data[field] = v.split(",")

        return data

    @model_validator(mode="before")
    @classmethod
    def allow_summaries_validation(cls, data: Any) -> Any:
        """Add properties of field ``summaries`` that can be validated
        in the model to the input and remove the other ones"""
        if (
            isinstance(data, dict)
            and "summaries" in data
            and isinstance(data["summaries"], dict)
        ):
            errors: list[InitErrorDetails] = []

            for prop, v in data["summaries"].copy().items():
                prop_from_alias = cls.get_collection_field_from_alias(prop)
                # raise an error for each unknown "summaries" property
                if prop_from_alias not in cls.summaries_fields():
                    msg = (
                        'Extra inputs are not permitted in collection field "summaries"'
                    )
                    error = InitErrorDetails(
                        type=PydanticCustomError("extra_forbidden", msg),
                        loc=("summaries", prop),
                        input=data["summaries"][prop],
                    )
                    errors.append(error)
                    continue

                # remove null values and empty values ({}, [] or "") when there are not the default values
                default = cls.model_fields[prop_from_alias].get_default()
                if v is None or (
                    not v and isinstance(v, (dict, list, str)) and default is None
                ):
                    del data["summaries"][prop]
                    continue

                add_prop = True

                # values set in kwargs have priority over the ones in "summaries" except if they are null
                for field, value in data.copy().items():
                    # handle aliases
                    field_from_alias = cls.get_collection_field_from_alias(field)
                    if prop_from_alias == field_from_alias:
                        if value is None:
                            # use the name already used in kwargs
                            data[field] = v
                        else:
                            del data["summaries"][prop]
                        add_prop = False
                        break

                if add_prop:
                    data[prop] = v

            if errors:
                raise PydanticValidationError.from_exception_data(
                    title="Summaries field check", line_errors=errors
                )

        return data

    @model_validator(mode="before")
    @classmethod
    def are_values_default(cls, data: Any) -> Any:
        """Check if the value of static fields is their default value"""
        if not isinstance(data, dict):
            return data

        errors: list[InitErrorDetails] = []

        for field, v in data.copy().items():
            field_from_alias = cls.get_collection_field_from_alias(field)

            if field_from_alias not in cls.__static_fields__:
                continue

            default = cls.model_fields[field_from_alias].get_default()

            # set static field to default value without raising an error if its value is null
            if v is None:
                data[field] = default
                continue

            # raise an error if its value is nor null nor the default value
            if v != default:
                msg = f"Input is fixed to its default value: {default}"
                error = InitErrorDetails(
                    type=PydanticCustomError("value_error", msg),
                    loc=(field,),
                    input=data[field],
                )
                errors.append(error)

        if errors:
            raise PydanticValidationError.from_exception_data(
                title="Static fields check", line_errors=errors
            )
        return data

    @model_validator(mode="after")
    def set_id_from_alias(self) -> Self:
        """If an alias exists, use it to update field ``id``"""
        if self.alias is not None:
            self.id = self.alias
        return self

    @model_validator(mode="after")
    def set_description_from_id(self) -> Self:
        """Set field ``description`` to the value of ``id`` if it is not given or did not pass validation"""
        if self.description is None:
            self.description = self.id
        return self

    @model_validator(mode="after")
    def finalize_summaries(self) -> Self:
        """Update field ``summaries`` after all summaries fields have been validated"""
        # reset summaries to later have only validated values and
        # remove not-STAC-formatted values that "summaries" may contain
        self.summaries = {}

        # add "summaries" fields which are not null
        for field in Collection.summaries_fields():
            value = self.__dict__[field]

            if value is not None:
                # use aliases as key of field "summaries" to make sure having STAC field names
                alias_from_field = Collection.get_collection_alias_from_field(field)
                self.summaries[alias_from_field] = value

        # set field "summaries" to its default value if it is empty
        if not self.summaries:
            self.summaries = Collection.model_fields["summaries"].get_default()

        return self

    @model_validator(mode="wrap")
    @classmethod
    def validate_collection(
        cls, values: dict[str, Any] | Self, handler: ModelWrapValidatorHandler[Self]
    ) -> Self:
        """Allow to create a collection instance with bad formatted field (except ``id``).
        Set incorrectly formatted fields to their default value and ignore extra fields.
        Log a warning about validation errors if ``EODAG_VALIDATE_COLLECTIONS`` environment variable is set to ``True``.
        """
        errors: list[ErrorDetails] = []
        continue_validation: bool = True

        # iterate over each step of validation where error(s) raise(s)
        while continue_validation:
            try:
                handler(values)
            except PydanticValidationError as e:
                tmp_errors = e.errors()
                # raise an error if the id is invalid
                if any(error["loc"][0] == "id" for error in tmp_errors):
                    raise ValidationError.from_error(e) from e

                # convert values to dict if it is a model instance
                values_dict = values if isinstance(values, dict) else values.__dict__

                for error in tmp_errors:
                    wrong_field = error["loc"][0]
                    if not isinstance(wrong_field, str):
                        continue

                    wrong_field_from_alias = cls.get_collection_field_from_alias(
                        wrong_field
                    )

                    # if validation failed for a dictionary field for a specific key, remove only that key
                    # same for a specific element of a list
                    if len(error["loc"]) > 1 and (
                        isinstance(values_dict[wrong_field], (dict, list))
                    ):
                        # as the error is at a sub-level, the field exists in the model
                        default = cls.model_fields[wrong_field_from_alias].get_default()

                        # use methods to remove the wrong element which prevent errors if the element
                        # have already been removed during a previous error handling
                        if isinstance(values_dict[wrong_field], dict):
                            if not isinstance(error["loc"][1], str):
                                continue

                            default_json = (
                                default.model_dump(mode="json")
                                if isinstance(default, BaseModel)
                                else default
                            )

                            values_dict[wrong_field].pop(error["loc"][1], None)

                            # if the sub-field is in the default value of the field,
                            # replace the wrong value by its default value
                            if (
                                default_json is not None
                                and error["loc"][1] in default_json
                            ):
                                values_dict[wrong_field][
                                    error["loc"][1]
                                ] = default_json[error["loc"][1]]
                        else:
                            try:
                                values_dict[wrong_field].remove(error["input"])
                            except ValueError:
                                pass

                        # set the field to None if it become empty ({} or []) after the previous removal and
                        # its default value is None
                        if not values_dict[wrong_field] and default is None:
                            values_dict[wrong_field] = None

                    elif wrong_field_from_alias not in cls.model_fields:
                        # ignore extra attribute(s)
                        del values_dict[wrong_field]
                    else:
                        # set other incorrectly formatted attribute(s) to their default value
                        values_dict[wrong_field] = cls.model_fields[
                            wrong_field_from_alias
                        ].get_default()

                errors.extend(tmp_errors)
            else:
                continue_validation = False

        # log a warning if there were validation errors and the env var is set to True
        if errors and is_env_var_true("EODAG_VALIDATE_COLLECTIONS"):
            # log all errors at once
            error_title = f"collection {values_dict['id']}"
            init_errors: list[InitErrorDetails] = [
                InitErrorDetails(
                    type=PydanticCustomError(error["type"], error["msg"]),
                    loc=error["loc"],
                    input=error["input"],
                )
                for error in errors
            ]
            pydantic_error = PydanticValidationError.from_exception_data(
                title=error_title, line_errors=init_errors
            )
            logger.warning(pydantic_error)

        # Create a fresh instance with the cleaned values
        return handler(values)

    def model_dump(  # type: ignore[override]
        self,
        *,
        by_alias: bool = True,
        exclude_unset: bool = False,
        display_extensions: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Overwrite the method from inherited class ``StacBaseModel()`` which excludes unset fields
        and add the possibility to display the field ``stac_extensions`` or not"""
        if self.summaries is None or not display_extensions:
            return super().model_dump(
                by_alias=by_alias, exclude_unset=exclude_unset, **kwargs
            )

        summaries_model = cast(CommonStacMetadata, create_stac_metadata_model())
        summaries_validated = summaries_model.model_construct(
            _fields_set=None, **self.summaries
        )

        # update directly the instance as the called method is applied on it
        self.stac_extensions = cast(
            list[AnyUrl], summaries_validated.get_conformance_classes()
        )

        collection_dict = super().model_dump(
            by_alias=by_alias, exclude_unset=exclude_unset, **kwargs
        )

        # restore to default value
        self.stac_extensions = Collection.model_fields["stac_extensions"].get_default()

        return collection_dict

    def model_dump_json(  # type: ignore[override]
        self,
        *,
        by_alias: bool = True,
        exclude_unset: bool = False,
        display_extensions: bool = False,
        **kwargs: Any,
    ) -> str:
        """Overwrite the method from inherited class ``StacBaseModel()`` which excludes unset fields
        and add the possibility to display the field ``stac_extensions`` or not"""
        if self.summaries is None or not display_extensions:
            return super().model_dump_json(
                by_alias=by_alias, exclude_unset=exclude_unset, **kwargs
            )

        summaries_model = cast(CommonStacMetadata, create_stac_metadata_model())
        summaries_validated = summaries_model.model_construct(
            _fields_set=None, **self.summaries
        )

        # update directly the instance as the called method is applied on it
        self.stac_extensions = cast(
            list[AnyUrl], summaries_validated.get_conformance_classes()
        )

        collection_str = super().model_dump_json(
            by_alias=by_alias, exclude_unset=exclude_unset, **kwargs
        )

        # restore to default value
        self.stac_extensions = Collection.model_fields["stac_extensions"].get_default()

        return collection_str

    def __str__(self) -> str:
        return f'{type(self).__name__}("{self.id}")'

    def __repr_str__(self, join_str: str) -> str:
        return join_str.join(
            repr(v) if a is None else f"{a}={v!r}"
            for a, v in self.__repr_args__()
            if v is not None
        )

    def _repr_html_(self, embedded: bool = False) -> str:
        thead = (
            f"""<thead><tr><td style='text-align: left; color: grey;'>
                {type(self).__name__}("<span style='color: black'>{self.id}</span>")</td></tr></thead>
            """
            if not embedded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embedded else ""
        col_html_table = dict_to_html_table(
            self.model_dump(exclude={"alias"}), depth=1, brackets=False
        )

        return (
            f"<table>{thead}<tbody>"
            f"<tr {tr_style}><td style='text-align: left;'>"
            f"{col_html_table}</td></tr>"
            "</tbody></table>"
        )

    def _ensure_dag(self) -> EODataAccessGateway:
        if self._dag is None:
            raise RuntimeError(
                f"Collection '{self.id}' needs EODataAccessGateway to perform this operation. "
                "Create with: Collection.create_with_dag(dag, id='...')"
            )
        return self._dag

    def search(self, **kwargs: Any) -> SearchResult:
        """Look for products of this collection matching criteria using the ``dag`` attribute of the instance.

        :param kwargs: Some other criteria that will be used to do the search,
                       using parameters compatible with the provider

        :returns: A collection of EO products matching the criteria.
        :raises: :class:`~eodag.utils.exceptions.ValidationError`: If the `collection` argument is set in `kwargs`,
                                                                   since it is already defined by the instance
        """
        dag = self._ensure_dag()
        collection_search_arg = "collection"
        if collection_search_arg in kwargs:
            raise ValidationError(
                f"{collection_search_arg} should not be set in kwargs since a collection instance is used",
                {collection_search_arg},
            )

        return dag.search(collection=self.id, **kwargs)

    def list_queryables(self, **kwargs: Any) -> QueryablesDict:
        """Fetch the queryable properties for this collection using the ``dag`` attribute of the instance.

        :param kwargs: additional filters for queryables

        :returns: A :class:`~eodag.api.product.queryables.QuerybalesDict` containing the EODAG queryable
                  properties, associating parameters to their annotated type, and an ``additional_properties`` attribute
        :raises: :class:`~eodag.utils.exceptions.ValidationError`: If the `collection` argument is set in `kwargs`,
                                                                   since it is already defined by the instance
        """
        dag = self._ensure_dag()
        collection_search_arg = "collection"
        if collection_search_arg in kwargs:
            raise ValidationError(
                f"{collection_search_arg} should not be set in kwargs since a collection instance is used",
                {collection_search_arg},
            )

        return dag.list_queryables(collection=self.id, **kwargs)


class CollectionsDict(UserDict[str, Collection]):
    """A UserDict object which values are :class:`~eodag.api.collection.Collection` objects, keyed by provider ``id``.

    :param collections: A list of collections

    :cvar data: List of collections
    """

    def __init__(
        self,
        collections: list[Collection],
    ) -> None:
        super().__init__()

        self.data = {col._id: col for col in collections}

    def __str__(self) -> str:
        return "{" + ", ".join(f'"{col}": {col_f}' for col, col_f in self.items()) + "}"

    def __repr__(self) -> str:
        return str(self)


class CollectionsList(UserList[Collection]):
    """An object representing a collection of :class:`~eodag.api.collection.Collection`.

    :param collections: A list of collections

    :cvar data: List of collections
    """

    def __init__(
        self,
        collections: list[Collection],
    ) -> None:
        super().__init__(collections)

    def __str__(self) -> str:
        return f"{type(self).__name__}([{', '.join(str(col) for col in self)}])"

    def __repr__(self) -> str:
        return str(self)

    def _repr_html_(self, embedded: bool = False) -> str:
        # mock "thead" tag by reproduicing its style to make "details" and "summary" tags work properly
        mock_thead = (
            f"""<details class='foldable'>
                <summary style='text-align: left; color: grey; font-size: 12px;'>
                {type(self).__name__}&ensp;({len(self)})
                </summary>
            """
            if not embedded
            else ""
        )
        tr_style = "style='background-color: transparent;'" if embedded else ""

        return (
            f"{mock_thead}<table><tbody>"
            + "".join(
                [
                    f"""<tr {tr_style}><td style='text-align: left;'>
                        <details>
                        <summary style='color: grey; font-family: monospace;'>
                        {i}&ensp;
                        {type(col).__name__}("<span style='color: black'>{col.id}</span>")
                    </summary>
                    {re.sub(r"(<thead>.*|.*</thead>)", "", col._repr_html_())}
                    </details>
                    </td></tr>
                    """
                    for i, col in enumerate(self)
                ]
            )
            + "</tbody></table></details>"
        )
