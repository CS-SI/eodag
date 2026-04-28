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
from typing import TYPE_CHECKING, Annotated, Any, Iterable, Iterator, Optional, Union

import geojson
from pystac import ItemCollection
from shapely.geometry import GeometryCollection
from shapely.geometry import mapping as shapely_mapping
from shapely.geometry import shape
from typing_extensions import Doc

from eodag.api.product import EOProduct
from eodag.plugins.crunch import (
    Crunch,
    FilterDate,
    FilterLatestByName,
    FilterLatestIntersect,
    FilterOverlap,
    FilterProperty,
)
from eodag.utils import STAC_VERSION, _deprecated

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from eodag.api.core import EODataAccessGateway


logger = logging.getLogger("eodag.search_result")


class SearchResult(UserList[EOProduct]):
    """An object representing a collection of :class:`~eodag.api.product._product.EOProduct` resulting from a search.

    :param products: A list of products resulting from a search
    :param number_matched: (optional) the estimated total number of matching results
    :param errors: (optional) stored errors encountered during the search. Tuple of (provider name, exception)
    :param search_params: (optional) search parameters stored to use in pagination
    :param next_page_token: (optional) next page token value to use in pagination
    :param next_page_token_key: (optional) next page token key to use in pagination
    :param raise_errors: (optional) whether to raise errors encountered during the search

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
        next_page_token_key: Optional[str] = None,
        raise_errors: Optional[bool] = False,
    ) -> None:
        super().__init__(products)
        self.number_matched = number_matched
        self.errors = errors if errors is not None else []
        self.search_params = search_params
        self.next_page_token = next_page_token
        self.next_page_token_key = next_page_token_key
        self.raise_errors = raise_errors
        self._dag: Optional["EODataAccessGateway"] = None

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
        """Filter products by date.

        Allows to filter out products that are older than a start date (optional) or more recent than an end date
        (optional).

        Applies :class:`~eodag.plugins.crunch.filter_date.FilterDate` crunch.

        :param start: start sensing time in iso format
        :param end: end sensing time in iso format
        :returns: The result of the application of the crunching method to the EO products
        """
        return self.crunch(FilterDate(dict(start=start, end=end)))

    def filter_latest_intersect(
        self, geometry: Union[dict[str, Any], BaseGeometry, Any]
    ) -> SearchResult:
        """Filter latest products (the ones with a the highest start date) that intersect search extent.

        Applies :class:`~eodag.plugins.crunch.filter_latest_intersect.FilterLatestIntersect` crunch.

        :param geometry: geometry used as search extent.
        :returns: The result of the application of the crunching method to the EO products
        """
        return self.crunch(FilterLatestIntersect({}), geometry=geometry)

    def filter_latest_by_name(self, name_pattern: str) -> SearchResult:
        """Filter Search results to get only the latest product, based on the name of the product.

        Applies :class:`~eodag.plugins.crunch.filter_latest_tpl_name.FilterLatestByName` crunch.

        :param name_pattern: 6 digits product name pattern (tile id)
        :returns: The result of the application of the crunching method to the EO products
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
        """Filter products, retaining only those that are overlapping with the search_extent.

        Applies :class:`~eodag.plugins.crunch.filter_overlap.FilterOverlap` crunch.

        :param geometry: geometry used as search extent
        :param minimum_overlap: minimal overlap percentage
        :param contains: ``True`` if product geometry contains the search area
        :param intersects: ``True`` if product geometry intersects the search area
        :param within: ``True`` if product geometry is within the search area
        :returns: The result of the application of the crunching method to the EO products
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
        """Filter products, retaining only those whose property match criteria.

        Applies :class:`~eodag.plugins.crunch.filter_property.FilterProperty` crunch.

        :param operator: Operator used for filtering (one of :mod:`python:operator` functions ``lt,le,eq,ne,ge,...``)
        :param search_property: property key from ``product.properties``, associated to its filter value
        """
        return self.crunch(FilterProperty(dict(operator=operator, **search_property)))

    def filter_online(self) -> SearchResult:
        """Filter to only keep online products.

        Applies :class:`~eodag.plugins.crunch.filter_property.FilterProperty` crunch for ``order:status == succeeded``.

        :returns: The result of the application of the crunching method to the EO products
        """
        return self.filter_property(**{"order:status": "succeeded"})

    @classmethod
    def from_dict(
        cls,
        feature_collection: dict[str, Any],
        dag: Optional[EODataAccessGateway] = None,
    ) -> SearchResult:
        """Builds an :class:`~eodag.api.search_result.SearchResult` object from its representation as geojson

        :param feature_collection: A collection representing a search result.
        :param dag: (optional) The EODataAccessGateway instance to use for registering the products.
        :returns: An eodag representation of a search result
        """
        products: list[EOProduct] = []
        for feature in feature_collection.get("features", []):
            product = EOProduct.from_dict(feature, dag=dag)
            products.append(product)

        props = feature_collection.get("metadata", {}) or {}
        eodag_search_params = props.get("eodag:search_params", {})
        if eodag_search_params and eodag_search_params.get("geometry"):
            eodag_search_params["geometry"] = shape(eodag_search_params["geometry"])

        results = SearchResult(
            products=products,  # type: ignore
            number_matched=props.get("eodag:number_matched"),
            next_page_token=props.get("eodag:next_page_token"),
            next_page_token_key=props.get("eodag:next_page_token_key"),
            search_params=eodag_search_params or None,
            raise_errors=props.get("eodag:raise_errors"),
        )
        if dag is not None:
            results._dag = dag
        return results

    @classmethod
    def from_file(
        cls,
        filepath: str,
        dag: Optional[EODataAccessGateway] = None,
    ) -> SearchResult:
        """Builds an :class:`~eodag.api.search_result.SearchResult` object from a geojson file

        :param filepath: Path to the file containing the feature collection.
        :param dag: (optional) The EODataAccessGateway instance to use for registering the products.
        :returns: An eodag representation of a search result
        """
        with open(filepath, "r") as fh:
            feature = geojson.load(fh)

        return cls.from_dict(feature, dag=dag)

    @classmethod
    def from_pystac(
        cls,
        item_collection: ItemCollection,
        dag: Optional[EODataAccessGateway] = None,
    ) -> SearchResult:
        """Builds an :class:`~eodag.api.search_result.SearchResult` object from a pystac ItemCollection

        :param item_collection: The :class:`pystac.ItemCollection` containing the metadata of the products.
        :param dag: (optional) The EODataAccessGateway instance to use for registering the products.
        :returns: An eodag representation of a search result
        """
        features_collection = item_collection.to_dict()

        return cls.from_dict(features_collection, dag=dag)

    @staticmethod
    @_deprecated(
        reason="Please use 'SearchResult.from_dict' instead",
        version="4.1.0",
    )
    def from_geojson(feature_collection: dict[str, Any]) -> SearchResult:
        """Builds an :class:`~eodag.api.search_result.SearchResult` object from its representation as geojson

        :param feature_collection: A collection representing a search result.
        :returns: An eodag representation of a search result
        """
        return SearchResult.from_dict(feature_collection)

    def as_dict(self, skip_invalid: bool = True) -> dict[str, Any]:
        """GeoJSON representation of SearchResult

        :param skip_invalid: Whether to skip properties whose values are not valid according to the STAC specification.
        :returns: The representation of a :class:`~eodag.api.search_result.SearchResult` as a Python dict
        """

        geojson_search_params = {} | (self.search_params or {})
        # search_params shapely geometry to wkt
        if self.search_params and self.search_params.get("geometry"):
            geojson_search_params["geometry"] = shapely_mapping(
                self.search_params["geometry"]
            )

        return {
            "type": "FeatureCollection",
            "features": [
                product.as_dict(skip_invalid=skip_invalid) for product in self
            ],
            "metadata": {
                "eodag:number_matched": self.number_matched,
                "eodag:next_page_token": self.next_page_token,
                "eodag:next_page_token_key": self.next_page_token_key,
                "eodag:search_params": geojson_search_params or None,
                "eodag:raise_errors": self.raise_errors,
            },
            "links": [],
            "stac_extensions": [],
            "stac_version": STAC_VERSION,
        }

    @_deprecated(
        reason="Please use 'SearchResult.as_dict' instead",
        version="4.1.0",
    )
    def as_geojson_object(self, skip_invalid: bool = True) -> dict[str, Any]:
        """GeoJSON representation of SearchResult

        :param skip_invalid: Whether to skip properties whose values are not valid according to the STAC specification.
        :returns: The representation of a :class:`~eodag.api.search_result.SearchResult` as a Python dict
        """
        return self.as_dict(skip_invalid=skip_invalid)

    def as_shapely_geometry_object(
        self, skip_invalid: bool = True
    ) -> GeometryCollection:
        """:class:`shapely.GeometryCollection` representation of SearchResult

        :param skip_invalid: Whether to skip properties whose values are not valid according to the STAC specification.
        :returns: The representation of a :class:`~eodag.api.search_result.SearchResult` as a
                  :class:`shapely.GeometryCollection`
        """
        return GeometryCollection(
            [
                shape(feature["geometry"]).buffer(0)
                for feature in self.as_dict(skip_invalid=skip_invalid)["features"]
            ]
        )

    def as_wkt_object(self, skip_invalid: bool = True) -> str:
        """WKT representation of SearchResult

        :param skip_invalid: Whether to skip properties whose values are not valid according to the STAC specification.
        :returns: The representation of a :class:`~eodag.api.search_result.SearchResult` as a WKT string
        """
        return self.as_shapely_geometry_object(skip_invalid=skip_invalid).wkt

    def as_pystac_object(self, skip_invalid: bool = True) -> ItemCollection:
        """Pystac ItemCollection representation of SearchResult

        :param skip_invalid: Whether to skip properties whose values are not valid according to the STAC specification.
        :returns: The representation of a :class:`~eodag.api.search_result.SearchResult` as a
                  :class:`pystac.ItemCollection`
        """
        results_dict = self.as_dict(skip_invalid=skip_invalid)
        return ItemCollection.from_dict(results_dict)

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
            current.search_params["next_page_token_key"] = current.next_page_token_key
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
                # validate no needed for next pages
                search_kwargs["validate"] = False
                return current._dag._do_search(
                    search_plugin,
                    raise_errors=self.raise_errors,
                    **search_kwargs,
                )

        # Do not iterate if there is no next page token
        #  or if the current one returned less than the maximum number of items asked for.
        if self.next_page_token is None:
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
                self.next_page_token_key = new_results.next_page_token_key
            yield new_results
            # Stop iterating if there is no next page token
            #  or if the current one returned less than the maximum number of items asked for.
            if (
                new_results.next_page_token is None
                or len(new_results) < new_results.search_params["limit"]
            ):
                break
            old_results = new_results
            new_results = get_next_page(new_results)
            if not new_results:
                break
        return


class RawSearchResult(UserList[dict[str, Any]]):
    """An object representing a collection of raw/unparsed search results obtained from a provider.

    :param results: A list of raw/unparsed search results
    """

    query_params: dict[str, Any]
    collection_def_params: dict[str, Any]
    search_params: dict[str, Any]
    next_page_token: Optional[str] = None
    next_page_token_key: Optional[str] = None

    def __init__(self, results: list[Any]) -> None:
        super(RawSearchResult, self).__init__(results)
