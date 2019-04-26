#!/usr/bin/env python

# -*- coding: utf-8 -*-
# Copyright 2017-2018 CS Systemes d'Information (CS SI)
# All rights reserved

from __future__ import absolute_import, unicode_literals

import os
import sys
from functools import wraps

import flask
import requests
from flask import jsonify, make_response, render_template, request

from eodag.api.core import DEFAULT_ITEMS_PER_PAGE
from eodag.rest.utils import (
    get_home_page_content,
    get_product_types,
    search_product_by_id,
    search_products,
)
from eodag.utils import makedirs
from eodag.utils.exceptions import (
    UnsupportedProductType,
    UnsupportedProvider,
    ValidationError,
)

app = flask.Flask(__name__)


def cross_origin(request_handler):
    """Wraps a view to relax the need for csrf token"""

    @wraps(request_handler)
    def wrapper(*args, **kwargs):
        resp = make_response(request_handler(*args, **kwargs))
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    return wrapper


@app.route("/<product_type>/", methods=["GET"])
@cross_origin
def search(product_type):
    """Search for a product by product type on eodag"""
    try:
        response = search_products(product_type, request.args)
    except ValidationError as e:
        return jsonify({"error": e.message}), 400
    except RuntimeError as e:
        return jsonify({"error": e}), 400
    except UnsupportedProductType as e:
        return jsonify({"error": "Not Found: {}".format(e.product_type)}), 404

    return jsonify(response), 200


@app.route("/search/<uid>/", methods=["GET"])
@cross_origin
def search_by_id(uid):
    """Retrieve the quicklook of a eo product identified by its id"""
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
        return jsonify({"error": "Not found"}), 404
    return jsonify(search_result[0].as_dict()), 200


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


@app.route("/", methods=["GET"])
@cross_origin
def home():
    """Render home page"""
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
