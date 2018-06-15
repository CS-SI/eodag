# -*- coding: utf-8 -*-
# Copyright 2018 CS Systemes d'Information (CS SI)
# All rights reserved
from __future__ import unicode_literals

from eodag.api.product.drivers.base import NoDriver
from eodag.api.product.drivers.sentinel2_l1c import Sentinel2L1C


DRIVERS = {
    'S2_MSI_L1C': Sentinel2L1C(),
}
