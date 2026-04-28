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
import os
import unittest
from tempfile import TemporaryDirectory

from eodag.plugins.download import FileContentIterator, StreamResponse


class StreamResponseTest(unittest.TestCase):
    def test_streamresponse_download(self):

        with TemporaryDirectory() as tmp_dir:

            content = b""
            with open(__file__, "rb") as fd:
                content = fd.read()

            stream = StreamResponse(
                content=FileContentIterator(__file__),
                filename=os.path.basename(__file__),
            )

            filepath = os.path.join(tmp_dir, "io_{}".format(stream.filename))

            # Download to tmp directory as generator
            with open(filepath, "wb") as fp:
                for chunk in stream.content:
                    fp.write(chunk)

            with open(filepath, "rb") as fd:
                dest_content = fd.read()

            self.assertEqual(content, dest_content)
            os.remove(filepath)

    def test_streamresponse_download_byteio_interrupted(self):

        stream = StreamResponse(
            content=FileContentIterator(__file__),
            filename=os.path.basename(__file__),
        )

        _ = next(stream.content)
        stream.content.interrupt()
        try:
            _ = next(stream.content)
            self.fail(
                "Must not allow stream read after being interrupted by term signal"
            )
        except InterruptedError:
            pass
