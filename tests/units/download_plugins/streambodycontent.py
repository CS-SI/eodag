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
class StreamBodyContent:
    def __init__(self, content: bytes):
        self.content = content[:]

    def readable(self) -> bool:
        return len(self.content) > 0

    def read(self, size: int = -1) -> bool:
        if len(self.content) == 0:
            return b""
        if len(self.content) < size:
            chunk = self.content
            self.content = b""
        else:
            chunk = self.content[0:size]
            self.content = self.content[size:]
        return chunk


__all__ = ["StreamBodyContent"]
