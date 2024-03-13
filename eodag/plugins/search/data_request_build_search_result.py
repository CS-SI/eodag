import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from eodag.api.product import EOProduct
from eodag.config import PluginConfig
from eodag.plugins.search.base import Search
from eodag.plugins.search.build_search_result import BuildPostSearchResult
from eodag.rest.stac import DEFAULT_MISSION_START_DATE
from eodag.utils import DEFAULT_ITEMS_PER_PAGE, DEFAULT_PAGE

logger = logging.getLogger("eodag.search.data_request_build_search_result")


class DataRequestBuildSearchResult(BuildPostSearchResult):
    """
    Generate a search result from search parameters
    Useful for providers not supporting a discovery endpoint
    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        # init self.config.metadata_mapping using Search Base plugin
        Search.__init__(self, provider, config)

    def do_search(self, *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        """Should perform the actual search request."""
        return [{}]

    def query(
        self,
        product_type: Optional[str] = None,
        items_per_page: int = DEFAULT_ITEMS_PER_PAGE,
        page: int = DEFAULT_PAGE,
        count: bool = True,
        **kwargs: Any,
    ) -> Tuple[List[EOProduct], Optional[int]]:
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

    def clear(self) -> None:
        """Clear search context"""
