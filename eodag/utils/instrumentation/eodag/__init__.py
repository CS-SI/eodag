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
"""OpenTelemetry auto-instrumentation for EODAG in server mode"""
import functools
import logging
from timeit import default_timer
from typing import Any, Callable, Collection, Dict, Iterable, List, Optional

from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.metrics import (
    CallbackOptions,
    Counter,
    Histogram,
    Observation,
    get_meter,
)
from opentelemetry.trace import SpanKind, Tracer, get_tracer
from requests import Response

from eodag import EODataAccessGateway
from eodag.plugins.download.base import Download
from eodag.plugins.search.qssearch import QueryStringSearch
from eodag.rest import server
from eodag.utils import ProgressCallback
from eodag.utils.instrumentation.eodag.package import _instruments

logger = logging.getLogger("eodag.utils.instrumentation.eodag")


class OverheadTimer:
    """Timer class  to calculate the overhead of a task relative to other sub-tasks.

    The main task starts and stops the global timer with the start_global_timer and
    stop_global_timer functions. The sub-tasks record their time with the
    record_subtask_time function."""

    def __init__(self) -> None:
        self._start_global_timestamp: float = None
        self._end_global_timestamp: float = None
        self._subtasks_time: float = 0.0

    def start_global_timer(self) -> None:
        """Start the timer of the main task."""
        self._start_global_timestamp: float = default_timer()
        self._subtasks_time: float = 0.0

    def stop_global_timer(self) -> None:
        """Stop the timer of the main task."""
        self._end_global_timestamp: float = default_timer()

    def record_subtask_time(self, time: float):
        """Record the execution time of a subtask.

        :param time: Duration of the subtask.
        :type time: float
        """
        self._subtasks_time += time

    def get_global_time(self) -> float:
        """Returns the execution time of the main task.

        :returns: The global execution time.
        :rtype: float
        """
        return self._end_global_timestamp - self._start_global_timestamp

    def get_subtasks_time(self) -> float:
        """Returns the cumulative time of the sub-tasks.

        :returns: The sub-tasks execution time.
        :rtype: float
        """
        return self._subtasks_time

    def get_overhead_time(self) -> float:
        """Returns the overhead time of the main task relative to the sub-tasks.

        :returns: The overhead time.
        :rtype: float
        """
        return self.get_global_time() - self._subtasks_time


def _instrument_search(
    tracer: Tracer,
    searched_product_types_counter: Counter,
    request_duration_seconds: Histogram,
    outbound_request_duration_seconds_histogram: Histogram,
    request_overhead_duration_seconds: Histogram,
) -> None:
    """Add the instrumentation for search operations in server mode.

    :param tracer: OpenTelemetry tracer.
    :type tracer: Tracer
    :param searched_product_types_counter: Searched product types counter.
    :type searched_product_types_counter: Counter
    :param request_duration_seconds: Request duration histogram.
    :type request_duration_seconds: Histogram
    :param outbound_request_duration_seconds_histogram: Outbound request duration histogram.
    :type outbound_request_duration_seconds_histogram: Histogram
    :param request_overhead_duration_seconds: EODAG overhead histogram.
    :type request_overhead_duration_seconds: Histogram
    """
    overhead_timers: Dict[str, OverheadTimer] = {}
    trace_attributes: Dict[str, Any] = {}

    wrapped_server_search_stac_items = server.search_stac_items

    @functools.wraps(wrapped_server_search_stac_items)
    def wrapper_server_search_stac_items(
        url: str,
        arguments: Dict[str, Any],
        root: str = "/",
        catalogs: List[str] = [],
        provider: Optional[str] = None,
        method: Optional[str] = "GET",
    ) -> Dict[str, Any]:

        # use catalogs from path or if it is empty, collections from args
        collections = arguments.get("collections", None)
        product_type = None
        if catalogs:
            product_type = catalogs[0]
        elif collections:
            if isinstance(collections, str):
                product_type = collections.split(",")[0] if collections else None
            elif isinstance(collections, list) and len(collections) > 0:
                product_type = collections[0]
            if not product_type:
                logger.warning("Collections argument type should be Array")

        span_name = "core-search"
        attributes = {}
        if provider:
            attributes["provider"] = provider
        if product_type:
            attributes["product_type"] = product_type

        with tracer.start_as_current_span(
            span_name, kind=SpanKind.CLIENT, attributes=attributes
        ) as span:
            exception = None
            trace_id = span.get_span_context().trace_id
            timer = OverheadTimer()
            overhead_timers[trace_id] = timer
            trace_attributes[trace_id] = attributes
            timer.start_global_timer()

            # Call wrapped function
            try:
                result = wrapped_server_search_stac_items(
                    url, arguments, root, catalogs, provider, method
                )
            except Exception as exc:
                exception = exc
            finally:
                timer.stop_global_timer()

            # Retrieve possible updated attributes
            attributes = trace_attributes[trace_id]
            span.set_attributes(attributes)

            # Product type counter
            searched_product_types_counter.add(1, attributes)

            # Duration histograms
            request_duration_seconds.record(
                timer.get_global_time(), attributes=attributes
            )
            request_overhead_duration_seconds.record(
                timer.get_overhead_time(), attributes=attributes
            )
            del overhead_timers[trace_id]
            del trace_attributes[trace_id]

            if exception is not None:
                raise exception.with_traceback(exception.__traceback__)

        return result

    wrapper_server_search_stac_items.opentelemetry_instrumentation_eodag_applied = True
    server.search_stac_items = wrapper_server_search_stac_items

    wrapped_qssearch_request = QueryStringSearch._request

    @functools.wraps(wrapped_qssearch_request)
    def wrapper_qssearch_request(
        self,
        url: str,
        info_message: Optional[str] = None,
        exception_message: Optional[str] = None,
    ) -> Response:

        span_name = "core-search"
        # This is the provider's product type.
        attributes = {
            "provider": self.provider,
            "product_type": self.product_type_def_params["productType"],
        }

        with tracer.start_as_current_span(
            span_name, kind=SpanKind.CLIENT, attributes=attributes
        ) as span:
            exception = None
            trace_id = span.get_span_context().trace_id
            timer = overhead_timers.get(trace_id)
            parent_attributes = trace_attributes.get(trace_id)
            parent_attributes["provider"] = self.provider
            attributes = parent_attributes

            start_time = default_timer()

            # Call wrapped function
            try:
                result = wrapped_qssearch_request(
                    self, url, info_message, exception_message
                )
            except Exception as exc:
                exception = exc
            finally:
                elapsed_time = default_timer() - start_time

            # Duration histograms
            # If the search is called by an operation other than the download, then no
            # timer is created and the metric is not generated.
            if timer:
                timer.record_subtask_time(elapsed_time)
                outbound_request_duration_seconds_histogram.record(
                    elapsed_time, attributes=attributes
                )

            if exception is not None:
                raise exception.with_traceback(exception.__traceback__)

        return result

    wrapper_qssearch_request.opentelemetry_instrumentation_eodag_applied = True
    QueryStringSearch._request = wrapper_qssearch_request


def _instrument_download(tracer: Tracer, downloaded_data_counter: Counter):
    """Add the instrumentation for download operations in server mode.

    :param tracer: OpenTelemetry tracer.
    :type tracer: Tracer
    :param downloaded_data_counter: Downloaded data counter.
    :type downloaded_data_counter: Counter
    """
    wrapped_progress_callback_decorator = Download.progress_callback_decorator

    @functools.wraps(wrapped_progress_callback_decorator)
    def wrapper_progress_callback_decorator(
        self, progress_callback: ProgressCallback, **decorator_kwargs: Any
    ) -> Callable[[Any, Any], None]:
        @functools.wraps(progress_callback)
        def progress_callback_wrapper(*args: Any, **kwargs: Any) -> None:
            increment = args[0]
            attributes = {
                "provider": decorator_kwargs["provider"],
                "product_type": decorator_kwargs["product_type"],
            }
            downloaded_data_counter.add(increment, attributes)
            progress_callback(*args, **kwargs)

        return progress_callback_wrapper

    wrapper_progress_callback_decorator.opentelemetry_instrumentation_eodag_applied = (
        True
    )
    Download.progress_callback_decorator = wrapper_progress_callback_decorator


class EODAGInstrumentor(BaseInstrumentor):
    """An instrumentor for EODAG"""

    def __init__(self, eodag_api: EODataAccessGateway = None) -> None:
        super().__init__()
        self._eodag_api = eodag_api

    def instrumentation_dependencies(self) -> Collection[str]:
        """Return a list of python packages with versions that the will be instrumented.

        :returns: The list of instrumented python packages.
        :rtype: Collection[str]"""
        return _instruments

    def _available_providers_callback(
        self, options: CallbackOptions
    ) -> Iterable[Observation]:
        """OpenTelemetry callback to measure the number of available providers.

        :param options: Options for the callback.
        :type options: CallbackOptions
        :returns: The list observation.
        :rtype: Iterable[Observation]
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
        :rtype: Iterable[Observation]
        """
        return [
            Observation(
                len(self._eodag_api.list_product_types()),
                {"label": "Available Product Types"},
            )
        ]

    def _instrument(self, **kwargs) -> None:
        """Instruments EODAG"""
        tracer_provider = kwargs.get("tracer_provider")
        tracer = get_tracer(__name__, tracer_provider=tracer_provider)
        meter_provider = kwargs.get("meter_provider")
        meter = get_meter(__name__, meter_provider=meter_provider)

        if self._eodag_api:
            meter.create_observable_gauge(
                name="eodag.core.available_providers",
                callbacks=[self._available_providers_callback],
                description="The number available providers",
            )
            meter.create_observable_gauge(
                name="eodag.core.available_product_types",
                callbacks=[self._available_product_types_callback],
                description="The number available product types",
            )

        downloaded_data_counter = meter.create_counter(
            name="eodag.download.downloaded_data_bytes_total",
            description="Measure data downloaded from each provider and product type",
        )
        _instrument_download(tracer, downloaded_data_counter)

        searched_product_types_counter = meter.create_counter(
            name="eodag.core.searched_product_types_total",
            description="The number of searches by provider and product type",
        )
        request_duration_seconds = meter.create_histogram(
            name="eodag.server.request_duration_seconds",
            unit="s",
            description="Measures the duration of the inbound HTTP request",
        )
        outbound_request_duration_seconds = meter.create_histogram(
            name="eodag.core.outbound_request_duration_seconds",
            unit="s",
            description="Measure the duration of the outbound HTTP request",
        )
        request_overhead_duration_seconds = meter.create_histogram(
            name="eodag.server.request_overhead_duration_seconds",
            unit="s",
            description="Measure the duration of the EODAG overhead on the inbound HTTP request",
        )
        _instrument_search(
            tracer,
            searched_product_types_counter,
            request_duration_seconds,
            outbound_request_duration_seconds,
            request_overhead_duration_seconds,
        )

    def _uninstrument(self, **kwargs) -> None:
        """Uninstrument the library.

        This only works if no other module also patches eodag"""
        patches = [
            (server, "search_stac_items"),
            (QueryStringSearch, "_request"),
            (Download, "progress_callback_decorator"),
        ]
        for p in patches:
            instr_func = getattr(p[0], p[1])
            if not getattr(
                instr_func,
                "opentelemetry_instrumentation_eodag_applied",
                False,
            ):
                continue
            setattr(p[0], p[1], instr_func.__wrapped__)
