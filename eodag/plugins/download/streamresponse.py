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
import hashlib
import os
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

from eodag.utils import Mime

from .contentiterator import FileContentIterator


@dataclass
class StreamResponse:
    """Represents a streaming response"""

    content: Iterable[bytes]
    _filename: Optional[str] = field(default=None, repr=False, init=False)
    _size: Optional[int] = field(default=None, repr=False, init=False)
    headers: dict[str, str] = field(default_factory=dict)
    media_type: Optional[str] = None
    status_code: Optional[int] = None
    arcname: Optional[str] = None

    @staticmethod
    def from_file(path: str):
        """Generate a StreamResponse from local_file

        :param str path: path of local file
        :return StreamResponse:
        :raise FileExistsError:
        """
        if not os.path.isfile(path):
            raise FileExistsError()

        fci = FileContentIterator(path)
        name = os.path.basename(path)
        stat = os.stat(path)
        size = stat.st_size
        mime = Mime.guess_file_type(path)
        with open(path, "rb") as fd:
            etag = hashlib.md5(fd.read()).hexdigest()

        return StreamResponse(
            content=fci,
            filename=name,
            size=size,
            headers={
                "Content-Length": str(size),
                "Content-Type": mime,
                "Content-Disposition": 'attachment; filename="{}"'.format(name),
                "ETag": '"{}"'.format(etag),
            },
            media_type=mime,
            status_code=200,
            arcname=None,
        )

    def __init__(
        self,
        content: Iterable[bytes],
        filename: Optional[str] = None,
        size: Optional[int] = None,
        headers: Optional[Mapping[str, str]] = None,
        media_type: Optional[str] = None,
        status_code: Optional[int] = None,
        arcname: Optional[str] = None,
    ):
        self.content = content
        self.headers = dict(headers) if headers else {}
        self.media_type = media_type
        self.status_code = status_code
        self.arcname = arcname
        # use property setters to update headers
        self._filename = filename
        self.size = size

    # filename handling
    @property
    def filename(self) -> Optional[str]:
        """Get the filename for the streaming response.

        :returns: The filename, or None if not set
        """
        return self._filename

    @filename.setter
    def filename(self, value: Optional[str]) -> None:
        """Set the filename and update the content-disposition header accordingly.

        :param value: The filename to set, or None to clear it
        """
        self._filename = value
        if value:
            outputs_filename = os.path.basename(value)
            self.headers[
                "Content-Disposition"
            ] = f'attachment; filename="{outputs_filename}"'
        elif "content-disposition" in self.headers:
            del self.headers["Content-Disposition"]

    # size handling
    @property
    def size(self) -> Optional[int]:
        """Get the content size for the streaming response.

        :returns: The content size in bytes, or None if not set
        """
        return self._size

    @size.setter
    def size(self, value: Optional[int]) -> None:
        """Set the content size and update the content-length header accordingly.

        :param value: The content size in bytes, or None to clear it
        """
        self._size = value
        if value is not None:
            self.headers["Content-Length"] = str(value)
        elif "Content-Length" in self.headers:
            del self.headers["Content-Length"]


__all__ = ["StreamResponse"]
