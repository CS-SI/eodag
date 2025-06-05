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

import os


def is_env_var_true(var_name: str) -> bool:
    """
    Check if an environment variable is set to 'true' (case-insensitive).

    :param var_name: Name of the environment variable to check.
    :return: True if the environment variable is set to 'true', False otherwise.
    """
    return os.getenv(var_name, "").strip().lower() in ("1", "true", "yes", "on")
