#!/usr/bin/env python

# -*- coding: utf-8 -*-
# Copyright 2017-2018 CS Systemes d'Information (CS SI)
# All rights reserved

from __future__ import absolute_import, unicode_literals

import os
import sys
from collections import namedtuple
from functools import wraps

import dateutil.parser
import flask
import geojson
import markdown
from flask import Markup, jsonify, render_template, request, make_response

import eodag
from eodag.plugins.crunch.filter_latest_intersect import FilterLatestIntersect
from eodag.plugins.crunch.filter_latest_tpl_name import FilterLatestByName
from eodag.plugins.crunch.filter_overlap import FilterOverlap
from eodag.utils.exceptions import MisconfiguredError, UnsupportedProductType, UnsupportedProvider, ValidationError


app = flask.Flask(__name__)
app.config.from_object('eodag.rest.settings')

eodag_api = eodag.EODataAccessGateway(user_conf_file_path=app.config['EODAG_CFG_FILE'])
Cruncher = namedtuple('Cruncher', ['clazz', 'config_params'])
crunchers = {
    'latestIntersect': Cruncher(FilterLatestIntersect, []),
    'latestByName': Cruncher(FilterLatestByName, ['name_pattern']),
    'overlap': Cruncher(FilterOverlap, ['minimum_overlap']),
}


def _get_date(date):
    """Check if the input date can be parsed as a date"""
    if date:
        app.logger.info('checking input date: %s', date)
        try:
            date = dateutil.parser.parse(date).isoformat()
        except ValueError as e:
            exc = ValidationError('invalid input date: %s' % e)
            app.logger.error(exc.message)
            raise exc
        app.logger.info('successfully parsed date: %s', date)
    return date


def _get_int(val):
    """Check if the input can be parsed as an integer"""
    if val:
        try:
            val = int(val)
        except ValueError as e:
            raise ValidationError('invalid input integer value: %s' % e)
        app.logger.info('successfully parsed integer: %s', val)
    return val


def _search_bbox():
    search_bbox = None
    search_bbox_keys = ['lonmin', 'latmin', 'lonmax', 'latmax']
    request_bbox = request.args.get('box')

    if request_bbox:

        try:
            request_bbox_list = [float(coord) for coord in request_bbox.split(',')]
        except ValueError as e:
            raise ValidationError('invalid box coordinate type: %s' % e)

        search_bbox = dict(zip(search_bbox_keys, request_bbox_list))
        if len(search_bbox) != 4:
            raise ValidationError('input box is invalid: %s' % request_bbox)
        app.logger.info('search bounding box is: %s', search_bbox)

    else:
        app.logger.debug('box request param not set')

    return search_bbox


def _filter(products, **kwargs):
    filter = request.args.get('filter')
    if filter:
        app.logger.info('applying "%s" filter on search results', filter)
        cruncher = crunchers.get(filter)
        if not cruncher:
            return jsonify({'error': 'unknown filter name'}), 400

        cruncher_config = dict()
        for config_param in cruncher.config_params:
            config_param_value = request.args.get(config_param)
            if not config_param_value:
                raise ValidationError('filter additional parameters required: %s'
                                      % ', '.join(cruncher.config_params))
            cruncher_config[config_param] = config_param_value

        try:
            products = products.crunch(cruncher.clazz(cruncher_config), **kwargs)
        except MisconfiguredError as e:
            raise ValidationError(e)

    return products


def _product_types():
    result = []
    for provider in eodag_api.available_providers():
        for pt in eodag_api.list_product_types(provider):
            result.append('* *__{ID}__*: {desc}'.format(**pt))
    return '\n'.join(sorted(result))


def cross_origin(request_handler):
    @wraps(request_handler)
    def wrapper(*args, **kwargs):
        resp = make_response(request_handler(*args, **kwargs))
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
    return wrapper


@app.route('/<product_type>/', methods=['GET'])
@cross_origin
def search(product_type):
    try:
        criteria = {
            'geometry': _search_bbox(),
            'startTimeFromAscendingNode': _get_date(request.args.get('dtstart')),
            'completionTimeFromAscendingNode': _get_date(request.args.get('dtend')),
            'cloudCover': _get_int(request.args.get('cloudCover')),
        }
        products = eodag_api.search(product_type, **criteria)
        products = _filter(products, **criteria)

    except ValidationError as e:
        return jsonify({'error': e.message}), 400
    except RuntimeError as e:
        return jsonify({'error': e}), 400
    except UnsupportedProductType as e:
        return jsonify({'error': 'Not Found: {}'.format(e.product_type)}), 404

    return geojson.dumps(products)


@app.route('/', methods=['GET'])
@cross_origin
def home():
    with open(os.path.join(os.path.dirname(__file__), 'description.md'), 'rt') as fp:
        content = fp.read()
    content = content.format(base_url=request.base_url, product_types=_product_types())
    content = Markup(markdown.markdown(content))
    return render_template('index.html', content=content)


@app.route('/product-types/', methods=['GET'])
@app.route('/product-types/<provider>')
@cross_origin
def list_product_types(provider=None):
    if provider is not None:
        try:
            product_types = eodag_api.list_product_types(provider)
        except UnsupportedProvider:
            return jsonify({"error": "Unknown provider: %s" % (provider,)}), 400
        return jsonify(product_types)
    try:
        product_types = eodag_api.list_product_types()
    except Exception:
        return jsonify({"error": "Unknown server error"}), 500
    return jsonify(product_types)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="""Script for starting EODAG server""",
        epilog=""""""
    )
    parser.add_argument('-d', '--daemon',
                        action='store_true', help='run in daemon mode')
    parser.add_argument('-a', '--all-addresses',
                        action='store_true',
                        help='run flask using IPv4 0.0.0.0 (all network interfaces), ' +
                             'otherwise bind to 127.0.0.1 (localhost). ' +
                             'This maybe necessary in systems that only run Flask')
    args = parser.parse_args()

    if args.all_addresses:
        bind_host = '0.0.0.0'
    else:
        bind_host = '127.0.0.1'

    if args.daemon:
        pid = None
        try:
            pid = os.fork()
        except OSError as e:
            raise Exception('%s [%d]' % (e.strerror, e.errno))

        if pid == 0:
            os.setsid()
            app.run(threaded=True, host=bind_host)
        else:
            sys.exit(0)
    else:
        # For development
        app.run(debug=True, use_reloader=True)


if __name__ == '__main__':
    main()
