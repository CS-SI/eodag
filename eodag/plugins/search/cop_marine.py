import copy
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, cast
from urllib.parse import urlsplit

import boto3
import botocore
import requests
from dateutil.parser import isoparse
from dateutil.utils import today
from pytz import timezone

from eodag import EOProduct
from eodag.api.product import AssetsDict
from eodag.config import PluginConfig
from eodag.plugins.search.static_stac_search import StaticStacSearch
from eodag.utils import DEFAULT_ITEMS_PER_PAGE, DEFAULT_PAGE
from eodag.utils.stac_reader import fetch_stac_collections


class CopMarineSearch(StaticStacSearch):
    """class that implements search for the Copernicus Marine provider"""

    def __init__(self, provider: str, config: PluginConfig):
        original_metadata_mapping = copy.deepcopy(config.metadata_mapping)
        super().__init__(provider, config)
        # reset to original metadata mapping from config (changed in super class init)
        self.config.metadata_mapping = original_metadata_mapping

    def _get_product_type_info(self, product_type: str) -> Dict[str, Any]:
        fetch_url = cast(
            str,
            self.config.discover_product_types["fetch_url"].format(
                **self.config.__dict__
            ),
        )
        collections = fetch_stac_collections(
            fetch_url,
            max_connections=self.config.max_connections,
            timeout=int(self.config.timeout),
            ssl_verify=self.config.ssl_verify,
        )
        if "item_discovery" in self.config.discover_product_types:
            for collection in collections:
                for link in collection["links"]:
                    if product_type in link["title"]:
                        collection_url = (
                            fetch_url.replace("catalog.stac.json", collection["id"])
                            + "/"
                            + product_type
                            + "/dataset.stac.json"
                        )
                        collection_data = requests.get(collection_url).json()
                        return collection_data
        return {}

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
        product_type = kwargs.get("productType", product_type)
        collection_data = self._get_product_type_info(product_type)
        s3_url = collection_data["assets"]["native"]["href"]
        url_parts = urlsplit(s3_url)
        path = url_parts.path
        endpoint_url = url_parts.scheme + "://" + url_parts.hostname
        bucket = path.split("/")[1]
        collection_path = "/".join(path.split("/")[2:])
        s3_session = boto3.Session()
        s3_client = s3_session.client(
            "s3",
            config=botocore.config.Config(
                # Configures to use subdomain/virtual calling format.
                s3={"addressing_style": "virtual"},
                signature_version=botocore.UNSIGNED,
            ),
            endpoint_url=endpoint_url,
        )
        if "startTimeFromAscendingNode" in kwargs:
            start_date = isoparse(kwargs["startTimeFromAscendingNode"])
        else:
            start_date = isoparse(collection_data["properties"]["datetime"])
        if "completionTimeFromAscendingNode" in kwargs:
            end_date = isoparse(kwargs["completionTimeFromAscendingNode"])
        else:
            end_date = today()

        products = []
        s3_objects = s3_client.list_objects(Bucket=bucket, Prefix=collection_path)
        if "Contents" not in s3_objects:
            return [], 0
        for obj in s3_objects["Contents"]:
            item_key = obj["Key"]
            item_dates = re.findall(r"\d{8}", item_key)
            start_year = item_dates[0][:4]
            start_month = item_dates[0][4:6]
            start_day = item_dates[0][6:]
            item_start = datetime(
                int(start_year),
                int(start_month),
                int(start_day),
                tzinfo=timezone("UTC"),
            )
            if not item_dates or (start_date <= item_start <= end_date):
                if len(item_dates) > 1:
                    end_year = item_dates[1][:4]
                    end_month = item_dates[1][4:6]
                    end_day = item_dates[1][6:]
                    item_end = datetime(int(end_year), int(end_month), int(end_day))
                else:
                    item_end = item_start
                id = item_key.split("/")[-1].split(".")[0]
                properties = {
                    "start_datetime": item_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end_datetime": item_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "id": id,
                    "title": id,
                    "geometry": self.config.metadata_mapping["defaultGeometry"],
                }
                assets = {
                    "native": {
                        "title": "native",
                        "href": endpoint_url + "/" + bucket + "/" + item_key,
                        "type": "application/x-netcdf",
                    }
                }
                product = EOProduct(self.provider, properties, productType=product_type)
                product.assets = AssetsDict(product, assets)
                products.append(product)

        return products, len(products)
