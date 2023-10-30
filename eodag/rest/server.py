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
import io
import logging
import os
import re
import traceback
from contextlib import asynccontextmanager
from distutils import dist
from typing import List, Optional, Union

import pkg_resources
from fastapi import APIRouter as FastAPIRouter
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import ORJSONResponse
from fastapi.types import Any, Callable, DecoratedCallable
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from eodag.api.core import DEFAULT_ITEMS_PER_PAGE
from eodag.config import load_stac_api_config
from eodag.rest.utils import (
    QueryableProperty,
    Queryables,
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
from eodag.utils import parse_header, update_nested_dict
from eodag.utils.exceptions import (
    AuthenticationError,
    DownloadError,
    MisconfiguredError,
    NoMatchingProductType,
    NotAvailableError,
    RequestError,
    UnsupportedProductType,
    UnsupportedProvider,
    ValidationError,
)

logger = logging.getLogger("eodag.rest.server")
CAMEL_TO_SPACE_TITLED = re.compile(r"[:_-]|(?<=[a-z])(?=[A-Z])")


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
async def lifespan(app: FastAPI):
    """API init and tear-down"""
    eodag_api_init()
    yield


app = FastAPI(lifespan=lifespan, title="EODAG", docs_url="/api.html")

# conf from resources/stac_api.yml
stac_api_config = load_stac_api_config()


@router.get("/api", tags=["Capabilities"], include_in_schema=False)
def eodag_openapi():
    """Customized openapi"""
    logger.debug("URL: /api")
    if app.openapi_schema:
        return app.openapi_schema

    # eodag metadata
    distribution = pkg_resources.get_distribution("eodag")
    metadata_str = distribution.get_metadata(distribution.PKG_INFO)
    metadata_obj = dist.DistributionMetadata()
    metadata_obj.read_pkg_file(io.StringIO(metadata_str))

    root_catalog = get_stac_catalogs(url="", fetch_providers=False)
    stac_api_version = get_stac_api_version()

    openapi_schema = get_openapi(
        title=f"{root_catalog['title']} / eodag",
        version=getattr(metadata_obj, "version", None),
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
        + " (stac-api-spec {})".format(stac_api_version)
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
async def forward_middleware(request: Request, call_next):
    """Middleware that handles forward headers and sets request.state.url*"""

    forwarded_host = request.headers.get("x-forwarded-host", None)
    forwarded_proto = request.headers.get("x-forwarded-proto", None)

    if "forwarded" in request.headers:
        header_forwarded = parse_header(request.headers["forwarded"])
        forwarded_host = header_forwarded.get_param("host", None) or forwarded_host
        forwarded_proto = header_forwarded.get_param("proto", None) or forwarded_proto

    request.state.url_root = f"{forwarded_proto or request.url.scheme}://{forwarded_host or request.url.netloc}"
    request.state.url = f"{request.state.url_root}{request.url.path}"

    response = await call_next(request)
    return response


@app.exception_handler(StarletteHTTPException)
async def default_exception_handler(request: Request, error):
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


@app.exception_handler(NoMatchingProductType)
@app.exception_handler(UnsupportedProductType)
@app.exception_handler(UnsupportedProvider)
@app.exception_handler(ValidationError)
async def handle_invalid_usage(request: Request, error):
    """Invalid usage [400] errors handle"""
    logger.warning(traceback.format_exc())
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=400,
            detail=f"{type(error).__name__}: {str(error)}",
        ),
    )


@app.exception_handler(NotAvailableError)
async def handle_resource_not_found(request: Request, error):
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
async def handle_auth_error(request: Request, error):
    """AuthenticationError should be sent as internal server error to the client"""
    logger.error(f"{type(error).__name__}: {str(error)}")
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=500,
            detail="Internal server error: please contact the administrator",
        ),
    )


@app.exception_handler(DownloadError)
@app.exception_handler(RequestError)
async def handle_server_error(request: Request, error):
    """These errors should be sent as internal server error with details to the client"""
    logger.error(f"{type(error).__name__}: {str(error)}")
    return await default_exception_handler(
        request,
        HTTPException(
            status_code=500,
            detail=f"{type(error).__name__}: {str(error)}",
        ),
    )


@router.get("/", tags=["Capabilities"])
def catalogs_root(request: Request):
    """STAC catalogs root"""
    logger.debug(f"URL: {request.url}")

    response = get_stac_catalogs(
        url=request.state.url,
        root=request.state.url_root,
        catalogs=[],
        provider=request.query_params.get("provider", None),
    )

    return jsonable_encoder(response)


@router.get("/conformance", tags=["Capabilities"])
def conformance():
    """STAC conformance"""
    logger.debug("URL: /conformance")
    response = get_stac_conformance()

    return jsonable_encoder(response)


@router.get("/extensions/oseo/json-schema/schema.json", include_in_schema=False)
def stac_extension_oseo(request: Request):
    """STAC OGC / OpenSearch extension for EO"""
    logger.debug(f"URL: {request.url}")
    response = get_stac_extension_oseo(url=request.state.url)

    return jsonable_encoder(response)


class SearchBody(BaseModel):
    """
    class which describes the body of a search request
    """

    provider: Union[str, None] = None
    collections: Union[List[str], str]
    datetime: Union[str, None] = None
    bbox: Union[list, str, None] = None
    intersects: Union[dict, None] = None
    limit: Union[int, None] = DEFAULT_ITEMS_PER_PAGE
    page: Union[int, None] = 1
    query: Union[dict, None] = None
    ids: Union[List[str], None] = None


@router.get(
    "/collections/{collection_id}/items/{item_id}/download",
    tags=["Data"],
    include_in_schema=False,
)
def stac_collections_item_download(collection_id, item_id, request: Request):
    """STAC collection item local download"""
    logger.debug(f"URL: {request.url}")

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)
    asset_filter = arguments.pop("asset", None)

    return download_stac_item_by_id_stream(
        catalogs=[collection_id], item_id=item_id, provider=provider, asset=asset_filter
    )


@router.get(
    "/collections/{collection_id}/items/{item_id}",
    tags=["Data"],
    include_in_schema=False,
)
def stac_collections_item(collection_id, item_id, request: Request):
    """STAC collection item by id"""
    logger.debug(f"URL: {request.url}")
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
    )

    if response:
        return jsonable_encoder(response)
    else:
        raise HTTPException(
            status_code=404,
            detail="No item found matching `{}` id in collection `{}`".format(
                item_id, collection_id
            ),
        )


@router.get(
    "/collections/{collection_id}/items",
    tags=["Data"],
    include_in_schema=False,
)
def stac_collections_items(collection_id, request: Request):
    """STAC collections items"""
    logger.debug(f"URL: {request.url}")
    url = request.state.url
    url_root = request.state.url_root

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    response = search_stac_items(
        url=url,
        arguments=arguments,
        root=url_root,
        provider=provider,
        catalogs=[collection_id],
    )
    return jsonable_encoder(response)


@router.get(
    "/collections/{collection_id}/queryables",
    tags=["Capabilities"],
    include_in_schema=False,
    response_model_exclude_none=True,
)
def list_collection_queryables(
    request: Request, collection_id: str, provider: Optional[str] = None
) -> Queryables:
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
    :returns: An object containing the list of available queryable properties for the specified collection.
    :rtype: eodag.rest.utils.Queryables
    """
    logger.debug(f"URL: {request.url}")

    queryables = Queryables(q_id=request.state.url, additional_properties=False)
    conf_args = [collection_id, provider] if provider else [collection_id]

    provider_properties = set(fetch_collection_queryable_properties(*conf_args))

    for prop in provider_properties:
        titled_name = re.sub(CAMEL_TO_SPACE_TITLED, " ", prop).title()
        queryables[prop] = QueryableProperty(description=titled_name)

    return queryables


@router.get(
    "/collections/{collection_id}",
    tags=["Capabilities"],
    include_in_schema=False,
)
def collection_by_id(collection_id, request: Request):
    """STAC collection by id"""
    logger.debug(f"URL: {request.url}")
    url = request.state.url_root + "/collections"
    url_root = request.state.url_root

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    response = get_stac_collection_by_id(
        url=url,
        root=url_root,
        collection_id=collection_id,
        provider=provider,
    )

    return jsonable_encoder(response)


@router.get(
    "/collections",
    tags=["Capabilities"],
    include_in_schema=False,
)
def collections(request: Request):
    """STAC collections

    Can be filtered using parameters: instrument, platform, platformSerialIdentifier, sensorType, processingLevel
    """
    logger.debug(f"URL: {request.url}")
    url = request.state.url
    url_root = request.state.url_root

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    response = get_stac_collections(
        url=url,
        root=url_root,
        arguments=arguments,
        provider=provider,
    )

    return jsonable_encoder(response)


@router.get(
    "/catalogs/{catalogs:path}/items/{item_id}/download",
    tags=["Data"],
    include_in_schema=False,
)
def stac_catalogs_item_download(catalogs, item_id, request: Request):
    """STAC item local download"""
    logger.debug(f"URL: {request.url}")

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    catalogs = catalogs.strip("/").split("/")

    return download_stac_item_by_id_stream(
        catalogs=catalogs, item_id=item_id, provider=provider
    )


@router.get(
    "/catalogs/{catalogs:path}/items/{item_id}",
    tags=["Data"],
    include_in_schema=False,
)
def stac_catalogs_item(catalogs, item_id, request: Request):
    """Fetch catalog's single features."""
    logger.debug(f"URL: {request.url}")
    url = request.state.url
    url_root = request.state.url_root

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    catalogs = catalogs.strip("/").split("/")
    response = get_stac_item_by_id(
        url=url,
        item_id=item_id,
        root=url_root,
        catalogs=catalogs,
        provider=provider,
    )

    if response:
        return jsonable_encoder(response)
    else:
        raise HTTPException(
            status_code=404,
            detail="No item found matching `{}` id in catalog `{}`".format(
                item_id, catalogs
            ),
        )


@router.get(
    "/catalogs/{catalogs:path}/items",
    tags=["Data"],
    include_in_schema=False,
)
def stac_catalogs_items(catalogs, request: Request):
    """Fetch catalog's features
    '"""
    logger.debug(f"URL: {request.url}")
    url = request.state.url
    url_root = request.state.url_root

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    catalogs = catalogs.strip("/").split("/")

    response = search_stac_items(
        url=url,
        arguments=arguments,
        root=url_root,
        catalogs=catalogs,
        provider=provider,
    )
    return jsonable_encoder(response)


@router.get(
    "/catalogs/{catalogs:path}",
    tags=["Capabilities"],
    include_in_schema=False,
)
def stac_catalogs(catalogs, request: Request):
    """Describe the given catalog and list available sub-catalogs"""
    logger.debug(f"URL: {request.url}")
    url = request.state.url
    url_root = request.state.url_root

    arguments = dict(request.query_params)
    provider = arguments.pop("provider", None)

    catalogs = catalogs.strip("/").split("/")
    response = get_stac_catalogs(
        url=url,
        root=url_root,
        catalogs=catalogs,
        provider=provider,
    )
    return jsonable_encoder(response)


@router.get(
    "/queryables",
    tags=["Capabilities"],
    include_in_schema=False,
    response_model_exclude_none=True,
)
def list_queryables(request: Request) -> Queryables:
    """Returns the list of terms available for use when writing filter expressions.

    This endpoint provides a list of terms that can be used as filters when querying
    the data. These terms correspond to properties that can be filtered using comparison
    operators.

    :param request: The incoming request object.
    :type request: fastapi.Request
    :returns: An object containing the list of available queryable terms.
    :rtype: eodag.rest.utils.Queryables
    """
    logger.debug(f"URL: {request.url}")

    return Queryables(q_id=request.state.url)


@router.get(
    "/search",
    tags=["STAC"],
    include_in_schema=False,
)
@router.post(
    "/search",
    tags=["STAC"],
    include_in_schema=False,
)
def stac_search(request: Request, search_body: Optional[SearchBody] = None):
    """STAC collections items"""
    logger.debug(f"URL: {request.url}")
    logger.debug(f"Body: {search_body}")

    url = request.state.url
    url_root = request.state.url_root

    if search_body is None:
        body = {}
    else:
        body = vars(search_body)

    arguments = dict(request.query_params, **body)
    provider = arguments.pop("provider", None)

    response = search_stac_items(
        url=url, arguments=arguments, root=url_root, provider=provider
    )
    resp = ORJSONResponse(
        content=response, status_code=200, media_type="application/json"
    )
    return resp


app.include_router(router)
