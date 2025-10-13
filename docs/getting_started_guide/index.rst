.. _getting_started:

Getting Started
===============

Welcome to ``eodag``

This guide will introduce you step by step to the main features of ``eodag``,
from installation to searching and downloading your first products.

The journey is structured so you can:

#. Install and configure ``eodag`` quickly.
#. Discover the **featured providers** available and learn how to register.
#. Explore the different **collections** and their characteristics.
#. Understand product storage status and ecosystem integration.

Each section below gives you a focused entry point with explanations and examples.

.. |icon-info| raw:: html

   <svg class="w-6 h-6 text-gray-800 dark:text-white" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" style="vertical-align:middle; margin-right:6px;">
      <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 11h2v5m-2 0h4m-2.592-8.5h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"/>
   </svg>


.. |icon-star| raw:: html

   <svg class="w-6 h-6 text-gray-800 dark:text-white" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" style="vertical-align:middle; margin-right:6px;">
      <path stroke="currentColor" stroke-width="2" d="M11.083 5.104c.35-.8 1.485-.8 1.834 0l1.752 4.022a1 1 0 0 0 .84.597l4.463.342c.9.069 1.255 1.2.556 1.771l-3.33 2.723a1 1 0 0 0-.337 1.016l1.03 4.119c.214.858-.71 1.552-1.474 1.106l-3.913-2.281a1 1 0 0 0-1.008 0L7.583 20.8c-.764.446-1.688-.248-1.474-1.106l1.03-4.119A1 1 0 0 0 6.8 14.56l-3.33-2.723c-.698-.571-.342-1.702.557-1.771l4.462-.342a1 1 0 0 0 .84-.597l1.753-4.022Z"/>
   </svg>


.. |icon-download| raw:: html

   <svg class="w-6 h-6 text-gray-800 dark:text-white" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" style="vertical-align:middle; margin-right:6px;">
      <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 13V4M7 14H5a1 1 0 0 0-1 1v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4a1 1 0 0 0-1-1h-2m-1-5-4 5-4-5m9 8h.01"/>
   </svg>


.. |icon-layers| raw:: html

   <svg class="w-6 h-6 text-gray-800 dark:text-white" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" style="vertical-align:middle; margin-right:6px;">
      <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5.005 11.19V12l6.998 4.042L19 12v-.81M5 16.15v.81L11.997 21l6.998-4.042v-.81M12.003 3 5.005 7.042l6.998 4.042L19 7.042 12.003 3Z"/>
   </svg>


.. |icon-database| raw:: html

   <svg class="w-6 h-6 text-gray-800 dark:text-white" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" style="vertical-align:middle; margin-right:6px;">
      <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 6c0 1.657-3.134 3-7 3S5 7.657 5 6m14 0c0-1.657-3.134-3-7-3S5 4.343 5 6m14 0v6M5 6v6m0 0c0 1.657 3.134 3 7 3s7-1.343 7-3M5 12v6c0 1.657 3.134 3 7 3s7-1.343 7-3v-6"/>
   </svg>


.. |icon-gear| raw:: html

   <svg class="w-6 h-6 text-gray-800 dark:text-white" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" style="vertical-align:middle; margin-right:6px;" >
      <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 13v-2a1 1 0 0 0-1-1h-.757l-.707-1.707.535-.536a1 1 0 0 0 0-1.414l-1.414-1.414a1 1 0 0 0-1.414 0l-.536.535L14 4.757V4a1 1 0 0 0-1-1h-2a1 1 0 0 0-1 1v.757l-1.707.707-.536-.535a1 1 0 0 0-1.414 0L4.929 6.343a1 1 0 0 0 0 1.414l.536.536L4.757 10H4a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1h.757l.707 1.707-.535.536a1 1 0 0 0 0 1.414l1.414 1.414a1 1 0 0 0 1.414 0l.536-.535 1.707.707V20a1 1 0 0 0 1 1h2a1 1 0 0 0 1-1v-.757l1.707-.708.536.536a1 1 0 0 0 1.414 0l1.414-1.414a1 1 0 0 0 0-1.414l-.535-.536.707-1.707H20a1 1 0 0 0 1-1Z"/>
      <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"/>
   </svg>

.. toctree::
   :hidden:
   :maxdepth: 2

   overview
   features_overview
   install
   collections
   product_storage_status
   configure

.. grid:: 1 2 2 3
   :gutter: 4

   .. grid-item-card:: |icon-info| Why EODAG ?
      :link: overview
      :link-type: doc
      :text-align: center

      Discover the key features and benefits of using ``eodag`` for Earth Observation data access.

   .. grid-item-card:: |icon-star| Features overview
      :link: features_overview
      :link-type: doc
      :text-align: center

      Get an overview of the main features offered by ``eodag`` for working with EO data.

   .. grid-item-card:: |icon-download| Installation
      :link: install
      :link-type: doc
      :text-align: center

      Get ``eodag`` installed and ready to use in minutes.

   .. grid-item-card:: |icon-layers| Collections
      :link: collections
      :link-type: doc
      :text-align: center

      Explore the EO collections available through providers.

   .. grid-item-card:: |icon-database| Product storage status
      :link: product_storage_status
      :link-type: doc
      :text-align: center

      Understand where products are stored and their availability.

   .. grid-item-card:: |icon-gear| Configuration
      :link: configure
      :link-type: doc
      :text-align: center

      Learn how to configure providers, priorities, and logging.
