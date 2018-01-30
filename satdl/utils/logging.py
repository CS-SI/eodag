# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import logging.config


def setup_logging(**kwargs):
    verbosity = kwargs.pop('verbose')
    if verbosity == 0:
        logging.config.dictConfig({
            'version': 1,
            'disable_existing_loggers': False,
            'handlers': {
                'null': {
                    'level': 'DEBUG',
                    'class': 'logging.NullHandler',
                },
            },
            'loggers': {
                'satdl': {
                    'handlers': ['null'],
                    'propagate': True,
                    'level': 'INFO',
                },
            }
        })
    elif verbosity <= 2:
        logging.config.dictConfig({
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s-15s %(name)-32s [%(levelname)-8s] %(message)s'
                },
            },
            'handlers': {
                'console': {
                    'level': 'DEBUG',
                    'class': 'logging.StreamHandler',
                    'formatter': 'standard'
                },
            },
            'loggers': {
                'satdl': {
                    'handlers': ['console'],
                    'propagate': True,
                    'level': 'INFO',
                },
            }
        })
    elif verbosity == 3:
        logging.config.dictConfig({
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'verbose': {
                    'format': '%(asctime)s-15s %(name)-32s [%(levelname)-8s] (%(module)-17s) %(message)s'
                },
            },
            'handlers': {
                'console': {
                    'level': 'DEBUG',
                    'class': 'logging.StreamHandler',
                    'formatter': 'verbose'
                },
            },
            'loggers': {
                'satdl': {
                    'handlers': ['console'],
                    'propagate': True,
                    'level': 'DEBUG',
                },
            }
        })
