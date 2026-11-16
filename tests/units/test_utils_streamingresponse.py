import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from unittest.mock import Mock

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

    def test_streamresponse_filename_overwrites_lowercase_content_disposition(self):
        """When headers contain 'content-disposition' (lowercase) and a filename is
        also provided, the filename setter must overwrite the existing header instead
        of creating a duplicate 'Content-Disposition' entry."""
        stream = StreamResponse(
            content=b"",
            headers={"content-disposition": 'attachment; filename="old_name.nc"'},
            filename="new_name.nc",
        )
        # Only one Content-Disposition key must exist (CaseInsensitiveDict merges them)
        matching = [k for k in stream.headers if k.lower() == "content-disposition"]
        self.assertEqual(len(matching), 1)
        self.assertIn("new_name.nc", stream.headers["Content-Disposition"])

    def test_streamresponse_headers_are_case_insensitive(self):
        """Headers must be accessible regardless of key casing."""
        stream = StreamResponse(
            content=b"",
            headers={"Content-Type": "text/plain", "X-Custom-Header": "value"},
        )
        # Access with different casings
        self.assertEqual(stream.headers["content-type"], "text/plain")
        self.assertEqual(stream.headers["CONTENT-TYPE"], "text/plain")
        self.assertEqual(stream.headers["x-custom-header"], "value")
        self.assertEqual(stream.headers["X-CUSTOM-HEADER"], "value")

    def test_streamresponse_headers_default_case_insensitive(self):
        """Headers must default to a CaseInsensitiveDict when not provided."""
        from requests.structures import CaseInsensitiveDict

        stream = StreamResponse(content=b"")
        self.assertIsInstance(stream.headers, CaseInsensitiveDict)

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
        self._handlers = StreamResponseContent._StreamResponseContent__signal_handlers
        self._instances = StreamResponseContent._StreamResponseContent__instances
        StreamResponseContent._StreamResponseContent__signal_handlers = {}
        StreamResponseContent._StreamResponseContent__instances = []

    def tearDown(self):
        signal.signal(signal.SIGINT, self._sigint)
        signal.signal(signal.SIGTERM, self._sigterm)
        StreamResponseContent._StreamResponseContent__signal_handlers = self._handlers
        StreamResponseContent._StreamResponseContent__instances = self._instances

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
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        StreamResponseContent.install_signal_handlers()
        stream = StreamResponseContent(iter([b"abc", b"def"]))

        # Simulate receiving SIGINT by invoking the installed handler.
        signal.getsignal(signal.SIGINT)(signal.SIGINT, None)

        with self.assertRaises(InterruptedError):
            stream.read(1)

    def test_handler_preserves_server_shutdown(self):
        """Interrupt streams before delegating to the server's signal handler."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=sig):
                stream = StreamResponseContent(b"abc")
                server_handler = Mock(
                    side_effect=lambda *args, stream=stream: self.assertTrue(
                        stream.interrupted
                    )
                )
                signal.signal(sig, server_handler)
                StreamResponseContent.install_signal_handlers()

                signal.getsignal(sig)(sig, None)

                server_handler.assert_called_once_with(sig, None)

    def test_reinstall_after_server_replaces_handler(self):
        """Rewrap a new server handler without stacking interruption callbacks."""
        old_handler = Mock()
        signal.signal(signal.SIGTERM, old_handler)
        self.assertTrue(StreamResponseContent.install_signal_handlers())
        first_handler = signal.getsignal(signal.SIGTERM)
        self.assertFalse(StreamResponseContent.install_signal_handlers())
        self.assertIs(signal.getsignal(signal.SIGTERM), first_handler)

        new_handler = Mock()
        signal.signal(signal.SIGTERM, new_handler)
        self.assertTrue(StreamResponseContent.install_signal_handlers())
        self.assertFalse(StreamResponseContent.install_signal_handlers())
        stream = StreamResponseContent(b"abc")
        stream.interrupt = Mock(wraps=stream.interrupt)

        signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)

        stream.interrupt.assert_called_once_with()
        new_handler.assert_called_once_with(signal.SIGTERM, None)
        old_handler.assert_not_called()

    def test_failed_interruption_preserves_server_shutdown(self):
        """Even a failing stream must not swallow the server shutdown callback."""
        server_handler = Mock()
        signal.signal(signal.SIGTERM, server_handler)
        StreamResponseContent.install_signal_handlers()
        stream = StreamResponseContent(b"abc")
        stream.interrupt = Mock(side_effect=RuntimeError("interruption failed"))

        with self.assertRaisesRegex(RuntimeError, "interruption failed"):
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)

        server_handler.assert_called_once_with(signal.SIGTERM, None)

    @unittest.skipUnless(os.name == "posix", "POSIX signal exit codes required")
    def test_real_signals_preserve_process_behavior(self):
        """Real signals must preserve server exit, default exit, and ignore."""
        code = textwrap.dedent("""
            import os
            import signal
            import sys
            from eodag.utils import StreamResponseContent

            sig = int(sys.argv[1])
            mode = sys.argv[2]
            stream = StreamResponseContent(b"abc")

            def server_handler(sig, frame):
                assert stream.interrupted
                sys.exit(0)

            previous = {
                "server": server_handler,
                "default": signal.SIG_DFL,
                "ignore": signal.SIG_IGN,
            }[mode]
            signal.signal(sig, previous)
            StreamResponseContent.install_signal_handlers()
            os.kill(os.getpid(), sig)
            assert stream.interrupted
            sys.exit(0 if mode == "ignore" else 42)
            """)
        for sig in (signal.SIGINT, signal.SIGTERM):
            for mode in ("server", "default", "ignore"):
                with self.subTest(signal=sig, mode=mode):
                    result = subprocess.run(
                        [sys.executable, "-c", code, str(int(sig)), mode],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=20,
                    )
                    expected = -int(sig) if mode == "default" else 0
                    self.assertEqual(result.returncode, expected, result.stderr)
