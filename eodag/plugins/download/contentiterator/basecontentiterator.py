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
import signal
from typing import final

from eodag.utils import Eventable

TRANSFERT_CHUNK_SIZE = 8388608  # "8Mo"


class BaseContentIterator(Eventable):
    """Base abstraction of content iterator"""

    _initialized: bool = False
    _terminating: bool = False

    @staticmethod
    def init():
        """Main singleton initializer"""
        if not BaseContentIterator._initialized:
            BaseContentIterator._initialized = True

            # Catch end of main process to internal status
            def signal_handler(sig, frame):
                if not BaseContentIterator._terminating:
                    BaseContentIterator._terminating = True

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

    def __init__(self):
        super().__init__()

    @final
    def is_terminating(self):
        """Return if current program is terminating"""
        return BaseContentIterator._terminating

    def __iter__(self):
        return self

    def __next__(self):
        raise NotImplementedError()


BaseContentIterator.init()


__all__ = ["TRANSFERT_CHUNK_SIZE", "BaseContentIterator"]
