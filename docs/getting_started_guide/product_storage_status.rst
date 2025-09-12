.. _product_storage_status:

Product storage status
======================

Providers make available a huge number of EO products. This results in the need of immense data
storage. In order to cope with this growing need, some providers make the most recent products
available immediately, and the oldest ones available after being ordered.

The storage status has been standardized for all providers in the parameter ``order:status``, and
its different values mapped to these 3 unique status:

* `succeeded`: the product is available for download (immediately);
* `ordered`: the product has been ordered and will be `succeeded` soon;
* `orderable`: the product is not available for download, but can eventually be ordered.

``eodag`` is able to order `OFFLINE` products and retry downloading them for a while. This
is described in more details in the `Python API user guide <../notebooks/api_user_guide/7_download.ipynb>`_.
