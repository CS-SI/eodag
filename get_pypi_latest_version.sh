#!/usr/bin/env bash

curl https://pypi.org/pypi/eodag/json | python -c \
"import sys, json; v = list(json.load(sys.stdin)['releases'].keys()); v.sort(); print(v[-1]);"
