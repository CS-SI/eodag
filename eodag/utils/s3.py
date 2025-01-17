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
import zipfile
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from zipfile import ZipInfo

    from mypy_boto3_s3.client import S3Client

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


def parse_int(bytes: len) -> int:
    """
    Parses 2 or 4 little-endian bits into their corresponding integer value.

    :param bytes: bytes to parse
    :returns: parsed int
    """
    val = (bytes[0]) + ((bytes[1]) << 8)
    if len(bytes) > 3:
        val += ((bytes[2]) << 16) + ((bytes[3]) << 24)
    return val


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
    response = client_s3.head_object(Bucket=bucket_name, Key=key_name)
    size = response["ContentLength"]

    # End Of Central Directory bytes
    eocd = fetch(bucket_name, key_name, size - 22, 22, client_s3)

    # start offset and size of the central directory
    cd_start = parse_int(eocd[16:20])
    cd_size = parse_int(eocd[12:16])

    # fetch central directory, append EOCD, and open as zipfile
    cd = fetch(bucket_name, key_name, cd_start, cd_size, client_s3)
    zip = zipfile.ZipFile(io.BytesIO(cd + eocd))

    logger.debug("Found %s files in %s" % (len(zip.filelist), key_name))

    return zip.filelist
