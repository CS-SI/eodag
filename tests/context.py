# -*- coding: utf-8 -*-
"""Explicitly import here everything you want to use from the eodag package"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from eodag import api, config
from eodag.cli import eodag, list_pt, search_crunch, download
from eodag.plugins.search.base import Search
from eodag.plugins.search.resto import RestoSearch
