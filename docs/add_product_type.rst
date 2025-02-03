.. _add_product_type:

Add a product type
==================

Add product type definition
^^^^^^^^^^^^^^^^^^^^^^^^^^^

To add a new product type to EODAG, you must add an entry to the file ``eodag/resources/product_types.yml``. Here is an
example:

.. code-block:: yaml

    CBERS4_AWFI_L2:
      abstract: |
        China-Brazil Earth Resources Satellite, CBERS-4 AWFI camera Level-2 product. System corrected images, expect
        some translation error.
      instrument: AWFI
      platform: CBERS
      platformSerialIdentifier: CBERS-4
      processingLevel: L2
      keywords: AWFI,CBERS,CBERS-4,L2
      sensorType: OPTICAL
      license: other
      missionStartDate: "2014-12-07T00:00:00Z"
      title: CBERS-4 AWFI Level-2

The first line ``CBERS4_AWFI_L2:`` is a YAML key corresponding to the name by
which the product will be referred to within EODAG. Note the use of uppercase
and underscores to separate words. This name will be used when searching for
products of the corresponding type.

The following lines need to be indented because they make a dictionary of
configuration information for the product type we are defining. Each bit of
information can usually be found on the provider's catalog. Note how the value
used for the ``keywords`` entry brings together values from other entries such
as ``instrument``, ``processingLevel``, ``platform``, etc.

Add product type to a provider
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the file ``eodag/resources/providers.yml``, add the product-type to the ``products``
entry of a provider:

.. code-block:: yaml

    ---
    !provider # MARK: aws_eos
      name: aws_eos
      # ...
      products:
        # ...
        CBERS4_AWFI_L2:
          # ...
          # product-type configuration comes here
          # ...

Then for each product-type listed under the ``products`` entry, you may
specify default parameters that will be used when searching for products of this
product type:

.. code-block:: yaml

    ---
    !provider
      name: aws_eos
      # ...
      products:
        # ...
        CBERS4_AWFI_L2:
          instrument: AWFI
          collection: cbers4
          processingLevel: 2

With the example above, when searching for products of the type ``CBERS4_AWFI_L2``, the
search will be performed by default as if we had specified the instrument ``AWFI``, the
collection ``cbers4`` and the processingLevel ``2``.
Each of those parameters can be overridden when performing an actual search. Note that
parameters have to be named following the common model used in EODAG (see
`Parameters mapping <params_mapping.rst>`_). Part of the provider search metadata
mapping can also be overridden per product-type, by adding a ``metadata_mapping``
section to the product type definition:

.. code-block:: yaml

    ---
    !provider # MARK: aws_eos
      name: aws_eos
      # ...
      products:
        # ...
        CBERS4_AWFI_L2:
          # ... default eodag search parameters
          metadata_mapping_from_product: CBERS4_PAN10M_L2
          metadata_mapping:
            previewBaseName: '{$.sceneID#replace_str("_L4","")}'
            thumbnail: 'https://s3.amazonaws.com/cbers-meta-pds/{awsPath}/{previewBaseName}_small.jpeg'

In the example above, we can see that the metadata mapping for the product type
in the context of this provider can be specified in two ways:

- ``metadata_mapping_from_product`` will include an existing metadata mapping
  from another product
- ``metadata_mapping`` will contain a metadata mapping as documented in the
  `section on parameters mapping <params_mapping.rst>`_
