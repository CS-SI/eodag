# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

from eodag.api.product.drivers.sentinel2 import Sentinel2


DRIVERS = {
    ('S2A', 'MSI'): Sentinel2,
    ('S2B', 'MSI'): Sentinel2,
}

