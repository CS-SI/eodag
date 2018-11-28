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

import re

import jsonpath_rw as jsonpath
from lxml import etree
from lxml.etree import XPathEvalError

from eodag.utils.metadata_mapping import get_metadata_path


# Keys taken from http://docs.opengeospatial.org/is/13-026r8/13-026r8.html
# For a metadata to be queryable, The way to query it must be specified in the provider metadata_mapping configuration
# parameter. It will be automatically detected as queryable by eodag when this is done
DEFAULT_METADATA_MAPPING = {
    # OpenSearch Parameters for Collection Search (Table 3)
    'productType': '$.properties.productType',
    'doi': '',
    'platform': '$.properties.platform',
    'platformSerialIdentifier': '$.properties.platformSerialIdentifier',
    'instrument': '$.properties.instrument',
    'sensorType': '$.properties.sensorType',
    'compositeType': '',
    'processingLevel': '$.properties.processingLevel',
    'orbitType': '$.properties.orbitType',
    'spectralRange': '',
    'wavelengths': '',
    'hasSecurityConstraints': '',
    'dissemination': '',

    # INSPIRE obligated OpenSearch Parameters for Collection Search (Table 4)
    'title': '$.properties.title',
    'topicCategory': '$.properties.topicCategory',
    'keyword': '$.properties.keyword',
    'abstract': '$.properties.abstract',
    'resolution': '$.properties.resolution',
    'organisationName': '$.properties.organisationName',
    'organisationRole': '',
    'publicationDate': '',
    'lineage': '',
    'useLimitation': '',
    'accessConstraint': '',
    'otherConstraint': '',
    'classification': '',
    'language': '',
    'specification': '',

    # OpenSearch Parameters for Product Search (Table 5)
    'parentIdentifier': '$.properties.parentIdentifier',
    'productionStatus': '',
    'acquisitionType': '',
    'orbitNumber': '$.properties.orbitNumber',
    'orbitDirection': '$.properties.orbitDirection',
    'track': '',
    'frame': '',
    'swathIdentifier': '',
    'cloudCover': '$.properties.cloudCover',
    'snowCover': '$.properties.snowCover',
    'lowestLocation': '',
    'highestLocation': '',
    'productVersion': '',
    'productQualityStatus': '',
    'productQualityDegradationTag': '',
    'processorName': '',
    'processingCenter': '',
    'creationDate': '',
    'modificationDate': '',
    'processingDate': '',
    'sensorMode': '$.properties.sensorMode',
    'archivingCenter': '',
    'processingMode': '',

    # OpenSearch Parameters for Acquistion Parameters Search (Table 6)
    'availabilityTime': '',
    'acquisitionStation': '',
    'acquisitionSubType': '',
    'startTimeFromAscendingNode': '$.properties.startTimeFromAscendingNode',
    'completionTimeFromAscendingNode': '$.properties.completionTimeFromAscendingNode',
    'illuminationAzimuthAngle': '',
    'illuminationZenithAngle': '',
    'illuminationElevationAngle': '',
    'polarizationMode': '',
    'polarisationChannels': '',
    'antennaLookDirection': '',
    'minimumIncidenceAngle': '',
    'maximumIncidenceAngle': '',
    'dopplerFrequency': '',
    'incidenceAngleVariation': '',

    # Custom parameters (not defined in the base document referenced above)
    'id': '$.id',
    # The geographic extent of the product
    'geometry': '$.geometry',
    # The url of the quicklook
    'quicklook': '$.properties.quicklook',
    # The url to download the product "as is" (literal or as a template to be completed either after the search result
    # is obtained from the provider or during the eodag download phase)
    'downloadLink': '$.properties.downloadLink'
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
    templates = {}
    for metadata in DEFAULT_METADATA_MAPPING:
        if metadata not in mapping:
            properties[metadata] = 'N/A'
        else:
            try:
                path = jsonpath.parse(get_metadata_path(mapping[metadata]))
            except Exception:   # jsonpath_rw does not provide a proper exception
                # Assume the mapping is to be passed as is, in which case we readily register it, or is a template, in
                # which case we register it for later formatting resolution using previously successfully resolved
                # properties
                text = get_metadata_path(mapping[metadata])
                if re.search(r'({[^{}]+})+', text):
                    templates[metadata] = text
                else:
                    properties[metadata] = text
            else:
                match = path.find(json)
                properties[metadata] = match[0].value if len(match) == 1 else None
    # Resolve templates
    for metadata, template in templates.items():
        properties[metadata] = template.format(**properties)
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
    templates = {}
    root = etree.XML(xml_as_text)
    for metadata in DEFAULT_METADATA_MAPPING:
        if metadata not in mapping:
            properties[metadata] = 'N/A'
        else:
            try:
                value = root.xpath(get_metadata_path(mapping[metadata]), namespaces=root.nsmap)
                if len(value) > 1:
                    properties[metadata] = value
                else:
                    properties[metadata] = value[0] if len(value) == 1 else None
            except XPathEvalError:
                # Assume the mapping is to be passed as is, in which case we readily register it, or is a template, in
                # which case we register it for later formatting resolution using previously successfully resolved
                # properties
                text = get_metadata_path(mapping[metadata])
                if re.search(r'({[^{}]+})+', text):
                    templates[metadata] = text
                else:
                    properties[metadata] = text
    # Resolve templates
    for metadata, template in templates.items():
        properties[metadata] = template.format(**properties)
    return properties
