.. module:: eodag.config

========
Settings
========

``EODAGSettings`` defines the global EODAG configuration parameters. Values can be provided directly when creating the
settings object or overridden with ``EODAG_``-prefixed environment variables. See
`Core configuration using environment variables <../getting_started_guide/configure.rst#core-configuration-using-environment-variables>`_
for detailled information on the supported environment variables.

.. autopydantic_settings:: EODAGSettings
	:settings-hide-paramlist:
	:exclude-members: __init__, warn_deprecated_settings, resolved_cfg_file, resolved_locations_cfg_file
