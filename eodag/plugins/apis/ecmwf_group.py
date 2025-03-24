# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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
from typing import TYPE_CHECKING
from urllib.parse import quote_plus

import orjson

from eodag.api.product._product import EOProduct
from eodag.api.product.metadata_mapping import DEFAULT_GEOMETRY, STAGING_STATUS
from eodag.api.search_result import RawSearchResult
from eodag.plugins.apis.base import Api
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.authentication.header import HTTPHeaderAuth
from eodag.plugins.authentication.openid_connect import OIDCAuthorizationCodeFlowAuth
from eodag.plugins.authentication.token import TokenAuth
from eodag.plugins.download.http import HTTPDownload
from eodag.plugins.search.build_search_result import ECMWFSearch, ecmwf_format
from eodag.plugins.search.qssearch import QueryStringSearch
from eodag.utils.exceptions import DownloadError, NotAvailableError, ValidationError

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger("eodag.apis.ecmwf_group")


class EcmwfGroupApi(Api, ECMWFSearch, HTTPDownload, Authentication):
    """ECMWF Group API plugin"""

    def do_search(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Should perform the actual search request."""
        if "id" in kwargs and "ORDERABLE" not in kwargs["id"]:
            # id is order id (from provider, not artificially created by eodag)
            # -> create product from metadata of status request
            return self._check_id(kwargs["id"])
        return ECMWFSearch.do_search(*args, **kwargs)

    def _check_id(self, product_id: str) -> list[dict[str, Any]]:
        """Check if the id is the one of an existing job.
        If the job exists, poll it, otherwise, raise an error.

        :param product: The product to check the id for
        :param id: The id to check
        :raises: :class:`~eodag.utils.exceptions.ValidationError`
        """
        # set fake properties to make EOProduct initialization possible
        # among these properties, "title" is set to deal with error while polling
        product_base = {
            "id": product_id,
            "title": product_id,
            "geometry": DEFAULT_GEOMETRY,
        }

        product = EOProduct(self.provider, product_base)
        product.downloader = self

        # update "orderStatusLink" and potential "search_link" properties to match the id from the search request
        order_status_link = product.downloader.config.order_on_response[
            "metadata_mapping"
        ]["orderStatusLink"]
        search_link = product.downloader.config.order_on_response[
            "metadata_mapping"
        ].get("searchLink", "")
        if not isinstance(order_status_link, str) or not isinstance(search_link, str):
            return [{}]
        product.properties["orderStatusLink"] = order_status_link.format(
            orderId=product_id
        )
        formatted_search_link = search_link.format(orderId=product_id)
        search_link_dict = (
            {"searchLink": formatted_search_link} if formatted_search_link else {}
        )
        product.properties.update(search_link_dict)

        auth = product.downloader.authenticate() if product.downloader else None

        # try to poll the job corresponding to the given id
        try:
            product.downloader._order_status(product=product, auth=auth)  # type: ignore
        # when a NotAvailableError is catched, it means the product is not ready and still needs to be polled
        except NotAvailableError:
            product.properties["storageStatus"] = STAGING_STATUS
        except Exception as e:
            if (
                isinstance(e, DownloadError) or isinstance(e, ValidationError)
            ) and "order status could not be checked" in e.args[0]:
                raise ValidationError(
                    f"Item {product_id} does not exist with {self.provider}."
                ) from e
            raise ValidationError(e.args[0]) from e

        return [product.properties]


class CopEcmwfGroupApi(EcmwfGroupApi, HTTPHeaderAuth):
    """Copernicus ECMWF Group API plugin.
    Override to use the proper authentication method.
    """


class WekeoEcmwfGroupApi(EcmwfGroupApi, TokenAuth):
    """WEkEO ECMWF Group API plugin.
    Override to use the proper authentication method.
    """

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> list[EOProduct]:
        """Build :class:`~eodag.api.product._product.EOProduct` from provider result

        :param results: Raw provider result as single dict in list
        :param kwargs: Search arguments
        :returns: list of single :class:`~eodag.api.product._product.EOProduct`
        """

        if kwargs.get("id"):
            return EcmwfGroupApi.normalize_results(self, results, **kwargs)

        # formating of orderLink requires access to the productType value.
        results.data = [
            {**result, **results.product_type_def_params} for result in results
        ]

        normalized = QueryStringSearch.normalize_results(self, results, **kwargs)

        if not normalized:
            return normalized

        query_params_encoded = quote_plus(orjson.dumps(results.query_params))
        for product in normalized:
            properties = {**product.properties, **results.query_params}
            properties["_dc_qs"] = query_params_encoded
            product.properties = {ecmwf_format(k): v for k, v in properties.items()}

        return normalized

    def do_search(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        """Should perform the actual search request.

        :param args: arguments to be used in the search
        :param kwargs: keyword arguments to be used in the search
        :return: list containing the results from the provider in json format
        """
        if "id" in kwargs and "-" not in kwargs["id"]:
            # id is order id (only letters and numbers) -> create product from metadata of status request
            return self._check_id(kwargs["id"])
        return QueryStringSearch.do_search(self, *args, **kwargs)


class DedtEcmwfGroupApi(EcmwfGroupApi, OIDCAuthorizationCodeFlowAuth):
    """DEDT ECMWF Group API plugin.
    Override to use the proper authentication method.
    """

    def _check_id(self, product_id: str) -> list[dict[str, Any]]:
        """Check if the id is the one of an existing job.
        If the job exists, poll it, otherwise, raise an error.

        :param product: The product to check the id for
        :param id: The id to check
        :raises: :class:`~eodag.utils.exceptions.ValidationError`
        """
        # set fake properties to make EOProduct initialization possible
        # among these properties, "title" is set to deal with error while polling
        product_base = {
            "id": product_id,
            "title": product_id,
            "geometry": DEFAULT_GEOMETRY,
        }

        product = EOProduct(self.provider, product_base)
        product.downloader = self

        # update "orderStatusLink" and potential "search_link" properties to match the id from the search request
        order_status_link = product.downloader.config.order_on_response[
            "metadata_mapping"
        ]["orderStatusLink"]
        search_link = product.downloader.config.order_on_response[
            "metadata_mapping"
        ].get("searchLink", "")
        if not isinstance(order_status_link, str) or not isinstance(search_link, str):
            return [{}]

        base_order_status_link = "/".join(order_status_link.split("/")[:-1])
        product.properties["orderStatusLink"] = f"{base_order_status_link}/{product_id}"

        auth = product.downloader.authenticate() if product.downloader else None

        # try to poll the job corresponding to the given id
        try:
            product.downloader._order_status(product=product, auth=auth)  # type: ignore
        # when a NotAvailableError is catched, it means the product is not ready and still needs to be polled
        except NotAvailableError:
            product.properties["storageStatus"] = STAGING_STATUS
        except Exception as e:
            if (
                isinstance(e, DownloadError) or isinstance(e, ValidationError)
            ) and "order status could not be checked" in e.args[0]:
                raise ValidationError(
                    f"Item {product_id} does not exist with {self.provider}."
                ) from e
            raise ValidationError(e.args[0]) from e

        return [product.properties]
