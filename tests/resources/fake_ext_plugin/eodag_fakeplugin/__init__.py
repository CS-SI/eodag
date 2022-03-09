# -*- coding: utf-8 -*-
# Copyright 2022, CS GROUP - France, https://www.csgroup.eu/
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
# Filter Cython warnings
# Apparently (see
# https://stackoverflow.com/questions/40845304/runtimewarning-numpy-dtype-size-changed-may-indicate-binary-incompatibility     # noqa
# and https://github.com/numpy/numpy/issues/11788) this is caused by Cython and affect pre-built Python packages that
# depends on numpy and ship with a pre-built version of numpy that is older than 1.15.1 (where the warning is silenced
# exactly as below)
"""EODAG fake_ext_plugin."""


class FakePluginAPI:
    pass
