# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from copy import deepcopy


INSTANCE_CONFIG_STRUCTURE = {
    'search': {
        'plugin': '',
        'productType': {''},
        'instanceUrl': '',
        'additionalConfig': {}
    },
    'download': {
        'plugin': '',
        'linkInfo': '',
    },
    'filter': {
        'plugin': '',
    },
}


class Config(object):
    def __init__(self, conf_path):
        self.conf_path = conf_path
        self.temporary = {
            'eocloud': deepcopy(INSTANCE_CONFIG_STRUCTURE),
            'theia': deepcopy(INSTANCE_CONFIG_STRUCTURE),
        }
        self.temporary['eocloud']['search'].update({
            'plugin': 'resto',
            'productType': {'S2L1B'}
        })
        self.temporary['eocloud']['download'].update({
            'plugin': 'resto',
            'linkInfo': 'productIdentifier',
        })

        self.temporary['theia']['search'].update({
            'plugin': 'resto',
            'productType': {'S2_L1C', 'S2_L2A'}
        })
        self.temporary['theia']['download'].update({
            'plugin': 'resto',
            'linkInfo': 'url',
        })


