# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, https://www.csgroup.eu/
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
import io
import logging
import os
import sys
import traceback
from distutils import dist
from functools import wraps

import flask
import geojson
import pkg_resources
from flasgger import Swagger
from flask import abort, jsonify, make_response, request, send_file

from eodag.config import load_stac_api_config
from eodag.rest.utils import (  # get_stac_landing_page,; get_stac_product_types_catalog,; search_products,
    download_stac_item_by_id,
    get_detailled_collections_list,
    get_stac_catalogs,
    get_stac_collection_by_id,
    get_stac_collections,
    get_stac_conformance,
    get_stac_extension_oseo,
    get_stac_item_by_id,
    load_stac_config,
    search_stac_items,
)
from eodag.utils.exceptions import (
    MisconfiguredError,
    NoMatchingProductType,
    NotAvailableError,
    UnsupportedProductType,
    UnsupportedProvider,
    ValidationError,
)

logger = logging.getLogger("eodag.rest.server")

app = flask.Flask(__name__)

# eodag metadata
distribution = pkg_resources.get_distribution("eodag")
metadata_str = distribution.get_metadata(distribution.PKG_INFO)
metadata_obj = dist.DistributionMetadata()
metadata_obj.read_pkg_file(io.StringIO(metadata_str))

# confs from resources yaml files
stac_config = load_stac_config()

stac_api_config = {"info": {}}
stac_api_config = load_stac_api_config()
root_catalog = get_stac_catalogs(url="")
stac_api_version = stac_api_config["info"]["version"]
stac_api_config["info"]["title"] = root_catalog["title"] + " / eodag"
stac_api_config["info"]["description"] = (
    root_catalog["description"]
    + " (stac-api-spec {})".format(stac_api_version)
    + "".join(
        [
            "\n - [{0}](/collections/{0}): {1}".format(pt["ID"], pt["abstract"])
            for pt in get_detailled_collections_list()
        ]
    )
)
stac_api_config["info"]["version"] = getattr(
    metadata_obj, "version", stac_api_config["info"]["version"]
)
stac_api_config["info"]["contact"]["name"] = "EODAG"
stac_api_config["info"]["contact"]["url"] = getattr(
    metadata_obj, "url", stac_api_config["info"]["contact"]["url"]
)
stac_api_config["title"] = root_catalog["title"] + " - service-doc"
stac_api_config["specs"] = [
    {
        "endpoint": "service-desc",
        "route": "/api",
        "rule_filter": lambda rule: True,  # all in
        "model_filter": lambda tag: True,  # all in
    }
]
stac_api_config["static_url_path"] = "/service-static"
stac_api_config["specs_route"] = "/service-doc/"
stac_api_config.pop("servers", None)
swagger = Swagger(app, config=stac_api_config, merge=True)


def cross_origin(request_handler):
    """Wraps a view to relax the need for csrf token"""

    @wraps(request_handler)
    def wrapper(*args, **kwargs):
        resp = make_response(request_handler(*args, **kwargs))
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    return wrapper


@app.errorhandler(MisconfiguredError)
@app.errorhandler(NoMatchingProductType)
@app.errorhandler(UnsupportedProductType)
@app.errorhandler(UnsupportedProvider)
@app.errorhandler(ValidationError)
def handle_invalid_usage(error):
    """Invalid usage [400] errors handle"""
    status_code = 400
    response = jsonify(
        {"code": status_code, "name": type(error).__name__, "description": str(error)}
    )
    response.status_code = status_code
    logger.warning(traceback.format_exc())
    return response


@app.errorhandler(RuntimeError)
@app.errorhandler(Exception)
def handle_internal_error(error):
    """Internal [500] errors handle"""
    status_code = 500
    response = jsonify(
        {"code": status_code, "name": type(error).__name__, "description": str(error)}
    )
    response.status_code = status_code
    logger.error(traceback.format_exc())
    return response


@app.errorhandler(NotAvailableError)
@app.errorhandler(404)
def handle_resource_not_found(e):
    """Not found [404] errors handle"""
    return jsonify(error=str(e)), 404


@app.route("/conformance", methods=["GET"])
@cross_origin
def conformance():
    """STAC conformance"""

    response = get_stac_conformance()

    return jsonify(response), 200


@app.route("/", methods=["GET"])
@cross_origin
def catalogs_root():
    """STAC catalogs root"""

    response = get_stac_catalogs(
        url=request.url.split("?")[0],
        root=request.url_root,
        catalogs=[],
        provider=request.args.to_dict().get("provider", None),
    )

    return jsonify(response), 200


@app.route("/<path:catalogs>", methods=["GET"])
@cross_origin
def stac_catalogs(catalogs):
    """Describe the given catalog and list available sub-catalogs
    ---
    tags:
      - Capabilities
    parameters:
      - name: catalogs
        in: path
        required: true
        description: |-
            The catalog's path.

            For a nested catalog, provide the root-related path to the catalog (for example `S2_MSI_L1C/year/2020`)
        schema:
            type: string
    responses:
        200:
            description: The catalog's description
            content:
                application/json:
                    schema:
                        $ref: '#/components/schemas/collection'
        '500':
            $ref: '#/components/responses/ServerError'
    """

    catalogs = catalogs.strip("/").split("/")
    response = get_stac_catalogs(
        url=request.url.split("?")[0],
        root=request.url_root,
        catalogs=catalogs,
        provider=request.args.to_dict().get("provider", None),
    )
    return jsonify(response), 200


@app.route("/<path:catalogs>/items", methods=["GET"])
@cross_origin
def stac_catalogs_items(catalogs):
    """Fetch catalog's features
    ---
    tags:
      - Data
    description: |-
        Fetch features in the given catalog provided with `catalogs`.
    parameters:
      - name: catalogs
        in: path
        required: true
        description: |-
            The path to the catalog that contains the requested features.

            For a nested catalog, provide the root-related path to the catalog (for example `S2_MSI_L1C/year/2020`)
        schema:
            type: string
      - $ref: '#/components/parameters/bbox'
      - $ref: '#/components/parameters/datetime'
      - $ref: '#/components/parameters/limit'
    responses:
        200:
            description: The list of items found for the given catalog.
            type: array
            content:
                application/json:
                    schema:
                        $ref: '#/components/schemas/itemCollection'
        '500':
            $ref: '#/components/responses/ServerError
    '"""

    catalogs = catalogs.strip("/").split("/")
    arguments = request.args.to_dict()
    provider = arguments.pop("provider", None)
    response = search_stac_items(
        url=request.url,
        arguments=arguments,
        root=request.url_root,
        catalogs=catalogs,
        provider=provider,
    )
    return app.response_class(
        response=geojson.dumps(response), status=200, mimetype="application/json"
    )


@app.route("/<path:catalogs>/items/<item_id>", methods=["GET"])
@cross_origin
def stac_catalogs_item(catalogs, item_id):
    """Fetch catalog's single features
    ---
    tags:
      - Data
    description: |-
        Fetch the feature with id `featureId` in the given catalog provided.
        with `catalogs`.
    parameters:
        - name: catalogs
          in: path
          required: true
          description: |-
                The path to the catalog that contains the requested feature.


                For a nested catalog, provide the root-related path to the catalog (for example `S2_MSI_L1C/year/2020`)
          schema:
                type: string
        - name: item_id
          in: path
          description: |-
            local identifier of a feature (for example `S2A_MSIL1C_20200805T104031_N0209_R008_T31TCJ_20200805T110310`)
          required: true
          schema:
              type: string
    responses:
        '200':
          $ref: '#/components/responses/Feature'
        '404':
          $ref: '#/components/responses/NotFound'
        '500':
          $ref: '#/components/responses/ServerError'
    """

    catalogs = catalogs.strip("/").split("/")
    response = get_stac_item_by_id(
        url=request.url.split("?")[0],
        item_id=item_id,
        root=request.url_root,
        catalogs=catalogs,
        provider=request.args.to_dict().get("provider", None),
    )

    if response:
        return app.response_class(
            response=geojson.dumps(response), status=200, mimetype="application/json"
        )
    else:
        abort(
            404,
            "No item found matching `{}` id in catalog `{}`".format(item_id, catalogs),
        )


@app.route("/<path:catalogs>/items/<item_id>/download", methods=["GET"])
@cross_origin
def stac_catalogs_item_download(catalogs, item_id):
    """STAC item local download"""

    catalogs = catalogs.strip("/").split("/")
    response = download_stac_item_by_id(
        catalogs=catalogs,
        item_id=item_id,
        provider=request.args.to_dict().get("provider", None),
    )
    filename = os.path.basename(response)

    return send_file(response, as_attachment=True, attachment_filename=filename)


@app.route("/collections/", methods=["GET"])
@app.route("/collections", methods=["GET"])
@cross_origin
def collections():
    """STAC collections

    Can be filtered using parameters: instrument, platform, platformSerialIdentifier, sensorType, processingLevel
    """
    arguments = request.args.to_dict()
    provider = arguments.pop("provider", None)
    response = get_stac_collections(
        url=request.url.split("?")[0],
        root=request.url_root,
        arguments=arguments,
        provider=provider,
    )

    return jsonify(response), 200


@app.route("/collections/<collection_id>", methods=["GET"])
@cross_origin
def collection_by_id(collection_id):
    """STAC collection by id"""

    response = get_stac_collection_by_id(
        url=request.url.split("?")[0],
        root=request.url_root,
        collection_id=collection_id,
        provider=request.args.to_dict().get("provider", None),
    )

    return jsonify(response), 200


@app.route("/collections/<collection_id>/items", methods=["GET"])
@cross_origin
def stac_collections_items(collection_id):
    """STAC collections items"""

    arguments = request.args.to_dict()
    provider = arguments.pop("provider", None)
    response = search_stac_items(
        url=request.url,
        arguments=arguments,
        root=request.url_root,
        provider=provider,
        catalogs=[collection_id],
    )
    return app.response_class(
        response=geojson.dumps(response), status=200, mimetype="application/json"
    )


@app.route("/search", methods=["GET", "POST"])
@cross_origin
def stac_search():
    """STAC collections items"""

    if request.get_json():
        arguments = dict(request.args.to_dict(), **request.get_json())
    else:
        arguments = request.args.to_dict()

    provider = arguments.pop("provider", None)
    response = search_stac_items(
        url=request.url, arguments=arguments, root=request.url_root, provider=provider
    )
    return app.response_class(
        response=geojson.dumps(response), status=200, mimetype="application/json"
    )


@app.route("/extensions/oseo/json-schema/schema.json", methods=["GET"])
@cross_origin
def stac_extension_oseo():
    """STAC OGC / OpenSearch extension for EO"""

    response = get_stac_extension_oseo(url=request.url.split("?")[0])

    return app.response_class(
        response=geojson.dumps(response), status=200, mimetype="application/json"
    )


@app.route("/collections/<collection_id>/items/<item_id>", methods=["GET"])
@cross_origin
def stac_collections_item(collection_id, item_id):
    """STAC collection item by id"""

    response = get_stac_item_by_id(
        url=request.url.split("?")[0],
        item_id=item_id,
        root=request.url_root,
        catalogs=[collection_id],
        provider=request.args.to_dict().get("provider", None),
    )

    return app.response_class(
        response=geojson.dumps(response), status=200, mimetype="application/json"
    )


@app.route("/collections/<collection_id>/items/<item_id>/download", methods=["GET"])
@cross_origin
def stac_collections_item_download(collection_id, item_id):
    """STAC collection item local download"""

    response = download_stac_item_by_id(
        catalogs=[collection_id],
        item_id=item_id,
        provider=request.args.to_dict().get("provider", None),
    )
    filename = os.path.basename(response)

    return send_file(response, as_attachment=True, attachment_filename=filename)


def main():
    """Launch the server"""
    import argparse

    parser = argparse.ArgumentParser(
        description="""Script for starting EODAG server""", epilog=""""""
    )
    parser.add_argument(
        "-d", "--daemon", action="store_true", help="run in daemon mode"
    )
    parser.add_argument(
        "-a",
        "--all-addresses",
        action="store_true",
        help="run flask using IPv4 0.0.0.0 (all network interfaces), "
        "otherwise bind to 127.0.0.1 (localhost). "
        "This maybe necessary in systems that only run Flask",
    )
    args = parser.parse_args()

    if args.all_addresses:
        bind_host = "0.0.0.0"
    else:
        bind_host = "127.0.0.1"

    if args.daemon:
        pid = None
        try:
            pid = os.fork()
        except OSError as e:
            raise Exception("%s [%d]" % (e.strerror, e.errno))

        if pid == 0:
            os.setsid()
            app.run(threaded=True, host=bind_host)
        else:
            sys.exit(0)
    else:
        # For development
        app.run(debug=True, use_reloader=True)


if __name__ == "__main__":
    main()
