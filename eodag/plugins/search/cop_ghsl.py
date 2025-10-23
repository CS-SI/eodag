import datetime
import logging
import math
from calendar import monthrange
from typing import Annotated, Any, Optional

import requests
from pydantic.fields import FieldInfo
from pyproj import CRS, Transformer
from typing_extensions import get_args

from eodag.api.product._assets import AssetsDict
from eodag.api.product._product import EOProduct
from eodag.api.product.metadata_mapping import (
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
)
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.base import Search
from eodag.types import json_field_definition_to_python
from eodag.types.queryables import Queryables
from eodag.utils import DEFAULT_ITEMS_PER_PAGE, HTTP_REQ_TIMEOUT, deepcopy
from eodag.utils.cache import instance_cached_method
from eodag.utils.exceptions import (
    MisconfiguredError,
    RequestError,
    TimeOutError,
    ValidationError,
)

logger = logging.getLogger("eodag.search.cop_ghsl")


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
    lon1, lat1 = transformer.transform(x1, y1)
    x2, y2 = bbox_int[2:]
    lon2, lat2 = transformer.transform(x2, y2)
    return [lon1, lat1, lon2, lat2]


def _get_available_values_from_constraints(
    constraints: list[dict[str, Any]], filters: dict[str, Any], product_type: str
) -> dict[str, list[Any]]:
    """get the available values for each parameter from the constraints"""
    available_values: dict[str, list[Any]] = {}
    constraint_keys = set([k for const in constraints for k in const.keys()])
    not_found_keys = set(filters.keys()) - constraint_keys
    if "month" in not_found_keys and isinstance(filters["month"], list):
        # month added from datetime but filter not available
        filters.pop("month")
        not_found_keys.remove("month")
    if not_found_keys and not_found_keys != {"id"}:
        raise ValidationError(
            f"Parameters {not_found_keys} do not exist for product type {product_type}; "
            f"available parameters: {constraint_keys}"
        )

    filtered_constraints = deepcopy(constraints)
    for filter_key, value in filters.items():
        available_values_key = []
        values_in_constraints = []
        for i, constraint in enumerate(constraints):
            if constraint not in filtered_constraints:
                continue
            if filter_key in constraint and isinstance(value, list):
                for v in value:
                    if v in constraint[filter_key]:
                        values_in_constraints.append(v)

            elif filter_key in constraint:
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

        if not values_in_constraints and isinstance(value, list):
            constraints_values = []
            for const in constraints:
                constraints_values.extend(const[filter_key])
            raise ValidationError(
                f"No values for {filter_key} available in given range; available values {set(constraints_values)}"
            )

    for constraint in filtered_constraints:
        for key, values in constraint.items():
            filter_values = values
            if key in filters and isinstance(filters[key], list):
                filter_values = list(set(filters[key]).intersection(set(values)))
            if key in available_values:
                available_values[key].extend(filter_values)
            else:
                available_values[key] = filter_values

    return available_values


def _replace_datetimes(params: dict[str, Any]):
    """replace datetimes by year/month"""
    start_date_str = params.pop("start_datetime", None)
    end_date_str = params.pop("end_datetime", None)
    if start_date_str and not end_date_str:
        end_date_str = start_date_str
    if end_date_str and not start_date_str:
        start_date_str = end_date_str

    if not start_date_str:
        return

    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%dT%H:%M:%SZ")
        end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d")
    start_year = start_date.year
    end_year = end_date.year
    years = [str(y) for y in range(start_year, end_year + 1)]
    if "year" not in params:
        params["year"] = years

    if start_year == end_year and "month" not in params:
        # month is only used for collection where only one year is available
        start_month = start_date.month
        end_month = end_date.month
        months = [f"{m:02}" for m in range(start_month, end_month + 1)]
        params["month"] = months


class CopGhslSearch(Search):
    """
    Search plugin to fetch items from Copernicus Global Human Settlement Layer
    """

    def _check_input_parameters_valid(self, product_type: str, params: Any):
        """
        Check if all required parameters are given and if the values are valid
        raises a ValidationError if this is not the case
        """
        constraints_data = self._fetch_constraints(product_type)
        constraints_values = constraints_data["constraints"]
        # get available values - will raise error if wrong parameters or wrong parameter values in request
        grouped_by = params.pop("grouped_by", None)
        available_values = _get_available_values_from_constraints(
            constraints_values, params, product_type
        )
        if grouped_by and grouped_by not in params:
            params[grouped_by] = available_values[grouped_by]
        missing_params = set(available_values.keys()) - set(params.keys())
        if missing_params:
            raise ValidationError(
                f"parameter(s) {missing_params} missing in the request"
            )
        # update lists in params with available values
        for param in params:
            if isinstance(params[param], list):
                params[param] = sorted(available_values[param])

    def _get_start_and_end_from_properties(
        self, properties: dict[str, Any]
    ) -> dict[str, str]:
        """get the start and end time from year/month in the properties or missionStart/EndDate"""
        if "month" in properties:
            start_date = datetime.datetime(
                year=int(properties["year"]),
                month=int(properties["month"]),
                day=1,
                hour=0,
                minute=0,
                second=0,
            )
            end_day = monthrange(int(properties["year"]), int(properties["month"]))[1]
            end_date = datetime.datetime(
                year=int(properties["year"]),
                month=int(properties["month"]),
                day=end_day,
                hour=23,
                minute=59,
                second=59,
            )
        elif "year" in properties:
            start_date = datetime.datetime(
                year=int(properties["year"]), month=1, day=1, hour=0, minute=0, second=0
            )
            end_date = datetime.datetime(
                year=int(properties["year"]),
                month=12,
                day=31,
                hour=23,
                minute=59,
                second=59,
            )
        else:
            interval = self.get_collection_cfg_value("extent")["temporal"]["interval"]
            start_date_str = interval[0][0]
            end_date_str = interval[0][1]
            return {"start_date": start_date_str, "end_date": end_date_str}

        result = {}
        result["start_date"] = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        result["end_date"] = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        return result

    def _create_products_from_tiles(
        self,
        tiles: dict[str, list[dict[str, Any]]],
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

        filter_geometry = params.pop("geometry", None)
        page = params.pop("page")
        per_page = params.pop("per_page")
        start_index = per_page * (page - 1)
        end_index = start_index + per_page - 1

        # parameters that need formatting
        dataset = metadata_mapping.get("dataset", None)
        if not dataset:
            raise MisconfiguredError(
                f"dataset mapping not available for {product_type}"
            )
        id_params = deepcopy(params)
        if "tile_size" in parsed_metadata_mapping:
            # format tile_size
            tile_size = properties_from_json(
                {"tile_size": params["tile_size"]}, parsed_metadata_mapping
            )["tile_size"]
            params.update({"tile_size": tile_size})

        # additional filter
        if additional_filter:
            add_filter_value = params.pop(additional_filter)
            if add_filter_value == "TOTAL":
                params.update({"add_filter": ""})
            else:
                params.update({"add_filter": add_filter_value})

        if isinstance(params["year"], int) or isinstance(params["year"], str):
            list_years = [str(params["year"])]
        else:
            list_years = params["year"]
        current_index = 0
        for year in list_years:
            properties = deepcopy(params)
            properties["start_datetime"] = datetime.datetime(
                year=int(year), month=1, day=1
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            properties["end_datetime"] = datetime.datetime(
                year=int(year), month=12, day=31, hour=23, minute=59, second=59
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            properties["year"] = year

            # information for id and download path
            id_params["year"] = year
            id_params = {k: str(v) for k, v in id_params.items()}
            product_id_base = (
                product_type + "__" + "_".join(v for v in id_params.values() if v)
            )

            dataset = dataset.format(**params)
            dataset = dataset.replace(
                "__", "_"
            )  # in case additional filter value is empty

            # create items from tiles
            for tile in tiles[year]:
                if not tile:  # empty grid position
                    continue
                # get geometry from tile
                if unit == "lat/lon":  # bbox is given as latitude/longitude
                    properties["geometry"] = tile["BBox"]
                elif unit == "metres" and "BBox" in tile:  # bbox is given in metres
                    bbox_lon_lat = _convert_bbox_to_lonlat_mollweide(tile["BBox"])
                    properties["geometry"] = bbox_lon_lat
                else:  # ETRS89/LAEA Europe coordinate system
                    bbox_lon_lat = _convert_bbox_to_lonlat_EPSG3035(tile["BBox_3035"])
                    properties["geometry"] = bbox_lon_lat
                # create id
                product_id = f"{product_id_base}__{tile['tileID']}"
                properties["id"] = properties["title"] = product_id
                download_link = metadata_mapping.get("eodag:download_link").format(
                    dataset=dataset, tile_id=tile["tileID"]
                )
                properties["eodag:download_link"] = download_link
                product = EOProduct(
                    provider="cop_ghsl", properties=properties, collection=product_type
                )
                if not filter_geometry or filter_geometry.intersects(product.geometry):
                    if current_index >= start_index and current_index <= end_index:
                        products.append(product)
                    current_index += 1

        return products, current_index

    def _create_products_without_tiles(
        self, collection: str, prep: PreparedSearch, filter_params: dict[str, Any]
    ) -> tuple[list[EOProduct], Optional[int]]:
        filters = deepcopy(filter_params)
        default_geometry = getattr(self.config, "metadata_mapping")[
            "eodag:default_geometry"
        ]
        properties = {}
        properties["geometry"] = default_geometry[1]
        product_type_config = self.config.products.get(collection, {})
        download_link = product_type_config.get("metadata_mapping", {}).get(
            "eodag:download_link", None
        )
        if not download_link:
            raise MisconfiguredError(
                f"Download link configuration missing for product type {collection}"
            )

        # product type with assets mapping
        assets_mapping = filters.pop("assets_mapping", None)
        products = []
        per_page = getattr(prep, "items_per_page", DEFAULT_ITEMS_PER_PAGE)
        page = getattr(prep, "PAGE", 1)
        start_index = per_page * (page - 1)
        end_index = start_index + per_page - 1
        grouped_by = filters.pop("grouped_by", None)
        if grouped_by:  # dataset with several files differentiated by one parameter
            format_params = {k: str(v) for k, v in filters.items() if v}
            format_params.pop("metadata_mapping", None)
            grouped_by_values = filters[grouped_by]
            if isinstance(grouped_by_values, str) or isinstance(grouped_by_values, int):
                grouped_by_values = [grouped_by_values]
            num_products = len(grouped_by_values)
            for i, value in enumerate(grouped_by_values):
                if i < start_index:
                    continue
                filters[grouped_by] = format_params[grouped_by] = str(value)
                product_id = collection + "__" + "_".join(format_params.values())
                properties["id"] = properties["title"] = product_id
                properties.update(format_params)
                properties["eodag:download_link"] = download_link.format(
                    **format_params
                )
                datetimes = self._get_start_and_end_from_properties(format_params)
                properties["start_datetime"] = datetimes["start_date"]
                properties["end_datetime"] = datetimes["end_date"]
                properties[grouped_by] = value
                product = EOProduct(
                    provider="cop_ghsl", properties=properties, collection=collection
                )
                if assets_mapping:  # item with several assets
                    assets = AssetsDict(product=product)
                    for key, mapping in assets_mapping.items():
                        download_link = mapping["href"].format(**filters)
                        assets.update(
                            {
                                key: {
                                    "href": download_link,
                                    "title": mapping["title"],
                                    "type": mapping["type"],
                                }
                            }
                        )
                    product.assets = assets
                products.append(product)
                if i == end_index:
                    break
        else:  # product type with only one file to download
            product_id = f"{collection}_ALL"
            properties["id"] = properties["title"] = product_id
            datetimes = self._get_start_and_end_from_properties(properties)
            properties["start_datetime"] = datetimes["start_date"]
            properties["end_datetime"] = datetimes["end_date"]
            properties["eodag:download_link"] = download_link
            product = EOProduct(
                provider="cop_ghsl", properties=properties, collection=collection
            )
            products.append(product)
            num_products = 1
        if prep.count:
            return products, num_products
        else:
            return products, None

    def _get_tile_from_product_id(
        self, query_params: dict[str, Any]
    ) -> Optional[tuple[dict[str, list[dict[str, Any]]], str]]:
        """fetch the tile for a specific product id from the provider
        returns a a dict with a list of length 1 to simplify further processing
        """
        product_id = query_params.pop("id")
        collection = query_params["collection"]
        tile_id = product_id.split("__")[-1]
        filter_part = product_id.split("__")[1]
        constraints_values = self._fetch_constraints(collection)["constraints"]
        available_values = _get_available_values_from_constraints(
            constraints_values, {}, collection
        )
        product_type_config = deepcopy(self.config.products.get(collection, {}))
        for key, values in available_values.items():
            for value in values:
                if value in filter_part:
                    query_params[key] = value
                    break
        tiles_or_none = self._get_tiles_for_filters(product_type_config, query_params)
        if tiles_or_none:
            tiles, unit = tiles_or_none
            matching_tile = [
                tile
                for tile in tiles[query_params["year"]]
                if tile and tile["tileID"] == tile_id
            ]
            return {query_params["year"]: matching_tile}, unit
        else:
            return None

    def _get_tiles_for_filters(
        self, collection_config: dict[str, Any], params: dict[str, Any]
    ) -> Optional[tuple[dict[str, list[dict[str, Any]]], str]]:
        """fetch the tiles matching the given filters from the provider"""

        logger.debug(f"get tiles for filter parameters {params}")
        collection = params.pop("collection")
        ssl_verify = getattr(self.config, "ssl_verify", True)
        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)

        # update filters with values from product type mapping
        provider_product_type = collection_config.pop("product:type", None)
        if not provider_product_type:
            raise MisconfiguredError(
                f"provider product type mapping not available for {collection}"
            )
        filter_params = deepcopy(params)
        filter_params.pop("geometry", None)
        filter_params.update(collection_config)
        filter_params.pop("metadata_mapping", None)
        filter_params.pop("assets_mapping", None)

        self._check_input_parameters_valid(collection, filter_params)
        # update parameters based on changes during validation
        params.update(filter_params)

        # fetch available tiles based on filters
        if "year" not in filter_params:
            logger.warning(f"no tiles available for {collection}")
            return None
        if isinstance(filter_params["year"], int) or isinstance(
            filter_params["year"], str
        ):
            list_years = [str(filter_params["year"])]
        else:
            list_years = filter_params["year"]
        all_tiles = {}
        for year in list_years:
            try:
                filter_str = (
                    f"{provider_product_type}_{year}_"
                    f"{filter_params['tile_size']}_{filter_params['coord_system']}"
                )
            except KeyError:
                logger.warning(f"no tiles available for {collection}")
                return None
            tiles_url = self.config.api_endpoint + "/tilesDLD_" + filter_str + ".json"
            try:
                res = requests.get(tiles_url, verify=ssl_verify, timeout=timeout)
                if res.status_code == 404:
                    return None
                res.raise_for_status()
                tiles = res.json()["grid"]
                if filter_params["coord_system"] == 3035:
                    tiles = []
                    for t_id, bbox in res.json()["BBoxes"].items():
                        tiles.append({"tileID": t_id, "BBox_3035": bbox})
                all_tiles[year] = tiles
                unit = res.json().get("unit", "")
            except requests.exceptions.Timeout as exc:
                raise TimeOutError(exc, timeout=timeout) from exc
            except requests.exceptions.RequestException as exc:
                raise RequestError.from_error(
                    exc, f"Unable to fetch {tiles_url}"
                ) from exc

        return all_tiles, unit

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
        page = getattr(prep, "page", 1)
        items_per_page = getattr(prep, "items_per_page", DEFAULT_ITEMS_PER_PAGE)

        # get year/month from start/end time if not given separately
        _replace_datetimes(kwargs)

        collection = kwargs.get("collection", None)
        if not collection:
            collection = kwargs["collection"] = prep.collection
        if not isinstance(collection, str):
            raise MisconfiguredError("invalid product type %s", collection)
        collection_config = deepcopy(self.config.products.get(collection, {}))
        if "id" in kwargs and "ALL" not in kwargs["id"]:
            tiles_or_none = self._get_tile_from_product_id(kwargs)
        else:
            tiles_or_none = self._get_tiles_for_filters(collection_config, kwargs)
        if tiles_or_none:
            tiles, unit = tiles_or_none
        else:
            kwargs.update(collection_config)
            return self._create_products_without_tiles(collection, prep, kwargs)

        # create products from tiles
        kwargs.update(collection_config)
        kwargs["page"] = page
        kwargs["per_page"] = items_per_page
        constraints_filters = self._fetch_constraints(collection)
        additional_filter = constraints_filters.get("additional_filter", None)
        if additional_filter:
            products, count = self._create_products_from_tiles(
                tiles,
                unit,
                collection,
                kwargs,
                additional_filter=additional_filter,
            )
        else:
            products, count = self._create_products_from_tiles(
                tiles, unit, collection, kwargs
            )
        if prep.count:
            return products, count
        else:
            return products, None

    @instance_cached_method()
    def _fetch_constraints(self, product_type: str) -> dict[str, Any]:
        logger.debug(f"fetching constraints for {product_type}")
        constraints_url = self.config.discover_queryables["constraints_url"].format(
            product_type=product_type
        )
        timeout = getattr(self.config, "timeout", HTTP_REQ_TIMEOUT)
        try:
            res = requests.get(constraints_url)
            if res.status_code == 404:
                logger.warning(f"no constraints found for {product_type}")
                return {"constraints": {}}
            res.raise_for_status()
            return res.json()
        except requests.exceptions.Timeout as exc:
            raise TimeOutError(exc, timeout=timeout) from exc
        except requests.exceptions.RequestException as exc:
            raise RequestError.from_error(
                exc, f"Unable to fetch constraints from {constraints_url}"
            ) from exc

    def discover_queryables(
        self, **kwargs
    ) -> Optional[dict[str, Annotated[Any, FieldInfo]]]:
        """Create queryables list based on constraints

        :param kwargs: additional filters for queryables (`collection` and other search
                       arguments)
        :returns: queryable parameters dict
        """

        collection = kwargs.pop("collection")
        kwargs.pop("product:type")
        grouped_by = kwargs.pop("grouped_by", None)
        _replace_datetimes(kwargs)
        constraints_values = self._fetch_constraints(collection)["constraints"]
        available_values = _get_available_values_from_constraints(
            constraints_values, kwargs, collection
        )
        queryables = {}
        for name, values in available_values.items():
            required = True
            if name == grouped_by:
                required = False
            queryables[name] = Annotated[
                get_args(
                    json_field_definition_to_python(
                        {"type": "string", "title": name, "enum": values},
                        default_value=kwargs.get(name, None),
                        required=required,
                    )
                )
            ]
        # add datetimes queryables if year filter is available
        if "year" in available_values:
            queryables.update(
                {
                    "start": Queryables.get_with_default(
                        "start", kwargs.get("start_datetime")
                    ),
                    "end": Queryables.get_with_default(
                        "end",
                        kwargs.get("end_datetime"),
                    ),
                }
            )
        # add geometry queryable if there are tiles
        if "tile_size" in available_values and not grouped_by:
            queryables.update(
                {
                    "geom": Queryables.get_with_default("geom", None),
                }
            )

        return queryables
