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
from __future__ import annotations

import io
import logging
import os
import zipfile
from typing import TYPE_CHECKING, List, Optional
from urllib.parse import urlparse

import boto3
import botocore

from eodag.plugins.authentication.aws_auth import AwsAuth
from eodag.utils import get_bucket_name_and_prefix, guess_file_type
from eodag.utils.exceptions import (
    AuthenticationError,
    MisconfiguredError,
    NotAvailableError,
)

if TYPE_CHECKING:
    from zipfile import ZipFile, ZipInfo

    from mypy_boto3_s3.client import S3Client

    from eodag.api.product import EOProduct  # type: ignore

logger = logging.getLogger("eodag.utils.s3")


def fetch(
    bucket_name: str, key_name: str, start: int, len: int, client_s3: S3Client
) -> bytes:
    """
    Range-fetches a S3 key.

    :param bucket_name: Bucket name of the object to fetch
    :param key_name: Key name of the object to fetch
    :param start: Bucket name to fetch
    :param len: Bucket name to fetch
    :param client_s3: s3 client used to fetch the object
    :returns: Object bytes
    """
    end = start + len - 1
    s3_object = client_s3.get_object(
        Bucket=bucket_name, Key=key_name, Range="bytes=%d-%d" % (start, end)
    )
    return s3_object["Body"].read()


def parse_int(bytes: bytes) -> int:
    """
    Parses 2 or 4 little-endian bits into their corresponding integer value.

    :param bytes: bytes to parse
    :returns: parsed int
    """
    val = (bytes[0]) + ((bytes[1]) << 8)
    if len(bytes) > 3:
        val += ((bytes[2]) << 16) + ((bytes[3]) << 24)
    return val


def open_s3_zipped_object(
    bucket_name: str, key_name: str, client_s3: S3Client, partial: bool = True
) -> ZipFile:
    """
    Open s3 zipped object, without downloading it.

    See https://stackoverflow.com/questions/41789176/how-to-count-files-inside-zip-in-aws-s3-without-downloading-it;
    Based on https://stackoverflow.com/questions/51351000/read-zip-files-from-s3-without-downloading-the-entire-file

    :param bucket_name: Bucket name of the object to fetch
    :param key_name: Key name of the object to fetch
    :param client_s3: s3 client used to fetch the object
    :param partial: fetch partial data if only content info is needed
    :returns: List of files in zip
    """
    response = client_s3.head_object(Bucket=bucket_name, Key=key_name)
    size = response["ContentLength"]

    # End Of Central Directory bytes
    eocd = fetch(bucket_name, key_name, size - 22, 22, client_s3)

    # start offset and size of the central directory
    cd_start = parse_int(eocd[16:20])
    cd_size = parse_int(eocd[12:16])

    # fetch central directory, append EOCD, and open as zipfile
    cd = fetch(bucket_name, key_name, cd_start, cd_size, client_s3)

    zip_data = (
        cd + eocd if partial else fetch(bucket_name, key_name, 0, size, client_s3)
    )

    zip = zipfile.ZipFile(io.BytesIO(zip_data))

    return zip


def list_files_in_s3_zipped_object(
    bucket_name: str, key_name: str, client_s3: S3Client
) -> List[ZipInfo]:
    """
    List files in s3 zipped object, without downloading it.

    See https://stackoverflow.com/questions/41789176/how-to-count-files-inside-zip-in-aws-s3-without-downloading-it;
    Based on https://stackoverflow.com/questions/51351000/read-zip-files-from-s3-without-downloading-the-entire-file

    :param bucket_name: Bucket name of the object to fetch
    :param key_name: Key name of the object to fetch
    :param client_s3: s3 client used to fetch the object
    :returns: List of files in zip
    """
    with open_s3_zipped_object(bucket_name, key_name, client_s3) as zip_file:
        logger.debug("Found %s files in %s" % (len(zip_file.filelist), key_name))
        return zip_file.filelist


def update_assets_from_s3(
    product: EOProduct,
    auth: AwsAuth,
    s3_endpoint: Optional[str] = None,
    content_url: Optional[str] = None,
) -> None:
    """Update ``EOProduct.assets`` using content listed in its ``remote_location`` or given
    ``content_url``.

    If url points to a zipped archive, its content will also be be listed.

    :param product: product to update
    :param auth: Authentication plugin
    :param s3_endpoint: s3 endpoint if not hosted on AWS
    :param content_url: s3 URL pointing to the content that must be listed (defaults to
                        ``product.remote_location`` if empty)
    """
    required_creds = ["aws_access_key_id", "aws_secret_access_key"]

    if content_url is None:
        content_url = product.remote_location

    bucket, prefix = get_bucket_name_and_prefix(content_url)

    if bucket is None or prefix is None:
        logger.debug(f"No s3 prefix could guessed from {content_url}")
        return None

    try:
        auth_dict = auth.authenticate()

        if not all(x in auth_dict for x in required_creds):
            raise MisconfiguredError(
                f"Incomplete credentials for {product.provider}, missing "
                f"{[x for x in required_creds if x not in auth_dict]}"
            )
        if not getattr(auth, "s3_client", None):
            auth.s3_client = boto3.client(
                service_name="s3",
                endpoint_url=s3_endpoint,
                aws_access_key_id=auth_dict.get("aws_access_key_id"),
                aws_secret_access_key=auth_dict.get("aws_secret_access_key"),
                aws_session_token=auth_dict.get("aws_session_token"),
            )

        logger.debug("Listing assets in %s", prefix)

        if prefix.endswith(".zip"):
            # List prefix zip content
            assets_urls = [
                f"zip+s3://{bucket}/{prefix}!{f.filename}"
                for f in list_files_in_s3_zipped_object(bucket, prefix, auth.s3_client)
            ]
        else:
            # List files in prefix
            assets_urls = [
                f"s3://{bucket}/{obj['Key']}"
                for obj in auth.s3_client.list_objects(
                    Bucket=bucket, Prefix=prefix, MaxKeys=300
                ).get("Contents", [])
            ]

        for asset_url in assets_urls:
            out_of_zip_url = asset_url.split("!")[-1]
            key, roles = product.driver.guess_asset_key_and_roles(
                out_of_zip_url, product
            )
            parsed_url = urlparse(out_of_zip_url)
            title = os.path.basename(parsed_url.path)

            if key and key not in product.assets:
                product.assets[key] = {
                    "title": title,
                    "roles": roles,
                    "href": asset_url,
                }
                if mime_type := guess_file_type(asset_url):
                    product.assets[key]["type"] = mime_type

        # sort assets
        product.assets.data = dict(sorted(product.assets.data.items()))

        # update driver
        product.driver = product.get_driver()

    except botocore.exceptions.ClientError as e:
        if hasattr(auth.config, "auth_error_code") and str(
            auth.config.auth_error_code
        ) in str(e):
            raise AuthenticationError(
                f"Authentication failed on {s3_endpoint} s3"
            ) from e
        raise NotAvailableError(
            f"assets for product {prefix} could not be found"
        ) from e
