import logging

import requests

from eodag.api.product.metadata_mapping import format_query_params
from eodag.plugins.search.base import Search
from eodag.utils import GENERIC_PRODUCT_TYPE

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
        self.config.__dict__.setdefault("results_entry", "features")
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
        data_request_id = self._create_data_request(provider_product_type, **kwargs)
        request_finished = False
        while not request_finished:
            request_finished = self._check_request_status(data_request_id)
        result = self._get_result_data(data_request_id)
        return self._convert_result_data(result)

    def _create_data_request(self, product_type, **kwargs):
        headers = getattr(self.auth, "headers", "")
        try:
            metadata_url = self.config.metadata_url + product_type
            print(self.auth)
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
                return request_job["jobId"]

    def _check_request_status(self, data_request_id):
        print(self.config.status_url)
        print(data_request_id)
        status_url = self.config.status_url + data_request_id
        status_data = requests.get(status_url, headers=self.auth.headers)
        if status_data["status"] == "failed":
            logger.error(
                "data request job has failed, message: %s", status_data["message"]
            )
            raise requests.RequestException
        return status_data["status"] == "completed"

    def _get_result_data(self, param):
        pass

    def _convert_result_data(self, result):
        pass

    def _map_product_type(self, product_type, **kwargs):
        """Map the eodag product type to the provider product type"""
        if product_type is None:
            return
        logger.debug("Mapping eodag product type to provider product type")
        return self.config.products.get(product_type, {}).get(
            "productType", GENERIC_PRODUCT_TYPE
        )
