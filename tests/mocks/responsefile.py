import datetime
import mimetypes
import os
import signal
from typing import Union


class ResponseFile:
    """Emulation of a response to requests.get method for a file"""

    __initialized: bool = False
    __terminating: bool = False

    @staticmethod
    def init() -> "ResponseFile":
        """Main singleton initializer"""
        if not ResponseFile.__initialized:
            ResponseFile.__initialized = True

            # Catch end of main process to internal status
            def signal_handler(sig, frame):
                if not ResponseFile.__terminating:
                    ResponseFile.__terminating = True

            signal.signal(signal.SIGINT, signal_handler)
        return ResponseFile

    def __init__(self, local_file: str, headers: dict = {}, url: str = ""):

        self.local_file = local_file
        self.url = url
        self.headers = {"Date": self.__date_format(), "Server": "Mock"}
        self.status_code = 200
        self.content = b""
        self.raw = None
        self.encoding = None
        self.history = []
        self.reason = None
        self.cookies = {}
        self.elapsed = datetime.timedelta(0)
        self.request = None

        if not os.path.isfile(local_file):
            raise FileNotFoundError("File {} not found".format(local_file))

        with open(local_file, "rb") as fd:
            self.content = fd.read()

        stat = os.stat(local_file)
        filename = os.path.basename(local_file)
        self.headers["Content-Length"] = str(stat.st_size)
        self.headers["Content-Disposition"] = "attachment; filename={}".format(filename)
        self.headers["Content-Type"] = mimetypes.guess_type(
            filename, "application/octet-stream"
        )[0]
        self.headers["Last-Modified"] = self.__date_format(stat.st_mtime)
        for name, value in self.__format_headers(headers).items():
            self.headers[name] = value

    def __format_headers(self, headers: dict):
        """format headers field name sa camel case"""
        formatted_headers = {}
        for key in headers:
            previous = ""
            formatted = ""
            for index in range(0, len(key)):
                char = key[index]
                if index == 0 or previous == "-":
                    char = char.upper()
                else:
                    char = char.lower()
                formatted += char
                previous = char
            formatted_headers[formatted] = headers[key]
        return formatted_headers

    def __date_format(self, value: Union[int, datetime.datetime, None] = None) -> str:
        """date format as iso gmt from mixed types"""
        if isinstance(value, datetime.datetime):
            date = value
        elif isinstance(value, int) or isinstance(value, float):
            date = datetime.datetime.fromtimestamp(int(value / 1000))
        else:
            date = datetime.datetime.now(datetime.timezone.utc)
        return date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __iter__(self):
        return self.iter_content(128)

    def iter_content(self, chunk_size=-1, decode_unicode=False):
        def generate():
            slice_start = 0
            while not ResponseFile.__terminating:
                chunk = b""
                if chunk_size > 0:
                    if slice_start < len(self.content):
                        slice_end = min(slice_start + chunk_size, len(self.content))
                        chunk = self.content[slice_start:slice_end]
                        slice_start = slice_end
                else:
                    chunk = self.content
                if not chunk:
                    break
                yield chunk

        return generate()

    def raise_for_status(self):
        pass

    def close(self):
        pass


ResponseFile.init()

__all__ = ["ResponseFile"]
