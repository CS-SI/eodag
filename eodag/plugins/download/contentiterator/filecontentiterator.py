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
from .basecontentiterator import TRANSFERT_CHUNK_SIZE, BaseContentIterator


class FileContentIterator(BaseContentIterator):
    """Content iterator based from a file"""

    def __init__(self, file_path: str):
        super().__init__()
        self.interrupted: bool = False
        self.file_path = file_path
        self.fp = None
        self.position: int = 0

    def interrupt(self):
        """Used to stop generator"""
        self.interrupted = True

    def __next__(self):
        if self.is_terminating() or self.interrupted:
            self.fire("error", InterruptedError())
            raise InterruptedError()
        try:
            if self.fp is None:
                self.fp = open(self.file_path, "rb")
            chunk = self.fp.read(TRANSFERT_CHUNK_SIZE)
            if len(chunk) == 0:
                raise StopIteration
            return chunk
        except Exception as e:
            if self.fp is not None:
                self.fp.close()
                self.fp = None
            self.fire("complete")
            raise e


__all__ = ["FileContentIterator"]
