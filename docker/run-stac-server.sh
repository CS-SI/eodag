#!/bin/bash

# some pre-start operation

LOGGING_OPTIONS=""
re='^[0-9]+$'
if [[ ${EODAG_LOGGING} =~ $re ]] && [ "${EODAG_LOGGING} " -gt "0" ]; then
   LOGGING_OPTIONS="-"$(printf '%0.sv' $(seq 1 ${EODAG_LOGGING}))
else
    echo "Logging level can be changed using EODAG_LOGGING environment variable [1-3]"
fi

# start
eodag $LOGGING_OPTIONS serve-rest -w
