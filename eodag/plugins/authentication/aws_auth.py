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
from collections import UserList
from typing import TYPE_CHECKING, Any, Optional

import boto3
from boto3.session import Session
from botocore.exceptions import ClientError, ProfileNotFound
from botocore.handlers import disable_signing

from eodag.plugins.authentication.base import Authentication
from eodag.types import S3SessionKwargs
from eodag.utils.exceptions import AuthenticationError

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3ServiceResource
    from mypy_boto3_s3.service_resource import BucketObjectsCollection

    from eodag.config import PluginConfig


logger = logging.getLogger("eodag.download.aws_auth")

AWS_AUTH_ERROR_MESSAGES = [
    "AccessDenied",
    "InvalidAccessKeyId",
    "SignatureDoesNotMatch",
    "InvalidRequest",
]


class S3AuthContext:

    """Class defining an S3 authentication context (resource, session and authentication type used)"""

    def __init__(
        self, s3_resource: S3ServiceResource, auth_type: str, s3_session: Session
    ):
        self.s3_resource = s3_resource
        self.auth_type = auth_type
        self.s3_session = s3_session

    @staticmethod
    def create_auth_context_unsigned(endpoint_url: str):
        """Auth strategy using no-sign-request"""
        s3_resource = boto3.resource(service_name="s3", endpoint_url=endpoint_url)
        s3_resource.meta.client.meta.events.register(
            "choose-signer.s3.*", disable_signing
        )
        return S3AuthContext(
            s3_resource=s3_resource, auth_type="unsigned", s3_session=Session()
        )

    @staticmethod
    def create_auth_context_auth_profile(endpoint_url: str, profile_name: str):
        """Auth strategy using ``aws_profile`` from provided credentials"""
        s3_session = Session(profile_name=profile_name)
        s3_resource = s3_session.resource(
            service_name="s3",
            endpoint_url=endpoint_url,
        )
        return S3AuthContext(
            s3_resource=s3_resource, auth_type="auth_profile", s3_session=s3_session
        )

    @staticmethod
    def create_auth_context_auth_keys(endpoint_url: str, credentials: dict[str, str]):
        """Auth strategy using ``aws_access_key_id``/``aws_secret_access_key`` from provided credentials"""
        s3_session_kwargs: S3SessionKwargs = {
            "aws_access_key_id": credentials["aws_access_key_id"],
            "aws_secret_access_key": credentials["aws_secret_access_key"],
        }
        if credentials.get("aws_session_token"):
            s3_session_kwargs["aws_session_token"] = credentials["aws_session_token"]
        s3_session = Session(**s3_session_kwargs)
        s3_resource = s3_session.resource(
            service_name="s3",
            endpoint_url=endpoint_url,
        )
        return S3AuthContext(
            s3_resource=s3_resource, auth_type="auth_keys", s3_session=s3_session
        )

    @staticmethod
    def create_auth_context_env(endpoint_url: str):
        """Auth strategy using current environment"""

        s3_session = Session()
        s3_resource = s3_session.resource(service_name="s3", endpoint_url=endpoint_url)
        return S3AuthContext(
            s3_resource=s3_resource, auth_type="env", s3_session=s3_session
        )


class S3AuthContextPool(UserList):

    """Instances of S3AuthContextPool contain a list of possible authentication contexts
    based on the given credentials"""

    def __init__(self, endpoint_url, credentials: dict[str, str], *args: Any):
        super(S3AuthContextPool, self).__init__(*args)
        self.data.append(S3AuthContext.create_auth_context_unsigned(endpoint_url))
        if "aws_profile" in credentials:
            self.data.append(
                S3AuthContext.create_auth_context_auth_profile(
                    endpoint_url, credentials["aws_profile"]
                )
            )
        if (
            "aws_access_key_id" in credentials
            and "aws_secret_access_key" in credentials
        ):
            self.data.append(
                S3AuthContext.create_auth_context_auth_keys(endpoint_url, credentials)
            )
        self.data.append(S3AuthContext.create_auth_context_env(endpoint_url))
        self.used_method = ""


class AwsAuth(Authentication):
    """AWS authentication plugin

    Authentication will use the first valid method within the following ones depending on which
    parameters are available in the configuration:

    * auth anonymously using no-sign-request
    * auth using ``aws_profile``
    * auth using ``aws_access_key_id`` and ``aws_secret_access_key``
      (optionally ``aws_session_token``)
    * auth using current environment (AWS environment variables and/or ``~/aws/*``),
      will be skipped if AWS credentials are filled in eodag conf

    :param provider: provider name
    :param config: Authentication plugin configuration:

        * :attr:`~eodag.config.PluginConfig.type` (``str``) (**mandatory**): AwsAuth
        * :attr:`~eodag.config.PluginConfig.auth_error_code` (``int``) (mandatory for ``creodias_s3``):
          which error code is returned in case of an authentication error

    """

    def __init__(self, provider: str, config: PluginConfig) -> None:
        super(AwsAuth, self).__init__(provider, config)
        endpoint_url = getattr(self.config, "s3_endpoint", None)
        credentials = getattr(self.config, "credentials", {}) or {}
        self.auth_context_pool = S3AuthContextPool(
            endpoint_url=endpoint_url, credentials=credentials
        )
        self.s3_client = boto3.client(
            service_name="s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=credentials.get("aws_access_key_id"),
            aws_secret_access_key=credentials.get("aws_secret_access_key"),
            aws_session_token=credentials.get("aws_session_token"),
        )

    def authenticate(self) -> S3AuthContextPool:
        """Authenticate

        :returns: S3AuthContextPool with possible auth contexts
        """

        return self.auth_context_pool

    def _get_authenticated_objects(
        self, bucket_name: str, prefix: str
    ) -> BucketObjectsCollection:
        """Get boto3 authenticated objects for the given bucket using
        the most adapted auth strategy.

        :param bucket_name: Bucket containg objects
        :param prefix: Prefix used to filter objects on auth try
                       (not used to filter returned objects)
        :returns: The boto3 authenticated objects
        """

        for auth_context in self.auth_context_pool:
            try:
                if getattr(self.config, "requester_pays", False):
                    objects = auth_context.s3_resource.Bucket(
                        bucket_name
                    ).objects.filter(RequestPayer="requester")
                else:
                    objects = auth_context.s3_resource.Bucket(bucket_name).objects
                list(objects.filter(Prefix=prefix).limit(1))
                if objects:
                    logger.debug("Auth using %s succeeded", auth_context.auth_type)
                    self.auth_context_pool.used_method = auth_context.auth_type
                    return objects
            except ClientError as e:
                if (
                    e.response.get("Error", {}).get("Code", {})
                    in AWS_AUTH_ERROR_MESSAGES
                ):
                    pass
                else:
                    raise e
            except ProfileNotFound:
                pass
            logger.debug("Auth using %s failed", auth_context.auth_type)

        raise AuthenticationError(
            "Unable do authenticate on s3://%s using any available credendials configuration"
            % bucket_name
        )

    def authenticate_objects(
        self,
        bucket_names_and_prefixes: list[tuple[str, Optional[str]]],
    ) -> tuple[dict[str, Any], BucketObjectsCollection]:
        """
        Authenticates with s3 and retrieves the available objects

        :param bucket_names_and_prefixes: list of bucket names and corresponding path prefixes
        :raises AuthenticationError: authentication is not possible
        :return: authenticated objects per bucket, list of available objects
        """

        authenticated_objects: dict[str, Any] = {}
        auth_error_messages: set[str] = set()
        for _, pack in enumerate(bucket_names_and_prefixes):
            try:
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
                    # connect to aws s3 and get bucket auhenticated objects
                    s3_objects = self._get_authenticated_objects(
                        bucket_name, common_prefix
                    )
                    authenticated_objects[bucket_name] = s3_objects
                else:
                    s3_objects = authenticated_objects[bucket_name]

            except AuthenticationError as e:
                logger.warning("Unexpected error: %s" % e)
                logger.warning("Skipping %s/%s" % (bucket_name, prefix))
                auth_error_messages.add(str(e))
            except ClientError as e:
                self._raise_if_auth_error(e)
                logger.warning("Unexpected error: %s" % e)
                logger.warning("Skipping %s/%s" % (bucket_name, prefix))
                auth_error_messages.add(str(e))

        # could not auth on any bucket
        if not authenticated_objects:
            raise AuthenticationError(", ".join(auth_error_messages))
        return authenticated_objects, s3_objects
