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

from typing import Callable, final

from typing_extensions import Self


class Eventable:
    """Use to manage events in a class"""

    def __init__(self):
        self._handlers: dict[str, list] = {}  # type: ignore

    @final
    def on(self, event_name: str, callback: Callable) -> Self:
        """Add a event listener
        :param str event_name
        :param callback Callable
        """
        if isinstance(event_name, str) and event_name != "" and callable(callback):
            if event_name not in self._handlers:
                self._handlers[event_name] = []
            if callback not in self._handlers[event_name]:
                self._handlers[event_name].append(callback)
        return self

    @final
    def off(self, event_name: str) -> Self:
        """Unset a event listener
        :param str event_name
        :param callback Callable
        """
        if isinstance(event_name, str) and event_name != "":
            if event_name in self._handlers:
                del self._handlers[event_name]
        return self

    @final
    def fire(self, event_name: str, *args, **kwargs) -> Self:
        """Trigger a event listener
        :param str event_name
        args and kwaargs pass through handlers
        """
        if (
            isinstance(event_name, str)
            and event_name != ""
            and event_name in self._handlers
        ):
            for func in self._handlers[event_name]:
                func(*args, **kwargs)
        return self


__all__ = ["Eventable"]
