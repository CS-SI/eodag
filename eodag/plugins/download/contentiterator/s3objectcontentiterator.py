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
from typing import Optional

from eodag.utils import ProgressCallback

from .basecontentiterator import TRANSFERT_CHUNK_SIZE, BaseContentIterator


class S3ObjectContentIterator(BaseContentIterator):
    """Content iterator based from a s3 object"""

    def __init__(
        self, s3_object: dict, progress_callback: Optional[ProgressCallback] = None
    ):
        super().__init__()
        self.progress_callback = progress_callback
        self.stream = s3_object["Body"]
        self.filesize = None
        self.interrupted: bool = False

        headers = s3_object.get("ResponseMetadata", {}).get("HTTPHeaders", {})
        for name in headers:
            if name.lower() == "content-length":
                self.filesize = int(headers[name])

    def interrupt(self):
        """Used to stop generator"""
        self.interrupted = True

    def __next__(self):

        if self.is_terminating() or self.interrupted:
            self.fire("error", InterruptedError())
            raise InterruptedError()

        try:
            chunk = next(self.stream.iter_chunks(chunk_size=TRANSFERT_CHUNK_SIZE))
            chunk_size = len(chunk)
            if chunk_size > 0:
                if self.progress_callback is not None and self.filesize is not None:
                    self.progress_callback(chunk_size)
                self.fire("chunk", chunk)
                return chunk

        except StopIteration:
            if self.progress_callback is not None:
                if isinstance(self.filesize, int):
                    self.progress_callback(self.filesize)
                else:
                    self.progress_callback(1)
            self.fire("complete")
            raise StopIteration


__all__ = ["S3ObjectContentIterator"]
