# -*- coding: utf-8 -*-
# Copyright 2018, CS Systemes d'Information, http://www.c-s.fr
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
from __future__ import unicode_literals

import jsonpath_rw as jsonpath
from lxml import etree

from eodag.utils.metadata_mapping import get_metadata_path


DEFAULT_METADATA_MAPPING = {
    'id': '$.id',
    'geometry': '$.geometry',
    'productType': '$.properties.productType',
    'platform': '$.properties.platform',
    'platformSerialIdentifier': '$.properties.platformSerialIdentifier',
    'instrument': '$.properties.instrument',
    'sensorType': '$.properties.sensorType',
    'processingLevel': '$.properties.processingLevel',
    'orbitType': '$.properties.orbitType',
    'title': '$.properties.title',
    'topicCategory': '$.properties.topicCategory',
    'keyword': '$.properties.keyword',
    'abstract': '$.properties.abstract',
    'organisationName': '$.properties.organisationName',
    'orbitNumber': '$.properties.orbitNumber',
    'orbitDirection': '$.properties.orbitDirection',
    'cloudCover': '$.properties.cloudCover',
    'snowCover': '$.properties.snowCover',
    'startTimeFromAscendingNode': '$.properties.startTimeFromAscendingNode',
    'completionTimeFromAscendingNode': '$.properties.completionTimeFromAscendingNode',
    'parentIdentifier': '$.properties.parentIdentifier',
    'resolution': '$.properties.resolution',
    'sensorMode': '$.properties.sensorMode',
}


def properties_from_json(json, mapping):
    """Extract properties from a provider json result.

    :param json: the representation of a provider result as a json object
    :type json: dict
    :param mapping: a mapping between :class:`~eodag.api.product.EOProduct`'s metadata keys and the location of the
                    values of these properties in the json representation, expressed as a
                    `jsonpath <http://goessner.net/articles/JsonPath/>`_
    :return: the metadata of the :class:`~eodag.api.product.EOProduct`
    :rtype: dict
    """
    properties = {}
    for metadata in DEFAULT_METADATA_MAPPING:
        if metadata not in mapping:
            properties[metadata] = 'N/A'
        else:
            path = jsonpath.parse(get_metadata_path(mapping[metadata]))
            match = path.find(json)
            properties[metadata] = match[0].value if len(match) == 1 else None
    return properties


def properties_from_xml(xml_as_text, mapping):
    """Extract properties from a provider xml result.

    :param xml_as_text: the representation of a provider result as xml
    :type xml_as_text: str or unicode
    :param mapping: a mapping between :class:`~eodag.api.product.EOProduct`'s metadata keys and the location of the
                    values of these properties in the xml representation, expressed as a
                    `xpath <https://www.w3schools.com/xml/xml_xpath.asp>`_
    :return: the metadata of the :class:`~eodag.api.product.EOProduct`
    :rtype: dict
    """
    properties = {}
    root = etree.XML(xml_as_text)
    for metadata in DEFAULT_METADATA_MAPPING:
        if metadata not in mapping:
            properties[metadata] = 'N/A'
        else:
            value = root.xpath(get_metadata_path(mapping[metadata]), namespaces=root.nsmap)
            if len(value) > 1:
                properties[metadata] = value
            else:
                properties[metadata] = value[0] if len(value) == 1 else None
    return properties
