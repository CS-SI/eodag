# -*- coding: utf-8 -*-
# Copyright 2020, CS GROUP - France, http://www.c-s.fr
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

from setuptools import find_packages, setup

BASEDIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))

metadata = {}
with open(os.path.join(BASEDIR, "eodag", "__meta__.py"), "r") as f:
    exec(f.read(), metadata)

with open(os.path.join(BASEDIR, "README.rst"), "r") as f:
    readme = f.read()

setup(
    name=metadata["__title__"],
    version=metadata["__version__"],
    description=metadata["__description__"],
    long_description=readme,
    author=metadata["__author__"],
    author_email=metadata["__author_email__"],
    url=metadata["__url__"],
    license=metadata["__license__"],
    packages=find_packages(exclude=("*.tests", "*.tests.*", "tests.*", "tests")),
    package_data={"": ["LICENSE", "NOTICE"]},
    include_package_data=True,
    install_requires=[
        # CLI Test fail with Click 7.1.1 : Changes introduced to string quoting in responses
        # https://github.com/pallets/click/issues/1499
        "click == 7.0.0",
        "requests",
        "python-dateutil",
        "PyYAML",
        "tqdm",
        "shapely",
        "fiona",
        "owslib == 0.18.0",
        "geojson",
        "pyproj",
        "usgs",
        "boto3 == 1.7.64",
        "numpy",
        "rasterio",
        "protobuf",
        "grpcio",
        "flasgger",
        "jsonpath-rw",
        "lxml",
        "xarray",
        "flask >= 1.0.2",
        "markdown >= 3.0.1",
        "unidecode == 1.0.22",
        "whoosh",
        # Temporary to avoid rasterio error on importing mock (to be removed when it is fixed upstream)
        'mock; python_version < "3.5" ',
    ],
    extras_require={
        "dev": [
            "nose",
            "tox",
            "faker",
            'mock; python_version < "3.5" ',
            "coverage",
            "moto==1.3.6",
            "twine",
            "wheel",
            "flake8",
            "pre-commit",
        ],
        "tutorials": [
            "jupyter",
            "ipyleaflet >= 0.10.0",
            "ipywidgets",
            "matplotlib",
            "folium",
            "imageio",
        ],
        "docs": ["sphinx == 3.3.0", "nbsphinx == 0.8.0", "nbsphinx-link == 1.3.0"],
    },
    entry_points={
        "console_scripts": ["eodag = eodag.cli:eodag"],
        "eodag.plugins.api": ["UsgsApi = eodag.plugins.apis.usgs:UsgsApi"],
        "eodag.plugins.auth": [
            "GenericAuth = eodag.plugins.authentication.generic:GenericAuth",
            "HTTPHeaderAuth = eodag.plugins.authentication.header:HTTPHeaderAuth",
            "OAuth = eodag.plugins.authentication.oauth:OAuth",
            "TokenAuth = eodag.plugins.authentication.token:TokenAuth",
            "OIDCAuthorizationCodeFlowAuth = eodag.plugins.authentication.openid_connect:OIDCAuthorizationCodeFlowAuth",  # noqa
            "KeycloakOIDCPasswordAuth = eodag.plugins.authentication.keycloak:KeycloakOIDCPasswordAuth",
        ],
        "eodag.plugins.crunch": [
            "FilterLatestIntersect = eodag.plugins.crunch.filter_latest_intersect:FilterLatestIntersect",
            "FilterLatestByName = eodag.plugins.crunch.filter_latest_tpl_name:FilterLatestByName",
            "FilterOverlap = eodag.plugins.crunch.filter_overlap:FilterOverlap",
        ],
        "eodag.plugins.download": [
            "AwsDownload = eodag.plugins.download.aws:AwsDownload",
            "HTTPDownload = eodag.plugins.download.http:HTTPDownload",
            "S3RestDownload = eodag.plugins.download.s3rest:S3RestDownload",
        ],
        "eodag.plugins.search": [
            "CSWSearch = eodag.plugins.search.csw:CSWSearch",
            "QueryStringSearch = eodag.plugins.search.qssearch:QueryStringSearch",
        ],
    },
    project_urls={
        "Bug Tracker": "https://github.com/CS-SI/eodag/issues/",
        "Documentation": "https://eodag.readthedocs.io/en/latest/",
        "Source Code": "https://github.com/CS-SI/eodag",
    },
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Natural Language :: English",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Scientific/Engineering :: GIS",
    ],
)
