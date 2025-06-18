import os
import zipfile
from unittest import TestCase

import boto3
from moto import mock_aws

from tests import TEST_RESOURCES_PATH
from tests.context import (
    AwsAuth,
    EOProduct,
    MisconfiguredError,
    PluginConfig,
    list_files_in_s3_zipped_object,
    open_s3_zipped_object,
    update_assets_from_s3,
)


class TestUtilsS3(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestUtilsS3, cls).setUpClass()
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

    @classmethod
    def tearDownClass(cls):
        cls.mock_aws.stop()

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
        zip_file = open_s3_zipped_object(
            "mybucket", "path/to/product.zip", self.s3_client
        )
        self.assertIsInstance(zip_file, zipfile.ZipFile)
        self.assertEqual(len(zip_file.filelist), 6)

    def test_utils_s3_update_assets_from_s3_zip(self):
        """update_assets_from_s3 must update the assets of a product from a zipped object stored in S3"""
        prod = EOProduct("dummy", dict(geometry="POINT (0 0)", id="foo"))
        auth_plugin = AwsAuth(
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
        update_assets_from_s3(
            prod, auth_plugin, content_url="s3://mybucket/path/to/product.zip"
        )
        self.assertEqual(len(prod.assets), 3)
        self.assertDictEqual(
            prod.assets["MTD_MSIL1C.xml"].data,
            {
                "title": "MTD_MSIL1C.xml",
                "roles": ["metadata"],
                "href": "zip+s3://mybucket/path/to/product.zip!MTD_MSIL1C.xml",
                "type": "application/xml",
            },
        )
        self.assertDictEqual(
            prod.assets["MTD_TL.xml"].data,
            {
                "title": "MTD_TL.xml",
                "roles": ["metadata"],
                "href": "zip+s3://mybucket/path/to/product.zip!GRANULE/L1C_T31TDH_A013204_20180101T105435/MTD_TL.xml",
                "type": "application/xml",
            },
        )
        self.assertDictEqual(
            prod.assets["T31TDH_20180101T105441_B01.jp2"].data,
            {
                "title": "T31TDH_20180101T105441_B01.jp2",
                "roles": ["data"],
                "href": (
                    "zip+s3://mybucket/path/to/product.zip!"
                    "GRANULE/L1C_T31TDH_A013204_20180101T105435/IMG_DATA/T31TDH_20180101T105441_B01.jp2"
                ),
                "type": "image/jp2",
            },
        )

    def test_utils_s3_update_assets_from_s3(self):
        """update_assets_from_s3 must update the assets of a product from a folder stored in S3"""
        prod = EOProduct("dummy", dict(geometry="POINT (0 0)", id="foo"))
        auth_plugin = AwsAuth(
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
        update_assets_from_s3(
            prod, auth_plugin, content_url="s3://mybucket/path/to/unzipped"
        )
        self.assertEqual(len(prod.assets), 3)
        self.assertDictEqual(
            prod.assets["MTD_MSIL1C.xml"].data,
            {
                "title": "MTD_MSIL1C.xml",
                "roles": ["metadata"],
                "href": "s3://mybucket/path/to/unzipped/MTD_MSIL1C.xml",
                "type": "application/xml",
            },
        )
        self.assertDictEqual(
            prod.assets["MTD_TL.xml"].data,
            {
                "title": "MTD_TL.xml",
                "roles": ["metadata"],
                "href": "s3://mybucket/path/to/unzipped/GRANULE/L1C_T31TDH_A013204_20180101T105435/MTD_TL.xml",
                "type": "application/xml",
            },
        )
        self.assertDictEqual(
            prod.assets["T31TDH_20180101T105441_B01.jp2"].data,
            {
                "title": "T31TDH_20180101T105441_B01.jp2",
                "roles": ["data"],
                "href": (
                    "s3://mybucket/path/to/unzipped/GRANULE/"
                    "L1C_T31TDH_A013204_20180101T105435/IMG_DATA/T31TDH_20180101T105441_B01.jp2"
                ),
                "type": "image/jp2",
            },
        )

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
