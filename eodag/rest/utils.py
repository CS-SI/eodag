# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, https://www.csgroup.eu/
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

import ast
import datetime
import logging
import os
import re
from shutil import make_archive, rmtree
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Set,
)
from urllib.parse import urlencode

import dateutil.parser
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from pydantic import ValidationError as pydanticValidationError

import eodag
from eodag import EOProduct
from eodag.api.product.metadata_mapping import OSEO_METADATA_MAPPING
from eodag.api.search_result import SearchResult
from eodag.config import load_stac_config, load_stac_provider_config
from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.rest.model.search_post_request import SearchPostRequest
from eodag.rest.model.stac_to_eodag import STACtoEODAGModel
from eodag.rest.rfc3339 import rfc3339_str_to_datetime
from eodag.rest.stac import StacCatalog, StacCollection, StacCommon, StacItem
from eodag.utils import (
    GENERIC_PRODUCT_TYPE,
    _deprecated,
    dict_items_recursive_apply,
    string_to_jsonpath,
)
from eodag.utils.exceptions import (
    MisconfiguredError,
    NoMatchingProductType,
    NotAvailableError,
    ValidationError,
)

if TYPE_CHECKING:
    from io import BufferedReader

logger = logging.getLogger("eodag.rest.utils")

eodag_api = eodag.EODataAccessGateway()


class Cruncher(NamedTuple):
    """Type hinted Cruncher namedTuple"""

    clazz: Callable[..., Any]
    config_params: List[str]


crunchers = {
    "latestIntersect": Cruncher(FilterLatestIntersect, []),
    "latestByName": Cruncher(FilterLatestByName, ["name_pattern"]),
    "overlap": Cruncher(FilterOverlap, ["minimum_overlap"]),
}
stac_config = load_stac_config()
stac_provider_config = load_stac_provider_config()

STAC_QUERY_PATTERN = "query.*.*"


@_deprecated(
    reason="Function internally used by get_home_page_content, also deprecated",
    version="2.6.1",
)
def format_product_types(product_types: List[Dict[str, Any]]) -> str:
    """Format product_types

    :param product_types: A list of EODAG product types as returned by the core api
    :type product_types: list
    """
    result: List[str] = []
    for pt in product_types:
        result.append(f'* *__{pt["ID"]}__*: {pt["abstract"]}')
    return "\n".join(sorted(result))


def format_pydantic_error(e: pydanticValidationError) -> str:
    """Format Pydantic ValidationError

    :param e: A Pydantic ValidationError object
    :tyype e: pydanticValidationError
    """
    error_header = f"Invalid request, {e.error_count()} error(s): "
    error_messages = [err["msg"] for err in e.errors()]
    return error_header + "; ".join(set(error_messages))


def get_detailled_collections_list(
    provider: Optional[str] = None, fetch_providers: bool = True
) -> List[Dict[str, Any]]:
    """Returns detailled collections / product_types list for a given provider as a list of
    config dicts

    :param provider: (optional) Chosen provider
    :type provider: str
    :param fetch_providers: (optional) Whether to fetch providers for new product
                            types or not
    :type fetch_providers: bool
    :returns: List of config dicts
    :rtype: list
    """
    return eodag_api.list_product_types(
        provider=provider, fetch_providers=fetch_providers
    )


@_deprecated(reason="No more needed with STAC API + Swagger", version="2.6.1")
def get_home_page_content(base_url: str, ipp: Optional[int] = None) -> str:
    """Compute eodag service home page content

    :param base_url: The service root URL
    :type base_url: str
    :param ipp: (optional) Items per page number
    :type ipp: int
    """
    base_url = base_url.rstrip("/") + "/"
    content = f"""<h1>EODAG Server</h1><br />
    <a href='{base_url}'>root</a><br />
    <a href='{base_url}service-doc'>service-doc</a><br />
    """
    return content


@_deprecated(
    reason="Used to format output from deprecated function get_home_page_content",
    version="2.6.1",
)
def get_templates_path() -> str:
    """Returns Jinja templates path"""
    return os.path.join(os.path.dirname(__file__), "templates")


def get_product_types(
    provider: Optional[str] = None, filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Returns a list of supported product types

    :param provider: (optional) Provider name
    :type provider: str
    :param filters: (optional) Additional filters for product types search
    :type filters: dict
    :returns: A list of corresponding product types
    :rtype: list
    """
    if filters is None:
        filters = {}
    try:
        guessed_product_types = eodag_api.guess_product_type(
            instrument=filters.get("instrument"),
            platform=filters.get("platform"),
            platformSerialIdentifier=filters.get("platformSerialIdentifier"),
            sensorType=filters.get("sensorType"),
            processingLevel=filters.get("processingLevel"),
        )
    except NoMatchingProductType:
        guessed_product_types = []
    if guessed_product_types:
        product_types = [
            pt
            for pt in eodag_api.list_product_types(provider=provider)
            if pt["ID"] in guessed_product_types
        ]
    else:
        product_types = eodag_api.list_product_types(provider=provider)
    return product_types


def filter_products(
    products: SearchResult, arguments: Dict[str, Any], **kwargs: Any
) -> SearchResult:
    """Apply an eodag cruncher to filter products"""
    filter_name = arguments.get("filter")
    if filter_name:
        cruncher = crunchers.get(filter_name)
        if not cruncher:
            raise ValidationError("unknown filter name")

        cruncher_config: Dict[str, Any] = dict()
        for config_param in cruncher.config_params:
            config_param_value = arguments.get(config_param)
            if not config_param_value:
                raise ValidationError(
                    f'filter additional parameters required: {", ".join(cruncher.config_params)}'
                )
            cruncher_config[config_param] = config_param_value

        try:
            products = products.crunch(cruncher.clazz(cruncher_config), **kwargs)
        except MisconfiguredError as e:
            raise ValidationError(str(e))

    return products


def get_metadata_query_paths(metadata_mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Get dict of query paths and their names from metadata_mapping

    :param metadata_mapping: STAC metadata mapping (see 'resources/stac_provider.yml')
    :type metadata_mapping: dict
    :returns: Mapping of query paths with their corresponding names
    :rtype: dict
    """
    metadata_query_paths: Dict[str, Any] = {}
    for metadata_name, metadata_spec in metadata_mapping.items():
        # When metadata_spec have a length of 1 the query path is not specified
        if len(metadata_spec) == 2:
            metadata_query_template = metadata_spec[0]
            try:
                # We create the dict corresponding to the metadata query of the metadata
                metadata_query_dict = ast.literal_eval(
                    metadata_query_template.format(**{metadata_name: None})
                )
                # We check if our query path pattern matches one or more of the dict path
                matches = [
                    (str(match.full_path))
                    for match in string_to_jsonpath(
                        STAC_QUERY_PATTERN, force=True
                    ).find(metadata_query_dict)
                ]
                if matches:
                    metadata_query_path = matches[0]
                    metadata_query_paths[metadata_query_path] = metadata_name
            except KeyError:
                pass
    return metadata_query_paths


def get_arguments_query_paths(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get dict of query paths and their values from arguments

    Build a mapping of the query paths present in the arguments
    with their values. All matching paths of our STAC_QUERY_PATTERN
    ('query.*.*') are used.

    :param arguments: Request args
    :type arguments: dict
    :returns: Mapping of query paths with their corresponding values
    :rtype: dict
    """
    return dict(
        (str(match.full_path), match.value)
        for match in string_to_jsonpath(STAC_QUERY_PATTERN, force=True).find(arguments)
    )


# STAC ------------------------------------------------------------------------


def get_stac_conformance() -> Dict[str, str]:
    """Build STAC conformance

    :returns: conformance dictionnary
    :rtype: dict
    """
    return stac_config["conformance"]


def get_stac_api_version() -> str:
    """Get STAC API version

    :returns: STAC API version
    :rtype: str
    """
    return stac_config["stac_api_version"]


def get_stac_collections(
    url: str, root: str, arguments: Dict[str, Any], provider: Optional[str] = None
) -> Dict[str, Any]:
    """Build STAC collections

    :param url: Requested URL
    :type url: str
    :param root: The API root
    :type root: str
    :param arguments: Request args
    :type arguments: dict
    :param provider: (optional) Chosen provider
    :type provider: str
    :returns: Collections dictionnary
    :rtype: dict
    """
    return StacCollection(
        url=url,
        stac_config=stac_config,
        provider=provider,
        eodag_api=eodag_api,
        root=root,
    ).get_collections(arguments)


def get_stac_collection_by_id(
    url: str, root: str, collection_id: str, provider: Optional[str] = None
) -> Dict[str, Any]:
    """Build STAC collection by id

    :param url: Requested URL
    :type url: str
    :param root: API root
    :type root: str
    :param collection_id: Product_type as ID of the collection
    :type collection_id: str
    :param provider: (optional) Chosen provider
    :type provider: str
    :returns: Collection dictionary
    :rtype: dict
    """
    return StacCollection(
        url=url,
        stac_config=stac_config,
        provider=provider,
        eodag_api=eodag_api,
        root=root,
    ).get_collection_by_id(collection_id)


def download_stac_item_by_id_stream(
    catalogs: List[str],
    item_id: str,
    provider: Optional[str] = None,
    asset: Optional[str] = None,
    **kwargs: Any,
) -> StreamingResponse:
    """Download item

    :param catalogs: Catalogs list (only first is used as product_type)
    :type catalogs: list
    :param item_id: Product ID
    :type item_id: str
    :param provider: (optional) Chosen provider
    :type provider: str
    :param kwargs: additional download parameters
    :type kwargs: Any
    :returns: a stream of the downloaded data (zip file)
    :rtype: StreamingResponse
    """
    product_type = catalogs[0]

    search_plugin = next(
        eodag_api._plugins_manager.get_search_plugins(product_type, provider)
    )
    provider_product_type_config = search_plugin.config.products.get(
        product_type, {}
    ) or search_plugin.config.products.get(GENERIC_PRODUCT_TYPE, {})
    if provider_product_type_config.get("storeDownloadUrl", False):
        if item_id not in search_plugin.download_info:
            logger.error("data for item %s not found", item_id)
            raise NotAvailableError(
                f"download url for product {item_id} could not be found, please redo "
                f"the search request to fetch the required data"
            )
        product_data = search_plugin.download_info[item_id]
        properties = {
            "id": item_id,
            "orderLink": product_data["orderLink"],
            "downloadLink": product_data["downloadLink"],
            "geometry": "-180 -90 180 90",
        }
        product = EOProduct(provider or product_data["provider"], properties)
    else:
        search_results, _ = eodag_api.search(
            id=item_id, product_type=product_type, provider=provider, **kwargs
        )
        if len(search_results) > 0:
            product = search_results[0]
        else:
            raise NotAvailableError(
                f"Could not find {item_id} item in {product_type} collection for provider {provider}"
            )

    if product.downloader is None:
        download_plugin = eodag_api._plugins_manager.get_download_plugin(product)
        auth_plugin = eodag_api._plugins_manager.get_auth_plugin(
            download_plugin.provider
        )
        product.register_downloader(download_plugin, auth_plugin)

    auth = (
        product.downloader_auth.authenticate()
        if product.downloader_auth is not None
        else product.downloader_auth
    )
    try:
        download_stream_dict = product.downloader._stream_download_dict(
            product, auth=auth, asset=asset
        )
    except NotImplementedError:
        logger.warning(
            "Download streaming not supported for %s: downloading locally then delete",
            product.downloader,
        )
        product_path = eodag_api.download(product, extract=False, asset=asset)
        if os.path.isdir(product_path):
            # do not zip if dir contains only one file
            all_filenames = next(os.walk(product_path), (None, None, []))[2]
            if len(all_filenames) == 1:
                filepath_to_stream = all_filenames[0]
            else:
                filepath_to_stream = f"{product_path}.zip"
                logger.debug(
                    "Building archive for downloaded product path %s",
                    filepath_to_stream,
                )
                make_archive(product_path, "zip", product_path)
                rmtree(product_path)
        else:
            filepath_to_stream = product_path

        filename = os.path.basename(filepath_to_stream)
        download_stream_dict = dict(
            content=read_file_chunks_and_delete(open(filepath_to_stream, "rb")),
            headers={
                "content-disposition": f"attachment; filename={filename}",
            },
        )

    return StreamingResponse(**download_stream_dict)


def read_file_chunks_and_delete(
    opened_file: BufferedReader, chunk_size: int = 64 * 1024
) -> Iterator[bytes]:
    """Yield file chunks and delete file when finished."""
    while True:
        data = opened_file.read(chunk_size)
        if not data:
            opened_file.close()
            os.remove(opened_file.name)
            logger.debug("%s deleted after streaming complete", opened_file.name)
            break
        yield data
    yield data


def get_stac_catalogs(
    url: str,
    root: str = "/",
    catalogs: Optional[List[str]] = None,
    provider: Optional[str] = None,
    fetch_providers: bool = True,
) -> Dict[str, Any]:
    """Build STAC catalog

    :param url: Requested URL
    :type url: str
    :param root: (optional) API root
    :type root: str
    :param catalogs: (optional) Catalogs list
    :type catalogs: list
    :param provider: (optional) Chosen provider
    :type provider: str
    :param fetch_providers: (optional) Whether to fetch providers for new product
                            types or not
    :type fetch_providers: bool
    :returns: Catalog dictionary
    :rtype: dict
    """
    return StacCatalog(
        url=url,
        stac_config=stac_config,
        root=root,
        provider=provider,
        eodag_api=eodag_api,
        catalogs=catalogs or [],
        fetch_providers=fetch_providers,
    ).get_stac_catalog()


def search_stac_items(
    url: str,
    search_request: SearchPostRequest,
    root: str = "/",
    catalogs: Optional[List[str]] = None,
    method: Optional[str] = "GET",
) -> Dict[str, Any]:
    """Get items collection dict for given catalogs list

    :param url: Requested URL
    :type url: str
    :param arguments: Request args
    :type arguments: dict
    :param root: (optional) API root
    :type root: str
    :param catalogs: (optional) Catalogs list
    :type catalogs: list
    :param provider: (optional) Chosen provider
    :type provider: str
    :param method: (optional) search request HTTP method ('GET' or 'POST')
    :type method: str
    :returns: Catalog dictionnary
    :rtype: dict
    """
    # geometry preferred
    next_page_kwargs = {
        key: value
        for key, value in search_request.model_dump(exclude_none=True).items()
        if key != "collections" and catalogs
    }
    next_page_id = (
        int(next_page_kwargs["page"]) + 1 if "page" in next_page_kwargs else 2
    )
    next_page_kwargs["page"] = next_page_id

    stac_args = search_request.model_dump(exclude_none=True)
    if search_request.start_date:
        stac_args["start_datetime"] = search_request.start_date
    if search_request.end_date:
        stac_args["end_datetime"] = search_request.end_date
    if search_request.spatial_filter:
        stac_args["geometry"] = search_request.spatial_filter

    try:
        eodag_args = STACtoEODAGModel.model_validate(
            stac_args, context={"isCatalog": bool(catalogs)}
        )
    except pydanticValidationError as e:
        raise ValidationError(format_pydantic_error(e)) from e

    catalog_url = url.replace("/items", "")

    # TODO: catalog search_args should be in EODAG format
    catalog = StacCatalog(
        url=catalog_url
        if catalogs
        else catalog_url.replace("/search", f"/collections/{eodag_args.productType}"),
        stac_config=stac_config,
        root=root,
        provider=eodag_args.provider,
        eodag_api=eodag_api,
        catalogs=catalogs or [eodag_args.productType],  # type: ignore
    )

    # get products by ids
    if eodag_args.ids:
        search_results = SearchResult([])
        for item_id in eodag_args.ids:
            products, _ = eodag_api.search(
                id=item_id,
                productType=catalogs[0] if catalogs else eodag_args.productType,
                provider=eodag_args.provider,
            )
            if len(products) == 1:
                search_results.extend(products)
        search_results.properties = {
            "page": 1,
            "itemsPerPage": len(search_results),
            "totalResults": len(search_results),
        }

    elif time_interval_overlap(eodag_args, catalog):
        criteria = {**catalog.search_args, **eodag_args.model_dump(exclude_none=True)}

        products, total = eodag_api.search(**criteria)
        search_results = filter_products(products, eodag_args.model_dump(), **criteria)
        search_results.properties = {
            "page": eodag_args.page,
            "itemsPerPage": eodag_args.items_per_page,
            "totalResults": total,
        }
    else:
        # return empty results
        search_results = SearchResult([])
        search_results.properties = {
            "page": eodag_args.page,
            "itemsPerPage": eodag_args.items_per_page,
            "totalResults": 0,
        }

    for record in search_results:
        record.product_type = eodag_api.get_alias_from_product_type(record.product_type)

    search_results.method = method
    if method == "POST":
        search_results.next = f"{url}"
        search_results.body = next_page_kwargs

    elif method == "GET":
        next_query_string = urlencode(next_page_kwargs)
        search_results.next = f"{url}?{next_query_string}"

    items = StacItem(
        url=url,
        stac_config=stac_config,
        provider=eodag_args.provider,
        eodag_api=eodag_api,
        root=root,
    ).get_stac_items(
        search_results=search_results,
        catalog=dict(
            catalog.get_stac_catalog(),
            **{"url": catalog.url, "root": catalog.root},
        ),
    )

    return items


def time_interval_overlap(eodag_args: STACtoEODAGModel, catalog: StacCatalog) -> bool:
    """fix search date filter based on catalog date range"""
    # check if time filtering appears both in search arguments and catalog
    # (for catalogs built by date: i.e. `year/2020/month/05`)
    if not set(["start", "end"]) <= set(eodag_args.model_dump().keys()) or not set(
        ["start", "end"]
    ) <= set(catalog.search_args.keys()):
        return True

    search_date_min = (
        dateutil.parser.parse(eodag_args.start)
        if eodag_args.start
        else datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    )
    search_date_max = (
        dateutil.parser.parse(eodag_args.end)
        if eodag_args.end
        else datetime.datetime.now(tz=datetime.timezone.utc)
    )

    catalog_date_min = rfc3339_str_to_datetime(catalog.search_args["start"])
    catalog_date_max = rfc3339_str_to_datetime(catalog.search_args["end"])
    # check if date intervals overlap
    if (search_date_min <= catalog_date_max) and (search_date_max >= catalog_date_min):
        # use intersection
        eodag_args.start = (
            max(search_date_min, catalog_date_min).isoformat().replace("+00:00", "Z")
        )
        eodag_args.end = (
            min(search_date_max, catalog_date_max).isoformat().replace("+00:00", "Z")
        )
        return True

    logger.warning("Time intervals do not overlap")
    return False


def get_stac_extension_oseo(url: str) -> Dict[str, str]:
    """Build STAC OGC / OpenSearch Extension for EO

    :param url: Requested URL
    :type url: str
    :returns: Catalog dictionnary
    :rtype: dict
    """

    item_mapping = dict_items_recursive_apply(
        stac_config["item"], lambda _, x: str(x).replace("$.product.", "$.")
    )

    # all properties as string type by default
    oseo_properties = {
        "oseo:{}".format(k): {
            "type": "string",
            "title": k[0].upper() + re.sub(r"([A-Z][a-z]+)", r" \1", k[1:]),
        }
        for k, v in OSEO_METADATA_MAPPING.items()
        if v not in str(item_mapping)
    }

    return StacCommon.get_stac_extension(
        url=url, stac_config=stac_config, extension="oseo", properties=oseo_properties
    )


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


def rename_to_stac_standard(key: str) -> str:
    """Fetch the queryable properties for a collection.

    :param key: The camelCase key name obtained from a collection's metadata mapping.
    :type key: str
    :returns: The STAC-standardized property name if it exists, else the default camelCase queryable name
    :rtype: str
    """
    # Load the stac config properties for renaming the properties
    # to their STAC standard
    stac_config_properties: Dict[str, Any] = stac_config["item"]["properties"]

    for stac_property, value in stac_config_properties.items():
        if isinstance(value, list):
            value = value[0]
        if str(value).endswith(key):
            return stac_property

    if key in OSEO_METADATA_MAPPING:
        return "oseo:" + key

    return key


def fetch_collection_queryable_properties(
    collection_id: str, provider: Optional[str] = None
) -> Set[str]:
    """Fetch the queryable properties for a collection.

    :param collection_id: The ID of the collection.
    :type collection_id: str
    :param provider: (optional) The provider.
    :type provider: str
    :returns queryable_properties: A set containing the STAC standardized queryable properties for a collection.
    :rtype queryable_properties: set
    """
    # Fetch the metadata mapping for collection-specific queryables
    kwargs = {"product_type": collection_id}
    if provider is not None:
        kwargs["provider"] = provider
    eodag_queryable_properties = eodag_api.get_queryables(**kwargs)

    # list of all the STAC standardized collection-specific queryables
    queryable_properties: Set[str] = set()
    for prop in eodag_queryable_properties:
        # remove pure eodag properties
        if prop not in ["start", "end", "geom", "locations", "id"]:
            queryable_properties.add(rename_to_stac_standard(prop))
    return queryable_properties


def eodag_api_init() -> None:
    """Init EODataAccessGateway server instance, pre-running all time consuming tasks"""
    eodag_api.fetch_product_types_list()

    # pre-build search plugins
    for provider in eodag_api.available_providers():
        next(eodag_api._plugins_manager.get_search_plugins(provider=provider))
