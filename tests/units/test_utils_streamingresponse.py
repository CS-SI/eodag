import os
import shutil
import tempfile
import unittest

from eodag.utils import StreamResponse


class StreamResponseTest(unittest.TestCase):

    TMP_DIR = os.path.join(tempfile.gettempdir(), "test_streamresponse")

    @classmethod
    def setUpClass(cls):
        if not os.path.isdir(StreamResponseTest.TMP_DIR):
            os.mkdir(StreamResponseTest.TMP_DIR)

    @classmethod
    def tearDownClass(cls):
        if os.path.isdir(StreamResponseTest.TMP_DIR):
            shutil.rmtree(StreamResponseTest.TMP_DIR)

    def test_streamresponse_download_generator(self):

        content = b""
        with open(__file__, "rb") as fd:
            content = fd.read()

        stream = StreamResponse(
            content=content,
            filename=os.path.basename(__file__),
            size=len(content),
            headers={"Content-Length": len(content), "Content-Type": "text/plain"},
        )

        filepath = os.path.join(
            StreamResponseTest.TMP_DIR, "gs_{}".format(stream.filename)
        )

        # Download to tmp directory as generator
        with open(filepath, "wb") as fp:
            for chunk in stream.content:
                fp.write(chunk)

        with open(filepath, "rb") as fd:
            dest_content = fd.read()

        self.assertEqual(content, dest_content)
        os.remove(filepath)

    def test_streamresponse_download_byteio(self):

        content = b""
        with open(__file__, "rb") as fd:
            content = fd.read()

        stream = StreamResponse(
            content=content,
            filename=os.path.basename(__file__),
            size=len(content),
            headers={"Content-Length": len(content), "Content-Type": "text/plain"},
        )

        filepath = os.path.join(
            StreamResponseTest.TMP_DIR, "io_{}".format(stream.filename)
        )

        # Download to tmp directory as generator
        with open(filepath, "wb") as fp:
            downloading = True
            while downloading:
                chunk = stream.content.read()
                if len(chunk) == 0:
                    downloading = False
                else:
                    fp.write(chunk)

        with open(filepath, "rb") as fd:
            dest_content = fd.read()

        self.assertEqual(content, dest_content)
        os.remove(filepath)

    def test_streamresponse_download_byteio_interrupted(self):

        content = b""
        with open(__file__, "rb") as fd:
            content = fd.read()

        # Chukize content
        chunked_content = []
        while len(content) > 1024:
            chunked_content.append(content[0:1024])
            content = content[1024:]
        if len(content) > 0:
            chunked_content.append(content)
        content = chunked_content

        stream = StreamResponse(
            content=content,
            filename=os.path.basename(__file__),
            size=len(content),
            headers={"Content-Length": len(content), "Content-Type": "text/plain"},
        )

        _ = stream.content.read()
        stream.content.interrupt()
        try:
            _ = stream.content.read()
            self.fail(
                "Must not allow stream read after being interrupted by term signal"
            )
        except InterruptedError:
            pass
