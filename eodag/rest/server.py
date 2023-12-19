# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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
import os
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    Optional
)

from fastapi import APIRouter as FastAPIRouter
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import ORJSONResponse, StreamingResponse
from pydantic import ValidationError as pydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from eodag.config import load_stac_api_config
from eodag.rest.core import (
    download_stac_item_by_id_stream,
    eodag_api_init,
    fetch_collection_queryable_properties,
    get_detailled_collections_list,
    get_stac_api_version,
    get_stac_catalogs,
    get_stac_collection_by_id,
    get_stac_collections,
    get_stac_conformance,
    get_stac_extension_oseo,
    get_stac_item_by_id,
    search_stac_items,
)
from eodag.rest.types.eodag_search import EODAGSearch
from eodag.rest.types.stac_queryables import StacQueryables
from eodag.rest.types.stac_search import SearchPostRequest, sortby2list
from eodag.rest.utils import format_pydantic_error, str2json, str2list
from eodag.utils import parse_header, update_nested_dict
from eodag.utils.exceptions import (
    AuthenticationError,
    DownloadError,
    MisconfiguredError,
    NoMatchingProductType,
    NotAvailableError,
    RequestError,
    TimeOutError,
    UnsupportedProductType,
    UnsupportedProvider,
    ValidationError,
)

if TYPE_CHECKING:
    from fastapi.types import DecoratedCallable
    from requests import Response

logger = logging.getLogger("eodag.rest.server")
ERRORS_WITH_500_STATUS_CODE = {
    "MisconfiguredError",
    "AuthenticationError",
    "DownloadError",
    "RequestError",
}


class APIRouter(FastAPIRouter):
    """API router"""

    def api_route(
        self, path: str, *, include_in_schema: bool = True, **kwargs: Any
    ) -> Callable[[DecoratedCallable], DecoratedCallable]:
        """Creates API route decorator"""
        if path == "/":
            return super().api_route(
                path, include_in_schema=include_in_schema, **kwargs
            )

        if path.endswith("/"):
            path = path[:-1]
        add_path = super().api_route(
            path, include_in_schema=include_in_schema, **kwargs
        )

        alternate_path = path + "/"
        add_alternate_path = super().api_route(
            alternate_path, include_in_schema=False, **kwargs
        )

        def decorator(func: DecoratedCallable) -> DecoratedCallable:
            add_alternate_path(func)
            return add_path(func)

        return decorator


router = APIRouter()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """API init and tear-down"""
    eodag_api_init()
    yield


app = FastAPI(lifespan=lifespan, title="EODAG", docs_url="/api.html")

# conf from resources/stac_api.yml
stac_api_config = load_stac_api_config()


@router.get("/api", tags=["Capabilities"], include_in_schema=False)
def eodag_openapi() -> Dict[str, Any]:
    """Customized openapi"""
    logger.debug("URL: /api")
    if app.openapi_schema:
        return app.openapi_schema

    root_catalog = get_stac_catalogs(url="", fetch_providers=False)
    stac_api_version = get_stac_api_version()

    openapi_schema = get_openapi(
        title=f"{root_catalog['title']} / eodag",
        version=version("eodag"),
        routes=app.routes,
    )

    # stac_api_config
    update_nested_dict(openapi_schema["paths"], stac_api_config["paths"])
    try:
        update_nested_dict(openapi_schema["components"], stac_api_config["components"])
    except KeyError:
        openapi_schema["components"] = stac_api_config["components"]
    openapi_schema["tags"] = stac_api_config["tags"]

    detailled_collections_list = get_detailled_collections_list(fetch_providers=False)

    openapi_schema["info"]["description"] = (
        root_catalog["description"]
        + f" (stac-api-spec {stac_api_version})"
        + "<details><summary>Available collections / product types</summary>"
        + "".join(
            [
                f"[{pt['ID']}](/collections/{pt['ID']} '{pt['title']}') - "
                for pt in detailled_collections_list
            ]
        )[:-2]
        + "</details>"
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.__setattr__("openapi", eodag_openapi)

# Cross-Origin Resource Sharing
allowed_origins = os.getenv("EODAG_CORS_ALLOWED_ORIGINS")
allowed_origins_list = allowed_origins.split(",") if allowed_origins else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def forward_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Middleware that handles forward headers and sets request.state.url*"""

    forwarded_host = request.headers.get("x-forwarded-host", None)
    forwarded_proto = request.headers.get("x-forwarded-proto", None)

    if "forwarded" in request.headers:
        header_forwarded = parse_header(request.headers["forwarded"])
        forwarded_host = str(header_forwarded.get_param("host", None)) or forwarded_host
        forwarded_proto = str(header_forwarded.get_param("proto", None)) or forwarded_proto

    request.state.url_root = f"{forwarded_proto or request.url.scheme}://{forwarded_host or request.url.netloc}"
    request.state.url = f"{request.state.url_root}{request.url.path}"

    response = await call_next(request)
    return response


@app.exception_handler(StarletteHTTPException)
async def default_exception_handler(
    request: Request, error: Exception
) -> ORJSONResponse:
    """Default errors handle"""
    description = (
        getattr(error, "description", None)
        or getattr(error, "detail", None)
        or str(error)
    )
    return ORJSONResponse(
        status_code=error.status_code,
        content={"description": description},
    )


@app.exception_handler(ValidationError)
async def handle_invalid_usage_with_validation_error(
    request: Request, error: ValidationError
) -> ORJSONResponse:
    """Invalid usage [400] ValidationError handle"""
    if error.parameters:
        for error_param in error.parameters:
            stac_param = EODAGSearch.to_stac(error_param)
            error.message = error.message.replace(error_param, stac_param)
    logger.warning(traceback.format_exc())
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=400,
            detail=f"{type(error).__name__}: {str(error.message)}",
        ),
    )


@app.exception_handler(NoMatchingProductType)
@app.exception_handler(UnsupportedProductType)
@app.exception_handler(UnsupportedProvider)
async def handle_invalid_usage(request: Request, error: Exception) -> ORJSONResponse:
    """Invalid usage [400] errors handle"""
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=400,
            detail=f"{type(error).__name__}: {str(error)}",
        ),
    )


@app.exception_handler(NotAvailableError)
async def handle_resource_not_found(
    request: Request, error: Exception
) -> ORJSONResponse:
    """Not found [404] errors handle"""
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=404,
            detail=f"{type(error).__name__}: {str(error)}",
        ),
    )


@app.exception_handler(MisconfiguredError)
@app.exception_handler(AuthenticationError)
async def handle_auth_error(request: Request, error: Exception) -> ORJSONResponse:
    """These errors should be sent as internal server error to the client"""
    logger.error("%s: %s", type(error).__name__, str(error))
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=500,
            detail="Internal server error: please contact the administrator",
        ),
    )


@app.exception_handler(DownloadError)
async def handle_download_error(request: Request, error: Exception) -> ORJSONResponse:
    """DownloadError should be sent as internal server error with details to the client"""
    logger.error(f"{type(error).__name__}: {str(error)}")
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=500,
            detail=f"{type(error).__name__}: {str(error)}",
        ),
    )


@app.exception_handler(RequestError)
async def handle_request_error(request: Request, error: RequestError) -> ORJSONResponse:
    """RequestError should be sent as internal server error with details to the client"""
    if getattr(error, "history", None):
        error_history_tmp = list(error.history)
        for i, search_error in enumerate(error_history_tmp):
            if search_error[1].__class__.__name__ in ERRORS_WITH_500_STATUS_CODE:
                search_error[1].args = ("an internal error occured",)
                error_history_tmp[i] = search_error
                continue
            if getattr(error, "parameters", None):
                for error_param in error.parameters:
                    stac_param = EODAGSearch.to_stac(error_param)
                    search_error[1].args = (
                        search_error[1].args[0].replace(error_param, stac_param),
                    )
                    error_history_tmp[i] = search_error
        error.history = set(error_history_tmp)
    logger.error(f"{type(error).__name__}: {str(error)}")
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=500,
            detail=f"{type(error).__name__}: {str(error)}",
        ),
    )


@app.exception_handler(TimeOutError)
async def handle_timeout(request: Request, error: Exception) -> ORJSONResponse:
    """Timeout [504] errors handle"""
    logger.error(f"{type(error).__name__}: {str(error)}")
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=504,
            detail=f"{type(error).__name__}: {str(error)}",
        ),
    )


@router.get("/", tags=["Capabilities"])
def catalogs_root(request: Request) -> Any:
    """STAC catalogs root"""
    logger.debug("URL: %s", request.url)

    response = get_stac_catalogs(
        url=request.state.url,
        root=request.state.url_root,
        provider=request.query_params.get("provider", None),
    )

    return jsonable_encoder(response)


@router.get("/conformance", tags=["Capabilities"])
def conformance() -> Any:
    """STAC conformance"""
    logger.debug("URL: /conformance")
    response = get_stac_conformance()

    return jsonable_encoder(response)


@router.get("/extensions/oseo/json-schema/schema.json", include_in_schema=False)
def stac_extension_oseo(request: Request) -> Any:
    """STAC OGC / OpenSearch extension for EO"""
    logger.debug("URL: %s", request.url)
    response = get_stac_extension_oseo(url=request.state.url)

    return jsonable_encoder(response)


@router.get(
    "/collections/{collection_id}/items/{item_id}/download",
    tags=["Data"],
    include_in_schema=False,
)
def stac_collections_item_download(
    collection_id: str, item_id: str, request: Request
) -> StreamingResponse:
    """STAC collection item download"""
    logger.debug("URL: %s", request.url)

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    return download_stac_item_by_id_stream(
        catalogs=[collection_id], item_id=item_id, provider=provider, **arguments
    )


@router.get(
    "/collections/{collection_id}/items/{item_id}/download/{asset_filter}",
    tags=["Data"],
    include_in_schema=False,
)
def stac_collections_item_download_asset(
    collection_id: str, item_id: str, asset_filter: str, request: Request
):
    """STAC collection item asset download"""
    logger.debug("URL: %s", request.url)

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    return download_stac_item_by_id_stream(
        catalogs=[collection_id],
        item_id=item_id,
        provider=provider,
        asset=asset_filter,
        **arguments,
    )


@router.get(
    "/collections/{collection_id}/items/{item_id}",
    tags=["Data"],
    include_in_schema=False,
)
def stac_collections_item(collection_id: str, item_id: str, request: Request) -> Any:
    """STAC collection item by id"""
    logger.debug("URL: %s", request.url)

    url = request.state.url
    url_root = request.state.url_root

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    response = get_stac_item_by_id(
        url=url,
        item_id=item_id,
        root=url_root,
        catalogs=[collection_id],
        provider=provider,
        **arguments,
    )

    if response:
        return jsonable_encoder(response)
    else:
        raise HTTPException(
            status_code=404,
            detail=f"No item found matching `{item_id}` id in collection `{collection_id}`",
        )


@router.get(
    "/collections/{collection_id}/items",
    tags=["Data"],
    include_in_schema=False,
)
def stac_collections_items(request: Request, collection_id: str) -> Any:
    """STAC collections items"""
    logger.debug("URL: %s", request.url)

    base_args: Dict[str, Any] = dict(request.query_params)
    base_args["collections"] = [collection_id]

    clean = {k: v for k, v in base_args.items() if v is not None}
    try:
        search_request = SearchPostRequest.model_validate(clean)
    except pydanticValidationError as e:
        raise HTTPException(status_code=400, detail=format_pydantic_error(e)) from e

    response = search_stac_items(
        request=request,
        search_request=search_request,
        catalogs=[collection_id],
    )
    return ORJSONResponse(
        content=response, status_code=200, media_type="application/json"
    )


@router.get(
    "/collections/{collection_id}/queryables",
    tags=["Capabilities"],
    include_in_schema=False,
    response_model_exclude_none=True,
)
def list_collection_queryables(
    request: Request, collection_id: str, provider: Optional[str] = None, **kwargs: Any
) -> Any:
    """Returns the list of queryable properties for a specific collection.

    This endpoint provides a list of properties that can be used as filters when querying
    the specified collection. These properties correspond to characteristics of the data
    that can be filtered using comparison operators.

    :param request: The incoming request object.
    :type request: fastapi.Request
    :param collection_id: The identifier of the collection for which to retrieve queryable properties.
    :type collection_id: str
    :param provider: (optional) The provider for which to retrieve additional properties.
    :type provider: str
    :returns: A json object containing the list of available queryable properties for the specified collection.
    :rtype: Any
    """
    logger.debug(f"URL: {request.url}")

    queryables = StacQueryables(q_id=request.state.url, additional_properties=False)

    collection_queryables = fetch_collection_queryable_properties(
        collection_id, provider, **kwargs
    )
    for key, collection_queryable in collection_queryables.items():
        queryables[key] = collection_queryable
    queryables.properties.pop("collections")

    return jsonable_encoder(queryables)


@router.get(
    "/collections/{collection_id}",
    tags=["Capabilities"],
    include_in_schema=False,
)
def collection_by_id(collection_id: str, request: Request) -> Any:
    """STAC collection by id"""
    logger.debug("URL: %s", request.url)

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    response = get_stac_collection_by_id(
        url=request.state.url_root + "/collections",
        root=request.state.url_root,
        collection_id=collection_id,
        provider=provider,
    )

    return jsonable_encoder(response)


@router.get(
    "/collections",
    tags=["Capabilities"],
    include_in_schema=False,
)
def collections(request: Request) -> Any:
    """STAC collections

    Can be filtered using parameters: instrument, platform, platformSerialIdentifier, sensorType,
    processingLevel
    """
    logger.debug("URL: %s", request.url)

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    response = get_stac_collections(
        url=request.state.url,
        root=request.state.url_root,
        arguments=arguments,
        provider=provider,
    )

    return jsonable_encoder(response)


@router.get(
    "/catalogs/{catalogs:path}/items/{item_id}/download",
    tags=["Data"],
    include_in_schema=False,
)
def stac_catalogs_item_download(
    catalogs: str, item_id: str, request: Request
) -> StreamingResponse:
    """STAC Catalog item download"""
    logger.debug("URL: %s", request.url)

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    list_catalog = catalogs.strip("/").split("/")

    return download_stac_item_by_id_stream(
        catalogs=list_catalog, item_id=item_id, provider=provider, **arguments
    )


@router.get(
    "/catalogs/{catalogs:path}/items/{item_id}/download/{asset_filter}",
    tags=["Data"],
    include_in_schema=False,
)
def stac_catalogs_item_download_asset(
    catalogs: str, item_id: str, asset_filter: str, request: Request
):
    """STAC Catalog item asset download"""
    logger.debug("URL: %s", request.url)

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    list_catalog = catalogs.strip("/").split("/")

    return download_stac_item_by_id_stream(
        catalogs=list_catalog,
        item_id=item_id,
        provider=provider,
        asset=asset_filter,
        **arguments,
    )


@router.get(
    "/catalogs/{catalogs:path}/items/{item_id}",
    tags=["Data"],
    include_in_schema=False,
)
def stac_catalogs_item(catalogs: str, item_id: str, request: Request):
    """Fetch catalog's single features."""
    logger.debug("URL: %s", request.url)

    url = request.state.url
    url_root = request.state.url_root

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    list_catalog = catalogs.strip("/").split("/")
    response = get_stac_item_by_id(
        url=url,
        item_id=item_id,
        root=url_root,
        catalogs=list_catalog,
        provider=provider,
        **arguments,
    )

    if response:
        return jsonable_encoder(response)
    else:
        raise HTTPException(
            status_code=404,
            detail=f"No item found matching `{item_id}` id in catalog `{catalogs}`",
        )


@router.get(
    "/catalogs/{catalogs:path}/items",
    tags=["Data"],
    include_in_schema=False,
)
def stac_catalogs_items(catalogs: str, request: Request) -> Any:
    """Fetch catalog's features
    '"""
    logger.debug("URL: %s", request.url)

    base_args = dict(request.query_params)

    list_catalog = catalogs.strip("/").split("/")

    try:
        search_request = SearchPostRequest.model_validate(base_args)
    except pydanticValidationError as e:
        raise HTTPException(status_code=400, detail=format_pydantic_error(e)) from e

    response = search_stac_items(
        request=request,
        search_request=search_request,
        catalogs=list_catalog,
    )
    return jsonable_encoder(response)


@router.get(
    "/catalogs/{catalogs:path}",
    tags=["Capabilities"],
    include_in_schema=False,
)
def stac_catalogs(catalogs: str, request: Request) -> Any:
    """Describe the given catalog and list available sub-catalogs"""
    logger.debug("URL: %s", request.url)
    url = request.state.url
    url_root = request.state.url_root

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    list_catalog = catalogs.strip("/").split("/")
    response = get_stac_catalogs(
        url=url,
        root=url_root,
        catalogs=list_catalog,
        provider=provider,
    )
    return jsonable_encoder(response)


@router.get(
    "/queryables",
    tags=["Capabilities"],
    response_model_exclude_none=True,
    include_in_schema=False,
)
def list_queryables(request: Request, provider: Optional[str] = None) -> Any:
    """Returns the list of terms available for use when writing filter expressions.

    This endpoint provides a list of terms that can be used as filters when querying
    the data. These terms correspond to properties that can be filtered using comparison
    operators.

    :param request: The incoming request object.
    :type request: fastapi.Request
    :returns: A json object containing the list of available queryable terms.
    :rtype: Any
    """
    logger.debug(f"URL: {request.url}")
    query_params = request.query_params.items()
    additional_params = dict(query_params)
    additional_params.pop("provider", None)
    queryables = StacQueryables(q_id=request.state.url)
    if provider:
        queryables.properties.update(
            fetch_collection_queryable_properties(None, provider, **additional_params)
        )

    return jsonable_encoder(queryables)

@router.get(
    "/search",
    tags=["STAC"],
    include_in_schema=False,
)
def get_search(
    request: Request,
    provider: Optional[str] = None,
    collections: Optional[str] = None,
    ids: Optional[str] = None,
    bbox: Optional[str] = None,
    datetime: Optional[str] = None,
    intersects: Optional[str] = None,
    limit: Optional[int] = None,
    query: Optional[str] = None,
    page: Optional[int] = None,
    sortby: Optional[str] = None,
    crunch: Optional[str] = None,
):
    """Handler for GET /search"""
    logger.debug("URL: %s", request.state.url)
    base_args = {
        "provider": provider,
        "collections": str2list(collections),
        "ids": str2list(ids),
        "datetime": datetime,
        "bbox": str2list(bbox),
        "intersects": str2json("intersects", intersects),
        "limit": limit,
        "query": str2json("query", query),
        "page": page,
        "sortby": sortby2list(sortby),
        "crunch": crunch,
    }
    clean = {k: v for k, v in base_args.items() if v is not None}

    try:
        search_request = SearchPostRequest.model_validate(clean)
    except pydanticValidationError as e:
        raise HTTPException(status_code=400, detail=format_pydantic_error(e)) from e

    response = search_stac_items(
        request=request,
        search_request=search_request,
    )
    return ORJSONResponse(
        content=response, status_code=200, media_type="application/json"
    )


@router.post(
    "/search",
    tags=["STAC"],
    include_in_schema=False,
)
def post_search(request: Request, search_request: SearchPostRequest) -> ORJSONResponse:
    """STAC post search"""
    logger.debug("URL: %s", request.url)
    logger.debug("Body: %s", search_request)

    response = search_stac_items(
        request=request,
        search_request=search_request,
    )
    return ORJSONResponse(
        content=response, status_code=200, media_type="application/json"
    )


app.include_router(router)
