# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals


def no_blanks(string):
    """Removes all the blanks in string

    :param string: A string to remove blanks from
    :type string: str | unicode (PY2 only)

    :returns the same string with all blank characters removed
    """
    return string.replace('\n', '').replace('\t', '').replace(' ', '')
