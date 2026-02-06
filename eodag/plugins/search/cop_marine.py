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
import datetime
import logging
import os
import re
from typing import TYPE_CHECKING, Any, Optional, cast
from urllib.parse import urlsplit

import boto3
import botocore
import requests
from dateutil.parser import parse as dateutil_parse
from dateutil.tz import tzutc
from dateutil.utils import today

from eodag import EOProduct
from eodag.api.product import AssetsDict
from eodag.api.search_result import SearchResult
from eodag.config import PluginConfig
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.static_stac_search import StaticStacSearch
from eodag.utils import get_bucket_name_and_prefix, get_geometry_from_various
from eodag.utils.exceptions import RequestError, UnsupportedCollection, ValidationError

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

logger = logging.getLogger("eodag.search.cop_marine")


def _get_date_from_yyyymmdd(
    date_str: str, item_key: str
) -> Optional[datetime.datetime]:
    year = date_str[:4]
    month = date_str[4:6]
    if len(date_str) > 6:
        day = date_str[6:]
    else:
        day = "1"
    try:
        date = datetime.datetime(
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


def _get_dates_from_dataset_data(
    dataset_item: dict[str, Any]
) -> Optional[dict[str, str]]:
    dates = {}
    if "start_datetime" in dataset_item["properties"]:
        dates["start"] = dataset_item["properties"]["start_datetime"]
        dates["end"] = dataset_item["properties"]["end_datetime"]
    elif "datetime" in dataset_item["properties"]:
        dates["start"] = dataset_item["properties"]["datetime"]
        dates["end"] = dataset_item["properties"]["datetime"]
    else:
        return None
    return dates


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


def _check_int_values_properties(properties: dict[str, Any]):
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
    """class that implements search for the Copernicus Marine provider

    It calls :meth:`~eodag.plugins.search.static_stac_search.StaticStacSearch.discover_collections`
    inherited from :class:`~eodag.plugins.search.static_stac_search.StaticStacSearch`
    but for the actual search a special method which fetches the urls of the available products from an S3 storage and
    filters them has been written.

    The configuration parameters are inherited from the parent and grand-parent classes. The
    :attr:`~eodag.config.PluginConfig.DiscoverMetadata.auto_discovery` parameter in the
    :attr:`~eodag.config.PluginConfig.discover_metadata` section has to be set to ``false`` and the
    :attr:`~eodag.config.PluginConfig.DiscoverQueryables.fetch_url` in the
    :attr:`~eodag.config.PluginConfig.discover_queryables` queryables section has to be set to ``null`` to
    overwrite the default config from the stac provider configuration because those functionalities
    are not available.
    """

    def __init__(self, provider: str, config: PluginConfig):
        original_metadata_mapping = copy.deepcopy(config.metadata_mapping)
        super().__init__(provider, config)
        # reset to original metadata mapping from config (changed in super class init)
        self.config.metadata_mapping = original_metadata_mapping

    def _get_collection_info(
        self, collection: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Fetch collection and associated datasets info"""

        fetch_url = cast(str, self.config.discover_collections["fetch_url"]).format(
            **self.config.__dict__
        )

        logger.debug("fetch data for collection %s", collection)
        provider_collection = self.config.products.get(collection, {}).get(
            "_collection", None
        )
        if not provider_collection:
            provider_collection = collection
        collection_url = (
            fetch_url.replace("catalog.stac.json", provider_collection)
            + "/product.stac.json"
        )
        try:
            collection_data = requests.get(collection_url).json()
        except requests.RequestException as exc:
            if exc.errno == 404:
                logger.error("product %s not found", collection)
                raise UnsupportedCollection(collection)
            logger.error("data for product %s could not be fetched", collection)
            raise RequestError.from_error(
                exc, f"data for product {collection} could not be fetched"
            ) from exc

        datasets = []
        for link in [li for li in collection_data["links"] if li["rel"] == "item"]:
            dataset_url = (
                fetch_url.replace("catalog.stac.json", provider_collection)
                + "/"
                + link["href"]
            )
            try:
                dataset_item = requests.get(dataset_url).json()
                datasets.append(dataset_item)
            except requests.RequestException:
                logger.error("data for dataset %s could not be fetched", link["title"])

        return collection_data, datasets

    def _create_product(
        self,
        collection: str,
        item_key: str,
        s3_url: str,
        dataset_item: dict[str, Any],
        collection_dict: dict[str, Any],
        use_dataset_dates: bool = False,
        product_id: Optional[str] = None,
        asset_properties: dict = {},
    ) -> Optional[EOProduct]:

        item_id = os.path.splitext(item_key.split("/")[-1])[0]
        if product_id and product_id != item_id:
            return None
        download_url = s3_url + "/" + item_key
        geometry = (
            get_geometry_from_various(**dataset_item)
            or self.config.metadata_mapping["eodag:default_geometry"]
        )
        properties = {
            "id": item_id,
            "title": item_id,
            "geometry": geometry,
            "eodag:download_link": download_url,
            "dataset": dataset_item["id"],
            # order:status set to succeeded for consistency between providers
            "order:status": "succeeded",
        }
        if use_dataset_dates:
            dates = _get_dates_from_dataset_data(dataset_item)
            if not dates:
                return None
            properties["start_datetime"] = dates["start"]
            properties["end_datetime"] = dates["end"]
        else:
            item_dates = re.findall(r"(\d{4})(0[1-9]|1[0-2])([0-3]\d)", item_id)
            if not item_dates:
                item_dates = re.findall(r"_(\d{4})(0[1-9]|1[0-2])", item_id)
            item_dates = ["".join(row) for row in item_dates]
            item_start = _get_date_from_yyyymmdd(item_dates[0], item_key)
            if not item_start:  # identified pattern was not a valid datetime
                return None
            if len(item_dates) > 2:  # start, end and created_at timestamps
                item_end = _get_date_from_yyyymmdd(item_dates[1], item_key)
            else:  # only date and created_at timestamps
                item_end = item_start
            properties["start_datetime"] = item_start.strftime("%Y-%m-%dT%H:%M:%SZ")
            properties["end_datetime"] = (item_end or item_start).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

        for key, value in collection_dict["properties"].items():
            if key not in ["id", "title", "start_datetime", "end_datetime", "datetime"]:
                properties[key] = value
        for key, value in dataset_item["properties"].items():
            if key not in ["id", "title", "start_datetime", "end_datetime", "datetime"]:
                properties[key] = value

        code_mapping = self.config.products.get(collection, {}).get(
            "code_mapping", None
        )
        if code_mapping:
            id_parts = item_id.split("_")
            if len(id_parts) > code_mapping["index"]:
                code = id_parts[code_mapping["index"]]
                if "pattern" not in code_mapping:
                    properties[code_mapping["param"]] = code
                elif re.findall(code_mapping["pattern"], code):
                    properties[code_mapping["param"]] = re.findall(
                        code_mapping["pattern"], code
                    )[0]

        _check_int_values_properties(properties)

        properties["eodag:thumbnail"] = collection_dict["assets"]["thumbnail"]["href"]
        if "omiFigure" in collection_dict["assets"]:
            properties["eodag:quicklook"] = collection_dict["assets"]["omiFigure"][
                "href"
            ]

        asset_native = {
            "title": "native",
            "href": download_url,
            "type": "application/x-netcdf",
        }
        asset_native.update(asset_properties)
        assets = {"native": asset_native}
        additional_assets = self.get_assets_from_mapping(dataset_item)
        assets.update(additional_assets)

        product = EOProduct(self.provider, properties, collection=collection)
        product.assets = AssetsDict(product, assets)
        product._normalize_bands()
        return product

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> SearchResult:
        """
        Implementation of search for the Copernicus Marine provider
        :param prep: object containing search parameterds
        :param kwargs: additional search arguments
        :returns: list of products and total number of products
        """
        limit = prep.limit
        token_value = getattr(prep, "next_page_token") or prep.page

        # only return 1 page if pagination is disabled
        if token_value is None or limit is None or int(token_value) > 1 and limit <= 0:
            result = SearchResult([])
            if prep.count:
                result.number_matched = 0
            return result

        token = int(token_value)

        collection = kwargs.get("collection", prep.collection)
        if not collection:
            raise ValidationError(
                "parameter collection is required for search with cop_marine provider"
            )
        collection_dict, datasets_items_list = self._get_collection_info(collection)
        geometry = kwargs.pop("geometry", None)
        products: list[EOProduct] = []
        start_index = limit * (token - 1) + 1
        num_total = 0
        for i, dataset_item in enumerate(datasets_items_list):
            if len(products) >= limit and not prep.count and limit > 0:
                break
            # Filter by geometry
            if "id" not in kwargs and geometry:
                dataset_geom = get_geometry_from_various(**dataset_item)
                if dataset_geom and not dataset_geom.intersects(geometry):
                    continue
            try:
                logger.debug("searching data for dataset %s", dataset_item["id"])

                # date bounds
                if "start_datetime" in kwargs:
                    start_date = dateutil_parse(kwargs["start_datetime"])
                elif "start_datetime" in dataset_item["properties"]:
                    start_date = dateutil_parse(
                        dataset_item["properties"]["start_datetime"]
                    )
                else:
                    start_date = dateutil_parse(dataset_item["properties"]["datetime"])
                if not start_date.tzinfo:
                    start_date = start_date.replace(tzinfo=tzutc())
                if "end_datetime" in kwargs:
                    end_date = dateutil_parse(kwargs["end_datetime"])
                elif "end_datetime" in dataset_item["properties"]:
                    end_date = dateutil_parse(
                        dataset_item["properties"]["end_datetime"]
                    )
                else:
                    end_date = today(tzinfo=tzutc())
                if not end_date.tzinfo:
                    end_date = end_date.replace(tzinfo=tzutc())

                # retrieve information about s3 from collection data
                s3_url = dataset_item["assets"]["native"]["href"]
            except KeyError as e:
                logger.warning(
                    f"Unable to extract info from {collection} item #{i}: {str(e)}"
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

            s3_client = _get_s3_client(endpoint_url)
            asset_properties: dict[str, Any] = {}

            if ".nc" in collection_path:
                num_total += 1
                if num_total < start_index:
                    continue

                if len(products) < limit or limit < 0:
                    asset_properties = {}
                    try:
                        object_metadata = s3_client.head_object(
                            Bucket=bucket, Key=collection_path
                        )
                        if (
                            object_metadata.get("ResponseMetadata", {}).get(
                                "HTTPStatusCode", None
                            )
                            == 200
                        ):
                            headers = object_metadata.get("ResponseMetadata", {}).get(
                                "HTTPHeaders", {}
                            )
                            # do not use 'content-type' header, always at value binary/octet-stream
                            if (
                                content_length := headers.get("content-length")
                            ) is not None:
                                asset_properties["file:size"] = int(content_length)
                            if (etag := headers.get("etag")) is not None:
                                if "-" not in etag:
                                    asset_properties["file:checksum"] = etag.strip('"')
                            if (
                                last_modified := headers.get("last-modified")
                            ) is not None:
                                try:
                                    updated = dateutil_parse(last_modified)
                                    asset_properties["updated"] = updated.strftime(
                                        "%Y-%m-%dT%H:%I:%SZ"
                                    )
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    product = self._create_product(
                        collection,
                        collection_path,
                        endpoint_url + "/" + bucket,
                        dataset_item,
                        collection_dict,
                        True,
                        kwargs.get("id"),
                        asset_properties=asset_properties,
                    )
                    if product:
                        products.append(product)
                    if product and kwargs.get("id"):
                        break
                    continue

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
                        result = SearchResult([])
                        if prep.count:
                            result.number_matched = 0
                        return result
                    else:
                        break
                elif len(s3_objects["Contents"]) == 0:
                    stop_search = True
                    break

                for obj in s3_objects["Contents"]:
                    item_key = obj["Key"]
                    item_id = os.path.splitext(item_key.split("/")[-1])[0]
                    # filter according to date(s) in item id
                    item_dates = re.findall(r"(\d{4})(0[1-9]|1[0-2])([0-3]\d)", item_id)
                    if not item_dates:
                        item_dates = re.findall(r"_(\d{4})(0[1-9]|1[0-2])", item_id)
                    item_dates = [
                        "".join(row) for row in item_dates
                    ]  # join tuples returned by findall

                    if "id" in kwargs:
                        if kwargs["id"] in obj["Key"]:
                            product = self._create_product(
                                collection,
                                obj["Key"],
                                s3_url,
                                dataset_item,
                                collection_dict,
                                not bool(item_dates),
                            )
                            if product:
                                return SearchResult([product], 1)
                        if len(s3_objects["Contents"]) > 0:
                            current_object = s3_objects["Contents"][-1]["Key"]
                            continue

                    item_start = None
                    item_end = None
                    use_dataset_dates = False
                    if item_dates:
                        item_start = _get_date_from_yyyymmdd(item_dates[0], item_key)
                        if len(item_dates) > 2:  # start, end and created_at timestamps
                            item_end = _get_date_from_yyyymmdd(item_dates[1], item_key)
                    if not item_start:
                        # no valid datetime given in id
                        use_dataset_dates = True
                        dates = _get_dates_from_dataset_data(dataset_item)
                        if dates:
                            item_start_str = dates["start"].replace("Z", "+0000")
                            item_end_str = dates["end"].replace("Z", "+0000")
                            try:
                                item_start = datetime.datetime.strptime(
                                    item_start_str, "%Y-%m-%dT%H:%M:%S.%f%z"
                                )
                                item_end = datetime.datetime.strptime(
                                    item_end_str, "%Y-%m-%dT%H:%M:%S.%f%z"
                                )
                            except ValueError:
                                item_start = datetime.datetime.strptime(
                                    item_start_str, "%Y-%m-%dT%H:%M:%S%z"
                                )
                                item_end = datetime.datetime.strptime(
                                    item_end_str, "%Y-%m-%dT%H:%M:%S%z"
                                )
                    if not item_start:
                        # no valid datetime in id and dataset data
                        continue
                    if item_start > end_date:
                        stop_search = True
                    if (
                        (start_date <= item_start <= end_date)
                        or (item_end and start_date <= item_end <= end_date)
                        or (
                            item_end and item_start < start_date and item_end > end_date
                        )
                    ):
                        num_total += 1
                        if num_total < start_index:
                            continue

                        if len(products) < limit or limit < 0:

                            # Asset properties
                            asset_properties = {}

                            last_modified_date = obj.get("LastModified")
                            if isinstance(last_modified_date, datetime.datetime):
                                asset_properties[
                                    "updated"
                                ] = last_modified_date.strftime("%Y-%m-%dT%H:%I:%SZ")

                            etag_obj: Any = obj.get("ETag")
                            if isinstance(etag_obj, str) and "-" not in etag_obj:
                                asset_properties["file:checksum"] = etag_obj.strip('"')

                            size = obj.get("Size")
                            if size is not None:
                                asset_properties["file:size"] = int(size)

                            owner_id = obj.get("Owner", {}).get("ID")
                            if owner_id is not None:
                                asset_properties["cop_marine:owner_id"] = owner_id

                            owner_displayname = obj.get("Owner", {}).get("DisplayName")
                            if owner_displayname is not None:
                                asset_properties[
                                    "cop_marine:owner_name"
                                ] = owner_displayname

                            product = self._create_product(
                                collection,
                                item_key,
                                endpoint_url + "/" + bucket,
                                dataset_item,
                                collection_dict,
                                use_dataset_dates,
                                asset_properties=asset_properties,
                            )
                            if product:
                                products.append(product)
                    current_object = item_key
                    if len(products) >= limit and not prep.count:
                        stop_search = True
                        break

        search_params = (
            kwargs
            | {"limit": prep.limit}
            | {"collection": collection}
            | {"provider": self.provider}
            | {"geometry": geometry}
            if geometry
            else {}
        )

        number_matched = num_total if prep.count else None

        formated_result = SearchResult(
            products,
            number_matched,
            search_params=search_params,
            next_page_token=str(start_index + 1),
        )
        return formated_result
