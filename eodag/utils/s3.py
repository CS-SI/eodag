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
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from zipfile import ZIP_STORED, ZipFile

import boto3
import botocore
import botocore.exceptions
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from zipstream import ZipStream

from eodag.plugins.authentication.aws_auth import AwsAuth
from eodag.utils import (
    StreamResponse,
    get_bucket_name_and_prefix,
    guess_file_type,
    parse_le_uint16,
    parse_le_uint32,
)
from eodag.utils.exceptions import (
    AuthenticationError,
    InvalidDataError,
    MisconfiguredError,
    NotAvailableError,
)

if TYPE_CHECKING:
    from typing import Iterable, Iterator, Literal, Optional
    from zipfile import ZipInfo

    from mypy_boto3_s3.client import S3Client

    from eodag.api.product import EOProduct  # type: ignore

logger = logging.getLogger("eodag.utils.s3")

MIME_OCTET_STREAM = "application/octet-stream"

# Backpressure configuration
BACKPRESSURE_DOWNLOAD_CHUNKS = 10  # Total chunks (downloading + buffered) per file


def fetch_range(
    bucket_name: str, key_name: str, start: int, end: int, client_s3: S3Client
) -> bytes:
    """
    Range-fetches a S3 key.

    :param bucket_name: Bucket name of the object to fetch
    :param key_name: Key name of the object to fetch
    :param start: Start byte position to fetch
    :param end: End byte position to fetch
    :param client_s3: s3 client used to fetch the object
    :returns: Object bytes
    """
    response = client_s3.get_object(
        Bucket=bucket_name, Key=key_name, Range="bytes=%d-%d" % (start, end)
    )
    return response["Body"].read()


@dataclass
class S3FileInfo:
    """
    Describe a S3 object with basic f_info and its download state.
    """

    size: int
    key: str
    bucket_name: str
    #: Path inside the ZIP archive if the file is stored inside a ZIP.
    zip_filepath: Optional[str] = None
    #: Offset in the ZIP archive where the file data starts.
    data_start_offset: int = 0
    #: MIME type of the file, defaulting to application/octet-stream.
    #: It can be updated based on the file extension or content type.
    data_type: str = MIME_OCTET_STREAM
    #: Relative path of the file, if applicable (e.g., inside a ZIP archive).
    rel_path: Optional[str] = None

    # These fields hold the state for downloading
    #: Offset in the logical (global) file stream where this file starts.
    file_start_offset: int = 0
    #: Buffers for downloaded data chunks, mapping start byte offsets to the actual data.
    #: This allows for partial downloads and efficient memory usage.
    #: The key is the start byte offset, and the value is the bytes data for that
    #: offset. This is used to yield data in the correct order during streaming.
    #: It is updated as chunks are downloaded.
    buffers: dict[int, bytes] = field(default_factory=dict)
    #: The next offset to yield in the file, used to track progress during downloading
    #: and yielding chunks. It starts at 0 and is updated as data is yielded.
    #: This allows the streaming process to continue from where it left off,
    #: ensuring that all data is eventually yielded without duplication.
    next_yield: int = 0
    #: Queue of pending ranges that haven't been submitted yet
    pending_ranges: list[tuple[int, int]] = field(default_factory=list)


def _prepare_file_in_zip(f_info: S3FileInfo, s3_client: S3Client):
    """Update file information with the offset and size of the file inside the zip archive"""

    splitted_path = f_info.key.split(".zip!")
    f_info.key = f"{splitted_path[0]}.zip"
    f_info.zip_filepath = splitted_path[-1]  # file path inside the ZIP archive

    f_info.data_start_offset, f_info.size = file_position_from_s3_zip(
        f_info.bucket_name,
        f_info.key,
        s3_client,
        f_info.zip_filepath,
    )


def _compute_file_ranges(
    file_info: S3FileInfo,
    byte_range: tuple[Optional[int], Optional[int]],
    range_size: int,
) -> Optional[list[tuple[int, int]]]:
    """
    Compute the byte ranges to download for a single file, considering the overall requested range.

    This function calculates which byte ranges within the given file should be downloaded,
    based on the global requested byte range (`byte_range`) and the size of each chunk (`range_size`).
    It accounts for possible offsets if the file is part of a ZIP archive or not aligned at offset zero.

    :param file_info: The S3FileInfo object containing file metadata, including size, data offset,
                      and its starting offset in the full logical file stream.
    :param byte_range: A tuple (start, end) specifying the requested global byte range, where either
                       value may be None to indicate an open-ended range.
    :param range_size: The size of each download chunk in bytes.
    :returns: A list of (start, end) tuples indicating byte ranges to download within this file,
              or None if the file lies completely outside the requested range.
    """
    file_size = file_info.size
    file_start_offset = file_info.file_start_offset
    file_end_offset = file_start_offset + file_size - 1

    range_start, range_end = byte_range

    # Check if the file overlaps with the requested range
    if range_end is not None and range_start is not None:
        if file_end_offset < range_start or file_start_offset > range_end:
            return None  # No overlap, skip this file

    start = 0
    end = file_size - 1

    # Adjust start and end based on the requested range
    if range_start is not None:
        start = max(0, range_start - file_start_offset)
    if range_end is not None:
        end = min(file_size - 1, range_end - file_start_offset)

    start += file_info.data_start_offset
    end += file_info.data_start_offset

    # Compute the ranges in chunks
    ranges = []
    for chunk_start in range(start, end + 1, range_size):
        chunk_end = min(chunk_start + range_size - 1, end)
        ranges.append((chunk_start, chunk_end))

    return ranges


def _chunks_from_s3_objects(
    s3_client: S3Client,
    files_info: list[S3FileInfo],
    byte_range: tuple[Optional[int], Optional[int]],
    range_size: int,
    executor: ThreadPoolExecutor,
) -> Iterator[tuple[int, Iterator[bytes]]]:
    """Download chunks from S3 objects in parallel, respecting byte ranges and file order."""
    # Prepare ranges and futures per file
    pending_chunks_count = 0
    for f_info in files_info:
        ranges = _compute_file_ranges(f_info, byte_range, range_size)

        f_info.buffers = {}
        f_info.next_yield = 0

        if not ranges:
            # Mark as inactive
            f_info.pending_ranges = []
            continue

        f_info.pending_ranges = ranges

        pending_chunks_count += len(ranges)

    # Keep only files that actually have something to download
    active_indices = [i for i, fi in enumerate(files_info) if fi.pending_ranges]

    # Combine all futures to wait on globally (initially empty)
    all_futures = {}

    # Track outstanding chunks and next file index
    total_outstanding_chunks = 0
    next_file_index = 0  # Track which file to submit from next

    def submit_tasks_to_limit() -> bool:
        """Submit S3 chunk download tasks up to the global backpressure limit, prioritizing files sequentially."""
        nonlocal all_futures, total_outstanding_chunks, next_file_index

        while total_outstanding_chunks < BACKPRESSURE_DOWNLOAD_CHUNKS:
            if next_file_index >= len(files_info):
                break  # No more files with pending ranges

            f_info = files_info[next_file_index]
            if f_info.pending_ranges:
                start, end = f_info.pending_ranges.pop(0)
                future = executor.submit(
                    fetch_range,
                    f_info.bucket_name,
                    f_info.key,
                    start,
                    end,
                    s3_client,
                )
                all_futures[future] = (f_info, start, end)
                total_outstanding_chunks += 1

                if not f_info.pending_ranges:
                    next_file_index += 1  # Move to next file when current is exhausted
            else:
                next_file_index += 1  # Skip completed files
                # If we reach here, no files have pending ranges

        return False

    def make_chunks_generator(target_info: S3FileInfo) -> Iterator[bytes]:
        """Create a generator bound to a specific file info (no late-binding bug)."""
        info = target_info  # bind
        nonlocal all_futures, total_outstanding_chunks, pending_chunks_count
        while info.next_yield < info.size:
            # First, try to flush anything already buffered for this file
            next_start = info.next_yield
            flushed = False
            while next_start in info.buffers:
                chunk = info.buffers.pop(next_start)
                if not isinstance(chunk, bytes):
                    raise InvalidDataError(
                        f"Expected bytes, got {type(chunk).__name__} in stream chunks: {chunk}"
                    )
                chunk_len = len(chunk)

                yield chunk
                next_start += chunk_len
                info.next_yield = next_start
                flushed = True
                total_outstanding_chunks -= 1
                pending_chunks_count -= 1

            if info.next_yield >= info.size:
                break

            # If we flushed something, loop back to try again before waiting
            if flushed:
                continue

            # Nothing to flush for this file: wait for more futures to complete globally
            if not pending_chunks_count:
                # No more incoming data anywhere; stop to avoid waiting on an empty set
                break

            done, _ = wait(all_futures.keys(), return_when=FIRST_COMPLETED)
            for fut in done:
                f_info, start, end = all_futures.pop(fut)
                data = fut.result()
                # Store buffer with a key relative to the start of the file data
                rel_start = start - f_info.data_start_offset
                f_info.buffers[rel_start] = data

            submit_tasks_to_limit()

    submit_tasks_to_limit()

    # Yield per-file generators with their original indices
    for idx in active_indices:
        yield idx, make_chunks_generator(files_info[idx])


def _build_stream_response(
    zip_filename: str,
    files_info: list[S3FileInfo],
    files_iterator: Iterator[tuple[int, Iterator[bytes]]],
    compress: Literal["zip", "raw", "auto"],
    executor: ThreadPoolExecutor,
) -> StreamResponse:
    """
    Build a streaming HTTP response for one or multiple files from S3, supporting ZIP, raw, and multipart formats.

    The response format depends on the `compress` parameter and the number of files:

    - If `compress` is "zip" or "auto" with multiple files, returns a ZIP archive containing all files.
    - If `compress` is "raw" and multiple files, returns a multipart/mixed response with each file as a part.
    - If only one file is present and `compress` is "raw" or "auto", streams the file directly with its MIME type.

    Response formats:

    - ZIP archive (Content-Type: application/zip) with Content-Disposition for download.
    - Multipart/mixed (Content-Type: multipart/mixed; boundary=...) with each file as a part.
    - Single raw file stream with its MIME type and Content-Disposition for download.

    :param zip_filename: Base filename to use for the ZIP archive (without extension).
    :param files_info: List of S3FileInfo objects describing each file (metadata, MIME type, etc.).
    :param files_iterator: Iterator yielding (file_index, chunk_iterator) for streaming file contents.
    :param compress: Output format:
        - "zip": Always produce a ZIP archive.
        - "raw": Stream files directly, as a single file or multipart.
        - "auto": ZIP if multiple files, raw if single file.
    :param executor: Executor used for concurrent streaming and cleanup.
    :return: Streaming HTTP response with appropriate content, headers, and media type.
    """

    def _build_response(
        content_gen: Iterable[bytes],
        media_type: str,
        filename: Optional[str] = None,
        size: Optional[int] = None,
    ) -> StreamResponse:
        return StreamResponse(
            content=content_gen,
            media_type=media_type,
            headers={"Accept-Ranges": "bytes"},
            filename=filename,
            size=size,
        )

    zip_response = (len(files_info) > 1 and compress == "auto") or compress == "zip"

    if zip_response:
        zs = ZipStream(sized=True)
        for index, chunks_generator in files_iterator:
            file_info = files_info[index]
            file_path = file_info.rel_path or file_info.key
            zs.add(chunks_generator, file_path, size=file_info.size)

        return _build_response(
            content_gen=zs,
            media_type="application/zip",
            filename=f"{zip_filename}.zip",
            size=len(zs),
        )
    elif len(files_info) > 1:
        boundary = uuid.uuid4().hex

        def multipart_stream():
            current_index = -1
            for index, chunks_generator in files_iterator:
                if index != current_index:
                    if current_index != -1:
                        yield b"\r\n"
                    filename = os.path.basename(files_info[index].key)
                    yield (
                        f"--{boundary}\r\n"
                        f'Content-Disposition: attachment; filename="{filename}"\r\n'
                        f"Content-Type: {files_info[index].data_type}\r\n\r\n"
                    ).encode()
                    current_index = index
                yield from chunks_generator
            yield f"\r\n--{boundary}--\r\n".encode()

        return _build_response(
            content_gen=multipart_stream(),
            media_type=f"multipart/mixed; boundary={boundary}",
        )
    else:
        index, chunks_generator = next(files_iterator)
        first_chunk = next(chunks_generator)
        filename = os.path.basename(files_info[index].key)

        def single_file_stream() -> Iterator[bytes]:
            yield first_chunk
            yield from chunks_generator

        return _build_response(
            content_gen=single_file_stream(),
            media_type=files_info[index].data_type,
            filename=filename,
        )


def stream_download_from_s3(
    s3_client: S3Client,
    files_info: list[S3FileInfo],
    byte_range: tuple[Optional[int], Optional[int]] = (None, None),
    compress: Literal["zip", "raw", "auto"] = "auto",
    zip_filename: str = "archive",
    range_size: int = 1024**2 * 16,
    max_workers: int = 8,
) -> StreamResponse:
    """
    Stream data from one or more S3 objects in chunks, with support for global byte ranges.

    This function provides efficient streaming download of S3 objects with support for:

    * Single file streaming with direct MIME type detection
    * Multiple file streaming as ZIP archives
    * Byte range requests for partial content
    * Files within ZIP archives (using ``.zip!`` notation)
    * Concurrent chunk downloading for improved performance
    * Memory-efficient streaming without loading entire files

    The response format depends on the compress parameter and number of files:

    * Single file + ``compress="raw"`` or ``"auto"``: streams file directly with detected MIME type
    * Multiple files + ``compress="zip"`` or ``"auto"``: creates ZIP archive containing all files
    * ``compress="zip"``: always creates ZIP archive regardless of file count

    For files stored within ZIP archives, use the ``.zip!`` notation in the ``S3FileInfo.key``:
    ``"path/to/archive.zip!internal/file.txt"``

    :param s3_client: Boto3 S3 client instance for making requests
    :param files_info: List of S3FileInfo objects describing files to download.
        Each object must contain at minimum: ``bucket_name``, ``key``, and ``size``.
        Optional fields include: ``data_type``, ``rel_path``, ``zip_filepath``.
    :param byte_range: Global byte range to download as ``(start, end)`` tuple.
        ``None`` values indicate open-ended ranges.
        Applied across the logical concatenation of all files.
    :param compress: Output format control:

        * ``"zip"``: Always create ZIP archive
        * ``"raw"``: Stream files directly (single) or as multipart (multiple)
        * ``"auto"``: ZIP for multiple files, raw for single file

    :param zip_filename: Base filename for ZIP archives (without ``.zip`` extension).
        Only used when creating ZIP archives.
    :param range_size: Size of each download chunk in bytes. Larger chunks reduce
        request overhead but use more memory. Default: 8MB.
    :param max_workers: Maximum number of concurrent download threads.
        Higher values improve throughput for multiple ranges.
    :return: StreamResponse object containing:

        * ``content``: Iterator of bytes for the streaming response
        * ``media_type``: MIME type (``"application/zip"`` for archives, detected type for single files)
        * ``headers``: HTTP headers including Content-Disposition for downloads

    :rtype: StreamResponse
    :raises InvalidDataError: If ZIP file structures are malformed
    :raises NotAvailableError: If S3 objects cannot be accessed
    :raises AuthenticationError: If S3 credentials are invalid
    :raises NotImplementedError: If compressed files within ZIP archives are encountered

    Example usage:

    .. code-block:: python

        import boto3
        from eodag.utils.s3 import stream_download_from_s3, S3FileInfo

        # Create S3 client
        s3_client = boto3.client('s3')

        # Single file download
        files = [S3FileInfo(bucket_name="bucket", key="file.txt", size=1024)]
        response = stream_download_from_s3(s3_client, files)

        # Multiple files as ZIP archive
        files = [
            S3FileInfo(bucket_name="bucket", key="file1.txt", size=1024),
            S3FileInfo(bucket_name="bucket", key="file2.txt", size=2048)
        ]
        response = stream_download_from_s3(s3_client, files, compress="zip")

        # File within ZIP archive
        files = [S3FileInfo(
            bucket_name="bucket",
            key="archive.zip!internal.txt",
            size=512
        )]
        response = stream_download_from_s3(s3_client, files)

        # Process streaming response
        for chunk in response.content:
            # Handle chunk data
            pass
    """

    executor = ThreadPoolExecutor(max_workers=max_workers)

    # Prepare all files
    offset = 0
    for f_info in files_info:
        if ".zip!" in f_info.key:
            _prepare_file_in_zip(f_info, s3_client)

        f_info.file_start_offset = offset
        offset += f_info.size

        if not f_info.data_type or f_info.data_type == MIME_OCTET_STREAM:
            guessed = guess_file_type(f_info.key)
            f_info.data_type = guessed or MIME_OCTET_STREAM

    # Create the files iterator using the original approach
    files_iterator = _chunks_from_s3_objects(
        s3_client, files_info, byte_range, range_size, executor
    )

    # Use the existing _build_stream_response function with the additional parameters
    return _build_stream_response(
        zip_filename=zip_filename,
        files_info=files_info,
        files_iterator=files_iterator,
        compress=compress,
        executor=executor,
    )


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


# ----- ZIP section -----


def open_s3_zipped_object(
    bucket_name: str,
    key_name: str,
    s3_client,
    zip_size: Optional[int] = None,
    partial: bool = True,
) -> tuple[ZipFile, bytes]:
    """
    Fetches the central directory and EOCD (End Of Central Directory) from an S3 object and opens a ZipFile in memory.

    This function retrieves the ZIP file's central directory and EOCD by performing range requests on the S3 object.
    It supports partial fetching (only the central directory and EOCD) for efficiency, or full ZIP download if needed.

    :param bucket_name: Name of the S3 bucket containing the ZIP file.
    :param key_name: Key (path) of the ZIP file in the S3 bucket.
    :param s3_client: S3 client instance used to perform range requests.
    :param zip_size: Size of the ZIP file in bytes. If None, it will be determined via a HEAD request.
    :param partial: If True, only fetch the central directory and EOCD. If False, fetch the entire ZIP file.
    :return: Tuple containing the opened ZipFile object and the central directory bytes.
    :raises InvalidDataError: If the EOCD signature is not found in the last 64KB of the file.
    """
    # EOCD is at least 22 bytes, but can be longer if ZIP comment exists.
    # For simplicity, we fetch last 64KB max (max EOCD + comment length allowed by ZIP spec)
    if zip_size is None:
        response = s3_client.head_object(Bucket=bucket_name, Key=key_name)
        zip_size = int(response["ContentLength"])

    fetch_size = min(65536, zip_size)
    eocd_search = fetch_range(
        bucket_name, key_name, zip_size - fetch_size, zip_size - 1, s3_client
    )

    # Find EOCD signature from end: 0x06054b50 (little endian)
    eocd_signature = b"\x50\x4b\x05\x06"
    eocd_offset = eocd_search.rfind(eocd_signature)
    if eocd_offset == -1:
        raise InvalidDataError("EOCD signature not found in last 64KB of the file.")

    eocd = eocd_search[eocd_offset : eocd_offset + 22]

    cd_size = parse_le_uint32(eocd[12:16])
    cd_start = parse_le_uint32(eocd[16:20])

    # Fetch central directory
    cd_data = fetch_range(
        bucket_name, key_name, cd_start, cd_start + cd_size - 1, s3_client
    )

    zip_data = (
        cd_data + eocd
        if partial
        else fetch_range(bucket_name, key_name, 0, zip_size - 1, s3_client)
    )
    zipf = ZipFile(io.BytesIO(zip_data))
    return zipf, cd_data


def _parse_central_directory_entry(cd_data: bytes, offset: int) -> dict[str, int]:
    """
    Parse one central directory file header entry starting at offset.
    Returns dict with relative local header offset and sizes.
    """
    signature = cd_data[offset : offset + 4]
    if signature != b"PK\x01\x02":
        raise InvalidDataError("Bad central directory file header signature")

    filename_len = parse_le_uint16(cd_data[offset + 28 : offset + 30])
    extra_len = parse_le_uint16(cd_data[offset + 30 : offset + 32])
    comment_len = parse_le_uint16(cd_data[offset + 32 : offset + 34])

    relative_offset = parse_le_uint32(cd_data[offset + 42 : offset + 46])

    header_size = 46 + filename_len + extra_len + comment_len

    return {
        "relative_offset": relative_offset,
        "header_size": header_size,
        "filename_len": filename_len,
        "extra_len": extra_len,
        "comment_len": comment_len,
        "total_size": header_size,
    }


def _parse_local_file_header(local_header_bytes: bytes) -> int:
    """
    Parse local file header to find total header size:
    fixed 30 bytes + filename length + extra field length
    """
    if local_header_bytes[0:4] != b"PK\x03\x04":
        raise InvalidDataError("Bad local file header signature")

    filename_len = parse_le_uint16(local_header_bytes[26:28])
    extra_len = parse_le_uint16(local_header_bytes[28:30])
    total_size = 30 + filename_len + extra_len
    return total_size


def file_position_from_s3_zip(
    s3_bucket: str,
    object_key: str,
    s3_client,
    target_filepath: str,
) -> tuple[int, int]:
    """
    Get the start position and size of a specific file inside a ZIP archive stored in S3.
    This function assumes the file is uncompressed (ZIP_STORED).

    The returned tuple contains:

    - **file_data_start**: The byte offset where the file data starts in the ZIP archive.
    - **file_size**: The size of the file in bytes.

    :param s3_bucket: The S3 bucket name.
    :param object_key: The S3 object key for the ZIP file.
    :param s3_client: The Boto3 S3 client.
    :param target_filepath: The file path inside the ZIP archive to locate.
    :return: A tuple (file_data_start, file_size)
    :raises FileNotFoundError: If the target file is not found in the ZIP archive.
    :raises NotImplementedError: If the file is not uncompressed (ZIP_STORED)
    """
    zipf, cd_data = open_s3_zipped_object(s3_bucket, object_key, s3_client)

    # Find file in zipf.filelist to get its index and f_info
    target_info = None
    cd_offset = 0
    for fi in zipf.filelist:
        if fi.filename == target_filepath:
            target_info = fi
            break
        # 46 is the fixed size (in bytes) of the Central Directory File Header according to the ZIP spec
        cd_entry_len = (
            46 + len(fi.filename.encode("utf-8")) + len(fi.extra) + len(fi.comment)
        )
        cd_offset += cd_entry_len

    zipf.close()

    if target_info is None:
        raise FileNotFoundError(f"File {target_filepath} not found in ZIP archive")

    if target_info.compress_type != ZIP_STORED:
        raise NotImplementedError("Only uncompressed files (ZIP_STORED) are supported.")

    # Parse central directory entry to get relative local header offset
    cd_entry = cd_data[
        cd_offset : cd_offset
        + (
            46
            + len(target_info.filename.encode("utf-8"))
            + len(target_info.extra)
            + len(target_info.comment)
        )
    ]
    cd_entry_info = _parse_central_directory_entry(cd_entry, 0)

    local_header_offset = cd_entry_info["relative_offset"]

    # Fetch local file header from S3 (at least 30 bytes + filename + extra field)
    # We'll fetch 4 KB max to cover large filenames/extra fields safely
    local_header_fetch_size = 4096
    local_header_bytes = fetch_range(
        s3_bucket,
        object_key,
        local_header_offset,
        local_header_offset + local_header_fetch_size - 1,
        s3_client,
    )

    local_header_size = _parse_local_file_header(local_header_bytes)

    # Calculate file data start and end offsets
    file_data_start = local_header_offset + local_header_size

    return file_data_start, target_info.file_size


def list_files_in_s3_zipped_object(
    bucket_name: str, key_name: str, s3_client: S3Client
) -> list[ZipInfo]:
    """
    List files in s3 zipped object, without downloading it.

    See https://stackoverflow.com/questions/41789176/how-to-count-files-inside-zip-in-aws-s3-without-downloading-it;
    Based on https://stackoverflow.com/questions/51351000/read-zip-files-from-s3-without-downloading-the-entire-file

    :param bucket_name: Bucket name of the object to fetch
    :param key_name: Key name of the object to fetch
    :param s3_resource: s3 resource used to fetch the object
    :returns: List of files in zip
    """
    zip_file, _ = open_s3_zipped_object(bucket_name, key_name, s3_client)
    with zip_file:
        logger.debug("Found %s files in %s" % (len(zip_file.filelist), key_name))
        return zip_file.filelist
