import logging
import time

import requests

from eodag import EOProduct
from eodag.api.core import DEFAULT_ITEMS_PER_PAGE, DEFAULT_PAGE
from eodag.api.product.metadata_mapping import (
    format_query_params,
    mtd_cfg_as_conversion_and_querypath,
    properties_from_json,
)
from eodag.plugins.search.base import Search
from eodag.utils import (
    GENERIC_PRODUCT_TYPE,
    deepcopy,
    format_dict_items,
    string_to_jsonpath,
)
from eodag.utils.exceptions import RequestError

logger = logging.getLogger("eodag.search.data_request_search")


class DataRequestSearch(Search):
    """
    Plugin to execute search requests composed of several steps:
        - do a data request which defines which data shall be searched
        - check the status of the request job
        - if finished - fetch the result of the job
    """

    def __init__(self, provider, config):
        super(DataRequestSearch, self).__init__(provider, config)
        self.config.__dict__.setdefault("result_type", "json")
        self.config.__dict__.setdefault("results_entry", "content")
        self.config.__dict__.setdefault("pagination", {})
        self.config.__dict__.setdefault("free_text_search_operations", {})
        for product_type in self.config.products.keys():
            if "metadata_mapping" in self.config.products[product_type].keys():
                self.config.products[product_type][
                    "metadata_mapping"
                ] = mtd_cfg_as_conversion_and_querypath(
                    self.config.products[product_type]["metadata_mapping"]
                )
                # Complete and ready to use product type specific metadata-mapping
                product_type_metadata_mapping = deepcopy(self.config.metadata_mapping)

                # update config using provider product type definition metadata_mapping
                # from another product
                other_product_for_mapping = self.config.products[product_type].get(
                    "metadata_mapping_from_product", ""
                )
                if other_product_for_mapping:
                    other_product_type_def_params = self.get_product_type_def_params(
                        other_product_for_mapping,  # **kwargs
                    )
                    product_type_metadata_mapping.update(
                        other_product_type_def_params.get("metadata_mapping", {})
                    )
                # from current product
                product_type_metadata_mapping.update(
                    self.config.products[product_type]["metadata_mapping"]
                )

                self.config.products[product_type][
                    "metadata_mapping"
                ] = product_type_metadata_mapping

        if (
            self.config.result_type == "json"
            and "next_page_url_key_path" in self.config.pagination
        ):
            self.config.pagination["next_page_url_key_path"] = string_to_jsonpath(
                self.config.pagination.get("next_page_url_key_path", None)
            )
        self.download_info = {}
        self.data_request_id = None

    def get_product_type_def_params(self, product_type, **kwargs):
        """Get the provider product type definition parameters"""
        if product_type in self.config.products.keys():
            logger.debug(
                "Getting provider product type definition parameters for %s",
                product_type,
            )
            return self.config.products[product_type]
        elif GENERIC_PRODUCT_TYPE in self.config.products.keys():
            logger.debug(
                "Getting generic provider product type definition parameters for %s",
                product_type,
            )
            return {
                k: v
                for k, v in format_dict_items(
                    self.config.products[GENERIC_PRODUCT_TYPE], **kwargs
                ).items()
                if v
            }
        else:
            return {}

    def get_metadata_mapping(self, product_type=None):
        """Get the plugin metadata mapping configuration (product type specific if exists)"""
        return self.config.products.get(product_type, {}).get(
            "metadata_mapping", self.config.metadata_mapping
        )

    def discover_product_types(self):
        """Fetch product types is disabled for `DataRequestSearch`

        :returns: empty dict
        :rtype: dict
        """
        return {}

    def clear(self):
        """Clear search context"""
        super().clear()
        self.data_request_id = None

    def query(self, *args, count=True, **kwargs):
        """
        performs the search for a provider where several steps are required to fetch the data
        """
        product_type = kwargs.get("productType", None)
        # replace "product_type" to "providerProductType" in search args if exists
        # for compatibility with DataRequestSearch method
        if kwargs.get("product_type"):
            kwargs["providerProductType"] = kwargs.pop("product_type", None)
        provider_product_type = self._map_product_type(product_type)
        keywords = {k: v for k, v in kwargs.items() if k != "auth" and v is not None}

        if provider_product_type and provider_product_type != GENERIC_PRODUCT_TYPE:
            keywords["productType"] = provider_product_type
        elif product_type:
            keywords["productType"] = product_type

        # provider product type specific conf
        self.product_type_def_params = self.get_product_type_def_params(
            product_type, **kwargs
        )

        # update config using provider product type definition metadata_mapping
        # from another product
        other_product_for_mapping = self.product_type_def_params.get(
            "metadata_mapping_from_product", ""
        )
        if other_product_for_mapping:
            other_product_type_def_params = self.get_product_type_def_params(
                other_product_for_mapping, **kwargs
            )
            self.config.metadata_mapping.update(
                other_product_type_def_params.get("metadata_mapping", {})
            )
        # from current product
        self.config.metadata_mapping.update(
            self.product_type_def_params.get("metadata_mapping", {})
        )

        # if product_type_def_params is set, remove product_type as it may conflict with this conf
        if self.product_type_def_params:
            keywords.pop("productType", None)
        keywords.update(
            {
                k: v
                for k, v in self.product_type_def_params.items()
                if k not in keywords.keys()
                and k in self.config.metadata_mapping.keys()
                and isinstance(self.config.metadata_mapping[k], list)
            }
        )

        # ask for data_request_id if not set (it must exist when iterating over pages)
        if not self.data_request_id:
            data_request_id = self._create_data_request(
                provider_product_type, product_type, **keywords
            )
            self.data_request_id = data_request_id
            request_finished = False
        else:
            data_request_id = self.data_request_id
            request_finished = True

        while not request_finished:
            request_finished = self._check_request_status(data_request_id)
            time.sleep(1)
        logger.info("search job for product_type %s finished", provider_product_type)
        result = self._get_result_data(
            data_request_id,
            kwargs.get("items_per_page", DEFAULT_ITEMS_PER_PAGE),
            kwargs.get("page", DEFAULT_PAGE),
        )
        # if exists, add the geometry from search args in the content of the response for each product
        if keywords.get("geometry"):
            for product_content in result["content"]:
                if product_content["extraInformation"] is None:
                    product_content["extraInformation"] = {
                        "footprint": keywords["geometry"]
                    }
                elif not product_content["extraInformation"].get("footprint"):
                    product_content["extraInformation"]["footprint"] = keywords[
                        "geometry"
                    ]
        logger.info("result retrieved from search job")
        if self._check_uses_custom_filters(product_type):
            result = self._apply_additional_filters(
                result, self.config.products[product_type]["custom_filters"]
            )
        return self._convert_result_data(
            result, data_request_id, product_type, **kwargs
        )

    def _create_data_request(self, product_type, eodag_product_type, **kwargs):
        headers = getattr(self.auth, "headers", "")
        try:
            url = self.config.data_request_url
            request_body = format_query_params(
                eodag_product_type, self.config, **kwargs
            )
            logger.debug(
                f"Sending search job request to {url} with {str(request_body)}"
            )
            request_job = requests.post(url, json=request_body, headers=headers)
            request_job.raise_for_status()
        except requests.RequestException as e:
            raise RequestError(
                f"search job for product_type {product_type} could not be created: {str(e)}, {request_job.text}"
            )
        else:
            logger.info("search job for product_type %s created", product_type)
            return request_job.json()["jobId"]

    def _check_request_status(self, data_request_id):
        logger.info("checking status of request job %s", data_request_id)
        status_url = self.config.status_url + data_request_id
        try:
            status_resp = requests.get(status_url, headers=self.auth.headers)
            status_resp.raise_for_status()
        except requests.RequestException as e:
            raise RequestError(f"_check_request_status failed: {str(e)}")
        else:
            status_data = status_resp.json()
            if "status_code" in status_data and status_data["status_code"] in [
                403,
                404,
            ]:
                logger.error(f"_check_request_status failed: {status_data}")
                raise RequestError("authentication token expired during request")
            if status_data["status"] == "failed":
                logger.error(f"_check_request_status failed: {status_data}")
                raise RequestError(
                    f"data request job has failed, message: {status_data['message']}"
                )
            return status_data["status"] == "completed"

    def _get_result_data(self, data_request_id, items_per_page, page):
        page = page - 1 + self.config.pagination.get("start_page", 1)
        url = self.config.result_url.format(
            jobId=data_request_id, items_per_page=items_per_page, page=page
        )
        try:
            return requests.get(url, headers=self.auth.headers).json()
        except requests.RequestException:
            logger.error(f"Result could not be retrieved for {url}")

    def _convert_result_data(
        self, result_data, data_request_id, product_type, **kwargs
    ):
        """Build EOProducts from provider results"""
        results_entry = self.config.results_entry
        results = result_data[results_entry]
        normalize_remaining_count = len(results)
        logger.debug(
            "Adapting %s plugin results to eodag product representation"
            % normalize_remaining_count
        )
        products = []
        for result in results:
            product = EOProduct(
                self.provider,
                properties_from_json(
                    result,
                    self.get_metadata_mapping(kwargs.get("productType")),
                    discovery_config=getattr(self.config, "discover_metadata", {}),
                ),
                **kwargs,
            )
            # use product_type_config as default properties
            product.properties = dict(
                getattr(self.config, "product_type_config", {}), **product.properties
            )
            products.append(product)
        total_items_nb_key_path = string_to_jsonpath(
            self.config.pagination["total_items_nb_key_path"]
        )
        if len(total_items_nb_key_path.find(result_data)) > 0:
            total_items_nb = total_items_nb_key_path.find(result_data)[0].value
        else:
            total_items_nb = 0
        for p in products:
            # add the request id to the order link property (required to create data order)
            p.properties["orderLink"] = p.properties["orderLink"].replace(
                "requestJobId", str(data_request_id)
            )
            if self.config.products[product_type].get("storeDownloadUrl", False):
                # store download information to retrieve it later in case search by id
                # is not possible
                self.download_info[p.properties["id"]] = {
                    "requestJobId": data_request_id,
                    "orderLink": p.properties["orderLink"],
                    "downloadLink": p.properties["downloadLink"],
                    "provider": self.provider,
                }
        return products, total_items_nb

    def _check_uses_custom_filters(self, product_type):
        if (
            product_type in self.config.products
            and "custom_filters" in self.config.products[product_type]
        ):
            return True
        return False

    def _apply_additional_filters(self, result, custom_filters):
        filtered_result = []
        results_entry = self.config.results_entry
        results = result[results_entry]
        path = string_to_jsonpath(custom_filters["filter_attribute"])
        indexes = custom_filters["indexes"].split("-")
        for record in results:
            filter_param = path.find(record)[0].value
            filter_value = filter_param[int(indexes[0]) : int(indexes[1])]
            filter_clause = "'" + filter_value + "' " + custom_filters["filter_clause"]
            if eval(filter_clause):
                filtered_result.append(record)
        result[results_entry] = filtered_result
        return result

    def _map_product_type(self, product_type):
        """Map the eodag product type to the provider product type"""
        if product_type is None:
            return
        logger.debug("Mapping eodag product type to provider product type")
        return self.config.products.get(product_type, {}).get(
            "productType", GENERIC_PRODUCT_TYPE
        )
