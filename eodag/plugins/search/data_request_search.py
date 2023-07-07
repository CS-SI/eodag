import logging

import requests

from eodag.plugins.search.base import Search
from eodag.plugins.search.qssearch import QueryStringSearch

logger = logging.getLogger("eodag.plugins.search.data_request_search")


class DataRequestSearch(Search):
    """
    Plugin to execute search requests composed of several steps:
        - do a data request which defines which data shall be searched
        - check the status of the request job
        - if finished - fetch the result of the job
    """

    def __init__(self, provider, config):
        self.qs_search = QueryStringSearch(provider, config)
        super(DataRequestSearch, self).__init__(provider, config)

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
        provider_product_type = self.qs_search.map_product_type(product_type)
        data_request_id = self._create_data_request(provider_product_type, **kwargs)
        request_finished = False
        while not request_finished:
            request_finished = self._check_request_status(data_request_id)
        result = self._get_result_data(data_request_id)
        return self._convert_result_data(result)

    def _create_data_request(self, product_type, **kwargs):
        metadata_url = self.config.metadata_url + product_type
        headers = self.auth.headers
        try:
            metadata = requests.get(metadata_url, headers=headers)
            metadata.raise_for_status()
        except requests.RequestException:
            logger.error(
                "metadata for product_type %s could not be retrieved", product_type
            )
            raise

        url = self.config.data_request_url
        request_body = self.qs_search.format_query_params(product_type, **kwargs)
        try:
            request_job = requests.post(url, json=request_body, headers=headers)
            request_job.raise_for_status()
        except requests.RequestException:
            logger.error(
                "search job for product_type %s could not be created", product_type
            )
        else:
            return request_job["jobId"]

    def _check_request_status(self, data_request_id):
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
