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

import datetime
import glob
import hashlib
import multiprocessing
import os
import re
import shutil
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from eodag.api.product.metadata_mapping import ONLINE_STATUS
from tests import TEST_RESOURCES_PATH
from tests.context import (
    GENERIC_PRODUCT_TYPE,
    AuthenticationError,
    EODataAccessGateway,
    SearchResult,
    uri_to_path,
)

THEIA_SEARCH_ARGS = [
    "theia",
    "S2_MSI_L2A_MAJA",
    "2019-03-01",
    "2019-03-15",
    [0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565],
]
PEPS_SEARCH_ARGS = [
    "peps",
    "S2_MSI_L1C",
    "2020-08-08",
    "2020-08-16",
    [137.772897, 13.134202, 153.749135, 23.885986],
]
AWSEOS_SEARCH_ARGS = [
    "aws_eos",
    "S2_MSI_L1C",
    "2020-01-01",
    "2020-01-15",
    [0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565],
]
ASTRAE_EOD_SEARCH_ARGS = [
    "astraea_eod",
    "S2_MSI_L1C",
    "2020-01-01",
    "2020-01-15",
    [0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565],
]
EARTH_SEARCH_SEARCH_ARGS = [
    "earth_search",
    "S2_MSI_L1C",
    "2020-01-01",
    "2020-01-15",
    [0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565],
]
EARTH_SEARCH_COG_SEARCH_ARGS = [
    "earth_search_cog",
    "S2_MSI_L2A_COG",
    "2020-01-01",
    "2020-01-15",
    [0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565],
]
EARTH_SEARCH_GCS_SEARCH_ARGS = [
    "earth_search_gcs",
    "S2_MSI_L1C",
    "2020-01-01",
    "2020-01-15",
    [0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565],
]
USGS_SATAPI_AWS_SEARCH_ARGS = [
    "usgs_satapi_aws",
    "LANDSAT_C2L1",
    "2020-01-01",
    "2020-01-15",
    [0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565],
]
CREODIAS_SEARCH_ARGS = [
    "creodias",
    "S2_MSI_L1C",
    "2019-03-01",
    "2019-03-15",
    [0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565],
]
COP_DATASPACE_SEARCH_ARGS = [
    "cop_dataspace",
    "S2_MSI_L1C",
    "2019-03-01",
    "2019-03-15",
    [0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565],
]
MUNDI_SEARCH_ARGS = [
    "mundi",
    "S2_MSI_L1C",
    "2021-11-08",
    "2021-11-16",
    [0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565],
]
# As of 2021-01-14 the products previously required in 2020-08 were offline.
# Trying here to retrieve the most recent products which are more likely to be online.
today = datetime.date.today()
week_span = datetime.timedelta(days=7)
day_span = datetime.timedelta(days=1)
ONDA_SEARCH_ARGS = [
    "onda",
    "S2_MSI_L1C",
    (today - week_span).isoformat(),
    today.isoformat(),
    [0.2563590566012408, 43.19555008715042, 2.379835675499976, 43.907759172380565],
]
USGS_RECENT_SEARCH_ARGS = [
    "usgs",
    "LANDSAT_C2L1",
    (today - 6 * week_span).isoformat(),
    (today - 5 * week_span).isoformat(),
    [50, 50, 50.3, 50.3],
]
USGS_OLD_SEARCH_ARGS = [
    "usgs",
    "LANDSAT_C2L1",
    "2017-03-01",
    "2017-03-10",
    [50, 50, 50.3, 50.3],
]
ECMWF_SEARCH_ARGS = [
    "ecmwf",
    "TIGGE_CF_SFC",
    "2017-03-01",
    "2017-03-02",
    # no need of an additional post-processing area extraction
    [-180, -90, 180, 90],
]
ECMWF_SEARCH_KWARGS = {
    # request for only 1 parameter instead of all available
    "param": "tcc",
}
COP_ADS_SEARCH_ARGS = [
    "cop_ads",
    "CAMS_EAC4",
    "2021-01-01",
    "2021-01-05",
    # no need of an additional post-processing area extraction
    [-180, -90, 180, 90],
]
COP_ADS_SEARCH_KWARGS = {
    # request for grib file instead of netcdf
    "format": "grib",
}
COP_CDS_SEARCH_ARGS = [
    "cop_cds",
    "ERA5_SL",
    "2021-01-01",
    "2021-01-05",
    # no need of an additional post-processing area extraction
    [-180, -90, 180, 90],
]
COP_CDS_SEARCH_KWARGS = {
    # request for grib file instead of netcdf
    "format": "grib",
}
SARA_SEARCH_ARGS = [
    "sara",
    "S2_MSI_L1C",
    "2020-03-01",
    "2020-03-15",
    [150, -33, 151, -32],
]
METEOBLUE_SEARCH_ARGS = [
    "meteoblue",
    "NEMSGLOBAL_TCDC",
    (today + day_span).isoformat(),
    (today + 2 * day_span).isoformat(),
    [0.2, 43.2, 0.5, 43.5],
]


@pytest.mark.enable_socket
class EndToEndBase(unittest.TestCase):
    def execute_search(
        self,
        provider,
        product_type,
        start,
        end,
        geom,
        offline=False,
        page=None,
        items_per_page=None,
        check_product=True,
        search_kwargs_dict={},
    ):
        """Search products on provider:

        - First set the preferred provider as the one given in parameter
        - Then do the search
        - Then ensure that at least the first result originates from the provider
        - Return one product to be downloaded
        """
        search_criteria = {
            "productType": product_type,
            "start": start,
            "end": end,
            "geom": geom,
            "raise_errors": True,
            **search_kwargs_dict,
        }
        if items_per_page:
            search_criteria["items_per_page"] = items_per_page
        if page:
            search_criteria["page"] = page
        self.eodag.set_preferred_provider(provider)
        results, nb_results = self.eodag.search(**search_criteria)
        if offline:
            results = [
                prod
                for prod in results
                if prod.properties.get("storageStatus", "") != ONLINE_STATUS
            ]
        if check_product:
            self.assertGreater(len(results), 0)
            one_product = results[0]
            self.assertEqual(one_product.provider, provider)
            return one_product
        else:
            return results

    def execute_search_all(
        self,
        provider,
        product_type,
        start,
        end,
        geom,
        items_per_page=None,
        check_products=True,
    ):
        """Search all the products on provider:

        - First set the preferred provider as the one given in parameter
        - Then do the search_all
        - Then ensure that at least the first result originates from the provider
        - Return all the products
        """
        search_criteria = {
            "start": start,
            "end": end,
            "geom": geom,
        }
        self.eodag.set_preferred_provider(provider)
        results = self.eodag.search_all(
            productType=product_type, items_per_page=items_per_page, **search_criteria
        )
        if check_products:
            self.assertGreater(len(results), 0)
            one_product = results[0]
            self.assertEqual(one_product.provider, provider)
        return results


# @unittest.skip("skip auto run")
class TestEODagEndToEnd(EndToEndBase):
    """Make real case tests. This assume the existence of a user conf file in resources folder named user_conf.yml"""  # noqa

    @classmethod
    def setUpClass(cls):

        # use tests/resources/user_conf.yml if exists else default file ~/.config/eodag/eodag.yml
        tests_user_conf = os.path.join(TEST_RESOURCES_PATH, "user_conf.yml")
        if os.path.isfile(tests_user_conf):
            cls.eodag = EODataAccessGateway(
                user_conf_file_path=os.path.join(TEST_RESOURCES_PATH, "user_conf.yml")
            )
        else:
            cls.eodag = EODataAccessGateway()

        # temp download directory
        cls.tmp_download_dir = TemporaryDirectory()
        cls.tmp_download_path = cls.tmp_download_dir.name

        for provider, conf in cls.eodag.providers_config.items():
            # Change download directory to cls.tmp_download_path for tests
            if hasattr(conf, "download") and hasattr(conf.download, "outputs_prefix"):
                conf.download.outputs_prefix = cls.tmp_download_path
            elif hasattr(conf, "api") and hasattr(conf.api, "outputs_prefix"):
                conf.api.outputs_prefix = cls.tmp_download_path
            else:
                # no outputs_prefix found for provider
                pass
            # Force all providers implementing RestoSearch and defining how to retrieve
            # products by specifying the
            # location scheme to use https, enabling actual downloading of the product
            if (
                getattr(getattr(conf, "search", {}), "product_location_scheme", "https")
                == "file"
            ):
                conf.search.product_location_scheme = "https"
            # Disable extraction
            try:  # Case HTTPDownload plugin
                conf.download.extract = False
            except (KeyError, AttributeError):  # case api plugin
                conf.api.extract = False

    def setUp(self):
        self.downloaded_file_path = ""

    @classmethod
    def tearDownClass(cls):
        cls.tmp_download_dir.cleanup()

    def execute_download(self, product, expected_filename, wait_sec=5, timeout_sec=120):
        """Download the product in a child process, avoiding to perform the entire
        download, then do some checks and delete the downloaded result from the
        filesystem.
        """

        start_time = time.time()

        dl_pool = multiprocessing.Pool()

        dl_result = dl_pool.apply_async(
            func=self.eodag.download,
            args=(product, None, wait_sec / 60, timeout_sec / 60),
        )
        max_wait_time = timeout_sec
        while (
            not glob.glob("%s/[!quicklooks]*" % self.tmp_download_path)
            and max_wait_time > 0
        ):
            # check every 2s if download has start
            dl_result.wait(2)
            max_wait_time -= 2

        try:
            dl_result.get(timeout=wait_sec)
        except multiprocessing.TimeoutError:
            pass

        dl_pool.terminate()
        dl_pool.close()

        stop_time = time.time()
        print(stop_time - start_time)

        self.assertIn(
            expected_filename, os.listdir(product.downloader.config.outputs_prefix)
        )
        self.downloaded_file_path = os.path.join(
            product.downloader.config.outputs_prefix, expected_filename
        )
        # check whether expected_filename refers to a file or a dir
        if os.path.isdir(self.downloaded_file_path):
            product_directory = Path(self.downloaded_file_path)
            downloaded_size = sum(
                f.stat().st_size for f in product_directory.glob("**/*") if f.is_file()
            )
        else:
            downloaded_size = os.stat(self.downloaded_file_path).st_size
        # The partially downloaded file should be greater or equal to 5 KB
        self.assertGreaterEqual(downloaded_size, 5 * 2**10)

    def test_end_to_end_search_download_usgs_recent(self):
        product = self.execute_search(*USGS_RECENT_SEARCH_ARGS)
        expected_filename = "{}.tar.gz".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_usgs_old(self):
        product = self.execute_search(*USGS_OLD_SEARCH_ARGS)
        expected_filename = "{}.tar.gz".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    # @unittest.skip("service unavailable for the moment")
    def test_end_to_end_search_download_peps(self):
        product = self.execute_search(*PEPS_SEARCH_ARGS)
        expected_filename = "{}.zip".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_mundi(self):
        product = self.execute_search(*MUNDI_SEARCH_ARGS)
        expected_filename = "{}".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    # @unittest.skip("service unavailable for the moment")
    def test_end_to_end_search_download_theia(self):
        product = self.execute_search(*THEIA_SEARCH_ARGS)
        expected_filename = "{}.zip".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_creodias(self):
        product = self.execute_search(*CREODIAS_SEARCH_ARGS)
        expected_filename = "{}.zip".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_cop_dataspace(self):
        product = self.execute_search(*COP_DATASPACE_SEARCH_ARGS)
        expected_filename = "{}.zip".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_creodias_noresult(self):
        """Requesting a page on creodias with no results must return an empty SearchResult"""
        # As of 2021-03-19 this search at page 1 returns 31 products, so at page 2 there
        # are no products available and creodias returns a response without products (`hits`).
        product = self.execute_search(
            *CREODIAS_SEARCH_ARGS, page=2, items_per_page=50, check_product=False
        )
        self.assertEqual(len(product), 0)

    def test_end_to_end_search_download_onda(self):
        product = self.execute_search(*ONDA_SEARCH_ARGS)
        expected_filename = "{}.zip".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    # @unittest.skip("expired aws_eos api key")
    def test_end_to_end_search_download_aws_eos(self):
        product = self.execute_search(*AWSEOS_SEARCH_ARGS)
        expected_filename = "{}".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_astraea_eod(self):
        product = self.execute_search(*ASTRAE_EOD_SEARCH_ARGS)
        expected_filename = "{}".format(product.properties["title"])
        self.execute_download(product, expected_filename, wait_sec=15)

    def test_end_to_end_search_download_earth_search(self):
        product = self.execute_search(*EARTH_SEARCH_SEARCH_ARGS)
        expected_filename = "{}".format(product.properties["title"])
        self.execute_download(product, expected_filename, wait_sec=15)

    def test_end_to_end_search_download_earth_search_cog(self):
        product = self.execute_search(*EARTH_SEARCH_COG_SEARCH_ARGS)
        expected_filename = "{}".format(product.properties["title"])
        self.execute_download(product, expected_filename, wait_sec=20)

    def test_end_to_end_search_download_earth_search_gcs(self):
        product = self.execute_search(*EARTH_SEARCH_GCS_SEARCH_ARGS)
        expected_filename = "{}".format(product.properties["title"])
        self.execute_download(product, expected_filename, wait_sec=20)

    def test_end_to_end_search_download_usgs_satapi_aws(self):
        product = self.execute_search(*USGS_SATAPI_AWS_SEARCH_ARGS)
        expected_filename = "{}".format(product.properties["title"])
        self.execute_download(product, expected_filename, wait_sec=15)

    @unittest.skip(
        "The public datasets service will not be available during the DHS Move, "
        + "see https://confluence.ecmwf.int/x/jSKADQ"
    )
    def test_end_to_end_search_download_ecmwf(self):
        product = self.execute_search(
            *ECMWF_SEARCH_ARGS, search_kwargs_dict=ECMWF_SEARCH_KWARGS
        )
        expected_filename = "{}.grib".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_cop_ads(self):
        product = self.execute_search(
            *COP_ADS_SEARCH_ARGS, search_kwargs_dict=COP_ADS_SEARCH_KWARGS
        )
        expected_filename = "{}.grib".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_cop_cds(self):
        product = self.execute_search(
            *COP_CDS_SEARCH_ARGS, search_kwargs_dict=COP_CDS_SEARCH_KWARGS
        )
        expected_filename = "{}.grib".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_sara(self):
        product = self.execute_search(*SARA_SEARCH_ARGS)
        expected_filename = "{}.zip".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    def test_end_to_end_search_download_meteoblue(self):
        product = self.execute_search(*METEOBLUE_SEARCH_ARGS)
        expected_filename = "{}.nc".format(product.properties["title"])
        self.execute_download(product, expected_filename)

    # @unittest.skip("service unavailable for the moment")
    def test_get_quicklook_peps(self):
        product = self.execute_search(
            "peps", "S2_MSI_L1C", "2019-03-01", "2019-03-15", [50, 50, 50.3, 50.3]
        )
        quicklook_file_path = product.get_quicklook(filename="peps_quicklook")
        # TearDown will remove quicklook_file_path on end
        self.downloaded_file_path = quicklook_file_path

        self.assertNotEqual(quicklook_file_path, "")
        self.assertEqual(os.path.basename(quicklook_file_path), "peps_quicklook")
        self.assertEqual(
            os.path.dirname(quicklook_file_path),
            os.path.join(product.downloader.config.outputs_prefix, "quicklooks"),
        )
        self.assertGreaterEqual(os.stat(quicklook_file_path).st_size, 2**5)

    def test__search_by_id_creodias(self):
        # A single test with creodias to check that _search_by_id returns
        # correctly the exact product looked for.
        uid = "S2A_MSIL1C_20200810T030551_N0209_R075_T53WPU_20200810T050611"
        provider = "creodias"

        products, _ = self.eodag._search_by_id(
            uid=uid, provider=provider, productType="S2_MSI_L1C"
        )
        product = products[0]

        self.assertEqual(product.properties["id"], uid)
        self.assertIsNotNone(product.product_type)

    def test_end_to_end_search_all_mundi_default(self):
        # 23/03/2021: Got 16 products for this search
        results = self.execute_search_all(*MUNDI_SEARCH_ARGS)
        self.assertGreater(len(results), 10)

    def test_end_to_end_search_all_mundi_iterate(self):
        # 23/03/2021: Got 16 products for this search
        results = self.execute_search_all(*MUNDI_SEARCH_ARGS, items_per_page=10)
        self.assertGreater(len(results), 10)

    def test_end_to_end_search_all_astraea_eod_iterate(self):
        # 23/03/2021: Got 39 products for this search
        results = self.execute_search_all(*ASTRAE_EOD_SEARCH_ARGS, items_per_page=10)
        self.assertGreater(len(results), 10)

    def test_end_to_end_discover_product_types_creodias(self):
        """discover_product_types() must return an external product types configuration for creodias"""
        provider = "creodias"
        ext_product_types_conf = self.eodag.discover_product_types(provider=provider)
        self.assertEqual(
            "SENTINEL-1",
            ext_product_types_conf[provider]["providers_config"]["SENTINEL-1"][
                "collection"
            ],
        )
        self.assertEqual(
            "SENTINEL-1",
            ext_product_types_conf[provider]["product_types_config"]["SENTINEL-1"][
                "title"
            ],
        )
        # check that all pre-configured product types are listed by provider
        provider_product_types = [
            v["collection"]
            for k, v in self.eodag.providers_config[provider].products.items()
            if k != GENERIC_PRODUCT_TYPE
        ]
        for provider_product_type in provider_product_types:
            self.assertIn(
                provider_product_type,
                ext_product_types_conf[provider]["providers_config"],
            )

    def test_end_to_end_discover_product_types_astraea_eod(self):
        """discover_product_types() must return an external product types configuration for astraea_eod"""
        provider = "astraea_eod"
        ext_product_types_conf = self.eodag.discover_product_types(provider=provider)
        self.assertEqual(
            "sentinel1_l1c_grd",
            ext_product_types_conf[provider]["providers_config"]["sentinel1_l1c_grd"][
                "productType"
            ],
        )
        self.assertEqual(
            "Sentinel-1 L1C GRD",
            ext_product_types_conf[provider]["product_types_config"][
                "sentinel1_l1c_grd"
            ]["title"],
        )
        self.assertEqual(
            "CC-BY-SA-3.0",
            ext_product_types_conf[provider]["product_types_config"][
                "sentinel1_l1c_grd"
            ]["license"],
        )
        # check that all pre-configured product types are listed by provider
        provider_product_types = [
            v["productType"]
            for k, v in self.eodag.providers_config[provider].products.items()
            if k != GENERIC_PRODUCT_TYPE
        ]
        for provider_product_type in provider_product_types:
            self.assertIn(
                provider_product_type,
                ext_product_types_conf[provider]["providers_config"],
            )

    def test_end_to_end_discover_product_types_usgs_satapi_aws(self):
        """discover_product_types() must return an external product types configuration for usgs_satapi_aws"""
        provider = "usgs_satapi_aws"
        ext_product_types_conf = self.eodag.discover_product_types(provider=provider)
        self.assertEqual(
            "landsat-c2l1",
            ext_product_types_conf[provider]["providers_config"]["landsat-c2l1"][
                "productType"
            ],
        )
        self.assertEqual(
            "Landsat Collection 2 Level-1 Product",
            ext_product_types_conf[provider]["product_types_config"]["landsat-c2l1"][
                "title"
            ],
        )
        self.assertEqual(
            "1972-07-25T00:00:00.000Z",
            ext_product_types_conf[provider]["product_types_config"]["landsat-c2l1"][
                "missionStartDate"
            ],
        )
        # check that all pre-configured product types are listed by provider
        provider_product_types = [
            v["productType"]
            for k, v in self.eodag.providers_config[provider].products.items()
            if k != GENERIC_PRODUCT_TYPE
        ]
        for provider_product_type in provider_product_types:
            self.assertIn(
                provider_product_type,
                ext_product_types_conf[provider]["providers_config"],
            )

    def test_end_to_end_discover_product_types_earth_search(self):
        """discover_product_types() must return an external product types configuration for earth_search"""
        provider = "earth_search"
        ext_product_types_conf = self.eodag.discover_product_types(provider=provider)
        self.assertEqual(
            "sentinel-s2-l1c",
            ext_product_types_conf[provider]["providers_config"]["sentinel-s2-l1c"][
                "productType"
            ],
        )
        self.assertEqual(
            "Sentinel 2 L1C",
            ext_product_types_conf[provider]["product_types_config"]["sentinel-s2-l1c"][
                "title"
            ],
        )
        self.assertEqual(
            "proprietary",
            ext_product_types_conf[provider]["product_types_config"]["sentinel-s2-l1c"][
                "license"
            ],
        )
        # check that all pre-configured product types are listed by provider
        provider_product_types = [
            v["productType"]
            for k, v in self.eodag.providers_config[provider].products.items()
            if k != GENERIC_PRODUCT_TYPE
        ]
        for provider_product_type in provider_product_types:
            self.assertIn(
                provider_product_type,
                ext_product_types_conf[provider]["providers_config"],
            )

    def test_end_to_end_discover_product_types_earth_search_cog(self):
        """discover_product_types() must return None for earth_search_cog"""
        provider = "earth_search_cog"
        ext_product_types_conf = self.eodag.discover_product_types(provider=provider)
        self.assertIsNone(ext_product_types_conf[provider])

    def test_end_to_end_discover_product_types_earth_search_gcs(self):
        """discover_product_types() must return None for earth_search_gcs"""
        provider = "earth_search_gcs"
        ext_product_types_conf = self.eodag.discover_product_types(provider=provider)
        self.assertIsNone(ext_product_types_conf[provider])


# @unittest.skip("skip auto run")
class TestEODagEndToEndComplete(unittest.TestCase):
    """Make real and complete test cases that search for products, download them and
    extract them. There should be just a tiny number of these tests which can be quite
    long to run.

    There must be a user conf file in the test resources folder named user_conf.yml
    """

    @classmethod
    def setUpClass(cls):

        # use tests/resources/user_conf.yml if exists else default file ~/.config/eodag/eodag.yml
        tests_user_conf = os.path.join(TEST_RESOURCES_PATH, "user_conf.yml")
        if not os.path.isfile(tests_user_conf):
            unittest.SkipTest("Missing user conf file with credentials")
        cls.eodag = EODataAccessGateway(
            user_conf_file_path=os.path.join(TEST_RESOURCES_PATH, "user_conf.yml")
        )

        # temp download directory
        cls.tmp_download_dir = TemporaryDirectory()
        cls.tmp_download_path = cls.tmp_download_dir.name

        for provider, conf in cls.eodag.providers_config.items():
            # Change download directory to cls.tmp_download_path for tests
            if hasattr(conf, "download") and hasattr(conf.download, "outputs_prefix"):
                conf.download.outputs_prefix = cls.tmp_download_path
            elif hasattr(conf, "api") and hasattr(conf.api, "outputs_prefix"):
                conf.api.outputs_prefix = cls.tmp_download_path
            else:
                # no outputs_prefix found for provider
                pass
            # Force all providers implementing RestoSearch and defining how to retrieve
            # products by specifying the
            # location scheme to use https, enabling actual downloading of the product
            if (
                getattr(getattr(conf, "search", {}), "product_location_scheme", "https")
                == "file"
            ):
                conf.search.product_location_scheme = "https"

    @classmethod
    def tearDownClass(cls):
        cls.tmp_download_dir.cleanup()

    def test_end_to_end_complete_peps(self):
        """Complete end-to-end test with PEPS for download and download_all"""
        # Search for products that are ONLINE and as small as possible
        today = datetime.date.today()
        month_span = datetime.timedelta(weeks=4)
        self.eodag.set_preferred_provider("peps")
        search_results, _ = self.eodag.search(
            productType="S2_MSI_L1C",
            start=(today - month_span).isoformat(),
            end=today.isoformat(),
            geom={"lonmin": 1, "latmin": 42, "lonmax": 5, "latmax": 46},
            items_per_page=100,
        )
        prods_sorted_by_size = SearchResult(
            sorted(search_results, key=lambda p: p.properties["resourceSize"])
        )
        prods_online = [
            p for p in prods_sorted_by_size if p.properties["storageStatus"] == "ONLINE"
        ]
        if len(prods_online) < 2:
            unittest.skip(
                "Not enough ONLINE products found, update the search criteria."
            )

        # Retrieve one product to work with
        product = prods_online[0]

        prev_remote_location = product.remote_location
        prev_location = product.location
        # The expected product's archive filename is based on the product's title
        expected_product_name = f"{product.properties['title']}.zip"

        # Download the product, but DON'T extract it
        archive_file_path = self.eodag.download(product, extract=False)

        # The archive must have been downloaded
        self.assertTrue(os.path.isfile(archive_file_path))
        # Its name must be the "{product_title}.zip"
        self.assertIn(
            expected_product_name, os.listdir(product.downloader.config.outputs_prefix)
        )
        # Its size should be >= 5 KB
        archive_size = os.stat(archive_file_path).st_size
        self.assertGreaterEqual(archive_size, 5 * 2**10)
        # The product remote_location should be the same
        self.assertEqual(prev_remote_location, product.remote_location)
        # However its location should have been update
        self.assertNotEqual(prev_location, product.location)
        # The location must follow the file URI scheme
        self.assertTrue(product.location.startswith("file://"))
        # That points to the downloaded archive
        self.assertEqual(uri_to_path(product.location), archive_file_path)
        # A .downloaded folder must have been created
        record_dir = os.path.join(self.tmp_download_path, ".downloaded")
        self.assertTrue(os.path.isdir(record_dir))
        # It must contain a file per product downloade, whose name is
        # the MD5 hash of the product's remote location
        expected_hash = hashlib.md5(product.remote_location.encode("utf-8")).hexdigest()
        record_file = os.path.join(record_dir, expected_hash)
        self.assertTrue(os.path.isfile(record_file))
        # Its content must be the product's remote location
        record_content = Path(record_file).read_text()
        self.assertEqual(record_content, product.remote_location)

        # The downloaded product should not be downloaded again if the download
        # method is executed again
        previous_archive_file_path = archive_file_path
        previous_location = product.location
        start_time = time.time()
        archive_file_path = self.eodag.download(product, extract=False)
        end_time = time.time()
        self.assertLess(end_time - start_time, 2)  # Should be really fast (< 2s)
        # The paths should be the same as before
        self.assertEqual(archive_file_path, previous_archive_file_path)
        self.assertEqual(product.location, previous_location)

        # If we emulate that the product has just been found, it should not
        # be downloaded again since the record file is still present.
        product.location = product.remote_location
        # Pretty much the same checks as with the previous step
        previous_archive_file_path = archive_file_path
        start_time = time.time()
        archive_file_path = self.eodag.download(product, extract=False)
        end_time = time.time()
        self.assertLess(end_time - start_time, 2)  # Should be really fast (< 2s)
        # The returned path should be the same as before
        self.assertEqual(archive_file_path, previous_archive_file_path)
        self.assertEqual(uri_to_path(product.location), archive_file_path)

        # Remove the archive
        os.remove(archive_file_path)

        # Now, the archive is removed but its associated record file
        # still exists. Downloading the product again should really
        # download it, if its location points to the remote location.
        # The product should be automatically extracted.
        product.location = product.remote_location
        product_dir_path = self.eodag.download(
            product, extract=True, delete_archive=False
        )

        # Its size should be >= 5 KB
        downloaded_size = sum(
            f.stat().st_size for f in Path(product_dir_path).glob("**/*") if f.is_file()
        )
        self.assertGreaterEqual(downloaded_size, 5 * 2**10)
        # The product remote_location should be the same
        self.assertEqual(prev_remote_location, product.remote_location)
        # However its location should have been update
        self.assertNotEqual(prev_location, product.location)
        # The location must follow the file URI scheme
        self.assertTrue(product.location.startswith("file://"))
        # The location must point to a SAFE directory
        self.assertTrue(product.location.endswith("SAFE"))
        # The path must point to a SAFE directory
        self.assertTrue(os.path.isdir(product_dir_path))
        self.assertTrue(product_dir_path.endswith("SAFE"))

        # The downloaded & extracted product should not be downloaded again if
        # the download method is executed again
        previous_product_dir_path = product_dir_path
        start_time = time.time()
        product_dir_path = self.eodag.download(product)
        end_time = time.time()
        self.assertLess(end_time - start_time, 2)  # Should be really fast (< 2s)
        # The paths should be the same as before
        self.assertEqual(product_dir_path, previous_product_dir_path)

        # Remove the archive and extracted product and reset the product's location
        os.remove(archive_file_path)
        shutil.rmtree(Path(product_dir_path).parent)
        product.location = product.remote_location

        # Now let's check download_all
        products = prods_sorted_by_size[:2]
        # Pass a copy because download_all empties the list
        archive_paths = self.eodag.download_all(products[:], extract=False)

        # The returned paths must point to the downloaded archives
        # Each product's location must be a URI path to the archive
        for product, archive_path in zip(products, archive_paths):
            self.assertTrue(os.path.isfile(archive_path))
            self.assertEqual(uri_to_path(product.location), archive_path)

        # Downloading the product again should not download them, since
        # they are all already there.
        prev_archive_paths = archive_paths
        start_time = time.time()
        archive_paths = self.eodag.download_all(products[:], extract=False)
        end_time = time.time()
        self.assertLess(end_time - start_time, 2)  # Should be really fast (< 2s)
        self.assertEqual(archive_paths, prev_archive_paths)


# @unittest.skip("skip auto run")
class TestEODagEndToEndWrongCredentials(EndToEndBase):
    """Make real case tests with wrong credentials. This assumes the existence of a
    wrong_credentials_cong.yml file in resources folder named user_conf.yml"""

    @classmethod
    def setUpClass(cls):
        tests_wrong_conf = os.path.join(
            TEST_RESOURCES_PATH, "wrong_credentials_conf.yml"
        )
        cls.eodag = EODataAccessGateway(user_conf_file_path=tests_wrong_conf)
        # backup os.environ as it will be modified by tests
        cls.eodag_env_pattern = re.compile(r"EODAG_\w+")
        cls.eodag_env_backup = {
            k: v for k, v in os.environ.items() if cls.eodag_env_pattern.match(k)
        }

    @classmethod
    def tearDownClass(cls):
        super(TestEODagEndToEndWrongCredentials, cls).tearDownClass()
        # restore os.environ
        for k, v in os.environ.items():
            if cls.eodag_env_pattern.match(k):
                os.environ.pop(k)
        os.environ.update(cls.eodag_env_backup)

    def test_end_to_end_wrong_credentials_theia(self):
        product = self.execute_search(*THEIA_SEARCH_ARGS)
        with self.assertRaises(AuthenticationError):
            self.eodag.download(product)

    def test_end_to_end_wrong_credentials_peps(self):
        product = self.execute_search(*PEPS_SEARCH_ARGS)
        with self.assertRaises(AuthenticationError):
            self.eodag.download(product)

    def test_end_to_end_wrong_apikey_search_aws_eos(self):
        self.eodag.set_preferred_provider(AWSEOS_SEARCH_ARGS[0])
        with self.assertRaises(AuthenticationError):
            results, _ = self.eodag.search(
                raise_errors=True,
                **dict(
                    zip(["productType", "start", "end", "geom"], AWSEOS_SEARCH_ARGS[1:])
                ),
            )

    # @unittest.skip("expired aws_eos api key")
    def test_end_to_end_good_apikey_wrong_credentials_aws_eos(self):
        # Setup
        # We retrieve correct credentials from the user_conf.yml file
        tests_user_conf = os.path.join(TEST_RESOURCES_PATH, "user_conf.yml")
        if not os.path.isfile(tests_user_conf):
            self.skipTest("user_conf.yml file with credentials not found.")
        # But we set the access key id and the secret to wrong values
        try:
            os.environ[
                "EODAG__AWS_EOS__AUTH__CREDENTIALS__AWS_ACCESS_KEY_ID"
            ] = "badaccessid"
            os.environ[
                "EODAG__AWS_EOS__AUTH__CREDENTIALS__AWS_SECRET_ACCESS_KEY"
            ] = "badsecret"
            os.environ["EODAG__AWS_EOS__AUTH__CREDENTIALS__AWS_PROFILE"] = "badsecret"

            eodag = EODataAccessGateway(
                user_conf_file_path=os.path.join(TEST_RESOURCES_PATH, "user_conf.yml")
            )
            eodag.set_preferred_provider(AWSEOS_SEARCH_ARGS[0])
            results, nb_results = eodag.search(
                raise_errors=True,
                **dict(
                    zip(["productType", "start", "end", "geom"], AWSEOS_SEARCH_ARGS[1:])
                ),
            )
            self.assertGreater(len(results), 0)
            one_product = results[0]
            self.assertEqual(one_product.provider, AWSEOS_SEARCH_ARGS[0])
            with self.assertRaises(AuthenticationError):
                self.eodag.download(one_product)
        # Teardown
        finally:
            os.environ.pop("EODAG__AWS_EOS__AUTH__CREDENTIALS__AWS_ACCESS_KEY_ID")
            os.environ.pop("EODAG__AWS_EOS__AUTH__CREDENTIALS__AWS_SECRET_ACCESS_KEY")
            os.environ.pop("EODAG__AWS_EOS__AUTH__CREDENTIALS__AWS_PROFILE")

    def test_end_to_end_wrong_credentials_creodias(self):
        product = self.execute_search(*CREODIAS_SEARCH_ARGS)
        with self.assertRaises(AuthenticationError):
            self.eodag.download(product)

    def test_end_to_end_wrong_credentials_cop_dataspace(self):
        product = self.execute_search(*COP_DATASPACE_SEARCH_ARGS)
        with self.assertRaises(AuthenticationError):
            self.eodag.download(product)

    def test_end_to_end_wrong_credentials_mundi(self):
        product = self.execute_search(*MUNDI_SEARCH_ARGS)
        with self.assertRaises(AuthenticationError):
            self.eodag.download(product)

    def test_end_to_end_wrong_credentials_onda(self):
        product = self.execute_search(*ONDA_SEARCH_ARGS)
        with self.assertRaises(AuthenticationError):
            self.eodag.download(product)

    def test_end_to_end_wrong_credentials_search_usgs(self):
        # It should already fail while searching for the products.
        self.eodag.set_preferred_provider(USGS_RECENT_SEARCH_ARGS[0])
        with self.assertRaises(AuthenticationError):
            results, _ = self.eodag.search(
                raise_errors=True,
                **dict(
                    zip(
                        ["productType", "start", "end", "geom"],
                        USGS_RECENT_SEARCH_ARGS[1:],
                    )
                ),
            )
