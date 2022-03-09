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

import importlib
import pkgutil
from contextlib import contextmanager
from functools import partial


def import_all_modules(base_package, depth=1, exclude=()):
    """Import all modules in base_package, including modules in the sub-packages up to `depth` and excluding modules in
    `exclude`.

    Example::

        # base_package
        #    __init__.py
        #    module1.py
        #    subpackage
        #        __init__.py
        #        subsubpackage
        #            __init__.py
        #            module3.py
        #        module2.py
        #        excluded.py

        # Import 'module1' and 'module2'
        import_all_modules(base_package, depth=2, exclude=['excluded'])
        # Import 'module1'
        import_all_modules(base_package)

    :param base_package: The package from where we must import all the modules
    :type base_package: `module`
    :param depth: (optional) If `base_package` has sub packages, import all the modules recursively up to this level.
                  Defaults to 1 (limits to the level of `base_package`)
    :type depth: int
    :param exclude: (optional) The sub packages and modules to ignore while importing. Empty by default
    :type exclude: tuple(str, ...)

    .. note::
        if `package` and `subpackage` have a module of the same name and this name is included in the exclude
        parameter, the module will be excluded from import for both packages. This is intentionally left as is by
        now for simplification
    """
    if depth > 1:
        for _, name, ispkg in pkgutil.iter_modules(base_package.__path__):
            if not exclude or name not in exclude:
                if ispkg:
                    pkg = importlib.import_module(
                        ".{}".format(name), package=base_package.__name__
                    )
                    import_all_modules(pkg, depth=depth - 1, exclude=exclude)
                else:
                    importlib.import_module(
                        ".{}".format(name), package=base_package.__name__
                    )
    for _, name, ispkg in pkgutil.iter_modules(base_package.__path__):
        if (not exclude or name not in exclude) and not ispkg:
            importlib.import_module(".{}".format(name), package=base_package.__name__)


@contextmanager
def patch_owslib_requests(verify=True):
    """Overrides call to the :func:`requests.request` and :func:`requests.post` functions by
    :func:`owslib.util.openURL` and :func:`owslib.util.http_post` functions, providing some control over how to use
    these functions in `owslib <https://geopython.github.io/OWSLib/>`_.

    :param verify: (optional) Whether to verify the use of https or not
    :type verify: bool
    """
    from owslib.util import requests

    old_request = requests.request
    old_post = requests.post
    try:
        requests.request = partial(requests.request, verify=verify)
        requests.post = partial(requests.post, verify=verify)
        yield
    finally:
        requests.request = old_request
        requests.post = old_post
