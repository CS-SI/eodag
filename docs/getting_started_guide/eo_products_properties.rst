.. _eo_products_properties:

EO Products Properties
======================

EODAG maps each provider's specific metadata parameters to a common model using
`OGC OpenSearch Extension for Earth Observation <http://docs.opengeospatial.org/is/13-026r9/13-026r9.html>`_.
Extra parameters that have no equivalent in this model are mapped as they are.
For more information on parameters mapping, please see `Contributing / Parameters mapping <../params_mapping.rst>`_.
Here is a list of these common mapped properties:
----------------------------

* **id**: Unique identifier for the resource, harmonized across providers.
* **uid**: Unique identifier for the resource, using provider specific formatting.
* **tileIdentifier**: Tile identifier from Sentinel 2 MGRS tiling grid (``31TCJ``, ``17FQE``, ...)
* **productType**: A string identifying the entry type (e.g., ``CBERS4_MUX_L2``, ``LANDSAT_C2L2_SR``, etc).
* **doi**: Digital Object Identifier identifying the product.
* **platform**: A string with the platform short name (e.g., Sentinel-1).
* **platformSerialIdentifier**: A string with the platform serial identifier.
* **instrument**: A string identifying the instrument (e.g., MERIS, AATSR, ASAR, HRVIR, SAR).
* **sensorType**: A string identifying the sensor type. Suggested values include: OPTICAL, RADAR, ALTIMETRIC, ATMOSPHERIC, LIMB.
* **compositeType**: Type of composite product expressed as the time period that the composite product covers (e.g., P10D for a 10-day composite).
* **processingLevel**: A string identifying the processing level applied to the entry.
* **orbitType**: A string identifying the platform orbit type (e.g., LEO, GEO).
* **spectralRange**: A string identifying the sensor spectral range (e.g., INFRARED, NEAR-INFRARED, UV, VISIBLE).
* **wavelengths**: A number, set, or interval requesting the sensor wavelengths in nanometers.
* **hasSecurityConstraints**: A string indicating if the resource has any security constraints.
* **dissemination**: Information about the dissemination level of the resource.
* **title**: A name given to the resource.
* **topicCategory**: Main theme(s) of the dataset.
* **keyword**: Commonly used word(s) or formalized word(s) or phrase(s) used to describe the subject.
* **abstract**: A brief narrative summary of the resource.
* **resolution**: The spatial resolution of the resource.
* **organisationName**: Name of the organization responsible for the resource.
* **organisationRole**: Role of the organization (e.g., resourceProvider, custodian, owner, user, distributor, originator, pointOfContact, principalInvestigator, processor, publisher, author).
* **publicationDate**: Date when the resource was published.
* **lineage**: Information about the lineage of the resource.
* **useLimitation**: Constraints on the usage of the resource.
* **accessConstraint**: Restrictions and legal prerequisites for accessing the resource.
* **otherConstraint**: Other constraints related to the resource.
* **classification**: Security classification of the resource (e.g., unclassified, restricted, confidential, secret, topSecret).
* **language**: Language of the resource content.
* **specification**: Reference to the specification to which the resource conforms.
* **parentIdentifier**: A string identifying the parent of the entry in a hierarchy of resources.
* **acquisitionType**: Used to distinguish at a high level the appropriateness of the acquisition for general use.
* **orbitNumber**: A number, set, or interval requesting the acquisition orbit.
* **orbitDirection**: A string identifying the acquisition orbit direction.
* **track**: A string identifying the orbit track.
* **frame**: A string identifying the orbit frame.
* **swathIdentifier**: Swath identifier (e.g., Envisat ASAR has 7 distinct swaths (I1, I2, I3...I7) that correspond to precise incidence angles for the sensor).
* **cloudCover**: A number, set, or interval of the cloud cover percentage (0–100). When searching using it, values equal or less will be returned.
* **snowCover**: A number, set, or interval of the snow cover percentage (0–100).
* **lowestLocation**: A number, set, or interval of the bottom height of the data layer (in meters).
* **highestLocation**: A number, set, or interval of the top height of the data layer (in meters).
* **productVersion**: Version of the product.
* **productQualityStatus**: Status of the product's quality.
* **productQualityDegradationTag**: Tag indicating any degradation in product quality.
* **processorName**: Name of the processor used to generate the product.
* **processingCenter**: Center responsible for processing the product.
* **creationDate**: Date when the product was created.
* **modificationDate**: Date when the product was last modified.
* **processingDate**: Date when the product was processed.
* **sensorMode**: Mode of the sensor during acquisition.
* **archivingCenter**: Center responsible for archiving the product.
* **processingMode**: Mode used during processing.
* **availabilityTime**: The time when the result became available (e.g., if post-processing or laboratory analysis is required, it might differ from the phenomenon time). Format: ISO 8601 dateTime.
* **acquisitionStation**: A string identifying the station used for the acquisition.
* **acquisitionSubType**: Acquisition sub-type.
* **startTimeFromAscendingNode**: Start time from the ascending node.
* **completionTimeFromAscendingNode**: Completion time from the ascending node.
* **illuminationAzimuthAngle**: Illumination azimuth angle during acquisition.
* **illuminationZenithAngle**: Illumination zenith angle during acquisition.
* **illuminationElevationAngle**: Illumination elevation angle during acquisition.
* **polarizationMode**: Mode of polarization.
* **polarizationChannels**: Channels used for polarization, space-separated (i.e. ``VV``, ``VV VH``, etc).
* **antennaLookDirection**: Direction in which the antenna was looking during acquisition.
* **minimumIncidenceAngle**: Minimum incidence angle during acquisition.
* **maximumIncidenceAngle**: Maximum incidence angle during acquisition.
* **dopplerFrequency**: Doppler frequency during acquisition.
* **incidenceAngleVariation**: Variation in incidence angle during acquisition.
* **storageStatus**: Storage status on the provider. One of the following strings:

  * ONLINE: the product is available for download (immediately);
  * STAGING: the product has been ordered and will be `ONLINE` soon;
  * OFFLINE: the product is not available for download, but can eventually be ordered.

    * ``eodag`` is able to order `OFFLINE` products and retry downloading them for a while. This is described in more details in the `Python API user guide <../notebooks/api_user_guide/8_download.ipynb>`_.
