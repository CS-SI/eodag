# Template Extension Specification

- **Title:** Template
- **Identifier:** <https://raw.githubusercontent.com/CS-SI/eodag/master/stac-extensions/oseo/json-schema/schema.json>
- **Field Name Prefix:** oseo
- **Scope:** Item, Collection
- **Extension [Maturity Classification](https://github.com/radiantearth/stac-spec/tree/master/extensions/README.md#extension-maturity):** Proposal
- **Owner**:

This document explains the Template Extension to the [SpatioTemporal Asset Catalog](https://github.com/radiantearth/stac-spec) (STAC) specification.
This is the place to add a short introduction.

- Examples:
  - [Item example](examples/item.json): Shows the basic usage of the extension in a STAC Item
  - [Collection example](examples/collection.json): Shows the basic usage of the extension in a STAC Collection
- [JSON Schema](json-schema/schema.json)
- [Changelog](./CHANGELOG.md)

## Fields

The fields in the table below can be used in these parts of STAC documents:

- [ ] Catalogs
- [x] Collections
- [x] Item Properties (incl. Summaries in Collections)
- [ ] Assets (for both Collections and Items, incl. Item Asset Definitions in Collections)
- [ ] Links

| Field Name           | Type                      | Description                                  |
| -------------------- | ------------------------- | -------------------------------------------- |
| oseo:uid   | string                    | Uid |
| oseo:sensor_type   | string                    | Sensor Type |
| oseo:composite_type   | string                    | Composite Type |
| oseo:orbit_type   | string                    | Orbit Type |
| oseo:spectral_range   | string                    | Spectral Range |
| oseo:wavelengths   | string                    | Wavelengths |
| oseo:has_security_constraints   | string                    | Has Security Constraints |
| oseo:dissemination   | string                    | Dissemination |
| oseo:topic_category   | string                    | Topic Category |
| oseo:keyword         | string | Keyword |
| oseo:organisation_name         | string | Organisation Name |
| oseo:organisation_role         | string | Organisation Role |
| oseo:lineage         | string | Lineage |
| oseo:use_limitation         | string | Use Limitation |
| oseo:access_constraint         | string | Access Constraint |
| oseo:other_constraint         | string | Other Constraint |
| oseo:classification         | string | Classification |
| oseo:language         | string | Language |
| oseo:specification         | string | Specification |
| oseo:parent_identifier         | string | Parent Identifier |
| oseo:production_status         | string | Production Status |
| oseo:acquisition_type         | string | Acquisition Type |
| oseo:orbit_number         | string | Orbit Number |
| oseo:track         | string | Track |
| oseo:frame         | string | Frame |
| oseo:swath_identifier         | string | Swath Identifier |
| oseo:snow_cover         | string | Snow Cover |
| oseo:lowest_location         | string | Lowest Location |
| oseo:highest_location         | string | Highest Location |
| oseo:product_quality_status         | string | Product Quality Status |
| oseo:product_quality_degradation_tag         | string | Product Quality Degradation Tag |
| oseo:processor_name         | string | Processor Name |
| oseo:processing_center         | string | Processing Center |
| oseo:processing_date         | string | Processing Date |
| oseo:archiving_center         | string | Archiving Center |
| oseo:processing_mode         | string | Processing Mode |
| oseo:availability_time         | string | Availability Time |
| oseo:acquisition_station         | string | Acquisition Station |
| oseo:acquisition_sub_type         | string | Acquisition Sub Type |
| oseo:illumination_zenith_angle         | string | Illumination Zenith Angle |
| oseo:polarization_mode         | string | Polarization Mode |
| oseo:antenna_look_direction         | string | Antenna Look Direction |
| oseo:minimum_incidence_angle         | string | Minimum Incidence Angle |
| oseo:maximum_incidence_angle         | string | Maximum Incidence Angle |
| oseo:incidence_angle_variation         | string | Incidence Angle Variation |

## Contributing

All contributions are subject to the
[STAC Specification Code of Conduct](https://github.com/radiantearth/stac-spec/blob/master/CODE_OF_CONDUCT.md).
For contributions, please follow the
[STAC specification contributing guide](https://github.com/radiantearth/stac-spec/blob/master/CONTRIBUTING.md) Instructions
for running tests are copied here for convenience.
