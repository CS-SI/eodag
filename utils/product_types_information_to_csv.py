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
import csv
import os
import re
from typing import Any, Dict, List

from eodag.api.core import EODataAccessGateway
from eodag.config import load_default_config

DEFAULT_PRODUCT_TYPES_CSV_FILE_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "../docs/_static/product_types_information.csv",
)


def product_types_info_to_csv(
    product_types_csv_file_path: str = DEFAULT_PRODUCT_TYPES_CSV_FILE_PATH,
) -> None:
    """Get product types metadata and their availability for providers, and writes it to a csv file

    :param product_types_csv_file_path: (optional) Path to product types information csv output file
    :type product_types_csv_file_path: str
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

    product_types = dag.list_product_types(fetch_providers=False)
    product_types_names: List[str] = [product_type["ID"] for product_type in product_types]
    metadata_params = list(k for k in product_types[0].keys() if k != "ID")

    # csv fieldnames
    fieldnames = ["product type"] + metadata_params + providers

    # write to csv
    with open(product_types_csv_file_path, "w") as product_types_csvfile:
        product_types_writer = csv.DictWriter(
            product_types_csvfile, fieldnames=fieldnames
        )
        product_types_writer.writeheader()

        # create product types table rows
        product_types_rows: Dict[str, Any] = {}
        for product_type_name in product_types_names:
            product_types_rows[product_type_name] = {"product type": product_type_name}
            for metadata_param in metadata_params:
                metadata_string = [
                    product_type[metadata_param]
                    for product_type in product_types
                    if product_type["ID"] == product_type_name
                ][0]
                if metadata_string is not None:
                    metadata_string = metadata_string.replace("\n", " ")
                product_types_rows[product_type_name][metadata_param] = metadata_string
            for provider in providers:
                if product_type_name in config[provider]:
                    product_types_rows[product_type_name][provider] = "available"

            # write product types information
            product_types_writer.writerow(
                {k: v for k, v in product_types_rows[product_type_name].items()}
            )


if __name__ == "__main__":
    product_types_info_to_csv()
