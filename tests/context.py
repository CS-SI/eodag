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
"""Explicitly import here everything you want to use from the eodag package

isort:skip_file
"""

# ruff: noqa
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from eodag import EODataAccessGateway, api, config, setup_logging
from eodag.api.core import DEFAULT_ITEMS_PER_PAGE, DEFAULT_MAX_ITEMS_PER_PAGE
from eodag.api.product import EOProduct
from eodag.api.product.drivers import DRIVERS
from eodag.api.product.drivers.generic import GenericDriver
from eodag.api.product.drivers.sentinel1 import Sentinel1Driver
from eodag.api.product.drivers.sentinel2 import Sentinel2Driver
from eodag.api.product.drivers.base import DatasetDriver
from eodag.api.product.metadata_mapping import (
    format_metadata,
    OFFLINE_STATUS,
    ONLINE_STATUS,
    STAGING_STATUS,
    properties_from_json,
    NOT_AVAILABLE,
)
from eodag.api.collection import Collection, CollectionsDict, CollectionsList
from eodag.api.search_result import SearchResult
from eodag.cli import download, eodag, list_col, search_crunch
from eodag.config import (
    load_default_config,
    load_stac_provider_config,
    get_ext_collections_conf,
    EXT_COLLECTIONS_CONF_URI,
    PluginConfig,
    ProviderConfig,
)
from eodag.plugins.apis.ecmwf import EcmwfApi
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.authentication.aws_auth import AwsAuth
from eodag.plugins.authentication.header import HeaderAuth
from eodag.plugins.authentication.openid_connect import CodeAuthorizedAuth
from eodag.plugins.base import PluginTopic
from eodag.plugins.crunch.filter_date import FilterDate
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_property import FilterProperty
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.plugins.download.aws import AwsDownload
from eodag.plugins.download.base import (
    Download,
    DEFAULT_DOWNLOAD_WAIT,
)
from eodag.plugins.download.http import HTTPDownload
from eodag.plugins.manager import PluginManager
from eodag.plugins.search import PreparedSearch
from eodag.plugins.search.base import Search
from eodag.plugins.search.build_search_result import ecmwf_temporal_to_eodag
from eodag.plugins.search.qssearch import QueryStringSearch
from eodag.types import model_fields_to_annotated
from eodag.types.queryables import CommonQueryables, Queryables
from eodag.utils import (
    DEFAULT_MISSION_START_DATE,
    DEFAULT_SHAPELY_GEOMETRY,
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
    HTTP_REQ_TIMEOUT,
    DEFAULT_SEARCH_TIMEOUT,
    USER_AGENT,
    get_bucket_name_and_prefix,
    get_geometry_from_various,
    makedirs,
    merge_mappings,
    path_to_uri,
    ProgressCallback,
    DownloadedCallback,
    uri_to_path,
    urlsplit,
    GENERIC_COLLECTION,
    GENERIC_STAC_PROVIDER,
    flatten_top_directories,
    deepcopy,
    cached_parse,
    sanitize,
    parse_header,
    get_ssl_context,
    cached_yaml_load_all,
    StreamResponse,
)
from eodag.utils.dates import get_timestamp
from eodag.utils.env import is_env_var_true
from eodag.utils.requests import fetch_json
from eodag.utils.s3 import (
    list_files_in_s3_zipped_object,
    update_assets_from_s3,
    open_s3_zipped_object,
    S3FileInfo,
    file_position_from_s3_zip,
    _chunks_from_s3_objects,
    _prepare_file_in_zip,
    _compute_file_ranges,
    stream_download_from_s3,
)


from eodag.utils.exceptions import (
    AddressNotFound,
    AuthenticationError,
    DownloadError,
    MisconfiguredError,
    NoMatchingCollection,
    NotAvailableError,
    PluginImplementationError,
    RequestError,
    STACOpenerError,
    TimeOutError,
    UnsupportedDatasetAddressScheme,
    UnsupportedCollection,
    UnsupportedProvider,
    ValidationError,
    InvalidDataError,
)
from eodag.utils.stac_reader import fetch_stac_items, _TextOpener
from tests import TEST_RESOURCES_PATH
from usgs.api import USGSAuthExpiredError, USGSError
from usgs.api import TMPFILE as USGS_TMPFILE
