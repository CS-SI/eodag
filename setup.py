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
import os
from setuptools import setup, find_packages

BASEDIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))

metadata = {}
with open(os.path.join(BASEDIR, 'eodag', '__meta__.py'), 'r') as f:
    exec(f.read(), metadata)

with open(os.path.join(BASEDIR, 'README.rst'), 'r') as f:
    readme = f.read()

setup(
    name=metadata['__title__'],
    version=metadata['__version__'],
    description=metadata['__description__'],
    long_description=readme,
    author=metadata['__author__'],
    author_email=metadata['__author_email__'],
    url=metadata['__url__'],
    license=metadata['__license__'],
    packages=find_packages(exclude=('*.tests', '*.tests.*', 'tests.*', 'tests')),
    package_data={'': ['LICENSE', 'NOTICE']},
    include_package_data=True,
    install_requires=[
        'click',
        'requests',
        'python-dateutil',
        'PyYAML',
        'tqdm',
        'shapely',
        'owslib',
        'six',
        'geojson',
        'pyproj',
        'usgs',
        'boto3 == 1.7.64',
        'numpy',
        'rasterio',
        'protobuf',
        'grpcio',
        # To be able to do 'import concurrent.futures' in Python 2.7
        "futures; python_version < '3.5'",
        'jsonpath-rw',
        'lxml',
        'xarray',
    ],
    extras_require={
        'dev': [
            'nose',
            'tox',
            'faker',
            'mock; python_version < "3.5" ',
            'coverage',
            'moto==1.3.6',
            'twine',
            'wheel',
            'flake8',
        ],
        'tutorials': [
            'jupyter',
            'ipyleaflet',
            'ipywidgets',
            'matplotlib',
        ],
        'docs': [
            'sphinx == 1.8.0',
            'nbsphinx-link == 1.1.1'
        ]
    },
    entry_points={
        'console_scripts': [
            'eodag = eodag.cli:eodag'
        ],
        'eodag.plugins.api': [
            'UsgsApi = eodag.plugins.apis.usgs:UsgsApi',
        ],
        'eodag.plugins.auth': [
            'GenericAuth = eodag.plugins.authentication.generic:GenericAuth',
            'HTTPHeaderAuth = eodag.plugins.authentication.header:HTTPHeaderAuth',
            'OAuth = eodag.plugins.authentication.oauth:OAuth',
            'TokenAuth = eodag.plugins.authentication.token:TokenAuth',
            'OIDCAuthorizationCodeFlowAuth = eodag.plugins.authentication.openid_connect:OIDCAuthorizationCodeFlowAuth',    # noqa
            'KeycloakOIDCPasswordAuth = eodag.plugins.authentication.keycloak:KeycloakOIDCPasswordAuth',
        ],
        'eodag.plugins.crunch': [
            'FilterLatestIntersect = eodag.plugins.crunch.filter_latest_intersect:FilterLatestIntersect',
            'FilterLatestByName = eodag.plugins.crunch.filter_latest_tpl_name:FilterLatestByName',
            'FilterOverlap = eodag.plugins.crunch.filter_overlap:FilterOverlap',
        ],
        'eodag.plugins.download': [
            'AwsDownload = eodag.plugins.download.aws:AwsDownload',
            'HTTPDownload = eodag.plugins.download.http:HTTPDownload',
        ],
        'eodag.plugins.search': [
            'CSWSearch = eodag.plugins.search.csw:CSWSearch',
            'QueryStringSearch = eodag.plugins.search.qssearch:QueryStringSearch',
        ],
    },
    project_urls={
        "Bug Tracker": "https://bitbucket.org/geostorm/eodag/issues/",
        "Documentation": "https://eodag.readthedocs.io/en/latest/",
        "Source Code": "https://bitbucket.org/geostorm/eodag",
    },
    classifiers=(
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Scientific/Engineering :: GIS',
    ),
)
