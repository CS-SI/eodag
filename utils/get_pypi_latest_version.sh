#!/usr/bin/env bash

curl https://pypi.org/pypi/eodag/json | python -c "import sys, json; print(json.load(sys.stdin)['info']['version']);"
