# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved


class ValidationError(Exception):
    """Error validating data"""
    def __init__(self, message):
        self.message = message


class PluginNotFoundError(Exception):
    """Error when looking for a plugin class that was not defined"""


class PluginImplementationError(Exception):
    """Error when a plugin does not behave as expected"""

