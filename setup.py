# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
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

