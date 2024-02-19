# -*- coding: utf-8 -*-
# Copyright 2024, CS GROUP - France, https://www.csgroup.eu/
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

import ast
import configparser
import os
import unittest

import importlib_metadata
from packaging.requirements import Requirement
from stdlib_list import stdlib_list

from tests.context import MisconfiguredError

project_path = "./eodag"
setup_cfg_path = "./setup.cfg"
allowed_missing_imports = ["eodag"]


def get_imports(filepath):
    """Get python imports from the given file path"""
    with open(filepath, "r") as file:
        try:
            root = ast.parse(file.read())
        except UnicodeDecodeError as e:
            raise MisconfiguredError(
                f"UnicodeDecodeError in {filepath}: {e.object[max(e.start - 50, 0):min(e.end + 50, len(e.object))]}"
            ) from e

    for node in ast.iter_child_nodes(root):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "utils":
                    pass

                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            if node.module.split(".")[0] == "utils":
                pass
            yield node.module.split(".")[0]


def get_project_imports(project_path):
    """Get python imports from the project path"""
    imports = set()
    for dirpath, dirs, files in os.walk(project_path):
        for filename in files:
            if filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                imports.update(get_imports(filepath))
    return imports


def get_setup_requires(setup_cfg_path):
    """Get requirements from the given setup.cfg file path"""
    config = configparser.ConfigParser()
    config.read(setup_cfg_path)
    return set(
        [
            Requirement(r).name
            for r in config["options"]["install_requires"].split("\n")
            if r
        ]
    )


class TestRequirements(unittest.TestCase):
    def test_requirements(self):
        """Needed libraries must be in project requirements"""

        project_imports = get_project_imports(project_path)
        setup_requires = get_setup_requires(setup_cfg_path)
        import_required_dict = importlib_metadata.packages_distributions()
        default_libs = stdlib_list()

        missing_imports = []
        for project_import in project_imports:
            required = import_required_dict.get(project_import, [project_import])
            if (
                not set(required).intersection(setup_requires)
                and project_import not in default_libs + allowed_missing_imports
            ):
                missing_imports.append(project_import)

        self.assertEqual(
            len(missing_imports),
            0,
            f"The following libraries were not found in project requirements: {missing_imports}",
        )
