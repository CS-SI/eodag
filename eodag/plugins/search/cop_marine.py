import copy
import logging
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
from eodag.utils.exceptions import UnsupportedProductType, ValidationError

logger = logging.getLogger("eodag.search.cop_marine")


def _get_date_from_yyyymmdd(date_str: str) -> datetime:
    year = date_str[:4]
    month = date_str[4:6]
    if len(date_str) > 6:
        day = date_str[6:]
    else:
        day = 1
    return datetime(
        int(year),
        int(month),
        int(day),
        tzinfo=timezone("UTC"),
    )


class CopMarineSearch(StaticStacSearch):
    """class that implements search for the Copernicus Marine provider"""

    def __init__(self, provider: str, config: PluginConfig):
        original_metadata_mapping = copy.deepcopy(config.metadata_mapping)
        super().__init__(provider, config)
        # reset to original metadata mapping from config (changed in super class init)
        self.config.metadata_mapping = original_metadata_mapping

    def _get_product_type_info(self, product_type: str) -> List[Dict[str, Any]]:
        fetch_url = cast(
            str,
            self.config.discover_product_types["fetch_url"].format(
                **self.config.__dict__
            ),
        )
        logger.debug("fetch data for collection %s", product_type)
        collection_url = (
            fetch_url.replace("catalog.stac.json", product_type) + "/product.stac.json"
        )
        collection_data = requests.get(collection_url).json()
        if len(collection_data) == 0:
            raise UnsupportedProductType(product_type)

        datasets = []
        for link in [li for li in collection_data["links"] if li["rel"] == "item"]:
            dataset_url = (
                fetch_url.replace("catalog.stac.json", product_type)
                + "/"
                + link["href"]
            )
            try:
                dataset_data = requests.get(dataset_url).json()
                datasets.append(dataset_data)
            except requests.RequestException:
                logger.error("data for dataset %s could not be fetched", link["title"])

        return datasets

    def _get_product_by_id(
        self,
        collection_objects: Dict[str, Any],
        product_id: str,
        s3_url: str,
        product_type: str,
        dataset: str,
    ):
        for obj in collection_objects["Contents"]:
            if product_id in obj["Key"]:
                item_dates = re.findall(r"\d{8}", obj["Key"])
                return self._create_product(
                    item_dates, product_type, obj["Key"], s3_url, dataset
                )
        return None

    def _create_product(
        self,
        item_dates: List[str],
        product_type: str,
        item_key: str,
        s3_url: str,
        dataset: str,
    ) -> EOProduct:
        item_start = _get_date_from_yyyymmdd(item_dates[0])
        if len(item_dates) > 2:  # start, end and created_at timestamps
            item_end = _get_date_from_yyyymmdd(item_dates[1])
        else:  # only date and created_at timestamps
            item_end = item_start
        item_id = item_key.split("/")[-1].split(".")[0]
        download_url = s3_url + "/" + item_key
        properties = {
            "startTimeFromAscendingNode": item_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "completionTimeFromAscendingNode": item_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "id": item_id,
            "title": item_id,
            "geometry": self.config.metadata_mapping["defaultGeometry"],
            "downloadLink": download_url,
            "dataset": dataset,
        }
        assets = {
            "native": {
                "title": "native",
                "href": download_url,
                "type": "application/x-netcdf",
            }
        }
        product = EOProduct(self.provider, properties, productType=product_type)
        product.assets = AssetsDict(product, assets)
        return product

    def query(
        self,
        product_type: Optional[str] = None,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        page: int = DEFAULT_PAGE,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[EOProduct], Optional[int]]:
        """
        Implementation of search for the Copernicus Marine provider
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
        if not product_type:
            raise ValidationError(
                "parameter product type is required for search with cop_marine provider"
            )
        datasets = self._get_product_type_info(product_type)
        products = []
        start_index = items_per_page * (page - 1)
        num_total = 0
        for dataset in datasets:
            logger.debug("searching data for dataset %s", dataset["id"])
            # retrieve information about s3 from collection data
            s3_url = dataset["assets"]["native"]["href"]
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

            stop_search = False

            if "startTimeFromAscendingNode" in kwargs:
                start_date = isoparse(kwargs["startTimeFromAscendingNode"])
            elif "start_datetime" in dataset["properties"]:
                start_date = isoparse(dataset["properties"]["start_datetime"])
            else:
                start_date = isoparse(dataset["properties"]["datetime"])
            if "completionTimeFromAscendingNode" in kwargs:
                end_date = isoparse(kwargs["completionTimeFromAscendingNode"])
            elif "end_datetime" in dataset["properties"]:
                end_date = isoparse(dataset["properties"]["end_datetime"])
            else:
                end_date = today()
            current_object = None

            while not stop_search:
                # list_objects returns max 1000 objects -> use marker to get next objects
                if current_object:
                    s3_objects = s3_client.list_objects(
                        Bucket=bucket, Prefix=collection_path, Marker=current_object
                    )
                else:
                    s3_objects = s3_client.list_objects(
                        Bucket=bucket, Prefix=collection_path
                    )
                if "Contents" not in s3_objects:
                    if len(products) == 0:
                        return [], 0
                    else:
                        break

                if "id" in kwargs:
                    product = self._get_product_by_id(
                        s3_objects,
                        kwargs["id"],
                        endpoint_url + "/" + bucket,
                        product_type,
                        dataset["id"],
                    )
                    if product:
                        return [product], 1
                    current_object = s3_objects["Contents"][-1]["Key"]
                    continue

                for obj in s3_objects["Contents"]:
                    item_key = obj["Key"]
                    # filter according to date(s) in item id
                    item_dates = re.findall(r"\d{8}", item_key)
                    if not item_dates:
                        item_dates = re.findall(r"\d{6}", item_key)
                    item_start = _get_date_from_yyyymmdd(item_dates[0])
                    if item_start > end_date:
                        stop_search = True
                    if not item_dates or (start_date <= item_start <= end_date):
                        num_total += 1
                        if num_total < start_index:
                            continue
                        if len(products) < items_per_page:
                            product = self._create_product(
                                item_dates,
                                product_type,
                                item_key,
                                endpoint_url + "/" + bucket,
                                dataset["id"],
                            )
                            products.append(product)
                    current_object = item_key

        return products, num_total
