# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import re

# AWS chunk path identify patterns

# S2 L2A Tile files -----------------------------------------------------------
S2L2A_TILE_IMG_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/R(?P<res>[0-9]+m)/(?P<file>[A-Z0-9_]+)\.jp2$"
)
S2L2A_TILE_AUX_DIR_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/auxiliary/(?P<file>AUX_.+)$"
)
# S2 L2A QI Masks
S2_TILE_QI_MSK_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/qi/(?P<file_base>.+)_(?P<file_suffix>[0-9]+m\.jp2)$"
)
# S2 L2A QI PVI
S2_TILE_QI_PVI_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/qi/L2A_PVI\.jp2$"
)
# S2 Tile files ---------------------------------------------------------------
S2_TILE_IMG_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/(?P<file>[A-Z0-9_]+\.jp2)$"
)
S2_TILE_PREVIEW_DIR_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/preview/(?P<file>.+)$"
)
S2_TILE_AUX_DIR_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/auxiliary/(?P<file>.+)$"
)
S2_TILE_QI_DIR_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/qi/(?P<file>.+)$"
)
S2_TILE_THUMBNAIL_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/(?P<file>preview\.\w+)$"
)
S2_TILE_MTD_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/(?P<file>metadata\.xml)$"
)
# S2 Tile generic
S2_TILE_REGEX = re.compile(
    r"^tiles/(?P<tile1>[0-9]+)/(?P<tile2>[A-Z]+)/(?P<tile3>[A-Z]+)/(?P<year>[0-9]+)/(?P<month>[0-9]+)/"
    + r"(?P<day>[0-9]+)/(?P<num>[0-9]+)/(?P<file>.+)$"
)
# S2 Product files
S2_PROD_REGEX = re.compile(
    r"^products/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<title>[A-Z0-9_]+)/(?P<file>.+)$"
)
S2_PROD_DS_MTD_REGEX = re.compile(
    r"^products/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<title>[A-Z0-9_]+)/datastrip/"
    + r"(?P<num>.+)/(?P<file>metadata\.xml)$"
)
S2_PROD_DS_QI_REGEX = re.compile(
    r"^products/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<title>[A-Z0-9_]+)/datastrip/"
    + r"(?P<num>.+)/qi/(?P<file>.+)$"
)
S2_PROD_DS_QI_REPORT_REGEX = re.compile(
    r"^products/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<title>[A-Z0-9_]+)/datastrip/"
    + r"(?P<num>.+)/qi/(?P<filename>.+)_report\.xml$"
)
S2_PROD_INSPIRE_REGEX = re.compile(
    r"^products/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<title>[A-Z0-9_]+)/"
    + r"(?P<file>inspire\.xml)$"
)
# S2 Product generic
S2_PROD_MTD_REGEX = re.compile(
    r"^products/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<title>[A-Z0-9_]+)/"
    + r"(?P<file>metadata\.xml)$"
)
# S1 files --------------------------------------------------------------------
S1_CALIB_REGEX = re.compile(
    r"^GRD/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<beam>[A-Z0-9]+)/(?P<prod_pol>[A-Z0-9]+)/"
    + r"(?P<title>[A-Z0-9_]+)/annotation/calibration/"
    + r"(?P<file_prefix>[a-z]+)-(?P<file_beam>[a-z]+)-(?P<file_pol>.+)\.xml$"
)
S1_ANNOT_REGEX = re.compile(
    r"^GRD/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<beam>[A-Z0-9]+)/(?P<prod_pol>[A-Z0-9]+)/"
    + r"(?P<title>[A-Z0-9_]+)/annotation/"
    + r"(?P<file_beam>[a-z]+)-(?P<file_pol>.+)\.xml$"
)
S1_MEAS_REGEX = re.compile(
    r"^GRD/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<beam>[A-Z0-9]+)/(?P<prod_pol>[A-Z0-9]+)/"
    + r"(?P<title>[A-Z0-9_]+)/measurement/"
    + r"(?P<file_beam>[a-z]+)-(?P<file_pol>.+)\.(?P<file_ext>[a-z0-9]+)$"
)
S1_REPORT_REGEX = re.compile(
    r"^GRD/(?P<year>[0-9]+)/(?P<month>[0-9]+)/(?P<day>[0-9]+)/(?P<beam>[A-Z0-9]+)/(?P<prod_pol>[A-Z0-9]+)/"
    + r"(?P<title>[A-Z0-9_]+)/(?P<file>report-\w+\.pdf)$"
)
# S1 generic
S1_REGEX = re.compile(
    r"^GRD/[0-9]{4}/[0-9]+/[0-9]+/[A-Z0-9]+/[A-Z0-9]+/(?P<title>S1[A-Z0-9_]+)/(?P<file>.+)$"
)
# CBERS4 generic
CBERS4_REGEX = re.compile(
    r"^GRD/[0-9]{4}/[0-9]+/[0-9]+/[A-Z0-9]+/[A-Z0-9]+/(?P<title>S1[A-Z0-9_]+)/(?P<file>.+)$"
)

# S1 image number conf per polarization ---------------------------------------
S1_IMG_NB_PER_POLAR = {
    "SH": {"HH": 1},
    "SV": {"VV": 1},
    "DH": {"HH": 1, "HV": 2},
    "DV": {"VV": 1, "VH": 2},
    "HH": {"HH": 1},
    "HV": {"HV": 1},
    "VV": {"VV": 1},
    "VH": {"VH": 1},
}
