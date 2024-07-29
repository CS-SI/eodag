# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, https://www.csgroup.eu/
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
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import dateutil.parser
import geojson
import shapefile
from dateutil import tz
from dateutil.relativedelta import relativedelta
from jsonpath_ng.jsonpath import Child
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from eodag.api.product.metadata_mapping import (
    DEFAULT_METADATA_MAPPING,
    format_metadata,
    get_metadata_path,
)
from eodag.rest.config import Settings
from eodag.rest.utils.rfc3339 import str_to_interval
from eodag.utils import (
    DEFAULT_MISSION_START_DATE,
    deepcopy,
    dict_items_recursive_apply,
    format_dict_items,
    guess_file_type,
    jsonpath_parse_dict_items,
    string_to_jsonpath,
    update_nested_dict,
    urljoin,
)
from eodag.utils.exceptions import (
    NoMatchingProductType,
    NotAvailableError,
    RequestError,
    TimeOutError,
    ValidationError,
)
from eodag.utils.requests import fetch_json

if TYPE_CHECKING:
    from eodag.api.core import EODataAccessGateway
    from eodag.api.product import EOProduct
    from eodag.api.search_result import SearchResult


logger = logging.getLogger("eodag.rest.stac")

STAC_CATALOGS_PREFIX = "catalogs"

# fields not to put in item properties
COLLECTION_PROPERTIES = [
    "abstract",
    "instrument",
    "platform",
    "platformSerialIdentifier",
    "processingLevel",
    "sensorType",
    "md5",
    "license",
    "title",
    "missionStartDate",
    "missionEndDate",
    "keywords",
    "stacCollection",
]
IGNORED_ITEM_PROPERTIES = [
    "_id",
    "id",
    "keyword",
    "quicklook",
    "thumbnail",
    "downloadLink",
    "orderLink",
    "_dc_qs",
    "qs",
    "defaultGeometry",
    "_date",
]


class StacCommon:
    """Stac common object

    :param url: Requested URL
    :param stac_config: STAC configuration from stac.yml conf file
    :param provider: (optional) Chosen provider
    :param eodag_api: EODAG python API instance
    :param root: (optional) API root
    """

    def __init__(
        self,
        url: str,
        stac_config: Dict[str, Any],
        provider: Optional[str],
        eodag_api: EODataAccessGateway,
        root: str = "/",
    ) -> None:
        self.url = url.rstrip("/") if len(url) > 1 else url
        self.stac_config = stac_config
        self.provider = provider
        self.eodag_api = eodag_api
        self.root = root.rstrip("/") if len(root) > 1 else root

        self.data: Dict[str, Any] = {}

    def update_data(self, data: Dict[str, Any]) -> None:
        """Updates data using given input STAC dict data

        :param data: Catalog data (parsed STAC dict)
        """
        self.data.update(data)

        # bbox: str to float
        if (
            "extent" in self.data.keys()
            and "spatial" in self.data["extent"].keys()
            and "bbox" in self.data["extent"]["spatial"].keys()
        ):
            for i, bbox in enumerate(self.data["extent"]["spatial"]["bbox"]):
                self.data["extent"]["spatial"]["bbox"][i] = [float(x) for x in bbox]

        def apply_method_none(_: str, v: str) -> Optional[str]:
            """ "None" values to None"""
            return None if v == "None" else v

        self.data = dict_items_recursive_apply(self.data, apply_method_none)

        def apply_method_ids(k, v):
            """ids and titles as str"""
            return str(v) if k in ["title", "id"] else v

        self.data = dict_items_recursive_apply(self.data, apply_method_ids)

        # empty stac_extensions: "" to []
        if not self.data.get("stac_extensions", True):
            self.data["stac_extensions"] = []

    @staticmethod
    def get_stac_extension(
        url: str, stac_config: Dict[str, Any], extension: str, **kwargs: Any
    ) -> Dict[str, str]:
        """Parse STAC extension from config and return as dict

        :param url: Requested URL
        :param stac_config: STAC configuration from stac.yml conf file
        :param extension: Extension name
        :param kwargs: Additional variables needed for parsing extension
        :returns: STAC extension as dictionnary
        """
        extension_model = deepcopy(stac_config).get("extensions", {}).get(extension, {})

        # parse f-strings
        format_args = deepcopy(stac_config)
        format_args["extension"] = {
            "url": url,
            "properties": kwargs.get("properties", {}),
        }
        return format_dict_items(extension_model, **format_args)

    def get_provider_dict(self, provider: str) -> Dict[str, Any]:
        """Generate STAC provider dict"""
        provider_config = next(
            p
            for p in self.eodag_api.providers_config.values()
            if provider in [p.name, getattr(p, "group", None)]
        )
        return {
            "name": getattr(provider_config, "group", provider_config.name),
            "description": getattr(provider_config, "description", None),
            "roles": getattr(provider_config, "roles", None),
            "url": getattr(provider_config, "url", None),
            "priority": getattr(provider_config, "priority", None),
        }


class StacItem(StacCommon):
    """Stac item object

    :param url: Requested URL
    :param stac_config: STAC configuration from stac.yml conf file
    :param provider: (optional) Chosen provider
    :param eodag_api: EODAG python API instance
    :param root: (optional) API root
    """

    def __init__(
        self,
        url: str,
        stac_config: Dict[str, Any],
        provider: Optional[str],
        eodag_api: EODataAccessGateway,
        root: str = "/",
    ) -> None:
        super(StacItem, self).__init__(
            url=url,
            stac_config=stac_config,
            provider=provider,
            eodag_api=eodag_api,
            root=root,
        )

    def __get_item_list(
        self, search_results: SearchResult, catalog: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build STAC items list from EODAG search results

        :param search_results: EODAG search results
        :param catalog: STAC catalog dict used for parsing item metadata
        :returns: STAC item dicts list
        """
        if len(search_results) <= 0:
            return []

        item_model = self.__filter_item_model_properties(
            self.stac_config["item"], str(search_results[0].product_type)
        )

        # check if some items need to be converted
        need_conversion: Dict[str, Any] = {}
        for k, v in item_model["properties"].items():
            if isinstance(v, str):
                conversion, item_model["properties"][k] = get_metadata_path(
                    item_model["properties"][k]
                )
                if conversion is not None:
                    need_conversion[k] = conversion
                    # convert str to jsonpath if needed
                    item_model["properties"][k] = string_to_jsonpath(
                        k, item_model["properties"][k]
                    )

        item_props = [
            p.right.fields[0]
            for p in item_model["properties"].values()
            if isinstance(p, Child)
        ]
        ignored_props = COLLECTION_PROPERTIES + item_props + IGNORED_ITEM_PROPERTIES

        item_list: List[Dict[str, Any]] = []
        for product in search_results:
            product_dict = deepcopy(product.__dict__)

            product_item: Dict[str, Any] = jsonpath_parse_dict_items(
                item_model,
                {
                    "product": product_dict,
                    "providers": [self.get_provider_dict(product.provider)],
                },
            )

            # add additional item props
            for p in set(product.properties) - set(ignored_props):
                prefix = getattr(
                    self.eodag_api.providers_config[product.provider],
                    "group",
                    product.provider,
                )
                key = p if ":" in p else f"{prefix}:{p}"
                product_item["properties"][key] = product.properties[p]

            # parse download link
            downloadlink_href = (
                f"{catalog['url']}/items/{product.properties['id']}/download"
            )
            _dc_qs = product.properties.get("_dc_qs")
            url_parts = urlparse(downloadlink_href)
            query_dict = parse_qs(url_parts.query)
            without_arg_url = (
                f"{url_parts.scheme}://{url_parts.netloc}{url_parts.path}"
                if url_parts.scheme
                else f"{url_parts.netloc}{url_parts.path}"
            )
            # add provider to query-args
            p_config = self.eodag_api.providers_config[product.provider]
            query_dict.update(provider=[getattr(p_config, "group", p_config.name)])
            # add datacube query-string to query-args
            if _dc_qs:
                query_dict.update(_dc_qs=[_dc_qs])
            if query_dict:
                downloadlink_href = (
                    f"{without_arg_url}?{urlencode(query_dict, doseq=True)}"
                )

            # generate STAC assets
            product_item["assets"] = self._get_assets(
                product, downloadlink_href, without_arg_url, query_dict, _dc_qs
            )

            # apply conversion if needed
            for prop_key, prop_val in need_conversion.items():
                conv_func, conv_args = prop_val
                # colon `:` in key breaks format() method, hide it
                formatable_prop_key = prop_key.replace(":", "")
                if conv_args is not None:
                    product_item["properties"][prop_key] = format_metadata(
                        "{%s#%s(%s)}" % (formatable_prop_key, conv_func, conv_args),
                        **{formatable_prop_key: product_item["properties"][prop_key]},
                    )
                else:
                    product_item["properties"][prop_key] = format_metadata(
                        "{%s#%s}" % (formatable_prop_key, conv_func),
                        **{formatable_prop_key: product_item["properties"][prop_key]},
                    )

            # parse f-strings
            format_args = deepcopy(self.stac_config)
            format_args["catalog"] = catalog
            format_args["item"] = product_item
            product_item = format_dict_items(product_item, **format_args)
            product_item["bbox"] = [float(i) for i in product_item["bbox"]]

            # transform shapely geometry to geojson
            product_item["geometry"] = geojson.loads(
                geojson.dumps(product_item["geometry"])
            )

            # remove empty properties
            product_item = self.__filter_item_properties_values(product_item)

            # update item link with datacube query-string
            if _dc_qs or self.provider:
                url_parts = urlparse(str(product_item["links"][0]["href"]))
                without_arg_url = (
                    f"{url_parts.scheme}://{url_parts.netloc}{url_parts.path}"
                    if url_parts.scheme
                    else f"{url_parts.netloc}{url_parts.path}"
                )
                product_item["links"][0][
                    "href"
                ] = f"{without_arg_url}?{urlencode(query_dict, doseq=True)}"

            item_list.append(product_item)

        return item_list

    def _get_assets(
        self,
        product: EOProduct,
        downloadlink_href: str,
        without_arg_url: str,
        query_dict: Optional[Dict[str, Any]] = None,
        _dc_qs: Optional[str] = None,
    ) -> Dict[str, Any]:
        assets: Dict[str, Any] = {}
        settings = Settings.from_environment()

        if _dc_qs:
            parsed = urlparse(product.remote_location)
            fragments = parsed.fragment.split("?")
            parsed = parsed._replace(fragment=f"{fragments[0]}?_dc_qs={_dc_qs}")
            origin_href = urlunparse(parsed)
        else:
            origin_href = product.remote_location

        # update download link with up-to-date query-args
        assets["downloadLink"] = {
            "title": "Download link",
            "href": downloadlink_href,
            "type": "application/zip",
        }

        if not origin_href.startswith(tuple(settings.origin_url_blacklist)):
            assets["downloadLink"]["alternate"] = {
                "origin": {
                    "title": "Origin asset link",
                    "href": origin_href,
                }
            }

        if "storageStatus" in product.properties:
            assets["downloadLink"]["storage:tier"] = product.properties["storageStatus"]

        # move origin asset urls to alternate links and replace with eodag-server ones
        if product.assets:
            origin_assets = product.assets.as_dict()
            # replace origin asset urls with eodag-server ones
            for asset_key, asset_value in origin_assets.items():
                # use origin asset as default
                assets[asset_key] = asset_value
                # origin assets as alternate link
                if not asset_value["href"].startswith(
                    tuple(settings.origin_url_blacklist)
                ):
                    assets[asset_key]["alternate"] = {
                        "origin": {
                            "title": "Origin asset link",
                            "href": asset_value["href"],
                        }
                    }
                # use server-mode assets download links
                asset_value["href"] = without_arg_url
                if query_dict:
                    assets[asset_key][
                        "href"
                    ] += f"/{asset_key}?{urlencode(query_dict, doseq=True)}"
                else:
                    assets[asset_key]["href"] += f"/{asset_key}"
                if asset_type := asset_value.get("type", None):
                    assets[asset_key]["type"] = asset_type
                    if origin := assets[asset_key].get("alternate", {}).get("origin"):
                        origin["type"] = asset_type

        if thumbnail_url := product.properties.get(
            "quicklook", product.properties.get("thumbnail", None)
        ):
            assets["thumbnail"] = {
                "title": "Thumbnail",
                "href": thumbnail_url,
                "role": "thumbnail",
            }
            if mime_type := guess_file_type(thumbnail_url):
                assets["thumbnail"]["type"] = mime_type
        return assets

    def get_stac_items(
        self,
        search_results: SearchResult,
        total: int,
        catalog: Dict[str, Any],
        next_link: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build STAC items from EODAG search results

        :param search_results: EODAG search results
        :param catalog: STAC catalog dict used for parsing item metadata
        :returns: Items dictionnary
        """
        items_model = deepcopy(self.stac_config["items"])

        if "?" in self.url:
            # search endpoint: use page url as self link
            for i, _ in enumerate(items_model["links"]):
                if items_model["links"][i]["rel"] == "self":
                    items_model["links"][i]["href"] = catalog["url"]

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # parse jsonpath
        items = jsonpath_parse_dict_items(
            items_model,
            {
                "numberMatched": total,
                "numberReturned": len(search_results),
                "timeStamp": timestamp,
            },
        )
        # parse f-strings
        format_args = deepcopy(self.stac_config)
        format_args["catalog"] = catalog
        items = format_dict_items(items, **format_args)

        if next_link:
            items["links"].append(next_link)

        # provide static catalog to build features
        if "search?" in catalog["url"]:
            catalog["url"] = os.path.join(
                catalog["url"].split("search?")[0],
                "collections",
                catalog["id"],
            )
        else:
            catalog["url"] = catalog["url"].split("?")[0]
        items["features"] = self.__get_item_list(search_results, catalog)

        self.update_data(items)
        return self.data

    def __filter_item_model_properties(
        self, item_model: Dict[str, Any], product_type: str
    ) -> Dict[str, Any]:
        """Filter item model depending on product type metadata and its extensions.
        Removes not needed parameters, and adds supplementary ones as
        part of oseo extension.

        :param item_model: Item model from stac_config
        :param product_type: Product type
        :returns: Filtered item model
        """
        try:
            product_type_dict = [
                pt
                for pt in self.eodag_api.list_product_types(
                    provider=self.provider, fetch_providers=False
                )
                if pt["ID"] == product_type
                or ("alias" in pt and pt["alias"] == product_type)
            ][0]
        except IndexError as e:
            raise NoMatchingProductType(
                f"Product type {product_type} not available for {self.provider}"
            ) from e

        result_item_model = deepcopy(item_model)
        result_item_model["stac_extensions"] = list(
            self.stac_config["stac_extensions"].values()
        )

        # build jsonpath for eodag product default properties and adapt path
        eodag_properties_dict = {
            k: string_to_jsonpath(k, v.replace("$.", "$.product."))
            for k, v in DEFAULT_METADATA_MAPPING.items()
            if "$.properties." in v
        }
        # add missing properties as oseo:missingProperty
        for k, v in eodag_properties_dict.items():
            if (
                v not in result_item_model["properties"].values()
                and k not in self.stac_config["metadata_ignore"]
                and not any(
                    k in str(prop) for prop in result_item_model["properties"].values()
                )
            ):
                result_item_model["properties"]["oseo:" + k] = string_to_jsonpath(k, v)

        # Filter out unneeded extensions
        if product_type_dict.get("sensorType", "RADAR") != "RADAR":
            result_item_model["stac_extensions"].remove(
                self.stac_config["stac_extensions"]["sar"]
            )

        # Filter out unneeded properties
        extensions_prefixes = [
            k
            for k, v in self.stac_config["stac_extensions"].items()
            if v in result_item_model["stac_extensions"]
        ]
        for k, v in item_model["properties"].items():
            # remove key if extension not in stac_extensions
            if ":" in k and k.split(":")[0] not in extensions_prefixes:
                result_item_model["properties"].pop(k, None)

        return result_item_model

    def __filter_item_properties_values(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Removes empty properties, unused extensions, and add missing extensions

        :param item: STAC item data
        :returns: Filtered item model
        """
        all_extensions_dict: Dict[str, str] = deepcopy(
            self.stac_config["stac_extensions"]
        )
        # parse f-strings with root
        all_extensions_dict = format_dict_items(
            all_extensions_dict, **{"catalog": {"root": self.root}}
        )

        item["stac_extensions"] = []
        # dict to list of keys to permit pop() while iterating
        for k in list(item["properties"]):
            extension_prefix: str = k.split(":")[0]

            if item["properties"][k] is None:
                item["properties"].pop(k, None)
            # feed found extensions list
            elif (
                extension_prefix in all_extensions_dict.keys()
                and all_extensions_dict[extension_prefix] not in item["stac_extensions"]
            ):
                # append path from item extensions
                item["stac_extensions"].append(all_extensions_dict[extension_prefix])

        return item

    def get_stac_item_from_product(self, product: EOProduct) -> Dict[str, Any]:
        """Build STAC item from EODAG product

        :param product: EODAG product
        :returns: STAC item
        """
        product_type = str(product.product_type)

        item_model = self.__filter_item_model_properties(
            self.stac_config["item"], product_type
        )

        catalog = StacCatalog(
            url=self.url.split("/items")[0],
            stac_config=self.stac_config,
            root=self.root,
            provider=self.provider,
            eodag_api=self.eodag_api,
            catalogs=[product_type],
        )

        product_dict = deepcopy(product.__dict__)
        product_dict["assets"] = product.assets.as_dict()

        # parse jsonpath
        product_item = jsonpath_parse_dict_items(
            item_model,
            {
                "product": product_dict,
                "providers": [self.get_provider_dict(product.provider)],
            },
        )
        # parse f-strings
        format_args = deepcopy(self.stac_config)
        format_args["catalog"] = {
            **catalog.data,
            **{"url": catalog.url, "root": catalog.root},
        }
        format_args["item"] = product_item
        product_item = format_dict_items(product_item, **format_args)
        product_item["bbox"] = [float(i) for i in product_item["bbox"]]

        # remove empty properties
        product_item = self.__filter_item_properties_values(product_item)

        self.update_data(product_item)
        return self.data


class StacCollection(StacCommon):
    """Stac collection object

    :param url: Requested URL
    :param stac_config: STAC configuration from stac.yml conf file
    :param provider: (optional) Chosen provider
    :param eodag_api: EODAG python API instance
    :param root: (optional) API root
    """

    # External STAC collections
    ext_stac_collections: Dict[str, Dict[str, Any]] = dict()

    @classmethod
    def fetch_external_stac_collections(cls, eodag_api: EODataAccessGateway) -> None:
        """Load external STAC collections

        :param eodag_api: EODAG python API instance
        """
        list_product_types = eodag_api.list_product_types(fetch_providers=False)
        for product_type in list_product_types:
            ext_stac_collection_path = product_type.get("stacCollection")
            if not ext_stac_collection_path:
                continue
            logger.info(f"Fetching external STAC collection for {product_type['ID']}")

            try:
                ext_stac_collection = fetch_json(ext_stac_collection_path)
            except (RequestError, TimeOutError) as e:
                logger.debug(e)
                logger.warning(
                    f"Could not read remote external STAC collection from {ext_stac_collection_path}",
                )
                ext_stac_collection = {}

            cls.ext_stac_collections[product_type["ID"]] = ext_stac_collection

    def __init__(
        self,
        url: str,
        stac_config: Dict[str, Any],
        provider: Optional[str],
        eodag_api: EODataAccessGateway,
        root: str = "/",
    ) -> None:
        super(StacCollection, self).__init__(
            url=url,
            stac_config=stac_config,
            provider=provider,
            eodag_api=eodag_api,
            root=root,
        )

    def __list_product_type_providers(self, product_type: Dict[str, Any]) -> List[str]:
        """Retrieve a list of providers for a given product type.

        :param product_type: Dictionary containing information about the product type.
        :return: A list of provider names.
        """
        if self.provider:
            return [self.provider]

        return [
            plugin.provider
            for plugin in self.eodag_api._plugins_manager.get_search_plugins(
                product_type=product_type.get("_id", product_type["ID"])
            )
        ]

    def __generate_stac_collection(
        self, collection_model: Any, product_type: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a STAC collection dictionary for a given product type.

        :param collection_model: The base model for the STAC collection.
        :param product_type: Dictionary containing information about the product type.
        :return: A dictionary representing the STAC collection for the given product type.
        """
        providers = self.__list_product_type_providers(product_type)

        providers_dict: Dict[str, Dict[str, Any]] = {}
        for provider in providers:
            p_dict = self.get_provider_dict(provider)
            providers_dict.setdefault(p_dict["name"], p_dict)
        providers_list = list(providers_dict.values())

        # parse jsonpath
        product_type_collection = jsonpath_parse_dict_items(
            collection_model,
            {
                "product_type": product_type,
                "providers": providers_list,
            },
        )
        # override EODAG's collection with the external collection
        ext_stac_collection = deepcopy(
            self.ext_stac_collections.get(product_type["ID"], {})
        )

        # update links (keep eodag links as defaults)
        ext_stac_collection.setdefault("links", {})
        for link in product_type_collection["links"]:
            ext_stac_collection["links"] = [
                x for x in ext_stac_collection["links"] if x["rel"] != link["rel"]
            ]
            ext_stac_collection["links"].append(link)

        # merge "keywords" lists
        if "keywords" in ext_stac_collection:
            try:
                ext_stac_collection["keywords"] = [
                    k
                    for k in set(
                        ext_stac_collection["keywords"]
                        + product_type_collection["keywords"]
                    )
                    if k is not None
                ]
            except TypeError as e:
                logger.warning(
                    f"Could not merge keywords from external collection for {product_type['ID']}: {str(e)}"
                )
                logger.debug(
                    f"External collection keywords: {str(ext_stac_collection['keywords'])}, ",
                    f"Product type keywords: {str(product_type_collection['keywords'])}",
                )

        # merge providers
        if "providers" in ext_stac_collection:
            ext_stac_collection["providers"] += product_type_collection["providers"]

        product_type_collection.update(ext_stac_collection)

        # parse f-strings
        format_args = deepcopy(self.stac_config)
        format_args["collection"] = {
            **product_type_collection,
            **{
                "url": self.url
                if self.url.endswith(product_type["ID"])
                else f"{self.url}/{product_type['ID']}",
                "root": self.root,
            },
        }
        product_type_collection = format_dict_items(
            product_type_collection, **format_args
        )

        return product_type_collection

    def get_collection_list(
        self,
        collection: Optional[str] = None,
        q: Optional[str] = None,
        platform: Optional[str] = None,
        instrument: Optional[str] = None,
        constellation: Optional[str] = None,
        datetime: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Build STAC collections list

        :param filters: (optional) Additional filters for collections search
        :returns: STAC collection dicts list
        """
        collection_model = deepcopy(self.stac_config["collection"])

        start, end = str_to_interval(datetime)

        all_pt = self.eodag_api.list_product_types(
            provider=self.provider, fetch_providers=False
        )

        if any((collection, q, platform, instrument, constellation, datetime)):
            try:
                guessed_product_types = self.eodag_api.guess_product_type(
                    free_text=q,
                    platformSerialIdentifier=platform,
                    instrument=instrument,
                    platform=constellation,
                    productType=collection,
                    missionStartDate=start.isoformat() if start else None,
                    missionEndDate=end.isoformat() if end else None,
                )
            except NoMatchingProductType:
                product_types = []
            else:
                product_types = [
                    pt for pt in all_pt if pt["ID"] in guessed_product_types
                ]
        else:
            product_types = all_pt

        # list product types with all metadata using guessed ids
        collection_list: List[Dict[str, Any]] = []
        for product_type in product_types:
            stac_collection = self.__generate_stac_collection(
                collection_model, product_type
            )
            collection_list.append(stac_collection)

        return collection_list


class StacCatalog(StacCommon):
    """Stac Catalog object

    :param url: Requested URL
    :param stac_config: STAC configuration from stac.yml conf file
    :param provider: Chosen provider
    :param eodag_api: EODAG python API instance
    :param root: (optional) API root
    :param catalogs: (optional) Catalogs list
    """

    def __init__(
        self,
        url: str,
        stac_config: Dict[str, Any],
        provider: Optional[str],
        eodag_api: EODataAccessGateway,
        root: str = "/",
        catalogs: Optional[List[str]] = None,
    ) -> None:
        super(StacCatalog, self).__init__(
            url=url,
            stac_config=stac_config,
            provider=provider,
            eodag_api=eodag_api,
            root=root,
        )
        self.data = {}

        self.shp_location_config = eodag_api.locations_config
        self.search_args: Dict[str, Any] = {}
        self.children: List[Dict[str, Any]] = []

        self.catalog_config = deepcopy(stac_config["catalog"])

        self.__update_data_from_catalog_config({"model": {}})

        # expand links
        self.parent = "/".join(self.url.rstrip("/").split("/")[:-1])
        if self.parent != self.root:
            self.data["links"].append({"rel": "parent", "href": self.parent})
        if self.children:
            self.data["links"] += self.children

        # build catalog
        self.__build_stac_catalog(catalogs)

    def __update_data_from_catalog_config(self, catalog_config: Dict[str, Any]) -> bool:
        """Updates configuration and data using given input catalog config

        :param catalog_config: Catalog config, from yml stac_config[catalogs]
        """
        model = catalog_config["model"]

        self.catalog_config = update_nested_dict(self.catalog_config, catalog_config)

        # parse f-strings
        # defaultdict usage will return "" for missing keys in format_args
        format_args = deepcopy(self.stac_config)
        format_args["catalog"] = defaultdict(
            str, dict(model, **{"root": self.root, "url": self.url})
        )
        # use existing data as parent_catalog
        format_args["parent_catalog"] = defaultdict(str, **self.data)
        parsed_model = format_dict_items(self.catalog_config["model"], **format_args)

        self.update_data(parsed_model)

        return True

    def set_children(self, children: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Set catalog children / links

        :param children: (optional) Children list
        """
        self.children = children or []
        self.data["links"] = [
            link for link in self.data["links"] if link["rel"] != "child"
        ]
        self.data["links"] += self.children
        return True

    def set_stac_product_type_by_id(
        self, product_type: str, **_: Any
    ) -> Dict[str, Any]:
        """Updates catalog with given product_type

        :param product_type: Product type
        """
        collections = StacCollection(
            url=self.url,
            stac_config=self.stac_config,
            provider=self.provider,
            eodag_api=self.eodag_api,
            root=self.root,
        ).get_collection_list(collection=product_type)

        if not collections:
            raise NotAvailableError(f"Collection {product_type} does not exist.")

        cat_model = deepcopy(self.stac_config["catalogs"]["product_type"]["model"])
        # parse f-strings
        format_args = deepcopy(self.stac_config)
        format_args["catalog"] = defaultdict(str, **self.data)
        format_args["collection"] = collections[0]
        try:
            parsed_dict: Dict[str, Any] = format_dict_items(cat_model, **format_args)
        except Exception:
            logger.error("Could not format product_type catalog")
            raise

        self.update_data(parsed_dict)

        # update search args
        self.search_args.update({"productType": product_type})

        return parsed_dict

    # get / set dates filters -------------------------------------------------

    def get_stac_years_list(self, **_: Any) -> List[int]:
        """Get catalog available years list

        :returns: Years list
        """
        extent_date_min, extent_date_max = self.get_datetime_extent()

        return list(range(extent_date_min.year, extent_date_max.year + 1))

    def get_stac_months_list(self, **_: Any) -> List[int]:
        """Get catalog available months list

        :returns: Months list
        """
        extent_date_min, extent_date_max = self.get_datetime_extent()

        return list(
            range(
                extent_date_min.month,
                (extent_date_max - relativedelta(days=1)).month + 1,
            )
        )

    def get_stac_days_list(self, **_: Any) -> List[int]:
        """Get catalog available days list

        :returns: Days list
        """
        extent_date_min, extent_date_max = self.get_datetime_extent()

        return list(
            range(
                extent_date_min.day, (extent_date_max - relativedelta(days=1)).day + 1
            )
        )

    def set_stac_year_by_id(self, year: str, **_: Any) -> Dict[str, Any]:
        """Updates and returns catalog with given year

        :param year: Year number
        :returns: Updated catalog
        """
        extent_date_min, extent_date_max = self.get_datetime_extent()

        datetime_min = max(
            [extent_date_min, dateutil.parser.parse(f"{year}-01-01T00:00:00Z")]
        )
        datetime_max = min(
            [
                extent_date_max,
                dateutil.parser.parse(f"{year}-01-01T00:00:00Z")
                + relativedelta(years=1),
            ]
        )

        catalog_model = deepcopy(self.stac_config["catalogs"]["year"]["model"])

        parsed_dict = self.set_stac_date(datetime_min, datetime_max, catalog_model)

        return parsed_dict

    def set_stac_month_by_id(self, month: str, **_: Any) -> Dict[str, Any]:
        """Updates and returns catalog with given month

        :param month: Month number
        :returns: Updated catalog
        """
        extent_date_min, extent_date_max = self.get_datetime_extent()
        year = extent_date_min.year

        datetime_min = max(
            [
                extent_date_min,
                dateutil.parser.parse(f"{year}-{month}-01T00:00:00Z"),
            ]
        )
        datetime_max = min(
            [
                extent_date_max,
                dateutil.parser.parse(f"{year}-{month}-01T00:00:00Z")
                + relativedelta(months=1),
            ]
        )

        catalog_model = deepcopy(self.stac_config["catalogs"]["month"]["model"])

        parsed_dict = self.set_stac_date(datetime_min, datetime_max, catalog_model)

        return parsed_dict

    def set_stac_day_by_id(self, day: str, **_: Any) -> Dict[str, Any]:
        """Updates and returns catalog with given day

        :param day: Day number
        :returns: Updated catalog
        """
        extent_date_min, extent_date_max = self.get_datetime_extent()
        year = extent_date_min.year
        month = extent_date_min.month

        datetime_min = max(
            [
                extent_date_min,
                dateutil.parser.parse(f"{year}-{month}-{day}T00:00:00Z"),
            ]
        )
        datetime_max = min(
            [
                extent_date_max,
                dateutil.parser.parse(f"{year}-{month}-{day}T00:00:00Z")
                + relativedelta(days=1),
            ]
        )

        catalog_model = deepcopy(self.stac_config["catalogs"]["day"]["model"])

        parsed_dict = self.set_stac_date(datetime_min, datetime_max, catalog_model)

        return parsed_dict

    def get_datetime_extent(self) -> Tuple[datetime, datetime]:
        """Returns catalog temporal extent as datetime objs

        :returns: Start & stop dates
        """
        extent_date_min = dateutil.parser.parse(DEFAULT_MISSION_START_DATE).replace(
            tzinfo=tz.UTC
        )
        extent_date_max = datetime.now(timezone.utc).replace(tzinfo=tz.UTC)
        for interval in self.data["extent"]["temporal"]["interval"]:
            extent_date_min_str, extent_date_max_str = interval
            # date min
            if extent_date_min_str:
                extent_date_min = max(
                    extent_date_min, dateutil.parser.parse(extent_date_min_str)
                )
            # date max
            if extent_date_max_str:
                extent_date_max = min(
                    extent_date_max, dateutil.parser.parse(extent_date_max_str)
                )

        return (
            extent_date_min.replace(tzinfo=tz.UTC),
            extent_date_max.replace(tzinfo=tz.UTC),
        )

    def set_stac_date(
        self,
        datetime_min: datetime,
        datetime_max: datetime,
        catalog_model: Dict[str, Any],
    ):
        """Updates catalog data using given dates

        :param datetime_min: Date min of interval
        :param datetime_max: Date max of interval
        :param catalog_model: Catalog model to use, from yml stac_config[catalogs]
        :returns: Updated catalog
        """
        # parse f-strings
        format_args = deepcopy(self.stac_config)
        format_args["catalog"] = defaultdict(str, **self.data)
        format_args["date"] = defaultdict(
            str,
            {
                "year": datetime_min.year,
                "month": datetime_min.month,
                "day": datetime_min.day,
                "min": datetime_min.isoformat().replace("+00:00", "Z"),
                "max": datetime_max.isoformat().replace("+00:00", "Z"),
            },
        )
        parsed_dict: Dict[str, Any] = format_dict_items(catalog_model, **format_args)

        self.update_data(parsed_dict)

        # update search args
        self.search_args.update(
            {
                "start": datetime_min.isoformat().replace("+00:00", "Z"),
                "end": datetime_max.isoformat().replace("+00:00", "Z"),
            }
        )
        return parsed_dict

    # get / set cloud_cover filter --------------------------------------------

    def get_stac_cloud_covers_list(self, **_: Any) -> List[int]:
        """Get cloud_cover list

        :returns: cloud_cover list
        """
        return list(range(0, 101, 10))

    def set_stac_cloud_cover_by_id(self, cloud_cover: str, **_: Any) -> Dict[str, Any]:
        """Updates and returns catalog with given max cloud_cover

        :param cloud_cover: Cloud_cover number
        :returns: Updated catalog
        """
        cat_model = deepcopy(self.stac_config["catalogs"]["cloud_cover"]["model"])
        # parse f-strings
        format_args = deepcopy(self.stac_config)
        format_args["catalog"] = defaultdict(str, **self.data)
        format_args["cloud_cover"] = cloud_cover
        parsed_dict: Dict[str, Any] = format_dict_items(cat_model, **format_args)

        self.update_data(parsed_dict)

        # update search args
        self.search_args.update({"cloudCover": cloud_cover})

        return parsed_dict

    # get / set locations filter ----------------------------------------------

    def get_stac_location_list(self, catalog_name: str) -> List[str]:
        """Get locations list using stac_conf & locations_config

        :param catalog_name: Catalog/location name
        :returns: Locations list
        """

        if catalog_name not in self.stac_config["catalogs"]:
            logger.warning("no entry found for %s in location_config", catalog_name)
            return []
        location_config = self.stac_config["catalogs"][catalog_name]

        for k in ["path", "attr"]:
            if k not in location_config.keys():
                logger.warning(
                    "no %s key found for %s in location_config", k, catalog_name
                )
                return []
        path = location_config["path"]
        attr = location_config["attr"]

        with shapefile.Reader(path) as shp:
            countries_list: List[str] = [rec[attr] for rec in shp.records()]  # type: ignore

        # remove duplicates
        countries_list = list(set(countries_list))

        countries_list.sort()

        return countries_list

    def set_stac_location_by_id(
        self, location: str, catalog_name: str
    ) -> Dict[str, Any]:
        """Updates and returns catalog with given location

        :param location: Feature attribute value for shp filtering
        :param catalog_name: Catalog/location name
        :returns: Updated catalog
        """
        location_list_cat_key = catalog_name + "_list"

        if location_list_cat_key not in self.stac_config["catalogs"]:
            logger.warning(
                "no entry found for %s's list in location_config", catalog_name
            )
            return {}
        location_config = self.stac_config["catalogs"][location_list_cat_key]

        for k in ["path", "attr"]:
            if k not in location_config.keys():
                logger.warning(
                    "no %s key found for %s's list in location_config", k, catalog_name
                )
                return {}
        path = location_config["path"]
        attr = location_config["attr"]

        with shapefile.Reader(path) as shp:
            geom_hits = [
                shape(shaperec.shape)
                for shaperec in shp.shapeRecords()
                if shaperec.record.as_dict().get(attr, None) == location
            ]

        if not geom_hits:
            logger.warning(
                "no feature found in %s matching %s=%s", path, attr, location
            )
            return {}

        geom = cast(BaseGeometry, unary_union(geom_hits))

        cat_model = deepcopy(self.stac_config["catalogs"]["country"]["model"])
        # parse f-strings
        format_args = deepcopy(self.stac_config)
        format_args["catalog"] = defaultdict(str, **self.data)
        format_args["feature"] = defaultdict(str, {"geometry": geom, "id": location})
        parsed_dict: Dict[str, Any] = format_dict_items(cat_model, **format_args)

        self.update_data(parsed_dict)

        # update search args
        self.search_args.update({"geom": geom})

        return parsed_dict

    def build_locations_config(self) -> Dict[str, str]:
        """Build locations config from stac_conf[locations_catalogs] & eodag_api.locations_config

        :returns: Locations configuration dict
        """
        user_config_locations_list = self.eodag_api.locations_config

        locations_config_model = deepcopy(self.stac_config["locations_catalogs"])

        locations_config: Dict[str, str] = {}
        for loc in user_config_locations_list:
            # parse jsonpath
            parsed = jsonpath_parse_dict_items(
                locations_config_model, {"shp_location": loc}
            )

            # set default child/parent for this location
            parsed["location"]["parent_key"] = f"{loc['name']}_list"

            locations_config[f"{loc['name']}_list"] = parsed["locations_list"]
            locations_config[loc["name"]] = parsed["location"]

        return locations_config

    def __build_stac_catalog(self, catalogs: Optional[List[str]] = None) -> StacCatalog:
        """Build nested catalog from catalag list

        :param catalogs: (optional) Catalogs list
        :returns: This catalog obj
        """
        settings = Settings.from_environment()

        # update conf with user shp locations
        locations_config = self.build_locations_config()

        self.stac_config["catalogs"] = {
            **deepcopy(self.stac_config["catalogs"]),
            **locations_config,
        }

        if not catalogs:
            # Build root catalog combined with landing page
            self.__update_data_from_catalog_config(
                {
                    "model": {
                        **deepcopy(self.stac_config["landing_page"]),
                        **{
                            "provider": self.provider,
                            "id": settings.stac_api_landing_id,
                            "title": settings.stac_api_title,
                            "description": settings.stac_api_description,
                        },
                    }
                }
            )

            # build children : product_types
            product_types_list = [
                pt
                for pt in self.eodag_api.list_product_types(
                    provider=self.provider, fetch_providers=False
                )
            ]
            self.set_children(
                [
                    {
                        "rel": "child",
                        "href": urljoin(
                            self.url, f"{STAC_CATALOGS_PREFIX}/{product_type['ID']}"
                        ),
                        "title": product_type["title"],
                    }
                    for product_type in product_types_list
                ]
            )
            return self

        # use product_types_list as base for building nested catalogs
        self.__update_data_from_catalog_config(
            deepcopy(self.stac_config["catalogs"]["product_types_list"])
        )

        for idx, cat in enumerate(catalogs):
            if idx % 2 == 0:
                # even: cat is a filtering value ----------------------------------
                cat_data_name = self.catalog_config["child_key"]
                cat_data_value = cat

                # update data
                cat_data_name_dict = self.stac_config["catalogs"][cat_data_name]
                set_data_method_name = (
                    f"set_stac_{cat_data_name}_by_id"
                    if "catalog_type" not in cat_data_name_dict.keys()
                    else f"set_stac_{cat_data_name_dict['catalog_type']}_by_id"
                )
                set_data_method = getattr(self, set_data_method_name)
                set_data_method(cat_data_value, catalog_name=cat_data_name)

                if idx == len(catalogs) - 1:
                    # build children : remaining filtering keys
                    remaining_catalogs_list = [
                        c
                        for c in self.stac_config["catalogs"].keys()
                        # keep filters not used yet AND
                        if self.stac_config["catalogs"][c]["model"]["id"]
                        not in catalogs
                        and (
                            # filters with no parent_key constraint (no key, or key=None) OR
                            "parent_key" not in self.stac_config["catalogs"][c]
                            or not self.stac_config["catalogs"][c]["parent_key"]
                            # filters matching parent_key constraint
                            or self.stac_config["catalogs"][c]["parent_key"]
                            == cat_data_name
                        )
                        # AND filters that match parent attr constraint (locations)
                        and (
                            "parent" not in self.stac_config["catalogs"][c]
                            or not self.stac_config["catalogs"][c]["parent"]["key"]
                            or (
                                self.stac_config["catalogs"][c]["parent"]["key"]
                                == cat_data_name
                                and self.stac_config["catalogs"][c]["parent"]["attr"]
                                == cat_data_value
                            )
                        )
                    ]

                    self.set_children(
                        [
                            {
                                "rel": "child",
                                "href": self.url
                                + "/"
                                + self.stac_config["catalogs"][c]["model"]["id"],
                                "title": str(
                                    self.stac_config["catalogs"][c]["model"]["id"]
                                ),
                            }
                            for c in remaining_catalogs_list
                        ]
                        + [
                            {
                                "rel": "items",
                                "href": self.url + "/items",
                                "title": "items",
                            }
                        ]
                    )

            else:
                # odd: cat is a filtering key -------------------------------------
                try:
                    cat_key = [
                        c
                        for c in self.stac_config["catalogs"].keys()
                        if self.stac_config["catalogs"][c]["model"]["id"] == cat
                    ][0]
                except IndexError as e:
                    raise ValidationError(
                        f"Bad settings for {cat} in stac_config catalogs"
                    ) from e
                cat_config = deepcopy(self.stac_config["catalogs"][cat_key])
                # update data
                self.__update_data_from_catalog_config(cat_config)

                # get filtering values list
                get_data_method_name = (
                    f"get_stac_{cat_key}"
                    if "catalog_type"
                    not in self.stac_config["catalogs"][cat_key].keys()
                    else f"get_stac_{self.stac_config['catalogs'][cat_key]['catalog_type']}"
                )
                get_data_method = getattr(self, get_data_method_name)
                cat_data_list = get_data_method(catalog_name=cat_key)

                if idx == len(catalogs) - 1:
                    # filtering values list as children (do not include items)
                    self.set_children(
                        [
                            {
                                "rel": "child",
                                "href": self.url + "/" + str(filtering_data),
                                "title": str(filtering_data),
                            }
                            for filtering_data in cat_data_list
                        ]
                    )

        return self
