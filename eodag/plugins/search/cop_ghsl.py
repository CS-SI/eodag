import datetime
from typing import Any, Optional

import requests

from eodag.api.product._product import EOProduct
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.base import Search
from eodag.utils import HTTP_REQ_TIMEOUT
from eodag.utils.exceptions import RequestError, TimeOutError, ValidationError

available_values = {
    "GHS_BUILT_S": {
        "filters": {
            "year": [
                "2030",
                "2025",
                "2020",
                "2015",
                "2018",
                "2010",
                "2005",
                "2000",
                "1995",
                "1990",
                "1985",
                "1980",
                "1975",
            ],
            "resolution": [
                "10m",
                "100m",
                "1k",
                "3ss",
                "30ss",
            ],
            "coord_system": ["54009", "4326"],
        },
        "additional_filters": {"classification": ["TOTAL", "NRES"]},
    }
}


def _check_input_parameters_valid(product_type: str, **kwargs: Any):
    """
    Check if all required parameters are given and if the values are valid
    raises a ValidationError if this is not the case
    """
    all_filters = available_values[product_type]["filters"]
    all_filters.update(available_values[product_type]["additional_filters"])
    required_params = set(all_filters.keys())
    given_params = set(kwargs.keys())
    missing_params = required_params - given_params
    if missing_params:
        raise ValidationError(
            f"Invalid request - missing filter parameters {missing_params}"
        )
    for param in given_params:
        if param not in required_params:
            raise ValidationError(
                f"Parameter {param} does not exist; available parameters: {required_params}"
            )
        elif kwargs[param] not in all_filters[param]:
            raise ValidationError(
                f"Parameter {param} does not have value {kwargs[param]} for product type {product_type}; \
                                    available values: {all_filters[param]}"
            )


def _create_products_from_tiles(
    tiles: list[dict[str, Any]], unit: str, product_type: str, params: dict[str, Any]
) -> list[EOProduct]:
    products = []
    properties = params
    properties["startTimeFromAscendingNode"] = datetime.datetime(
        year=int(params["year"]), month=1, day=1
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    properties["completionTimeFromAscendingNode"] = datetime.datetime(
        year=int(params["year"]), month=12, day=31
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    for tile in tiles:
        if not tile:  # empty grid position
            continue
        if unit == "lat/lon":  # bbox is given as latitude/longitude
            properties["geometry"] = tile["BBox"]
            product = EOProduct(
                provider="cop_ghsl", properties=properties, productType=product_type
            )
            products.append(product)
    return products


class CopGhslSearch(Search):
    """
    Search plugin to fetch items from Copernicus Global Human Settlement Layer
    """

    def query(
        self,
        prep: PreparedSearch = PreparedSearch(),
        **kwargs: Any,
    ) -> tuple[list[EOProduct], Optional[int]]:
        """
        Implementation of search for the Copernicus GHSL provider
        :param prep: object containing search parameters
        :param kwargs: additional search arguments
        :returns: list of products and total number of products
        """
        page = prep.page
        items_per_page = prep.items_per_page
        ssl_verify = getattr(self.config, "ssl_verify", True)
        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
        product_type = kwargs.pop("productType", prep.product_type)
        geometry = kwargs.pop("geometry")
        print(page, items_per_page, geometry)

        start_time = kwargs.pop("startTimeFromAscendingNode", None)
        end_time = kwargs.pop("completionTimeFromAscendingNode", None)
        if "year" not in kwargs:
            if start_time:
                kwargs["year"] = start_time[:4]
            elif end_time:
                kwargs["year"] = end_time[:4]
        _check_input_parameters_valid(product_type, **kwargs)

        provider_product_type = self.config.products.get(product_type, {}).get(
            "productType", None
        )
        filter_str = f"{provider_product_type}_{kwargs['year']}_{kwargs['resolution']}_{kwargs['coord_system']}"
        tiles_url = self.config.api_endpoint + "/tilesDLD_" + filter_str + ".json"
        try:
            res = requests.get(tiles_url, verify=ssl_verify, timeout=timeout)
            tiles = res.json()["grid"]
            unit = res.json()["unit"]
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=timeout) from exc
        except requests.exceptions.RequestException as exc:
            raise RequestError.from_error(exc, f"Unable to fetch {tiles_url}") from exc

        products = _create_products_from_tiles(tiles, unit, product_type, kwargs)

        return products, None
