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

import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from boto3.resources.collection import ResourceCollection
from boto3.session import Session
from botocore.exceptions import ClientError, ProfileNotFound
from botocore.handlers import disable_signing as botocore_disable_signing

from eodag.plugins.authentication.base import Authentication
from eodag.utils.exceptions import AuthenticationError

logger = logging.getLogger("eodag.authentication.aws_auth")


class AwsAuth(Authentication):
    """AWS authentication plugin

    Authentication will use the first valid method within the following ones:

    - auth anonymously using no-sign-request
    - auth using ``aws_profile``
    - auth using ``aws_access_key_id`` and ``aws_secret_access_key``
    - auth using current environment (AWS environment variables and/or ``~/aws/*``),
      will be skipped if AWS credentials are filled in eodag conf
    """

    aws_access_key_id: str
    aws_secret_access_key: str
    profile_name: str

    def authenticate(self):
        """Authenticate"""
        credentials = getattr(self.config, "credentials", {}) or {}
        self.aws_access_key_id = credentials.get(
            "aws_access_key_id", self.aws_access_key_id
        )
        self.aws_secret_access_key = credentials.get(
            "aws_secret_access_key", self.aws_secret_access_key
        )
        self.profile_name = credentials.get("aws_profile", self.profile_name)

        auth_keys = ["aws_access_key_id", "aws_secret_access_key", "profile_name"]
        return {k: getattr(self, k) for k in auth_keys if getattr(self, k)}

    def s3Requests(self, requester_pays: bool = False):
        """
        Get authenticated S3 requests.

        :param bool requester_pays: Whether the requester pays for the data transfer costs. Defaults to False.

        :return: An instance of AuthenticatedS3Requests.
        :rtype: AuthenticatedS3Requests
        """
        return AuthenticatedS3Requests(self, requester_pays)


class AuthenticatedS3Requests:
    """Authenticated requests to S3 bucket"""

    session: Session

    def __init__(self, auth: AwsAuth, requester_pays: bool = False) -> None:
        """
        Initialize the AuthenticatedS3Requests class.

        :param AwsAuth auth: The AWS authentication object.
        :param bool requester_pays: Whether the requester pays for the data transfer costs. Defaults to False.
        """
        self.requester_pays = requester_pays
        self.auth = auth.authenticate()

    def get_all_objects(
        self, endpoint_url: str, bucket_names_and_prefixes: List[Tuple[str, str]]
    ) -> Tuple[Dict[str, Any], Any]:
        """
        Get all objects from the specified S3 buckets.

        :param str endpoint_url: The endpoint URL of the S3 service.
        :param List[Tuple[str, str]] bucket_names_and_prefixes: A list of tuples where each tuple contains a bucket name
            and a prefix.

        :return: A tuple containing a dictionary of authenticated objects and parameters of the S3 objects.
        :rtype: Tuple[Dict[str, Any], Any]

        :raises AuthenticationError: If all attempts to authenticate fail.
        """
        authenticated_objects: Dict[str, Any] = {}
        auth_error_messages: Set[str] = set()
        s3_objects = None
        for bucket_name, prefix in bucket_names_and_prefixes:
            try:
                if bucket_name not in authenticated_objects:
                    common_prefix: str = self._get_common_prefix(
                        bucket_name, prefix, bucket_names_and_prefixes
                    )
                    s3_objects = self.get_bucket_objects(
                        endpoint_url, bucket_name, common_prefix
                    )
                    authenticated_objects[bucket_name] = s3_objects
                else:
                    s3_objects = authenticated_objects[bucket_name]
            except (AuthenticationError, ClientError) as e:
                logger.warning(f"Unexpected error: {e}")
                logger.warning(f"Skipping {bucket_name}/{prefix}")
                auth_error_messages.add(str(e))

        if not authenticated_objects:
            raise AuthenticationError(", ".join(auth_error_messages))

        return authenticated_objects, getattr(s3_objects, "_params", None)

    def get_bucket_objects(
        self, endpoint_url: str, bucket_name: str, prefix: str
    ) -> ResourceCollection:
        """
        Get objects from a specific S3 bucket.

        :param str endpoint_url: The endpoint URL of the S3 service.
        :param str bucket_name: The name of the S3 bucket.
        :param str prefix: The prefix used to filter the objects in the bucket.

        :return: A collection of resources representing the objects in the S3 bucket.
        :rtype: ResourceCollection

        :raises AuthenticationError: If unable to authenticate using any available credentials configuration.
        """
        auth_methods = ["unsigned", "auth_profile", "auth_keys", "env"]

        for auth_method in auth_methods:
            try:
                s3_objects = self._get_authenticated_objects(
                    endpoint_url, bucket_name, prefix, auth_method
                )
                if s3_objects:
                    logger.debug(f"Auth using {auth_method} succeeded")
                    return s3_objects
            except ClientError as e:
                if e.response.get("Error", {}).get("Code", {}) not in [
                    "AccessDenied",
                    "InvalidAccessKeyId",
                    "SignatureDoesNotMatch",
                ]:
                    raise e
            except ProfileNotFound:
                pass
            logger.debug(f"Auth using {auth_method} failed")

        raise AuthenticationError(
            f"Unable do authenticate on s3://{bucket_name} using any available credendials configuration"
        )

    def rio_env(
        self, endpoint_url: str, bucket_name: str, prefix: str
    ) -> Dict[str, Union[Session, bool]]:
        """
        Get rasterio environment variables needed for data access authentication.

        :param str endpoint_url: The endpoint URL of the S3 service.
        :param str bucket_name: The name of the S3 bucket.
        :param str prefix: The prefix used to filter the objects in the bucket.

        :return: A dictionary containing rasterio environment variables.
        :rtype: Dict[str, Union[Session, bool]]
        """
        if not self.session:
            _ = self.get_bucket_objects(endpoint_url, bucket_name, prefix)

        env: Dict[str, Union[Session, bool]] = (
            {"session": self.session} if self.session else {"aws_unsigned": True}
        )

        if self.requester_pays:
            env["requester_pays"] = True

        return env

    def _get_common_prefix(
        self, bucket_name: str, prefix: str, bucket_names_and_prefixes: List
    ) -> str:
        """
        Get the common prefix for a specific S3 bucket.

        :param str bucket_name: The name of the S3 bucket.
        :param str prefix: The prefix used to filter the objects in the bucket.
        :param List bucket_names_and_prefixes: A list of tuples where each tuple contains a bucket name and a prefix.

        :return: The common prefix for the specified S3 bucket.
        :rtype: str
        """
        common_prefix = ""

        prefix_split = prefix.split("/")
        prefixes_in_bucket = [
            p for b, p in bucket_names_and_prefixes if b == bucket_name
        ]
        for i in range(1, len(prefix_split)):
            common_prefix = "/".join(prefix_split[0:i])
            if len([p for p in prefixes_in_bucket if common_prefix in p]) < len(
                prefixes_in_bucket
            ):
                common_prefix = "/".join(prefix_split[0 : i - 1])
                break
        return common_prefix

    def _get_authenticated_objects(
        self, endpoint_url: str, bucket_name: str, prefix: str, auth_method: str
    ) -> Optional[ResourceCollection]:
        """
        Get authenticated objects from a specific S3 bucket.

        :param str endpoint_url: The endpoint URL of the S3 service.
        :param str bucket_name: The name of the S3 bucket.
        :param str prefix: The prefix used to filter the objects in the bucket.
        :param str auth_method: The authentication method to use.

        :return: A collection of resources representing the authenticated objects in the S3 bucket. Returns None if
            authentication fails.
        :rtype: Optional[ResourceCollection]
        """
        disable_signing = False

        if auth_method == "unsigned":
            disable_signing = True

        elif auth_method == "auth_profile":
            if "profile_name" not in self.auth.keys():
                return None
            self.session = Session(profile_name=self.auth["profile_name"])

        elif auth_method == "auth_keys":
            if not all(
                k in self.auth for k in ("aws_access_key_id", "aws_secret_access_key")
            ):
                return None
            self.session = Session(
                aws_access_key_id=self.auth["aws_access_key_id"],
                aws_secret_access_key=self.auth["aws_secret_access_key"],
            )

        elif auth_method == "env":
            self.session = Session()
        else:
            return None

        objects = self._get_objects(endpoint_url, bucket_name, prefix, disable_signing)

        return objects

    def _get_objects(
        self,
        endpoint_url: str,
        bucket_name: str,
        prefix: str,
        disable_signing: bool = False,
    ) -> Any:
        """
        Get objects from a specific S3 bucket.

        :param str endpoint_url: The endpoint URL of the S3 service.
        :param str bucket_name: The name of the S3 bucket.
        :param str prefix: The prefix used to filter the objects in the bucket.
        :param bool disable_signing (optional): Whether to disable signing for the request. Defaults to False.

        :return:
            A collection of resources representing the objects in the S3 bucket.
            Returns None if authentication fails or if an unsupported authentication method is specified.

            If disable_signing is True and an error occurs during signing,
            this method will catch and log that error but will not raise an exception.
            Instead, it will return None. This allows for graceful handling of signing errors
            when making unsigned requests.
        :rtype: Any
        """
        s3_resource = self.session.resource(
            service_name="s3", endpoint_url=endpoint_url
        )

        if disable_signing:
            s3_resource.meta.client.meta.events.register(  # type: ignore
                "choose-signer.s3.*", botocore_disable_signing
            )

        objects = s3_resource.Bucket(bucket_name).objects  # type: ignore

        if self.requester_pays:
            objects = objects.filter(RequestPayer="requester")

        list(objects.filter(Prefix=prefix).limit(1))

        return objects
