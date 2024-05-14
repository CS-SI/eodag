import logging
from typing import Dict, Optional, Union, Unpack
from urllib.parse import unquote_plus

import copernicusmarine
import geojson
from requests.auth import AuthBase

from eodag import EOProduct
from eodag.plugins.download.base import Download
from eodag.types.download_args import DownloadConf
from eodag.utils import (
    DEFAULT_DOWNLOAD_TIMEOUT,
    DEFAULT_DOWNLOAD_WAIT,
    ProgressCallback,
)
from eodag.utils.exceptions import DownloadError

logger = logging.getLogger("eodag.download.cop_marine")


class CopMarineDownload(Download):
    """Download plugin to download data from the Copernicus Marine provider using the
    copernicusmarine library
    """

    def download(
        self,
        product: EOProduct,
        auth: Optional[Union[AuthBase, Dict[str, str]]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        wait: int = DEFAULT_DOWNLOAD_WAIT,
        timeout: int = DEFAULT_DOWNLOAD_TIMEOUT,
        **kwargs: Unpack[DownloadConf],
    ) -> Optional[str]:
        r"""
        Download method for the Copernicus Marine provider, uses the copernicusmarine library

        :param product: The EO product to download
        :type product: :class:`~eodag.api.product._product.EOProduct`
        :param auth: (optional) authenticated object
        :type auth: Optional[Union[AuthBase, Dict[str, str]]]
        :param progress_callback: (optional) A progress callback
        :type progress_callback: :class:`~eodag.utils.ProgressCallback`
        :param wait: (optional) If download fails, wait time in minutes between two download tries
        :type wait: int
        :param timeout: (optional) If download fails, maximum time in minutes before stop retrying
                        to download
        :type timeout: int
        :param kwargs: `outputs_prefix` (str), `extract` (bool), `delete_archive` (bool)
                        and `dl_url_params` (dict) can be provided as additional kwargs
                        and will override any other values defined in a configuration
                        file or with environment variables.
        :type kwargs: Union[str, bool, dict]
        :returns: The absolute path to the downloaded product in the local filesystem
            (e.g. '/tmp/product.zip' on Linux or
            'C:\\Users\\username\\AppData\\Local\\Temp\\product.zip' on Windows)
        :rtype: str
        """
        if auth:
            copernicusmarine.login(
                username=auth.username,
                password=auth.password,
                skip_if_user_logged_in=True,
            )
        _dc_qs = product.properties["_dc_qs"]
        query_str = unquote_plus(unquote_plus(_dc_qs))
        query_params = geojson.loads(query_str)
        fs_path, record_filename = self._prepare_download(
            product,
            progress_callback=progress_callback,
            **kwargs,
        )
        filename = fs_path.split("/")[-1].replace("zip", "nc")
        dir_path = "/".join(fs_path.split("/")[:-1])
        query_params["output_filename"] = filename
        query_params["output_directory"] = dir_path
        logger.info("start download of data for params %s", str(query_params))
        try:
            copernicusmarine.subset(force_download=True, **query_params)
        except Exception as ex:
            logger.error(str(ex))
            raise DownloadError()
        return dir_path + "/" + filename
