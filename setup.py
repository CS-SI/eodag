# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from setuptools import setup, find_packages


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

with open('requirements.txt') as f:
    requirements = f.readlines()

setup(
    name='satdl',
    version='0.1.0',
    description='A library and cli for downloading satellites images',
    long_description=readme,
    author="CS Systemes d'Information (CS SI)",
    author_email='adrien.oyono@c-s.fr',
    url='https://bitbucket.org/geostorm/eodag',
    license=license,
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=requirements,
    entry_points='''
        [console_scripts]
        satdl=satdl.cli:main
    ''',
)

