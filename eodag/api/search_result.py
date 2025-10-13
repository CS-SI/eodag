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
from collections import UserList
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Iterable,
    Iterator,
    Optional,
    Union,
    cast,
)

from shapely.geometry import GeometryCollection
from shapely.geometry import mapping as shapely_mapping
from shapely.geometry import shape
from typing_extensions import Doc

from eodag.api.product import EOProduct, unregistered_product_from_item
from eodag.plugins.crunch.filter_date import FilterDate
from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.plugins.crunch.filter_property import FilterProperty
from eodag.utils import GENERIC_STAC_PROVIDER, STAC_SEARCH_PLUGINS
from eodag.utils.exceptions import MisconfiguredError

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from eodag.api.core import EODataAccessGateway
    from eodag.plugins.crunch.base import Crunch
    from eodag.plugins.manager import PluginManager


logger = logging.getLogger("eodag.search_result")


class SearchResult(UserList[EOProduct]):
    """An object representing a collection of :class:`~eodag.api.product._product.EOProduct` resulting from a search.

    :param products: A list of products resulting from a search
    :param number_matched: (optional) the estimated total number of matching results

    :cvar data: List of products
    :ivar number_matched: Estimated total number of matching results
    """

    errors: Annotated[
        list[tuple[str, Exception]], Doc("Tuple of provider name, exception")
    ]

    def __init__(
        self,
        products: list[EOProduct],
        number_matched: Optional[int] = None,
        errors: Optional[list[tuple[str, Exception]]] = None,
        search_params: Optional[dict[str, Any]] = None,
        next_page_token: Optional[str] = None,
        raise_errors: Optional[bool] = False,
    ) -> None:
        super().__init__(products)
        self.number_matched = number_matched
        self.errors = errors if errors is not None else []
        self.search_params = search_params
        self.next_page_token = next_page_token
        self._dag: Optional["EODataAccessGateway"] = None
        self.raise_errors = raise_errors

    def crunch(self, cruncher: Crunch, **search_params: Any) -> SearchResult:
        """Do some crunching with the underlying EO products.

        :param cruncher: The plugin instance to use to work on the products
        :param search_params: The criteria that have been used to produce this result
        :returns: The result of the application of the crunching method to the EO products
        """
        crunched_results = cruncher.proceed(self.data, **search_params)
        return SearchResult(crunched_results)

    def filter_date(
        self, start: Optional[str] = None, end: Optional[str] = None
    ) -> SearchResult:
        """
        Apply :class:`~eodag.plugins.crunch.filter_date.FilterDate` crunch,
        check its documentation to know more.
        """
        return self.crunch(FilterDate(dict(start=start, end=end)))

    def filter_latest_intersect(
        self, geometry: Union[dict[str, Any], BaseGeometry, Any]
    ) -> SearchResult:
        """
        Apply :class:`~eodag.plugins.crunch.filter_latest_intersect.FilterLatestIntersect` crunch,
        check its documentation to know more.
        """
        return self.crunch(FilterLatestIntersect({}), geometry=geometry)

    def filter_latest_by_name(self, name_pattern: str) -> SearchResult:
        """
        Apply :class:`~eodag.plugins.crunch.filter_latest_tpl_name.FilterLatestByName` crunch,
        check its documentation to know more.
        """
        return self.crunch(FilterLatestByName(dict(name_pattern=name_pattern)))

    def filter_overlap(
        self,
        geometry: Any,
        minimum_overlap: int = 0,
        contains: bool = False,
        intersects: bool = False,
        within: bool = False,
    ) -> SearchResult:
        """
        Apply :class:`~eodag.plugins.crunch.filter_overlap.FilterOverlap` crunch,
        check its documentation to know more.
        """
        return self.crunch(
            FilterOverlap(
                dict(
                    minimum_overlap=minimum_overlap,
                    contains=contains,
                    intersects=intersects,
                    within=within,
                )
            ),
            geometry=geometry,
        )

    def filter_property(
        self, operator: str = "eq", **search_property: Any
    ) -> SearchResult:
        """
        Apply :class:`~eodag.plugins.crunch.filter_property.FilterProperty` crunch,
        check its documentation to know more.
        """
        return self.crunch(FilterProperty(dict(operator=operator, **search_property)))

    def filter_online(self) -> SearchResult:
        """
        Use cruncher :class:`~eodag.plugins.crunch.filter_property.FilterProperty`,
        filter for online products.
        """
        return self.filter_property(**{"order:status": "succeeded"})

    @staticmethod
    def from_geojson(feature_collection: dict[str, Any]) -> SearchResult:
        """Builds an :class:`~eodag.api.search_result.SearchResult` object from its representation as geojson

        :param feature_collection: A collection representing a search result.
        :returns: An eodag representation of a search result
        """

        products = [
            EOProduct.from_geojson(feature)
            for feature in feature_collection.get("features", [])
        ]
        props = feature_collection.get("metadata", {}) or {}

        eodag_search_params = props.get("eodag_search_params", {})
        if eodag_search_params and eodag_search_params.get("geometry"):
            eodag_search_params["geometry"] = shape(eodag_search_params["geometry"])

        return SearchResult(
            products=products,
            number_matched=props.get("eodag_number_matched"),
            next_page_token=props.get("eodag_next_page_token"),
            search_params=eodag_search_params or None,
            raise_errors=props.get("eodag_raise_errors"),
        )

    def as_geojson_object(self) -> dict[str, Any]:
        """GeoJSON representation of SearchResult"""

        geojson_search_params = {} | (self.search_params or {})
        # search_params shapely geometry to wkt
        if self.search_params and self.search_params.get("geometry"):
            geojson_search_params["geometry"] = shapely_mapping(
                self.search_params["geometry"]
            )

        return {
            "type": "FeatureCollection",
            "features": [product.as_dict() for product in self],
            "metadata": {
                "eodag_number_matched": self.number_matched,
                "eodag_next_page_token": self.next_page_token,
                "eodag_search_params": geojson_search_params or None,
                "eodag_raise_errors": self.raise_errors,
            },
        }

    def as_shapely_geometry_object(self) -> GeometryCollection:
        """:class:`shapely.GeometryCollection` representation of SearchResult"""
        return GeometryCollection(
            [
                shape(feature["geometry"]).buffer(0)
                for feature in self.as_geojson_object()["features"]
            ]
        )

    def as_wkt_object(self) -> str:
        """WKT representation of SearchResult"""
        return self.as_shapely_geometry_object().wkt

    @property
    def __geo_interface__(self) -> dict[str, Any]:
        """Implements the geo-interface protocol.

        See https://gist.github.com/sgillies/2217756
        """
        return self.as_geojson_object()

    def _repr_html_(self):
        total_count = f"/{self.number_matched}" if self.number_matched else ""
        return (
            f"""<table>
                <thead><tr><td style='text-align: left; color: grey;'>
                 {type(self).__name__}&ensp;({len(self)}{total_count})
                </td></tr></thead>
            """
            + "".join(
                [
                    f"""<tr><td style='text-align: left;'>
                <details><summary style='color: grey; font-family: monospace;'>
                    {i}&ensp;
                    {type(p).__name__}(id=<span style='color: black;'>{
                        p.properties["id"]
                    }</span>, provider={p.provider})
                </summary>
                {p._repr_html_()}
                </details>
                </td></tr>
                """
                    for i, p in enumerate(self)
                ]
            )
            + "</table>"
        )

    def extend(self, other: Iterable) -> None:
        """override extend method to include errors"""
        if isinstance(other, SearchResult):
            self.errors.extend(other.errors)

        return super().extend(other)

    def next_page(self, update: bool = True) -> Iterator[SearchResult]:
        """
        Retrieve and iterate over the next pages of search results, if available.

        This method uses the current search parameters and next page token to request
        additional results from the provider. If ``update`` is ``True``, the current ``SearchResult``
        instance is updated with new products and pagination information as pages are fetched.

        :param update: If ``True``, update the current ``SearchResult`` with new results.
        :returns: An iterator yielding ``SearchResult`` objects for each subsequent page.

        Example:
        >>> first_page = SearchResult([])  # result of a search
        >>> for new_results in first_page.next_page():
        ...     continue  # do something with new_results
        """

        def get_next_page(current):
            if current.search_params is None:
                current.search_params = {}
            # Update the next_page_token in the search params
            current.search_params["next_page_token"] = current.next_page_token
            # Ensure the provider is in the search params
            if "provider" in current.search_params:
                current.search_params["provider"] = current.search_params.get(
                    "provider", None
                )
            elif current.data and hasattr(current.data[-1], "provider"):
                current.search_params["provider"] = current.data[-1].provider
            search_plugins, search_kwargs = current._dag._prepare_search(
                **current.search_params
            )
            # If number_matched was provided, ensure it is passed to the next search
            if current.number_matched:
                search_kwargs["number_matched"] = current.number_matched
            for i, search_plugin in enumerate(search_plugins):
                current.search_params["next_page_token"] = current.next_page_token
                return current._dag._do_search(
                    search_plugin,
                    raise_errors=self.raise_errors,
                    **search_kwargs,
                )

        # Do not iterate if there is no next page token
        #  or if the current one returned less than the maximum number of items asked for.
        if self.next_page_token is None or (
            self.search_params
            and self.search_params.get("items_per_page")
            and len(self) < cast(int, self.search_params["items_per_page"])
        ):
            return

        new_results = get_next_page(self)
        old_results = self

        while new_results.data:
            # The products between two iterations are compared. If they
            # are actually the same product, it means the iteration failed at
            # progressing for some reason.
            if (
                old_results.data[0].properties["id"]
                == new_results.data[0].properties["id"]
            ):
                logger.warning(
                    "Iterate over pages: stop iterating since the next page "
                    "appears to have the same products as in the previous one. "
                    "This provider may not implement pagination.",
                )
                break
            if update:
                self.data += new_results.data
                self.search_params = new_results.search_params
                self.next_page_token = new_results.next_page_token
            yield new_results
            # Stop iterating if there is no next page token
            #  or if the current one returned less than the maximum number of items asked for.
            if (
                new_results.next_page_token is None
                or len(new_results) < new_results.search_params["items_per_page"]
            ):
                break
            old_results = new_results
            new_results = get_next_page(new_results)
            if not new_results:
                break
        return

    @classmethod
    def _from_stac_item(
        cls, feature: dict[str, Any], plugins_manager: PluginManager
    ) -> SearchResult:
        """Create a SearchResult from a STAC item.

        :param feature: A STAC item as a dictionary
        :param plugins_manager: The EODAG plugin manager instance
        :returns: A SearchResult containing the EOProduct(s) created from the STAC item
        """
        # Try importing from EODAG Server
        if results := _import_stac_item_from_eodag_server(feature, plugins_manager):
            return results

        # try importing from a known STAC provider
        if results := _import_stac_item_from_known_provider(feature, plugins_manager):
            return results

        # try importing from an unknown STAC provider
        return _import_stac_item_from_unknown_provider(feature, plugins_manager)


def _import_stac_item_from_eodag_server(
    feature: dict[str, Any], plugins_manager: PluginManager
) -> Optional[SearchResult]:
    """Import a STAC item from EODAG Server.

    :param feature: A STAC item as a dictionary
    :param plugins_manager: The EODAG plugin manager instance
    :returns: A SearchResult containing the EOProduct(s) created from the STAC item
    """
    provider = None
    if backends := feature["properties"].get("federation:backends"):
        provider = backends[0]
    elif providers := feature["properties"].get("providers"):
        provider = providers[0].get("name")
    if provider is not None:
        logger.debug("Trying to import STAC item from EODAG Server")
        # assets coming from a STAC provider
        assets = {
            k: v["alternate"]["origin"]
            for k, v in feature.get("assets", {}).items()
            if k not in ("thumbnail", "downloadLink", "eodag:download_link")
            and "origin" in v.get("alternate", {})
        }
        if assets:
            updated_item = {**feature, **{"assets": assets}}
        else:
            # item coming from a non-STAC provider
            updated_item = {**feature}
            download_link = (
                feature.get("assets", {})
                .get("downloadLink", {})
                .get("alternate", {})
                .get("origin", {})
                .get("href")
            ) or (
                feature.get("assets", {})
                .get("eodag:download_link", {})
                .get("alternate", {})
                .get("origin", {})
                .get("href")
            )
            if download_link:
                updated_item["assets"] = {}
                updated_item["links"] = [{"rel": "self", "href": download_link}]
            else:
                updated_item = {}
        try:
            eo_product = unregistered_product_from_item(
                updated_item, GENERIC_STAC_PROVIDER, plugins_manager
            )
        except MisconfiguredError:
            eo_product = None
        if eo_product is not None:
            eo_product.provider = provider
            eo_product._register_downloader_from_manager(plugins_manager)
            return SearchResult([eo_product])
    return None


def _import_stac_item_from_known_provider(
    feature: dict[str, Any], plugins_manager: PluginManager
) -> Optional[SearchResult]:
    """Import a STAC item from an already-configured STAC provider.

    :param feature: A STAC item as a dictionary
    :param plugins_manager: The EODAG plugin manager instance
    :returns: A SearchResult containing the EOProduct(s) created from the STAC item
    """
    item_hrefs = [f for f in feature.get("links", []) if f.get("rel") == "self"]
    item_href = item_hrefs[0]["href"] if len(item_hrefs) > 0 else None
    imported_products = SearchResult([])
    for search_plugin in plugins_manager.get_search_plugins():
        # only try STAC search plugins
        if (
            search_plugin.config.type in STAC_SEARCH_PLUGINS
            and search_plugin.provider != GENERIC_STAC_PROVIDER
            and hasattr(search_plugin, "normalize_results")
        ):
            provider_base_url = search_plugin.config.api_endpoint.removesuffix(
                "/search"
            )
            # compare the item href with the provider base URL
            if item_href and item_href.startswith(provider_base_url):
                products = search_plugin.normalize_results([feature])
                if len(products) == 0 or len(products[0].assets) == 0:
                    continue
                logger.debug(
                    "Trying to import STAC item from %s", search_plugin.provider
                )
                eo_product = products[0]

                configured_pts = [
                    k
                    for k, v in search_plugin.config.products.items()
                    if v.get("_collection") == feature.get("collection")
                ]
                if len(configured_pts) > 0:
                    eo_product.collection = configured_pts[0]
                else:
                    eo_product.collection = feature.get("collection")

                eo_product._register_downloader_from_manager(plugins_manager)
                imported_products.append(eo_product)
    if len(imported_products) > 0:
        return imported_products
    return None


def _import_stac_item_from_unknown_provider(
    feature: dict[str, Any], plugins_manager: PluginManager
) -> SearchResult:
    """Import a STAC item from an unknown STAC provider.

    :param feature: A STAC item as a dictionary
    :param plugins_manager: The EODAG plugin manager instance
    :returns: A SearchResult containing the EOProduct(s) created from the STAC item
    """
    try:
        logger.debug("Trying to import STAC item from unknown provider")
        eo_product = unregistered_product_from_item(
            feature, GENERIC_STAC_PROVIDER, plugins_manager
        )
    except MisconfiguredError:
        pass
    if eo_product is not None:
        eo_product.collection = feature.get("collection")
        eo_product._register_downloader_from_manager(plugins_manager)
        return SearchResult([eo_product])
    else:
        return SearchResult([])


class RawSearchResult(UserList[dict[str, Any]]):
    """An object representing a collection of raw/unparsed search results obtained from a provider.

    :param results: A list of raw/unparsed search results
    """

    query_params: dict[str, Any]
    collection_def_params: dict[str, Any]
    search_params: dict[str, Any]
    next_page_token: Optional[str] = None

    def __init__(self, results: list[Any]) -> None:
        super(RawSearchResult, self).__init__(results)
