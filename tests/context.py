# -*- coding: utf-8 -*-
"""Explicitly import here everything you want to use from the satdl package"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from satdl import api, cli, config
from satdl.plugins.search.base import Search
from satdl.plugins.search.resto import RestoSearch
