import logging

from terracatalogueclient import Catalogue
from terracatalogueclient.config import CatalogueConfig, CatalogueEnvironment

from eodag import EOProduct
from eodag.api.product.metadata_mapping import format_query_params, properties_from_json
from eodag.plugins.apis.base import Api
from eodag.plugins.download.base import Download
from eodag.plugins.search.base import Search
from eodag.utils import GENERIC_PRODUCT_TYPE

logger = logging.getLogger("eodag.api.global_land_api")


class GlobalLandApi(Api, Download, Search):
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
