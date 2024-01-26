import logging
from typing import Any, Optional

from terracatalogueclient import Catalogue
from terracatalogueclient.config import CatalogueConfig, CatalogueEnvironment

from eodag import EOProduct, SearchResult
from eodag.api.product.metadata_mapping import format_query_params, properties_from_json
from eodag.config import PluginConfig
from eodag.plugins.apis.base import Api
from eodag.plugins.download.http import HTTPDownload
from eodag.plugins.search.base import Search
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    GENERIC_PRODUCT_TYPE,
    DownloadedCallback,
    ProgressCallback,
    path_to_uri,
)
from eodag.utils.exceptions import DownloadError

logger = logging.getLogger("eodag.api.global_land_api")


class GlobalLandApi(HTTPDownload, Api, Search):
    """
    plugin used to fetch Copernicus land data from the global land API
    """

    def __init__(self, provider, config):
        # init self.config.metadata_mapping using Search Base plugin
        Search.__init__(self, provider, config)
        # init Catalogue
        global_land_config = CatalogueConfig.from_environment(CatalogueEnvironment.CGLS)
        self.catalogue = Catalogue(global_land_config)

    def query(self, product_type=None, **kwargs):
        """
        fetches the data from the api and formats it
        """
        if not product_type:
            product_type = kwargs.get("productType", None)
        collection = self._map_product_type(product_type)
        query_params = format_query_params(product_type, self.config, **kwargs)
        logger.debug("sending request with query params: %s", query_params)
        results = self.catalogue.get_products(collection, **query_params)
        products = []
        mapping = self.config.products.get(product_type, {}).get(
            "metadata_mapping", self.config.metadata_mapping
        )
        for result in results:
            product = EOProduct(
                self.provider,
                properties_from_json(
                    result.__dict__,
                    mapping,
                    discovery_config=getattr(self.config, "discover_metadata", {}),
                ),
                **kwargs,
            )
            # use product_type_config as default properties
            product.properties = dict(
                getattr(self.config, "product_type_config", {}), **product.properties
            )
            products.append(product)
        return products, len(products)

    def _map_product_type(self, product_type):
        """Map the eodag product type to the provider product type"""
        if product_type is None:
            logger.debug("no product type given")
            return GENERIC_PRODUCT_TYPE
        logger.debug("Mapping eodag product type to provider product type")
        return self.config.products.get(product_type, {}).get(
            "productType", GENERIC_PRODUCT_TYPE
        )

    def download(
        self,
        product: EOProduct,
        auth: Optional[PluginConfig] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Any,
    ) -> Optional[str]:
        """
        downloads the given product.

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: (optional) The configuration of a plugin of type Authentication
        :type auth: :class:`~eodag.config.PluginConfig`
        :param progress_callback: (optional) A progress callback
        :type progress_callback: :class:`~eodag.utils.ProgressCallback`
        :param wait: (optional) If download fails, wait time in minutes between two download tries
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes before stop retrying
                        to download
        :type timeout: int
        :param kwargs: `outputs_prefix` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :type kwargs: Union[str, bool, dict]
        :returns: The absolute path to the downloaded product in the local filesystem
            (e.g. '/tmp/product.zip' on Linux or
            'C:\\Users\\username\\AppData\\Local\\Temp\\product.zip' on Windows)
        :rtype: str
        """
        fs_path, record_filename = self._prepare_download(
            product,
            progress_callback=progress_callback,
            outputs_extension="nc",
            **kwargs,
        )
        if not fs_path or not record_filename:
            if fs_path:
                product.location = path_to_uri(fs_path)
            return fs_path

        try:
            return super(GlobalLandApi, self).download(
                product,
                progress_callback=progress_callback,
                **kwargs,
            )
        except Exception as e:
            logger.error(e)
            raise DownloadError(e)

    def download_all(
        self,
        products: SearchResult,
        auth: Optional[PluginConfig] = None,
        downloaded_callback: Optional[DownloadedCallback] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Any,
    ):
        """
        Download all using parent (base plugin) method
        """
        return super(GlobalLandApi, self).download_all(
            products,
            auth=auth,
            downloaded_callback=downloaded_callback,
            progress_callback=progress_callback,
            wait=wait,
            timeout=timeout,
            **kwargs,
        )
