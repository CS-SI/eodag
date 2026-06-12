import os
import shutil
import signal
import tempfile
import threading
import unittest

from eodag.utils import StreamResponse, StreamResponseContent


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

        # Chunkize content
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


class StreamResponseSignalHandlersTest(unittest.TestCase):
    """Signal handlers must only be installed explicitly, on the main thread."""

    def setUp(self):
        # Preserve handlers possibly set by other tests/the runtime.
        self._sigint = signal.getsignal(signal.SIGINT)
        self._sigterm = signal.getsignal(signal.SIGTERM)
        # Reset the one-shot installation flag so each test starts clean.
        StreamResponseContent._StreamResponseContent__initialized = False

    def tearDown(self):
        signal.signal(signal.SIGINT, self._sigint)
        signal.signal(signal.SIGTERM, self._sigterm)
        StreamResponseContent._StreamResponseContent__initialized = False

    def test_importing_streamresponse_does_not_register_handlers(self):
        """Importing streamresponse must not modify process signal handlers."""
        # Importing the module must not override the default SIGINT handler.
        self.assertIs(signal.getsignal(signal.SIGINT), signal.default_int_handler)

    def test_install_signal_handlers_on_main_thread(self):
        """Main-thread installation must register handlers once and be idempotent."""
        self.assertTrue(StreamResponseContent.install_signal_handlers())
        self.assertIsNot(signal.getsignal(signal.SIGINT), signal.default_int_handler)
        self.assertIsNot(signal.getsignal(signal.SIGTERM), signal.SIG_DFL)
        # Idempotent: a second call is a no-op.
        self.assertFalse(StreamResponseContent.install_signal_handlers())

    def test_install_signal_handlers_off_main_thread_is_noop(self):
        """Background-thread installation must be a no-op."""
        results = {}

        def worker():
            results["installed"] = StreamResponseContent.install_signal_handlers()

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

        self.assertFalse(results["installed"])
        # Default handler untouched when called from a background thread.
        self.assertIs(signal.getsignal(signal.SIGINT), signal.default_int_handler)

    def test_construct_streamresponse_off_main_thread_does_not_raise(self):
        """Creating stream content in worker threads must not raise."""
        errors = []

        def worker():
            try:
                StreamResponseContent.install_signal_handlers()
                StreamResponseContent(iter([b"abc"]))
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

        self.assertEqual(errors, [])

    def test_handler_interrupts_live_stream(self):
        """Installed signal handler must interrupt active stream reads."""
        StreamResponseContent.install_signal_handlers()
        stream = StreamResponseContent(iter([b"abc", b"def"]))

        # Simulate receiving SIGINT by invoking the installed handler.
        signal.getsignal(signal.SIGINT)(signal.SIGINT, None)

        with self.assertRaises(InterruptedError):
            stream.read(1)
