import datetime
import math
from typing import Annotated, Any, Optional

import requests
from pydantic.fields import FieldInfo
from pyproj import CRS, Transformer
from typing_extensions import get_args

from eodag.api.product._assets import Asset, AssetsDict
from eodag.api.product._product import EOProduct
from eodag.api.product.metadata_mapping import (
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
)
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.base import Search
from eodag.types import json_field_definition_to_python
from eodag.types.queryables import Queryables
from eodag.utils import HTTP_REQ_TIMEOUT, deepcopy
from eodag.utils.exceptions import (
    MisconfiguredError,
    RequestError,
    TimeOutError,
    ValidationError,
)

constraints_filters = {
    "GHS_BUILT_S": {
        "constraints": [
            {
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
                "tile_size": ["10m", "100m", "1k"],
                "coord_system": ["54009"],
                "classification": ["TOTAL", "NRES"],
            },
            {
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
                "tile_size": ["3ss", "30ss"],
                "coord_system": ["4326"],
                "classification": ["TOTAL", "NRES"],
            },
        ],
        "additional_filter": "classification",
    },
    "GHS_ESM_2015": {
        "constraints": [
            {"year": ["2015"], "tile_size": ["2m", "10m"], "coord_system": ["3035"]}
        ]
    },
}


def _check_input_parameters_valid(product_type: str, params: Any):
    """
    Check if all required parameters are given and if the values are valid
    raises a ValidationError if this is not the case
    """
    constraints_values = constraints_filters[product_type]["constraints"]
    # get available values - will raise error if wrong parameters or wrong parameter values in request
    available_values = _get_available_values_from_constraints(
        constraints_values, params, product_type
    )
    missing_params = set(available_values.keys()) - set(params.keys())
    if missing_params:
        raise ValidationError(f"parameter(s) {missing_params} missing in the request")


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


def _get_available_values_from_constraints(
    constraints: list[dict[str, Any]], filters: dict[str, Any], product_type: str
) -> dict[str, list[Any]]:
    available_values = {}
    constraint_keys = set([k for const in constraints for k in const.keys()])
    not_found_keys = set(filters.keys()) - constraint_keys
    if not_found_keys:
        raise ValidationError(
            f"Parameters {not_found_keys} do not exist for product type {product_type}; "
            f"available parameters: {constraint_keys}"
        )

    filtered_constraints = deepcopy(constraints)
    for filter_key, value in filters.items():
        available_values_key = []
        for i, constraint in enumerate(constraints):
            if constraint not in filtered_constraints:
                continue
            if filter_key in constraint:
                available_values_key.extend(constraint[filter_key])
                if (
                    value not in constraint[filter_key]
                    and str(value) not in constraint[filter_key]
                ):
                    filtered_constraints.remove(constraint)
            if len(filtered_constraints) == 0:
                raise ValidationError(
                    f"Value {value} is not available for parameter {filter_key} with the given parameter values; "
                    f"available values: {set(available_values_key)}"
                )

    for constraint in filtered_constraints:
        for key, values in constraint.items():
            if key in available_values:
                available_values[key].extend(values)
            else:
                available_values[key] = values

    return available_values


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
    ) -> tuple[list[EOProduct], int]:
        """
        create EOProduct objects from the input parameters and the tiles containing bboxes
        if the bbox is given in metres, it is transformed to longitude and latitude
        """
        products = []
        metadata_mapping = params.pop("metadata_mapping", {})
        parsed_metadata_mapping = mtd_cfg_as_conversion_and_querypath(metadata_mapping)

        properties = deepcopy(params)
        properties["startTimeFromAscendingNode"] = datetime.datetime(
            year=int(params["year"]), month=1, day=1
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        properties["completionTimeFromAscendingNode"] = datetime.datetime(
            year=int(params["year"]), month=12, day=31
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        filter_geometry = params.pop("geometry", None)
        page = params.pop("page")
        per_page = params.pop("per_page")
        start_index = per_page * (page - 1)
        end_index = start_index + per_page - 1

        # information for id and download path
        dataset = metadata_mapping.get("dataset", None)
        if not dataset:
            raise MisconfiguredError(
                f"dataset mapping not available for {product_type}"
            )
        format_params = params
        # format tile_size
        tile_size = properties_from_json(
            {"tile_size": params["tile_size"]}, parsed_metadata_mapping
        )["tile_size"]
        format_params.update({"tile_size": tile_size})
        # additional filter
        if additional_filter:
            add_filter_value = format_params.pop(additional_filter)
            if add_filter_value == "TOTAL":
                add_filter_value = ""
            format_params.update({"add_filter": add_filter_value})
        dataset = dataset.format(**format_params)
        dataset = dataset.replace("__", "_")  # in case additional filter value is empty

        # create items from tiles
        current_index = 0
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
                product=product,
                key=tile["tileID"],
                href=downloadLink,
                title=tile["tileID"],
                type="application/zip",
            )
            product.assets = assets
            if not filter_geometry or filter_geometry.intersects(product.geometry):
                if current_index >= start_index and current_index <= end_index:
                    products.append(product)
                current_index += 1

        return products, current_index + 1

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

        # get year from start/end time if not given separately
        start_time = kwargs.pop("startTimeFromAscendingNode", None)
        end_time = kwargs.pop("completionTimeFromAscendingNode", None)
        if "year" not in kwargs:
            if start_time:
                kwargs["year"] = start_time[:4]
            elif end_time:
                kwargs["year"] = end_time[:4]

        # update filters with values from product type mapping
        product_type_config = deepcopy(self.config.products.get(product_type, {}))
        provider_product_type = product_type_config.pop("productType", None)
        if not provider_product_type:
            raise MisconfiguredError(
                f"provider productType mapping not available for {product_type}"
            )
        filter_params = deepcopy(kwargs)
        filter_params.pop("geometry", None)
        filter_params.update(product_type_config)
        filter_params.pop("metadata_mapping")

        _check_input_parameters_valid(product_type, filter_params)

        # fetch available tiles based on filters
        filter_str = (
            f"{provider_product_type}_{filter_params['year']}_"
            f"{filter_params['tile_size']}_{filter_params['coord_system']}"
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

        # create products from tiles
        kwargs.update(product_type_config)
        kwargs["page"] = page
        kwargs["per_page"] = items_per_page
        additional_filter = constraints_filters[product_type].get(
            "additional_filter", None
        )
        if additional_filter:
            products, count = self._create_products_from_tiles(
                tiles,
                unit,
                product_type,
                kwargs,
                additional_filter=additional_filter,
            )
        else:
            products, count = self._create_products_from_tiles(
                tiles, unit, product_type, kwargs
            )
        if prep.count:
            return products, count
        else:
            return products, None

    def discover_queryables(
        self, **kwargs
    ) -> Optional[dict[str, Annotated[Any, FieldInfo]]]:
        """Create queryables list based on constraints

        :param kwargs: additional filters for queryables (`productType` and other search
                       arguments)
        :returns: queryable parameters dict
        """

        product_type = kwargs.pop("productType")
        constraints_values = constraints_filters[product_type]["constraints"]
        available_values = _get_available_values_from_constraints(
            constraints_values, kwargs, product_type
        )
        queryables = {}
        for name, values in available_values.items():
            queryables[name] = Annotated[
                get_args(
                    json_field_definition_to_python(
                        {"type": "string", "title": name, "enum": values},
                        default_value=kwargs.get(name, None),
                        required=True,
                    )
                )
            ]
        # add datetimes and geometry
        queryables.update(
            {
                "start": Queryables.get_with_default(
                    "start", kwargs.get("startTimeFromAscendingNode")
                ),
                "end": Queryables.get_with_default(
                    "end",
                    kwargs.get("completionTimeFromAscendingNode"),
                ),
                "geom": Queryables.get_with_default("geom", None),
            }
        )
        return queryables
