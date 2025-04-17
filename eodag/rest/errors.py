# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
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
import logging
from typing import Union

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from eodag.rest.types.eodag_search import EODAGSearch
from eodag.utils.exceptions import (
    AuthenticationError,
    DownloadError,
    EodagError,
    MisconfiguredError,
    NoMatchingProductType,
    NotAvailableError,
    PluginImplementationError,
    RequestError,
    TimeOutError,
    UnsupportedProductType,
    UnsupportedProvider,
    ValidationError,
)

EODAG_DEFAULT_STATUS_CODES = {
    AuthenticationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    DownloadError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    MisconfiguredError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    PluginImplementationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    NotAvailableError: status.HTTP_404_NOT_FOUND,
    NoMatchingProductType: status.HTTP_404_NOT_FOUND,
    TimeOutError: status.HTTP_504_GATEWAY_TIMEOUT,
    UnsupportedProductType: status.HTTP_404_NOT_FOUND,
    UnsupportedProvider: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_400_BAD_REQUEST,
}

logger = logging.getLogger("eodag.rest.server")


class ResponseSearchError(Exception):
    """Represent a EODAG search error response"""

    def __init__(self, errors: list[tuple[str, Exception]]) -> None:
        self._errors = errors

    @property
    def errors(self) -> list[dict[str, Union[str, int]]]:
        """return errors as a list of dict"""
        error_list: list[dict[str, Union[str, int]]] = []
        for name, exception in self._errors:

            error_dict: dict[str, Union[str, int]] = {
                "provider": name,
                "error": exception.__class__.__name__,
            }

            if exception.args:
                error_dict["message"] = exception.args[0]

            if len(exception.args) > 1:
                error_dict["detail"] = " ".join([str(i) for i in exception.args[1:]])

            error_dict["status_code"] = EODAG_DEFAULT_STATUS_CODES.get(
                type(exception), getattr(exception, "status_code", 500)
            )

            if type(exception) in (
                MisconfiguredError,
                AuthenticationError,
                PluginImplementationError,
            ):
                logger.error("%s: %s", type(exception).__name__, str(exception))
                error_dict[
                    "message"
                ] = "Internal server error: please contact the administrator"
                error_dict.pop("detail", None)

            if type(exception) is ValidationError:
                for error_param in exception.parameters:
                    stac_param = EODAGSearch.to_stac(error_param)
                    exception.message = exception.message.replace(
                        error_param, stac_param
                    )
                error_dict["message"] = exception.message

            error_list.append(error_dict)

        return error_list

    @property
    def status_code(self) -> int:
        """get global errors status code"""
        if len(self._errors) == 1 and type(self.errors[0]["status_code"]) is int:
            return self.errors[0]["status_code"]

        return 400


async def response_search_error_handler(
    request: Request, exc: Exception
) -> ORJSONResponse:
    """Handle ResponseSearchError exceptions"""
    if not isinstance(exc, ResponseSearchError):
        return starlette_exception_handler(request, exc)

    return ORJSONResponse(
        status_code=exc.status_code,
        content={"errors": exc.errors},
    )


async def eodag_errors_handler(request: Request, exc: Exception) -> ORJSONResponse:
    """Handler for EODAG errors"""
    if not isinstance(exc, EodagError):
        return starlette_exception_handler(request, exc)

    exception_status_code = getattr(exc, "status_code", None)
    default_status_code = exception_status_code or 500
    code = EODAG_DEFAULT_STATUS_CODES.get(type(exc), default_status_code)

    detail = f"{type(exc).__name__}: {str(exc)}"

    if type(exc) in (
        MisconfiguredError,
        AuthenticationError,
        TimeOutError,
        PluginImplementationError,
    ):
        logger.error("%s: %s", type(exc).__name__, str(exc))

    if type(exc) in (
        MisconfiguredError,
        AuthenticationError,
        PluginImplementationError,
    ):
        detail = "Internal server error: please contact the administrator"

    if type(exc) is ValidationError:
        for error_param in exc.parameters:
            stac_param = EODAGSearch.to_stac(error_param)
            exc.message = exc.message.replace(error_param, stac_param)
        detail = exc.message

    return ORJSONResponse(
        status_code=code,
        content={"description": detail},
    )


def starlette_exception_handler(request: Request, error: Exception) -> ORJSONResponse:
    """Default errors handle"""
    description = (
        getattr(error, "description", None)
        or getattr(error, "detail", None)
        or str(error)
    )
    return ORJSONResponse(
        status_code=getattr(error, "status_code", 500),
        content={"description": description},
    )


def add_exception_handlers(app: FastAPI) -> None:
    """Add exception handlers to the FastAPI application.

    Args:
        app: the FastAPI application.

    Returns:
        None
    """
    app.add_exception_handler(StarletteHTTPException, starlette_exception_handler)

    app.add_exception_handler(RequestError, eodag_errors_handler)
    for exc in EODAG_DEFAULT_STATUS_CODES:
        app.add_exception_handler(exc, eodag_errors_handler)

    app.add_exception_handler(ResponseSearchError, response_search_error_handler)
