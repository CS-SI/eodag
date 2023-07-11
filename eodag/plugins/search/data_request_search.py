import logging

import requests

from eodag import EOProduct
from eodag.api.product.metadata_mapping import format_query_params, properties_from_json
from eodag.plugins.search.base import Search
from eodag.utils import GENERIC_PRODUCT_TYPE, string_to_jsonpath

logger = logging.getLogger("eodag.plugins.search.data_request_search")


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

    def discover_product_types(self):
        """Fetch product types is disabled for `StaticStacSearch`

        :returns: empty dict
        :rtype: dict
        """
        return {}

    def query(self, *args, count=True, **kwargs):
        """
        performs the search for a provider where several steps are required to fetch the data
        """
        product_type = kwargs.get("productType", None)
        provider_product_type = self._map_product_type(product_type)
        kwargs["productType"] = provider_product_type
        print(provider_product_type)
        data_request_id = self._create_data_request(provider_product_type, **kwargs)
        request_finished = False
        while not request_finished:
            request_finished = self._check_request_status(data_request_id)
        logger.info("search job for product_type %s finished", provider_product_type)
        result = self._get_result_data(data_request_id)
        logger.info("result retrieved from search job")
        return self._convert_result_data(result)

    def _create_data_request(self, product_type, **kwargs):
        headers = getattr(self.auth, "headers", "")
        try:
            metadata_url = self.config.metadata_url + product_type
            print("h" + str(headers))
            metadata = requests.get(metadata_url, headers=headers)
            print(metadata)
            metadata.raise_for_status()
        except requests.RequestException:
            logger.error(
                "metadata for product_type %s could not be retrieved", product_type
            )
            raise
        else:
            try:
                url = self.config.data_request_url
                print(url)
                request_body = format_query_params(product_type, self.config, **kwargs)
                print(request_body)
                request_job = requests.post(url, json=request_body, headers=headers)
                print(request_job)
                request_job.raise_for_status()
            except requests.RequestException:
                logger.error(
                    "search job for product_type %s could not be created", product_type
                )
            else:
                logger.info("search job for product_type %s created", product_type)
                return request_job.json()["jobId"]

    def _check_request_status(self, data_request_id):
        print(self.config.status_url)
        print(data_request_id)
        status_url = self.config.status_url + data_request_id
        status_data = requests.get(status_url, headers=self.auth.headers).json()
        if status_data["status"] == "failed":
            logger.error(
                "data request job has failed, message: %s", status_data["message"]
            )
            raise requests.RequestException
        return status_data["status"] == "completed"

    def _get_result_data(self, data_request_id):
        url = self.config.result_url.format(jobId=data_request_id)
        try:
            result = requests.get(url, headers=self.auth.headers).json()
            print(result)
            return result
        except requests.RequestException:
            logger.error("data from job %s could not be retrieved", data_request_id)

    def _convert_result_data(self, result_data, **kwargs):
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
                    self.config.metadata_mapping,
                    discovery_config=getattr(self.config, "discover_metadata", {}),
                ),
                **kwargs,
            )
            products.append(product)
        total_items_nb_key_path = string_to_jsonpath(
            self.config.pagination["total_items_nb_key_path"]
        )
        print(total_items_nb_key_path.find(result_data))
        total_items_nb = total_items_nb_key_path.find(result_data)[0].value
        print(products)
        return products, total_items_nb

    def _map_product_type(self, product_type):
        """Map the eodag product type to the provider product type"""
        if product_type is None:
            return
        logger.debug("Mapping eodag product type to provider product type")
        return self.config.products.get(product_type, {}).get(
            "productType", GENERIC_PRODUCT_TYPE
        )
