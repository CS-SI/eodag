import logging
import os
from types import MethodType
from typing import Any, Dict, List

import boto3
from botocore.exceptions import BotoCoreError

from eodag import EOProduct
from eodag.config import PluginConfig
from eodag.plugins.search.qssearch import QueryStringSearch
from eodag.utils.exceptions import RequestError

DATA_EXTENSIONS = ["jp2", "tiff", "nc", "grib"]
logger = logging.getLogger("eodag.search.creodiass3")
AWS_ACCESS_KEY_ID = os.environ.get(
    "EODAG__CREODIAS_S3__AUTH__CREDENTIALS__AWS_ACCESS_KEY_ID", "foo"
)
AWS_SECRET_ACCESS_KEY = os.environ.get(
    "EODAG__CREODIAS_S3__AUTH__CREDENTIALS__AWS_SECRET_ACCESS_KEY", "bar"
)


def patched_register_downloader(self, downloader, authenticator):
    """Add the download information to the product.
    :param self: product to which information should be added
    :type self: EoProduct
    :param downloader: The download method that it can use
    :type downloader: Concrete subclass of
                      :class:`~eodag.plugins.download.base.Download` or
                      :class:`~eodag.plugins.api.base.Api`
    :param authenticator: The authentication method needed to perform the download
    :type authenticator: Concrete subclass of
                         :class:`~eodag.plugins.authentication.base.Authentication`
    """
    # register downloader
    self.register_downloader_only(downloader, authenticator)
    # and also update assets
    try:
        _update_assets(self, downloader.config)
    except BotoCoreError as e:
        logger.error(f"could not update assets: {str(e)}")
        raise RequestError(e)


def _update_assets(product: EOProduct, config: PluginConfig):
    product.assets = {}
    prefix = (
        product.properties.get("productIdentifier", None).replace("/eodata/", "") + "/"
    )
    if prefix:
        s3 = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            endpoint_url=config.base_uri,
        )

        product.assets = dict()
        for asset in s3.list_objects(
            Bucket=config.s3_bucket, Prefix=prefix, MaxKeys=300
        )["Contents"]:
            asset_basename = (
                asset["Key"].split("/")[-1] if "/" in asset["Key"] else asset["Key"]
            )

            if len(asset_basename) > 0 and asset_basename not in product.assets:
                role = (
                    "data"
                    if asset_basename.split(".")[-1] in DATA_EXTENSIONS
                    else "metadata"
                )

                product.assets[asset_basename] = {
                    "title": asset_basename,
                    "roles": [role],
                    "href": f"s3://{config.s3_bucket}/{asset['Key']}",
                }

        # update driver
        product.driver = product.get_driver()


class CreodiasS3Search(QueryStringSearch):
    """
    Search on creodias and adapt results to s3
    """

    def __init__(self, provider, config):
        super(CreodiasS3Search, self).__init__(provider, config)

    def normalize_results(
        self, results: List[Dict[str, Any]], **kwargs: Any
    ) -> List[EOProduct]:
        """Build EOProducts from provider results"""

        products = super(CreodiasS3Search, self).normalize_results(results, **kwargs)

        for product in products:
            # backup original register_downloader to register_downloader_only
            product.register_downloader_only = product.register_downloader
            # patched register_downloader that will also update assets
            product.register_downloader = MethodType(
                patched_register_downloader, product
            )

        return products
