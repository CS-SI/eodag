import datetime
import math
from typing import Any, Optional

import requests
from pyproj import CRS, Transformer

from eodag.api.product._assets import Asset, AssetsDict
from eodag.api.product._product import EOProduct
from eodag.api.product.metadata_mapping import (
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
)
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.base import Search
from eodag.utils import HTTP_REQ_TIMEOUT
from eodag.utils.exceptions import (
    MisconfiguredError,
    RequestError,
    TimeOutError,
    ValidationError,
)

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
    },
    "GHS_ESM_2015": {"filters": {"resolution": ["2m", "10m"]}},
}


def _check_input_parameters_valid(product_type: str, **kwargs: Any):
    """
    Check if all required parameters are given and if the values are valid
    raises a ValidationError if this is not the case
    """
    all_filters = available_values[product_type]["filters"]
    all_filters.update(available_values[product_type].get("additional_filters", {}))
    required_params = set(all_filters.keys())
    given_params = set(kwargs.keys())
    missing_params = required_params - given_params
    if missing_params:
        raise ValidationError(
            f"Invalid request - missing filter parameters {missing_params}"
        )
    for param in given_params:
        if param not in required_params:
            if param != "geometry":
                raise ValidationError(
                    f"Parameter {param} does not exist; available parameters: {required_params}"
                )
        elif kwargs[param] not in all_filters[param]:
            raise ValidationError(
                f"Parameter {param} does not have value {kwargs[param]} for product type {product_type}; \
                                    available values: {all_filters[param]}"
            )


def _convert_bbox_to_lonlat_mollweide(bbox: list[str]) -> list[float]:
    """
    convert a bbox from Mollweide coordinate system (metres)
    to WGS84 coordinate system (longitude and latitude)
    """
    bbox_int = [int(x.replace(" ", "")) for x in bbox]
    crs_mollweide = CRS("ESRI:54009")
    crs_wgs84 = CRS("WGS84")
    transformer = Transformer.from_crs(crs_from=crs_mollweide, crs_to=crs_wgs84)
    x1, y1 = bbox_int[:2]
    lat1, lon1 = transformer.transform(x1, y1)
    if math.isinf(lat1):
        # one corner is outside of the surface -> find latitude and take max longitude value
        lat1, _ = transformer.transform(0, y1)
        lon1 = -180 if x1 < 0 else 180
    x2, y2 = bbox_int[2:]
    lat2, lon2 = transformer.transform(x2, y2)
    if math.isinf(lat2):
        lat2, _ = transformer.transform(0, y2)
        lon2 = -180 if x1 < 0 else 180
    return [lon1, lat1, lon2, lat2]


def _convert_bbox_to_lonlat_EPSG3035(bbox: list[str]) -> list[float]:
    """
    convert a bbox from ETRS89/LAEA Europe (EPSG:3035) coordinate system (metres)
    to WGS84 coordinate system (longitude and latitude)
    """
    bbox_int = [int(x.replace(",", "")) for x in bbox]
    crs_3035 = CRS("3035")
    crs_wgs84 = CRS("WGS84")
    transformer = Transformer.from_crs(
        crs_from=crs_3035, crs_to=crs_wgs84, always_xy=True
    )
    x1, y1 = bbox_int[:2]
    lat1, lon1 = transformer.transform(x1, y1)
    x2, y2 = bbox_int[2:]
    lat2, lon2 = transformer.transform(x2, y2)
    return [lon1, lat1, lon2, lat2]


class CopGhslSearch(Search):
    """
    Search plugin to fetch items from Copernicus Global Human Settlement Layer
    """

    def _create_products_from_tiles(
        self,
        tiles: list[dict[str, Any]],
        unit: str,
        product_type: str,
        params: dict[str, Any],
        additional_filter: Optional[str] = None,
    ) -> list[EOProduct]:
        """
        create EOProduct objects from the input parameters and the tiles containing bboxes
        if the bbox is given in metres, it is transformed to longitude and latitude
        """
        products = []
        properties = params
        properties["startTimeFromAscendingNode"] = datetime.datetime(
            year=int(params["year"]), month=1, day=1
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        properties["completionTimeFromAscendingNode"] = datetime.datetime(
            year=int(params["year"]), month=12, day=31
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        filter_geometry = params.pop("geometry", None)

        # information for id and download path
        metadata_mapping = params.pop("metadata_mapping", {})
        dataset = metadata_mapping.get("dataset", None)
        if not dataset:
            raise MisconfiguredError(
                f"dataset mapping not available for {product_type}"
            )
        format_params = params
        # format resolution
        parsed_metadata_mapping = mtd_cfg_as_conversion_and_querypath(metadata_mapping)
        resolution = properties_from_json(
            {"resolution": params["resolution"]}, parsed_metadata_mapping
        )["resolution"]
        format_params.update({"resolution": resolution})
        # additional filter
        if additional_filter:
            add_filter_value = format_params.pop(additional_filter)
            if add_filter_value == "TOTAL":
                add_filter_value = ""
            format_params.update({"add_filter": add_filter_value})
        dataset = dataset.format(**format_params)
        dataset = dataset.replace("__", "_")  # in case additional filter value is empty
        # create items from tiles
        for tile in tiles:
            if not tile:  # empty grid position
                continue
            # get geometry from tile
            if unit == "lat/lon":  # bbox is given as latitude/longitude
                properties["geometry"] = tile["BBox"]
            elif unit == "metres" and "BBox" in tile:  # bbox is given in metres
                bbox_lon_lat = _convert_bbox_to_lonlat_mollweide(tile["BBox"])
                properties["geometry"] = bbox_lon_lat
            else:
                bbox_lon_lat = _convert_bbox_to_lonlat_EPSG3035(tile["BBox_3035"])
                properties["geometry"] = bbox_lon_lat
            # create id
            product_id = f"{dataset}_{tile['tileID']}"
            properties["id"] = properties["title"] = product_id
            downloadLink = metadata_mapping.get("downloadLink").format(
                dataset=dataset, tile_id=tile["tileID"]
            )
            properties["downloadLink"] = downloadLink
            product = EOProduct(
                provider="cop_ghsl", properties=properties, productType=product_type
            )
            assets = AssetsDict(product=product)
            assets[tile["tileID"]] = Asset(
                product=product, key=tile["tileID"], href=downloadLink
            )
            product.assets = assets
            if not filter_geometry or filter_geometry.intersects(product.geometry):
                products.append(product)

        return products

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
        print(page, items_per_page)

        start_time = kwargs.pop("startTimeFromAscendingNode", None)
        end_time = kwargs.pop("completionTimeFromAscendingNode", None)
        if "year" not in kwargs:
            if start_time:
                kwargs["year"] = start_time[:4]
            elif end_time:
                kwargs["year"] = end_time[:4]
        _check_input_parameters_valid(product_type, **kwargs)

        product_type_config = self.config.products.get(product_type, {})
        provider_product_type = product_type_config.get("productType", None)
        if not provider_product_type:
            raise MisconfiguredError(
                f"provider productType mapping not available for {product_type}"
            )
        filter_params = kwargs
        filter_params.update(product_type_config)
        filter_str = (
            f"{provider_product_type}_{filter_params['year']}_"
            f"{filter_params['resolution']}_{filter_params['coord_system']}"
        )
        tiles_url = self.config.api_endpoint + "/tilesDLD_" + filter_str + ".json"
        try:
            res = requests.get(tiles_url, verify=ssl_verify, timeout=timeout)
            tiles = res.json()["grid"]
            if filter_params["coord_system"] == 3035:
                tiles = []
                for t_id, bbox in res.json()["BBoxes"].items():
                    tiles.append({"tileID": t_id, "BBox_3035": bbox})
            unit = res.json().get("unit", "")
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=timeout) from exc
        except requests.exceptions.RequestException as exc:
            raise RequestError.from_error(exc, f"Unable to fetch {tiles_url}") from exc

        additional_filters = list(
            available_values[product_type].get("additional_filters", {}).keys()
        )
        if len(additional_filters) > 0:
            products = self._create_products_from_tiles(
                tiles,
                unit,
                product_type,
                kwargs,
                additional_filter=additional_filters[0],
            )
        else:
            products = self._create_products_from_tiles(
                tiles, unit, product_type, kwargs
            )

        return products, None
