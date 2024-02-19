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
from __future__ import annotations

import logging.config
from typing import Optional

disable_tqdm = False


def setup_logging(verbose: int, no_progress_bar: bool = False) -> None:
    """Define logging level

    :param verbose: Accepted values:

                    * 0: no logging with muted progress bars
                    * 1: no logging but still displays progress bars
                    * 2: INFO level
                    * 3: DEBUG level
    :type verbose: int
    :param no_progress_bar: (optional) Disable progress bars
    :type no_progress_bar: bool
    """
    global disable_tqdm
    disable_tqdm = no_progress_bar

    if verbose < 1:
        disable_tqdm = True

    if verbose <= 1:
        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "handlers": {
                    "null": {"level": "DEBUG", "class": "logging.NullHandler"}
                },
                "loggers": {
                    "eodag": {"handlers": ["null"], "propagate": True, "level": "INFO"}
                },
            }
        )
    elif verbose == 2:
        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "standard": {
                        "format": "%(asctime)-15s %(name)-32s [%(levelname)-8s] %(message)s"
                    }
                },
                "handlers": {
                    "console": {
                        "level": "DEBUG",
                        "class": "logging.StreamHandler",
                        "formatter": "standard",
                    }
                },
                "loggers": {
                    "eodag": {
                        "handlers": ["console"],
                        "propagate": True,
                        "level": "INFO",
                    },
                    "sentinelsat": {
                        "handlers": ["console"],
                        "propagate": True,
                        "level": "INFO",
                    },
                },
            }
        )
    elif verbose == 3:
        logging.config.dictConfig(
            {
                "version": 1,
                "disable_existing_loggers": False,
                "formatters": {
                    "verbose": {
                        "format": (
                            "%(asctime)-15s %(name)-32s [%(levelname)-8s] (tid=%(thread)d) %(message)s"
                        )
                    }
                },
                "handlers": {
                    "console": {
                        "level": "DEBUG",
                        "class": "logging.StreamHandler",
                        "formatter": "verbose",
                    }
                },
                "loggers": {
                    "eodag": {
                        "handlers": ["console"],
                        "propagate": True,
                        "level": "DEBUG",
                    },
                    "sentinelsat": {
                        "handlers": ["console"],
                        "propagate": True,
                        "level": "DEBUG",
                    },
                },
            }
        )
    else:
        raise ValueError("'verbose' must be one of: 0, 1, 2, 3")


def get_logging_verbose() -> Optional[int]:
    """Get logging verbose level

    >>> from eodag import setup_logging
    >>> get_logging_verbose()
    >>> setup_logging(verbose=0)
    >>> get_logging_verbose()
    0
    >>> setup_logging(verbose=1)
    >>> get_logging_verbose()
    1
    >>> setup_logging(verbose=2)
    >>> get_logging_verbose()
    2
    >>> setup_logging(verbose=3)
    >>> get_logging_verbose()
    3

    :returns: Verbose level in ``[0, 1, 2, 3]`` or None if not set
    :rtype: int or None
    """
    global disable_tqdm
    logger = logging.getLogger("eodag")

    try:
        if disable_tqdm and isinstance(logger.handlers[0], logging.NullHandler):
            return 0
        elif isinstance(logger.handlers[0], logging.NullHandler):
            return 1
        elif logger.getEffectiveLevel() == logging.INFO:
            return 2
        elif logger.getEffectiveLevel() == logging.DEBUG:
            return 3
    except IndexError:
        # verbose level has not been set yet
        pass

    return None
