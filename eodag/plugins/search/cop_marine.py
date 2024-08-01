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
from __future__ import annotations

import copy
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast
from urllib.parse import urlsplit

import boto3
import botocore
import requests
from dateutil.parser import isoparse
from dateutil.tz import tzutc
from dateutil.utils import today

from eodag import EOProduct
from eodag.api.product import AssetsDict
from eodag.config import PluginConfig
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.static_stac_search import StaticStacSearch
from eodag.utils import get_bucket_name_and_prefix
from eodag.utils.exceptions import UnsupportedProductType, ValidationError

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_s3.type_defs import ListObjectsOutputTypeDef

logger = logging.getLogger("eodag.search.cop_marine")


def _get_date_from_yyyymmdd(date_str: str, item_key: str) -> Optional[datetime]:
    year = date_str[:4]
    month = date_str[4:6]
    if len(date_str) > 6:
        day = date_str[6:]
    else:
        day = "1"
    try:
        date = datetime(
            int(year),
            int(month),
            int(day),
            tzinfo=tzutc(),
        )
    except ValueError:
        logger.error(f"{item_key}: {date_str} is not a valid date")
        return None
    else:
        return date


def _get_s3_client(endpoint_url: str) -> S3Client:
    s3_session = boto3.Session()
    return s3_session.client(
        "s3",
        config=botocore.config.Config(
            # Configures to use subdomain/virtual calling format.
            s3={"addressing_style": "virtual"},
            signature_version=botocore.UNSIGNED,
        ),
        endpoint_url=endpoint_url,
    )


def _check_int_values_properties(properties: Dict[str, Any]):
    # remove int values with a bit length of more than 64 from the properties
    invalid = []
    for prop, prop_value in properties.items():
        if isinstance(prop_value, int) and prop_value.bit_length() > 64:
            invalid.append(prop)
        if isinstance(prop_value, dict):
            _check_int_values_properties(prop_value)

    for inv_key in invalid:
        properties.pop(inv_key)


class CopMarineSearch(StaticStacSearch):
    """class that implements search for the Copernicus Marine provider"""

    def __init__(self, provider: str, config: PluginConfig):
        original_metadata_mapping = copy.deepcopy(config.metadata_mapping)
        super().__init__(provider, config)
        # reset to original metadata mapping from config (changed in super class init)
        self.config.metadata_mapping = original_metadata_mapping

    def _get_product_type_info(
        self, product_type: str
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Fetch product type and associated datasets info"""

        fetch_url = cast(
            str,
            self.config.discover_product_types["fetch_url"].format(
                **self.config.__dict__
            ),
        )
        logger.debug("fetch data for collection %s", product_type)
        provider_product_type = self.config.products.get(product_type, {}).get(
            "productType", None
        )
        if not provider_product_type:
            provider_product_type = product_type
        collection_url = (
            fetch_url.replace("catalog.stac.json", provider_product_type)
            + "/product.stac.json"
        )
        try:
            collection_data = requests.get(collection_url).json()
        except requests.RequestException:
            logger.error("data for product %s could not be fetched", product_type)
            raise UnsupportedProductType(product_type)

        datasets = []
        for link in [li for li in collection_data["links"] if li["rel"] == "item"]:
            dataset_url = (
                fetch_url.replace("catalog.stac.json", provider_product_type)
                + "/"
                + link["href"]
            )
            try:
                dataset_item = requests.get(dataset_url).json()
                datasets.append(dataset_item)
            except requests.RequestException:
                logger.error("data for dataset %s could not be fetched", link["title"])

        return collection_data, datasets

    def _get_product_by_id(
        self,
        collection_objects: ListObjectsOutputTypeDef,
        product_id: str,
        s3_url: str,
        product_type: str,
        dataset_item: Dict[str, Any],
        collection_dict: Dict[str, Any],
    ):
        for obj in collection_objects["Contents"]:
            if product_id in obj["Key"]:
                return self._create_product(
                    product_type, obj["Key"], s3_url, dataset_item, collection_dict
                )
        return None

    def _create_product(
        self,
        product_type: str,
        item_key: str,
        s3_url: str,
        dataset_item: Dict[str, Any],
        collection_dict: Dict[str, Any],
        use_dataset_dates: bool = False,
    ) -> Optional[EOProduct]:

        item_id = item_key.split("/")[-1].split(".")[0]
        download_url = s3_url + "/" + item_key
        properties = {
            "id": item_id,
            "title": item_id,
            "geometry": self.config.metadata_mapping["defaultGeometry"],
            "downloadLink": download_url,
            "dataset": dataset_item["id"],
        }
        if use_dataset_dates:
            if "start_datetime" in dataset_item:
                properties["startTimeFromAscendingNode"] = dataset_item[
                    "start_datetime"
                ]
                properties["completionTimeFromAscendingNode"] = dataset_item[
                    "end_datetime"
                ]
            elif "datetime" in dataset_item:
                properties["startTimeFromAscendingNode"] = dataset_item["datetime"]
                properties["completionTimeFromAscendingNode"] = dataset_item["datetime"]
        else:
            item_dates = re.findall(r"\d{8}", item_key)
            if not item_dates:
                item_dates = re.findall(r"\d{6}", item_key)
            item_start = _get_date_from_yyyymmdd(item_dates[0], item_key)
            if not item_start:  # identified pattern was not a valid datetime
                return None
            if len(item_dates) > 2:  # start, end and created_at timestamps
                item_end = _get_date_from_yyyymmdd(item_dates[1], item_key)
            else:  # only date and created_at timestamps
                item_end = item_start
            properties["startTimeFromAscendingNode"] = item_start.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            properties["completionTimeFromAscendingNode"] = (
                item_end or item_start
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

        for key, value in collection_dict["properties"].items():
            if key not in ["id", "title", "start_datetime", "end_datetime"]:
                properties[key] = value
        for key, value in dataset_item["properties"].items():
            if key not in ["id", "title", "start_datetime", "end_datetime"]:
                properties[key] = value
        _check_int_values_properties(properties)

        properties["thumbnail"] = collection_dict["assets"]["thumbnail"]["href"]
        if "omiFigure" in collection_dict["assets"]:
            properties["quicklook"] = collection_dict["assets"]["omiFigure"]["href"]
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
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> Tuple[List[EOProduct], Optional[int]]:
        """
        Implementation of search for the Copernicus Marine provider
        :param prep: object containing search parameterds
        :param kwargs: additional search arguments
        :returns: list of products and total number of products
        """
        page = prep.page
        items_per_page = prep.items_per_page

        # only return 1 page if pagination is disabled
        if page is None or items_per_page is None or page > 1 and items_per_page <= 0:
            return ([], 0) if prep.count else ([], None)

        product_type = kwargs.get("productType", prep.product_type)
        if not product_type:
            raise ValidationError(
                "parameter product type is required for search with cop_marine provider"
            )
        collection_dict, datasets_items_list = self._get_product_type_info(product_type)
        products: List[EOProduct] = []
        start_index = items_per_page * (page - 1) + 1
        num_total = 0
        for i, dataset_item in enumerate(datasets_items_list):
            try:
                logger.debug("searching data for dataset %s", dataset_item["id"])

                # date bounds
                if "startTimeFromAscendingNode" in kwargs:
                    start_date = isoparse(kwargs["startTimeFromAscendingNode"])
                elif "start_datetime" in dataset_item["properties"]:
                    start_date = isoparse(dataset_item["properties"]["start_datetime"])
                else:
                    start_date = isoparse(dataset_item["properties"]["datetime"])
                if not start_date.tzinfo:
                    start_date = start_date.replace(tzinfo=tzutc())
                if "completionTimeFromAscendingNode" in kwargs:
                    end_date = isoparse(kwargs["completionTimeFromAscendingNode"])
                elif "end_datetime" in dataset_item["properties"]:
                    end_date = isoparse(dataset_item["properties"]["end_datetime"])
                else:
                    end_date = today(tzinfo=tzutc())
                if not end_date.tzinfo:
                    end_date = end_date.replace(tzinfo=tzutc())

                # retrieve information about s3 from collection data
                s3_url = dataset_item["assets"]["native"]["href"]
            except KeyError as e:
                logger.warning(
                    f"Unable to extract info from {product_type} item #{i}: {str(e)}"
                )
                continue

            url_parts = urlsplit(s3_url)
            endpoint_url = url_parts.scheme + "://" + url_parts.hostname
            bucket, collection_path = get_bucket_name_and_prefix(s3_url, 0)
            if bucket is None or collection_path is None:
                logger.warning(
                    f"Unable to get bucket and prefix from {s3_url}, got {(bucket, collection_path)}"
                )
                continue

            if ".nc" in collection_path:
                num_total += 1
                if num_total < start_index:
                    continue
                if len(products) < items_per_page or items_per_page < 0:
                    product = self._create_product(
                        product_type,
                        collection_path,
                        endpoint_url + "/" + bucket,
                        dataset_item,
                        collection_dict,
                        True,
                    )
                    if product:
                        products.append(product)
                    continue

            s3_client = _get_s3_client(endpoint_url)
            stop_search = False
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
                    if len(products) == 0 and i == len(datasets_items_list) - 1:
                        return ([], 0) if prep.count else ([], None)
                    else:
                        break

                if "id" in kwargs:
                    product = self._get_product_by_id(
                        s3_objects,
                        kwargs["id"],
                        endpoint_url + "/" + bucket,
                        product_type,
                        dataset_item,
                        collection_dict,
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
                    item_start = _get_date_from_yyyymmdd(item_dates[0], item_key)
                    if not item_start:  # identified pattern was not a valid datetime
                        continue
                    if item_start > end_date:
                        stop_search = True
                    if not item_dates or (start_date <= item_start <= end_date):
                        num_total += 1
                        if num_total < start_index:
                            continue
                        if len(products) < items_per_page or items_per_page < 0:
                            product = self._create_product(
                                product_type,
                                item_key,
                                endpoint_url + "/" + bucket,
                                dataset_item,
                                collection_dict,
                            )
                            if product:
                                products.append(product)
                    current_object = item_key

        return products, num_total
