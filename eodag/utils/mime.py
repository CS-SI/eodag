import mimetypes
import os
from typing import Optional


class Mime:
    """Class to manage file mime and extension"""

    DEFAULT: str = "application/octet-stream"
    MIME_OVERRIDE: dict[str, str] = {"text/xml": "application/xml"}
    EXTENSIONS_FILEHEAD_CHUNKSIZE: int = 30
    EXTENSIONS_FILEHEADS: dict[str, bytes] = {
        "hdf5": b"\211HDF\r\n\032\n",
        "grib": b"GRIB\255\255",
    }

    @staticmethod
    def guess_file_type(file: str) -> str:
        """Guess the mime type of a file or URL based on its extension,
        using eodag extended mimetypes definition

        >>> Mime.guess_file_type('foo.tiff')
        'image/tiff'
        >>> Mime.guess_file_type('foo.grib')
        'application/x-grib'

        :param file: file url or path
        :returns: guessed mime type
        """
        mime_type, _ = mimetypes.guess_type(file, False)
        if mime_type is None:
            mime_type = Mime.DEFAULT
        elif mime_type in Mime.MIME_OVERRIDE:
            mime_type = Mime.MIME_OVERRIDE[mime_type]
        return mime_type

    @staticmethod
    def guess_extension(type: str) -> Optional[str]:
        """Guess extension from mime type, using eodag extended mimetypes definition

        >>> Mime.guess_extension('image/tiff')
        '.tiff'
        >>> Mime.guess_extension('application/x-grib')
        '.grib'

        :param type: mime type
        :returns: guessed file extension
        """
        return mimetypes.guess_extension(type, strict=False)

    @staticmethod
    def guess_extension_from_fileheaders(file: str) -> Optional[str]:
        """Guees file extension from file header"""
        if not os.path.isfile(file):
            return None

        # Already have an extension ?
        filename = os.path.basename(file)
        pos = filename.rfind(".")
        if pos >= 0:
            return filename[pos + 1 :].lower()

        # if it's a local file ad type is not recognized
        if os.path.isfile(file):
            # Try read fileheader
            with open(file, "rb") as fd:
                bytes = fd.read(Mime.EXTENSIONS_FILEHEAD_CHUNKSIZE)
            for ext in Mime.EXTENSIONS_FILEHEADS:
                head = Mime.EXTENSIONS_FILEHEADS[ext]
                if bytes[0 : len(head)] == head:
                    return ext

        return None
