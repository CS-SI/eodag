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
import csv
import json
import logging
import os

import requests
from lxml import html

from eodag.api.core import EODataAccessGateway
from eodag.config import load_stac_provider_config
from eodag.utils import HTTP_REQ_TIMEOUT

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

OPENSEARCH_DOC_URL = "http://docs.opengeospatial.org/is/13-026r9/13-026r9.html"
DEFAULT_OPENSEARCH_CSV_FILE_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "../docs/_static/params_mapping_opensearch.csv",
)
DEFAULT_EXTRA_CSV_FILE_PATH = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "../docs/_static/params_mapping_extra.csv",
)
OFFLINE_OPENSEARCH_JSON = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "../docs/_static/params_mapping_offline_infos.json",
)


def params_mapping_to_csv(
    ogc_doc_url=OPENSEARCH_DOC_URL,
    opensearch_csv_file_path=DEFAULT_OPENSEARCH_CSV_FILE_PATH,
    extra_csv_file_path=DEFAULT_EXTRA_CSV_FILE_PATH,
):
    """Get providers metadata mapping, with corresponding description from OGC
    documentation and writes it to csv files (for opensearch and extra params)

    :param ogc_doc_url: (optional) URL to OGC OpenSearch documentation
    :type ogc_doc_url: str
    :param opensearch_csv_file_path: (optional) Path to opensearch params csv output file
    :type opensearch_csv_file_path: str
    :param extra_csv_file_path: (optional) Path to extra params csv output file
    :type extra_csv_file_path: str
    """
    dag = EODataAccessGateway()

    # update stac providers metadata_mapping
    stac_mapping = load_stac_provider_config()["search"]["metadata_mapping"]
    for p in dag.providers_config.keys():
        if (
            hasattr(dag.providers_config[p], "search")
            and getattr(dag.providers_config[p].search, "type", None) == "StacSearch"
        ):
            dag.providers_config[p].search.metadata_mapping = dict(
                stac_mapping,
                **dag.providers_config[p].search.__dict__.get("metadata_mapping", {}),
            )

    # list of lists of all parameters per provider
    params_list_of_lists = []
    for p in dag.providers_config.keys():
        if hasattr(dag.providers_config[p], "search") and hasattr(
            dag.providers_config[p].search, "metadata_mapping"
        ):
            params_list_of_lists.append(
                list(dag.providers_config[p].search.__dict__["metadata_mapping"].keys())
            )

    # union of params_list_of_lists
    global_keys = sorted(list(set().union(*(params_list_of_lists))))

    # csv fieldnames
    fieldnames = ["parameter"] + sorted(dag.providers_config.keys())

    logging_additional_infos = ""

    # write to csv
    with open(opensearch_csv_file_path, "w") as opensearch_csvfile:
        opensearch_writer = csv.DictWriter(opensearch_csvfile, fieldnames=fieldnames)
        opensearch_writer.writeheader()

        with open(extra_csv_file_path, "w") as extra_csvfile:
            extra_writer = csv.DictWriter(extra_csvfile, fieldnames=fieldnames)
            extra_writer.writeheader()

            # create metadata mapping table rows
            try:
                page = requests.get(ogc_doc_url, timeout=HTTP_REQ_TIMEOUT)
                # page reachable, read infos from remote html
                tree = html.fromstring(page.content.decode("utf8"))

                params_rows = {}

                for param in global_keys:
                    params_rows[param] = {
                        "parameter": param,
                        "open-search": "",
                        "class": "",
                        "description": "",
                        "type": "",
                    }
                    # search html node matching containing param
                    param_node_list = tree.xpath(
                        '/html/body/main/section/table/tr/td[1]/p[text()="%s"]' % param
                    )

                    for param_node in param_node_list:
                        params_rows[param]["open-search"] = True

                        # table must have 3 columns, and 'Definition' as 2nd header
                        if (
                            len(param_node.xpath("../../../thead/tr/th")) == 3
                            and "Definition"
                            in param_node.xpath("../../../thead/tr/th[2]/text()")[0]
                        ):

                            params_rows[param]["class"] = param_node.xpath(
                                "../../../caption/text()"
                            )[1].strip(": ")

                            # description formatting
                            params_rows[param]["description"] = param_node.xpath(
                                "../../td[2]/p/text()"
                            )[0].replace("\n", " ")
                            # multiple spaces to 1
                            params_rows[param]["description"] = " ".join(
                                params_rows[param]["description"].split()
                            )

                            params_rows[param]["type"] = param_node.xpath(
                                "../../td[3]/p/text()"
                            )[0]
                            break
                # save infos for offline mode
                with open(OFFLINE_OPENSEARCH_JSON, "w+") as f:
                    json.dump(params_rows, f)
                    f.write("\n")

            except requests.RequestException:
                # page unreachable, read infos from previously saved json
                with open(OFFLINE_OPENSEARCH_JSON, "r") as f:
                    params_rows = json.load(f)

                logging_additional_infos = "(OFFLINE mode)"

            # write metadata mapping
            for param in global_keys:
                for provider in dag.providers_config.keys():
                    if hasattr(dag.providers_config[provider], "search") and hasattr(
                        dag.providers_config[provider].search, "metadata_mapping"
                    ):
                        mapping_dict = dag.providers_config[provider].search.__dict__[
                            "metadata_mapping"
                        ]
                        if param in mapping_dict.keys():
                            if isinstance(mapping_dict[param], list):
                                params_rows[param][
                                    provider
                                ] = ":green:`queryable metadata`"
                            else:
                                params_rows[param][provider] = "metadata only"

                # write opensearch parameters mapping
                if params_rows[param]["open-search"] is True:
                    # format parameter name with tooltip if available
                    if params_rows[param]["description"]:
                        params_rows[param][
                            "parameter"
                        ] = ":abbr:`%s ([%s] %s (%s))`" % (
                            params_rows[param]["parameter"],
                            params_rows[param]["class"],
                            params_rows[param]["description"],
                            params_rows[param]["type"],
                        )
                    opensearch_writer.writerow(
                        {k: v for k, v in params_rows[param].items() if k in fieldnames}
                    )
                # write extra parameters mapping
                else:
                    extra_writer.writerow(
                        {k: v for k, v in params_rows[param].items() if k in fieldnames}
                    )

    logger.info(f"{opensearch_csv_file_path} written {logging_additional_infos}")
    logger.info(f"{extra_csv_file_path} written {logging_additional_infos}")


if __name__ == "__main__":
    params_mapping_to_csv()
