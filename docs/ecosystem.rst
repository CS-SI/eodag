.. ecosystem:

EODAG-related projects
========================

EODAG-cube
----------

Data access functionalities have been split to a separate project to avoid conflicts with
unneeded libraries when using only EODAG basic functionalities. EODAG-cube is available
on `github <https://github.com/CS-SI/eodag-cube>`__ and `pypi <https://pypi.org/project/eodag-cube>`__.

EODAG-labextension
------------------

Jupyterlab extension for searching and browsing remote sensed imagery directly from your notebook.

This extension is using the eodag library to efficiently search from various image providers.
It can transform search results to code cells into the active Python notebook to further process/visualize the dataset.

EODAG-labextension is available
on `github <https://github.com/CS-SI/eodag-labextension>`__ and `pypi <https://pypi.org/project/eodag-labextension>`__.

STAC-FastAPI-EODAG
------------------

EODAG backend for stac-fastapi, the FastAPI implementation of the STAC API spec

stac-fastapi-eodag combines the capabilities of EODAG and STAC FastAPI to provide a powerful, unified API for accessing
Earth observation data from various providers.

STAC-FastAPI-EODAG is available
on `github <https://github.com/CS-SI/stac-fastapi-eodag>`__ and `pypi <https://pypi.org/project/stac-fastapi-eodag>`__.

OpenTelemetry EODAG Instrumentation
-----------------------------------

This library provides automatic and manual instrumentation of EODAG.

auto-instrumentation using the opentelemetry-instrumentation package is also supported.

OpenTelemetry-EODAG-Instrumentation is available
on `github <https://github.com/CS-SI/opentelemetry-instrumentation-eodag>`__ and
`pypi <https://pypi.org/project/opentelemetry-instrumentation-eodag>`__.
