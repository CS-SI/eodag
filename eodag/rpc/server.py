# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
from __future__ import unicode_literals

import logging
import time

import grpc
from concurrent.futures import ThreadPoolExecutor

from eodag import SatImagesAPI
from eodag.rpc.protocol import eodag_pb2, eodag_pb2_grpc


logger = logging.getLogger('eodag.rpc.server')


class EODAGRPCServer(object):
    ONE_DAY_IN_SECONDS = 60 * 60 * 24

    def __init__(self, host, port, user_conf):
        logger.info('Initializing eodag rpc server')
        eodag = SatImagesAPI(user_conf_file_path=user_conf)
        self.eo_product_type_iface = EOProductTypeService(eodag)
        self.eo_product_iface = EOProductService(eodag)
        self.address = '{}:{}'.format(host, port)

    def serve(self):
        server = grpc.server(ThreadPoolExecutor(max_workers=10))
        eodag_pb2_grpc.add_EOProductServicer_to_server(self.eo_product_iface, server)
        eodag_pb2_grpc.add_EOProductTypeServicer_to_server(self.eo_product_type_iface, server)
        server.add_insecure_port(self.address)
        logger.info('Starting eodag rpc server')
        server.start()
        logger.info('eodag rpc server is now listening for requests at %s', self.address)
        try:
            while True:
                time.sleep(self.ONE_DAY_IN_SECONDS)
        except KeyboardInterrupt:
            server.stop(0)


class EOProductTypeService(eodag_pb2_grpc.EOProductTypeServicer):

    def __init__(self, eodag):
        super(EOProductTypeService, self).__init__()
        self.eodag = eodag

    def ListProductTypes(self, request, context):
        """List the product types known by the system"""
        logger.info('New request for available product types: %s', request or '<Empty>')
        logger.debug('Context: %s', context)
        for product_type in self.eodag.list_product_types():
            schema = eodag_pb2.EOProductTypeSchema()
            schema.id = product_type['ID']
            schema.description = product_type['desc']
            for metadata in product_type['meta']:
                meta = schema.meta.add()
                meta.key = metadata['key']
                meta.value_type = metadata['type']
            yield schema
        logger.info('Request successfully executed')

    def SearchProductType(self, request, context):
        """Show the information on a known product type"""
        # TODO: implement the interaction with whoosh here


class EOProductService(eodag_pb2_grpc.EOProductServicer):

    def __init__(self, eodag):
        super(EOProductService, self).__init__()
        self.eodag = eodag

    def SearchProduct(self, request, context):
        pass

    def DownloadProduct(self, request, context):
        pass
