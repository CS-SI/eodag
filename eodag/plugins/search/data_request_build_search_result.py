import logging
import re
from datetime import datetime

import requests
from requests import Session

from eodag.api.product.metadata_mapping import format_query_params
from eodag.plugins.search.base import Search
from eodag.plugins.search.build_search_result import BuildPostSearchResult
from eodag.rest.stac import DEFAULT_MISSION_START_DATE
from eodag.utils import USER_AGENT, MisconfiguredError
from eodag.utils.exceptions import NotAvailableError

logger = logging.getLogger("eodag.search.data_request_build_search_result")


class DataRequestBuildSearchResult(BuildPostSearchResult):
    """
    plugin to fetch data from an API with a data request where a search result
    needs to be built (polytope)
    """

    def __init__(self, provider, config):
        # init self.config.metadata_mapping using Search Base plugin
        Search.__init__(self, provider, config)
        self.request_params = {}
        self.request_url = ""

    def do_search(self, *args, **kwargs):
        """Should perform the actual search request."""
        if "id" in kwargs or "server_mode" not in kwargs or not kwargs["server_mode"]:
            # in server mode only send request when search by id is done (before download)
            # to avoid creating unnecessary requests
            product_type = kwargs.pop("productType", None)
            keywords = {
                k: v for k, v in kwargs.items() if k != "auth" and v is not None
            }
            self.product_type_def_params = self.get_product_type_def_params(
                product_type, **kwargs
            )

            # Add to the query, the queryable parameters set in the provider product type definition
            keywords.update(
                {
                    k: v
                    for k, v in self.product_type_def_params.items()
                    if k not in keywords.keys()
                    and k in self.config.metadata_mapping.keys()
                    and isinstance(self.config.metadata_mapping[k], list)
                }
            )
            self.request_params = format_query_params(
                product_type, self.config, **keywords
            )
            collection = self._map_product_type(product_type)
            if not collection:
                raise MisconfiguredError
            request_url = self.config.data_request_url.format(collection=collection)
            self.request_url = request_url
            request_body = {"verb": "retrieve", "request": self.request_params}
            request_header = USER_AGENT
            s = Session()
            request = requests.Request(
                method="POST",
                url=request_url,
                headers=request_header,
                json=request_body,
            )
            prep = request.prepare()
            self.auth(prep)
            s.send(prep)

        return [{}]

    def query(
        self, product_type=None, items_per_page=None, page=None, count=True, **kwargs
    ):
        """query results"""
        if "id" in kwargs:
            dates_str = re.search("[0-9]{8}_[0-9]{8}", kwargs["id"]).group()
            dates = dates_str.split("_")
            start_date = datetime.strptime(dates[0], "%Y%m%d")
            kwargs["startTimeFromAscendingNode"] = start_date.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            end_date = datetime.strptime(dates[1], "%Y%m%d")
            kwargs["completionTimeFromAscendingNode"] = end_date.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        else:
            if "startTimeFromAscendingNode" not in kwargs:
                kwargs["startTimeFromAscendingNode"] = getattr(
                    self.config, "product_type_config", {}
                ).get("missionStartDate", DEFAULT_MISSION_START_DATE)
            if "completionTimeFromAscendingNode" not in kwargs:
                kwargs["completionTimeFromAscendingNode"] = getattr(
                    self.config, "product_type_config", {}
                ).get("missionEndDate", datetime.utcnow().isoformat())

        return BuildPostSearchResult.query(
            self, items_per_page=items_per_page, page=page, count=count, **kwargs
        )

    def normalize_results(self, results, **kwargs):
        """create a formatted result"""
        kwargs["params_in_download_link"] = False
        products = BuildPostSearchResult.normalize_results(self, results, **kwargs)
        if "id" in kwargs or "server_mode" not in kwargs or not kwargs["server_mode"]:
            request_header = USER_AGENT
            request = requests.Request(
                method="GET", url=self.request_url, headers=request_header
            )
            s = Session()
            prep = request.prepare()
            self.auth(prep)
            request_finished = False
            request_id = ""
            while not request_finished:
                collection_requests = s.send(prep).json()
                results_entry = getattr(self.config, "results_entry", None)
                if results_entry:
                    collection_requests = collection_requests[results_entry]
                params_entry = getattr(self.config, "request_params_entry")
                for req in collection_requests:
                    if (
                        request_id
                        and req["id"] == request_id
                        and req["status"] == "processed"
                    ):
                        request_finished = True
                    elif not request_id:
                        if req[params_entry] == str(self.request_params):
                            request_id = req["id"]
            if not request_id:
                raise NotAvailableError(
                    "request with parameters %s not found", str(self.request_params)
                )
            for p in products:
                p.properties["downloadLink"] = p.properties["downloadLink"].replace(
                    "request_id", str(request_id)
                )
                p.location = p.remote_location = p.properties["downloadLink"]
        return products

    def clear(self):
        """Clear search context"""
        self.request_params = {}
        self.request_url = ""

    def _map_product_type(self, product_type):
        """Map the eodag product type to the provider product type"""
        logger.debug("Mapping eodag product type to provider product type")
        return self.config.products.get(product_type, {}).get("productType", None)
