.. _eo_products_properties:

EO Products Properties
======================

EODAG exposes metadata for queryables based on [OGC OpenSearch Extension for Earth Observation](https://docs.ogc.org/is/13-026r9/13-026r9.html) for all providers that support it.
All of the parameters are string based. If a parameter requires an specific format it will be defined on the list below.

----------------------------

- **uid**: Unique identifier for the resource.
- **productType**: A string identifying the entry type (e.g., ER02_SAR_IM__0P, MER_RR__1P, SM_SLC__1S, GES_DISC_AIRH3STD_V005).
- **doi**: Digital Object Identifier identifying the product.
- **platform**: A string with the platform short name (e.g., Sentinel-1).
- **platformSerialIdentifier**: A string with the platform serial identifier.
- **instrument**: A string identifying the instrument (e.g., MERIS, AATSR, ASAR, HRVIR, SAR).
- **sensorType**: A string identifying the sensor type. Suggested values include: OPTICAL, RADAR, ALTIMETRIC, ATMOSPHERIC, LIMB.
- **compositeType**: Type of composite product expressed as the time period that the composite product covers (e.g., P10D for a 10-day composite).
- **processingLevel**: A string identifying the processing level applied to the entry.
- **orbitType**: A string identifying the platform orbit type (e.g., LEO, GEO).
- **spectralRange**: A string identifying the sensor spectral range (e.g., INFRARED, NEAR-INFRARED, UV, VISIBLE).
- **wavelengths**: A number, set, or interval requesting the sensor wavelengths in nanometers.
- **hasSecurityConstraints**: A string indicating if the resource has any security constraints. Possible values: TRUE, FALSE.
- **dissemination**: Information about the dissemination level of the resource.
- **title**: A name given to the resource.
- **topicCategory**: Main theme(s) of the dataset.
- **keyword**: Commonly used word(s) or formalized word(s) or phrase(s) used to describe the subject.
- **abstract**: A brief narrative summary of the resource.
- **resolution**: The spatial resolution of the resource.
- **organisationName**: Name of the organization responsible for the resource.
- **organisationRole**: Role of the organization (e.g., resourceProvider, custodian, owner, user, distributor, originator, pointOfContact, principalInvestigator, processor, publisher, author).
- **publicationDate**: Date when the resource was published.
- **lineage**: Information about the lineage of the resource.
- **useLimitation**: Constraints on the usage of the resource.
- **accessConstraint**: Restrictions and legal prerequisites for accessing the resource.
- **otherConstraint**: Other constraints related to the resource.
- **classification**: Security classification of the resource (e.g., unclassified, restricted, confidential, secret, topSecret).
- **language**: Language of the resource content.
- **specification**: Reference to the specification to which the resource conforms.
- **parentIdentifier**: A string identifying the parent of the entry in a hierarchy of resources.
- **productionStatus**: A string identifying the status of the entry (e.g., ARCHIVED, ACQUIRED, CANCELLED).
- **acquisitionType**: Used to distinguish at a high level the appropriateness of the acquisition for general use. Values: NOMINAL, CALIBRATION, OTHER.
- **orbitNumber**: A number, set, or interval requesting the acquisition orbit.
- **orbitDirection**: A string identifying the acquisition orbit direction. Possible values: ASCENDING, DESCENDING.
- **track**: A string identifying the orbit track.
- **frame**: A string identifying the orbit frame.
- **swathIdentifier**: Swath identifier (e.g., Envisat ASAR has 7 distinct swaths (I1, I2, I3...I7) that correspond to precise incidence angles for the sensor).
- **cloudCover**: A number, set, or interval of the cloud cover percentage (0–100). When searching using it, values equal or less will be returned.
- **snowCover**: A number, set, or interval of the snow cover percentage (0–100).
- **lowestLocation**: A number, set, or interval of the bottom height of the data layer (in meters).
- **highestLocation**: A number, set, or interval of the top height of the data layer (in meters).
- **productVersion**: Version of the product.
- **productQualityStatus**: Status of the product's quality.
- **productQualityDegradationTag**: Tag indicating any degradation in product quality.
- **processorName**: Name of the processor used to generate the product.
- **processingCenter**: Center responsible for processing the product.
- **creationDate**: Date when the product was created.
- **modificationDate**: Date when the product was last modified.
- **processingDate**: Date when the product was processed.
- **sensorMode**: Mode of the sensor during acquisition.
- **archivingCenter**: Center responsible for archiving the product.
- **processingMode**: Mode used during processing.
- **availabilityTime**: The time when the result became available (e.g., if post-processing or laboratory analysis is required, it might differ from the phenomenon time). Format: ISO 8601 dateTime.
- **acquisitionStation**: A string identifying the station used for the acquisition.
- **acquisitionSubType**: Acquisition sub-type.
- **startTimeFromAscendingNode**: Start time from the ascending node.
- **completionTimeFromAscendingNode**: Completion time from the ascending node.
- **illuminationAzimuthAngle**: Illumination azimuth angle during acquisition.
- **illuminationZenithAngle**: Illumination zenith angle during acquisition.
- **illuminationElevationAngle**: Illumination elevation angle during acquisition.
- **polarizationMode**: Mode of polarization, space-separated (i.e. VV, VV VH, etc).
- **polarizationChannels**: Channels used for polarization.
- **antennaLookDirection**: Direction in which the antenna was looking during acquisition.
- **minimumIncidenceAngle**: Minimum incidence angle during acquisition.
- **maximumIncidenceAngle**: Maximum incidence angle during acquisition.
- **dopplerFrequency**: Doppler frequency during acquisition.
- **incidenceAngleVariation**: Variation in incidence angle during acquisition.