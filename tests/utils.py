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
import os
from importlib.resources import files as res_files
from typing import Any, Literal, Optional

# All tests files should import mock from this place
from unittest import mock
from urllib.parse import parse_qs, urlparse

import fastapi
import yaml
from fastapi.datastructures import QueryParams  # noqa


def no_blanks(string):
    """Removes all the blanks in string

    :param string: A string to remove blanks from

    :returns the same string with all blank characters removed
    """
    return string.replace("\n", "").replace("\t", "").replace(" ", "")


def write_eodag_conf_with_fake_credentials(config_file):
    """Writes fake EODAG config file with fake credentials.
    Uses empty default conf with fake credentials. When loading
    this conf, eodag will not prune any provider that may need
    credentials for search.

    :param config_file: path to the file where the conf must be written
    """
    empty_conf_file_path = str(
        res_files("eodag") / "resources" / "user_conf_template.yml"
    )
    with open(os.path.abspath(os.path.realpath(empty_conf_file_path)), "r") as fh:
        was_empty_conf = yaml.safe_load(fh)
    for provider, conf in was_empty_conf.items():
        for auth_plugin_key in ("auth", "api"):
            if "credentials" in conf.get(auth_plugin_key, {}):
                cred_key = next(iter(conf[auth_plugin_key]["credentials"]))
                conf[auth_plugin_key]["credentials"][cred_key] = "foo"
    with open(config_file, mode="w") as fh:
        yaml.dump(was_empty_conf, fh, default_flow_style=False)


def mock_request(
    url: str,
    body: Optional[dict[str, Any]] = None,
    method: Optional[Literal["GET", "POST"]] = "GET",
) -> mock.Mock:
    parsed_url = urlparse(url)
    url_without_qs = parsed_url.scheme + "://" + parsed_url.netloc + parsed_url.path
    url_root = parsed_url.scheme + "://" + parsed_url.netloc
    query_dict = parse_qs(parsed_url.query)
    query_params = {k: ",".join(v) for k, v in query_dict.items()}

    mocked_request = mock.Mock(spec=fastapi.Request)
    mocked_request.state.url_root = url_root
    mocked_request.state.url = url_without_qs
    mocked_request.url = url
    mocked_request.method = method
    mocked_request.query_params = QueryParams(query_params)
    mocked_request.json.return_value = body
    return mocked_request
