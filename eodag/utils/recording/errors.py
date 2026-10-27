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

"""Errors and warnings raised by :mod:`eodag.utils.recording`."""

from __future__ import annotations


class EodagRecordingError(Exception):
    """Base class of all the errors raised by :mod:`eodag.utils.recording`."""


class NoMatchingRecordError(EodagRecordingError):
    """Raised in replay mode when a call has no matching entry in the cassettes."""


class DuplicateKeyError(EodagRecordingError):
    """Raised when the same key is present several times, within one cassette or
    across several cassettes read together."""


class CassetteFormatError(EodagRecordingError):
    """Raised when a cassette is unreadable, has an unsupported version, or contains
    something that cannot be decoded."""


class EodagRecordingConfigError(EodagRecordingError):
    """Raised on an invalid configuration (cassettes, ``write_to``, mode...)."""


class EodagRecordingWarning(UserWarning):
    """Warning emitted by :mod:`eodag.utils.recording`."""
