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
from typing import Any, List

import boto3
import botocore
from botocore.exceptions import BotoCoreError

from eodag.api.product import AssetsDict, EOProduct  # type: ignore
from eodag.api.search_result import RawSearchResult
from eodag.config import PluginConfig
from eodag.plugins.authentication.aws_auth import AwsAuth
from eodag.plugins.search.qssearch import ODataV4Search
from eodag.utils import guess_file_type
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    NotAvailableError,
    RequestError,
)

DATA_EXTENSIONS = ["jp2", "tiff", "nc", "grib"]
logger = logging.getLogger("eodag.search.creodiass3")


def patched_register_downloader(self, downloader, authenticator):
    """Add the download information to the product.

    :param self: product to which information should be added
    :param downloader: The download method that it can use
                      :class:`~eodag.plugins.download.base.Download` or
                      :class:`~eodag.plugins.api.base.Api`
    :param authenticator: The authentication method needed to perform the download
                         :class:`~eodag.plugins.authentication.base.Authentication`
    """
    # register downloader
    self.register_downloader_only(downloader, authenticator)
    # and also update assets
    try:
        _update_assets(self, downloader.config, authenticator)
    except BotoCoreError as e:
        raise RequestError.from_error(e, "could not update assets") from e


def _update_assets(product: EOProduct, config: PluginConfig, auth: AwsAuth):
    product.assets = AssetsDict(product)
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
                    endpoint_url=config.s3_endpoint,
                    aws_access_key_id=auth_dict["aws_access_key_id"],
                    aws_secret_access_key=auth_dict["aws_secret_access_key"],
                )
            logger.debug("Listing assets in %s", prefix)
            product.assets = AssetsDict(product)
            s3_res = auth.s3_client.list_objects(
                Bucket=config.s3_bucket, Prefix=prefix, MaxKeys=300
            )
            # check if product path has assets or is already a file
            if "Contents" in s3_res:
                for asset in s3_res["Contents"]:
                    asset_basename = (
                        asset["Key"].split("/")[-1]
                        if "/" in asset["Key"]
                        else asset["Key"]
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
            raise NotAvailableError(
                f"assets for product {prefix} could not be found"
            ) from e


class CreodiasS3Search(ODataV4Search):
    """
    ``CreodiasS3Search`` is an extension of :class:`~eodag.plugins.search.qssearch.ODataV4Search`,
    it executes a Search on creodias and adapts results so that the assets contain links to s3.
    It has the same configuration parameters as :class:`~eodag.plugins.search.qssearch.ODataV4Search` and
    one additional parameter:

    :param provider: provider name
    :param config: Search plugin configuration:

        * :attr:`~eodag.config.PluginConfig.s3_endpoint` (``str``) (**mandatory**): base url of the s3
    """

    def __init__(self, provider, config):
        super(CreodiasS3Search, self).__init__(provider, config)

    def normalize_results(
        self, results: RawSearchResult, **kwargs: Any
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
