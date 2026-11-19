.. _product_storage_status:

Product storage status
======================

Providers make available a huge number of EO products. This results in the need of immense data
storage. In order to cope with this growing need, some providers make the most recent products
available immediately, and the oldest ones available after being ordered.

Storage status is stored separately on each asset in ``order:status``, not in
product properties. Provider values are mapped to four standard statuses:

* ``succeeded``: the asset is available for download immediately;
* ``ordered``: the asset has been ordered and is awaiting availability;
* ``orderable``: the asset is not yet available but can be ordered;
* ``failed``: the provider rejected the order or its completed result is unusable.

An asset without ``order:status`` is treated as online. Use
``product.assets[asset_key].get("order:status", "succeeded")`` to read its status.
``SearchResult.filter_online()`` keeps only products whose assets are all online.

``eodag`` can order selected offline assets and retry downloading them for a while.
Failed orders are not submitted again automatically; search again before retrying.
Authentication, quota, timeout and transient request errors do not mark an order
failed. See the `Python API user guide <../notebooks/api_user_guide/7_download.ipynb>`_
for ordering and download examples.
