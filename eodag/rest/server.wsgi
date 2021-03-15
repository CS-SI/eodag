#!/usr/bin/env python

from eodag.rest.server import app as application  # noqa
from eodag.utils.logging import setup_logging

setup_logging(verbose=3)
