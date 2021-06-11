# -*- coding: utf-8 -*-
# Copyright 2017-2018 CS GROUP - France (CS SI)
# All rights reserved

import datetime
import os
import re
from collections import namedtuple

import dateutil.parser
import markdown
from dateutil import tz
from shapely.geometry import Polygon, shape

import eodag
from eodag.api.core import DEFAULT_ITEMS_PER_PAGE, DEFAULT_PAGE
from eodag.api.product.metadata_mapping import OSEO_METADATA_MAPPING
from eodag.api.search_result import SearchResult
from eodag.config import load_stac_config
from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.rest.stac import StacCatalog, StacCollection, StacCommon, StacItem
from eodag.utils import dict_items_recursive_apply
from eodag.utils.exceptions import (
    MisconfiguredError,
    NoMatchingProductType,
    UnsupportedProductType,
    ValidationError,
)

eodag_api = eodag.EODataAccessGateway()
Cruncher = namedtuple("Cruncher", ["clazz", "config_params"])
crunchers = {
    "latestIntersect": Cruncher(FilterLatestIntersect, []),
    "latestByName": Cruncher(FilterLatestByName, ["name_pattern"]),
    "overlap": Cruncher(FilterOverlap, ["minimum_overlap"]),
}
stac_config = load_stac_config()


def format_product_types(product_types):
    """Format product_types

    :param list product_types: A list of EODAG product types as returned by the core api
    """
    result = []
    for pt in product_types:
        result.append("* *__{ID}__*: {abstract}".format(**pt))
    return "\n".join(sorted(result))


def get_detailled_collections_list(provider=None):
    """Returns detailled collections / product_types list for a given provider as a list of config dicts

    :param provider: chosen provider
    :type provider: str
    :returns: list of config dicts
    :rtype: list
    """
    return eodag_api.list_product_types(provider=provider)


def get_home_page_content(base_url, ipp=None):
    """Compute eodag service home page content

    :param base_url: the service root URL
    :param ipp: items per page number"""

    with open(os.path.join(os.path.dirname(__file__), "description.md"), "rt") as fp:
        content = fp.read()
    content = content.format(
        base_url=base_url,
        product_types=format_product_types(eodag_api.list_product_types()),
        ipp=ipp or DEFAULT_ITEMS_PER_PAGE,
    )
    content = markdown.markdown(content)
    return content


def get_templates_path():
    """Returns Jinja templates path"""
    return os.path.join(os.path.dirname(__file__), "templates")


def get_product_types(provider=None, filters=None):
    """Returns a list of supported product types
    :param provider: provider name
    :type provider: str
    :param filters: additional filters for product types search
    :type filters: dict
    :returns: a list of corresponding product types
    :rtype: list
    """
    if filters is None:
        filters = {}
    try:
        guessed_product_types = eodag_api.guess_product_type(
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
            for pt in eodag_api.list_product_types(provider=provider)
            if pt["ID"] in guessed_product_types
        ]
    else:
        product_types = eodag_api.list_product_types(provider=provider)
    return product_types


def search_bbox(request_bbox):
    """Transform request bounding box as a bbox suitable for eodag search"""

    eodag_bbox = None
    search_bbox_keys = ["lonmin", "latmin", "lonmax", "latmax"]

    if request_bbox:

        try:
            request_bbox_list = [float(coord) for coord in request_bbox.split(",")]
        except ValueError as e:
            raise ValidationError("invalid box coordinate type: %s" % e)

        eodag_bbox = dict(zip(search_bbox_keys, request_bbox_list))
        if len(eodag_bbox) != 4:
            raise ValidationError("input box is invalid: %s" % request_bbox)

    return eodag_bbox


def get_date(date):
    """Check if the input date can be parsed as a date"""

    if date:
        try:
            date = (
                dateutil.parser.parse(date)
                .replace(tzinfo=tz.UTC)
                .isoformat()
                .replace("+00:00", "")
            )
        except ValueError as e:
            exc = ValidationError("invalid input date: %s" % e)
            raise exc
    return date


def get_int(val):
    """Check if the input can be parsed as an integer"""

    if val:
        try:
            val = int(val)
        except ValueError as e:
            raise ValidationError("invalid input integer value: %s" % e)
    return val


def filter_products(products, arguments, **kwargs):
    """Apply an eodag cruncher to filter products"""
    filter_name = arguments.get("filter")
    if filter_name:
        cruncher = crunchers.get(filter_name)
        if not cruncher:
            raise ValidationError("unknown filter name")

        cruncher_config = dict()
        for config_param in cruncher.config_params:
            config_param_value = arguments.get(config_param)
            if not config_param_value:
                raise ValidationError(
                    "filter additional parameters required: %s"
                    % ", ".join(cruncher.config_params)
                )
            cruncher_config[config_param] = config_param_value

        try:
            products = products.crunch(cruncher.clazz(cruncher_config), **kwargs)
        except MisconfiguredError as e:
            raise ValidationError(e)

    return products


def get_pagination_info(arguments):
    """Get pagination arguments"""
    page = get_int(arguments.pop("page", DEFAULT_PAGE))
    # items_per_page can be specified using limit or itemsPerPage
    items_per_page = get_int(arguments.pop("limit", DEFAULT_ITEMS_PER_PAGE))
    items_per_page = get_int(arguments.pop("itemsPerPage", items_per_page))

    if page is not None and page < 0:
        raise ValidationError("invalid page number. Must be positive integer")
    if items_per_page is not None and items_per_page < 0:
        raise ValidationError(
            "invalid number of items per page. Must be positive integer"
        )
    return page, items_per_page


def get_geometry(arguments):
    """Get geometry from arguments"""

    geom = None

    if "bbox" in arguments or "box" in arguments:
        # get bbox
        request_bbox = arguments.pop("bbox", None) or arguments.pop("box", None)
        if request_bbox and isinstance(request_bbox, str):
            request_bbox = request_bbox.split(",")
        elif request_bbox and not isinstance(request_bbox, list):
            raise ValidationError("bbox argument type should be Array")

        try:
            request_bbox_list = [float(coord) for coord in request_bbox]
        except ValueError as e:
            raise ValidationError("invalid bbox coordinate type: %s" % e)
        # lonmin, latmin, lonmax, latmax
        if len(request_bbox_list) < 4:
            raise ValidationError(
                "invalid bbox length (%s) for bbox %s"
                % (len(request_bbox_list), request_bbox)
            )
        geom = Polygon(
            (
                (request_bbox_list[0], request_bbox_list[1]),
                (request_bbox_list[0], request_bbox_list[3]),
                (request_bbox_list[2], request_bbox_list[3]),
                (request_bbox_list[2], request_bbox_list[1]),
            )
        )

    if "intersects" in arguments and geom:
        new_geom = shape(arguments.pop("intersects"))
        if new_geom.intersects(geom):
            geom = new_geom.intersection(geom)
        else:
            geom = new_geom
    elif "intersects" in arguments:
        geom = shape(arguments.pop("intersects"))

    if "geom" in arguments and geom:
        new_geom = shape(arguments.pop("geom"))
        if new_geom.intersects(geom):
            geom = new_geom.intersection(geom)
        else:
            geom = new_geom
    elif "geom" in arguments:
        geom = shape(arguments.pop("geom"))

    return geom


def search_products(product_type, arguments):
    """Returns product search results

    :param product_type: the product type criteria
    :type product_type: str
    :param arguments: filter criteria
    :type arguments: dict
    :return: search result
    :rtype serialized GeoJSON response"""

    try:
        page, items_per_page = get_pagination_info(arguments)
        geom = get_geometry(arguments)

        criteria = {
            "geom": geom,
            "startTimeFromAscendingNode": get_date(arguments.pop("dtstart", None)),
            "completionTimeFromAscendingNode": get_date(arguments.pop("dtend", None)),
            "cloudCover": get_int(arguments.pop("cloudCover", None)),
            "productType": product_type,
        }
        if "id" in arguments.keys():
            criteria["id"] = arguments["id"]

        if items_per_page is None:
            items_per_page = DEFAULT_ITEMS_PER_PAGE
        if page is None:
            page = DEFAULT_PAGE

        unserialized = arguments.pop("unserialized", None)
        arguments.pop("product_type", None)

        products, total = eodag_api.search(
            page=page,
            items_per_page=items_per_page,
            raise_errors=True,
            **dict(criteria, **arguments),
        )

        products = filter_products(products, arguments, **criteria)

        if not unserialized:
            response = SearchResult(products).as_geojson_object()
            response.update(
                {
                    "properties": {
                        "page": page,
                        "itemsPerPage": items_per_page,
                        "totalResults": total,
                    }
                }
            )
        else:
            response = SearchResult(products)
            response.properties = {
                "page": page,
                "itemsPerPage": items_per_page,
                "totalResults": total,
            }

    except ValidationError as e:
        raise e
    except RuntimeError as e:
        raise e
    except UnsupportedProductType as e:
        raise e

    return response


def search_product_by_id(uid, product_type=None):
    """Search a product by its id

    :param uid: The uid of the EO product
    :type uid: str
    :param product_type: (optional) The product type
    :type product_type: str
    :returns: An search result
    :rtype: :class:`~eodag.api.search_result.SearchResult`
    :raises: :class:`~eodag.utils.exceptions.ValidationError`
    :raises: RuntimeError
    """
    try:
        products, total = eodag_api.search(id=uid, productType=product_type)
        # products, total = eodag_api.search(id=uid, productType=product_type, provider=provider, raise_errors=True)
        return products
    except ValidationError:
        raise
    except RuntimeError:
        raise


# STAC ------------------------------------------------------------------------


def get_stac_conformance():
    """Build STAC conformance

    :returns: conformance dictionnary
    :rtype: dict
    """
    return stac_config["conformance"]


def get_stac_collections(url, root, arguments, provider=None):
    """Build STAC collections

    :param url: requested URL
    :type url: str
    :param root: API root
    :type root: str
    :param arguments: request args
    :type arguments: dict
    :param provider: chosen provider
    :type provider: str
    :returns: collections dictionnary
    :rtype: dict
    """
    return StacCollection(
        url=url,
        stac_config=stac_config,
        provider=provider,
        eodag_api=eodag_api,
        root=root,
    ).get_collections(arguments)


def get_stac_collection_by_id(url, root, collection_id, provider=None):
    """Build STAC collection by id

    :param url: requested URL
    :type url: str
    :param root: API root
    :type root: str
    :param collection_id: product_type as ID of the collection
    :type collection_id: str
    :param provider: chosen provider
    :type provider: str
    :returns: collection dictionnary
    :rtype: dict
    """
    return StacCollection(
        url=url,
        stac_config=stac_config,
        provider=provider,
        eodag_api=eodag_api,
        root=root,
    ).get_collection_by_id(collection_id)


def get_stac_item_by_id(url, item_id, root="/", catalogs=[], provider=None):
    """Build STAC item by id

    :param url: requested URL
    :type url: str
    :param root: API root
    :type root: str
    :param item_id: product ID
    :type item_id: str
    :param catalogs: catalogs list (only first is used as product_type)
    :type catalogs: list
    :param provider: chosen provider
    :type provider: str
    :returns: collection dictionnary
    :rtype: dict
    """
    product_type = catalogs[0]
    found_products = search_product_by_id(item_id, product_type=product_type)
    if len(found_products) > 0:
        return StacItem(
            url=url,
            stac_config=stac_config,
            provider=provider,
            eodag_api=eodag_api,
            root=root,
        ).get_stac_item_from_product(product=found_products[0])
    else:
        return None


def download_stac_item_by_id(catalogs, item_id, provider=None):
    """Download item

    :param catalogs: catalogs list (only first is used as product_type)
    :type catalogs: list
    :param item_id: product ID
    :type item_id: str
    :param provider: chosen provider
    :type provider: str
    :returns: downloaded item local path
    :rtype: str
    """
    if provider:
        eodag_api.set_preferred_provider(provider)

    product = search_product_by_id(item_id, product_type=catalogs[0])[0]

    eodag_api.providers_config[product.provider].download.extract = False

    product_path = eodag_api.download(product)

    return product_path


def get_stac_catalogs(url, root="/", catalogs=[], provider=None):
    """Build STAC catalog

    :param url: requested URL
    :type url: str
    :param root: API root
    :type root: str
    :param catalogs: catalogs list
    :type catalogs: list
    :param provider: chosen provider
    :type provider: str
    :returns: catalog dictionnary
    :rtype: dict
    """
    return StacCatalog(
        url=url,
        stac_config=stac_config,
        root=root,
        provider=provider,
        eodag_api=eodag_api,
        catalogs=catalogs,
    ).get_stac_catalog()


def search_stac_items(url, arguments, root="/", catalogs=[], provider=None):
    """Get items collection dict for given catalogs list

    :param url: requested URL
    :type url: str
    :param arguments: request args
    :type arguments: dict
    :param root: API root
    :type root: str
    :param catalogs: catalogs list
    :type catalogs: list
    :param provider: chosen provider
    :type provider: str
    :returns: catalog dictionnary
    :rtype: dict
    """
    collections = arguments.get("collections", None)

    catalog_url = url.replace("/items", "")

    # use catalogs from path or if it is empty, collections from args
    if catalogs:
        result_catalog = StacCatalog(
            url=catalog_url,
            stac_config=stac_config,
            root=root,
            provider=provider,
            eodag_api=eodag_api,
            catalogs=catalogs,
        )
    elif collections:
        # get collection as product_type
        if isinstance(collections, str):
            collections = collections.split(",")
        elif not isinstance(collections, list):
            raise ValidationError("Collections argument type should be Array")

        result_catalog = StacCatalog(
            url=catalog_url,
            stac_config=stac_config,
            root=root,
            provider=provider,
            eodag_api=eodag_api,
            # handle only one collection per request (STAC allows multiple)
            catalogs=collections[0:1],
        )
        arguments.pop("collections")
    else:
        raise NoMatchingProductType("No product_type found in collections argument")

    # get id
    ids = arguments.get("ids", None)
    if ids:
        # handle only one id per request (STAC allows multiple)
        arguments["id"] = ids.split(",")[0]
        arguments.pop("ids")

    # get datetime
    if "datetime" in arguments.keys():
        dtime_split = arguments.get("datetime", "").split("/")
        if len(dtime_split) > 1:
            arguments["dtstart"] = (
                dtime_split[0]
                if dtime_split[0] != ".."
                else datetime.datetime.min.isoformat() + "Z"
            )
            arguments["dtend"] = (
                dtime_split[1]
                if dtime_split[1] != ".."
                else datetime.datetime.now(datetime.timezone.utc)
                .isoformat()
                .replace("+00:00", "")
                + "Z"
            )
        elif len(dtime_split) == 1:
            # same time for start & end if only one is given
            arguments["dtstart"], arguments["dtend"] = dtime_split[0:1] * 2
        arguments.pop("datetime")

    search_results = search_products(
        product_type=result_catalog.search_args["product_type"],
        arguments=dict(
            arguments, **result_catalog.search_args, **{"unserialized": "true"}
        ),
    )

    return StacItem(
        url=url,
        stac_config=stac_config,
        provider=provider,
        eodag_api=eodag_api,
        root=root,
    ).get_stac_items(
        search_results=search_results,
        catalog=dict(
            result_catalog.get_stac_catalog(),
            **{"url": result_catalog.url, "root": result_catalog.root},
        ),
    )


def get_stac_extension_oseo(url):
    """Build STAC OGC / OpenSearch Extension for EO

    :param url: requested URL
    :type url: str
    :returns: catalog dictionnary
    :rtype: dict
    """

    item_mapping = dict_items_recursive_apply(
        stac_config["item"], lambda _, x: str(x).replace("$.product.", "$.")
    )

    # all properties as string type by default
    oseo_properties = {
        "oseo:{}".format(k): {
            "type": "string",
            "title": k[0].upper() + re.sub(r"([A-Z][a-z]+)", r" \1", k[1:]),
        }
        for k, v in OSEO_METADATA_MAPPING.items()
        if v not in str(item_mapping)
    }

    return StacCommon.get_stac_extension(
        url=url, stac_config=stac_config, extension="oseo", properties=oseo_properties
    )
