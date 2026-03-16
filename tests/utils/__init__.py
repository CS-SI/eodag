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
from .consts import SUPPORTED_COLLECTIONS, SUPPORTED_PROVIDERS
from .eodagtestbase import RESOURCES_PATH, TEST_RESOURCES_PATH, EODagTestBase
from .eodagtestcase import EODagTestCase
from .utils import (
    no_blanks,
    temporary_environment,
    write_eodag_conf_with_fake_credentials,
)

__all__ = [
    "EODagTestBase",
    "TEST_RESOURCES_PATH",
    "RESOURCES_PATH",
    "EODagTestCase",
    "no_blanks",
    "write_eodag_conf_with_fake_credentials",
    "temporary_environment",
    "SUPPORTED_PROVIDERS",
    "SUPPORTED_COLLECTIONS",
]
