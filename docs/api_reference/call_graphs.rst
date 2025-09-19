.. _call_graphs:

Call graphs
===========

This section provides visual representations of the call graphs for the EODAG library.
Call graphs are useful for understanding the relationships and interactions between
different components of the codebase. They can help developers and contributors
navigate the code more effectively and identify dependencies or areas for improvement.

* `Main API calls graph <../_static/eodag_main_calls_graph.svg>`_
* `Advanced calls graph (main API + search and authentication plugins) <../_static/eodag_advanced_calls_graph.svg>`_

These call graphs are generated using *graphviz* and `Pyan3 <https://github.com/davidfraser/pyan>`_

.. code-block:: bash

   cd eodag_working_copy/eodag
   # main api
   pyan3 `find ./api -name "*.py"` \
   --uses --colored --grouped-alt --nested-groups --annotated --dot --dot-rankdir=LR \
   >/tmp/eodag_main_calls_graph.dot
   dot -Tsvg /tmp/eodag_main_calls_graph.dot >../docs/_static/eodag_main_calls_graph.svg
   # advanced api
   pyan3 `find ./api ./plugins/search/ ./plugins/authentication/ -name "*.py"` \
   --uses --colored --grouped-alt --nested-groups --annotated --dot --dot-rankdir=LR \
   >/tmp/eodag_advanced_calls_graph.dot
   dot -Tsvg /tmp/eodag_advanced_calls_graph.dot >../docs/_static/eodag_advanced_calls_graph.svg
