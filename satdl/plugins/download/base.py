# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from satdl.plugins.base import GeoProductDownloaderPluginMount
from satdl.plugins.search.base import MisconfiguredError


class Download(metaclass=GeoProductDownloaderPluginMount):
    def __init__(self, config):
        self.config = config
        self.authenticate = bool(self.config.setdefault('authenticate', False))
        # if self.system_config['auth']:
        #     try:
        #         if self.system_config['auth']['method'] not in ('basic', 'digest', 'token'):
        #             raise MisconfiguredError
        #     except KeyError:    # KeyError raised if 'method' not in self.system_config['auth']
        #         raise MisconfiguredError
        #     if 'credentials' not in self.system_config['auth'] or not isinstance(self.system_config['auth']['credentials'], dict):
        #         raise MisconfiguredError
        #     if self.system_config['auth']['method'] in ('basic', 'digest'):
        #         if not all(key in self.system_config['auth']['credentials'] for key in ('username', 'password')):
        #             raise MisconfiguredError
        #     if self.system_config['auth']['method'] == 'token':
        #         if 'auth_uri' not in self.system_config['auth']:
        #             raise MisconfiguredError
        # try:
        #     self.priority = int(config.get('priority', self.priority))
        # except ValueError:
        #     raise MisconfiguredError("'priority' must be an integer (lower value means lower priority, even for "
        #                              "negative values)")

    def download(self, product, auth=None):
        raise NotImplementedError('A Download plugin must implement a method named download')

