#!/usr/bin/env python

activate_this = '/projects/geostorm/wps-venv/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

from .server import app as application
