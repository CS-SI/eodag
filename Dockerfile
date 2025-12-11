# Copyright 2025, CS GROUP - France, https://www.csgroup.eu/
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

FROM python:alpine3.13

LABEL author="CS GROUP - France"

WORKDIR /app

COPY eodag/ eodag/
COPY setup.cfg pyproject.toml README.rst LICENSE MANIFEST.in ./

# build-base is required to enable logging
RUN apk add --no-cache build-base && \
    pip install --no-cache-dir ".[all-providers]" && \
    apk del build-base

# Create a non-root user to run the application
RUN addgroup -g 1000 eodag && \
    adduser -u 1000 -G eodag \
        -h /home/eodag \
        -s /bin/sh \
        -D eodag
USER eodag

ENTRYPOINT ["eodag"]
CMD ["--help"]
