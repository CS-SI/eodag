# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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
from typing import Any, List

from eodag.api.product import EOProduct  # type: ignore
from eodag.api.product.metadata_mapping import OFFLINE_STATUS, ONLINE_STATUS
from eodag.api.search_result import RawSearchResult
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.qssearch import StacSearch

logger = logging.getLogger("eodag.search.geodes")


class GeodesSearch(StacSearch):
    """``GeodesSearch`` is an extension of :class:`~eodag.plugins.search.qssearch.StacSearch`.

    It executes a Search on given STAC API endpoint and updates assets with content listed by the plugin using
    ``eodag:download_link`` :class:`~eodag.api.product._product.EOProduct` property.

    :param provider: provider name
    :param config: It has the same Search plugin configuration as :class:`~eodag.plugins.search.qssearch.StacSearch` and
                   one additional parameter:

        * :attr:`~eodag.config.PluginConfig.s3_endpoint` (``str``): s3 endpoint if not hosted on AWS
    """

    def __init__(self, provider, config):
        super(GeodesSearch, self).__init__(provider, config)

    def _get_availability(self, products: list[EOProduct]) -> dict[str, Any]:
        """Get availability information for the products from the provider's 'fastavailability' endpoint."""
        body: dict[str, list] = {"availability": []}
        for product in products:
            download_link = product.properties.get("eodag:download_link")
            endpoint_url = product.properties.get("geodes:endpoint_url")
            if download_link and endpoint_url:
                body["availability"].append(
                    {"href": download_link, "endpointURL": endpoint_url}
                )

        url = self.config.api_endpoint.replace("api/stac/search", "fastavailability")
        prep = PreparedSearch(url=url)
        prep.query_params = body

        logger.debug("Get products availability information from %s", url)
        resp = self._request(prep)

        return resp.json()

    def _set_availability(self, products: list[EOProduct]) -> None:
        """Set availability information on the products."""
        availability_dict = self._get_availability(products)
        updated = 0

        for product in products:
            download_link = product.properties.get("eodag:download_link")

            # find matching product
            product_availability_list = [
                a
                for a in availability_dict.get("products", [])
                if a.get("id") in download_link
            ]
            if len(product_availability_list) != 1:
                continue
            product_availability = product_availability_list[0]

            # find matching asset
            asset_availability_list = [
                a.get("available")
                for a in product_availability.get("files", {})
                if a.get("checksum") in download_link
            ]
            if len(asset_availability_list) != 1:
                continue
            asset_availability = asset_availability_list[0]

            # set status
            product.properties["order:status"] = (
                ONLINE_STATUS if asset_availability else OFFLINE_STATUS
            )

            updated += 1

        if updated < len(products):
            logger.warning(
                "Could not update availability for %d out of %d products",
                len(products) - updated,
                len(products),
            )

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
    ) -> List[EOProduct]:
        """Build EOProducts from provider results"""

        # Preprocess parsable description
        for index in range(0, len(results)):
            assets = results[index].get("assets", {})
            for key in assets:
                segments = assets[key].get("description", "").split("\n")

                for segment in segments:
                    segment = segment.strip("\r\t")

                    if segment.startswith("File size") and (segment.endswith("byte")):
                        filesize = segment[10:-4].strip()
                        if filesize.isnumeric():
                            assets[key]["file:size"] = int(filesize)
                    elif segment.startswith("File size") and (
                        segment.endswith("bytes")
                    ):
                        filesize = segment[10:-5].strip()
                        if filesize.isnumeric():
                            assets[key]["file:size"] = int(filesize)
                    elif segment.startswith("Is reference:"):
                        assets[key]["geodes:reference"] = segment[14:].lower() == "true"
                    elif segment.startswith("Is online:"):
                        assets[key]["geodes:online"] = segment[11:].lower() == "true"
                    elif segment.startswith("Datatype:"):
                        assets[key]["geodes:datatype"] = segment[10:]
                    elif segment.startswith("Checksum MD5:"):
                        assets[key]["file:checksum"] = segment[14:].lower()

            results[index]["assets"] = assets

        products = super(GeodesSearch, self).normalize_results(results, **kwargs)

        self._set_availability(products)

        return products
