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
from typing import Any, Dict, List, Set, Tuple, Union

import boto3
from boto3.resources.base import ServiceResource
from boto3.resources.collection import ResourceCollection
from boto3.session import Session
from botocore.exceptions import ClientError, ProfileNotFound
from botocore.handlers import disable_signing

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

    def __init__(self, provider, config):
        super(AwsAuth, self).__init__(provider, config)
        self.aws_access_key_id = None
        self.aws_secret_access_key = None
        self.profile_name = None

    def authenticate(self):
        """Authenticate

        :returns: dict containing AWS/boto3 non-empty credentials
        :rtype: dict
        """
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
        return AuthenticatedS3Requests(self, requester_pays)


class AuthenticatedS3Requests:
    """Authenticated requests to S3 bucket"""

    def __init__(self, auth: AwsAuth, requester_pays: bool = False) -> None:
        self.requester_pays = requester_pays
        self.auth = auth.authenticate()
        self.session: Session = None

    def get_all_objects(
        self, bucket_names_and_prefixes: List[Tuple[str, str]]
    ) -> Tuple[Dict[str, Any], Any]:
        authenticated_objects: Dict[str, Any] = {}
        auth_error_messages: Set[str] = set()
        for bucket_name, prefix in bucket_names_and_prefixes:
            try:
                if bucket_name not in authenticated_objects:
                    common_prefix: str = self._get_common_prefix(
                        bucket_name, prefix, bucket_names_and_prefixes
                    )
                    s3_objects = self.get_bucket_objects(bucket_name, common_prefix)
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

    def get_bucket_objects(self, bucket_name: str, prefix: str) -> ResourceCollection:
        auth_methods = ["unsigned", "auth_profile", "auth_keys", "env"]

        for auth_method in auth_methods:
            try:
                s3_objects = self._get_authenticated_objects(
                    bucket_name, prefix, auth_method
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

    def rio_env(self, bucket_name: str, prefix: str) -> Dict[str, Union[Session, bool]]:
        """Get rasterio environment variables needed for data access authentication.

        :param bucket_name: Bucket containg objects
        :type bucket_name: str
        :param prefix: Prefix used to try auth
        :type prefix: str
        :returns: The rasterio environement variables
        :rtype: dict
        """
        if not self.session:
            _ = self.get_bucket_objects(bucket_name, prefix)

        env = {"session": self.session} if self.session else {"aws_unsigned": True}

        if self.requester_pays:
            env["requester_pays"] = True

        return env

    def _get_common_prefix(
        self, bucket_name: str, prefix: str, bucket_names_and_prefixes: List
    ) -> str:
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
        self, bucket_name: str, prefix: str, auth_method: str
    ) -> ResourceCollection:
        if auth_method == "unsigned":
            objects = self._get_objects(bucket_name, disable_signing=True)
        elif auth_method == "auth_profile":
            if "profile_name" not in self.auth.keys():
                return None
            self.session = Session(profile_name=self.auth["profile_name"])
            objects = self._get_objects(bucket_name, prefix)
        elif auth_method == "auth_keys":
            if not all(
                k in self.auth for k in ("aws_access_key_id", "aws_secret_access_key")
            ):
                return None
            self.session = Session(
                aws_access_key_id=self.auth["aws_access_key_id"],
                aws_secret_access_key=self.auth["aws_secret_access_key"],
            )
            objects = self._get_objects(bucket_name, prefix)
        elif auth_method == "env":
            self.session = Session()
            objects = self._get_objects(bucket_name, prefix)

        return objects

    def _get_objects(
        self, bucket_name: str, prefix: str, disable_signing: bool = False
    ) -> Any:
        s3_resource = self.session.resource(
            service_name="s3", endpoint_url=getattr(self.config, "base_uri", None)
        )

        if disable_signing:
            s3_resource.meta.client.meta.events.register(
                "choose-signer.s3.*", disable_signing
            )

        objects = s3_resource.Bucket(bucket_name).objects

        if self.requester_pays:
            objects = objects.filter(RequestPayer="requester")

        list(objects.filter(Prefix=prefix).limit(1))

        return objects
