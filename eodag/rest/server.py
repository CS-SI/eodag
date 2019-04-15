#!/usr/bin/env python

# -*- coding: utf-8 -*-
# Copyright 2017-2018 CS Systemes d'Information (CS SI)
# All rights reserved

from __future__ import absolute_import, unicode_literals

import os
import sys
from functools import wraps

import flask
from flask import jsonify, make_response, render_template, request

from eodag.api.core import DEFAULT_ITEMS_PER_PAGE
from eodag.rest.utils import get_home_page_content, get_product_types, search_products
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
