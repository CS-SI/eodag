.. _recording:

EODAG recording
###############

EODAG provides a :external+pytest:doc:`pytest plugin <how-to/plugins>` to help test your
EODAG based applications without actually contacting any EO data provider.

This plugin has been strongly inspired by :external+vcrpy:std:doc:`VCR.py <index>` and
`pytest-recording <https://pypi.org/project/pytest-recording/>`_ which it shares the
rationale with:

- The ability to work offline,
- Completely deterministic tests,
- Increased test execution speed.


Unlike VCR.py, ``eodag_recording`` doesn't record HTTP requests and responses, but those
of :func:`EODataAccessGateway.search() <eodag.api.core.EODataAccessGateway.search()>`
and :func:`EODataAccessGateway.download()
<eodag.api.core.EODataAccessGateway.download()>`.

This alleviates considerably all issues related to token anonymization, or to the
internal stability of the exact HTTP requests issued by EODAG.

TL;DR
=====

- Annotate your tests with ``@pytest.mark.eodag_record``.
- Execute them once with ``pytest --eodag-record-mode=all -p
  eodag.utils.recording.pytest_integration``

  This will create a :class:`replay cassette <eodag.utils.recording.cassette.Cassette>`
  with all the necessary information from actual data obtained from an EO data provider.
- Execute them as many times as you wish with ``pytest --eodag-record-mode=none
  -p eodag.utils.recording.pytest_integration``

  The EO data will be replied from previously recorded cassettes. No network request
  happens.

.. _recording-preparation:

Preparation
=============

In order to be able to use this :external+pytest:doc:`pytest plugin <how-to/plugins>`,
you will need to explicitly tell you want to use it.

Either:

* pass ``-p eodag.utils.recording.pytest_integration`` to :external+pytest:ref:`pytest
  <command-line-flags>`,
* or add the following to your :program:`pytest` configuration options in your project
  :file:`pyproject.toml`.

    .. code:: toml

        [tool.pytest.ini_options]
        addopts = "-p eodag.utils.recording.pytest_integration"


Test execution
==============

.. option:: --eodag-record-mode={none,once,all,new_episodes}

   Once registered, ``eodag_recording`` will add ``--eodag-record-mode`` to
   :external+pytest:ref:`pytest command line <command-line-flags>` to select the
   :class:`recording mode <eodag.utils.recording.recorder.RecordMode>`.

   This option supersedes
   :func:`eodag.utils.recording.pytest_integration.eodag_record_mode` fixture.

   Mode priority is as follows: CLI > marker > fixture ``eodag_record_mode`` > ``none``.


1. Record new cassettes
-----------------------
Tests need to be executed once to prepare the cassettes that will be replayed.
During this first execution, HTTP requests will be issued to EO data providers.

Several :class:`recording modes <eodag.utils.recording.recorder.RecordMode>` permit this
preparation: ``all``, ``once`` and ``new_episodes``.

For instance (expecting :external+pytest:confval:`addopts` has been set):

.. code:: bash

   pytest --eodag-record-mode=once

.. note:: Valid credentials are required for this use case.
.. note:: A cassette will be written only and only if its test succeeds.


2. Replay existing cassettes
----------------------------
Once cassettes are created, make sure they are available in your testing environment
like your project CI, and use them with one of the :class:`replay modes
<eodag.utils.recording.recorder.RecordMode>`: ``none``, ``once`` or ``new_episodes``.

For instance (expecting :external+pytest:confval:`addopts` has been set):

.. code:: bash

   pytest --eodag-record-mode=none

.. note:: We highly recommend ``none`` for automated test on CI side.

.. note:: No credential is required for this use case.

.. note::
        No context is updated when replaying. This is very similar to pure function
        calls: a same replay can be repeated endlessly.


Write tests
============

Annotations
-----------

You can annotate tests where you use EODAG with :func:`@pytest.mark.eodag_record
<eodag.utils.recording.pytest_integration.eodag_record>`, or the alias
:func:`@eodag_record <eodag.utils.recording.pytest_integration.eodag_record>`:

.. code:: python

    import pytest
    from eodag.utils.recording.pytest_integration import eodag_record

    @eodag_record()
    def test_one(): ...
        # Here the cassette name will be deduced from the name of the test.

    @pytest.mark.eodag_record(cassettes="common.yaml", record_mode="once")
    def test_two(): ...
        # We choose the actual name of our cassette.
        # We override the record mode: while possible, this is not recommanded.

    @eodag_record(cassettes=["a.yaml", "b.yaml"], write_to="b.yaml")
    def test_three(): ...
        # - We choose which cassettes will be used,
        # - But the test will fill only one, "a" cassette will always be in
        #   replay mode: it is expected to be filled in another test executed
        #   beforehand.
        #   Warning: Using correctly this feature can be tricky.

    @pytest.mark.eodag_record("c.yaml", archive_dir="there/")
    def test_four(): ...
        # We choose the actual name of our cassette.
        # We choose where the EOProducts will be actually stored to in real
        # modes, and read from in replay modes.

    def test_five(eodag_recorder): ...     # fixture: plugin defaults


Configuration hooks
-------------------

``eodag_recording`` actual behaviour can be configured through the following hooks:

- :func:`eodag.utils.recording.pytest_integration.eodag_cassette_name` that dictates
  default :class:`cassette <eodag.utils.eodag_recording.cassette.Cassette>` name
  generation from (py)test names.

- :func:`eodag.utils.recording.pytest_integration.eodag_cassette_dir` that tells where
  :class:`cassettes <eodag.utils.eodag_recording.cassette.Cassette>` are stored.

- :func:`eodag.utils.recording.pytest_integration.eodag_archive_dir` that tells where
  EOProducts are actually stored.

- :func:`eodag.utils.recording.pytest_integration.eodag_record_mode` that tells the
  default :class:`replay modes <eodag.utils.recording.recorder.RecordMode>` when
  :option:`--eodag-record-mode` is not set.


Design Choices & Limitations
============================

- Currently, only the following methods are supported:

  - :func:`EODataAccessGateway.search() <eodag.api.core.EODataAccessGateway.search()>`,
  - :func:`EODataAccessGateway.search_all() <eodag.api.core.EODataAccessGateway.search_all()>`,
  - and :func:`EODataAccessGateway.download() <eodag.api.core.EODataAccessGateway.download()>`.

  Neither:

  - :func:`EODataAccessGateway.download_all() <eodag.api.core.EODataAccessGateway.download_all()>`,
  - nor :func:`EOProduct.download() <eodag.api.product._product.EOProduct.download()>`

  are supported (yet).

- :class:`Cassettes <eodag.utils.recording.cassette.Cassette>` are serialized in YAML to
  ease their visualization and their edition.


- :class:`Cassettes <eodag.utils.recording.cassette.Cassette>` will be written only and
  only if theirs tests succeed.

- :class:`Cassettes <eodag.utils.recording.cassette.Cassette>` associate `keys` to EODAG
  results.

  Each key needs to be unique: :class:`eodag.utils.eodag_recording.DuplicateKeyError`
  will be raised otherwise.

  The keys are determined:

  - By the exact parameters passed to :func:`search()
    <eodag.api.core.EODataAccessGateway.search()>` methods. Meaning, that ``search(a=1,
    page=1)`` and ``search(a=1)`` requests will be identified by two distinct keys.
    To ensure reproducibility, the parameters will be sorted in the YAML cassettes.

    .. note::

        The page number is considered like any other search criteria.
        Recording searches with multiple pages of 10 items par page, and replaying with
        42 items per page is not supported.

  - By the pair `{product-id, provider}` in the case of :func:`download()
    <eodag.api.core.EODataAccessGateway.download()>` method

- No actual downloading from a search cassette is expected. The typical scenario is for
  a ``all`` mode to actually communicate with an EO data provider, and record
  everything. Actually downloading from a replayed search is not supported.

- Internally the plugin creates symlinks, from the officially requested ``output``
  download directory, to :class:`cached EOProducts
  <eodag.api.product._product.EOProduct>` actually downloaded in the :func:`archive_dir
  <eodag.utils.recording.pytest_integration.eodag_archive_dir>`.

  .. warning:: Your program shall not expect files that it can move around freely.
  .. warning::

    Replayed downloads rely on symbolic links. They are supported on Linux, and on
    Windows with limitations: creating symbolic links requires Developer Mode (or the
    corresponding privilege), and the archive directory and the download directory are
    expected to be on the same drive.
