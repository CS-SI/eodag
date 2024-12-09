.. _add_product_type:

How to add a new product type to EODag?
=======================================


To add a new product type to EODag, you need to add an entry to the file `eodag/resources/product_types.yml`. Here is an example:

.. code-block::

    CBERS4_AWFI_L2:
      abstract: |
        China-Brazil Earth Resources Satellite, CBERS-4 AWFI camera Level-2 product. System corrected images, expect some
        translation error.
      instrument: AWFI
      platform: CBERS
      platformSerialIdentifier: CBERS-4
      processingLevel: L2
      keywords: AWFI,CBERS,CBERS-4,L2
      sensorType: OPTICAL
      license: proprietary
      missionStartDate: "2014-12-07T00:00:00Z"
      title: CBERS-4 AWFI Level-2

The first line `CBERS4_AWFI_L2:` is a YAML key corresponding to the name by which the product will be referred to within EODag. Note the use of uppercase and underscores to separate words. This name will be used when searching for products of the corresponging type.

The following lines need to be indented because they make a dictionnary of configuration information for the product type we are defining. Each bit of information can usually be found on the provider's catalogue. Note that the value used for `keywords` entry puts together values from other entries such as `instrument`, `processingLevel`, `platform`, etc.
