# -*- coding: utf-8 -*-
# Copyright 2021, CS GROUP - France, https://www.csgroup.eu/
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

import logging.config

disable_tqdm = False


def setup_logging(verbose, no_progress_bar=False):
    """Define logging level

    :param verbose: Accepted values:

                    * 0: no logging with muted progress bars
                    * 1: no logging but still displays progress bars
                    * 2: INFO level
                    * 3: DEBUG level
    :type verbose: int

    :param no_progress_bar: (optional) disable progress bars (default=False)
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
                        "format": "%(asctime)s-15s %(name)-32s [%(levelname)-8s] %(message)s"
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
                        "format": "%(asctime)s-15s %(name)-32s [%(levelname)-8s] (%(module)-17s) %(message)s"
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
