# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import os
from operator import attrgetter
from os.path import join as join_path
from pathlib import Path

from contextlib import contextmanager

from satdl.config import Config
from satdl.plugins.instances_manager import PluginInstancesManager
from satdl.utils.exceptions import PluginImplementationError


class SatImagesAPI(object):
    """An API for downloading a wide variety of geospatial products originating from different types of systems."""

    def __init__(self, config_filepath=None):
        # if config_filepath is None:
        #     config_path = Path(join_path(os.path.dirname(__file__), 'resources', 'default_config.yml'))
        # else:
        #     config_path = Path(os.path.abspath(os.path.realpath(config_filepath)))
        # self.config_path = config_path
        # self.config = Config(config_path)
        self.config = {
            'eocloud': {
                'search': {
                    'plugin': 'RestoSearch',
                    'priority': 1000,
                    'api_endpoint': 'http://finder.eocloud.eu/resto/api/',
                    'products': {
                        'Sentinel2': {
                            'min_start_date': '2016-12-10',  # new S2 products specification
                            'product_types': 'L1C',
                            'instrument': None,
                            'band2_pattern': '*B02.tif',
                            'lms': '40',
                        },
                        'Landsat8': {
                            'min_start_date': '2013-05-26',
                            'product_types': 'L1T',
                            'instrument': 'OLI',
                            'band2_pattern': '*_B2.tif',
                            'lms': '120',
                        },
                        'Envisat': {
                            'min_start_date': '2002-05-17',
                            'product_types': 'FRS',
                            'instrument': None,
                            'band2_pattern': '*_band_02.tif',
                            'lms': '1200',
                        },
                    },
                },
                'download': {
                    'plugin': 'HTTPDownload',
                    'priority': 1000,
                    'authenticate': True,
                    'on_site': False,
                    'base_uri': 'https://static.eocloud.eu/v1/AUTH_8f07679eeb0a43b19b33669a4c888c45/eorepo',
                    'outputs_prefix': '/home/adrien/workspace/geoproductsgod',
                },
                'auth': {
                    'plugin': 'TokenAuth',
                    'auth_uri': 'https://finder.eocloud.eu/resto/api/authidentity',
                    'token_type': 'json',
                    'credentials': {
                        'domainName': 'cloud_00154',
                        'userName': 'vincent.gaudissart@c-s.fr',
                        'userPass': 'Moimoi31!',
                    },
                },
            },
            # 'thiea-landsat': {
            #     'search': {
            #         'plugin': 'RestoSearch',
            #         'priority': 1,
            #         'api_endpoint': 'https://theia-landsat.cnes.fr/resto/api/',
            #         'products': {
            #             'Landsat': {
            #                 'product_types': [
            #                     'REFLECTANCE',
            #                     'REFLECTANCETOA',
            #                 ],
            #             },
            #         },
            #     },
            #     'download': {
            #         'plugin': 'HTTPDownload',
            #         'priority': 1,
            #         'auth': {
            #             'method': 'basic',
            #             'auth_uri': '',
            #             'credentials': {
            #                 'username': '',
            #                 'password': '',
            #             },
            #         },
            #         'issuer_id': '',
            #     }
            # },
            'thiea': {
                'search': {
                    'plugin': 'RestoSearch',
                    'priority': 10,
                    'api_endpoint': 'https://theia.cnes.fr/atdistrib/resto2/api',
                    'products': {
                        'SpotWorldHeritage': {
                            'product_types': 'REFLECTANCETOA',
                            'min_start_date': '2018-01-01',
                        },
                        'SENTINEL2': {
                            'product_types': 'REFLECTANCE',
                            'min_start_date': '2018-01-01',
                        },
                        'Snow': {
                            'product_types': ['REFLECTANCE', 'SNOW_MASK'],
                            'min_start_date': '2018-01-01',
                        },
                    },
                },
                'download': {
                    'plugin': 'HTTPDownload',
                    'priority': 10,
                    'authenticate': False,
                    'base_uri': 'https://theia.cnes.fr/atdistrib/resto2',
                    'dl_url_params': {
                        'issuerId': 'theia'
                    }
                },
                'auth': {
                    'plugin': 'TokenAuth',
                    'auth_uri': 'https://theia.cnes.fr/atdistrib/services/authenticate/',
                    'credentials': {
                        'ident': '',
                        'pass': '',
                    },
                },
            },
            # 'scihub': {
            #     'search': {
            #         'plugin': 'SentinelSearch',
            #         'priority': 0,
            #         'api_endpoint': 'https://scihub.copernicus.eu/apihub/',
            #         'products': {},
            #     },
            #     'download': {
            #         'plugin': 'HTTPDownload',
            #         'priority': 0,
            #         'auth': {
            #             'method': 'basic',
            #             'auth_uri': '',
            #             'credentials': {
            #                 'username': '',
            #                 'password': '',
            #             },
            #         },
            #         'issuer_id': '',
            #     }
            # }
        }
        self.pim = PluginInstancesManager(self.config)

    def search(self, product_type, **kwargs):
        """Look for products matching criteria in known systems.

        The interfaces are required to return a list as a result of their processing, we enforce this requirement here.
        """
        interface = self.__get_searcher()
        query_params = self.__get_interface_query_params(interface, kwargs)
        results = interface.query(product_type, **query_params)
        if not isinstance(results, list):
            raise PluginImplementationError(
                'The query function of a Search plugin must return a list of results, got {} '
                'instead'.format(type(results))
            )
        return results

    def filter(self, results):
        """Consolidate results of a search (prep for downloading)"""
        return results
        # interface = self.__get_consolidator(results)
        # return interface.process()

    def download_all(self, products):
        """Download all products of a search"""
        for product in products:
            yield self.__download(product)

    def __download(self, product):
        """Download a single product"""
        interface = self.__get_downloader()
        authentication = None
        if interface.authenticate:
            authenticator = self.pim.instantiate_plugin_by_config(
                topic_name='auth',
                topic_config=self.config[interface.instance_name]['auth']
            )
            authentication = authenticator.authenticate()
        try:
            local_filename = interface.download(product, auth=authentication)
            if local_filename is None:
                print(
                    'WARNING: the download method of a Download plugin should return the absolute path to the '
                    'downloaded resource'
                )
            else:
                return local_filename
        except TypeError as e:
            # Enforcing the requirement for download plugins to implement a download method with auth kwarg
            if any("got an unexpected keyword argument 'auth'" in arg for arg in e.args):
                raise PluginImplementationError(
                    'The download method of a Download plugin must support auth keyword argument'
                )
            raise e

    def __get_searcher(self):
        """Look for a search interface to use, based on the configuration of the api"""
        search_plugin_instances = self.pim.instantiate_configured_plugins(topic='search')
        # The searcher used will be the one with higher priority
        search_plugin_instances.sort(key=attrgetter('priority'), reverse=True)
        return search_plugin_instances[0]

    def __get_downloader(self):
        dl_plugin_instances = self.pim.instantiate_configured_plugins(topic='download')
        dl_plugin_instances.sort(key=attrgetter('priority'), reverse=True)
        return dl_plugin_instances[0]

    def __get_consolidator(self, search_result):
        from .plugins.filter.base import Filter
        for consolidator in Filter.plugins:
            if True:
                return consolidator()

    def __get_interface_query_params(self, interface, generic_query_params):
        """If a mapping should be done for the interface, do it here"""
        return generic_query_params

