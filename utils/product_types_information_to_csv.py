# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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

import csv
import os
import re
from typing import Any

from eodag.api.core import EODataAccessGateway
from eodag.config import load_default_config

DEFAULT_PRODUCT_TYPES_CSV_FILE_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "../docs/_static/collections_information.csv",
)


def collections_info_to_csv(
    collections_csv_file_path: str = DEFAULT_PRODUCT_TYPES_CSV_FILE_PATH,
) -> None:
    """Get product types metadata and their availability for providers, and writes it to a csv file

    :param collections_csv_file_path: (optional) Path to product types information csv output file
    """
    config = {}
    for provider_config in load_default_config().values():
        config[provider_config.name] = list(provider_config.products.keys())

    # backup os.environ as it will be modified by the script
    eodag_env_pattern = re.compile(r"EODAG_\w+")
    eodag_env_backup = {
        k: v for k, v in os.environ.items() if eodag_env_pattern.match(k)
    }

    providers = sorted(load_default_config().keys())
    for provider in providers:
        os.environ[f"EODAG__{provider}__AUTH__CREDENTIALS__FOO"] = "bar"

    dag = EODataAccessGateway()

    # restore os.environ
    for k, _ in os.environ.items():
        if eodag_env_pattern.match(k):
            os.environ.pop(k)
    os.environ.update(eodag_env_backup)

    collections = dag.list_collections(fetch_providers=False)
    collections_names: list[str] = [collection["ID"] for collection in collections]
    metadata_params = list(k for k in collections[0].keys() if k != "ID")

    # csv fieldnames
    fieldnames = ["product type"] + metadata_params + providers

    # write to csv
    with open(collections_csv_file_path, "w") as collections_csvfile:
        collections_writer = csv.DictWriter(collections_csvfile, fieldnames=fieldnames)
        collections_writer.writeheader()

        # create product types table rows
        collections_rows: dict[str, Any] = {}
        for collection_name in collections_names:
            collections_rows[collection_name] = {"product type": collection_name}
            for metadata_param in metadata_params:
                metadata_string = [
                    collection[metadata_param]
                    for collection in collections
                    if collection["ID"] == collection_name
                ][0]
                if metadata_string is not None:
                    metadata_string = metadata_string.replace("\n", " ")
                collections_rows[collection_name][metadata_param] = metadata_string
            for provider in providers:
                if collection_name in config[provider]:
                    collections_rows[collection_name][provider] = "available"

            # write product types information
            collections_writer.writerow(
                {k: v for k, v in collections_rows[collection_name].items()}
            )


if __name__ == "__main__":
    collections_info_to_csv()
