import os
import signal
import threading
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Mapping, Optional, Union


class StreamResponseContent(Iterable[bytes]):
    """
    ByteIO minimal compatibility, used by boto3.upload_fileobj that's
    usually expect BytesIO object, not Iterable[bytes]
    """

    __initialized: bool = False
    __instances: list["StreamResponseContent"] = []

    @staticmethod
    def install_signal_handlers() -> bool:
        """Register SIGINT/SIGTERM handlers that interrupt any live stream.

        This must be called explicitly from the main thread (typically during a
        server's startup) because :func:`signal.signal` only works there. It is
        a no-op if the handlers are already installed or if it is called outside
        of the main thread.

        :returns: ``True`` if the handlers were installed, ``False`` otherwise.
        """
        if StreamResponseContent.__initialized:
            return False
        if threading.current_thread() is not threading.main_thread():
            return False

        StreamResponseContent.__initialized = True

        # Catch end of main process to internal status
        def signal_handler(sig, frame):
            for stream in StreamResponseContent.__instances:
                stream.interrupt()
            StreamResponseContent.__instances = []

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        return True

    def __init__(self, content: Union[Iterable[bytes], bytes]):
        self.buffer: bytes = b""
        self.interrupted: bool = False
        StreamResponseContent.__instances.append(self)
        if isinstance(content, bytes):
            content = [content]
        self.iterator: Iterator[bytes] = iter(content)

    def __iter__(self) -> Iterator[bytes]:
        return self.iterator

    def interrupt(self):
        if not self.interrupted:
            self.interrupted = True

    def read(self, size=-1) -> bytes:

        # Fill the buffer with enough bytes to fulfil the request.
        while not self.interrupted and (size < 0 or len(self.buffer) < size):
            try:
                chunk = next(self.iterator)
                self.buffer = self.buffer + bytes(chunk)
            except StopIteration:
                break

        if self.interrupted:
            raise InterruptedError()

        result: bytes = b""
        if size < 0:
            result, self.buffer = self.buffer, b""
        else:
            result, self.buffer = self.buffer[:size], self.buffer[size:]

        return bytes(result)


@dataclass
class StreamResponse:
    """Represents a streaming response"""

    content: StreamResponseContent
    _filename: Optional[str] = field(default=None, repr=False, init=False)
    _size: Optional[int] = field(default=None, repr=False, init=False)
    headers: dict[str, str] = field(default_factory=dict)
    media_type: Optional[str] = None
    status_code: Optional[int] = None
    arcname: Optional[str] = None

    def __init__(
        self,
        content: Union[Iterable[bytes], bytes],
        filename: Optional[str] = None,
        size: Optional[int] = None,
        headers: Optional[Mapping[str, str]] = None,
        media_type: Optional[str] = None,
        status_code: Optional[int] = None,
        arcname: Optional[str] = None,
    ):
        self.content = StreamResponseContent(content)
        self.headers = dict(headers) if headers else {}
        self.media_type = media_type
        self.status_code = status_code
        self.arcname = arcname
        # use property setters to update headers
        self.filename = filename
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
        """Set the filename and update the Content-Disposition header accordingly.

        :param value: The filename to set, or None to clear it
        """
        self._filename = value
        if value:
            outputs_filename = os.path.basename(value)
            self.headers[
                "Content-Disposition"
            ] = f'attachment; filename="{outputs_filename}"'
        elif "Content-Disposition" in self.headers:
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
        """Set the content size and update the Content-Length header accordingly.

        :param value: The content size in bytes, or None to clear it
        """
        self._size = value
        if value is not None:
            self.headers["Content-Length"] = str(value)
        elif "Content-Length" in self.headers:
            del self.headers["Content-Length"]


__all__ = ["StreamResponse"]
