import copy
import hashlib
import re
from typing import Any, List, Optional, Tuple
from urllib.parse import quote_plus, unquote_plus

import copernicusmarine
import geojson

from eodag import EOProduct
from eodag.api.product.metadata_mapping import format_query_params
from eodag.config import PluginConfig
from eodag.plugins.search.static_stac_search import StaticStacSearch
from eodag.utils import DEFAULT_ITEMS_PER_PAGE, DEFAULT_PAGE


class CopMarineSearch(StaticStacSearch):
    """class that implements search for the Copernicus Marine provider"""

    def __init__(self, provider: str, config: PluginConfig):
        original_metadata_mapping = copy.deepcopy(config.metadata_mapping)
        super().__init__(provider, config)
        # reset to original metadata mapping from config (changed in super class init)
        self.config.metadata_mapping = original_metadata_mapping

    def query(
        self,
        product_type: Optional[str] = None,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        page: int = DEFAULT_PAGE,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[EOProduct], Optional[int]]:
        """
        Implementation of search for the Copernicus Marine provider using the copernicusmarine library
        :param product_type: product type for the search
        :type product_type: str
        :param items_per_page: number of items per page
        :type items_per_page: int
        :param page: page number
        :type page: int
        :param count: if the total number of records should be returned
        :type count: bool
        :param kwargs: additional search arguments
        :returns: list of products and total number of products
        :rtype: Tuple[List[EOProduct], Optional[int]]
        """
        auth = kwargs.pop("auth").authenticate()
        copernicusmarine.login(username=auth.username, password=auth.password)
        product_type = kwargs.get("productType", product_type)
        bbox = None
        if "_dc_qs" in kwargs:
            query_params = unquote_plus(unquote_plus(kwargs["_dc_qs"]))
        else:
            query_params = format_query_params(product_type, self.config, **kwargs)
            query_params["dataset_id"] = product_type
            version = re.search(r"_\d{6}", product_type)
            if version:
                query_params["dataset_version"] = version.group().replace("_", "")
                query_params["dataset_id"] = query_params["dataset_id"].replace(
                    version.group(), ""
                )
            if "bbox" in query_params:
                bbox = query_params.pop("bbox")
                query_params["minimum_longitude"] = bbox[0]
                query_params["minimum_latitude"] = bbox[1]
                query_params["maximum_longitude"] = bbox[2]
                query_params["maximum_latitude"] = bbox[3]

        ds = copernicusmarine.open_dataset(**query_params)
        products = []
        if not bbox:
            min_lon = float(ds.coords["longitude"][0])
            max_lon = float(ds.coords["longitude"][-1])
            min_lat = float(ds.coords["latitude"][0])
            max_lat = float(ds.coords["latitude"][-1])
            bbox = [min_lon, min_lat, max_lon, max_lat]
        bbox = [str(value) for value in bbox]
        for t in ds.coords["time"]:
            for v in ds.variables:
                if v not in ds.coords:
                    new_query_params = copy.deepcopy(query_params)
                    new_query_params["start_datetime"] = str(t.values)
                    new_query_params["end_datetime"] = str(t.values)
                    new_query_params["variables"] = v
                    qs = geojson.dumps(new_query_params)
                    query_hash = hashlib.sha1(str(qs).encode("UTF-8")).hexdigest()
                    product_id = "%s_%s_%s_%s" % (
                        product_type,
                        str(t.values).split("T")[0].replace("-", ""),
                        v,
                        query_hash,
                    )

                    properties = {
                        "id": product_id,
                        "title": product_id,
                        "startTimeFromAscendingNode": str(t.values),
                        "completionTimeFromAscendingNode": str(t.values),
                        "variable": v,
                        "_dc_qs": quote_plus(qs),
                        "geometry": " ".join(bbox),
                    }
                    product = EOProduct(
                        provider=self.provider,
                        productType=product_type,
                        properties=properties,
                    )
                    products.append(product)
        return products, len(products)
