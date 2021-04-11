.. _add_provider:

Add a Provider
==============

For developers, there are 2 ways for adding support for a new provider:

* By configuring existing plugins: a provider is an instance of already
  implemented plugins (search, download). This approach only involves knowing how
  to write ``yaml`` documents.

* By developing new plugins (most of the time it will be search plugins)
  and configuring instances of these plugins (see :ref:`creating_plugins`).

Parameters mapping
^^^^^^^^^^^^^^^^^^

EODAG maps each provider specific metadata parameters to a common model using
`OGC OpenSearch Extension for Earth Observation <http://docs.opengeospatial.org/is/13-026r9/13-026r9.html>`_.

The list of parameters mapped for the available providers can be found in this
`CSV file <_static/params_mapping.csv>`_.


Providers pre-configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^

All the providers are pre-configured in ``eodag`` in a YAML file.
Click on the link below to display its full content.

.. raw:: html

   <details>
   <summary><a>providers.yml</a></summary>

.. include:: ../eodag/resources/providers.yml
   :start-line: 17
   :code: yaml

.. raw:: html

   </details>
