import io
import os
import re
import zipfile
from unittest import TestCase
from unittest.mock import call, patch

import boto3
from concurrent.futures import ThreadPoolExecutor
from moto import mock_aws

from tests import TEST_RESOURCES_PATH
from tests.context import (
    AwsAuth,
    EOProduct,
    InvalidDataError,
    MisconfiguredError,
    PluginConfig,
    S3FileInfo,
    StreamResponse,
    _chunks_from_s3_objects,
    _compute_file_ranges,
    _prepare_file_in_zip,
    file_position_from_s3_zip,
    list_files_in_s3_zipped_object,
    open_s3_zipped_object,
    stream_download_from_s3,
    update_assets_from_s3,
)


def make_mock_fileinfo(
    key,
    size=10,
    data_start_offset=0,
    file_start_offset=0,
    data_type="application/octet-stream",
):
    fi = S3FileInfo(key=key, size=size, data_type=data_type, bucket_name="mybucket")
    fi.rel_path = key
    fi.futures = {}
    fi.file_start_offset = file_start_offset
    fi.data_start_offset = data_start_offset
    return fi


class TestUtilsS3(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mock_aws = mock_aws()
        cls.mock_aws.start()

        cls.s3_client = boto3.client("s3", region_name="us-east-1")
        cls.s3_client.create_bucket(Bucket="mybucket")

        # zip to s3
        cls.s3_client.upload_file(
            os.path.join(
                TEST_RESOURCES_PATH,
                "products",
                "as_archive",
                "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911.zip",
            ),
            "mybucket",
            "path/to/product.zip",
        )

        # unzipped to s3
        s3_prefix = "path/to/unzipped"
        product_dir = os.path.join(
            TEST_RESOURCES_PATH,
            "products",
            "S2A_MSIL1C_20180101T105441_N0206_R051_T31TDH_20180101T124911",
        )
        for root, _, files in os.walk(product_dir):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                relative_path = os.path.relpath(file_path, product_dir)
                # windows path compatibilty
                s3_key = os.path.join(s3_prefix, relative_path).replace("\\", "/")
                cls.s3_client.upload_file(file_path, "mybucket", s3_key)

        cls.s3_client.put_object(Bucket="mybucket", Key="file1.txt", Body=b"abcdef")
        cls.s3_client.put_object(Bucket="mybucket", Key="file2.txt", Body=b"ghijkl")

    @classmethod
    def tearDownClass(cls):
        cls.mock_aws.stop()

    def setUp(self):
        self.prod = EOProduct("dummy", dict(geometry="POINT (0 0)", id="foo"))
        self.auth_plugin = AwsAuth(
            "dummy",
            PluginConfig.from_mapping(
                {
                    "type": "AwsAuth",
                    "credentials": dict(
                        aws_access_key_id="foo",
                        aws_secret_access_key="bar",
                    ),
                }
            ),
        )

    def assert_stream_response(
        self,
        response,
        expected_media_type,
        expected_filename_ext=None,
        expected_filename=None,
        expected_content=None,
        expected_files=None,
    ):
        self.assertIsInstance(response, StreamResponse)
        if expected_media_type == "multipart/mixed":
            self.assertTrue(response.media_type.startswith("multipart/mixed"))
        else:
            self.assertEqual(response.media_type, expected_media_type)
        if expected_filename_ext:
            self.assertIn("content-disposition", response.headers)
            match = re.search(
                r'filename="([^"]+)"',
                response.headers["content-disposition"],
            )
            self.assertIsNotNone(match)
            filename = match.group(1)  # type: ignore
            self.assertTrue(filename.endswith(expected_filename_ext))
        elif expected_filename:
            self.assertIn("content-disposition", response.headers)
            self.assertIn(expected_filename, response.headers["content-disposition"])
        else:
            self.assertNotIn("content-disposition", response.headers)

        # --- Content checks ---
        content = b"".join(response.content)
        if expected_content is not None:
            # For single file, raw
            self.assertEqual(content, expected_content)
        elif expected_files is not None:
            if expected_media_type == "application/zip":
                # For zipped responses: check zip content
                with io.BytesIO(content) as bio:
                    with zipfile.ZipFile(bio) as zf:
                        names = set(zf.namelist())
                        self.assertEqual(names, set(expected_files.keys()))
                        for fname, fcontent in expected_files.items():
                            self.assertEqual(zf.read(fname), fcontent)
            elif expected_media_type == "multipart/mixed":
                # For multipart: check that all filenames are present in the payload
                for fname in expected_files:
                    self.assertIn(fname.encode(), content)

    def test_utils_s3_list_files_in_s3_zipped_object(self):
        """list_files_in_s3_zipped_object must list the files in a zipped object stored in S3"""
        zip_infos = list_files_in_s3_zipped_object(
            "mybucket", "path/to/product.zip", self.s3_client
        )
        self.assertListEqual(
            [z.filename for z in zip_infos],
            [
                "GRANULE/",
                "GRANULE/L1C_T31TDH_A013204_20180101T105435/",
                "GRANULE/L1C_T31TDH_A013204_20180101T105435/IMG_DATA/",
                "GRANULE/L1C_T31TDH_A013204_20180101T105435/IMG_DATA/T31TDH_20180101T105441_B01.jp2",
                "GRANULE/L1C_T31TDH_A013204_20180101T105435/MTD_TL.xml",
                "MTD_MSIL1C.xml",
            ],
        )

    def test_utils_s3_open_s3_zipped_object(self):
        """list_files_in_s3_zipped_object must list the files in a zipped object stored in S3"""
        zip_file, cd_data = open_s3_zipped_object(
            "mybucket", "path/to/product.zip", self.s3_client
        )
        self.assertIsInstance(zip_file, zipfile.ZipFile)
        self.assertIsInstance(cd_data, bytes)
        self.assertEqual(len(zip_file.filelist), 6)

    def test_utils_s3_update_assets_from_s3_zip(self):
        """update_assets_from_s3 must update the assets of a product from a zipped object stored in S3"""
        update_assets_from_s3(
            self.prod, self.auth_plugin, content_url="s3://mybucket/path/to/product.zip"
        )
        self.assertEqual(len(self.prod.assets), 3)
        expected_assets = {
            "MTD_MSIL1C.xml": {
                "title": "MTD_MSIL1C.xml",
                "roles": ["metadata"],
                "href": "zip+s3://mybucket/path/to/product.zip!MTD_MSIL1C.xml",
                "type": "application/xml",
            },
            "MTD_TL.xml": {
                "title": "MTD_TL.xml",
                "roles": ["metadata"],
                "href": "zip+s3://mybucket/path/to/product.zip!GRANULE/L1C_T31TDH_A013204_20180101T105435/MTD_TL.xml",
                "type": "application/xml",
            },
            "T31TDH_20180101T105441_B01.jp2": {
                "title": "T31TDH_20180101T105441_B01.jp2",
                "roles": ["data"],
                "href": (
                    "zip+s3://mybucket/path/to/product.zip!"
                    "GRANULE/L1C_T31TDH_A013204_20180101T105435/IMG_DATA/T31TDH_20180101T105441_B01.jp2"
                ),
                "type": "image/jp2",
            },
        }
        for asset_name, expected in expected_assets.items():
            with self.subTest(asset=asset_name):
                self.assertDictEqual(self.prod.assets[asset_name].data, expected)

    def test_utils_s3_update_assets_from_s3(self):
        """update_assets_from_s3 must update the assets of a product from a folder stored in S3"""
        update_assets_from_s3(
            self.prod, self.auth_plugin, content_url="s3://mybucket/path/to/unzipped"
        )
        self.assertEqual(len(self.prod.assets), 3)
        expected_assets = {
            "MTD_MSIL1C.xml": {
                "title": "MTD_MSIL1C.xml",
                "roles": ["metadata"],
                "href": "s3://mybucket/path/to/unzipped/MTD_MSIL1C.xml",
                "type": "application/xml",
            },
            "MTD_TL.xml": {
                "title": "MTD_TL.xml",
                "roles": ["metadata"],
                "href": "s3://mybucket/path/to/unzipped/GRANULE/L1C_T31TDH_A013204_20180101T105435/MTD_TL.xml",
                "type": "application/xml",
            },
            "T31TDH_20180101T105441_B01.jp2": {
                "title": "T31TDH_20180101T105441_B01.jp2",
                "roles": ["data"],
                "href": (
                    "s3://mybucket/path/to/unzipped/GRANULE/"
                    "L1C_T31TDH_A013204_20180101T105435/IMG_DATA/T31TDH_20180101T105441_B01.jp2"
                ),
                "type": "image/jp2",
            },
        }
        for asset_name, expected in expected_assets.items():
            with self.subTest(asset=asset_name):
                self.assertDictEqual(self.prod.assets[asset_name].data, expected)

    def test_utils_s3_update_assets_from_s3_credentials_nok(self):
        """update_assets_from_s3 must have required credentials"""
        prod = EOProduct("dummy", dict(geometry="POINT (0 0)", id="foo"))
        auth_plugin = AwsAuth("dummy", PluginConfig())
        self.assertRaises(
            MisconfiguredError,
            update_assets_from_s3,
            prod,
            auth_plugin,
            content_url="s3://mybucket/path/to/unzipped",
        )

    def test_utils_s3_file_position_from_s3_zip(self):
        # Prepare a zip with both uncompressed and compressed files
        zip_bytes = io.BytesIO()
        with zipfile.ZipFile(zip_bytes, "w", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("intro.txt", "Intro file content.")
            zf.writestr("folder/data.txt", "This is a test.")
        zip_bytes.seek(0)
        self.s3_client.put_object(
            Bucket="mybucket", Key="test_uncompressed.zip", Body=zip_bytes.read()
        )

        # Prepare a zip with a compressed file
        zip_bytes2 = io.BytesIO()
        with zipfile.ZipFile(zip_bytes2, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("compressed.txt", "compressed content")
        zip_bytes2.seek(0)
        self.s3_client.put_object(
            Bucket="mybucket", Key="test_compressed.zip", Body=zip_bytes2.read()
        )

        test_cases = [
            {
                "desc": "uncompressed file found",
                "bucket": "mybucket",
                "key": "test_uncompressed.zip",
                "filename": "folder/data.txt",
                "expected_start": 103,
                "expected_size": 15,
                "expect_exception": None,
            },
            {
                "desc": "file not found",
                "bucket": "mybucket",
                "key": "test_uncompressed.zip",
                "filename": "does/not/exist.txt",
                "expected_start": None,
                "expected_size": None,
                "expect_exception": FileNotFoundError,
            },
            {
                "desc": "compressed file",
                "bucket": "mybucket",
                "key": "test_compressed.zip",
                "filename": "compressed.txt",
                "expected_start": None,
                "expected_size": None,
                "expect_exception": NotImplementedError,
            },
        ]

        for case in test_cases:
            with self.subTest(msg=case["desc"]):
                if case["expect_exception"]:
                    with self.assertRaises(case["expect_exception"]) as ctx:
                        file_position_from_s3_zip(
                            case["bucket"],
                            case["key"],
                            self.s3_client,
                            case["filename"],
                        )
                    if case["expect_exception"] is NotImplementedError:
                        self.assertIn(
                            "Only uncompressed files (ZIP_STORED) are supported.",
                            str(ctx.exception),
                        )
                else:
                    start, size = file_position_from_s3_zip(
                        case["bucket"], case["key"], self.s3_client, case["filename"]
                    )
                    self.assertIsInstance(start, int)
                    self.assertIsInstance(size, int)
                    self.assertEqual(start, case["expected_start"])
                    self.assertEqual(size, case["expected_size"])

    def test_utils_s3_open_s3_zipped_object_invalid(self):
        """Test a corrupted ZIP file to ensure you raise properly on bad EOCD."""
        self.s3_client.put_object(
            Bucket="mybucket", Key="bad.zip", Body=b"This is not a zip"
        )
        from tests.context import open_s3_zipped_object

        with self.assertRaises(InvalidDataError) as e:
            open_s3_zipped_object("mybucket", "bad.zip", self.s3_client)
        self.assertIn("EOCD signature not found", str(e.exception))

    def test_utils_s3_empty_zip(self):
        """Test an empty ZIP file to ensure it returns an empty list."""
        empty_zip = io.BytesIO()
        with zipfile.ZipFile(empty_zip, "w"):
            pass
        empty_zip.seek(0)
        self.s3_client.put_object(
            Bucket="mybucket", Key="empty.zip", Body=empty_zip.read()
        )

        files = list_files_in_s3_zipped_object("mybucket", "empty.zip", self.s3_client)
        self.assertEqual(files, [])

    def test_chunks_from_s3_objects(self):
        """Test _chunks_from_s3_objects to ensure it correctly retrieves data from S3 objects."""

        data = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        self.s3_client.put_object(Bucket="mybucket", Key="alpha", Body=data)

        fi = make_mock_fileinfo("alpha", len(data))
        fi.data_start_offset = 0

        with ThreadPoolExecutor(max_workers=2) as executor:
            it = _chunks_from_s3_objects(
                self.s3_client, [fi], (None, None), range_size=10, executor=executor
            )
            idx, gen = next(it)
            chunks = b"".join(gen)
            self.assertEqual(idx, 0)
            self.assertEqual(chunks, data)

    def test_chunks_from_s3_objects_chunk_count_and_worker_usage(self):
        """Test that correct number of chunks are requested and workers are used efficiently."""

        data_map = {
            "file1": b"A" * 25,  # 3 chunks (10 + 10 + 5)
            "file2": b"B" * 30,  # 3 chunks (10 + 10 + 10)
        }
        range_size = 10

        file_infos = []
        for key, body in data_map.items():
            self.s3_client.put_object(Bucket="mybucket", Key=key, Body=body)
            fi = make_mock_fileinfo(key, len(body))
            fi.data_start_offset = 0
            file_infos.append(fi)

        with patch(
            "eodag.utils.s3.fetch_range", return_value=b"X" * range_size
        ) as mock_fetch:
            with ThreadPoolExecutor(max_workers=4) as executor:
                result = _chunks_from_s3_objects(
                    self.s3_client,
                    file_infos,
                    byte_range=(None, None),
                    range_size=range_size,
                    executor=executor,
                )

                for _ in result:
                    pass

            # Each 10-byte chunk corresponds to one fetch_range call
            expected_calls = [
                call("mybucket", "file1", 0, 9, self.s3_client),
                call("mybucket", "file1", 10, 19, self.s3_client),
                call("mybucket", "file1", 20, 24, self.s3_client),
                call("mybucket", "file2", 0, 9, self.s3_client),
                call("mybucket", "file2", 10, 19, self.s3_client),
                call("mybucket", "file2", 20, 29, self.s3_client),
            ]

            self.assertEqual(mock_fetch.call_count, 6)
            mock_fetch.assert_has_calls(expected_calls, any_order=True)

    def test_prepare_file_in_zip(self):
        """Test _prepare_file_in_zip to ensure it sets the correct attributes for retrieving a file inside a ZIP."""

        zip_bytes = io.BytesIO()
        with zipfile.ZipFile(zip_bytes, "w", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("foo.txt", "hello")
        zip_bytes.seek(0)
        self.s3_client.put_object(
            Bucket="mybucket", Key="test.zip", Body=zip_bytes.read()
        )

        fi = make_mock_fileinfo("test.zip!foo.txt", 0)
        _prepare_file_in_zip(fi, self.s3_client)

        self.assertEqual(fi.key, "test.zip")
        self.assertEqual(fi.zip_filepath, "foo.txt")
        self.assertGreater(fi.data_start_offset, 0)
        self.assertEqual(fi.size, len("hello"))

    def test_compute_file_ranges(self):
        """Test _compute_file_ranges to ensure it calculates correct byte ranges for files to download."""

        range_size = 10

        test_cases = [
            {
                "desc": "Full file, no byte_range limits (start=None, end=None)",
                "file_info": make_mock_fileinfo("a", 50),
                "byte_range": (None, None),
                "expected": [
                    (i, min(i + range_size - 1, 49)) for i in range(0, 50, range_size)
                ],
            },
            {
                "desc": "Partial overlap at start: range starts inside the file",
                "file_info": make_mock_fileinfo("a", 50, 5, 100),
                "byte_range": (110, 149),
                "expected": [(15, 24), (25, 34), (35, 44), (45, 54)],
            },
            {
                "desc": "Partial overlap at end: range ends inside the file",
                "file_info": make_mock_fileinfo("a", 50, 0, 100),
                "byte_range": (90, 120),
                "expected": [(0, 9), (10, 19), (20, 20)],
            },
            {
                "desc": "Range fully inside file",
                "file_info": make_mock_fileinfo("a", 50, 0, 0),
                "byte_range": (10, 29),
                "expected": [(10, 19), (20, 29)],
            },
            {
                "desc": "Range fully outside before file - should return None",
                "file_info": make_mock_fileinfo("a", 50, 0, 100),
                "byte_range": (0, 50),
                "expected": None,
            },
            {
                "desc": "Range fully outside after file - should return None",
                "file_info": make_mock_fileinfo("a", 50, 0, 100),
                "byte_range": (151, 200),
                "expected": None,
            },
            {
                "desc": "Open ended start range (None as start)",
                "file_info": make_mock_fileinfo("a", 50, 2, 100),
                "byte_range": (None, 105),
                "expected": [(2, 7)],
            },
            {
                "desc": "Open ended end range (None as end)",
                "file_info": make_mock_fileinfo("a", 50, 2, 100),
                "byte_range": (102, None),
                "expected": [(4, 13), (14, 23), (24, 33), (34, 43), (44, 51)],
            },
        ]

        for case in test_cases:
            with self.subTest(msg=case["desc"]):
                result = _compute_file_ranges(
                    case["file_info"], case["byte_range"], range_size
                )
                self.assertEqual(result, case["expected"])

    def test_stream_download_from_s3(self):
        test_cases = [
            {
                "desc": "single file, raw",
                "files_info": [
                    make_mock_fileinfo("file1.txt", size=6, data_type="text/plain")
                ],
                "compress": "raw",
                "zip_filename": "archive",
                "expected_media_type": "text/plain",
                "expected_filename_ext": None,
                "expected_filename": "file1.txt",
                "expected_content": b"abcdef",
            },
            {
                "desc": "multiple files, zip",
                "files_info": [
                    make_mock_fileinfo("file1.txt", size=6),
                    make_mock_fileinfo("file2.txt", size=6),
                ],
                "compress": "zip",
                "zip_filename": "myarchive",
                "expected_media_type": "application/zip",
                "expected_filename_ext": ".zip",
                "expected_files": {
                    "file1.txt": b"abcdef",
                    "file2.txt": b"ghijkl",
                },
            },
            {
                "desc": "multiple files, multipart",
                "files_info": [
                    make_mock_fileinfo("file1.txt", size=6, data_type="text/plain"),
                    make_mock_fileinfo("file2.txt", size=6, data_type="text/plain"),
                ],
                "compress": "raw",
                "zip_filename": "archive",
                "expected_media_type": "multipart/mixed",
                "expected_filename_ext": None,
                "expected_filename": None,
                "expected_files": {
                    "file1.txt": b"abcdef",
                    "file2.txt": b"ghijkl",
                },
            },
            {
                "desc": "single file, zipped",
                "files_info": [
                    make_mock_fileinfo("file1.txt", size=6, data_type="text/plain")
                ],
                "compress": "zip",
                "zip_filename": "singlefile",
                "expected_media_type": "application/zip",
                "expected_filename_ext": ".zip",
                "expected_files": {
                    "file1.txt": b"abcdef",
                },
            },
        ]

        for case in test_cases:
            with self.subTest(msg=case["desc"]):
                response = stream_download_from_s3(
                    s3_client=self.s3_client,
                    files_info=case["files_info"],
                    compress=case["compress"],
                    zip_filename=case["zip_filename"],
                    max_workers=2,
                )

                self.assert_stream_response(
                    response,
                    case["expected_media_type"],
                    expected_filename_ext=case.get("expected_filename_ext"),
                    expected_filename=case.get("expected_filename"),
                    expected_content=case.get("expected_content"),
                    expected_files=case.get("expected_files"),
                )
