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
from __future__ import annotations

import logging
from time import perf_counter
from typing import TYPE_CHECKING, Dict, Iterable

from fastapi import FastAPI

if TYPE_CHECKING:
    from eodag.api.core import EODataAccessGateway

logger = logging.getLogger("eodag.utils.otel")

try:
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.metrics import CallbackOptions, Instrument, Observation
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics._internal.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    logger.debug("OpenTelemetry library imported")
except ImportError:
    pass


class OverheadTimer:
    """Timer class  to calculate the overhead of a task relative to other sub-tasks."""

    def __init__(self):
        self._start_global_timestamp: float = None
        self._end_global_timestamp: float = None
        self._subtasks_time: float = 0.0

    def start_global_timer(self):
        """Start the timer of the main task."""
        self._start_global_timestamp: float = perf_counter()
        self._subtasks_time: float = 0.0

    def stop_global_timer(self):
        """Stop the timer of the main task."""
        self._end_global_timestamp: float = perf_counter()

    def record_subtask_time(self, time: float):
        """Record the execution time of a subtask.
        :param time: Duration of the subtask.
        :type time: float
        """
        self._subtasks_time += time

    def get_global_time(self) -> float:
        """Calculate the execution time of the main task.

        :returns: The global execution time.
        :rtype: float
        """
        return self._end_global_timestamp - self._start_global_timestamp

    def get_overhead_time(self) -> float:
        """Calculate the overhead time of the main task relative to the sub-tasks.

        :returns: The overhead time.
        :rtype: float
        """
        return self.get_global_time() - self._subtasks_time


class Telemetry:
    """Class to record the telemetry.

    A single instance is created on startup. To collect the telemetry, it must be
    configured by calling :func:`~eodag.utils.otel.Telemetry.configure_instruments`
    """

    def __init__(self):
        self._eodag_api: EODataAccessGateway = None
        self._eodag_app: FastAPI = None
        self._instruments: Dict[str, Instrument] = {}
        self._overhead_timers: Dict[str, OverheadTimer] = {}
        self._instrumented: bool = False

    def configure_instruments(self, eodag_api: EODataAccessGateway, eodag_app: FastAPI):
        """Configure the instrumentation.

        :param eodag_api: EODAG's API instance
        :type eodag_api: EODataAccessGateway
        :param eodag_app: EODAG's app
        :type eodag_app: FastAPI
        """
        self._eodag_api = eodag_api
        self._eodag_app = eodag_app
        self._instruments.clear()
        self._overhead_timers.clear()

        # Start OTLP exporter
        resource = Resource(attributes={SERVICE_NAME: "eodag-serve-rest"})
        # trace
        tracer_provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(OTLPSpanExporter())
        tracer_provider.add_span_processor(processor)
        trace.set_tracer_provider(tracer_provider)
        # metrics
        reader = PeriodicExportingMetricReader(OTLPMetricExporter())
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(meter_provider)

        # FastAPI instrumentation
        FastAPIInstrumentor.instrument_app(
            self._eodag_app, meter_provider=meter_provider
        )

        # Manual instrumentation
        meter = metrics.get_meter("eodag.meter")
        self._instruments["searched_product_types_total"] = meter.create_counter(
            name="eodag.core.searched_product_types_total",
            description="The number of searches by product type",
        )
        self._instruments["downloaded_data_bytes_total"] = meter.create_counter(
            name="eodag.download.downloaded_data_bytes_total",
            description="Measure data downloaded from each provider",
        )
        self._instruments["available_providers"] = meter.create_observable_gauge(
            name="eodag.core.available_providers",
            callbacks=[self._available_providers_callback],
            description="The number available providers",
        )
        self._instruments["available_product_types"] = meter.create_observable_gauge(
            name="eodag.core.available_product_types",
            callbacks=[self._available_product_types_callback],
            description="The number available product types",
        )
        self._instruments["request_duration_seconds"] = meter.create_histogram(
            name="eodag.server.request_duration_seconds",
            unit="s",
            description="Measures the duration of the inbound HTTP request",
        )
        self._instruments["request_overhead_duration_seconds"] = meter.create_histogram(
            name="eodag.server.request_overhead_duration_seconds",
            unit="s",
            description="Measure the duration of the EODAG overhead on the inbound HTTP request",
        )
        self._instruments["outbound_request_duration_seconds"] = meter.create_histogram(
            name="eodag.core.outbound_request_duration_seconds",
            unit="s",
            description="Measure the duration of the outbound HTTP request",
        )
        self._instrumented = True

    def _available_providers_callback(
        self, options: CallbackOptions
    ) -> Iterable[Observation]:
        """OpenTelemetry callback to measure the number of available providers.

        :param options: Options for the callback.
        :type options: CallbackOptions
        :returns: The list observation.
        :rtype: list(dict)
        """
        return [
            Observation(
                len(self._eodag_api.available_providers()),
                {"label": "Available Providers"},
            )
        ]

    def _available_product_types_callback(
        self,
        options: CallbackOptions,
    ) -> Iterable[Observation]:
        """OpenTelemetry callback to measure the number of available product types.

        :param options: Options for the callback.
        :type options: CallbackOptions
        :returns: The list observation.
        :rtype: list(dict)
        """
        return [
            Observation(
                len(self._eodag_api.list_product_types()),
                {"label": "Available Product Types"},
            )
        ]

    def record_downloaded_data(self, provider: str, byte_count: int):
        """Measure the downloaded bytes for a given provider.

        :param provider: The provider from which the data is downloaded.
        :type provider: str
        :param byte_count: Number of bytes downloaded.
        :type byte_count: int
        """
        if not self._instrumented:
            return

        self._instruments["downloaded_data_bytes_total"].add(
            byte_count,
            {"provider": provider},
        )

    def record_searched_product_type(self, product_type: str):
        """Measure the number of times a product type is searched.

        :param product_type: The product type.
        :type product_type: str
        """
        if not self._instrumented:
            return

        self._instruments["searched_product_types_total"].add(
            1, {"product_type": product_type}
        )

    def record_request_duration(self, provider: str, time: float):
        """Measure the duration of the inbound HTTP requests.

        :param provider: The provider selected for the request.
        :type provider: str
        :param time: Duration of the request.
        :type time: float
        """
        if not self._instrumented:
            return

        attributes = {"provider": str(provider)}
        self._instruments["request_duration_seconds"].record(time, attributes)

    def record_request_overhead_duration(self, provider: str, time: float):
        """Measure the duration of the EODAG overhead on the inbound HTTP request.

        :param provider: The provider selected for the request.
        :type provider: str
        :param time: Duration of the overhead.
        :type time: float
        """
        if not self._instrumented:
            return

        attributes = {"provider": str(provider)}
        self._instruments["request_overhead_duration_seconds"].record(time, attributes)

    def record_outbound_request_duration(self, provider: str, time: float):
        """Measure the duration of the outbound HTTP request.

        :param provider: The provider selected for the request.
        :type provider: str
        :param time: Duration of the request.
        :type time: float
        """
        if not self._instrumented:
            return

        attributes = {"provider": str(provider)}
        self._instruments["outbound_request_duration_seconds"].record(time, attributes)

    def create_overhead_timer(self, timer_id: str) -> OverheadTimer:
        """Create a new timer to calculate an overhead.

        The timers are stored in a structure internal to the module otel and should be
        deleted manually after use.

        :param timer_id: The ID to use for the timer.
        :type timer_id: str
        :returns: The new timer.
        :rtype: OverheadTimer
        """
        timer = OverheadTimer()
        self._overhead_timers[timer_id] = OverheadTimer()
        return timer

    def delete_overhead_timer(self, timer_id: str):
        """Delete a timer from the module.

        :param timer_id: The ID of the timer to delete.
        :type timer_id: str
        """
        del self._overhead_timers[timer_id]

    def get_overhead_timer(self, timer_id: str) -> OverheadTimer:
        """Get a previously created timer by ID.

        :param timer_id: The ID of the timer.
        :type timer_id: str
        :returns: The timer.
        :rtype: OverheadTimer
        """
        return self._overhead_timers[timer_id]


telemetry: Telemetry = Telemetry()
