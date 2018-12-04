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
    'doi': '$.properties.doi',
    'platform': '$.properties.platform',
    'platformSerialIdentifier': '$.properties.platformSerialIdentifier',
    'instrument': '$.properties.instrument',
    'sensorType': '$.properties.sensorType',
    'compositeType': '$.properties.compositeType',
    'processingLevel': '$.properties.processingLevel',
    'orbitType': '$.properties.orbitType',
    'spectralRange': '$.properties.spectralRange',
    'wavelengths': '$.properties.wavelengths',
    'hasSecurityConstraints': '$.properties.hasSecurityConstraints',
    'dissemination': '$.properties.dissemination',

    # INSPIRE obligated OpenSearch Parameters for Collection Search (Table 4)
    'title': '$.properties.title',
    'topicCategory': '$.properties.topicCategory',
    'keyword': '$.properties.keyword',
    'abstract': '$.properties.abstract',
    'resolution': '$.properties.resolution',
    'organisationName': '$.properties.organisationName',
    'organisationRole': '$.properties.organisationRole',
    'publicationDate': '$.properties.publicationDate',
    'lineage': '$.properties.lineage',
    'useLimitation': '$.properties.useLimitation',
    'accessConstraint': '$.properties.accessConstraint',
    'otherConstraint': '$.properties.otherConstraint',
    'classification': '$.properties.classification',
    'language': '$.properties.language',
    'specification': '$.properties.specification',

    # OpenSearch Parameters for Product Search (Table 5)
    'parentIdentifier': '$.properties.parentIdentifier',
    'productionStatus': '$.properties.productionStatus',
    'acquisitionType': '$.properties.acquisitionType',
    'orbitNumber': '$.properties.orbitNumber',
    'orbitDirection': '$.properties.orbitDirection',
    'track': '$.properties.track',
    'frame': '$.properties.frame',
    'swathIdentifier': '$.properties.swathIdentifier',
    'cloudCover': '$.properties.cloudCover',
    'snowCover': '$.properties.snowCover',
    'lowestLocation': '$.properties.lowestLocation',
    'highestLocation': '$.properties.highestLocation',
    'productVersion': '$.properties.productVersion',
    'productQualityStatus': '$.properties.productQualityStatus',
    'productQualityDegradationTag': '$.properties.productQualityDegradationTag',
    'processorName': '$.properties.processorName',
    'processingCenter': '$.properties.processingCenter',
    'creationDate': '$.properties.creationDate',
    'modificationDate': '$.properties.modificationDate',
    'processingDate': '$.properties.processingDate',
    'sensorMode': '$.properties.sensorMode',
    'archivingCenter': '$.properties.archivingCenter',
    'processingMode': '$.properties.processingMode',

    # OpenSearch Parameters for Acquistion Parameters Search (Table 6)
    'availabilityTime': '$.properties.availabilityTime',
    'acquisitionStation': '$.properties.acquisitionStation',
    'acquisitionSubType': '$.properties.acquisitionSubType',
    'startTimeFromAscendingNode': '$.properties.startTimeFromAscendingNode',
    'completionTimeFromAscendingNode': '$.properties.completionTimeFromAscendingNode',
    'illuminationAzimuthAngle': '$.properties.illuminationAzimuthAngle',
    'illuminationZenithAngle': '$.properties.illuminationZenithAngle',
    'illuminationElevationAngle': '$.properties.illuminationElevationAngle',
    'polarizationMode': '$.properties.polarizationMode',
    'polarisationChannels': '$.properties.polarisationChannels',
    'antennaLookDirection': '$.properties.antennaLookDirection',
    'minimumIncidenceAngle': '$.properties.minimumIncidenceAngle',
    'maximumIncidenceAngle': '$.properties.maximumIncidenceAngle',
    'dopplerFrequency': '$.properties.dopplerFrequency',
    'incidenceAngleVariation': '$.properties.incidenceAngleVariation',

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


def properties_from_xml(xml_as_text, mapping, empty_ns_prefix='ns'):
    """Extract properties from a provider xml result.

    :param xml_as_text: the representation of a provider result as xml
    :type xml_as_text: str or unicode
    :param mapping: a mapping between :class:`~eodag.api.product.EOProduct`'s metadata keys and the location of the
                    values of these properties in the xml representation, expressed as a
                    `xpath <https://www.w3schools.com/xml/xml_xpath.asp>`_
    :param empty_ns_prefix: the name to give to the default namespace of `xml_as_text`. This is a technical workaround
                            for the limitation of lxml not supporting empty namespace prefix (default: ns). The xpath
                            in `mapping` must use this value to be able to correctly reach empty-namespace prefixed
                            elements
    :type empty_ns_prefix: str or unicode
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
                value = root.xpath(
                    get_metadata_path(mapping[metadata]),
                    namespaces={
                        k or empty_ns_prefix: v for k, v in root.nsmap.items()
                    }
                )
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
