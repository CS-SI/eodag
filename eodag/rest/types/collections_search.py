# -*- coding: utf-8 -*-
# Copyright 2023, CS GROUP - France, https://www.csgroup.eu/
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
from typing import Any, Dict, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
)

from eodag.rest.types.eodag_search import EODAGSearch


class CollectionsSearchRequest(BaseModel):
    """Search args for GET collections"""

    model_config = ConfigDict(frozen=True)

    q: Optional[str] = Field(default=None, serialization_alias="free_text")
    platform: Optional[str] = Field(default=None)
    instrument: Optional[str] = Field(default=None)
    constellation: Optional[str] = Field(default=None)

    @model_serializer(mode="wrap")
    def _serialize(self, handler: SerializerFunctionWrapHandler) -> Dict[str, Any]:
        dumped: Dict[str, Any] = handler(self)
        return {EODAGSearch.to_eodag(k): v for k, v in dumped.items()}
