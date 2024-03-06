# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
from types import MethodType
from typing import Any, Dict, List

import boto3
import botocore
from botocore.exceptions import BotoCoreError

from eodag import EOProduct
from eodag.api.product._assets import AssetsDict
from eodag.config import PluginConfig
from eodag.plugins.authentication.aws_auth import AwsAuth
from eodag.plugins.search.qssearch import QueryStringSearch
from eodag.utils import guess_file_type
from eodag.utils.exceptions import AuthenticationError, MisconfiguredError, RequestError

DATA_EXTENSIONS = ["jp2", "tiff", "nc", "grib"]
logger = logging.getLogger("eodag.search.creodiass3")


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
        _update_assets(self, downloader.config, authenticator)
    except BotoCoreError as e:
        raise RequestError(f"could not update assets: {str(e)}") from e


def _update_assets(product: EOProduct, config: PluginConfig, auth: AwsAuth):
    product.assets = {}
    prefix = (
        product.properties.get("productIdentifier", None).replace("/eodata/", "") + "/"
    )
    if prefix:
        try:
            auth_dict = auth.authenticate()
            required_creds = ["aws_access_key_id", "aws_secret_access_key"]
            if not all(x in auth_dict for x in required_creds):
                raise MisconfiguredError(
                    f"Incomplete credentials for {product.provider}, missing "
                    f"{[x for x in required_creds if x not in auth_dict]}"
                )
            if not getattr(auth, "s3_client", None):
                auth.s3_client = boto3.client(
                    "s3",
                    endpoint_url=config.base_uri,
                    aws_access_key_id=auth_dict["aws_access_key_id"],
                    aws_secret_access_key=auth_dict["aws_secret_access_key"],
                )
            logger.debug("Listing assets in %s", prefix)
            product.assets = AssetsDict(product)
            for asset in auth.s3_client.list_objects(
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
                    if mime_type := guess_file_type(asset["Key"]):
                        product.assets[asset_basename]["type"] = mime_type
            # update driver
            product.driver = product.get_driver()

        except botocore.exceptions.ClientError as e:
            if str(auth.config.auth_error_code) in str(e):
                raise AuthenticationError(
                    f"Authentication failed on {config.base_uri} s3"
                ) from e
            raise RequestError(f"assets for product {prefix} could not be found") from e


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
