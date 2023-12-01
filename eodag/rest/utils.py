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
import json
import logging
import os
import re
from shutil import make_archive, rmtree
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Union,
)
from urllib.parse import urlencode

import dateutil.parser
from dateutil import tz
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from prometheus_client import start_http_server
from pydantic import BaseModel, Field
from shapely.geometry import Polygon, shape

import eodag
from eodag import EOProduct
from eodag.api.product.metadata_mapping import OSEO_METADATA_MAPPING
from eodag.api.search_result import SearchResult
from eodag.config import load_stac_config, load_stac_provider_config
from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.rest.stac import StacCatalog, StacCollection, StacCommon, StacItem
from eodag.utils import (
    DEFAULT_ITEMS_PER_PAGE,
    DEFAULT_PAGE,
    GENERIC_PRODUCT_TYPE,
    _deprecated,
    dict_items_recursive_apply,
    string_to_jsonpath,
)
from eodag.utils.exceptions import (
    MisconfiguredError,
    NoMatchingProductType,
    NotAvailableError,
    UnsupportedProductType,
    ValidationError,
)

if TYPE_CHECKING:
    from io import BufferedReader

    from shapely.geometry.base import BaseGeometry


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

telemetry = {}


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
        result.append("* *__{ID}__*: {abstract}".format(**pt))
    return "\n".join(sorted(result))


def get_detailled_collections_list(
    provider: Optional[str] = None, fetch_providers: bool = True
) -> List[Dict[str, Any]]:
    """Returns detailled collections / product_types list for a given provider as a list of config dicts

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


def search_bbox(request_bbox: str) -> Optional[Dict[str, float]]:
    """Transform request bounding box as a bbox suitable for eodag search"""

    eodag_bbox = None
    search_bbox_keys = ["lonmin", "latmin", "lonmax", "latmax"]

    if not request_bbox:
        return None

    try:
        request_bbox_list = [float(coord) for coord in request_bbox.split(",")]
    except ValueError as e:
        raise ValidationError("invalid box coordinate type: %s" % e)

    eodag_bbox = dict(zip(search_bbox_keys, request_bbox_list))
    if len(eodag_bbox) != 4:
        raise ValidationError("input box is invalid: %s" % request_bbox)

    return eodag_bbox


def get_date(date: Optional[str]) -> Optional[str]:
    """Check if the input date can be parsed as a date"""

    if not date:
        return None
    try:
        return (
            dateutil.parser.parse(date)
            .replace(tzinfo=tz.UTC)
            .isoformat()
            .replace("+00:00", "")
        )
    except ValueError as e:
        exc = ValidationError("invalid input date: %s" % e)
        raise exc


def get_int(input: Optional[Any]) -> Optional[int]:
    """Check if the input can be parsed as an integer"""

    if input is None:
        return None

    try:
        val = int(input)
    except ValueError as e:
        raise ValidationError("invalid input integer value: %s" % e)
    return val


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
                    "filter additional parameters required: %s"
                    % ", ".join(cruncher.config_params)
                )
            cruncher_config[config_param] = config_param_value

        try:
            products = products.crunch(cruncher.clazz(cruncher_config), **kwargs)
        except MisconfiguredError as e:
            raise ValidationError(str(e))

    return products


def get_pagination_info(
    arguments: Dict[str, Any]
) -> Tuple[Optional[int], Optional[int]]:
    """Get pagination arguments"""
    page = get_int(arguments.pop("page", DEFAULT_PAGE))
    # items_per_page can be specified using limit or itemsPerPage
    items_per_page = get_int(arguments.pop("limit", DEFAULT_ITEMS_PER_PAGE))
    items_per_page = get_int(arguments.pop("itemsPerPage", items_per_page))

    if page is not None and page < 0:
        raise ValidationError("invalid page number. Must be positive integer")
    if items_per_page is not None and items_per_page < 0:
        raise ValidationError(
            "invalid number of items per page. Must be positive integer"
        )
    return page, items_per_page


def get_geometry(arguments: Dict[str, Any]) -> Optional[BaseGeometry]:
    """Get geometry from arguments"""
    if arguments.get("intersects") and arguments.get("bbox"):
        raise ValidationError("Only one of bbox and intersects can be used at a time.")

    if arguments.get("bbox"):
        request_bbox = arguments.pop("bbox")
        if isinstance(request_bbox, str):
            request_bbox = request_bbox.split(",")
        elif not isinstance(request_bbox, list):
            raise ValidationError("bbox argument type should be Array")

        try:
            request_bbox = [float(coord) for coord in request_bbox]
        except ValueError as e:
            raise ValidationError(f"invalid bbox coordinate type: {e}")

        if len(request_bbox) == 4:
            min_x, min_y, max_x, max_y = request_bbox
        elif len(request_bbox) == 6:
            min_x, min_y, _, max_x, max_y, _ = request_bbox
        else:
            raise ValidationError(
                f"invalid bbox length ({len(request_bbox)}) for bbox {request_bbox}"
            )

        geom = Polygon([(min_x, min_y), (min_x, max_y), (max_x, max_y), (max_x, min_y)])

    elif arguments.get("intersects"):
        intersects_value = arguments.pop("intersects")
        if isinstance(intersects_value, str):
            try:
                intersects_dict = json.loads(intersects_value)
            except json.JSONDecodeError:
                raise ValidationError(
                    "The 'intersects' parameter is not a valid JSON string."
                )
        else:
            intersects_dict = intersects_value

        try:
            geom = shape(intersects_dict)
        except Exception as e:
            raise ValidationError(
                f"The 'intersects' parameter does not represent a valid geometry: {str(e)}"
            )

    else:
        geom = None

    return geom


def get_datetime(arguments: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Get the datetime criterias from the search arguments

    :param arguments: Request args
    :type arguments: dict
    :returns: Start date and end date from datetime string.
    :rtype: Tuple[Optional[str], Optional[str]]
    """
    datetime_str = arguments.pop("datetime", None)

    if datetime_str:
        datetime_split = datetime_str.split("/")
        if len(datetime_split) > 1:
            dtstart = datetime_split[0] if datetime_split[0] != ".." else None
            dtend = datetime_split[1] if datetime_split[1] != ".." else None
        elif len(datetime_split) == 1:
            # same time for start & end if only one is given
            dtstart, dtend = datetime_split[0:1] * 2
        else:
            return None, None

        return get_date(dtstart), get_date(dtend)

    else:
        # return already set (dtstart, dtend) or None
        dtstart = get_date(arguments.pop("dtstart", None))
        dtend = get_date(arguments.pop("dtend", None))
        return get_date(dtstart), get_date(dtend)


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


def get_criterias_from_metadata_mapping(
    metadata_mapping: Dict[str, Any], arguments: Dict[str, Any]
) -> Dict[str, Any]:
    """Get criterias from the search arguments with the metadata mapping config

    :param metadata_mapping: STAC metadata mapping (see 'resources/stac_provider.yml')
    :type metadata_mapping: dict
    :param arguments: Request args
    :type arguments: dict
    :returns: Mapping of criterias with their corresponding values
    :rtype: dict
    """
    criterias: Dict[str, Any] = {}
    metadata_query_paths = get_metadata_query_paths(metadata_mapping)
    arguments_query_paths = get_arguments_query_paths(arguments)
    for query_path in arguments_query_paths:
        if query_path in metadata_query_paths:
            criteria_name = metadata_query_paths[query_path]
        else:
            # The criteria is custom and we must read
            # its name from the query path
            criteria_name = query_path.split(".")[1]
        criteria_value = arguments_query_paths[query_path]
        criterias[criteria_name] = criteria_value
    return criterias


def search_products(
    product_type: str, arguments: Dict[str, Any], stac_formatted: bool = True
) -> Union[Dict[str, Any], SearchResult]:
    """Returns product search results

    :param product_type: The product type criteria
    :type product_type: str
    :param arguments: Request args
    :type arguments: dict
    :param stac_formatted: Whether input is STAC-formatted or not
    :type stac_formatted: bool
    :returns: A search result
    :rtype serialized GeoJSON response"""

    try:
        arg_product_type = arguments.pop("product_type", None)
        provider = arguments.pop("provider", None)

        unserialized = arguments.pop("unserialized", None)

        page, items_per_page = get_pagination_info(arguments)
        dtstart, dtend = get_datetime(arguments)
        geom = get_geometry(arguments)

        criterias = {
            "productType": product_type if product_type else arg_product_type,
            "page": page,
            "items_per_page": items_per_page,
            "start": dtstart,
            "end": dtend,
            "geom": geom,
            "provider": provider,
        }

        if stac_formatted:
            stac_provider_metadata_mapping = stac_provider_config.get("search", {}).get(
                "metadata_mapping", {}
            )
            extra_criterias = get_criterias_from_metadata_mapping(
                stac_provider_metadata_mapping, arguments
            )
            criterias.update(extra_criterias)
        else:
            criterias.update(arguments)

        # We remove potential None values to use the default values of the search method
        criterias = dict((k, v) for k, v in criterias.items() if v is not None)

        products, total = eodag_api.search(**criterias)

        products = filter_products(products, arguments, **criterias)

        response: Union[Dict[str, Any], SearchResult]
        if not unserialized:
            response = products.as_geojson_object()
            response.update(
                {
                    "properties": {
                        "page": page,
                        "itemsPerPage": items_per_page,
                        "totalResults": total,
                    }
                }
            )
        else:
            response = products
            response.properties = {
                "page": page,
                "itemsPerPage": items_per_page,
                "totalResults": total,
            }

    except ValidationError as e:
        raise e
    except RuntimeError as e:
        raise e
    except UnsupportedProductType as e:
        raise e

    return response


def search_product_by_id(
    uid: str,
    product_type: Optional[str] = None,
    provider: Optional[str] = None,
    **kwargs: Any,
) -> SearchResult:
    """Search a product by its id

    :param uid: The uid of the EO product
    :type uid: str
    :param product_type: (optional) The product type
    :type product_type: str
    :param provider: (optional) The provider to be used
    :type provider: str
    :param kwargs: additional search parameters
    :type kwargs: Any
    :returns: A search result
    :rtype: :class:`~eodag.api.search_result.SearchResult`
    :raises: :class:`~eodag.utils.exceptions.ValidationError`
    :raises: RuntimeError
    """
    try:
        products, _ = eodag_api.search(
            id=uid, productType=product_type, provider=provider, **kwargs
        )
        return products
    except ValidationError:
        raise
    except RuntimeError:
        raise


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


def get_stac_item_by_id(
    url: str,
    item_id: str,
    catalogs: List[str],
    root: str = "/",
    provider: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Build STAC item by id

    :param url: Requested URL
    :type url: str
    :param item_id: Product ID
    :type item_id: str
    :param catalogs: Catalogs list (only first is used as product_type)
    :type catalogs: list
    :param root: (optional) API root
    :type root: str
    :param provider: (optional) Chosen provider
    :type provider: str
    :param kwargs: additional search parameters
    :type kwargs: Any
    :returns: Collection dictionary
    :rtype: dict
    """
    product_type = catalogs[0]
    _dc_qs = kwargs.get("_dc_qs", None)

    found_products = search_product_by_id(
        item_id, product_type=product_type, _dc_qs=_dc_qs
    )

    if len(found_products) > 0:
        found_products[0].product_type = eodag_api.get_alias_from_product_type(
            found_products[0].product_type
        )
        return StacItem(
            url=url,
            stac_config=stac_config,
            provider=provider,
            eodag_api=eodag_api,
            root=root,
        ).get_stac_item_from_product(product=found_products[0])
    else:
        return None


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
    _dc_qs = kwargs.get("_dc_qs", None)

    search_plugin = next(
        eodag_api._plugins_manager.get_search_plugins(product_type, provider)
    )
    provider_product_type_config = search_plugin.config.products.get(
        product_type, {}
    ) or search_plugin.config.products.get(GENERIC_PRODUCT_TYPE, {})
    if provider_product_type_config.get("storeDownloadUrl", False):
        if item_id not in search_plugin.download_info:
            logger.error(f"data for item {item_id} not found")
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

        search_results = search_product_by_id(
            item_id, product_type=product_type, provider=provider, _dc_qs=_dc_qs
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
            f"Download streaming not supported for {product.downloader}: downloading locally then delete"
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
                    f"Building archive for downloaded product path {filepath_to_stream}"
                )
                make_archive(product_path, "zip", product_path)
                rmtree(product_path)
        else:
            filepath_to_stream = product_path

        download_stream_dict = dict(
            content=read_file_chunks_and_delete(open(filepath_to_stream, "rb")),
            headers={
                "content-disposition": f"attachment; filename={os.path.basename(filepath_to_stream)}",
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
            logger.debug(f"{opened_file.name} deleted after streaming complete")
            break
        yield data
    yield data


def get_stac_catalogs(
    url: str,
    root: str = "/",
    catalogs: List[str] = [],
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
        catalogs=catalogs,
        fetch_providers=fetch_providers,
    ).get_stac_catalog()


def search_stac_items(
    url: str,
    arguments: Dict[str, Any],
    root: str = "/",
    catalogs: List[str] = [],
    provider: Optional[str] = None,
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
    collections = arguments.get("collections", None)

    catalog_url = url.replace("/items", "")

    next_page_kwargs = {
        key: value for key, value in arguments.copy().items() if value is not None
    }
    next_page_id = (
        int(next_page_kwargs["page"]) + 1 if "page" in next_page_kwargs else 2
    )
    next_page_kwargs["page"] = next_page_id

    # use catalogs from path or if it is empty, collections from args
    if catalogs:
        result_catalog = StacCatalog(
            url=catalog_url,
            stac_config=stac_config,
            root=root,
            provider=provider,
            eodag_api=eodag_api,
            catalogs=catalogs,
        )
    elif collections:
        # get collection as product_type
        if isinstance(collections, str):
            collections = collections.split(",")
        elif not isinstance(collections, list):
            raise ValidationError("Collections argument type should be Array")

        result_catalog = StacCatalog(
            stac_config=stac_config,
            root=root,
            provider=provider,
            eodag_api=eodag_api,
            # handle only one collection
            # per request (STAC allows multiple)
            catalogs=collections[0:1],
            url=catalog_url.replace("/search", f"/collections/{collections[0]}"),
        )
        arguments.pop("collections")
    else:
        raise NoMatchingProductType("Invalid request, collections argument is missing")

    # get products by ids
    ids = arguments.get("ids", None)
    if isinstance(ids, str):
        ids = [ids]
    if ids:
        search_results = SearchResult([])
        for item_id in ids:
            found_products = search_product_by_id(
                item_id, product_type=collections[0], provider=provider
            )
            if len(found_products) == 1:
                search_results.extend(found_products)
        search_results.properties = {
            "page": 1,
            "itemsPerPage": len(search_results),
            "totalResults": len(search_results),
        }
    else:
        if "datetime" in arguments.keys() and arguments["datetime"] is not None:
            arguments["dtstart"], arguments["dtend"] = get_datetime(arguments)

        search_products_arguments = dict(
            arguments,
            **result_catalog.search_args,
            **{"unserialized": "true", "provider": provider},
        )

        # check if time filtering appears both in search arguments and catalog
        if set(["dtstart", "dtend"]) <= set(arguments.keys()) and set(
            ["dtstart", "dtend"]
        ) <= set(result_catalog.search_args.keys()):
            search_date_min = (
                dateutil.parser.parse(arguments["dtstart"])
                if arguments["dtstart"]
                else datetime.datetime.min
            )
            search_date_max = (
                dateutil.parser.parse(arguments["dtend"])
                if arguments["dtend"]
                else datetime.datetime.now()
            )
            catalog_date_min = dateutil.parser.parse(
                result_catalog.search_args["dtstart"]
            )
            catalog_date_max = dateutil.parser.parse(
                result_catalog.search_args["dtend"]
            )
            # check if date intervals overlap
            if (search_date_min <= catalog_date_max) and (
                search_date_max >= catalog_date_min
            ):
                # use intersection
                search_products_arguments["dtstart"] = (
                    max(search_date_min, catalog_date_min)
                    .isoformat()
                    .replace("+00:00", "")
                    + "Z"
                )
                search_products_arguments["dtend"] = (
                    min(search_date_max, catalog_date_max)
                    .isoformat()
                    .replace("+00:00", "")
                    + "Z"
                )
            else:
                logger.warning("Time intervals do not overlap")
                # return empty results
                search_results = SearchResult([])
                search_results.properties = {
                    "page": search_products_arguments.get("page", 1),
                    "itemsPerPage": search_products_arguments.get(
                        "itemsPerPage", DEFAULT_ITEMS_PER_PAGE
                    ),
                    "totalResults": 0,
                }
                return StacItem(
                    url=url,
                    stac_config=stac_config,
                    provider=provider,
                    eodag_api=eodag_api,
                    root=root,
                ).get_stac_items(
                    search_results=search_results,
                    catalog=dict(
                        result_catalog.get_stac_catalog(),
                        **{"url": result_catalog.url, "root": result_catalog.root},
                    ),
                )

        search_results = search_products(
            product_type=result_catalog.search_args["product_type"],
            arguments=search_products_arguments,
        )

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
        provider=provider,
        eodag_api=eodag_api,
        root=root,
    ).get_stac_items(
        search_results=search_results,
        catalog=dict(
            result_catalog.get_stac_catalog(),
            **{"url": result_catalog.url, "root": result_catalog.root},
        ),
    )

    return items


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


def telemetry_init(app: FastAPI):
    """Init telemetry

    :param app: FastAPI to automatically instrument.
    :type app: FastAPI"""

    # Start Prometheus client
    resource = Resource(attributes={SERVICE_NAME: "eodag-serve-rest"})
    exporter_host = os.getenv("EODAG_EXPORTER_PROMETHEUS_HOST", "0.0.0.0")
    exporter_port = os.getenv("EODAG_EXPORTER_PROMETHEUS_PORT", "8000")
    start_http_server(port=int(exporter_port), addr=exporter_host)
    reader = PrometheusMetricReader()
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

    # FastAPI instrumentation
    FastAPIInstrumentor.instrument_app(app, meter_provider=meter_provider)

    # Manual instrumentation
    meter = metrics.get_meter("eodag.core.meter")
    telemetry["search_product_type_total"] = meter.create_counter(
        "eodag.core.search_product_type_total",
        description="The number of searches by product type",
    )
    telemetry["downloaded_data_bytes_total"] = meter.create_counter(
        "eodag.download.downloaded_data_bytes_total",
        description="Measure data downloaded from each provider",
    )
    telemetry["available_providers_total"] = meter.create_observable_gauge(
        "eodag.core.available_providers_total",
        callbacks=[_available_providers_callback],
        description="The number available providers",
    )
    telemetry["available_product_types_total"] = meter.create_observable_gauge(
        "eodag.core.available_product_types_total",
        callbacks=[_available_product_types_callback],
        description="The number available product types",
    )


def _available_providers_callback(options: CallbackOptions) -> Iterable[Observation]:
    return [
        Observation(
            len(eodag_api.available_providers()),
            {"eodag.core.gauge.label": "Available Providers"},
        )
    ]


def _available_product_types_callback(
    options: CallbackOptions,
) -> Iterable[Observation]:
    return [
        Observation(
            len(eodag_api.list_product_types()),
            {"eodag.core.gauge.label": "Available Product Types"},
        )
    ]


def record_downloaded_data(provider: str, byte_count: int):
    """Measure the downloaded bytes for a given provider.

    :param provider: The provider from which the data is downloaded.
    :type provider: str
    :param byte_count: Number of bytes downloaded.
    :type byte_count: int
    """
    if telemetry:
        telemetry["downloaded_data_bytes_total"].add(
            byte_count,
            {"eodag.download.provider": provider},
        )


def record_searched_product_type(product_type: str):
    """Measure the number of times a product type is searcher.

    :param product_type: The product type.
    :type product_type: str
    """
    if telemetry:
        telemetry["search_product_type_total"].add(
            1, {"eodag.search.product_type": product_type}
        )
