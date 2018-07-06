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

from eodag import __version__

BASEDIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))

with open(os.path.join(BASEDIR, 'README.rst'), 'r') as f:
    readme = f.read()

with open(os.path.join(BASEDIR, 'LICENSE'), 'r') as f:
    license = f.read()

with open(os.path.join(BASEDIR, 'requirements.txt'), 'r') as f:
    requirements = f.readlines()

setup(
    name='eodag',
    version=__version__,
    description='A library and cli for downloading satellites images',
    long_description=readme,
    author="CS Systemes d'Information (CS SI)",
    author_email='adrien.oyono@c-s.fr',
    url='https://bitbucket.org/geostorm/eodag',
    license=license,
    packages=find_packages(exclude=('tests', 'docs')),
    package_data={'eodag': ['resources/*', ]},
    install_requires=requirements,
    entry_points='''
        [console_scripts]
        eodag=eodag.cli:eodag
    ''',
)

