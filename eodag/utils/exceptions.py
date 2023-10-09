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


class EODAGError(Exception):
    """EODAG general exception"""


class ValidationError(EODAGError):
    """Error validating data"""


class PluginNotFoundError(EODAGError):
    """Error when looking for a plugin class that was not defined"""


class PluginImplementationError(EODAGError):
    """Error when a plugin does not behave as expected"""


class MisconfiguredError(EODAGError):
    """An error indicating a Search Plugin that is not well configured"""


class AddressNotFound(EODAGError):
    """An error indicating the address of a subdataset was not found"""


class UnsupportedProvider(EODAGError):
    """An error indicating that eodag does not support a provider"""


class UnsupportedProductType(EODAGError):
    """An error indicating that eodag does not support a product type"""

    def __init__(self, product_type):
        self.product_type = product_type


class UnsupportedDatasetAddressScheme(EODAGError):
    """An error indicating that eodag does not yet support an address scheme for
    accessing raster subdatasets"""


class AuthenticationError(EODAGError):
    """An error indicating that an authentication plugin did not succeeded
    authenticating a user"""


class DownloadError(EODAGError):
    """An error indicating something wrong with the download process"""


class NotAvailableError(EODAGError):
    """An error indicating that the product is not available for download"""


class RequestError(EODAGError):
    """An error indicating that a HTTP request has failed. Usually eodag functions
    and methods should catch and skip this"""


class NoMatchingProductType(EODAGError):
    """An error indicating that eodag was unable to derive a product type from a set
    of search parameters"""


class STACOpenerError(EODAGError):
    """An error indicating that a STAC file could not be opened"""
