.. _overview:

Why EODAG?
==========

Nowadays, we observe a rise in publicly accessible Earth Observation (EO) data.
Together with it, there is more and more EO data providers, each potentially having
a different data access policy. This difference is visible at various levels:
in the data discovery (CSW, OpenSearch more or less custom, etc.), in the
product access (object storage, downloads, direct file system access, etc.), in
the storage structure and in the authentication mechanisms (OAUTH, JWT, basic
auth,...). All these different technologies add a knowledge overhead on a user
(end-user or application developer) wishing to take advantage of these
data. EODAG was designed to solve this problem.

EODAG (Earth Observation Data Access Gateway) is a command line tool and a
plugin-oriented Python framework for searching, aggregating results and
downloading remote sensed images while offering a unified API for data access
regardless of the data provider. The EODAG SDK is structured around three
functions:

* List product types: list of supported products and their description
* Search products (by product type) : searches products according to the
  search criteria provided
* Download products : download product “as is"

EODAG is developed in Python. It is structured according to a modular plugin
architecture, easily extensible and able to integrate new data providers. Three
types of plugins compose the tool:

* Catalog search plugins, responsible for searching data (OpenSearch, CSW, ...),
  building paths, retrieving quicklook, combining results
* Download plugins, allowing to download and retrieve data locally (via FTP, HTTP, ..),
  always with the same directory organization
* Authentication plugins, which are used to authenticate the user on the
  external services used (JSON Token, Basic Auth, OAUTH, ...).


EODAG-cube
----------

Data access functionalities have been split to a separate project to avoid conflicts with
unneeded libraries when using only EODAG basic functionalities. EODAG-cube is available
on `github <https://github.com/CS-SI/eodag-cube>`_ and `pypi <https://pypi.org/project/eodag-cube>`_.
