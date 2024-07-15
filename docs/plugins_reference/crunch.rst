.. module:: eodag.plugins.crunch

==============
Crunch Plugins
==============

Crunch plugins must inherit the following class and implement :meth:`proceed`:

.. autoclass:: eodag.plugins.crunch.base.Crunch
   :members:

This table lists all the crunch plugins currently available:

.. autosummary::
   :toctree: generated/

   filter_date.FilterDate
   filter_latest_intersect.FilterLatestIntersect
   filter_latest_tpl_name.FilterLatestByName
   filter_overlap.FilterOverlap
   filter_property.FilterProperty

The signature of each plugin's :meth:`proceed` method is displayed below, it may contain information useful to execute the cruncher:

.. automethod:: eodag.plugins.crunch.filter_date.FilterDate.proceed
.. automethod:: eodag.plugins.crunch.filter_latest_intersect.FilterLatestIntersect.proceed
.. automethod:: eodag.plugins.crunch.filter_latest_tpl_name.FilterLatestByName.proceed
.. automethod:: eodag.plugins.crunch.filter_overlap.FilterOverlap.proceed
.. automethod:: eodag.plugins.crunch.filter_property.FilterProperty.proceed
