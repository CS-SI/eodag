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
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from eodag import EODataAccessGateway, api, config, setup_logging
from eodag.api.core import DEFAULT_ITEMS_PER_PAGE, DEFAULT_MAX_ITEMS_PER_PAGE
from eodag.api.product import EOProduct
from eodag.api.product.drivers import DRIVERS
from eodag.api.product.drivers.base import DatasetDriver
from eodag.api.product.metadata_mapping import (
    format_metadata,
    OFFLINE_STATUS,
    ONLINE_STATUS,
    properties_from_json,
    NOT_AVAILABLE,
)
from eodag.api.search_result import SearchResult
from eodag.cli import download, eodag, list_pt, search_crunch
from eodag.config import (
    load_default_config,
    merge_configs,
    load_stac_provider_config,
    get_ext_product_types_conf,
    EXT_PRODUCT_TYPES_CONF_URI,
    PluginConfig,
    ProviderConfig,
)
from eodag.plugins.apis.ecmwf import EcmwfApi
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.authentication.header import HeaderAuth
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
from eodag.plugins.search.base import Search
from eodag.rest.stac import DEFAULT_MISSION_START_DATE
from eodag.utils import (
    DEFAULT_STREAM_REQUESTS_TIMEOUT,
    HTTP_REQ_TIMEOUT,
    USER_AGENT,
    get_bucket_name_and_prefix,
    get_geometry_from_various,
    get_timestamp,
    makedirs,
    merge_mappings,
    path_to_uri,
    ProgressCallback,
    uri_to_path,
    DownloadedCallback,
    parse_qsl,
    urlsplit,
    GENERIC_PRODUCT_TYPE,
    flatten_top_directories,
    deepcopy,
    cached_parse,
    sanitize,
    parse_header,
)
from eodag.utils.exceptions import (
    AddressNotFound,
    AuthenticationError,
    DownloadError,
    MisconfiguredError,
    NoMatchingProductType,
    NotAvailableError,
    PluginImplementationError,
    RequestError,
    UnsupportedDatasetAddressScheme,
    UnsupportedProvider,
    ValidationError,
    STACOpenerError,
)
from eodag.utils.stac_reader import fetch_stac_items, _TextOpener
from tests import TEST_RESOURCES_PATH
from usgs.api import USGSAuthExpiredError, USGSError
