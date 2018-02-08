# -*- coding: utf-8 -*-
# Copyright 2015-2018 CS Systemes d'Information (CS SI)
# All rights reserved
import importlib
import pkgutil
from contextlib import contextmanager
from functools import partial


def import_all_modules(base_package, depth=1, exclude=()):
    """Import all modules in base_package, including modules in the sub-packages up to depth and excluding modules in
    exclude.

    Example:
        base_package
            __init__.py
            module1.py
            subpackage
                __init__.py
                subsubpackage
                    __init__.py
                    module3.py
                module2.py
                excluded.py
        import_all_modules(base_package, depth=2, exclude=['excluded']) will import 'module1' and 'module2'
        import_all_modules(base_package) will import 'module1'
    Note: if package and subpackage have a module of the same name and this name is included in the exclude parameter,
    the module will be excluded from import for both packages. This is intentionally left as is by now for
    simplification
    """
    if depth > 1:
        for _, name, ispkg in pkgutil.iter_modules(base_package.__path__):
            if not exclude or name not in exclude:
                if ispkg:
                    pkg = importlib.import_module('.{}'.format(name), package=base_package.__name__)
                    import_all_modules(pkg, depth=depth - 1, exclude=exclude)
                else:
                    importlib.import_module('.{}'.format(name), package=base_package.__name__)
    for _, name, ispkg in pkgutil.iter_modules(base_package.__path__):
        if (not exclude or name not in exclude) and not ispkg:
            importlib.import_module('.{}'.format(name), package=base_package.__name__)


@contextmanager
def patch_owslib_requests(verify=True):
    """Overrides call to the requests.(request and post) functions by owslib.util.(openURL and http_post) functions,
    providing some control over how to use these requests functions in owslib.
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
