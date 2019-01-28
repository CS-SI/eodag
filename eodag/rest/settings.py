# -*- coding: utf-8 -*-
# Copyright 2017-2018 CS Systemes d'Information (CS SI)
# All rights reserved
"""EODAG server configuration module"""
import os

# Default configuration file is supposed to live in the same directory as this module, named "eodag_config.yml"
EODAG_CFG_FILE = os.path.abspath(os.path.realpath(os.path.join(os.path.dirname(__file__), 'eodag_config.yml')))
