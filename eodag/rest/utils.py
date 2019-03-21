# -*- coding: utf-8 -*-
# Copyright 2017-2018 CS Systemes d'Information (CS SI)
# All rights reserved

import os
from collections import namedtuple

import dateutil.parser
import eodag
import markdown
from eodag.api.core import DEFAULT_ITEMS_PER_PAGE, DEFAULT_PAGE
from eodag.api.search_result import SearchResult
from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.utils.exceptions import (
    ValidationError,
    MisconfiguredError,
    UnsupportedProductType,
)

eodag_api = eodag.EODataAccessGateway()
Cruncher = namedtuple("Cruncher", ["clazz", "config_params"])
crunchers = {
    "latestIntersect": Cruncher(FilterLatestIntersect, []),
    "latestByName": Cruncher(FilterLatestByName, ["name_pattern"]),
    "overlap": Cruncher(FilterOverlap, ["minimum_overlap"]),
}


def format_product_types(product_types):
    """Format product_types

    :param list product_types: A list of EODAG product types as returned by the core api
    """
    result = []
    for pt in product_types:
        result.append("* *__{ID}__*: {desc}".format(**pt))
    return "\n".join(sorted(result))


def get_home_page_content(base_url, ipp):
    """Compute eodag service home page content

    :param base_url: the service root URL
    :param ipp: items per page number"""

    with open(os.path.join(os.path.dirname(__file__), "description.md"), "rt") as fp:
        content = fp.read()
    content = content.format(
        base_url=base_url,
        product_types=format_product_types(eodag_api.list_product_types()),
        ipp=DEFAULT_ITEMS_PER_PAGE,
    )
    content = markdown.markdown(content)
    return content


def get_templates_path():
    """Returns Jinja templates path"""
    return os.path.join(os.path.dirname(__file__), "templates")


def get_product_types():
    """Returns a list of supported product types"""
    return eodag_api.list_product_types()


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
            date = dateutil.parser.parse(date).isoformat()
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
    page = get_int(arguments.get("page", DEFAULT_PAGE))
    items_per_page = get_int(arguments.get("itemsPerPage", DEFAULT_ITEMS_PER_PAGE))
    if page is not None and page < 0:
        raise ValidationError("invalid page number. Must be positive integer")
    if items_per_page is not None and items_per_page < 0:
        raise ValidationError(
            "invalid number of items per page. Must be positive integer"
        )
    return page, items_per_page


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
        criteria = {
            "geometry": search_bbox(arguments.get("box")),
            "startTimeFromAscendingNode": get_date(arguments.get("dtstart")),
            "completionTimeFromAscendingNode": get_date(arguments.get("dtend")),
            "cloudCover": get_int(arguments.get("cloudCover")),
        }

        if items_per_page is None:
            items_per_page = DEFAULT_ITEMS_PER_PAGE
        if page is None:
            page = DEFAULT_PAGE
        products, total = eodag_api.search(
            product_type,
            page=page,
            items_per_page=items_per_page,
            raise_errors=True,
            **criteria
        )

        products = filter_products(products, arguments, **criteria)
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

    except ValidationError as e:
        raise e
    except RuntimeError as e:
        raise e
    except UnsupportedProductType as e:
        raise e

    return response
