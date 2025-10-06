# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional, cast
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError, ProfileNotFound
from botocore.handlers import disable_signing

from eodag.api.product._assets import Asset
from eodag.plugins.authentication.base import Authentication
from eodag.types import S3SessionKwargs
from eodag.utils.exceptions import AuthenticationError, EodagError

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client, S3ServiceResource
    from mypy_boto3_s3.service_resource import BucketObjectsCollection

    from eodag.config import PluginConfig


logger = logging.getLogger("eodag.download.aws_auth")

AWS_AUTH_ERROR_MESSAGES = [
    "AccessDenied",
    "InvalidAccessKeyId",
    "SignatureDoesNotMatch",
    "InvalidRequest",
]


def raise_if_auth_error(exception: ClientError, provider: str) -> None:
    """Raises an error if given exception is an authentication error"""
    err = cast(dict[str, str], exception.response["Error"])
    if err["Code"] in AWS_AUTH_ERROR_MESSAGES and "key" in err["Message"].lower():
        raise AuthenticationError(
            f"Please check your credentials for {provider}.",
            f"HTTP Error {exception.response['ResponseMetadata']['HTTPStatusCode']} returned.",
            err["Code"] + ": " + err["Message"],
        )


def create_s3_session(**kwargs) -> boto3.Session:
    """create s3 session based on available credentials

    :param kwargs: keyword arguments containing credentials
    :returns: boto3 Session
    """
    try:
        s3_session = boto3.Session(**kwargs)
    except ProfileNotFound:
        raise AuthenticationError(
            f"AWS profile {kwargs['profile_name']} not found, please check your credentials configuration"
        )
    return s3_session


class AwsAuth(Authentication):
    """AWS authentication plugin

    The authentication method will be chosen depending on which parameters are available in the configuration:

    * auth using ``profile_name`` (if credentials are given and contain ``aws_profile``)
    * auth using ``aws_access_key_id``, ``aws_secret_access_key`` and optionally ``aws_session_token``
      (if credentials are given but no ``aws_profile``)
    * auth using current environment - AWS environment variables and/or ``~/.aws/*``
      (if no credentials are given in config)
    * auth anonymously using no-sign-request if no credentials are given in config and
      auth using current environment failed

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): AwsAuth
        * :attr:`~eodag.config.PluginConfig.auth_error_code` (``int``) (mandatory for ``creodias_s3``):
          which error code is returned in case of an authentication error
        * :attr:`~eodag.config.PluginConfig.s3_endpoint` (``str``): s3 endpoint url
        * :attr:`~eodag.config.PluginConfig.requester_pays` (``bool``): whether download is done
          from a requester-pays bucket or not; default: ``False``

    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(AwsAuth, self).__init__(provider, config)
        self.s3_session: Optional[boto3.Session] = None
        self.s3_resource: Optional[S3ServiceResource] = None
        # set default for requester_pays if not given
        self.config.__dict__.setdefault("requester_pays", False)

    def _create_s3_session_from_credentials(self) -> boto3.Session:
        credentials = getattr(self.config, "credentials", {}) or {}
        if "aws_profile" in credentials:
            logger.debug("Authentication using AWS profile")
            return create_s3_session(profile_name=credentials["aws_profile"])
        # auth using aws keys
        elif credentials.get("aws_access_key_id") and credentials.get(
            "aws_secret_access_key"
        ):
            s3_session_kwargs: S3SessionKwargs = {
                "aws_access_key_id": credentials["aws_access_key_id"],
                "aws_secret_access_key": credentials["aws_secret_access_key"],
            }
            if credentials.get("aws_session_token"):
                s3_session_kwargs["aws_session_token"] = credentials[
                    "aws_session_token"
                ]
            return create_s3_session(**s3_session_kwargs)
        else:
            # auth using env variables or ~/.aws
            logger.debug("Authentication using AWS environment")
            return create_s3_session()

    def _create_s3_resource(self) -> S3ServiceResource:
        """create s3 resource based on s3 session"""
        if not self.s3_session:
            self.s3_session = self._create_s3_session_from_credentials()
        endpoint_url = getattr(self.config, "s3_endpoint", None)
        if self.s3_session.get_credentials():
            return self.s3_session.resource(
                service_name="s3",
                endpoint_url=endpoint_url,
            )
        # could not auth using credentials: use no-sign-request strategy
        logger.debug(
            "Authentication using AWS no-sign-request strategy (no credentials found)"
        )
        s3_resource = boto3.resource(service_name="s3", endpoint_url=endpoint_url)
        s3_resource.meta.client.meta.events.register(
            "choose-signer.s3.*", disable_signing
        )
        return s3_resource

    def get_s3_client(self) -> S3Client:
        """Get S3 client from S3 resource

        :returns: boto3 client
        """
        if not self.s3_resource:
            self.s3_resource = self._create_s3_resource()
        return self.s3_resource.meta.client

    def authenticate(self) -> S3ServiceResource:
        """Authenticate

        :returns: S3 Resource created based on an S3 session
        """
        self.s3_resource = self._create_s3_resource()
        return self.s3_resource

    def _get_authenticated_objects(
        self, bucket_name: str, prefix: str
    ) -> BucketObjectsCollection:
        """Get boto3 authenticated objects for the given bucket

        :param bucket_name: Bucket containg objects
        :param prefix: Prefix used to filter objects
        :returns: The boto3 authenticated objects
        """
        if not self.s3_resource:
            self.s3_resource = self._create_s3_resource()
        try:
            if self.config.requester_pays:
                objects = self.s3_resource.Bucket(bucket_name).objects.filter(
                    RequestPayer="requester"
                )
            else:
                objects = self.s3_resource.Bucket(bucket_name).objects
            list(objects.filter(Prefix=prefix).limit(1))
            if objects:
                logger.debug(
                    "Authentication for bucket %s succeeded; returning available objects",
                    bucket_name,
                )
                return objects
        except ClientError as e:
            if e.response.get("Error", {}).get("Code", {}) in AWS_AUTH_ERROR_MESSAGES:
                pass
            else:
                raise e
        logger.debug(
            "Authentication for bucket %s failed, please check the credentials",
            bucket_name,
        )

        raise AuthenticationError(
            "Unable do authenticate on s3://%s using credendials configuration"
            % bucket_name
        )

    def authenticate_objects(
        self,
        bucket_names_and_prefixes: list[tuple[str, Optional[str]]],
    ) -> dict[str, BucketObjectsCollection]:
        """
        Authenticates with s3 and retrieves the available objects

        :param bucket_names_and_prefixes: list of bucket names and corresponding path prefixes
        :raises AuthenticationError: authentication is not possible
        :return: authenticated objects per bucket
        """

        authenticated_objects: dict[str, Any] = {}
        auth_error_messages: set[str] = set()
        for _, pack in enumerate(bucket_names_and_prefixes):

            bucket_name, prefix = pack
            if not prefix:
                continue
            if bucket_name not in authenticated_objects:
                # get Prefixes longest common base path
                common_prefix = ""
                prefix_split = prefix.split("/")
                prefixes_in_bucket = len(
                    [p for b, p in bucket_names_and_prefixes if b == bucket_name]
                )
                for i in range(1, len(prefix_split)):
                    common_prefix = "/".join(prefix_split[0:i])
                    if (
                        len(
                            [
                                p
                                for b, p in bucket_names_and_prefixes
                                if p and b == bucket_name and common_prefix in p
                            ]
                        )
                        < prefixes_in_bucket
                    ):
                        common_prefix = "/".join(prefix_split[0 : i - 1])
                        break
                try:
                    # connect to aws s3 and get bucket auhenticated objects
                    authenticated_objects[
                        bucket_name
                    ] = self._get_authenticated_objects(bucket_name, common_prefix)

                except AuthenticationError as e:
                    logger.warning("Unexpected error: %s" % e)
                    logger.warning("Skipping %s/%s" % (bucket_name, prefix))
                    auth_error_messages.add(str(e))
                except ClientError as e:
                    raise_if_auth_error(e, self.provider)
                    logger.warning("Unexpected error: %s" % e)
                    logger.warning("Skipping %s/%s" % (bucket_name, prefix))
                    auth_error_messages.add(str(e))

        # could not auth on any bucket
        if not authenticated_objects:
            raise AuthenticationError(", ".join(auth_error_messages))
        return authenticated_objects

    def get_rio_env(self) -> dict[str, Any]:
        """Get rasterio environment variables needed for data access authentication.

        :returns: The rasterio environement variables
        """
        rio_env_kwargs = {}
        if endpoint_url := getattr(self.config, "s3_endpoint", None):
            rio_env_kwargs["endpoint_url"] = endpoint_url.split("://")[-1]

        if self.s3_session is None:
            self.authenticate()

        if self.config.requester_pays:
            rio_env_kwargs["requester_pays"] = True

        return {
            "session": self.s3_session,
            **rio_env_kwargs,
        }

    def presign_url(
        self,
        asset: Asset,
        expires_in: int = 3600,
    ) -> str:
        """This method is used to presign a url to download an asset from S3.

        :param asset: asset for which the url shall be presigned
        :param expires_in: expiration time of the presigned url in seconds
        :returns: presigned url
        :raises: :class:`~eodag.utils.exceptions.EodagError`
        :raises: :class:`NotImplementedError`
        """
        if not getattr(self.config, "support_presign_url", True):
            raise NotImplementedError(
                f"presign_url is not supported for provider {self.provider}"
            )

        url_parts = urlparse(asset["href"])

        s3_client = self.get_s3_client()
        url_path_parts = url_parts.path[1:].split("/")  # remove leading "/" and split
        try:
            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": url_path_parts[0],
                    "Key": "/".join(url_path_parts[1:]),
                },
                ExpiresIn=expires_in,
            )
            return presigned_url
        except ClientError:
            raise EodagError(f"Couldn't get a presigned URL for '{asset}'.")
