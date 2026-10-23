# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
#
# This file is part of EODAG project
#     https://www.github.com/CS-SI/EODAG
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""This submodule provides all the necessary classes and functions to record and replay
EODAG requests over EO Providers.

.. note::
    This submodule has been strongly inspired by :external+vcrpy:std:doc:`VCR.py <index>`.

    Yet, integration into pytest is done in
    :mod:`eodag.utils.recording.pytest_integration`, and it is volontarily not imported
    here. Indeed ``pytest`` is not an execution dependency of eodag.

    You'll have to do it explicitely in the tests of your projets that depends on eodag.
    See :ref:`recording preparation procedure <recording-preparation>`.
"""

from __future__ import annotations

from eodag.utils.recording.errors import (
    CassetteFormatError,
    DuplicateKeyError,
    EodagRecordingConfigError,
    EodagRecordingError,
    EodagRecordingWarning,
    NoMatchingRecordError,
)
from eodag.utils.recording.recorder import EodagRecorder, RecordMode

__all__ = [
    "RecordMode",
    "EodagRecorder",
    "EodagRecordingError",
    "NoMatchingRecordError",
    "DuplicateKeyError",
    "CassetteFormatError",
    "EodagRecordingConfigError",
    "EodagRecordingWarning",
]
