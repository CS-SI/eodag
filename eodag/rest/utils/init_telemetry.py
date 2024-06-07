# -*- coding: utf-8 -*-
# Copyright 2024, CS Systemes d'Information, https://www.csgroup.eu/
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
"""Programmatically instrument the EODAG server.

Set the the variable OTEL_EXPORTER_OTLP_ENDPOINT and optionally OTEL_METRIC_EXPORT_INTERVAL before launching
the EODAG server:

export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_METRIC_EXPORT_INTERVAL="5000"

"""
from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.eodag import EODAGInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.metrics import Histogram
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics._internal.aggregation import (
    ExplicitBucketHistogramAggregation,
)
from opentelemetry.sdk.metrics._internal.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics._internal.view import View
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from eodag.utils.logging import setup_logging

if TYPE_CHECKING:
    from fastapi import FastAPI

    from eodag import EODataAccessGateway


logger = logging.getLogger("opentelemetry.instrumentation.eodag")


def instrument_server(
    eodag_api: EODataAccessGateway,
    fastapi_app: FastAPI = None,
) -> None:
    """Instrument EODAG server."""
    # Start OTLP exporter
    resource = Resource(attributes={SERVICE_NAME: "eodag-serve-rest"})
    # trace
    tracer_provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(OTLPSpanExporter())
    tracer_provider.add_span_processor(processor)
    trace.set_tracer_provider(tracer_provider)
    # metrics
    reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    view_histograms: View = View(
        instrument_type=Histogram,
        aggregation=ExplicitBucketHistogramAggregation(
            boundaries=(
                0.25,
                0.50,
                0.75,
                1.0,
                1.5,
                2.0,
                3.0,
                4.0,
                5.0,
                6.0,
                7.0,
                8.0,
                9.0,
                10.0,
            )
        ),
    )
    view_overhead_histograms: View = View(
        instrument_type=Histogram,
        instrument_name="*overhead*",
        aggregation=ExplicitBucketHistogramAggregation(
            boundaries=(
                0.030,
                0.040,
                0.050,
                0.060,
                0.070,
                0.080,
                0.090,
                0.100,
                0.125,
                0.150,
                0.175,
                0.200,
                0.250,
                0.500,
            )
        ),
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[reader],
        views=(
            view_histograms,
            view_overhead_histograms,
        ),
    )
    metrics.set_meter_provider(meter_provider)

    # Auto instrumentation
    if fastapi_app:
        logger.debug("Instrument FastAPI app")
        FastAPIInstrumentor.instrument_app(
            app=fastapi_app,
            tracer_provider=tracer_provider,
            meter_provider=meter_provider,
        )
    logger.debug("Instrument EODAG app")
    EODAGInstrumentor(eodag_api).instrument(
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
    )


def serve_rest(
    fastapi_app: FastAPI,
    verbose: int,
    daemon: bool,
    world: bool,
    port: int,
    config: str,
    locs: str,
    debug: bool,
) -> None:
    """Serve EODAG functionalities through a WEB interface."""
    setup_logging(verbose=verbose)
    try:
        import uvicorn
    except ImportError:
        raise ImportError(
            "Feature not available, please install eodag[server] or eodag[all]"
        )

    # Set the settings of the app
    # IMPORTANT: the order of imports counts here (first we override the settings,
    # then we import the app so that the updated settings is taken into account in
    # the app initialization)
    if config:
        os.environ["EODAG_CFG_FILE"] = config

    if locs:
        os.environ["EODAG_LOCS_CFG_FILE"] = locs

    bind_host = "127.0.0.1"
    if world:
        bind_host = "0.0.0.0"
    if daemon:
        try:
            pid = os.fork()
        except OSError as e:
            raise Exception("%s [%d]" % (e.strerror, e.errno))

        if pid == 0:
            os.setsid()
            uvicorn.run(fastapi_app, host=bind_host, port=port)
        else:
            sys.exit(0)
    else:
        logging_config = uvicorn.config.LOGGING_CONFIG
        if debug:
            logging_config["loggers"]["uvicorn"]["level"] = "DEBUG"
            logging_config["loggers"]["uvicorn.error"]["level"] = "DEBUG"
            logging_config["loggers"]["uvicorn.access"]["level"] = "DEBUG"
            logging_config["formatters"]["default"][
                "fmt"
            ] = "%(asctime)-15s %(name)-32s [%(levelname)-8s] (%(module)-17s) %(message)s"
            logging_config["loggers"]["eodag"] = {
                "handlers": ["default"],
                "level": "DEBUG" if debug else "INFO",
                "propagate": False,
            }
        uvicorn.run(
            fastapi_app,
            host=bind_host,
            port=port,
            reload=debug,
            log_config=logging_config,
        )


if __name__ == "__main__":
    from eodag.rest.core import eodag_api
    from eodag.rest.server import app as fastapi_app

    instrument_server(eodag_api, fastapi_app)
    serve_rest(
        fastapi_app,
        verbose=1,
        daemon=False,
        world=False,
        port=5000,
        config=None,
        locs=None,
        debug=False,
    )
