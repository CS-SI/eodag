# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

import logging
import time

import grpc
from concurrent.futures import ThreadPoolExecutor

from eodag import SatImagesAPI
from eodag.rpc.protocol import eodag_pb2, eodag_pb2_grpc


logger = logging.getLogger(b'eodag.rpc.server')


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
        for pt_id, conf in self.eodag.product_types_config.items():
            schema = eodag_pb2.EOProductTypeSchema()
            schema.id = pt_id
            schema.description = conf['desc']
            for metadata in conf['meta']:
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
