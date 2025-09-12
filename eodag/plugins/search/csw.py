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
import re
from typing import TYPE_CHECKING, Any, Optional, Union

import pyproj
from owslib.csw import CatalogueServiceWeb
from owslib.fes import (
    BBox,
    PropertyIsEqualTo,
    PropertyIsGreaterThanOrEqualTo,
    PropertyIsLessThanOrEqualTo,
    PropertyIsLike,
)
from owslib.ows import ExceptionReport
from shapely import geometry, wkt

from eodag.api.product import EOProduct
from eodag.api.product.metadata_mapping import properties_from_xml
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.base import Search
from eodag.utils import DEFAULT_PROJ
from eodag.utils.import_system import patch_owslib_requests

if TYPE_CHECKING:
    from owslib.fes import OgcExpression

    from eodag.config import PluginConfig


logger = logging.getLogger("eodag.search.csw")

SUPPORTED_REFERENCE_SCHEMES = ["WWW:DOWNLOAD-1.0-http--download"]


class CSWSearch(Search):
    """A plugin for implementing search based on OGC CSW

    :param provider: provider name
    :param config: Search plugin configuration:

        * :attr:`~eodag.config.PluginConfig.api_endpoint` (``str``) (**mandatory**): The endpoint of the
          provider's search interface
        * :attr:`~eodag.config.PluginConfig.version` (``str``): OGC Catalogue Service version; default: ``2.0.2``
        * :attr:`~eodag.config.PluginConfig.search_definition` (``dict[str, Any]``) (**mandatory**):

          * **product_type_tags** (``list[dict[str, Any]``): dict of product type tags
          * **resource_location_filter** (``str``): regex string
          * **date_tags** (``dict[str, Any]``): tags for start and end

        * :attr:`~eodag.config.PluginConfig.metadata_mapping` (``dict[str, Any]``): The search plugins of this kind can
          detect when a metadata mapping is "query-able", and get the semantics of how to format the query string
          parameter that enables to make a query on the corresponding metadata. To make a metadata query-able,
          just configure it in the metadata mapping to be a list of 2 items, the first one being the
          specification of the query string search formatting. The later is a string following the
          specification of Python string formatting, with a special behaviour added to it. For example,
          an entry in the metadata mapping of this kind::

                completionTimeFromAscendingNode:
                    - 'f=acquisition.endViewingDate:lte:{completionTimeFromAscendingNode#timestamp}'
                    - '$.properties.acquisition.endViewingDate'

          means that the search url will have a query string parameter named ``f`` with a value of
          ``acquisition.endViewingDate:lte:1543922280.0`` if the search was done with the value
          of ``completionTimeFromAscendingNode`` being ``2018-12-04T12:18:00``. What happened is that
          ``{completionTimeFromAscendingNode#timestamp}`` was replaced with the timestamp of the value
          of ``completionTimeFromAscendingNode``. This example shows all there is to know about the
          semantics of the query string formatting introduced by this plugin: any eodag search parameter
          can be referenced in the query string with an additional optional conversion function that
          is separated from it by a ``#`` (see :func:`~eodag.api.product.metadata_mapping.format_metadata` for further
          details on the available converters). Note that for the values in the
          :attr:`~eodag.config.PluginConfig.free_text_search_operations` configuration parameter follow the same rule.
          If the metadata_mapping is not a list but only a string, this means that the parameters is not queryable but
          it is included in the result obtained from the provider. The string indicates how the provider result should
          be mapped to the eodag parameter.

    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(CSWSearch, self).__init__(provider, config)
        self.catalog = None

    def clear(self) -> None:
        """Clear search context"""
        super().clear()
        self.catalog = None

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> tuple[list[EOProduct], Optional[int]]:
        """Perform a search on a OGC/CSW-like interface"""
        product_type = kwargs.get("productType")
        if product_type is None:
            return ([], 0) if prep.count else ([], None)
        auth = kwargs.get("auth")
        if auth:
            self.__init_catalog(**getattr(auth.config, "credentials", {}))
        else:
            self.__init_catalog()
        results: list[EOProduct] = []
        if self.catalog:
            provider_product_type = self.config.products[product_type]["productType"]
            for product_type_def in self.config.search_definition["product_type_tags"]:
                product_type_search_tag = product_type_def["name"]
                logger.debug(
                    "Querying <%s> tag for product type %s",
                    product_type_search_tag,
                    provider_product_type,
                )
                constraints = self.__convert_query_params(
                    product_type_def, provider_product_type, kwargs
                )
                with patch_owslib_requests(verify=True):
                    try:
                        self.catalog.getrecords2(
                            constraints=constraints, esn="full", maxrecords=10
                        )
                    except ExceptionReport:
                        import traceback as tb

                        logger.warning(
                            "Failed to query %s for product type %s : %s",
                            product_type_search_tag,
                            product_type,
                            tb.format_exc(),
                        )
                        continue
                partial_results = [
                    self.__build_product(record, product_type, **kwargs)
                    for record in self.catalog.records.values()
                ]
                logger.info(
                    "Found %s results querying %s",
                    len(partial_results),
                    product_type_search_tag,
                )
                results.extend(partial_results)
        logger.info("Found %s overall results", len(results))
        total_results = len(results) if prep.count else None
        return results, total_results

    def __init_catalog(
        self, username: Optional[str] = None, password: Optional[str] = None
    ) -> None:
        """Initializes a catalogue by performing a GetCapabilities request on the url"""
        if not self.catalog:
            api_endpoint = self.config.api_endpoint
            version = getattr(self.config, "version", "2.0.2")
            logger.debug("Initialising CSW catalog at %s", api_endpoint)
            with patch_owslib_requests(verify=True):
                try:
                    self.catalog = CatalogueServiceWeb(
                        api_endpoint,
                        version=version,
                        username=username,
                        password=password,
                    )
                except Exception as e:
                    logger.warning(
                        "Initialization of catalog failed due to error: (%s: %s)",
                        type(e),
                        e,
                    )

    def __build_product(self, rec: Any, product_type: str, **kwargs: Any) -> EOProduct:
        """Enable search results to be handled by http download plugin"""
        download_url = ""
        resource_filter = re.compile(
            self.config.search_definition.get("resource_location_filter", "")
        )
        for ref in rec.references:
            if ref["scheme"] in SUPPORTED_REFERENCE_SCHEMES:
                if resource_filter.pattern and resource_filter.search(ref["url"]):
                    download_url = ref["url"]
                else:
                    download_url = ref["url"]  # noqa
                break
        properties = properties_from_xml(rec.xml, self.config.metadata_mapping)
        if not properties["geometry"]:
            bbox = rec.bbox_wgs84
            if not bbox:
                code = "EPSG:4326"
                if rec.bbox.crs and rec.bbox.crs.code and rec.bbox.crs.code > 0:
                    code = ":".join((str(rec.bbox.crs.id), str(rec.bbox.crs.code)))
                rec_proj = pyproj.Proj(init=code)
                default_proj_as_pyproj = pyproj.Proj(DEFAULT_PROJ)
                maxx, maxy = pyproj.transform(
                    rec_proj, default_proj_as_pyproj, rec.bbox.maxx, rec.bbox.maxy
                )
                minx, miny = pyproj.transform(
                    rec_proj, default_proj_as_pyproj, rec.bbox.minx, rec.bbox.miny
                )
                bbox = (minx, miny, maxx, maxy)
            properties["geometry"] = geometry.box(*bbox)
        # Ensure the geometry property is shapely-compatible (the geometry is assumed
        # to be a wkt)
        else:
            properties["geometry"] = wkt.loads(properties["geometry"])
        return EOProduct(
            product_type,
            self.provider,
            # TODO: EOProduct has no more *args in its __init__ (search_args attribute removed)
            # Not sure why download_url was here in the first place, needs to be updated,
            # possibly by having instead 'downloadLink' in the properties
            # download_url,
            properties,
            searched_bbox=kwargs.get("footprints"),
        )

    def __convert_query_params(
        self,
        product_type_def: dict[str, Any],
        product_type: str,
        params: dict[str, Any],
    ) -> Union[list[OgcExpression], list[list[OgcExpression]]]:
        """Translates eodag search to CSW constraints using owslib constraint classes"""
        constraints: list[OgcExpression] = []
        # How the match should be performed (fuzzy, prefix, postfix or exact).
        # defaults to fuzzy
        pt_tag, matching = (
            product_type_def["name"],
            product_type_def.get("matching", "fuzzy"),
        )
        if matching == "prefix":
            constraints.append(PropertyIsLike(pt_tag, "{}%".format(product_type)))
        elif matching == "postfix":
            constraints.append(PropertyIsLike(pt_tag, "%{}".format(product_type)))
        elif matching == "exact":
            constraints.append(PropertyIsEqualTo(pt_tag, product_type))
        else:  # unknown matching is considered to be equal to 'fuzzy'
            constraints.append(PropertyIsLike(pt_tag, "%{}%".format(product_type)))

        # `footprint`
        fp = params.get("geometry")
        if fp:
            constraints.append(
                BBox([fp["lonmin"], fp["latmin"], fp["lonmax"], fp["latmax"]])
            )

        # dates
        start, end = (
            params.get("startTimeFromAscendingNode"),
            params.get("completionTimeFromAscendingNode"),
        )
        if start and "date_tags" in self.config.search_definition:
            constraints.append(
                PropertyIsGreaterThanOrEqualTo(
                    self.config.search_definition["date_tags"]["start"], start
                )
            )
        if end and "date_tags" in self.config.search_definition:
            constraints.append(
                PropertyIsLessThanOrEqualTo(
                    self.config.search_definition["date_tags"]["end"], end
                )
            )
        # [[a, b]] is interpreted as a && b while [a, b] is interpreted as a || b
        return [constraints] if len(constraints) > 1 else constraints
