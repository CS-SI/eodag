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
import datetime
import logging
import os
import re
from collections import defaultdict
from urllib.parse import parse_qs, urlencode, urlparse

import dateutil.parser
import geojson
import shapefile
from dateutil import tz
from dateutil.relativedelta import relativedelta
from shapely.geometry import shape
from shapely.ops import unary_union

from eodag.api.product.metadata_mapping import (
    DEFAULT_METADATA_MAPPING,
    format_metadata,
    get_metadata_path,
)
from eodag.utils import (
    deepcopy,
    dict_items_recursive_apply,
    format_dict_items,
    jsonpath_parse_dict_items,
    string_to_jsonpath,
    update_nested_dict,
    urljoin,
)
from eodag.utils.exceptions import (
    MisconfiguredError,
    NoMatchingProductType,
    NotAvailableError,
    ValidationError,
)

logger = logging.getLogger("eodag.rest.stac")

DEFAULT_MISSION_START_DATE = "2015-01-01T00:00:00Z"
STAC_CATALOGS_PREFIX = "catalogs"


class StacCommon(object):
    """Stac common object

    :param url: Requested URL
    :type url: str
    :param stac_config: STAC configuration from stac.yml conf file
    :type stac_config: dict
    :param provider: Chosen provider
    :type provider: str
    :param eodag_api: EODAG python API instance
    :type eodag_api: :class:`eodag.api.core.EODataAccessGateway`
    :param root: (optional) API root
    :type root: str
    """

    def __init__(
        self, url, stac_config, provider, eodag_api, root="/", *args, **kwargs
    ):
        self.url = url.rstrip("/") if len(url) > 1 else url
        self.stac_config = stac_config
        self.provider = provider
        self.eodag_api = eodag_api
        self.root = root.rstrip("/") if len(root) > 1 else root

        self.data = {}

        if self.provider and self.eodag_api.get_preferred_provider() != self.provider:
            self.eodag_api.set_preferred_provider(self.provider)

    def update_data(self, data):
        """Updates data using given input STAC dict data

        :param data: Catalog data (parsed STAC dict)
        :type data: dict
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
        # "None" values to None
        self.data = dict_items_recursive_apply(
            self.data, lambda k, v: None if v == "None" else v
        )

        # ids and titles as str
        self.data = dict_items_recursive_apply(
            self.data, lambda k, v: str(v) if k in ["title", "id"] else v
        )

        # empty stac_extensions: "" to []
        if not self.data.get("stac_extensions", True):
            self.data["stac_extensions"] = []

    @staticmethod
    def get_stac_extension(url, stac_config, extension, **kwargs):
        """Parse STAC extension from config and return as dict

        :param url: Requested URL
        :type url: str
        :param stac_config: STAC configuration from stac.yml conf file
        :type stac_config: dict
        :param extension: Extension name
        :type extension: str
        :param kwargs: Additional variables needed for parsing extension
        :type kwargs: Any
        :returns: STAC extension as dictionnary
        :rtype: dict
        """
        extension_model = deepcopy(stac_config).get("extensions", {}).get(extension, {})

        # parse f-strings
        format_args = deepcopy(stac_config)
        format_args["extension"] = {
            "url": url,
            "properties": kwargs.get("properties", {}),
        }
        extension = format_dict_items(extension_model, **format_args)

        return extension

    def as_dict(self):
        """Returns object data as dictionnary

        :returns: STAC data dictionnary
        :rtype: dict
        """
        return geojson.loads(geojson.dumps(self.data))

    __geo_interface__ = property(as_dict)


class StacItem(StacCommon):
    """Stac item object

    :param url: Requested URL
    :type url: str
    :param stac_config: STAC configuration from stac.yml conf file
    :type stac_config: dict
    :param provider: Chosen provider
    :type provider: str
    :param eodag_api: EODAG python API instance
    :type eodag_api: :class:`eodag.api.core.EODataAccessGateway`
    :param root: (optional) API root
    :type root: str
    """

    def __init__(
        self, url, stac_config, provider, eodag_api, root="/", *args, **kwargs
    ):
        super(StacItem, self).__init__(
            url=url,
            stac_config=stac_config,
            provider=provider,
            eodag_api=eodag_api,
            root=root,
            *args,
            **kwargs,
        )

    def __get_item_list(self, search_results, catalog):
        """Build STAC items list from EODAG search results

        :param search_results: EODAG search results
        :type search_results: :class:`~eodag.api.search_result.SearchResult`
        :param catalog: STAC catalog dict used for parsing item metadata
        :type catalog: dict
        :returns: STAC item dicts list
        :rtype: list
        """
        if len(search_results) <= 0:
            return []

        item_model = self.__filter_item_model_properties(
            self.stac_config["item"], search_results[0].product_type
        )

        # check if some items need to be converted
        need_conversion = {}
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

        item_list = []
        for product in search_results:
            # parse jsonpath
            product_item = jsonpath_parse_dict_items(
                item_model, {"product": product.__dict__}
            )
            # add origin assets to product assets
            origin_assets = product_item["assets"].pop("origin_assets")
            if getattr(product, "assets", False):
                product_item["assets"] = dict(product_item["assets"], **origin_assets)
            # append provider query-arg to download link if specified
            if self.provider:
                parts = urlparse(product_item["assets"]["downloadLink"]["href"])
                query_dict = parse_qs(parts.query)
                query_dict.update(provider=self.provider)
                without_arg_url = (
                    f"{parts.scheme}://{parts.netloc}{parts.path}"
                    if parts.scheme
                    else f"{parts.netloc}{parts.path}"
                )
                product_item["assets"]["downloadLink"][
                    "href"
                ] = f"{without_arg_url}?{urlencode(query_dict, doseq=True)}"

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

            # remove empty properties
            product_item = self.__filter_item_properties_values(product_item)

            item_list.append(product_item)

        return item_list

    def get_stac_items(self, search_results, catalog):
        """Build STAC items from EODAG search results

        :param search_results: EODAG search results
        :type search_results: :class:`~eodag.api.search_result.SearchResult`
        :param catalog: STAC catalog dict used for parsing item metadata
        :type catalog: dict
        :returns: Items dictionnary
        :rtype: dict
        """
        items_model = deepcopy(self.stac_config["items"])

        search_results.numberMatched = search_results.properties["totalResults"]
        search_results.numberReturned = len(search_results)

        # next page link
        if "?" in self.url:
            # search endpoint: use page url as self link
            for i, _ in enumerate(items_model["links"]):
                if items_model["links"][i]["rel"] == "self":
                    items_model["links"][i]["href"] = catalog["url"]
            if "page=" not in self.url:
                search_results.next = "%s&page=%s" % (
                    self.url,
                    search_results.properties["page"] + 1,
                )
            else:
                search_results.next = re.sub(
                    r"^(.*)(page=[0-9]+)(.*)$",
                    r"\1page=%s\3" % (search_results.properties["page"] + 1),
                    self.url,
                )
        else:
            search_results.next = "%s?page=%s" % (
                self.url,
                search_results.properties["page"] + 1,
            )

        search_results.timeStamp = (
            datetime.datetime.now(datetime.timezone.utc)
            .isoformat()
            .replace("+00:00", "")
            + "Z"
        )

        # parse jsonpath
        items = jsonpath_parse_dict_items(
            items_model, {"search_results": search_results.__dict__}
        )
        # parse f-strings
        format_args = deepcopy(self.stac_config)
        format_args["catalog"] = catalog
        items = format_dict_items(items, **format_args)

        # last page: remove next page link
        if (
            search_results.properties["itemsPerPage"]
            * search_results.properties["page"]
            >= search_results.properties["totalResults"]
        ):
            items["links"] = [link for link in items["links"] if link["rel"] != "next"]

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
        return geojson.loads(geojson.dumps(self.data))

    def __filter_item_model_properties(self, item_model, product_type):
        """Filter item model depending on product type metadata and its extensions.
        Removes not needed parameters, and adds supplementary ones as
        part of oseo extension.

        :param item_model: Item model from stac_config
        :type item_model: dict
        :param product_type: Product type
        :type product_type: str
        :returns: Filtered item model
        :rtype: dict
        """
        try:
            product_type_dict = [
                pt
                for pt in self.eodag_api.list_product_types(
                    provider=self.provider, fetch_providers=False
                )
                if pt["ID"] == product_type
            ][0]
        except IndexError:
            raise MisconfiguredError(
                "Product type {} not available for {}".format(
                    product_type, self.provider
                )
            )

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

    def __filter_item_properties_values(self, item):
        """Removes empty properties, unused extensions, and add missing extensions

        :param item: STAC item data
        :type item: dict
        :returns: Filtered item model
        :rtype: dict
        """
        all_extensions_dict = deepcopy(self.stac_config["stac_extensions"])
        # parse f-strings with root
        all_extensions_dict = format_dict_items(
            all_extensions_dict, **{"catalog": {"root": self.root}}
        )

        item["stac_extensions"] = []
        # dict to list of keys to permit pop() while iterating
        for k in list(item["properties"]):
            extension_prefix = k.split(":")[0]

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

    def get_stac_item_from_product(self, product):
        """Build STAC item from EODAG product

        :param product: EODAG product
        :type product: :class:`eodag.api.product._product.EOProduct`
        :returns: STAC item
        :rtype: list
        """
        product_type = product.product_type

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

        # parse jsonpath
        product_item = jsonpath_parse_dict_items(
            item_model, {"product": product.__dict__}
        )
        # parse f-strings
        format_args = deepcopy(self.stac_config)
        # format_args["collection"] = dict(catalog.as_dict(), **{"url": catalog.url})
        format_args["catalog"] = dict(
            catalog.as_dict(), **{"url": catalog.url, "root": catalog.root}
        )
        format_args["item"] = product_item
        product_item = format_dict_items(product_item, **format_args)
        product_item["bbox"] = [float(i) for i in product_item["bbox"]]

        # remove empty properties
        product_item = self.__filter_item_properties_values(product_item)

        self.update_data(product_item)
        return self.as_dict()


class StacCollection(StacCommon):
    """Stac collection object

    :param url: Requested URL
    :type url: str
    :param stac_config: STAC configuration from stac.yml conf file
    :type stac_config: dict
    :param provider: Chosen provider
    :type provider: str
    :param eodag_api: EODAG python API instance
    :type eodag_api: :class:`eodag.api.core.EODataAccessGateway`
    :param root: (optional) API root
    :type root: str
    """

    def __init__(
        self, url, stac_config, provider, eodag_api, root="/", *args, **kwargs
    ):
        super(StacCollection, self).__init__(
            url=url,
            stac_config=stac_config,
            provider=provider,
            eodag_api=eodag_api,
            root=root,
            *args,
            **kwargs,
        )

    def __get_product_types(self, filters=None):
        """Returns a list of supported product types

        :param filters: (optional) Additional filters for product types search
        :type filters: dict
        :returns: List of corresponding product types
        :rtype: list
        """
        if filters is None:
            filters = {}
        try:
            guessed_product_types = self.eodag_api.guess_product_type(
                instrument=filters.get("instrument"),
                platform=filters.get("platform"),
                platformSerialIdentifier=filters.get("platformSerialIdentifier"),
                sensorType=filters.get("sensorType"),
                processingLevel=filters.get("processingLevel"),
            )
        except NoMatchingProductType:
            guessed_product_types = []
        if guessed_product_types:
            product_types = [
                pt
                for pt in self.eodag_api.list_product_types(provider=self.provider)
                if pt["ID"] in guessed_product_types
            ]
        else:
            product_types = self.eodag_api.list_product_types(provider=self.provider)
        return product_types

    def __get_collection_list(self, filters=None):
        """Build STAC collections list

        :param filters: (optional) Additional filters for collections search
        :type filters: dict
        :returns: STAC collection dicts list
        :rtype: list
        """
        collection_model = deepcopy(self.stac_config["collection"])

        product_types = self.__get_product_types(filters)

        collection_list = []
        for product_type in product_types:
            # get default provider for each product_type
            product_type_provider = (
                self.provider
                or next(
                    self.eodag_api._plugins_manager.get_search_plugins(
                        product_type=product_type["ID"]
                    )
                ).provider
            )
            #
            # if provider not in self.eodag_api.available_providers():
            #     for p in self.eodag_api._plugins_manager.get_search_plugins(product_type=product_type["ID"]):
            #         print(p.provider)

            # parse jsonpath
            product_type_collection = jsonpath_parse_dict_items(
                collection_model,
                {
                    "product_type": product_type,
                    "provider": self.eodag_api.providers_config[
                        product_type_provider
                    ].__dict__,
                },
            )
            # parse f-strings
            format_args = deepcopy(self.stac_config)
            format_args["collection"] = dict(
                product_type_collection, **{"url": self.url, "root": self.root}
            )
            product_type_collection = format_dict_items(
                product_type_collection, **format_args
            )

            collection_list.append(product_type_collection)

        return collection_list

    def get_collections(self, filters=None):
        """Build STAC collections

        :param filters: (optional) Additional filters for collections search
        :type filters: dict
        :returns: Collections dictionnary
        :rtype: dict
        """
        collections = deepcopy(self.stac_config["collections"])
        collections["collections"] = self.__get_collection_list(filters)

        collections["links"] += [
            {
                "rel": "child",
                "title": collec["id"],
                "href": [
                    link["href"] for link in collec["links"] if link["rel"] == "self"
                ][0],
            }
            for collec in collections["collections"]
        ]

        self.update_data(collections)
        return self.as_dict()

    def get_collection_by_id(self, collection_id):
        """Build STAC collection by its id

        :param collection_id: Product type as collection ID
        :type collection_id: str
        :returns: Collection dictionnary
        :rtype: dict
        """
        collection_list = self.__get_collection_list()

        try:
            collection = [c for c in collection_list if c["id"] == collection_id][0]
        except IndexError:
            raise NotAvailableError("%s collection not found" % collection_id)

        self.update_data(collection)
        return self.as_dict()


class StacCatalog(StacCommon):
    """Stac Catalog object

    :param url: Requested URL
    :type url: str
    :param stac_config: STAC configuration from stac.yml conf file
    :type stac_config: dict
    :param provider: Chosen provider
    :type provider: str
    :param eodag_api: EODAG python API instance
    :type eodag_api: :class:`eodag.api.core.EODataAccessGateway`
    :param root: (optional) API root
    :type root: str
    :param catalogs: (optional) Catalogs list
    :type catalogs: list
    :param fetch_providers: (optional) Whether to fetch providers for new product
                            types or not
    :type fetch_providers: bool
    """

    def __init__(
        self,
        url,
        stac_config,
        provider,
        eodag_api,
        root="/",
        catalogs=[],
        fetch_providers=True,
        *args,
        **kwargs,
    ):
        super(StacCatalog, self).__init__(
            url=url,
            stac_config=stac_config,
            provider=provider,
            eodag_api=eodag_api,
            root=root,
            *args,
            **kwargs,
        )
        self.shp_location_config = eodag_api.locations_config
        self.search_args = {}

        self.data = {}
        self.children = []

        self.catalog_config = deepcopy(stac_config["catalog"])

        self.__update_data_from_catalog_config({"model": {}})

        # expand links
        self.parent = "/".join(self.url.rstrip("/").split("/")[:-1])
        if self.parent != self.root:
            self.data["links"].append({"rel": "parent", "href": self.parent})
        if self.children:
            self.data["links"] += self.children

        # build catalog
        self.__build_stac_catalog(catalogs, fetch_providers=fetch_providers)

    def __update_data_from_catalog_config(self, catalog_config):
        """Updates configuration and data using given input catalog config

        :param catalog_config: Catalog config, from yml stac_config[catalogs]
        :type catalog_config: dict
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

    def set_children(self, children=[]):
        """Set catalog children / links

        :param children: (optional) Children list
        :type children: list
        """
        self.children = children
        self.data["links"] = [
            link for link in self.data["links"] if link["rel"] != "child"
        ]
        self.data["links"] += children
        return True

    def set_stac_product_type_by_id(self, product_type, **kwargs):
        """Updates catalog with given product_type

        :param product_type: Product type
        :type product_type: str
        """
        collection = StacCollection(
            url=self.url,
            stac_config=self.stac_config,
            provider=self.provider,
            eodag_api=self.eodag_api,
            root=self.root,
        ).get_collection_by_id(product_type)

        cat_model = deepcopy(self.stac_config["catalogs"]["product_type"]["model"])
        # parse f-strings
        format_args = deepcopy(self.stac_config)
        format_args["catalog"] = defaultdict(str, **self.data)
        format_args["collection"] = collection
        try:
            parsed_dict = format_dict_items(cat_model, **format_args)
        except Exception:
            logger.error("Could not format product_type catalog")
            raise

        self.update_data(parsed_dict)

        # update search args
        self.search_args.update({"product_type": product_type})

        return parsed_dict

    # get / set dates filters -------------------------------------------------

    def get_stac_years_list(self, **kwargs):
        """Get catalog available years list

        :returns: Years list
        :rtype: list
        """
        extent_date_min, extent_date_max = self.get_datetime_extent()

        return list(range(extent_date_min.year, extent_date_max.year + 1))

    def get_stac_months_list(self, **kwargs):
        """Get catalog available months list

        :returns: Months list
        :rtype: list
        """
        extent_date_min, extent_date_max = self.get_datetime_extent()

        return list(
            range(
                extent_date_min.month,
                (extent_date_max - relativedelta(days=1)).month + 1,
            )
        )

    def get_stac_days_list(self, **kwargs):
        """Get catalog available days list

        :returns: Days list
        :rtype: list
        """
        extent_date_min, extent_date_max = self.get_datetime_extent()

        return list(
            range(
                extent_date_min.day, (extent_date_max - relativedelta(days=1)).day + 1
            )
        )

    def set_stac_year_by_id(self, year, **kwargs):
        """Updates and returns catalog with given year

        :param year: Year number
        :type year: str
        :returns: Updated catalog
        :rtype: dict
        """
        extent_date_min, extent_date_max = self.get_datetime_extent()

        datetime_min = max(
            [extent_date_min, dateutil.parser.parse("{}-01-01T00:00:00Z".format(year))]
        )
        datetime_max = min(
            [
                extent_date_max,
                dateutil.parser.parse("{}-01-01T00:00:00Z".format((year)))
                + relativedelta(years=1),
            ]
        )

        catalog_model = deepcopy(self.stac_config["catalogs"]["year"]["model"])

        parsed_dict = self.set_stac_date(datetime_min, datetime_max, catalog_model)

        return parsed_dict

    def set_stac_month_by_id(self, month, **kwargs):
        """Updates and returns catalog with given month

        :param month: Month number
        :type month: str
        :returns: Updated catalog
        :rtype: dict
        """
        extent_date_min, extent_date_max = self.get_datetime_extent()
        year = extent_date_min.year

        datetime_min = max(
            [
                extent_date_min,
                dateutil.parser.parse("{}-{}-01T00:00:00Z".format(year, month)),
            ]
        )
        datetime_max = min(
            [
                extent_date_max,
                dateutil.parser.parse("{}-{}-01T00:00:00Z".format(year, month))
                + relativedelta(months=1),
            ]
        )

        catalog_model = deepcopy(self.stac_config["catalogs"]["month"]["model"])

        parsed_dict = self.set_stac_date(datetime_min, datetime_max, catalog_model)

        return parsed_dict

    def set_stac_day_by_id(self, day, **kwargs):
        """Updates and returns catalog with given day

        :param day: Day number
        :type day: str
        :returns: Updated catalog
        :rtype: dict
        """
        extent_date_min, extent_date_max = self.get_datetime_extent()
        year = extent_date_min.year
        month = extent_date_min.month

        datetime_min = max(
            [
                extent_date_min,
                dateutil.parser.parse("{}-{}-{}T00:00:00Z".format(year, month, day)),
            ]
        )
        datetime_max = min(
            [
                extent_date_max,
                dateutil.parser.parse("{}-{}-{}T00:00:00Z".format(year, month, day))
                + relativedelta(days=1),
            ]
        )

        catalog_model = deepcopy(self.stac_config["catalogs"]["day"]["model"])

        parsed_dict = self.set_stac_date(datetime_min, datetime_max, catalog_model)

        return parsed_dict

    def get_datetime_extent(self):
        """Returns catalog temporal extent as datetime objs

        :returns: Start & stop dates
        :rtype: tuple
        """
        extent_date_min = dateutil.parser.parse(DEFAULT_MISSION_START_DATE).replace(
            tzinfo=tz.UTC
        )
        extent_date_max = datetime.datetime.now(datetime.timezone.utc).replace(
            tzinfo=tz.UTC
        )
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

    def set_stac_date(self, datetime_min, datetime_max, catalog_model):
        """Updates catalog data using given dates

        :param datetime_min: Date min of interval
        :type datetime_min: :class:`datetime.datetime`
        :param datetime_max: Date max of interval
        :type datetime_max: :class:`datetime.datetime`
        :param catalog_model: Catalog model to use, from yml stac_config[catalogs]
        :type catalog_model: dict
        :returns: Updated catalog
        :rtype: dict
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
                "min": datetime_min.isoformat().replace("+00:00", "") + "Z",
                "max": datetime_max.isoformat().replace("+00:00", "") + "Z",
            },
        )
        parsed_dict = format_dict_items(catalog_model, **format_args)

        self.update_data(parsed_dict)

        # update search args
        self.search_args.update(
            {
                "dtstart": datetime_min.isoformat().split("T")[0],
                "dtend": datetime_max.isoformat().split("T")[0],
            }
        )
        return parsed_dict

    # get / set cloud_cover filter --------------------------------------------

    def get_stac_cloud_covers_list(self, **kwargs):
        """Get cloud_cover list

        :returns: cloud_cover list
        :rtype: list
        """
        return list(range(0, 101, 10))

    def set_stac_cloud_cover_by_id(self, cloud_cover, **kwargs):
        """Updates and returns catalog with given max cloud_cover

        :param cloud_cover: Cloud_cover number
        :type cloud_cover: str
        :returns: Updated catalog
        :rtype: dict
        """
        cat_model = deepcopy(self.stac_config["catalogs"]["cloud_cover"]["model"])
        # parse f-strings
        format_args = deepcopy(self.stac_config)
        format_args["catalog"] = defaultdict(str, **self.data)
        format_args["cloud_cover"] = cloud_cover
        parsed_dict = format_dict_items(cat_model, **format_args)

        self.update_data(parsed_dict)

        # update search args
        self.search_args.update({"query": {"eo:cloud_cover": {"lte": cloud_cover}}})

        return parsed_dict

    # get / set locations filter ----------------------------------------------

    def get_stac_location_list(self, catalog_name):
        """Get locations list using stac_conf & locations_config

        :param catalog_name: Catalog/location name
        :type catalog_name: str
        :returns: Locations list
        :rtype: list
        """

        if catalog_name not in self.stac_config["catalogs"]:
            logger.warning(
                "no entry found for {} in location_config".format(catalog_name)
            )
            return []
        location_config = self.stac_config["catalogs"][catalog_name]

        for k in ["path", "attr"]:
            if k not in location_config.keys():
                logger.warning(
                    "no {} key found for {} in location_config".format(k, catalog_name)
                )
                return []
        path = location_config["path"]
        attr = location_config["attr"]

        with shapefile.Reader(path) as shp:
            countries_list = [rec[attr] for rec in shp.records()]

        # remove duplicates
        countries_list = list(set(countries_list))

        countries_list.sort()

        return countries_list

    def set_stac_location_by_id(self, location, catalog_name):
        """Updates and returns catalog with given location

        :param location: Feature attribute value for shp filtering
        :type location: str
        :param catalog_name: Catalog/location name
        :type catalog_name: str
        :returns: Updated catalog
        :rtype: dict
        """
        location_list_cat_key = catalog_name + "_list"

        if location_list_cat_key not in self.stac_config["catalogs"]:
            logger.warning(
                "no entry found for {}'s list in location_config".format(catalog_name)
            )
            return {}
        location_config = self.stac_config["catalogs"][location_list_cat_key]

        for k in ["path", "attr"]:
            if k not in location_config.keys():
                logger.warning(
                    "no {} key found for {}'s list in location_config".format(
                        k, catalog_name
                    )
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

        if len(geom_hits) == 0:
            logger.warning(
                "no feature found in %s matching %s=%s" % (path, attr, location)
            )
            return {}

        geom = unary_union(geom_hits)

        cat_model = deepcopy(self.stac_config["catalogs"]["country"]["model"])
        # parse f-strings
        format_args = deepcopy(self.stac_config)
        format_args["catalog"] = defaultdict(str, **self.data)
        format_args["feature"] = defaultdict(str, {"geometry": geom, "id": location})
        parsed_dict = format_dict_items(cat_model, **format_args)

        self.update_data(parsed_dict)

        # update search args
        self.search_args.update({"geom": geom})

        return parsed_dict

    def build_locations_config(self):
        """Build locations config from stac_conf[locations_catalogs] & eodag_api.locations_config

        :returns: Locations configuration dict
        :rtype: dict
        """
        user_config_locations_list = self.eodag_api.locations_config

        locations_config_model = deepcopy(self.stac_config["locations_catalogs"])

        locations_config = {}
        for loc in user_config_locations_list:
            # parse jsonpath
            parsed = jsonpath_parse_dict_items(
                locations_config_model, {"shp_location": loc}
            )

            # set default child/parent for this location
            parsed["location"]["parent_key"] = "{}_list".format(loc["name"])

            locations_config["{}_list".format(loc["name"])] = parsed["locations_list"]
            locations_config[loc["name"]] = parsed["location"]

        return locations_config

    def __build_stac_catalog(self, catalogs=[], fetch_providers=True):
        """Build nested catalog from catalag list

        :param catalogs: (optional) Catalogs list
        :type catalogs: list
        :param fetch_providers: (optional) Whether to fetch providers for new product
                                types or not
        :type fetch_providers: bool
        :returns: This catalog obj
        :rtype: :class:`eodag.stac.StacCatalog`
        """
        # update conf with user shp locations
        locations_config = self.build_locations_config()

        self.stac_config["catalogs"] = dict(
            deepcopy(self.stac_config["catalogs"]), **locations_config
        )

        if len(catalogs) == 0:
            # Build root catalog combined with landing page
            self.__update_data_from_catalog_config(
                {
                    "model": dict(
                        deepcopy(self.stac_config["landing_page"]),
                        **{"provider": self.provider},
                    )
                }
            )

            # build children : product_types
            product_types_list = [
                pt
                for pt in self.eodag_api.list_product_types(
                    provider=self.provider, fetch_providers=fetch_providers
                )
            ]
            self.set_children(
                [
                    {
                        "rel": "child",
                        "href": urljoin(
                            self.url, f"{STAC_CATALOGS_PREFIX}/{product_type['ID']}"
                        ),
                        "title": product_type["ID"],
                    }
                    for product_type in product_types_list
                ]
            )
        else:
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
                set_data_method_name = (
                    "set_stac_%s_by_id" % cat_data_name
                    if "catalog_type"
                    not in self.stac_config["catalogs"][cat_data_name].keys()
                    else "set_stac_%s_by_id"
                    % self.stac_config["catalogs"][cat_data_name]["catalog_type"]
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
                except IndexError:
                    raise ValidationError(
                        "Bad settings for %s in stac_config catalogs" % cat
                    )
                cat_config = deepcopy(self.stac_config["catalogs"][cat_key])
                # update data
                self.__update_data_from_catalog_config(cat_config)

                # get filtering values list
                get_data_method_name = (
                    "get_stac_%s" % cat_key
                    if "catalog_type"
                    not in self.stac_config["catalogs"][cat_key].keys()
                    else "get_stac_%s"
                    % self.stac_config["catalogs"][cat_key]["catalog_type"]
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

    def get_stac_catalog(self):
        """Get nested STAC catalog as data dict

        :returns: Catalog dictionnary
        :rtype: dict
        """
        return self.as_dict()
