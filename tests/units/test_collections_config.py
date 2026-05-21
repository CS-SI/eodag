# -*- coding: utf-8 -*-
# Copyright 2026, CS GROUP - France, https://www.csgroup.eu/
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

from pathlib import Path

import yaml


def test_collection_processing_levels_use_stac_short_names():
    """Default collection processing levels should use STAC short names."""
    collections_path = (
        Path(__file__).parents[2] / "eodag" / "resources" / "collections.yml"
    )

    with open(collections_path, encoding="utf-8") as fh:
        collections = yaml.safe_load(fh)

    long_processing_levels = {
        collection_id: collection["processing:level"]
        for collection_id, collection in collections.items()
        if isinstance(collection, dict)
        and isinstance(collection.get("processing:level"), str)
        and collection["processing:level"].lower().startswith("level")
    }

    assert long_processing_levels == {}
