#!/usr/bin/env bash

pip search eodag \
| grep -P \
"^eodag[[:space:]]\([0-9]\.[0-9]\.[0-9](.*)\)[[:space:]]*-[[:space:]]Earth[[:space:]]Observation[[:space:]]"\
"Data[[:space:]]Access[[:space:]]Gateway$" \
| cut -d' ' -f2 | sed 's/[()]//g'