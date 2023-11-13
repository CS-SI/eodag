# -*- coding: utf-8 -*-
# Copyright 2023, CS GROUP - France, https://www.csgroup.eu/
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
import datetime
import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional, cast

import dateutil
from fastapi import Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError as pydanticValidationError

import eodag
from eodag import EOProduct
from eodag.api.product.metadata_mapping import OSEO_METADATA_MAPPING
from eodag.api.search_result import SearchResult
from eodag.config import load_stac_config
from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.rest.stac import StacCatalog, StacCollection, StacCommon, StacItem
from eodag.rest.types.eodag_search import EODAGSearch
from eodag.rest.types.stac_queryables import StacQueryableProperty, StacQueryables
from eodag.rest.types.stac_search import SearchPostRequest
from eodag.rest.utils import (
    Cruncher,
    file_to_stream,
    format_pydantic_error,
    get_datetime,
    get_next_link,
)
from eodag.rest.utils.rfc3339 import rfc3339_str_to_datetime
from eodag.utils import (
    StreamResponse,
    _deprecated,
    deepcopy,
    dict_items_recursive_apply,
)
from eodag.utils.exceptions import (
    MisconfiguredError,
    NoMatchingProductType,
    NotAvailableError,
    ValidationError,
)

eodag_api = eodag.EODataAccessGateway()

logger = logging.getLogger("eodag.rest.core")

stac_config = load_stac_config()

crunchers = {
    "filterLatestIntersect": Cruncher(FilterLatestIntersect, []),
    "filterLatestByName": Cruncher(FilterLatestByName, ["name_pattern"]),
    "filterOverlap": Cruncher(FilterOverlap, ["minimum_overlap"]),
}


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


def search_stac_items(
    request: Request,
    search_request: SearchPostRequest,
    catalogs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Search and retrieve STAC items from the given catalogs.

    This function takes a search request and optional catalogs list, performs a search using EODAG API, and returns a
    dictionary of STAC items.

    :param request: The incoming HTTP request with state information.
    :type request: Request
    :param search_request: The search criteria for STAC items.
    :type search_request: SearchPostRequest
    :param catalogs: (optional) A list of catalogs to search within. Defaults to None.
    :type catalogs: Optional[List[str]]
    :returns: A dictionary containing the STAC items and related metadata.
    :rtype: Dict[str, Any]

    The function handles the conversion of search criteria into STAC and EODAG compatible formats, validates the input
    using pydantic, and constructs the appropriate URLs for querying the STAC API. It also manages pagination and the
    construction of the 'next' link for the response.

    If specific item IDs are provided, it retrieves the corresponding products. Otherwise, it performs a search based on
    the provided criteria and time interval overlap checks.

    The results are then formatted into STAC items and returned as part of the response dictionary, which includes the
    items themselves, total count, and the next link if applicable.
    """
    stac_args = search_request.model_dump(exclude_none=True)
    if search_request.start_date:
        stac_args["start_datetime"] = search_request.start_date
    if search_request.end_date:
        stac_args["end_datetime"] = search_request.end_date
    if search_request.spatial_filter:
        stac_args["geometry"] = search_request.spatial_filter

    try:
        eodag_args = EODAGSearch.model_validate(
            stac_args, context={"isCatalog": bool(catalogs)}
        )
    except pydanticValidationError as e:
        raise ValidationError(format_pydantic_error(e)) from e

    catalog_url = re.sub("/items.*", "", request.state.url)

    catalog = StacCatalog(
        url=catalog_url
        if catalogs
        else catalog_url.replace("/search", f"/collections/{eodag_args.productType}"),
        stac_config=stac_config,
        root=request.state.url_root,
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
            search_results.extend(products)
        total = len(search_results)

    elif time_interval_overlap(eodag_args, catalog):
        criteria = {**catalog.search_args, **eodag_args.model_dump(exclude_none=True)}
        search_results, total = eodag_api.search(**criteria)
        if search_request.crunch:
            search_results = crunch_products(
                search_results, search_request.crunch, **criteria
            )
    else:
        # return empty results
        search_results = SearchResult([])
        total = 0

    for record in search_results:
        record.product_type = eodag_api.get_alias_from_product_type(record.product_type)

    items = StacItem(
        url=request.state.url,
        stac_config=stac_config,
        provider=eodag_args.provider,
        eodag_api=eodag_api,
        root=request.state.url_root,
    ).get_stac_items(
        search_results=search_results,
        total=total,
        next_link=get_next_link(
            request, search_request, total, eodag_args.items_per_page
        ),
        catalog=dict(
            catalog.get_stac_catalog(),
            **{"url": catalog.url, "root": catalog.root},
        ),
    )

    return items


def download_stac_item(
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

    search_results, _ = eodag_api.search(
        id=item_id, productType=product_type, provider=provider, **kwargs
    )
    if len(search_results) > 0:
        product = cast(EOProduct, search_results[0])
    else:
        raise NotAvailableError(
            f"Could not find {item_id} item in {product_type} collection"
            + (f" for provider {provider}" if provider else "")
        )

    try:
        download_stream = cast(
            StreamResponse,
            product.downloader._stream_download_dict(
                product,
                auth=product.downloader_auth.authenticate(),
                asset=asset,
                wait=-1,
                timeout=-1,
            ),
        )
    except NotImplementedError:
        logger.warning(
            "Download streaming not supported for %s: downloading locally then delete",
            product.downloader,
        )
        download_stream = file_to_stream(
            eodag_api.download(product, extract=False, asset=asset)
        )
    except NotAvailableError:
        download_stream.content = (i for i in range(0))
        download_stream.status_code = 202

    return StreamingResponse(
        content=download_stream.content,
        headers=download_stream.headers,
        media_type=download_stream.media_type,
        status_code=getattr(download_stream, "status_code", 200),
    )


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


def time_interval_overlap(eodag_args: EODAGSearch, catalog: StacCatalog) -> bool:
    """fix search date filter based on catalog date range"""
    # check if time filtering appears both in search arguments and catalog
    # (for catalogs built by date: i.e. `year/2020/month/05`)
    if not set(["start", "end"]) <= set(eodag_args.model_dump().keys()) or not set(
        ["start", "end"]
    ) <= set(catalog.search_args.keys()):
        return True

    search_date_min = cast(
        datetime.datetime,
        dateutil.parser.parse(eodag_args.start)  # type: ignore
        if eodag_args.start
        else datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
    )
    search_date_max = cast(
        datetime.datetime,
        dateutil.parser.parse(eodag_args.end)  # type: ignore
        if eodag_args.end
        else datetime.datetime.now(tz=datetime.timezone.utc),
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


def get_stac_extension_oseo(url: str) -> Dict[str, str]:
    """Build STAC OGC / OpenSearch Extension for EO

    :param url: Requested URL
    :type url: str
    :returns: Catalog dictionnary
    :rtype: dict
    """

    apply_method: Callable[[str, str], str] = lambda _, x: str(x).replace(
        "$.product.", "$."
    )
    item_mapping = dict_items_recursive_apply(stac_config["item"], apply_method)

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


def get_queryables(
    request: Request,
    collection: Optional[str] = None,
    provider: Optional[str] = None,
    **kwargs: Any,
) -> StacQueryables:
    """Fetch the queryable properties for a collection.

    :param collection_id: The ID of the collection.
    :type collection_id: str
    :param provider: (optional) The provider.
    :type provider: str
    :param kwargs: additional filters for queryables (`productType` or other search
                   arguments)
    :type kwargs: Any
    :returns: A set containing the STAC standardized queryable properties for a collection.
    :rtype Dict[str, StacQueryableProperty]: set
    """
    if collection and "productType" in kwargs:
        kwargs.pop("productType")
    elif "productType" in kwargs:
        collection = kwargs.pop("productType")

    if "datetime" in kwargs:
        dates = get_datetime(kwargs)
        kwargs["start"] = dates[0]
        kwargs["end"] = dates[1]

    python_queryables = eodag_api.list_queryables(
        provider=provider, productType=collection, **kwargs
    )
    python_queryables.pop("start")
    python_queryables.pop("end")

    # productType and id are already default in stac collection and id
    python_queryables.pop("productType", None)
    python_queryables.pop("id", None)

    stac_queryables: Dict[str, StacQueryableProperty] = deepcopy(
        StacQueryables.default_properties
    )
    for param, queryable in python_queryables.items():
        stac_param = EODAGSearch.to_stac(param)
        # only keep "datetime" queryable for dates
        if stac_param in stac_queryables or stac_param in (
            "start_datetime",
            "end_datetime",
        ):
            continue

        stac_queryables[
            stac_param
        ] = StacQueryableProperty.from_python_field_definition(stac_param, queryable)

    if collection:
        stac_queryables.pop("collection")

    return StacQueryables(
        q_id=request.state.url,
        additional_properties=bool(not collection),
        properties=stac_queryables,
    )


@_deprecated(
    reason="Used to format output from deprecated function get_home_page_content",
    version="2.6.1",
)
def get_templates_path() -> str:
    """Returns Jinja templates path"""
    return os.path.join(os.path.dirname(__file__), "templates")


def crunch_products(
    products: SearchResult, cruncher_name: str, **kwargs: Any
) -> SearchResult:
    """Apply an eodag cruncher to filter products"""
    cruncher = crunchers.get(cruncher_name)
    if not cruncher:
        raise ValidationError(
            f'Unknown crunch name. Use one of: {", ".join(crunchers.keys())}'
        )

    cruncher_config: Dict[str, Any] = dict()
    for config_param in cruncher.config_params:
        config_param_value = kwargs.get(config_param)
        if not config_param_value:
            raise ValidationError(
                (
                    f"cruncher {cruncher} require additional parameters:"
                    f' {", ".join(cruncher.config_params)}'
                )
            )
        cruncher_config[config_param] = config_param_value

    try:
        products = products.crunch(cruncher.clazz(cruncher_config), **kwargs)
    except MisconfiguredError as e:
        raise ValidationError(str(e)) from e

    return products


def eodag_api_init() -> None:
    """Init EODataAccessGateway server instance, pre-running all time consuming tasks"""
    eodag_api.fetch_product_types_list()

    # pre-build search plugins
    for provider in eodag_api.available_providers():
        next(eodag_api._plugins_manager.get_search_plugins(provider=provider))
