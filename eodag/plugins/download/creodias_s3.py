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
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from eodag import EOProduct
from eodag.plugins.download.aws import AwsDownload
from eodag.utils.exceptions import MisconfiguredError


class CreodiasS3Download(AwsDownload):
    """
    Download on creodias s3 from their VMs (extension of :class:`~eodag.plugins.download.aws.AwsDownload`)

    :param provider: provider name
    :param config: Download plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): CreodiasS3Download
        * :attr:`~eodag.config.PluginConfig.base_uri` (``str``) (**mandatory**): s3 endpoint url
        * :attr:`~eodag.config.PluginConfig.s3_bucket` (``str``) (**mandatory**): bucket where the products can be found
        * :attr:`~eodag.config.PluginConfig.ssl_verify` (``bool``): if the ssl certificates should be
          verified in requests; default: ``True``
    """

    def _get_authenticated_objects_unsigned(self, bucket_name, prefix, auth_dict):
        """Auth strategy using no-sign-request"""

        raise ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "skip unsigned"}},
            "_get_authenticated_objects_unsigned",
        )

    def _get_authenticated_objects_from_auth_keys(self, bucket_name, prefix, auth_dict):
        """Auth strategy using RequestPayer=requester and ``aws_access_key_id``/``aws_secret_access_key``
        from provided credentials"""

        # check if credentials are missing
        required_creds = ["aws_access_key_id", "aws_secret_access_key"]
        if not all(auth_dict.get(x, None) for x in required_creds):
            raise MisconfiguredError(
                f"Incomplete credentials for {self.provider}, missing "
                f"{[x for x in required_creds if not auth_dict.get(x, None)]}"
            )

        s3_session = boto3.session.Session(**auth_dict)
        s3_resource = s3_session.resource(
            "s3", endpoint_url=getattr(self.config, "s3_endpoint", None)
        )
        objects = s3_resource.Bucket(bucket_name).objects.filter()
        list(objects.filter(Prefix=prefix).limit(1))
        self.s3_session = s3_session
        return objects

    def _get_bucket_names_and_prefixes(
        self,
        product: EOProduct,
        asset_filter: Optional[str] = None,
        ignore_assets: Optional[bool] = False,
    ) -> list[tuple[str, Optional[str]]]:
        """
        Retrieves the bucket names and path prefixes for the assets

        :param product: product for which the assets shall be downloaded
        :param asset_filter: text for which the assets should be filtered
        :param ignore_assets: if product instead of individual assets should be used
        :return: tuples of bucket names and prefixes
        """
        # if assets are defined, use them instead of scanning product.location
        if len(product.assets) > 0 and not ignore_assets:
            bucket_names_and_prefixes = super()._get_bucket_names_and_prefixes(
                product, asset_filter, ignore_assets
            )
        else:
            # if no assets are given, use productIdentifier to get S3 path for download
            s3_url = "s3:/" + product.properties["productIdentifier"]
            bucket_names_and_prefixes = [
                self.get_product_bucket_name_and_prefix(product, s3_url)
            ]
        return bucket_names_and_prefixes
