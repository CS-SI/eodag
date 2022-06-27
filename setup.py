# -*- coding: utf-8 -*-
# Copyright 2018, CS GROUP - France, https://www.csgroup.eu/
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
import setuptools


def _get_fallback_version():
    """Read fallback_version from pyproject.toml"""
    import os
    import re

    BASEDIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))

    version_regex = r"^fallback_version\s+=\s+[\"'](.*)[\"']\s+$"
    with open(os.path.join(BASEDIR, "pyproject.toml")) as f:
        found_versions = re.findall(version_regex, f.read(), re.MULTILINE)

    fallback_version = found_versions[0] if found_versions else "0.0.0.dev0"
    return fallback_version


if __name__ == "__main__":
    setuptools.setup(
        use_scm_version={"fallback_version": _get_fallback_version()},
        setup_requires=["setuptools_scm<7"],
    )
