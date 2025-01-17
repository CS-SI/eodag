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
from __future__ import annotations

import datetime
import logging
import os
import re
from typing import TYPE_CHECKING, cast
from unittest.mock import Mock

import dateutil
from cachetools.func import lru_cache
from fastapi.responses import ORJSONResponse, StreamingResponse
from pydantic import ValidationError as pydanticValidationError
from requests.models import Response as RequestsResponse

import eodag
from eodag import EOProduct
from eodag.api.product.metadata_mapping import (
    NOT_AVAILABLE,
    OFFLINE_STATUS,
    ONLINE_STATUS,
    OSEO_METADATA_MAPPING,
    STAGING_STATUS,
)
from eodag.api.search_result import SearchResult
from eodag.config import load_stac_config
from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.rest.cache import cached
from eodag.rest.constants import (
    CACHE_KEY_COLLECTION,
    CACHE_KEY_COLLECTIONS,
    CACHE_KEY_QUERYABLES,
)
from eodag.rest.errors import ResponseSearchError
from eodag.rest.stac import StacCatalog, StacCollection, StacCommon, StacItem
from eodag.rest.types.eodag_search import EODAGSearch
from eodag.rest.types.queryables import QueryablesGetParams, StacQueryables
from eodag.rest.types.stac_search import SearchPostRequest
from eodag.rest.utils import (
    Cruncher,
    file_to_stream,
    format_pydantic_error,
    get_next_link,
)
from eodag.rest.utils.rfc3339 import rfc3339_str_to_datetime
from eodag.utils import (
    _deprecated,
    deepcopy,
    dict_items_recursive_apply,
    format_dict_items,
    obj_md5sum,
    urlencode,
)
from eodag.utils.exceptions import (
    MisconfiguredError,
    NotAvailableError,
    ValidationError,
)

if TYPE_CHECKING:
    from typing import Any, Optional, Union

    from fastapi import Request
    from requests.auth import AuthBase
    from starlette.responses import Response


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
    :param ipp: (optional) Items per page number
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
def format_product_types(product_types: list[dict[str, Any]]) -> str:
    """Format product_types

    :param product_types: A list of EODAG product types as returned by the core api
    """
    result: list[str] = []
    for pt in product_types:
        result.append(f'* *__{pt["ID"]}__*: {pt["abstract"]}')
    return "\n".join(sorted(result))


def search_stac_items(
    request: Request,
    search_request: SearchPostRequest,
) -> dict[str, Any]:
    """
    Search and retrieve STAC items based on the given search request.

    This function takes a search request, performs a search using EODAG API, and returns a
    dictionary of STAC items.

    :param request: The incoming HTTP request with state information.
    :param search_request: The search criteria for STAC items
    :returns: A dictionary containing the STAC items and related metadata.

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
        eodag_args = EODAGSearch.model_validate(stac_args)
    except pydanticValidationError as e:
        raise ValidationError(format_pydantic_error(e)) from e

    catalog_url = re.sub("/items.*", "", request.state.url)
    catalog = StacCatalog(
        url=catalog_url.replace("/search", f"/collections/{eodag_args.productType}"),
        stac_config=stac_config,
        root=request.state.url_root,
        provider=eodag_args.provider,
        eodag_api=eodag_api,
        collection=eodag_args.productType,  # type: ignore
    )

    # get products by ids
    if eodag_args.ids:
        results = SearchResult([])
        for item_id in eodag_args.ids:
            results.extend(
                eodag_api.search(
                    id=item_id,
                    productType=eodag_args.productType,
                    provider=eodag_args.provider,
                )
            )
        results.number_matched = len(results)
        total = len(results)

    else:
        criteria = eodag_args.model_dump(exclude_none=True)
        # remove provider prefixes
        # quickfix for ecmwf fake extension to not impact items creation
        stac_extensions = list(stac_config["extensions"].keys()) + ["ecmwf"]
        for key in list(criteria):
            if ":" in key and key.split(":")[0] not in stac_extensions:
                new_key = key.split(":")[1]
                criteria[new_key] = criteria.pop(key)

        results = eodag_api.search(count=True, **criteria)
        total = results.number_matched or 0

    if len(results) == 0 and results.errors:
        raise ResponseSearchError(results.errors)

    if search_request.crunch:
        results = crunch_products(results, search_request.crunch, **criteria)

    for record in results:
        record.product_type = eodag_api.get_alias_from_product_type(record.product_type)

    items = StacItem(
        url=request.state.url,
        stac_config=stac_config,
        provider=eodag_args.provider,
        eodag_api=eodag_api,
        root=request.state.url_root,
    ).get_stac_items(
        search_results=results,
        total=total,
        next_link=get_next_link(
            request, search_request, total, eodag_args.items_per_page
        ),
        catalog={
            **catalog.data,
            **{"url": catalog.url, "root": catalog.root},
        },
    )
    return items


def download_stac_item(
    request: Request,
    collection_id: str,
    item_id: str,
    provider: Optional[str] = None,
    asset: Optional[str] = None,
    **kwargs: Any,
) -> Response:
    """Download item

    :param collection_id: id of the product type
    :param item_id: Product ID
    :param provider: (optional) Chosen provider
    :param kwargs: additional download parameters
    :returns: a stream of the downloaded data (zip file)
    """
    product_type = collection_id

    search_results = eodag_api.search(
        id=item_id, productType=product_type, provider=provider, **kwargs
    )
    if len(search_results) > 0:
        product = cast(EOProduct, search_results[0])

    else:
        raise NotAvailableError(
            f"Could not find {item_id} item in {product_type} collection"
            + (f" for provider {provider}" if provider else "")
        )
    auth = product.downloader_auth.authenticate() if product.downloader_auth else None

    try:
        if product.properties.get("orderLink"):
            _order_and_update(product, auth, kwargs)

        download_stream = product.downloader._stream_download_dict(
            product,
            auth=auth,
            asset=asset,
            wait=-1,
            timeout=-1,
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
        if product.properties.get("storageStatus") != ONLINE_STATUS:
            kwargs["orderId"] = kwargs.get("orderId") or product.properties.get(
                "orderId"
            )
            kwargs["provider"] = provider
            qs = urlencode(kwargs, doseq=True)
            download_link = f"{request.state.url}?{qs}"
            return ORJSONResponse(
                status_code=202,
                headers={"Location": download_link},
                content={
                    "description": "Product is not available yet, please try again using given updated location",
                    "status": product.properties.get("orderStatus"),
                    "location": download_link,
                },
            )
        else:
            raise

    return StreamingResponse(
        content=download_stream.content,
        headers=download_stream.headers,
        media_type=download_stream.media_type,
    )


def _order_and_update(
    product: EOProduct,
    auth: Union[AuthBase, dict[str, str], None],
    query_args: dict[str, Any],
) -> None:
    """Order product if needed and update given kwargs with order-status-dict"""
    if product.properties.get("storageStatus") != ONLINE_STATUS and hasattr(
        product.downloader, "order_response_process"
    ):
        # update product (including orderStatusLink) if product was previously ordered
        logger.debug("Use given download query arguments to parse order link")
        response = Mock(spec=RequestsResponse)
        response.status_code = 200
        response.json.return_value = query_args
        response.headers = {}
        product.downloader.order_response_process(response, product)

    if (
        product.properties.get("storageStatus") != ONLINE_STATUS
        and NOT_AVAILABLE in product.properties.get("orderStatusLink", "")
        and hasattr(product.downloader, "_order")
    ):
        # first order
        logger.debug("Order product")
        order_status_dict = product.downloader._order(product=product, auth=auth)
        query_args.update(order_status_dict or {})

    if (
        product.properties.get("storageStatus") == OFFLINE_STATUS
        and product.properties.get("orderStatusLink")
        and NOT_AVAILABLE not in product.properties.get("orderStatusLink", "")
    ):
        product.properties["storageStatus"] = STAGING_STATUS

    if product.properties.get("storageStatus") == STAGING_STATUS and hasattr(
        product.downloader, "_order_status"
    ):
        # check order status if needed
        logger.debug("Checking product order status")
        product.downloader._order_status(product=product, auth=auth)

    if product.properties.get("storageStatus") != ONLINE_STATUS:
        raise NotAvailableError("Product is not available yet")


@lru_cache(maxsize=1)
def get_detailled_collections_list() -> list[dict[str, Any]]:
    """Returns detailled collections / product_types list as a list of
    config dicts

    :returns: List of config dicts
    """
    return eodag_api.list_product_types(fetch_providers=False)


async def all_collections(
    request: Request,
    provider: Optional[str] = None,
    q: Optional[str] = None,
    platform: Optional[str] = None,
    instrument: Optional[str] = None,
    constellation: Optional[str] = None,
    datetime: Optional[str] = None,
) -> dict[str, Any]:
    """Build STAC collections

    :param url: Requested URL
    :param root: The API root
    :param filters: Search collections filters
    :param provider: (optional) Chosen provider
    :returns: Collections dictionary
    """

    async def _fetch() -> dict[str, Any]:
        stac_collection = StacCollection(
            url=request.state.url,
            stac_config=stac_config,
            provider=provider,
            eodag_api=eodag_api,
            root=request.state.url_root,
        )
        collections = deepcopy(stac_config["collections"])
        collections["collections"] = stac_collection.get_collection_list(
            q=q,
            platform=platform,
            instrument=instrument,
            constellation=constellation,
            datetime=datetime,
        )

        # # parse f-strings
        format_args = deepcopy(stac_config)
        format_args["collections"].update(
            {
                "url": stac_collection.url,
                "root": stac_collection.root,
            }
        )

        collections["links"] = [
            format_dict_items(link, **format_args) for link in collections["links"]
        ]

        collections = format_dict_items(collections, **format_args)
        return collections

    hashed_collections = hash(
        f"{provider}:{q}:{platform}:{instrument}:{constellation}:{datetime}"
    )
    cache_key = f"{CACHE_KEY_COLLECTIONS}:{hashed_collections}"
    return await cached(_fetch, cache_key, request)


async def get_collection(
    request: Request, collection_id: str, provider: Optional[str] = None
) -> dict[str, Any]:
    """Build STAC collection by id

    :param url: Requested URL
    :param root: API root
    :param collection_id: Product_type as ID of the collection
    :param provider: (optional) Chosen provider
    :returns: Collection dictionary
    """

    async def _fetch() -> dict[str, Any]:
        stac_collection = StacCollection(
            url=request.state.url,
            stac_config=stac_config,
            provider=provider,
            eodag_api=eodag_api,
            root=request.state.url_root,
        )
        collection_list = stac_collection.get_collection_list(collection=collection_id)

        if not collection_list:
            raise NotAvailableError(f"Collection {collection_id} does not exist.")

        return collection_list[0]

    cache_key = f"{CACHE_KEY_COLLECTION}:{provider}:{collection_id}"
    return await cached(_fetch, cache_key, request)


async def get_stac_catalogs(
    request: Request,
    url: str,
    provider: Optional[str] = None,
) -> dict[str, Any]:
    """Build STAC catalog

    :param url: Requested URL
    :param root: (optional) API root
    :param provider: (optional) Chosen provider
    :returns: Catalog dictionary
    """

    async def _fetch() -> dict[str, Any]:
        return StacCatalog(
            url=url,
            stac_config=stac_config,
            root=request.state.url_root,
            provider=provider,
            eodag_api=eodag_api,
        ).data

    return await cached(_fetch, f"{CACHE_KEY_COLLECTION}:{provider}", request)


def time_interval_overlap(eodag_args: EODAGSearch, catalog: StacCatalog) -> bool:
    """fix search date filter based on catalog date range"""
    # check if time filtering appears both in search arguments and catalog
    # (for catalogs built by date: i.e. `year/2020/month/05`)
    if not set(["start", "end"]) <= set(eodag_args.model_dump().keys()) or not set(
        [
            "start",
            "end",
        ]
    ) <= set(catalog.search_args.keys()):
        return True

    search_date_min = cast(
        datetime.datetime,
        (
            dateutil.parser.parse(eodag_args.start)  # type: ignore
            if eodag_args.start
            else datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
        ),
    )
    search_date_max = cast(
        datetime.datetime,
        (
            dateutil.parser.parse(eodag_args.end)  # type: ignore
            if eodag_args.end
            else datetime.datetime.now(tz=datetime.timezone.utc)
        ),
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


@lru_cache(maxsize=1)
def get_stac_conformance() -> dict[str, str]:
    """Build STAC conformance

    :returns: conformance dictionary
    """
    return stac_config["conformance"]


def get_stac_api_version() -> str:
    """Get STAC API version

    :returns: STAC API version
    """
    return stac_config["stac_api_version"]


@lru_cache(maxsize=1)
def get_stac_extension_oseo(url: str) -> dict[str, str]:
    """Build STAC OGC / OpenSearch Extension for EO

    :param url: Requested URL
    :returns: Catalog dictionary
    """

    def apply_method(_: str, x: str) -> str:
        return str(x).replace("$.product.", "$.")

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


async def get_queryables(
    request: Request,
    params: QueryablesGetParams,
    provider: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch the queryable properties for a collection.

    :param collection_id: The ID of the collection.
    :returns: A set containing the STAC standardized queryable properties for a collection.
    """

    async def _fetch() -> dict[str, Any]:
        python_queryables = eodag_api.list_queryables(
            provider=provider,
            fetch_providers=False,
            **params.model_dump(exclude_none=True, by_alias=True),
        )

        python_queryables_json = python_queryables.get_model().model_json_schema(
            by_alias=True
        )

        properties: dict[str, Any] = python_queryables_json["properties"]
        required: list[str] = python_queryables_json.get("required") or []

        # productType is either simply removed or replaced by collection later.
        if "productType" in properties:
            properties.pop("productType")
        if "productType" in required:
            required.remove("productType")

        stac_properties: dict[str, Any] = {}

        # get stac default properties to set prefixes
        stac_item_properties = list(stac_config["item"]["properties"].values())
        stac_item_properties.extend(stac_config["metadata_ignore"])
        for param, queryable in properties.items():
            # convert key to STAC format
            if param in OSEO_METADATA_MAPPING.keys() and not any(
                param in str(prop) for prop in stac_item_properties
            ):
                param = f"oseo:{param}"
            stac_param = EODAGSearch.to_stac(param, stac_item_properties, provider)

            queryable["title"] = stac_param.split(":")[-1]

            # remove null default values
            if not queryable.get("default"):
                queryable.pop("default", None)

            stac_properties[stac_param] = queryable
            required = list(map(lambda x: x.replace(param, stac_param), required))

        # due to certain metadata mappings we might only get end_datetime but we can
        # assume that start_datetime is also available
        if (
            "end_datetime" in stac_properties
            and "start_datetime" not in stac_properties
        ):
            stac_properties["start_datetime"] = deepcopy(
                stac_properties["end_datetime"]
            )
            stac_properties["start_datetime"]["title"] = "start_datetime"
        # if we can search by start_datetime we can search by datetime
        if "start_datetime" in stac_properties:
            stac_properties["datetime"] = StacQueryables.possible_properties[
                "datetime"
            ].model_dump()

        # format spatial extend properties to STAC format.
        if "geometry" in stac_properties:
            stac_properties["bbox"] = StacQueryables.possible_properties[
                "bbox"
            ].model_dump()
            stac_properties["geometry"] = StacQueryables.possible_properties[
                "geometry"
            ].model_dump()

        if not params.collection:
            stac_properties["collection"] = StacQueryables.default_properties[
                "collection"
            ].model_dump()

        additional_properties = python_queryables.additional_properties
        description = "Queryable names for the EODAG STAC API Item Search filter. "
        description += python_queryables.additional_information

        return StacQueryables(
            q_id=request.state.url,
            additional_properties=additional_properties,
            properties=stac_properties,
            required=required or None,
            description=description,
        ).model_dump(mode="json", by_alias=True, exclude_none=True)

    hashed_queryables = hash(params.model_dump_json())
    return await cached(
        _fetch, f"{CACHE_KEY_QUERYABLES}:{provider}:{hashed_queryables}", request
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

    cruncher_config: dict[str, Any] = {}
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
    StacCollection.fetch_external_stac_collections(eodag_api)

    # update eodag product_types config form external stac collections
    for p, p_f in eodag_api.product_types_config.source.items():
        for key in (p, p_f.get("alias")):
            if key is None:
                continue
            ext_col = StacCollection.ext_stac_collections.get(key)
            if not ext_col:
                continue
            platform: Union[str, list[str]] = ext_col.get("summaries", {}).get(
                "platform"
            )
            constellation: Union[str, list[str]] = ext_col.get("summaries", {}).get(
                "constellation"
            )
            processing_level: Union[str, list[str]] = ext_col.get("summaries", {}).get(
                "processing:level"
            )
            # Check if platform or constellation are lists and join them into a string if they are
            if isinstance(platform, list):
                platform = ",".join(platform)
            if isinstance(constellation, list):
                constellation = ",".join(constellation)
            if isinstance(processing_level, list):
                processing_level = ",".join(processing_level)

            update_fields = {
                "title": ext_col.get("title"),
                "abstract": ext_col["description"],
                "keywords": ext_col.get("keywords"),
                "instrument": ",".join(
                    ext_col.get("summaries", {}).get("instruments", [])
                ),
                "platform": constellation,
                "platformSerialIdentifier": platform,
                "processingLevel": processing_level,
                "license": ext_col["license"],
                "missionStartDate": ext_col["extent"]["temporal"]["interval"][0][0],
                "missionEndDate": ext_col["extent"]["temporal"]["interval"][-1][1],
            }
            clean = {k: v for k, v in update_fields.items() if v}
            p_f.update(clean)

    eodag_api.product_types_config_md5 = obj_md5sum(
        eodag_api.product_types_config.source
    )

    eodag_api.build_index()

    # pre-build search plugins
    for provider in eodag_api.available_providers():
        next(eodag_api._plugins_manager.get_search_plugins(provider=provider))
