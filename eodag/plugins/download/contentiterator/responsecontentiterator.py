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

from requests import Response

from eodag.utils import ProgressCallback

from ..httputils import HttpUtils
from .basecontentiterator import TRANSFERT_CHUNK_SIZE, BaseContentIterator


class ResponseContentIterator(BaseContentIterator):
    """Content iterator based from a response"""

    def __init__(
        self,
        response: Response,
        progress_callback: Optional[ProgressCallback] = None,
        filename: Optional[str] = None,
        filesize: Optional[int] = None,
    ):
        super().__init__()
        self.response = response
        headers = HttpUtils.format_headers(response.headers)
        self.progress_callback = progress_callback
        self.filesize = headers.get("Content-Length", filesize)
        self.position = 0
        self.interrupted: bool = False
        if progress_callback is not None:
            if filesize is not None:
                self.filesize = int(filesize)
                progress_callback.reset(total=float(filesize))
            else:
                progress_callback.reset(total=1)
            if filename is not None:
                progress_callback.desc = filename

    def interrupt(self):
        """Used to stop generator"""
        self.interrupted = True

    def __next__(self):

        if self.is_terminating() or self.interrupted:
            self.fire("error", InterruptedError())
            raise InterruptedError()

        try:

            # Some trouble with iter_content when slow http Transfer: chunked
            # send too early StopIteration when internal buffer is empty, even if transfert is not complete
            if self.filesize is None:
                filesize = len(self.response.content)  # read updated content size
                if self.position >= filesize:
                    raise StopIteration
                else:
                    chunk = self.response.content[
                        self.position : self.position + TRANSFERT_CHUNK_SIZE
                    ]
                    self.position += TRANSFERT_CHUNK_SIZE
                    self.progress_callback(len(chunk))
                    self.fire("chunk", chunk)
                    return chunk
            else:
                if self.position >= self.filesize:
                    raise StopIteration()
                chunk = next(
                    self.response.iter_content(chunk_size=TRANSFERT_CHUNK_SIZE)
                )
                chunk_size = len(chunk)
                if chunk_size > 0:
                    self.position += chunk_size
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

        except Exception as e:

            if self.progress_callback is not None:
                if isinstance(self.filesize, int):
                    self.progress_callback(self.filesize)
                else:
                    self.progress_callback(1)
            self.fire("error", e)
            raise e


__all__ = ["ResponseContentIterator"]
