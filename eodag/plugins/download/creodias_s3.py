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
import boto3
from botocore.exceptions import ClientError

from eodag.plugins.download.aws import AwsDownload


class CreodiasS3Download(AwsDownload):
    """
    Download on creodias s3 from their VMs
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

        s3_session = boto3.session.Session(
            aws_access_key_id=auth_dict["aws_access_key_id"],
            aws_secret_access_key=auth_dict["aws_secret_access_key"],
        )
        s3_resource = s3_session.resource(
            "s3", endpoint_url=getattr(self.config, "base_uri", None)
        )
        objects = s3_resource.Bucket(bucket_name).objects.filter()
        list(objects.filter(Prefix=prefix).limit(1))
        self.s3_session = s3_session
        return objects
