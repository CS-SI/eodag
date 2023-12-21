from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict

from eodag.plugins.apis.base import Api
from eodag.plugins.authentication.base import Authentication
from eodag.plugins.download.base import Download
from eodag.plugins.search.base import Search


class Provider(BaseModel):
    """Model to represent EODAG providers"""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    # properties
    name: str
    public_name: Optional[str] = None
    priority: int = 0
    url: Optional[str] = None
    description: Optional[str] = None
    roles: List[str] = ["host"]
    products: Dict[str, Any] = {}

    # plugins
    search: Union[Search, Api]
    auth: Optional[Authentication] = None
    download: Union[Download, Api]
