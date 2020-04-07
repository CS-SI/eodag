#!/usr/bin/env python

# -*- coding: utf-8 -*-
# Copyright 2017-2018 CS GROUP - France (CS SI)
# All rights reserved

from __future__ import absolute_import, unicode_literals

import logging
import os
import sys
import traceback
from functools import wraps

import flask
import geojson
import requests
from flask import jsonify, make_response, render_template, request, send_file

from eodag.api.core import DEFAULT_ITEMS_PER_PAGE
from eodag.utils import makedirs
from eodag.utils.exceptions import (
    MisconfiguredError,
    NoMatchingProductType,
    UnsupportedProductType,
    UnsupportedProvider,
    ValidationError,
)

from eodag.rest.utils import (  # get_stac_landing_page,; get_stac_product_types_catalog,; search_products,
    download_stac_item_by_id,
    get_home_page_content,
    get_product_types,
    get_stac_catalogs,
    get_stac_collection_by_id,
    get_stac_collections,
    get_stac_conformance,
    get_stac_extension_oseo,
    get_stac_item_by_id,
    load_stac_config,
    search_product_by_id,
    search_stac_items,
)

logger = logging.getLogger("eodag.rest.server")

app = flask.Flask(__name__)

stac_config = load_stac_config()


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

    response = get_stac_catalogs(url=request.url, root=request.url_root, catalogs=[])

    return jsonify(response), 200


@app.route("/<path:catalogs>", methods=["GET"])
@cross_origin
def stac_catalogs(catalogs):
    """STAC catalogs"""

    catalogs = catalogs.strip("/").split("/")
    response = get_stac_catalogs(
        url=request.url, root=request.url_root, catalogs=catalogs
    )
    return jsonify(response), 200


@app.route("/<path:catalogs>/items", methods=["GET"])
@cross_origin
def stac_catalogs_items(catalogs):
    """STAC catalogs items"""

    catalogs = catalogs.strip("/").split("/")
    response = search_stac_items(
        url=request.url.split("?")[0],
        arguments=request.args.to_dict(),
        root=request.url_root,
        catalogs=catalogs,
    )
    return app.response_class(
        response=geojson.dumps(response), status=200, mimetype="application/json"
    )


@app.route("/<path:catalogs>/items/<item_id>", methods=["GET"])
@cross_origin
def stac_catalogs_item(catalogs, item_id):
    """STAC item by id"""

    catalogs = catalogs.strip("/").split("/")
    response = get_stac_item_by_id(
        url=request.url, item_id=item_id, root=request.url_root, catalogs=catalogs
    )

    return app.response_class(
        response=geojson.dumps(response), status=200, mimetype="application/json"
    )


@app.route("/<path:catalogs>/items/<item_id>/download", methods=["GET"])
@cross_origin
def stac_catalogs_item_download(catalogs, item_id):
    """STAC item local download"""

    catalogs = catalogs.strip("/").split("/")
    response = download_stac_item_by_id(catalogs=catalogs, item_id=item_id)
    filename = os.path.basename(response)

    return send_file(response, as_attachment=True, attachment_filename=filename)


@app.route("/collections", methods=["GET"])
@cross_origin
def collections():
    """STAC collections"""

    response = get_stac_collections(url=request.url, root=request.url_root)

    return jsonify(response), 200


@app.route("/collections/<collection_id>", methods=["GET"])
@cross_origin
def collection_by_id(collection_id):
    """STAC collection by id"""

    response = get_stac_collection_by_id(
        url=request.url, root=request.url_root, collection_id=collection_id
    )

    return jsonify(response), 200


@app.route("/collections/<collection_id>/items", methods=["GET"])
@cross_origin
def stac_collections_items(collection_id):
    """STAC collections items"""

    response = search_stac_items(
        url=request.url.split("?")[0],
        arguments=request.args.to_dict(),
        root=request.url_root,
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

    response = search_stac_items(
        url=request.url, arguments=arguments, root=request.url_root
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
        url=request.url,
        item_id=item_id,
        root=request.url_root,
        catalogs=[collection_id],
    )

    return app.response_class(
        response=geojson.dumps(response), status=200, mimetype="application/json"
    )


@app.route("/collections/<collection_id>/items/<item_id>/download", methods=["GET"])
@cross_origin
def stac_collections_item_download(collection_id, item_id):
    """STAC collection item local download"""

    response = download_stac_item_by_id(catalogs=[collection_id], item_id=item_id)
    filename = os.path.basename(response)

    return send_file(response, as_attachment=True, attachment_filename=filename)


# @app.route("/<product_type>/", methods=["GET"])
# @cross_origin
# def search(product_type):
#     """Search for a product by product type on eodag"""
#     try:
#         response = search_products(product_type, request.args)
#     except ValidationError as e:
#         return jsonify({"error": e.message}), 400
#     except RuntimeError as e:
#         return jsonify({"error": e}), 400
#     except UnsupportedProductType as e:
#         return jsonify({"error": "Not Found: {}".format(e.product_type)}), 404

#     return jsonify(response), 200


# @app.route("/search/<uid>/", methods=["GET"])
# @cross_origin
# def search_by_id(uid):
#     """Retrieve the quicklook of a eo product identified by its id"""
#     provider = request.args.get("provider")
#     try:
#         search_result = search_product_by_id(uid, provider=provider)
#     except ValidationError as e:
#         return jsonify({"error": e.message}), 400
#     except RuntimeError as e:
#         return jsonify({"error": e}), 500
#     except UnsupportedProvider:
#         return jsonify({"error": "Unknown provider: %s" % (provider,)}), 400

#     if len(search_result) == 0:
#         return jsonify({"error": "Not found"}), 404
#     return jsonify(search_result[0].as_dict()), 200


@app.route("/quicklook/<uid>/", methods=["GET"])
@cross_origin
def get_quicklook(uid=None):
    """Retrieve the quicklook of a eo product identified by its id"""
    if uid is None:
        return jsonify({"error": "You must provide a EO product uid"}), 400
    provider = request.args.get("provider")
    try:
        search_result = search_product_by_id(uid, provider=provider)
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except RuntimeError as e:
        return jsonify({"error": e}), 500
    except UnsupportedProvider:
        return jsonify({"error": "Unknown provider: %s" % (provider,)}), 400

    if len(search_result) == 0:
        return jsonify({"error": "EO product not found"}), 400

    eo_product = search_result[0]
    quicklook = eo_product.properties.get("quicklook", None)
    if quicklook is None:
        return jsonify({"error": "Not Found"}), 404
    quicklook_alt_text = "{} quicklook".format(uid)
    if quicklook.startswith("http") or quicklook.startswith("https"):
        # First see if the url of the quicklook is accessible as is
        resp = requests.get(quicklook)
        try:
            resp.raise_for_status()
            quicklook_src = quicklook
        except requests.HTTPError:
            # Flask is known to automatically serve files present in a folder named
            # "static" in the root folder of the application.
            # If the url is not accessible as is, try to get it from the provider using
            # its authentication mechanism
            quicklooks_dir = os.path.join(
                os.path.dirname(__file__), "static", "quicklooks"
            )
            # First create the static folder and quicklooks dir inside it if necessary
            makedirs(quicklooks_dir)
            # Then download the quicklook
            response = eo_product.get_quicklook(filename=uid, base_dir=quicklooks_dir)
            # get_quicklook should always return an absolute path, which starts with "/"
            # If it fails to do so, we consider an error occured while getting the
            # quicklook
            if not response.startswith("/"):
                return jsonify({"error": response}), 500
            quicklook_src = "/static/quicklooks/{}".format(uid)
    # If the quicklook is not an HTTP URL, we guess it is a base64 stream. In that case
    # we directly include it in the <img> tag and return it as is
    else:
        quicklook_src = "data:image/png;base64, {}".format(quicklook)
    return '<img src="{}" alt="{}" />'.format(quicklook_src, quicklook_alt_text), 200


@app.route("/service-desc/", methods=["GET"])
@cross_origin
def service_desc():
    """Render description"""
    return render_template(
        "index.html",
        content=get_home_page_content(request.base_url, DEFAULT_ITEMS_PER_PAGE),
    )


@app.route("/service-doc/", methods=["GET"])
@cross_origin
def service_doc():
    """Render doc"""
    return render_template(
        "index.html",
        content=get_home_page_content(request.base_url, DEFAULT_ITEMS_PER_PAGE),
    )


@app.route("/product-types/", methods=["GET"])
@app.route("/product-types/<provider>", methods=["GET"])
@cross_origin
def list_product_types(provider=None):
    """List eodag' supported product types"""
    try:
        product_types = get_product_types(provider, request.args)
    except UnsupportedProvider:
        return jsonify({"error": "Unknown provider: %s" % (provider,)}), 400
    except Exception:
        return jsonify({"error": "Unknown server error"}), 500
    return jsonify(product_types), 200


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
