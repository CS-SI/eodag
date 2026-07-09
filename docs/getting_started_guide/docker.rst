.. _docker:

Docker quickstart
=================

EODAG container images are published on GitHub Container Registry at
``ghcr.io/cs-si/eodag``. Images are built for EODAG releases.

Pull and run an image
^^^^^^^^^^^^^^^^^^^^^

Replace ``<version>`` with the EODAG release tag you want to use:

.. code-block:: bash

   docker pull ghcr.io/cs-si/eodag:<version>
   docker run --rm ghcr.io/cs-si/eodag:<version> --help

The image entry point is the ``eodag`` command, so CLI arguments can be passed
directly after the image name:

.. code-block:: bash

   docker run --rm ghcr.io/cs-si/eodag:latest list

See :ref:`cli_user_guide` for the full list of available commands and options.

Use a persistent configuration directory
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The container runs as the ``eodag`` user and its home directory is
``/home/eodag``. To keep user configuration outside the container, mount a host
directory to the default EODAG configuration directory:

.. code-block:: bash

   mkdir -p "$HOME/.config/eodag"
   docker run --rm \
      -v "$HOME/.config/eodag:/home/eodag/.config/eodag" \
      ghcr.io/cs-si/eodag:latest list

This lets EODAG create or reuse the same ``eodag.yml`` configuration file
across container runs. See :ref:`configure` for the full configuration
reference.

Use a specific configuration file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If your configuration file is stored elsewhere, mount it in the container and
set ``EODAG_CFG_FILE``:

.. code-block:: bash

   docker run --rm \
      -v "$PWD/eodag.yml:/config/eodag.yml:ro" \
      -e EODAG_CFG_FILE=/config/eodag.yml \
      ghcr.io/cs-si/eodag:latest list

Provide credentials safely
^^^^^^^^^^^^^^^^^^^^^^^^^^

Do not bake credentials into a custom image. Prefer one of the runtime
configuration methods documented in :ref:`configure`:

* Mount a user configuration file or directory, as shown above.
* Pass provider credentials through environment variables, using the
  ``EODAG__<PROVIDER>__AUTH__CREDENTIALS__<KEY>`` or
  ``EODAG__<PROVIDER>__API__CREDENTIALS__<KEY>`` naming patterns.

For example, to pass a provider username and password at runtime:

.. code-block:: bash

   docker run --rm \
      -e EODAG__CREODIAS__AUTH__CREDENTIALS__USERNAME="$CREODIAS_USERNAME" \
      -e EODAG__CREODIAS__AUTH__CREDENTIALS__PASSWORD="$CREODIAS_PASSWORD" \
      ghcr.io/cs-si/eodag:latest list

Persist downloaded products
^^^^^^^^^^^^^^^^^^^^^^^^^^^

When downloading products, mount a host output directory and point the provider
download configuration to it:

.. code-block:: bash

   mkdir -p "$PWD/eodag-downloads"
   docker run --rm \
      -v "$PWD:/work" \
      -v "$PWD/eodag-downloads:/data" \
      -v "$HOME/.config/eodag:/home/eodag/.config/eodag" \
      -e EODAG__CREODIAS__DOWNLOAD__OUTPUT_DIR=/data \
      ghcr.io/cs-si/eodag:latest download \
         --search-results /work/search_results.geojson

If ``search_results.geojson`` is in another host directory, mount that
directory and use the mounted path in the command.
