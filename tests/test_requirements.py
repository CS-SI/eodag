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
import re
import unittest
from typing import Any, Dict, Iterator, Set

import importlib_metadata
from packaging.requirements import Requirement
from stdlib_list import stdlib_list

from eodag.config import PluginConfig, load_default_config
from tests.context import MisconfiguredError

project_path = "./eodag"
setup_cfg_path = "./setup.cfg"
allowed_missing_imports = ["eodag"]


def get_imports(filepath: str) -> Iterator[Any]:
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


def get_project_imports(project_path: str) -> Set[str]:
    """Get python imports from the project path"""
    imports = set()
    for dirpath, dirs, files in os.walk(project_path):
        for filename in files:
            if filename.endswith(".py"):
                filepath = os.path.join(dirpath, filename)
                imports.update(get_imports(filepath))
    return imports


def get_setup_requires(setup_cfg_path: str):
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


def get_optional_dependencies(setup_cfg_path: str, extra: str) -> Set[str]:
    """Get extra requirements from the given setup.cfg file path"""
    config = configparser.ConfigParser()
    config.read(setup_cfg_path)
    deps = set()
    for req in config["options.extras_require"][extra].split("\n"):
        if req.startswith("eodag["):
            for found_extra in re.findall(r"([\w-]+)[,\]]", req):
                deps.update(get_optional_dependencies(setup_cfg_path, found_extra))
        elif req:
            deps.add(Requirement(req).name)

    return deps


def get_resulting_extras(setup_cfg_path: str, extra: str) -> Set[str]:
    """Get resulting extras for a single extra from the given setup.cfg file path"""
    config = configparser.ConfigParser()
    config.read(setup_cfg_path)
    extras = set()
    for req in config["options.extras_require"][extra].split("\n"):
        if req.startswith("eodag["):
            extras.update(re.findall(r"([\w-]+)[,\]]", req))
    return extras


def get_entrypoints_extras(setup_cfg_path: str) -> Dict[str, str]:
    """Get entrypoints and associated extra from the given setup.cfg file path"""
    config = configparser.ConfigParser()
    config.read(setup_cfg_path)
    plugins_extras_dict = dict()
    for group in config["options.entry_points"].keys():
        for ep in config["options.entry_points"][group].split("\n"):
            # plugin entrypoint with associated extra
            match = re.search(r"^(\w+) = [\w\.:]+ \[(\w+)\]$", ep)
            if match:
                plugins_extras_dict[match.group(1)] = match.group(2)
                continue
            # plugin entrypoint without extra
            match = re.search(r"^(\w+) = [\w\.:]+$", ep)
            if match:
                plugins_extras_dict[match.group(1)] = None

    return plugins_extras_dict


class TestRequirements(unittest.TestCase):
    def test_all_requirements(self):
        """Needed libraries must be in project requirements"""

        project_imports = get_project_imports(project_path)
        setup_requires = get_setup_requires(setup_cfg_path)
        setup_requires.update(get_optional_dependencies(setup_cfg_path, "all"))
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

    def test_plugins_extras(self):
        """All optional dependencies needed by providers must be resolved with all-providers extra"""

        plugins_extras_dict = get_entrypoints_extras(setup_cfg_path)
        all_providers_extras = get_resulting_extras(setup_cfg_path, "all-providers")

        providers_config = load_default_config()
        plugins = set()
        for provider_conf in providers_config.values():
            plugins.update(
                [
                    getattr(provider_conf, x).type
                    for x in dir(provider_conf)
                    if isinstance(getattr(provider_conf, x), PluginConfig)
                ]
            )

        for plugin in plugins:
            if extra := plugins_extras_dict.get(plugin):
                self.assertIn(extra, all_providers_extras)
